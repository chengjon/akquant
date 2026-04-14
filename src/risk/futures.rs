use crate::error::AkQuantError;
use crate::model::{AssetType, Order, OrderSide, OrderStatus};
use crate::portfolio::Portfolio;
use rust_decimal::Decimal;
use std::collections::HashMap;

use super::rule::{RiskCheckContext, RiskRule};

#[derive(Debug, Clone)]
pub struct FuturesMarginRule;

impl RiskRule for FuturesMarginRule {
    fn name(&self) -> &'static str {
        "FuturesMarginRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        if !ctx.config.check_cash
            || !ctx.config.is_margin_account()
            || ctx.instrument.asset_type != AssetType::Futures
        {
            return Ok(());
        }

        let maintenance_ratio = ctx.config.maintenance_margin_ratio_decimal();
        if maintenance_ratio <= Decimal::ZERO {
            return Ok(());
        }

        let Some(order_price) = resolve_order_price(order, ctx.current_prices) else {
            return Ok(());
        };

        let mut prices_for_order = ctx.current_prices.clone();
        prices_for_order.insert(order.symbol.clone(), order_price);

        let mut current_portfolio = ctx.portfolio.clone();
        for active_order in ctx.active_orders {
            if active_order.status != OrderStatus::New {
                continue;
            }
            let Some(active_price) = resolve_order_price(active_order, ctx.current_prices) else {
                continue;
            };
            apply_order_to_portfolio(
                &mut current_portfolio,
                active_order,
                active_price,
                ctx.instruments,
            );
        }

        let current_exposure = calculate_gross_exposure(
            &current_portfolio,
            &prices_for_order,
            ctx.instruments,
        );

        let mut next_portfolio = current_portfolio.clone();
        apply_order_to_portfolio(&mut next_portfolio, order, order_price, ctx.instruments);
        let next_exposure =
            calculate_gross_exposure(&next_portfolio, &prices_for_order, ctx.instruments);
        if next_exposure <= Decimal::ZERO {
            return Ok(());
        }

        let next_equity = next_portfolio.calculate_equity(&prices_for_order, ctx.instruments);
        let next_ratio = if next_exposure > Decimal::ZERO {
            next_equity / next_exposure
        } else {
            Decimal::MAX
        };

        if next_ratio < maintenance_ratio && next_exposure >= current_exposure {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Futures maintenance margin breach. Ratio: {next_ratio}, Required: {maintenance_ratio}",
            )));
        }

        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

fn resolve_order_price(
    order: &Order,
    current_prices: &HashMap<String, Decimal>,
) -> Option<Decimal> {
    order
        .price
        .or_else(|| current_prices.get(&order.symbol).copied())
}

fn apply_order_to_portfolio(
    portfolio: &mut Portfolio,
    order: &Order,
    price: Decimal,
    instruments: &HashMap<String, crate::model::Instrument>,
) {
    let Some(instr) = instruments.get(&order.symbol) else {
        return;
    };
    let cost = price * order.quantity * instr.multiplier();
    match order.side {
        OrderSide::Buy => {
            portfolio.adjust_cash(-cost);
            portfolio.adjust_position(&order.symbol, order.quantity);
        }
        OrderSide::Sell => {
            portfolio.adjust_cash(cost);
            portfolio.adjust_position(&order.symbol, -order.quantity);
        }
    }
}

