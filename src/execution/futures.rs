use crate::event::Event;
use crate::execution::common::CommonMatcher;
use crate::execution::matcher::{ExecutionMatcher, MatchContext};
use crate::model::{Order, OrderStatus, OrderType};
use rust_decimal::Decimal;

pub struct FuturesMatcher {
    default_enforce_tick_size: bool,
    default_enforce_lot_size: bool,
    validation_by_prefix: Vec<(String, Option<bool>, Option<bool>)>,
}

impl FuturesMatcher {
    pub fn new(enforce_tick_size: bool, enforce_lot_size: bool) -> Self {
        Self {
            default_enforce_tick_size: enforce_tick_size,
            default_enforce_lot_size: enforce_lot_size,
            validation_by_prefix: Vec::new(),
        }
    }

    pub fn with_prefix_rules(
        enforce_tick_size: bool,
        enforce_lot_size: bool,
        validation_by_prefix: Vec<(String, Option<bool>, Option<bool>)>,
    ) -> Self {
        Self {
            default_enforce_tick_size: enforce_tick_size,
            default_enforce_lot_size: enforce_lot_size,
            validation_by_prefix,
        }
    }

    fn reject(order: &mut Order, ctx: &MatchContext, reason: String) -> Option<Event> {
        order.status = OrderStatus::Rejected;
        order.reject_reason = reason;
        match ctx.event {
            Event::Bar(b) => order.updated_at = b.timestamp,
            Event::Tick(t) => order.updated_at = t.timestamp,
            _ => {}
        }
        Some(Event::ExecutionReport(order.clone(), None))
    }

    fn is_multiple(value: Decimal, step: Decimal) -> bool {
        if step <= Decimal::ZERO {
            return true;
        }
        value % step == Decimal::ZERO
    }

    fn validation_flags_for_symbol(&self, symbol: &str) -> (bool, bool) {
        let mut enforce_tick_size = self.default_enforce_tick_size;
        let mut enforce_lot_size = self.default_enforce_lot_size;
        let mut best_match_len = 0usize;
        let symbol_upper = symbol.to_uppercase();
        for (prefix, tick_opt, lot_opt) in &self.validation_by_prefix {
            let normalized = prefix.trim().to_uppercase();
            if normalized.is_empty() {
                continue;
            }
            if symbol_upper.starts_with(&normalized) && normalized.len() > best_match_len {
                if let Some(tick) = tick_opt {
                    enforce_tick_size = *tick;
                }
                if let Some(lot) = lot_opt {
                    enforce_lot_size = *lot;
                }
                best_match_len = normalized.len();
            }
        }
        (enforce_tick_size, enforce_lot_size)
    }

    fn validate_order(&self, order: &mut Order, ctx: &MatchContext) -> Option<Event> {
        let (enforce_tick_size, enforce_lot_size) =
            self.validation_flags_for_symbol(ctx.instrument.symbol());
        let lot_size = ctx.instrument.lot_size();
        if enforce_lot_size
            && lot_size > Decimal::ZERO
            && !Self::is_multiple(order.quantity, lot_size)
        {
            return Self::reject(
                order,
                ctx,
                format!(
                    "Quantity {} is not a multiple of lot size {}",
                    order.quantity, lot_size
                ),
            );
        }

        let tick_size = ctx.instrument.tick_size();
        if !enforce_tick_size || tick_size <= Decimal::ZERO {
            return None;
        }

        let mut prices_to_check: Vec<(&str, Decimal)> = Vec::new();
        match order.order_type {
            OrderType::Limit => {
                if let Some(price) = order.price {
                    prices_to_check.push(("price", price));
                }
            }
            OrderType::StopMarket => {
                if let Some(trigger_price) = order.trigger_price {
                    prices_to_check.push(("trigger_price", trigger_price));
                }
            }
            OrderType::StopLimit => {
                if let Some(price) = order.price {
                    prices_to_check.push(("price", price));
                }
                if let Some(trigger_price) = order.trigger_price {
                    prices_to_check.push(("trigger_price", trigger_price));
                }
            }
            OrderType::StopTrail => {
                if let Some(trigger_price) = order.trigger_price {
                    prices_to_check.push(("trigger_price", trigger_price));
                }
                if let Some(trail_offset) = order.trail_offset {
                    prices_to_check.push(("trail_offset", trail_offset));
                }
            }
            OrderType::StopTrailLimit => {
                if let Some(price) = order.price {
                    prices_to_check.push(("price", price));
                }
                if let Some(trigger_price) = order.trigger_price {
                    prices_to_check.push(("trigger_price", trigger_price));
                }
                if let Some(trail_offset) = order.trail_offset {
                    prices_to_check.push(("trail_offset", trail_offset));
                }
            }
            _ => {}
        }

        for (field_name, value) in prices_to_check {
            if !Self::is_multiple(value, tick_size) {
                return Self::reject(
                    order,
                    ctx,
                    format!(
                        "{} {} is not aligned with tick size {}",
                        field_name, value, tick_size
                    ),
                );
            }
        }
        None
    }
}

