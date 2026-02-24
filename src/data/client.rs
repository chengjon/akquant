use crate::error::AkQuantError;
use crate::event::Event;
use crate::model::Bar;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rust_decimal::prelude::*;
use std::collections::{HashMap, VecDeque};
use std::fs::File;
use std::sync::mpsc;
use std::time::Duration;

#[inline]
fn normalize_timestamp(ts: i64) -> i64 {
    let abs_ts = ts.abs();
    if abs_ts < 100_000_000_000 {
        // Seconds (< 10^11, up to year ~5138)
        ts * 1_000_000_000
    } else if abs_ts < 100_000_000_000_000 {
        // Milliseconds (< 10^14, up to year ~5138)
        ts * 1_000_000
    } else if abs_ts < 100_000_000_000_000_000 {
        // Microseconds (< 10^17, up to year ~5138)
        ts * 1_000
    } else {
        // Nanoseconds
        ts
    }
}

/// Data Client Trait for streaming or in-memory data
pub trait DataClient: Send {
    fn peek_timestamp(&mut self) -> Option<i64>;
    fn next(&mut self) -> Option<Event>;
    fn add(&mut self, event: Event) -> Result<(), AkQuantError>;
    fn sort(&mut self);
    fn len_hint(&self) -> Option<usize>;

    /// 是否为实时数据源
    fn is_live(&self) -> bool {
        false
    }

    /// 阻塞等待下一个事件的时间戳 (用于实时模式)
    fn wait_peek(&mut self, _timeout: Duration) -> Option<i64> {
        self.peek_timestamp()
    }
}

/// Simulated Data Client (In-Memory)
pub struct SimulatedDataClient {
    pub events: VecDeque<Event>,
}

impl SimulatedDataClient {
    pub fn new() -> Self {
        Self {
            events: VecDeque::new(),
        }
    }
}

impl DataClient for SimulatedDataClient {
    fn peek_timestamp(&mut self) -> Option<i64> {
        self.events.front().map(|e| match e {
            Event::Bar(b) => b.timestamp,
            Event::Tick(t) => t.timestamp,
            Event::ExecutionReport(_, Some(trade)) => trade.timestamp,
            _ => 0, // Fallback for events without timestamp
        })
    }

    fn next(&mut self) -> Option<Event> {
        self.events.pop_front()
    }

    fn add(&mut self, event: Event) -> Result<(), AkQuantError> {
        self.events.push_back(event);
        Ok(())
    }

    fn sort(&mut self) {
        self.events.make_contiguous().sort_by_key(|e| match e {
            Event::Bar(b) => b.timestamp,
            Event::Tick(t) => t.timestamp,
            Event::ExecutionReport(_, Some(trade)) => trade.timestamp,
            _ => 0,
        });
    }

    fn len_hint(&self) -> Option<usize> {
        Some(self.events.len())
    }
}

/// CSV Data Client (Streaming)
pub struct CsvDataClient {
    reader: csv::Reader<File>,
    current: Option<Event>,
    symbol: String,
}

impl CsvDataClient {
    pub fn new(path: &str, symbol: &str) -> PyResult<Self> {
        let file = File::open(path).map_err(|e| PyValueError::new_err(e.to_string()))?;
        let reader = csv::ReaderBuilder::new()
            .has_headers(true)
            .from_reader(file);

        Ok(Self {
            reader,
            current: None,
            symbol: symbol.to_string(),
        })
    }