fn calculate_gross_exposure(
    portfolio: &Portfolio,
    prices: &HashMap<String, Decimal>,
    instruments: &HashMap<String, crate::model::Instrument>,
) -> Decimal {
    let mut gross_exposure = Decimal::ZERO;
    for (symbol, quantity) in portfolio.positions.iter() {
        if quantity.is_zero() {
            continue;
        }
        let Some(price) = prices.get(symbol).copied() else {
            continue;
        };
        if price <= Decimal::ZERO {
            continue;
        }
        let multiplier = instruments
            .get(symbol)
            .map(|instr| instr.multiplier())
            .unwrap_or(Decimal::ONE);
        gross_exposure += quantity.abs() * price * multiplier;
    }
    gross_exposure
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::instrument::{FuturesInstrument, InstrumentEnum};
    use crate::model::{Instrument, OrderType, TimeInForce};
    use crate::risk::RiskConfig;
    use rust_decimal::prelude::FromStr;
    use std::sync::Arc;

    fn make_futures_instrument(symbol: &str) -> Instrument {
        Instrument {
            asset_type: AssetType::Futures,
            inner: InstrumentEnum::Futures(FuturesInstrument {
                symbol: symbol.to_string(),
                multiplier: Decimal::from(10),
                margin_ratio: Decimal::from_str("0.1").expect("decimal"),
                tick_size: Decimal::from_str("0.2").expect("decimal"),
                expiry_date: None,
                settlement_type: None,
                settlement_price: None,
            }),
        }
    }

    fn make_order(symbol: &str, side: OrderSide, quantity: Decimal) -> Order {
        let mut order = Order::test_new("test-order", symbol, side, OrderType::Limit, quantity);
        order.price = Some(Decimal::from(100));
        order.time_in_force = TimeInForce::Day;
        order.status = OrderStatus::New;
        order
    }

    fn make_context<'a>(
        portfolio: &'a Portfolio,
        instrument: &'a Instrument,
        instruments: &'a HashMap<String, Instrument>,
        current_prices: &'a HashMap<String, Decimal>,
        config: &'a RiskConfig,
    ) -> RiskCheckContext<'a> {
        RiskCheckContext {
            portfolio,
            instrument,
            instruments,
            active_orders: &[],
            current_prices,
            current_time: 0,
            config,
        }
    }

    #[test]
    fn futures_rule_rejects_new_order_below_maintenance_ratio() {
        let symbol = "IF9999".to_string();
        let instrument = make_futures_instrument(&symbol);
        let mut instruments = HashMap::new();
        instruments.insert(symbol.clone(), instrument.clone());
        let mut current_prices = HashMap::new();
        current_prices.insert(symbol.clone(), Decimal::from(100));
        let portfolio = Portfolio {
            cash: Decimal::from(100_000),
            positions: Arc::new(HashMap::new()),
            available_positions: Arc::new(HashMap::new()),
        };
        let mut config = RiskConfig::new();
        config.account_mode = "margin".to_string();
        config.maintenance_margin_ratio = 0.3;
        let order = make_order(&symbol, OrderSide::Buy, Decimal::from(400));
        let rule = FuturesMarginRule;
        let ctx = make_context(&portfolio, &instrument, &instruments, &current_prices, &config);

        let err = rule.check(&order, &ctx).expect_err("should reject order");
        assert!(err.to_string().contains("maintenance margin breach"));
    }

    #[test]
    fn futures_rule_allows_reducing_position_when_below_maintenance_ratio() {
        let symbol = "IF9999".to_string();
        let instrument = make_futures_instrument(&symbol);
        let mut instruments = HashMap::new();
        instruments.insert(symbol.clone(), instrument.clone());
        let mut current_prices = HashMap::new();
        current_prices.insert(symbol.clone(), Decimal::from(100));
        let mut positions = HashMap::new();
        positions.insert(symbol.clone(), Decimal::from(500));
        let portfolio = Portfolio {
            cash: Decimal::from(-400_000),
            positions: Arc::new(positions.clone()),
            available_positions: Arc::new(positions),
        };
        let mut config = RiskConfig::new();
        config.account_mode = "margin".to_string();
        config.maintenance_margin_ratio = 0.3;
        let order = make_order(&symbol, OrderSide::Sell, Decimal::from(100));
        let rule = FuturesMarginRule;
        let ctx = make_context(&portfolio, &instrument, &instruments, &current_prices, &config);

        assert!(rule.check(&order, &ctx).is_ok());
    }
}
