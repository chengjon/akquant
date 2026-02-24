use crate::context::EngineContext;
use crate::data::FeedAction;
use crate::engine::Engine;
use crate::event::Event;
use crate::model::{Bar, ExecutionMode, OrderStatus, TradingSession};
use crate::pipeline::processor::{Processor, ProcessorResult};
use pyo3::prelude::*;
use rust_decimal::Decimal;
use std::collections::HashSet;

pub struct ChannelProcessor;

impl Processor for ChannelProcessor {
    fn process(&mut self, engine: &mut Engine, _py: Python<'_>, _strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        let mut trades_to_process = Vec::new();
        while let Some(event) = engine.event_manager.try_recv() {
            match event {
                Event::OrderRequest(mut order) => {
                    // 1. Risk Check & Adjustment
                    // Create Context
                    let ctx = EngineContext {
                        instruments: &engine.instruments,
                        portfolio: &engine.state.portfolio,
                        last_prices: &engine.last_prices,
                        market_model: engine.market_manager.model.as_ref(),
                        execution_mode: engine.execution_mode,
                        bar_index: engine.bar_count,
                        session: engine.clock.session,
                        active_orders: &engine.state.order_manager.active_orders,
                    };

                    if let Err(err) = engine.risk_manager.check_and_adjust(&mut order, &ctx) {
                        // Rejected
                        order.status = OrderStatus::Rejected;
                        order.reject_reason = err.to_string();
                        order.updated_at = engine.clock.timestamp().unwrap_or(0);

                        // Send ExecutionReport (Rejected)
                        let _ = engine.event_manager.send(Event::ExecutionReport(order, None));
                    } else {
                        // Validated -> Send OrderValidated
                        let _ = engine.event_manager.send(Event::OrderValidated(order));
                    }
                }
                Event::OrderValidated(order) => {
                    // 2. Send to Execution Client
                    engine.execution_model.on_order(order.clone());
                    // Add to local active (Strategy View)
                    engine.state.order_manager.add_active_order(order);
                }
                Event::ExecutionReport(order, trade) => {
                    // 3. Update Order State
                    engine.state.order_manager.on_execution_report(order);

                    // 4. Process Trade (if any)
                    if let Some(t) = trade {
                        trades_to_process.push(t);
                    }
                }
                _ => {}
            }
        }

        if !trades_to_process.is_empty() {
            engine.state.order_manager.process_trades(
                trades_to_process,
                &mut engine.state.portfolio,
                &engine.instruments,
                engine.market_manager.model.as_ref(),
                &engine.history_buffer,
                &engine.last_prices,
            );
        }

        Ok(ProcessorResult::Next)
    }
}

pub struct DataProcessor {
    last_timestamp: i64,
    seen_symbols: HashSet<String>,
}

impl Default for DataProcessor {
    fn default() -> Self {
        Self::new()
    }
}

impl DataProcessor {
    pub fn new() -> Self {
        Self {
            last_timestamp: 0,
            seen_symbols: HashSet::new(),
        }
    }

    fn fill_missing_bars(&self, engine: &Engine) {
        if self.last_timestamp == 0 {
            return;
        }
        if let Ok(mut buffer) = engine.history_buffer.write() {
            for (symbol, _) in engine.instruments.iter() {
                if !self.seen_symbols.contains(symbol)
                    && let Some(&last_price) = engine.last_prices.get(symbol) {
                        // Create synthetic bar
                        let bar = Bar {
                            timestamp: self.last_timestamp,
                            symbol: symbol.clone(),
                            open: last_price,
                            high: last_price,
                            low: last_price,
                            close: last_price,
                            volume: Decimal::ZERO,
                            extra: Default::default(),
                        };
                        buffer.update(&bar);
                    }
            }
        }
    }
}