impl ExecutionMatcher for FuturesMatcher {
    fn match_order(&self, order: &mut Order, ctx: &MatchContext) -> Option<Event> {
        if let Some(report) = self.validate_order(order, ctx) {
            return Some(report);
        }
        CommonMatcher::match_order(order, ctx, false)
    }
}

impl Default for FuturesMatcher {
    fn default() -> Self {
        Self::new(true, true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::instrument::{FuturesInstrument, InstrumentEnum};
    use crate::model::{AssetType, ExecutionMode, Instrument, OrderRole, OrderSide, TimeInForce};
    use rust_decimal::prelude::FromStr;
    use rust_decimal_macros::dec;

    fn create_futures_instrument() -> Instrument {
        Instrument {
            asset_type: AssetType::Futures,
            inner: InstrumentEnum::Futures(FuturesInstrument {
                symbol: "RB2310".to_string(),
                multiplier: dec!(10),
                margin_ratio: dec!(0.1),
                tick_size: dec!(0.2),
                expiry_date: None,
                settlement_type: None,
                settlement_price: None,
            }),
        }
    }

    fn create_order(side: OrderSide) -> Order {
        Order {
            id: "1".to_string(),
            symbol: "RB2310".to_string(),
            side,
            order_type: OrderType::Limit,
            quantity: dec!(1),
            price: Some(dec!(3500.0)),
            trigger_price: None,
            trail_offset: None,
            trail_reference_price: None,
            graph_id: None,
            parent_order_id: None,
            order_role: OrderRole::Standalone,
            status: OrderStatus::New,
            filled_quantity: Decimal::ZERO,
            average_filled_price: None,
            time_in_force: TimeInForce::Day,
            created_at: 0,
            updated_at: 0,
            commission: Decimal::ZERO,
            tag: String::new(),
            reject_reason: String::new(),
            owner_strategy_id: None,
        }
    }

    fn create_context<'a>(
        event: &'a Event,
        instrument: &'a Instrument,
    ) -> crate::execution::matcher::MatchContext<'a> {
        crate::execution::matcher::MatchContext {
            event,
            instrument,
            execution_mode: ExecutionMode::NextOpen,
            slippage: &crate::execution::slippage::ZeroSlippage,
            volume_limit_pct: Decimal::ZERO,
            bar_index: 0,
            last_price: None,
        }
    }

    #[test]
    fn test_futures_reject_non_multiple_lot_size_for_sell() {
        let matcher = FuturesMatcher::default();
        let mut order = create_order(OrderSide::Sell);
        order.quantity = Decimal::from_str("1.5").unwrap();
        let instrument = create_futures_instrument();
        let bar = crate::model::Bar {
            timestamp: 100,
            symbol: "RB2310".to_string(),
            open: dec!(3500.0),
            high: dec!(3510.0),
            low: dec!(3490.0),
            close: dec!(3505.0),
            volume: dec!(1000),
            extra: Default::default(),
        };
        let event = Event::Bar(bar);
        let ctx = create_context(&event, &instrument);
        let res = matcher.match_order(&mut order, &ctx);
        assert!(res.is_some());
        assert_eq!(order.status, OrderStatus::Rejected);
        assert!(order.reject_reason.contains("lot size"));
    }

