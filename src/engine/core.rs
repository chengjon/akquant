use chrono::{DateTime, NaiveDate, NaiveTime, TimeZone, Utc};
use indicatif::ProgressBar;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rust_decimal::prelude::*;
use std::collections::{BinaryHeap, HashMap};
use std::sync::{Arc, RwLock};

// use crate::analysis::{BacktestResult, PositionSnapshot};
use crate::clock::Clock;
use crate::context::StrategyContext;
use crate::event::Event;
use crate::event_manager::EventManager;
use crate::execution::ExecutionClient;
use crate::history::HistoryBuffer;
use crate::market::corporate_action::CorporateActionManager;
use crate::market::manager::MarketManager;
use crate::model::{
    ExecutionMode, Instrument, Order, Timer, Trade,
};
use crate::pipeline::stages::{
    ChannelProcessor, CleanupProcessor, DataProcessor, ExecutionPhase, ExecutionProcessor,
    StatisticsProcessor, StrategyProcessor,
};
use crate::pipeline::PipelineRunner;
use crate::risk::RiskManager;
use crate::settlement::SettlementManager;
use crate::statistics::StatisticsManager;

use super::state::SharedState;

/// 主回测引擎.
///
/// :ivar feed: 数据源
/// :ivar portfolio: 投资组合
/// :ivar orders: 订单列表
/// :ivar trades: 成交列表
#[gen_stub_pyclass]
#[pyclass]
pub struct Engine {
    pub(crate) state: SharedState,
    pub(crate) last_prices: HashMap<String, Decimal>,
    pub(crate) instruments: HashMap<String, Instrument>,
    pub(crate) current_date: Option<NaiveDate>,
    pub(crate) market_manager: MarketManager,
    pub(crate) corporate_action_manager: CorporateActionManager,
    pub(crate) execution_model: Box<dyn ExecutionClient>,
    pub(crate) execution_mode: ExecutionMode,
    pub(crate) clock: Clock,
    pub(crate) timers: BinaryHeap<Timer>, // Min-Heap via Timer's Ord implementation
    pub(crate) force_session_continuous: bool,
    #[pyo3(get, set)]
    pub risk_manager: RiskManager,
    pub(crate) timezone_offset: i32,
    pub(crate) history_buffer: Arc<RwLock<HistoryBuffer>>,
    pub(crate) initial_cash: Decimal,
    // Components
    pub(crate) event_manager: EventManager,
    pub(crate) statistics_manager: StatisticsManager,
    pub(crate) settlement_manager: SettlementManager,
    // Pipeline state
    pub(crate) current_event: Option<Event>,
    pub(crate) bar_count: usize,
    pub(crate) progress_bar: Option<ProgressBar>,
    pub(crate) strategy_context: Option<Py<StrategyContext>>,
}

// Internal implementation of Engine (not exposed to Python)
impl Engine {
    pub(crate) fn create_context(
        &self,
        active_orders: Arc<Vec<Order>>,
        step_trades: Vec<Trade>,
    ) -> StrategyContext {
        // Create a temporary context for the strategy to use
        StrategyContext::new(crate::context::ContextInit {
            cash: self.state.portfolio.cash,
            positions: self.state.portfolio.positions.clone(),
            available_positions: self.state.portfolio.available_positions.clone(),
            session: self.clock.session,
            current_time: self.clock.timestamp().unwrap_or(0),
            active_orders,
            closed_trades: self.state.order_manager.trade_tracker.closed_trades.clone(),
            recent_trades: step_trades,
            history_buffer: Some(self.history_buffer.clone()),
            event_tx: Some(self.event_manager.sender()),
            risk_config: self.risk_manager.config.clone(),
        })
    }

    pub(crate) fn datetime_from_ns(timestamp: i64) -> DateTime<Utc> {
        let secs = timestamp.div_euclid(1_000_000_000);
        let nanos = timestamp.rem_euclid(1_000_000_000) as u32;
        Utc.timestamp_opt(secs, nanos)
            .single()
            .expect("Invalid timestamp")
    }

    pub(crate) fn local_datetime_from_ns(timestamp: i64, offset_secs: i32) -> DateTime<Utc> {
        let offset_ns = i64::from(offset_secs) * 1_000_000_000;
        Self::datetime_from_ns(timestamp + offset_ns)
    }

    pub(crate) fn parse_time_string(value: &str) -> PyResult<NaiveTime> {
        if let Ok(t) = NaiveTime::parse_from_str(value, "%H:%M:%S") {
            return Ok(t);
        }
        if let Ok(t) = NaiveTime::parse_from_str(value, "%H:%M") {
            return Ok(t);
        }
        Err(PyValueError::new_err(format!(
            "Invalid time format: {}",
            value
        )))
    }