impl Processor for DataProcessor {
    fn process(&mut self, engine: &mut Engine, py: Python<'_>, _strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        let next_timer_time = engine.timers.peek().map(|t| t.timestamp);
        let action = engine.state.feed.next_action(next_timer_time, py);

        match action {
            FeedAction::Wait => Ok(ProcessorResult::Loop),
            FeedAction::End => {
                self.fill_missing_bars(engine);
                Ok(ProcessorResult::Break)
            }
            FeedAction::Timer(_timestamp) => {
                if let Some(timer) = engine.timers.pop() {
                    let local_dt = Engine::local_datetime_from_ns(timer.timestamp, engine.timezone_offset);
                    let session = engine.market_manager.get_session_status(local_dt.time());
                    engine.clock.update(timer.timestamp, session);
                    if engine.force_session_continuous {
                        engine.clock.session = TradingSession::Continuous;
                    }
                    engine.current_event = Some(Event::Timer(timer));
                }
                Ok(ProcessorResult::Next)
            }
            FeedAction::Event(event) => {
                let event = *event;
                let timestamp = match &event {
                    Event::Bar(b) => b.timestamp,
                    Event::Tick(t) => t.timestamp,
                    _ => 0,
                };

                if self.last_timestamp != 0 && timestamp > self.last_timestamp {
                    self.fill_missing_bars(engine);
                    self.seen_symbols.clear();

                    engine.bar_count += 1;
                    if let Some(pb) = &engine.progress_bar {
                        pb.inc(1);
                    }
                }
                self.last_timestamp = timestamp;

                let local_dt = Engine::local_datetime_from_ns(timestamp, engine.timezone_offset);

                // Update Market Manager (Session)
                let session = engine.market_manager.get_session_status(local_dt.time());

                engine.clock.update(timestamp, session);
                if engine.force_session_continuous {
                    engine.clock.session = TradingSession::Continuous;
                }

                // Daily Snapshot & Settlement
                let local_date = local_dt.date_naive();
                if engine.current_date != Some(local_date) {
                    if engine.current_date.is_some() {
                        engine.statistics_manager.record_snapshot(
                            timestamp,
                            &engine.state.portfolio,
                            &engine.instruments,
                            &engine.last_prices,
                            &engine.state.order_manager.trade_tracker,
                        );
                    }
                    engine.current_date = Some(local_date);

                    // Process Corporate Actions (Split/Dividend)
                    engine.corporate_action_manager.process_date(
                        local_date,
                        &mut engine.state.portfolio,
                        &mut engine.state.order_manager.trade_tracker,
                    );

                    // Settlement Manager (T+1, Option Expiry, Day Order Expiry)
                    let mut expired_orders = Vec::new();
                    let settlement_ctx = crate::settlement::manager::SettlementContext {
                        date: local_date,
                        instruments: &engine.instruments,
                        last_prices: &engine.last_prices,
                        market_manager: &engine.market_manager,
                    };
                    engine.settlement_manager.process_daily_settlement(
                        &mut engine.state.portfolio,
                        &mut engine.state.order_manager.active_orders,
                        &mut expired_orders,
                        &settlement_ctx,
                    );

                    for o in expired_orders {
                        engine.state.order_manager.orders.push(o);
                    }
                }

                if let Event::Bar(ref b) = event {
                    self.seen_symbols.insert(b.symbol.clone());
                    // Update History Buffer
                    if let Ok(mut buffer) = engine.history_buffer.write() {
                        buffer.update(b);
                    }
                    // println!("DataProcessor: Bar Symbol={}, TS={}", b.symbol, b.timestamp);
                }

                engine.current_event = Some(event);
                Ok(ProcessorResult::Next)
            }
        }
    }
}

pub struct StrategyProcessor;

impl Processor for StrategyProcessor {
    fn process(&mut self, engine: &mut Engine, _py: Python<'_>, strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        if let Some(event) = engine.current_event.clone() {
            let (new_orders, new_timers, canceled_ids) = engine.call_strategy(strategy, &event)?;

            for id in canceled_ids {
                engine.execution_model.on_cancel(&id);
            }
            for order in new_orders {
                let _ = engine.event_manager.send(Event::OrderRequest(order));
            }
            for t in new_timers {
                engine.timers.push(t);
            }
        }
        Ok(ProcessorResult::Next)
    }
}

#[derive(Debug)]
pub enum ExecutionPhase {
    PreStrategy,
    PostStrategy,
}

pub struct ExecutionProcessor {
    phase: ExecutionPhase,
}

impl ExecutionProcessor {
    pub fn new(phase: ExecutionPhase) -> Self {
        Self { phase }
    }
}

impl Processor for ExecutionProcessor {
    fn process(&mut self, engine: &mut Engine, _py: Python<'_>, _strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        let should_run = match self.phase {
            ExecutionPhase::PreStrategy => matches!(
                engine.execution_mode,
                ExecutionMode::NextOpen | ExecutionMode::NextAverage | ExecutionMode::NextHighLowMid
            ),
            ExecutionPhase::PostStrategy => matches!(
                engine.execution_mode,
                ExecutionMode::CurrentClose
            ),
        };

        if !should_run {
            return Ok(ProcessorResult::Next);
        }