    fn read_next(&mut self) -> Option<Event> {
        // Assume CSV columns: timestamp, open, high, low, close, volume
        // Or using serde with a struct.
        // Let's use string records and parse manually for flexibility or define a struct.
        // Defining a struct is better.

        // Internal struct for CSV row
        #[derive(serde::Deserialize)]
        struct CsvRow {
            timestamp: i64,
            open: f64,
            high: f64,
            low: f64,
            close: f64,
            volume: f64,
        }

        let mut record = csv::StringRecord::new();
        if self.reader.read_record(&mut record).ok()? {
            // Deserialize
            let row: CsvRow = record.deserialize(self.reader.headers().ok()).ok()?;

            let bar = Bar {
                timestamp: normalize_timestamp(row.timestamp),
                open: Decimal::from_f64(row.open).unwrap_or_else(|| {
                    log::warn!("Invalid open price {}, defaulting to 0.0", row.open);
                    Decimal::ZERO
                }),
                high: Decimal::from_f64(row.high).unwrap_or_else(|| {
                    log::warn!("Invalid high price {}, defaulting to 0.0", row.high);
                    Decimal::ZERO
                }),
                low: Decimal::from_f64(row.low).unwrap_or_else(|| {
                    log::warn!("Invalid low price {}, defaulting to 0.0", row.low);
                    Decimal::ZERO
                }),
                close: Decimal::from_f64(row.close).unwrap_or_else(|| {
                    log::warn!("Invalid close price {}, defaulting to 0.0", row.close);
                    Decimal::ZERO
                }),
                volume: Decimal::from_f64(row.volume).unwrap_or_else(|| {
                    log::warn!("Invalid volume {}, defaulting to 0.0", row.volume);
                    Decimal::ZERO
                }),
                symbol: self.symbol.clone(),
                extra: HashMap::new(),
            };
            Some(Event::Bar(bar))
        } else {
            None
        }
    }
}

impl DataClient for CsvDataClient {
    fn peek_timestamp(&mut self) -> Option<i64> {
        if self.current.is_none() {
            self.current = self.read_next();
        }

        self.current.as_ref().map(|e| match e {
            Event::Bar(b) => b.timestamp,
            Event::Tick(t) => t.timestamp,
            Event::ExecutionReport(_, Some(trade)) => trade.timestamp,
            _ => 0,
        })
    }

    fn next(&mut self) -> Option<Event> {
        if self.current.is_none() {
            self.current = self.read_next();
        }
        self.current.take()
    }

    fn add(&mut self, _event: Event) -> Result<(), AkQuantError> {
        Err(AkQuantError::DataError(
            "Cannot add data to a streaming CSV provider".to_string(),
        ))
    }

    fn sort(&mut self) {
        // Assume CSV is sorted or ignore
    }

    fn len_hint(&self) -> Option<usize> {
        None
    }
}

/// Realtime Data Client (Channel)
/// 适用于 CTP 等实时数据推送场景
pub struct RealtimeDataClient {
    rx: mpsc::Receiver<Event>,
    sender: mpsc::Sender<Event>, // Keep sender to clone for external use
    current: Option<Event>,
}

impl RealtimeDataClient {
    pub fn new() -> Self {
        let (tx, rx) = mpsc::channel();
        Self {
            rx,
            sender: tx,
            current: None,
        }
    }

    pub fn get_sender(&self) -> mpsc::Sender<Event> {
        self.sender.clone()
    }
}

impl DataClient for RealtimeDataClient {
    fn peek_timestamp(&mut self) -> Option<i64> {
        // Try to read from channel non-blocking
        if self.current.is_none() {
            match self.rx.try_recv() {
                Ok(event) => self.current = Some(event),
                Err(_) => return None, // Empty or Disconnected
            }
        }

        self.current.as_ref().map(|e| match e {
            Event::Bar(b) => b.timestamp,
            Event::Tick(t) => t.timestamp,
            Event::ExecutionReport(_, Some(trade)) => trade.timestamp,
            _ => 0,
        })
    }

    fn next(&mut self) -> Option<Event> {
        if self.current.is_some() {
            return self.current.take();
        }
        self.rx.try_recv().ok()
    }

    fn add(&mut self, event: Event) -> Result<(), AkQuantError> {
        self.sender
            .send(event)
            .map_err(|e| AkQuantError::DataError(e.to_string()))
    }

    fn sort(&mut self) {
        // Live data cannot be sorted
    }

    fn len_hint(&self) -> Option<usize> {
        None
    }

    fn is_live(&self) -> bool {
        true
    }

    fn wait_peek(&mut self, timeout: Duration) -> Option<i64> {
        if self.current.is_some() {
            return self.peek_timestamp();
        }
        match self.rx.recv_timeout(timeout) {
            Ok(event) => {
                self.current = Some(event);
                self.peek_timestamp()
            }
            Err(_) => None,
        }
    }
}

pub enum FeedAction {
    Event(Box<Event>),
    Timer(i64),
    Wait,
    End,
}