    pub(crate) fn call_strategy(
        &mut self,
        strategy: &Bound<'_, PyAny>,
        event: &Event,
    ) -> PyResult<(Vec<Order>, Vec<Timer>, Vec<String>)> {
        // Update Last Price and Trigger Strategy
        match event {
            Event::Bar(b) => {
                self.last_prices.insert(b.symbol.clone(), b.close);
                let step_trades = std::mem::take(&mut self.state.order_manager.current_step_trades);
                // Share active orders via Arc
                let active_orders = Arc::new(self.state.order_manager.active_orders.clone());

                // Reuse or create StrategyContext
                let py_ctx = if let Some(ref ctx) = self.strategy_context {
                    // Reuse existing context
                    Python::attach(|py| {
                        let py_ctx = ctx.clone_ref(py);
                        {
                            let mut ctx_mut = py_ctx.borrow_mut(py);
                            ctx_mut.update_state(crate::context::ContextUpdate {
                                cash: self.state.portfolio.cash,
                                positions: self.state.portfolio.positions.clone(),
                                available_positions: self.state.portfolio.available_positions.clone(),
                                session: self.clock.session,
                                current_time: self.clock.timestamp().unwrap_or(0),
                                active_orders,
                                recent_trades: step_trades,
                            });
                        }
                        Ok::<_, PyErr>(py_ctx)
                    })?
                } else {
                    // Create new context (first time)
                    let ctx = self.create_context(active_orders, step_trades);
                    let (py_ctx, persistent_ref) = Python::attach(|py| {
                        let py_ctx = Py::new(py, ctx).unwrap();
                        Ok::<_, PyErr>((py_ctx.clone_ref(py), py_ctx.clone_ref(py)))
                    })?;
                    self.strategy_context = Some(persistent_ref);
                    py_ctx
                };

                let args = Python::attach(|py| {
                     let bar = b.clone();
                     (bar, py_ctx.clone_ref(py))
                });

                strategy.call_method1("_on_bar_event", args)?;

                // Extract orders and timers
                let mut new_orders = Vec::new();
                let mut new_timers = Vec::new();
                let mut canceled_ids = Vec::new();
                Python::attach(|py| {
                    let ctx_ref = py_ctx.borrow(py);
                    // Read from RwLock
                    if let Ok(orders) = ctx_ref.orders_arc.read() {
                        new_orders.extend(orders.clone());
                    }
                    if let Ok(timers) = ctx_ref.timers_arc.read() {
                        new_timers.extend(timers.clone());
                    }
                    if let Ok(canceled) = ctx_ref.canceled_order_ids_arc.read() {
                        canceled_ids.extend(canceled.clone());
                    }
                });
                Ok((new_orders, new_timers, canceled_ids))
            }
            Event::Tick(t) => {
                self.last_prices.insert(t.symbol.clone(), t.price);
                let step_trades = std::mem::take(&mut self.state.order_manager.current_step_trades);
                let active_orders = Arc::new(self.state.order_manager.active_orders.clone());

                 // Reuse or create StrategyContext
                let py_ctx = if let Some(ref ctx) = self.strategy_context {
                    // Reuse existing context
                    Python::attach(|py| {
                        let py_ctx = ctx.clone_ref(py);
                        {
                            let mut ctx_mut = py_ctx.borrow_mut(py);
                            ctx_mut.update_state(crate::context::ContextUpdate {
                                cash: self.state.portfolio.cash,
                                positions: self.state.portfolio.positions.clone(),
                                available_positions: self.state.portfolio.available_positions.clone(),
                                session: self.clock.session,
                                current_time: self.clock.timestamp().unwrap_or(0),
                                active_orders,
                                recent_trades: step_trades,
                            });
                        }
                        Ok::<_, PyErr>(py_ctx)
                    })?
                } else {
                    // Create new context (first time)
                    let ctx = self.create_context(active_orders, step_trades);
                    let (py_ctx, persistent_ref) = Python::attach(|py| {
                        let py_ctx = Py::new(py, ctx).unwrap();
                        Ok::<_, PyErr>((py_ctx.clone_ref(py), py_ctx.clone_ref(py)))
                    })?;
                    self.strategy_context = Some(persistent_ref);
                    py_ctx
                };

                let args = Python::attach(|py| {
                     let tick = t.clone();
                     (tick, py_ctx.clone_ref(py))
                });

                strategy.call_method1("_on_tick_event", args)?;

                // Extract orders and timers
                let mut new_orders = Vec::new();
                let mut new_timers = Vec::new();
                let mut canceled_ids = Vec::new();
                Python::attach(|py| {
                    let ctx_ref = py_ctx.borrow(py);
                    if let Ok(orders) = ctx_ref.orders_arc.read() {
                        new_orders.extend(orders.clone());
                    }
                    if let Ok(timers) = ctx_ref.timers_arc.read() {
                        new_timers.extend(timers.clone());
                    }
                    if let Ok(canceled) = ctx_ref.canceled_order_ids_arc.read() {
                        canceled_ids.extend(canceled.clone());
                    }
                });
                Ok((new_orders, new_timers, canceled_ids))
            }
            Event::Timer(timer) => {
                let step_trades = std::mem::take(&mut self.state.order_manager.current_step_trades);
                let active_orders = Arc::new(self.state.order_manager.active_orders.clone());

                 // Reuse or create StrategyContext
                let py_ctx = if let Some(ref ctx) = self.strategy_context {
                    // Reuse existing context
                    Python::attach(|py| {
                        let py_ctx = ctx.clone_ref(py);
                        {
                            let mut ctx_mut = py_ctx.borrow_mut(py);
                            ctx_mut.update_state(crate::context::ContextUpdate {
                                cash: self.state.portfolio.cash,
                                positions: self.state.portfolio.positions.clone(),
                                available_positions: self.state.portfolio.available_positions.clone(),
                                session: self.clock.session,
                                current_time: self.clock.timestamp().unwrap_or(0),
                                active_orders,
                                recent_trades: step_trades,
                            });
                        }
                        Ok::<_, PyErr>(py_ctx)
                    })?
                } else {
                    // Create new context (first time)
                    let ctx = self.create_context(active_orders, step_trades);
                    let (py_ctx, persistent_ref) = Python::attach(|py| {
                        let py_ctx = Py::new(py, ctx).unwrap();
                        Ok::<_, PyErr>((py_ctx.clone_ref(py), py_ctx.clone_ref(py)))
                    })?;
                    self.strategy_context = Some(persistent_ref);
                    py_ctx
                };

                let args = Python::attach(|py| {
                     let payload = timer.payload.as_str();
                     (payload, py_ctx.clone_ref(py))
                });

                strategy.call_method1("_on_timer_event", args)?;

                // Extract orders and timers
                let mut new_orders = Vec::new();
                let mut new_timers = Vec::new();
                let mut canceled_ids = Vec::new();
                Python::attach(|py| {
                    let ctx_ref = py_ctx.borrow(py);
                    if let Ok(orders) = ctx_ref.orders_arc.read() {
                        new_orders.extend(orders.clone());
                    }
                    if let Ok(timers) = ctx_ref.timers_arc.read() {
                        new_timers.extend(timers.clone());
                    }
                    if let Ok(canceled) = ctx_ref.canceled_order_ids_arc.read() {
                        canceled_ids.extend(canceled.clone());
                    }
                });
                Ok((new_orders, new_timers, canceled_ids))
            }
            Event::OrderRequest(_) | Event::OrderValidated(_) | Event::ExecutionReport(_, _) => {
                Ok((Vec::new(), Vec::new(), Vec::new()))
            }
        }
    }