    #[test]
    fn test_futures_reject_non_tick_aligned_limit_price() {
        let matcher = FuturesMatcher::default();
        let mut order = create_order(OrderSide::Buy);
        order.price = Some(dec!(3500.1));
        let instrument = create_futures_instrument();
        let tick = crate::model::Tick {
            timestamp: 100,
            price: dec!(3500.0),
            volume: dec!(10),
            symbol: "RB2310".to_string(),
        };
        let event = Event::Tick(tick);
        let ctx = create_context(&event, &instrument);
        let res = matcher.match_order(&mut order, &ctx);
        assert!(res.is_some());
        assert_eq!(order.status, OrderStatus::Rejected);
        assert!(order.reject_reason.contains("tick size"));
    }

    #[test]
    fn test_futures_accept_tick_aligned_prices() {
        let matcher = FuturesMatcher::default();
        let mut order = create_order(OrderSide::Buy);
        order.order_type = OrderType::StopLimit;
        order.price = Some(dec!(3500.2));
        order.trigger_price = Some(dec!(3501.0));
        let instrument = create_futures_instrument();
        let bar = crate::model::Bar {
            timestamp: 100,
            symbol: "RB2310".to_string(),
            open: dec!(3501.0),
            high: dec!(3510.0),
            low: dec!(3490.0),
            close: dec!(3505.0),
            volume: dec!(1000),
            extra: Default::default(),
        };
        let event = Event::Bar(bar);
        let ctx = create_context(&event, &instrument);
        let _ = matcher.match_order(&mut order, &ctx);
        assert_ne!(order.status, OrderStatus::Rejected);
    }

    #[test]
    fn test_futures_can_disable_tick_validation() {
        let matcher = FuturesMatcher::new(false, true);
        let mut order = create_order(OrderSide::Buy);
        order.price = Some(dec!(3500.1));
        let instrument = create_futures_instrument();
        let tick = crate::model::Tick {
            timestamp: 100,
            price: dec!(3500.0),
            volume: dec!(10),
            symbol: "RB2310".to_string(),
        };
        let event = Event::Tick(tick);
        let ctx = create_context(&event, &instrument);
        let _ = matcher.match_order(&mut order, &ctx);
        assert_ne!(order.status, OrderStatus::Rejected);
    }

    #[test]
    fn test_futures_can_disable_lot_validation() {
        let matcher = FuturesMatcher::new(true, false);
        let mut order = create_order(OrderSide::Sell);
        order.quantity = Decimal::from_str("1.5").unwrap();
        let instrument = create_futures_instrument();
        let bar = crate::model::Bar {
            timestamp: 100,
            symbol: "RB2310".to_string(),
            open: dec!(3500.0),
            high: dec!(3510.0),
            low: dec!(3490.0),
            close: dec!(3505.0),
            volume: dec!(1000),
            extra: Default::default(),
        };
        let event = Event::Bar(bar);
        let ctx = create_context(&event, &instrument);
        let _ = matcher.match_order(&mut order, &ctx);
        assert_ne!(order.status, OrderStatus::Rejected);
    }

    #[test]
    fn test_futures_prefix_rules_override_default_validation() {
        let matcher = FuturesMatcher::with_prefix_rules(
            true,
            true,
            vec![("RB".to_string(), Some(false), Some(false))],
        );
        let mut order = create_order(OrderSide::Sell);
        order.quantity = Decimal::from_str("1.5").unwrap();
        order.price = Some(dec!(3500.1));
        let instrument = create_futures_instrument();
        let bar = crate::model::Bar {
            timestamp: 100,
            symbol: "RB2310".to_string(),
            open: dec!(3500.0),
            high: dec!(3510.0),
            low: dec!(3490.0),
            close: dec!(3505.0),
            volume: dec!(1000),
            extra: Default::default(),
        };
        let event = Event::Bar(bar);
        let ctx = create_context(&event, &instrument);
        let _ = matcher.match_order(&mut order, &ctx);
        assert_ne!(order.status, OrderStatus::Rejected);
    }
}