        if let Some(event) = engine.current_event.clone() {
            match event {
                Event::Bar(_) | Event::Tick(_) => {
                    // Create Context
                    let ctx = EngineContext {
                        instruments: &engine.instruments,
                        portfolio: &engine.state.portfolio,
                        last_prices: &engine.last_prices,
                        market_model: engine.market_manager.model.as_ref(),
                        execution_mode: engine.execution_mode,
                        bar_index: engine.bar_count,
                        session: engine.clock.session,
                        active_orders: &engine.state.order_manager.active_orders,
                    };

                    let reports = engine.execution_model.on_event(&event, &ctx);
                    for report in reports {
                        let _ = engine.event_manager.send(report);
                    }
                }
                _ => {}
            }
        }
        Ok(ProcessorResult::Next)
    }
}

pub struct CleanupProcessor;

impl Processor for CleanupProcessor {
    fn process(&mut self, engine: &mut Engine, _py: Python<'_>, _strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        engine.state.order_manager.cleanup_finished_orders();
        Ok(ProcessorResult::Next)
    }
}

pub struct StatisticsProcessor;

impl Processor for StatisticsProcessor {
    fn process(&mut self, engine: &mut Engine, _py: Python<'_>, _strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        if let Some(Event::Bar(_) | Event::Tick(_)) = engine.current_event.clone()
            && let Some(timestamp) = engine.clock.timestamp() {
                let equity = engine.state.portfolio.calculate_equity(&engine.last_prices, &engine.instruments);
                engine.statistics_manager.update(timestamp, equity, engine.state.portfolio.cash);
            }
        Ok(ProcessorResult::Next)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::engine::Engine;
    use crate::model::{Instrument, AssetType, InstrumentEnum, StockInstrument, Bar};
    use rust_decimal_macros::dec;
    use std::collections::HashMap;
    use std::sync::Arc;

    fn create_instrument(symbol: &str) -> Instrument {
        Instrument {
            asset_type: AssetType::Stock,
            inner: InstrumentEnum::Stock(StockInstrument {
                symbol: symbol.to_string(),
                lot_size: dec!(100),
                tick_size: dec!(0.01),
            }),
        }
    }

    #[test]
    fn test_data_alignment_late_fill() {
        // pyo3::prepare_freethreaded_python() is deprecated and not needed with auto-initialize feature

        let mut engine = Engine::new();
        engine.instruments.insert("A".to_string(), create_instrument("A"));
        engine.instruments.insert("B".to_string(), create_instrument("B"));

        engine.last_prices.insert("A".to_string(), dec!(100));
        engine.last_prices.insert("B".to_string(), dec!(200));

        let mut processor = DataProcessor::new();

        let bar_t1_a = Bar {
            timestamp: 1000,
            symbol: "A".to_string(),
            open: dec!(100),
            high: dec!(100),
            low: dec!(100),
            close: dec!(100),
            volume: dec!(100),
            extra: HashMap::new(),
        };

        let bar_t2_b = Bar {
            timestamp: 2000,
            symbol: "B".to_string(),
            open: dec!(205),
            high: dec!(205),
            low: dec!(205),
            close: dec!(205),
            volume: dec!(200),
            extra: HashMap::new(),
        };

        let bar_t3_a = Bar {
            timestamp: 3000,
            symbol: "A".to_string(),
            open: dec!(102),
            high: dec!(102),
            low: dec!(102),
            close: dec!(102),
            volume: dec!(100),
            extra: HashMap::new(),
        };

        engine.state.feed.add_bar(bar_t1_a).unwrap();
        engine.state.feed.add_bar(bar_t2_b).unwrap();
        engine.state.feed.add_bar(bar_t3_a).unwrap();

        // Use Python::attach as recommended by PyO3 0.28+
        pyo3::Python::attach(|py| {
            let locals = py.import("builtins").unwrap();
            let strategy = locals.getattr("None").unwrap();

            // Step 1: Process T1 A
            processor.process(&mut engine, py, &strategy).unwrap();

            // Step 2: Process T2 B (Fill T1)
            processor.process(&mut engine, py, &strategy).unwrap();

            // Verify T1 Fill
            {
                let buffer = engine.history_buffer.read().unwrap();
                let hist_b = buffer.data.get("B").unwrap();
                assert_eq!(hist_b.timestamps[0], 1000);
                assert_eq!(hist_b.closes[0], 200.0);
                assert_eq!(hist_b.volumes[0], 0.0);
            }

            engine.last_prices.insert("B".to_string(), dec!(205));

            // Step 3: Process T3 A (Fill T2)
            processor.process(&mut engine, py, &strategy).unwrap();

             // Verify T2 Fill
            {
                let buffer = engine.history_buffer.read().unwrap();
                let hist_a = buffer.data.get("A").unwrap();
                assert_eq!(hist_a.timestamps[1], 2000);
                assert_eq!(hist_a.closes[1], 100.0);
                assert_eq!(hist_a.volumes[1], 0.0);
            }
        });
    }

    #[test]
    fn test_corporate_action_processing() {
        // pyo3::prepare_freethreaded_python();

        use crate::model::corporate_action::{CorporateAction, CorporateActionType};
        use chrono::NaiveDate;

        let mut engine = Engine::new();
        let symbol = "AAPL".to_string();
        engine.instruments.insert(symbol.clone(), create_instrument(&symbol));

        // Initial Position: 100 shares, Cash 0
        {
            let positions = Arc::make_mut(&mut engine.state.portfolio.positions);
            positions.insert(symbol.clone(), dec!(100));
            let available = Arc::make_mut(&mut engine.state.portfolio.available_positions);
            available.insert(symbol.clone(), dec!(100));
        }
        engine.state.portfolio.cash = dec!(0);

        // Add Split Action: 1-to-2 split on 2023-01-02
        let split_date = NaiveDate::from_ymd_opt(2023, 1, 2).unwrap();
        let split_action = CorporateAction {
            symbol: symbol.clone(),
            date: split_date,
            action_type: CorporateActionType::Split,
            value: dec!(2.0),
        };
        engine.corporate_action_manager.add(split_action);

        // Add Dividend Action: $0.5 per share on 2023-01-03
        let div_date = NaiveDate::from_ymd_opt(2023, 1, 3).unwrap();
        let div_action = CorporateAction {
            symbol: symbol.clone(),
            date: div_date,
            action_type: CorporateActionType::Dividend,
            value: dec!(0.5),
        };
        engine.corporate_action_manager.add(div_action);

        let mut processor = DataProcessor::new();

        // T1: 2023-01-01 (Before Split)
        let bar_t1 = Bar {
            timestamp: 1_672_531_200_000_000_000, // 2023-01-01
            symbol: symbol.clone(),
            open: dec!(100), high: dec!(100), low: dec!(100), close: dec!(100), volume: dec!(100),
            extra: HashMap::new(),
        };
        engine.state.feed.add_bar(bar_t1).unwrap();

        // T2: 2023-01-02 (Split Day)
        let bar_t2 = Bar {
            timestamp: 1_672_617_600_000_000_000, // 2023-01-02
            symbol: symbol.clone(),
            open: dec!(50), high: dec!(50), low: dec!(50), close: dec!(50), volume: dec!(100),
            extra: HashMap::new(),
        };
        engine.state.feed.add_bar(bar_t2).unwrap();

        // T3: 2023-01-03 (Dividend Day)
        let bar_t3 = Bar {
            timestamp: 1_672_704_000_000_000_000, // 2023-01-03
            symbol: symbol.clone(),
            open: dec!(50), high: dec!(50), low: dec!(50), close: dec!(50), volume: dec!(100),
            extra: HashMap::new(),
        };
        engine.state.feed.add_bar(bar_t3).unwrap();

        // Use Python::attach as recommended by PyO3 0.28+
        pyo3::Python::attach(|py| {
            let locals = py.import("builtins").unwrap();
            let strategy = locals.getattr("None").unwrap();

            // Process T1
            processor.process(&mut engine, py, &strategy).unwrap();
            // Verify T1 state: 100 shares
            assert_eq!(engine.state.portfolio.positions.get(&symbol).unwrap(), &dec!(100));

            // Process T2 (Split happens at day start/end depending on logic, here logic is triggered by date change)
            // Our logic: when processing T2 event, we detect date change T1 -> T2, then trigger end-of-day actions for T2?
            // Wait, let's check DataProcessor logic:
            // if self.last_timestamp != 0 && timestamp > self.last_timestamp {
            //    ...
            //    engine.clock.update(timestamp, ...);
            //    let local_date = local_dt.date_naive();
            //    if engine.current_date != Some(local_date) {
            //       // New Day!
            //       engine.current_date = Some(local_date);
            //       process_date(local_date) <--- This processes actions for the NEW date
            //    }
            // }

            // So when T2 bar comes in, date changes to 2023-01-02.
            // process_date(2023-01-02) is called. Split happens.

            processor.process(&mut engine, py, &strategy).unwrap();

            // Verify T2 Split: 100 shares * 2 = 200 shares
            assert_eq!(engine.state.portfolio.positions.get(&symbol).unwrap(), &dec!(200));

            // Process T3 (Dividend)
            processor.process(&mut engine, py, &strategy).unwrap();

            // Verify T3 Dividend: 200 shares * 0.5 = 100 Cash
            assert_eq!(engine.state.portfolio.cash, dec!(100));
        });
    }
}
