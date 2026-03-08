use crate::event::Event;
use crate::execution::matcher::{ExecutionMatcher, MatchContext};
use crate::execution::slippage::{SlippageModel, ZeroSlippage};
use crate::execution::{crypto, forex, futures, option, stock, ExecutionClient};
use crate::model::{AssetType, Order, OrderStatus, TimeInForce, TradingSession};
use rust_decimal::prelude::*;
use rust_decimal::Decimal;
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
}

impl SimulatedExecutionClient {
    pub fn new() -> Self {
        let mut matchers: HashMap<AssetType, Box<dyn ExecutionMatcher>> = HashMap::new();
        matchers.insert(AssetType::Stock, Box::new(stock::StockMatcher));
        matchers.insert(AssetType::Fund, Box::new(stock::StockMatcher)); // Fund uses StockMatcher
        matchers.insert(AssetType::Futures, Box::new(futures::FuturesMatcher));
        matchers.insert(AssetType::Option, Box::new(option::OptionMatcher));
        matchers.insert(AssetType::Crypto, Box::new(crypto::CryptoMatcher));
        matchers.insert(AssetType::Forex, Box::new(forex::ForexMatcher));

        SimulatedExecutionClient {
            slippage_model: Box::new(ZeroSlippage),
            volume_limit_pct: Decimal::ZERO,
            orders: HashMap::new(),
            order_queue: Vec::new(),
            matchers,
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
                || order.status == OrderStatus::New) {
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
                            && order.time_in_force == TimeInForce::Day {
                                order.status = OrderStatus::Expired;
                                order.updated_at = timestamp;
                                reports.push(Event::ExecutionReport(order.clone(), None));
                            }
                }
            }
            return reports;
        }

        // Track available margin for this step (snapshot of portfolio + changes in this loop)
        let mut current_free_margin = ctx.portfolio.calculate_free_margin(ctx.last_prices, ctx.instruments);

        // Split borrows
        let orders = &mut self.orders;
        let queue = &self.order_queue;
        let matchers = &self.matchers;

        for order_id in queue {
             if let Some(order) = orders.get_mut(order_id) {
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
                            execution_mode: ctx.execution_mode,
                            slippage: self.slippage_model.as_ref(),
                            volume_limit_pct: self.volume_limit_pct,
                            bar_index: ctx.bar_index,
                        };
                        let report_opt = matcher.match_order(
                            order,
                            &match_ctx,
                        );

                        if let Some(mut report) = report_opt {
                            // Check for dynamic position sizing (margin check)
                            if let Event::ExecutionReport(ref mut _r_order, Some(ref mut trade)) = report
                                && trade.side == crate::model::OrderSide::Buy {
                                    // Calculate estimated commission
                                    let commission = ctx.market_model.calculate_commission(
                                        instrument,
                                        trade.side,
                                        trade.price,
                                        trade.quantity,
                                    );

                                    let multiplier = instrument.multiplier();
                                    let margin_ratio = instrument.margin_ratio();

                                    // Margin Required = Price * Qty * Multiplier * MarginRatio
                                    let margin_required = trade.price * trade.quantity * multiplier * margin_ratio;
                                    let total_required = margin_required + commission;

                                    if total_required > current_free_margin {
                                        // Insufficient margin, reduce quantity
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

                                        // Apply safety factor (Default 0.9999 if risk manager not available)
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

                                        // Recalculate to ensure it fits
                                        let new_comm = ctx.market_model.calculate_commission(
                                            instrument,
                                            trade.side,
                                            trade.price,
                                            new_qty,
                                        );
                                        let new_margin = trade.price * new_qty * multiplier * margin_ratio;

                                        if new_margin + new_comm > current_free_margin {
                                            if new_qty >= lot_size {
                                                new_qty -= lot_size;
                                            } else {
                                                new_qty = Decimal::ZERO;
                                            }
                                        }

                                        // Update trade quantity
                                        trade.quantity = new_qty;
                                    }

                                    // Deduct cost from current_free_margin for next orders in this loop
                                    if trade.quantity > Decimal::ZERO {
                                        let final_comm = ctx.market_model.calculate_commission(
                                            instrument,
                                            trade.side,
                                            trade.price,
                                            trade.quantity,
                                        );
                                        let final_margin = trade.price * trade.quantity * multiplier * margin_ratio;
                                        current_free_margin -= final_margin + final_comm;
                                    }
                                }

                            // Filter out zero quantity trades
                            let mut keep_report = true;
                            if let Event::ExecutionReport(_, Some(ref trade)) = report
                                && trade.quantity <= Decimal::ZERO {
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
                && let Some(existing) = self.orders.get_mut(&updated_order.id) {
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
    use crate::model::{AssetType, Bar, Instrument, TimeInForce, ExecutionMode};
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
        Order {
            id: Uuid::new_v4().to_string(),
            symbol: symbol.to_string(),
            side,
            order_type,
            quantity,
            price,
            time_in_force: TimeInForce::Day,
            trigger_price: None,
            trail_offset: None,
            trail_reference_price: None,
            graph_id: None,
            parent_order_id: None,
            order_role: crate::model::OrderRole::Standalone,
            status: OrderStatus::New,
            filled_quantity: Decimal::ZERO,
            average_filled_price: None,
            created_at: 0,
            updated_at: 0,
            commission: Decimal::ZERO,
            tag: String::new(),
            reject_reason: String::new(),
            owner_strategy_id: None,
        }
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
        let _risk_manager = crate::risk::RiskManager::new();

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
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
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
        let _risk_manager = crate::risk::RiskManager::new();

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
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
        };

        let events = sim.on_event(&event, &ctx);

        // Should be filled at Limit Price (99)
        let trades: Vec<_> = events.iter().filter_map(|e| if let Event::ExecutionReport(_, Some(t)) = e { Some(t) } else { None }).collect();
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
        let _risk_manager = crate::risk::RiskManager::new();

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
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
        };

        let events = sim.on_event(&event, &ctx);

        let trades: Vec<_> = events.iter().filter_map(|e| if let Event::ExecutionReport(_, Some(t)) = e { Some(t) } else { None }).collect();
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
        let _risk_manager = crate::risk::RiskManager::new();

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
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 0,
            current_time: 0,
            session: TradingSession::Continuous,
            active_orders: &[],
        };

        let events = sim.on_event(&event, &ctx);

        let trades: Vec<_> = events.iter().filter_map(|e| if let Event::ExecutionReport(_, Some(t)) = e { Some(t) } else { None }).collect();
        assert_eq!(trades.len(), 1);

        // Should be reduced to approx 400 shares (due to lot size 100 and safety margin)
        // 50000 / 100 = 500. 500 * 0.9999 = 499.95 -> floor to 400 (lot size 100)
        assert_eq!(trades[0].quantity, Decimal::from(400));
    }
}