    pub(crate) fn build_pipeline(&self) -> PipelineRunner {
        let mut pipeline = PipelineRunner::new();
        // 1. Process events from previous iteration (or init)
        pipeline.add_processor(Box::new(ChannelProcessor));

        // 2. Fetch new Data Event
        pipeline.add_processor(Box::new(DataProcessor::new()));

        // 3. Pre-Strategy Execution (Match Pending Orders)
        // For NextOpen/NextAverage: Matches orders generated in previous bar against current bar.
        pipeline.add_processor(Box::new(ExecutionProcessor::new(ExecutionPhase::PreStrategy)));

        // 4. Process Fills from Pre-Execution immediately (Update Portfolio before Strategy)
        pipeline.add_processor(Box::new(ChannelProcessor));

        // 5. Run Strategy
        pipeline.add_processor(Box::new(StrategyProcessor));

        // 6. Process Order Requests from Strategy immediately (Validate -> Pending)
        pipeline.add_processor(Box::new(ChannelProcessor));

        // 7. Post-Strategy Execution
        // For CurrentClose: Matches orders generated in current bar against current bar.
        pipeline.add_processor(Box::new(ExecutionProcessor::new(ExecutionPhase::PostStrategy)));

        // 8. Process Fills from Post-Execution
        pipeline.add_processor(Box::new(ChannelProcessor));

        // 9. Statistics & Cleanup
        pipeline.add_processor(Box::new(StatisticsProcessor));
        pipeline.add_processor(Box::new(CleanupProcessor));

        pipeline
    }
}
