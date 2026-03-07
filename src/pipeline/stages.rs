use crate::context::EngineContext;
use crate::data::FeedAction;
use crate::engine::Engine;
use crate::event::Event;
use crate::model::{Bar, ExecutionMode, Order, OrderStatus, TradingSession};
use crate::pipeline::processor::{Processor, ProcessorResult};
use pyo3::prelude::*;
use rust_decimal::Decimal;
use std::collections::{HashMap, HashSet};
use std::sync::Arc;

pub struct ChannelProcessor;

fn process_order_request(
    engine: &mut Engine,
    py: Python<'_>,
    mut order: Order,
) {
    let current_time = engine.clock.timestamp().unwrap_or(0);
    engine.maybe_reset_risk_budget_usage(current_time);
    let mut strategy_limit_err = engine.check_strategy_risk_cooldown_mode(&order);
    let mut triggers_risk_fallback = false;
    if strategy_limit_err.is_none() {
        strategy_limit_err = engine.check_strategy_reduce_only_mode(&order);
    }
    if strategy_limit_err.is_none() {
        strategy_limit_err = engine
            .check_strategy_order_size_limit(&order)
            .or_else(|| engine.check_strategy_position_size_limit(&order))
            .or_else(|| engine.check_strategy_order_value_limit(&order));
        triggers_risk_fallback = strategy_limit_err.is_some();
    }
    if strategy_limit_err.is_none() {
        strategy_limit_err = engine.check_strategy_daily_loss_limit(
            &order,
            current_time,
        );
        triggers_risk_fallback = strategy_limit_err.is_some();
    }
    if strategy_limit_err.is_none() {
        strategy_limit_err = engine.check_strategy_drawdown_limit(&order);
        triggers_risk_fallback = strategy_limit_err.is_some();
    }
    if strategy_limit_err.is_none() {
        strategy_limit_err = engine.check_strategy_risk_budget_limit(&order);
    }
    if strategy_limit_err.is_none() {
        strategy_limit_err = engine.check_portfolio_risk_budget_limit(&order);
    }
    if triggers_risk_fallback {
        engine.activate_strategy_reduce_only_if_configured(&order);
        engine.activate_strategy_risk_cooldown_if_configured(&order);
    }
    let strategy_limit_err = strategy_limit_err.map(crate::error::AkQuantError::OrderError);
    let check_result = if let Some(err) = strategy_limit_err {
        Err(err)
    } else {
        let ctx = EngineContext {
            instruments: &engine.instruments,
            portfolio: &engine.state.portfolio,
            last_prices: &engine.last_prices,
            market_model: engine.market_manager.model.as_ref(),
            execution_mode: engine.execution_mode,
            bar_index: engine.bar_count,
            current_time: engine.clock.timestamp().unwrap_or(0),
            session: engine.clock.session,
            active_orders: &engine.state.order_manager.active_orders,
        };
        engine.risk_manager.check_and_adjust(&mut order, &ctx)
    };
    if let Err(err) = check_result {
        order.status = OrderStatus::Rejected;
        order.reject_reason = err.to_string();
        order.updated_at = engine.clock.timestamp().unwrap_or(0);

        let mut risk_payload = HashMap::new();
        risk_payload.insert("order_id", order.id.clone());
        risk_payload.insert("symbol", order.symbol.clone());
        risk_payload.insert("reason", order.reject_reason.clone());
        risk_payload.insert(
            "owner_strategy_id",
            order.owner_strategy_id.clone().unwrap_or_default(),
        );
        engine.emit_stream_event(
            py,
            "risk",
            Some(order.symbol.as_str()),
            "warn",
            risk_payload,
        );
        let _ = engine.event_manager.send(Event::ExecutionReport(order, None));
    } else {
        let mut order_payload = HashMap::new();
        order_payload.insert("order_id", order.id.clone());
        order_payload.insert("status", format!("{:?}", OrderStatus::New));
        order_payload.insert("symbol", order.symbol.clone());
        order_payload.insert(
            "owner_strategy_id",
            order.owner_strategy_id.clone().unwrap_or_default(),
        );
        engine.emit_stream_event(
            py,
            "order",
            Some(order.symbol.as_str()),
            "info",
            order_payload,
        );
        if !engine.risk_budget_use_trade_mode() {
            engine.apply_risk_budget_usage(&order);
        }
        let _ = engine.event_manager.send(Event::OrderValidated(order));
    }
}

