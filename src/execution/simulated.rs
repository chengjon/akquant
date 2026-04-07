use crate::event::Event;
use crate::execution::matcher::{ExecutionMatcher, MatchContext};
use crate::execution::slippage::{SlippageModel, ZeroSlippage};
use crate::execution::{ExecutionClient, crypto, forex, futures, option, stock};
use crate::model::{AssetType, Order, OrderStatus, TimeInForce, TradingSession};
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use std::collections::HashMap;

/// 模拟交易所执行器 (Simulated Execution Client)
/// 负责在内存中撮合订单 (回测模式)
pub struct SimulatedExecutionClient {
    slippage_model: Box<dyn SlippageModel>,
    volume_limit_pct: Decimal, // 成交量限制比例 (0.0 = 不限制)
    // Map order_id -> Order (O(1) access)
    orders: HashMap<String, Order>,
    // List of order_ids to maintain submission order (for matching fairness)
    order_queue: Vec<String>,
    // Matchers
    matchers: HashMap<AssetType, Box<dyn ExecutionMatcher>>,
    futures_enforce_tick_size: bool,
    futures_enforce_lot_size: bool,
    futures_validation_by_prefix: Vec<(String, Option<bool>, Option<bool>)>,
}

impl SimulatedExecutionClient {
    fn rebuild_futures_matcher(&mut self) {
        self.matchers.insert(
            AssetType::Futures,
            Box::new(futures::FuturesMatcher::with_prefix_rules(
                self.futures_enforce_tick_size,
                self.futures_enforce_lot_size,
                self.futures_validation_by_prefix.clone(),
            )),
        );
    }

    pub fn new() -> Self {
        let mut matchers: HashMap<AssetType, Box<dyn ExecutionMatcher>> = HashMap::new();
        matchers.insert(AssetType::Stock, Box::new(stock::StockMatcher));
        matchers.insert(AssetType::Fund, Box::new(stock::StockMatcher)); // Fund uses StockMatcher
        matchers.insert(
            AssetType::Futures,
            Box::new(futures::FuturesMatcher::with_prefix_rules(
                true,
                true,
                Vec::new(),
            )),
        );
        matchers.insert(AssetType::Option, Box::new(option::OptionMatcher));
        matchers.insert(AssetType::Crypto, Box::new(crypto::CryptoMatcher));
        matchers.insert(AssetType::Forex, Box::new(forex::ForexMatcher));

        SimulatedExecutionClient {
            slippage_model: Box::new(ZeroSlippage),
            volume_limit_pct: Decimal::ZERO,
            orders: HashMap::new(),
            order_queue: Vec::new(),
            matchers,
            futures_enforce_tick_size: true,
            futures_enforce_lot_size: true,
            futures_validation_by_prefix: Vec::new(),
        }
    }
}

impl Default for SimulatedExecutionClient {
    fn default() -> Self {
        Self::new()
    }
}

impl ExecutionClient for SimulatedExecutionClient {
    fn set_slippage_model(&mut self, model: Box<dyn SlippageModel>) {
        self.slippage_model = model;
    }

    fn set_volume_limit(&mut self, limit: f64) {
        self.volume_limit_pct = Decimal::from_f64(limit).unwrap_or_else(|| {
            log::warn!("Invalid volume limit {}, defaulting to 0.0", limit);
            Decimal::ZERO
        });
    }

    fn register_matcher(&mut self, asset_type: AssetType, matcher: Box<dyn ExecutionMatcher>) {
        self.matchers.insert(asset_type, matcher);
    }

    fn set_futures_validation_options(&mut self, enforce_tick_size: bool, enforce_lot_size: bool) {
        self.futures_enforce_tick_size = enforce_tick_size;
        self.futures_enforce_lot_size = enforce_lot_size;
        self.rebuild_futures_matcher();
    }