impl Processor for ChannelProcessor {
    fn process(&mut self, engine: &mut Engine, py: Python<'_>, _strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        let mut trades_to_process = Vec::new();
        let mut pending_order_requests = Vec::new();
        loop {
            let mut drained_event = false;
            while let Some(event) = engine.event_manager.try_recv() {
                drained_event = true;
                match event {
                    Event::OrderRequest(order) => pending_order_requests.push(order),
                    Event::OrderValidated(order) => {
                        engine.execution_model.on_order(order.clone());
                        engine.state.order_manager.add_active_order(order);
                    }
                    Event::ExecutionReport(order, trade) => {
                        engine.state.order_manager.on_execution_report(order);
                        let updated_order = engine.state.order_manager.orders.last().cloned();
                        if let Some(order_snapshot) = updated_order {
                            let mut order_payload = HashMap::new();
                            order_payload.insert("order_id", order_snapshot.id.clone());
                            order_payload.insert(
                                "status",
                                format!("{:?}", order_snapshot.status),
                            );
                            order_payload.insert(
                                "filled_qty",
                                order_snapshot.filled_quantity.to_string(),
                            );
                            order_payload.insert("symbol", order_snapshot.symbol.clone());
                            order_payload.insert(
                                "owner_strategy_id",
                                order_snapshot
                                    .owner_strategy_id
                                    .clone()
                                    .unwrap_or_default(),
                            );
                            engine.emit_stream_event(
                                py,
                                "order",
                                Some(order_snapshot.symbol.as_str()),
                                "info",
                                order_payload,
                            );
                        }

                        if let Some(t) = trade {
                            engine.maybe_reset_risk_budget_usage(t.timestamp);
                            if engine.risk_budget_use_trade_mode() {
                                engine.apply_risk_budget_usage_from_trade(&t);
                            }
                            engine.apply_strategy_trade_position(&t);
                            let mut trade_payload = HashMap::new();
                            trade_payload.insert("trade_id", t.id.clone());
                            trade_payload.insert("order_id", t.order_id.clone());
                            trade_payload.insert("price", t.price.to_string());
                            trade_payload.insert("quantity", t.quantity.to_string());
                            trade_payload.insert(
                                "owner_strategy_id",
                                t.owner_strategy_id.clone().unwrap_or_default(),
                            );
                            engine.emit_stream_event(
                                py,
                                "trade",
                                Some(t.symbol.as_str()),
                                "info",
                                trade_payload,
                            );
                            trades_to_process.push(t);
                        }
                    }
                    _ => {}
                }
            }

            if !pending_order_requests.is_empty() {
                pending_order_requests.sort_by(|left, right| {
                    let left_priority = engine.strategy_priority_for_order(left);
                    let right_priority = engine.strategy_priority_for_order(right);
                    right_priority.cmp(&left_priority).then_with(|| {
                        let left_id = Engine::normalized_order_strategy_id(left)
                            .unwrap_or_default();
                        let right_id = Engine::normalized_order_strategy_id(right)
                            .unwrap_or_default();
                        left_id.cmp(&right_id)
                    })
                });
                for order in pending_order_requests.drain(..) {
                    process_order_request(engine, py, order);
                }
                continue;
            }

            if !drained_event {
                break;
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
    #[must_use]
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
            for symbol in engine.instruments.keys() {
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
                            extra: HashMap::default(),
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

                if timestamp <= engine.snapshot_time {
                     return Ok(ProcessorResult::Loop);
                }

                if self.last_timestamp != 0 && timestamp > self.last_timestamp {
                    self.fill_missing_bars(engine);
                    self.seen_symbols.clear();

                    engine.bar_count += 1;
                    if let Some(pb) = &engine.progress_bar {
                        pb.inc(1);
                    }
                    let total_events = engine.state.feed.len_hint().unwrap_or(0);
                    let mut progress_payload = HashMap::new();
                    progress_payload.insert("processed", engine.bar_count.to_string());
                    progress_payload.insert("total", total_events.to_string());
                    engine.emit_stream_event(py, "progress", None, "info", progress_payload);
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
                if let Some(current) = engine.current_event.clone() {
                    match current {
                        Event::Bar(b) => {
                            let mut payload = HashMap::new();
                            payload.insert("timestamp", b.timestamp.to_string());
                            payload.insert("close", b.close.to_string());
                            payload.insert("volume", b.volume.to_string());
                            engine.emit_stream_event(
                                py,
                                "bar",
                                Some(b.symbol.as_str()),
                                "info",
                                payload,
                            );
                        }
                        Event::Tick(t) => {
                            let mut payload = HashMap::new();
                            payload.insert("timestamp", t.timestamp.to_string());
                            payload.insert("price", t.price.to_string());
                            payload.insert("volume", t.volume.to_string());
                            engine.emit_stream_event(
                                py,
                                "tick",
                                Some(t.symbol.as_str()),
                                "info",
                                payload,
                            );
                        }
                        _ => {}
                    }
                }
                Ok(ProcessorResult::Next)
            }
        }
    }
}

pub struct StrategyProcessor;

impl Processor for StrategyProcessor {
    fn process(&mut self, engine: &mut Engine, py: Python<'_>, strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        if let Some(event) = engine.current_event.clone() {
            engine.ensure_strategy_slot_exists();
            engine.ensure_strategy_context_capacity();
            let slot_count = engine.strategy_slots.len();
            let active_orders = Arc::new(engine.state.order_manager.active_orders.clone());
            let step_trades = engine.state.order_manager.current_step_trades.clone();

            for slot_index in 0..slot_count {
                let slot_strategy = engine
                    .strategy_slot_strategies
                    .get(slot_index)
                    .and_then(|slot| slot.as_ref())
                    .map(|slot| slot.clone_ref(py));
                let (new_orders, new_timers, canceled_ids) =
                    if let Some(ref slot_py) = slot_strategy {
                        let slot_bound = slot_py.bind(py);
                        engine.call_strategy_for_slot(
                            slot_bound,
                            &event,
                            slot_index,
                            active_orders.clone(),
                            step_trades.clone(),
                        )?
                    } else {
                        engine.call_strategy_for_slot(
                            strategy,
                            &event,
                            slot_index,
                            active_orders.clone(),
                            step_trades.clone(),
                        )?
                    };

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
            engine.state.order_manager.current_step_trades.clear();
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
                        current_time: engine.clock.timestamp().unwrap_or(0),
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
    fn process(&mut self, engine: &mut Engine, py: Python<'_>, _strategy: &Bound<'_, PyAny>) -> PyResult<ProcessorResult> {
        if let Some(Event::Bar(_) | Event::Tick(_)) = engine.current_event.clone()
            && let Some(timestamp) = engine.clock.timestamp() {
                let equity = engine.state.portfolio.calculate_equity(&engine.last_prices, &engine.instruments);
                engine.statistics_manager.update(timestamp, equity, engine.state.portfolio.cash);
                let mut payload = HashMap::new();
                payload.insert("timestamp", timestamp.to_string());
                payload.insert("equity", equity.to_string());
                payload.insert("cash", engine.state.portfolio.cash.to_string());
                engine.emit_stream_event(py, "equity", None, "info", payload);
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
        pyo3::Python::initialize();

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
        pyo3::Python::initialize();

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