    fn set_futures_validation_options_by_prefix(
        &mut self,
        symbol_prefix: String,
        enforce_tick_size: Option<bool>,
        enforce_lot_size: Option<bool>,
    ) {
        let normalized = symbol_prefix.trim().to_uppercase();
        if normalized.is_empty() {
            return;
        }
        let mut updated = false;
        for (prefix, tick_opt, lot_opt) in &mut self.futures_validation_by_prefix {
            if prefix == &normalized {
                *tick_opt = enforce_tick_size;
                *lot_opt = enforce_lot_size;
                updated = true;
                break;
            }
        }
        if !updated {
            self.futures_validation_by_prefix.push((
                normalized,
                enforce_tick_size,
                enforce_lot_size,
            ));
        }
        self.rebuild_futures_matcher();
    }

    fn on_order(&mut self, order: Order) {
        // 模拟交易所接收订单
        let mut order = order;
        if order.status == OrderStatus::New {
            order.status = OrderStatus::Submitted;
        }
        let id = order.id.clone();
        self.orders.insert(id.clone(), order);
        self.order_queue.push(id);
    }

    fn on_cancel(&mut self, order_id: &str) {
        if let Some(order) = self.orders.get_mut(order_id)
            && (order.status == OrderStatus::Submitted
                || order.status == OrderStatus::PartiallyFilled
                || order.status == OrderStatus::New)
        {
            order.status = OrderStatus::Cancelled;
        }
    }

    fn on_event(&mut self, event: &Event, ctx: &crate::context::EngineContext) -> Vec<Event> {
        let mut reports = Vec::new();

        // Skip matching during non-trading sessions
        if ctx.session == TradingSession::Break
            || ctx.session == TradingSession::Closed
            || ctx.session == TradingSession::PreOpen
            || ctx.session == TradingSession::PostClose
        {
            // Also check for Day orders expiry if Closed
            if ctx.session == TradingSession::Closed {
                let timestamp = match event {
                    Event::Bar(b) => b.timestamp,
                    Event::Tick(t) => t.timestamp,
                    _ => 0,
                };

                for order_id in &self.order_queue {
                    if let Some(order) = self.orders.get_mut(order_id)
                        && order.status != OrderStatus::Cancelled
                        && order.status != OrderStatus::Filled
                        && order.status != OrderStatus::Rejected
                        && order.status != OrderStatus::Expired
                        && order.time_in_force == TimeInForce::Day
                    {
                        order.status = OrderStatus::Expired;
                        order.updated_at = timestamp;
                        reports.push(Event::ExecutionReport(order.clone(), None));
                    }
                }
            }
            return reports;
        }

        // Track available margin for this step (snapshot of portfolio + changes in this loop)
        let mut projected_portfolio = ctx.portfolio.clone();
        let mut current_free_margin =
            projected_portfolio.calculate_free_margin(ctx.last_prices, ctx.instruments);

        let mut queue: Vec<String> = self.order_queue.clone();
        queue.sort_by_key(|order_id| {
            self.orders
                .get(order_id)
                .map(|order| match order.side {
                    crate::model::OrderSide::Sell => 0_u8,
                    crate::model::OrderSide::Buy => 1_u8,
                })
                .unwrap_or(2_u8)
        });

        let matchers = &self.matchers;

        for order_id in &queue {
            if let Some(order) = self.orders.get_mut(order_id) {
                if order.status == OrderStatus::Cancelled
                    || order.status == OrderStatus::Filled
                    || order.status == OrderStatus::Rejected
                    || order.status == OrderStatus::Expired
                {
                    continue;
                }

                // Find Instrument
                if let Some(instrument) = ctx.instruments.get(&order.symbol) {
                    // Dispatch to specific matcher
                    if let Some(matcher) = matchers.get(&instrument.asset_type) {
                        let match_ctx = MatchContext {
                            event,
                            instrument,
                            execution_policy_core: order
                                .fill_policy_override
                                .unwrap_or(ctx.execution_policy_core),
                            slippage: self.slippage_model.as_ref(),
                            volume_limit_pct: self.volume_limit_pct,
                            bar_index: ctx.bar_index,
                            last_price: ctx.last_prices.get(&order.symbol).copied(),
                        };
                        let report_opt = matcher.match_order(order, &match_ctx);

                        if let Some(mut report) = report_opt {
                            let mut replacement_report: Option<Event> = None;
                            if let Event::ExecutionReport(
                                ref mut report_order,
                                Some(ref mut trade),
                            ) = report
                                && trade.side == crate::model::OrderSide::Buy
                            {
                                // Calculate estimated commission
                                let commission = ctx.market_model.calculate_commission(
                                    instrument,
                                    trade.side,
                                    trade.price,
                                    trade.quantity,
                                );

                                let multiplier = instrument.multiplier();
                                let margin_ratio = if ctx.risk_config.is_margin_account()
                                    && (instrument.asset_type == AssetType::Stock
                                        || instrument.asset_type == AssetType::Fund)
                                {
                                    ctx.risk_config.stock_initial_margin_ratio()
                                } else {
                                    instrument.margin_ratio()
                                };

                                // Margin Required = Price * Qty * Multiplier * MarginRatio
                                let margin_required =
                                    trade.price * trade.quantity * multiplier * margin_ratio;
                                let total_required = margin_required + commission;

                                if total_required > current_free_margin {
                                    if report_order.allow_quantity_auto_resize {
                                        let unit_margin = trade.price * multiplier * margin_ratio;
                                        let mut max_qty = if unit_margin > Decimal::ZERO {
                                            if current_free_margin <= Decimal::ZERO {
                                                Decimal::ZERO
                                            } else {
                                                current_free_margin / unit_margin
                                            }
                                        } else {
                                            Decimal::ZERO
                                        };

                                        let safety_margin = 0.0001;
                                        let safety_factor = Decimal::from_f64(1.0 - safety_margin)
                                            .unwrap_or_else(|| {
                                                log::warn!("Invalid safety factor calculation, defaulting to 0.9999");
                                                Decimal::from_f64(0.9999).unwrap_or(Decimal::ZERO)
                                            });
                                        max_qty *= safety_factor;

                                        let lot_size = instrument.lot_size();
                                        let mut new_qty = max_qty.floor();
                                        if lot_size > Decimal::ZERO {
                                            new_qty = new_qty - (new_qty % lot_size);
                                        }

                                        let new_comm = ctx.market_model.calculate_commission(
                                            instrument,
                                            trade.side,
                                            trade.price,
                                            new_qty,
                                        );
                                        let new_margin =
                                            trade.price * new_qty * multiplier * margin_ratio;

                                        if new_margin + new_comm > current_free_margin {
                                            if new_qty >= lot_size {
                                                new_qty -= lot_size;
                                            } else {
                                                new_qty = Decimal::ZERO;
                                            }
                                        }

                                        trade.quantity = new_qty;
                                    } else {
                                        let mut rejected_order = report_order.clone();
                                        rejected_order.status = crate::model::OrderStatus::Rejected;
                                        rejected_order.updated_at = ctx.current_time;
                                        rejected_order.reject_reason = format!(
                                            "Risk: Insufficient margin at execution. Required: {total_required}, Available: {current_free_margin}"
                                        );
                                        replacement_report =
                                            Some(Event::ExecutionReport(rejected_order, None));
                                    }
                                }

                            }

                            if let Some(new_report) = replacement_report {
                                report = new_report;
                            }

                            if let Event::ExecutionReport(_, Some(ref trade)) = report
                                && trade.quantity > Decimal::ZERO
                            {
                                let commission = ctx.market_model.calculate_commission(
                                    instrument,
                                    trade.side,
                                    trade.price,
                                    trade.quantity,
                                );
                                let cost = trade.price * trade.quantity * instrument.multiplier();
                                projected_portfolio.adjust_cash(-commission);
                                if trade.side == crate::model::OrderSide::Buy {
                                    projected_portfolio.adjust_cash(-cost);
                                    projected_portfolio.adjust_position(
                                        &trade.symbol,
                                        trade.quantity,
                                    );
                                } else {
                                    projected_portfolio.adjust_cash(cost);
                                    projected_portfolio.adjust_position(
                                        &trade.symbol,
                                        -trade.quantity,
                                    );
                                }
                                current_free_margin = projected_portfolio
                                    .calculate_free_margin(ctx.last_prices, ctx.instruments);
                            }

                            let mut keep_report = true;
                            if let Event::ExecutionReport(_, Some(ref trade)) = report
                                && trade.quantity <= Decimal::ZERO
                            {
                                keep_report = false;
                            }

                            if keep_report {
                                reports.push(report);
                            }
                        }
                    } else {
                        // No matcher found for this asset type, skip or log warning?
                        // For now just skip
                    }
                }
            }
        }

        // Cleanup filled/cancelled/rejected orders from pending list
        for report in &reports {
            if let Event::ExecutionReport(updated_order, _) = report
                && let Some(existing) = self.orders.get_mut(&updated_order.id)
            {
                existing.status = updated_order.status;
                existing.filled_quantity = updated_order.filled_quantity;
                existing.average_filled_price = updated_order.average_filled_price;
                existing.commission = updated_order.commission;
                existing.updated_at = updated_order.updated_at;
            }
        }

        // Clean up completed orders
        let mut finished_ids = Vec::new();
        for id in &self.order_queue {
            if let Some(order) = self.orders.get(id) {
                if order.status == OrderStatus::Filled
                    || order.status == OrderStatus::Cancelled
                    || order.status == OrderStatus::Rejected
                    || order.status == OrderStatus::Expired
                {
                    finished_ids.push(id.clone());
                }
            } else {
                finished_ids.push(id.clone()); // Orphaned
            }
        }

        for id in finished_ids {
            self.orders.remove(&id);
        }

        // Retain only existing orders in queue
        self.order_queue.retain(|id| self.orders.contains_key(id));

        reports
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{
        AssetType, Bar, ExecutionPolicyCore, Instrument, PriceBasis, TemporalPolicy, TimeInForce,
    };
    use std::collections::HashMap;

    fn create_test_instruments() -> HashMap<String, Instrument> {
        use crate::model::instrument::{InstrumentEnum, StockInstrument};

        let mut map = HashMap::new();
        let aapl = Instrument {
            asset_type: AssetType::Stock,
            inner: InstrumentEnum::Stock(StockInstrument {
                symbol: "AAPL".to_string(),
                lot_size: Decimal::from(100),
                tick_size: Decimal::new(1, 2),
                expiry_date: None,
            }),
        };
        map.insert("AAPL".to_string(), aapl);
        map
    }

    fn create_test_order(
        symbol: &str,
        side: crate::model::OrderSide,
        order_type: crate::model::OrderType,
        quantity: Decimal,
        price: Option<Decimal>,
    ) -> Order {
        use uuid::Uuid;
        let mut order =
            Order::test_new(&Uuid::new_v4().to_string(), symbol, side, order_type, quantity);
        order.price = price;
        order.time_in_force = TimeInForce::Day;
        order.status = OrderStatus::New;
        order
    }

    fn create_test_bar(
        symbol: &str,
        open: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
    ) -> Bar {
        Bar {
            symbol: symbol.to_string(),
            timestamp: 1000,
            open,
            high,
            low,
            close,
            volume: Decimal::from(1000),
            extra: HashMap::new(),
        }
    }

    #[test]
    fn test_execution_market_order() {
        let mut sim = SimulatedExecutionClient::new();
        let instruments = create_test_instruments();
        let order = create_test_order(
            "AAPL",
            crate::model::OrderSide::Buy,
            crate::model::OrderType::Market,
            Decimal::from(100),
            None,
        );
        sim.on_order(order);

        let bar = create_test_bar(
            "AAPL",
            Decimal::from(100),
            Decimal::from(105),
            Decimal::from(95),
            Decimal::from(102),
        );
        let event = Event::Bar(bar);

        let portfolio = crate::portfolio::Portfolio {
            cash: Decimal::from(100000),
            positions: HashMap::new().into(),
            available_positions: HashMap::new().into(),
        };
        let last_prices = HashMap::new();
        let risk_manager = crate::risk::RiskManager::new();

        let china_config = crate::market::ChinaMarketConfig {
            stock: Some(crate::market::stock::StockConfig::default()),
            ..Default::default()
        };
        let market_config = crate::market::MarketConfig::China(china_config);

        let market_model = market_config.create_model();

        let ctx = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &last_prices,
            market_model: market_model.as_ref(),
            execution_policy_core: ExecutionPolicyCore::default(),
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
            risk_config: &risk_manager.config,
        };

        let events = sim.on_event(&event, &ctx);

        let trades: Vec<crate::model::Trade> = events
            .iter()
            .filter_map(|e| {
                if let Event::ExecutionReport(_, Some(trade)) = e {
                    Some(trade.clone())
                } else {
                    None
                }
            })
            .collect();

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].price, Decimal::from(100)); // Open price

        let _last_order = events
            .iter()
            .filter_map(|e| {
                if let Event::ExecutionReport(o, _) = e {
                    Some(o)
                } else {
                    None
                }
            })
            .next_back()
            .unwrap();
    }

    #[test]
    fn test_execution_market_order_next_close() {
        let mut sim = SimulatedExecutionClient::new();
        let instruments = create_test_instruments();
        let order = create_test_order(
            "AAPL",
            crate::model::OrderSide::Buy,
            crate::model::OrderType::Market,
            Decimal::from(100),
            None,
        );
        sim.on_order(order);

        let bar = create_test_bar(
            "AAPL",
            Decimal::from(100),
            Decimal::from(105),
            Decimal::from(95),
            Decimal::from(102),
        );
        let event = Event::Bar(bar);

        let portfolio = crate::portfolio::Portfolio {
            cash: Decimal::from(100000),
            positions: HashMap::new().into(),
            available_positions: HashMap::new().into(),
        };
        let last_prices = HashMap::new();
        let risk_manager = crate::risk::RiskManager::new();

        let china_config = crate::market::ChinaMarketConfig {
            stock: Some(crate::market::stock::StockConfig::default()),
            ..Default::default()
        };
        let market_config = crate::market::MarketConfig::China(china_config);
        let market_model = market_config.create_model();

        let ctx = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &last_prices,
            market_model: market_model.as_ref(),
            execution_policy_core: ExecutionPolicyCore {
                price_basis: PriceBasis::Close,
                bar_offset: 1,
                temporal: TemporalPolicy::SameCycle,
            },
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
            risk_config: &risk_manager.config,
        };

        let events = sim.on_event(&event, &ctx);
        let trades: Vec<crate::model::Trade> = events
            .iter()
            .filter_map(|e| {
                if let Event::ExecutionReport(_, Some(trade)) = e {
                    Some(trade.clone())
                } else {
                    None
                }
            })
            .collect();

        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].price, Decimal::from(102));
    }

    #[test]
    fn test_execution_limit_buy() {
        let mut sim = SimulatedExecutionClient::new();
        let instruments = create_test_instruments();
        // Buy Limit @ 99.0
        let order = create_test_order(
            "AAPL",
            crate::model::OrderSide::Buy,
            crate::model::OrderType::Limit,
            Decimal::from(100),
            Some(Decimal::from(99)),
        );
        sim.on_order(order);

        let bar = create_test_bar(
            "AAPL",
            Decimal::from(100),
            Decimal::from(105),
            Decimal::from(95),
            Decimal::from(102),
        );
        let event = Event::Bar(bar);

        let portfolio = crate::portfolio::Portfolio {
            cash: Decimal::from(100000),
            positions: HashMap::new().into(),
            available_positions: HashMap::new().into(),
        };
        let last_prices = HashMap::new();
        let risk_manager = crate::risk::RiskManager::new();

        let china_config = crate::market::ChinaMarketConfig {
            stock: Some(crate::market::stock::StockConfig::default()),
            ..Default::default()
        };
        let market_config = crate::market::MarketConfig::China(china_config);

        let market_model = market_config.create_model();

        let ctx = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &last_prices,
            market_model: market_model.as_ref(),
            execution_policy_core: ExecutionPolicyCore::default(),
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
            risk_config: &risk_manager.config,
        };

        let events = sim.on_event(&event, &ctx);

        // Should be filled at Limit Price (99)
        let trades: Vec<_> = events
            .iter()
            .filter_map(|e| {
                if let Event::ExecutionReport(_, Some(t)) = e {
                    Some(t)
                } else {
                    None
                }
            })
            .collect();
        assert_eq!(trades.len(), 1);
        assert_eq!(trades[0].price, Decimal::from(99));
    }

    #[test]
    fn test_execution_limit_buy_no_fill() {
        let mut sim = SimulatedExecutionClient::new();
        let instruments = create_test_instruments();
        // Buy Limit @ 90.0 (Below Low 95)
        let order = create_test_order(
            "AAPL",
            crate::model::OrderSide::Buy,
            crate::model::OrderType::Limit,
            Decimal::from(100),
            Some(Decimal::from(90)),
        );
        sim.on_order(order);

        let bar = create_test_bar(
            "AAPL",
            Decimal::from(100),
            Decimal::from(105),
            Decimal::from(95),
            Decimal::from(102),
        );
        let event = Event::Bar(bar);

        let portfolio = crate::portfolio::Portfolio {
            cash: Decimal::from(100000),
            positions: HashMap::new().into(),
            available_positions: HashMap::new().into(),
        };
        let last_prices = HashMap::new();
        let risk_manager = crate::risk::RiskManager::new();

        let china_config = crate::market::ChinaMarketConfig {
            stock: Some(crate::market::stock::StockConfig::default()),
            ..Default::default()
        };
        let market_config = crate::market::MarketConfig::China(china_config);

        let market_model = market_config.create_model();

        let ctx = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &last_prices,
            market_model: market_model.as_ref(),
            execution_policy_core: ExecutionPolicyCore::default(),
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
            risk_config: &risk_manager.config,
        };

        let events = sim.on_event(&event, &ctx);

        let trades: Vec<_> = events
            .iter()
            .filter_map(|e| {
                if let Event::ExecutionReport(_, Some(t)) = e {
                    Some(t)
                } else {
                    None
                }
            })
            .collect();
        assert_eq!(trades.len(), 0);
    }

    #[test]
    fn test_dynamic_position_sizing() {
        let mut sim = SimulatedExecutionClient::new();
        let instruments = create_test_instruments();

        // Buy 1000 shares @ 100 = 100,000 value.
        // But cash is only 50,000.
        let order = create_test_order(
            "AAPL",
            crate::model::OrderSide::Buy,
            crate::model::OrderType::Market,
            Decimal::from(1000),
            None,
        );
        sim.on_order(order);

        let bar = create_test_bar(
            "AAPL",
            Decimal::from(100),
            Decimal::from(105),
            Decimal::from(95),
            Decimal::from(102),
        );
        let event = Event::Bar(bar);

        let portfolio = crate::portfolio::Portfolio {
            cash: Decimal::from(50000), // Only 50k
            positions: HashMap::new().into(),
            available_positions: HashMap::new().into(),
        };
        let last_prices = HashMap::new();
        let risk_manager = crate::risk::RiskManager::new();

        let china_config = crate::market::ChinaMarketConfig {
            stock: Some(crate::market::stock::StockConfig::default()),
            ..Default::default()
        };
        let market_config = crate::market::MarketConfig::China(china_config);

        let market_model = market_config.create_model();

        let ctx = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &last_prices,
            market_model: market_model.as_ref(),
            execution_policy_core: ExecutionPolicyCore::default(),
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
            risk_config: &risk_manager.config,
        };

        let events = sim.on_event(&event, &ctx);

        let trades: Vec<_> = events
            .iter()
            .filter_map(|e| {
                if let Event::ExecutionReport(_, Some(t)) = e {
                    Some(t)
                } else {
                    None
                }
            })
            .collect();
        assert_eq!(trades.len(), 1);

        // Should be reduced to approx 400 shares (due to lot size 100 and safety margin)
        // 50000 / 100 = 500. 500 * 0.9999 = 499.95 -> floor to 400 (lot size 100)
        assert_eq!(trades[0].quantity, Decimal::from(400));
    }
}
