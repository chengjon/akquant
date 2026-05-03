use crate::error::AkQuantError;
use crate::model::instrument::InstrumentEnum;
use crate::model::{AssetType, Order, OrderSide, OrderStatus};
use crate::pricing::bsm::{calculate_greeks, time_to_expiry};
use crate::portfolio::Portfolio;
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use std::collections::HashMap;

use super::rule::{RiskCheckContext, RiskRule};

/// Check per-slot (per-strategy) Greek limits.
///
/// Given a map of slot positions (`strategy_id -> {symbol -> quantity}`), instruments, prices,
/// and config, compute Greeks for the specified slot and check against `slot_max_delta/gamma/vega`.
/// Returns an error string if any limit is breached, or `None` if the order passes.
pub fn check_slot_greek_limit(
    strategy_id: &str,
    slot_positions: &HashMap<String, Decimal>,
    instruments: &HashMap<String, crate::model::Instrument>,
    current_prices: &HashMap<String, Decimal>,
    current_time: i64,
    config: &super::config::RiskConfig,
) -> Option<String> {
    let max_delta = config.slot_max_delta;
    let max_gamma = config.slot_max_gamma;
    let max_vega = config.slot_max_vega;

    // Early exit if no slot-level limits configured
    if max_delta.is_none() && max_gamma.is_none() && max_vega.is_none() {
        return None;
    }

    if slot_positions.is_empty() {
        return None;
    }

    let r = config.option_risk_free_rate;
    let sigma = config.option_default_volatility;

    let mut total_delta: f64 = 0.0;
    let mut total_gamma: f64 = 0.0;
    let mut total_vega: f64 = 0.0;
    let mut has_option = false;

    for (symbol, quantity) in slot_positions {
        if quantity.is_zero() {
            continue;
        }
        let Some(instr) = instruments.get(symbol) else {
            continue;
        };
        if instr.asset_type != AssetType::Option {
            continue;
        }
        let InstrumentEnum::Option(ref opt) = instr.inner else {
            continue;
        };

        let qty_f = quantity.to_f64().unwrap_or(0.0);
        if qty_f == 0.0 {
            continue;
        }

        // Get underlying price
        let Some(underlying_price_dec) = current_prices.get(&opt.underlying_symbol).copied() else {
            continue;
        };
        let underlying_price = underlying_price_dec.to_f64().unwrap_or(0.0);
        if underlying_price <= 0.0 {
            continue;
        }

        let strike = opt.strike_price.to_f64().unwrap_or(0.0);
        let t = time_to_expiry(opt.expiry_date, current_time);

        let greeks = if t <= 0.0 {
            let delta = match opt.option_type {
                crate::model::types::OptionType::Call => {
                    if underlying_price > strike { 1.0 } else { 0.0 }
                }
                crate::model::types::OptionType::Put => {
                    if underlying_price < strike { -1.0 } else { 0.0 }
                }
            };
            crate::pricing::bsm::Greeks {
                delta,
                gamma: 0.0,
                vega: 0.0,
                theta: 0.0,
                rho: 0.0,
                price: 0.0,
            }
        } else {
            calculate_greeks(underlying_price, strike, t, r, sigma, opt.option_type)
        };

        let multiplier = opt.multiplier.to_f64().unwrap_or(1.0);
        let scale = qty_f * multiplier;

        total_delta += greeks.delta * scale;
        total_gamma += greeks.gamma * scale;
        total_vega += greeks.vega * scale;
        has_option = true;
    }

    if !has_option {
        return None;
    }

    // Check limits
    if let Some(limit) = max_delta {
        let limit_f = limit.to_f64().unwrap_or(0.0);
        if total_delta.abs() > limit_f {
            return Some(format!(
                "Risk: Slot {} delta {:.2} exceeds slot limit {:.2}",
                strategy_id, total_delta, limit_f
            ));
        }
    }
    if let Some(limit) = max_gamma {
        let limit_f = limit.to_f64().unwrap_or(0.0);
        if total_gamma.abs() > limit_f {
            return Some(format!(
                "Risk: Slot {} gamma {:.4} exceeds slot limit {:.4}",
                strategy_id, total_gamma, limit_f
            ));
        }
    }
    if let Some(limit) = max_vega {
        let limit_f = limit.to_f64().unwrap_or(0.0);
        if total_vega.abs() > limit_f {
            return Some(format!(
                "Risk: Slot {} vega {:.4} exceeds slot limit {:.4}",
                strategy_id, total_vega, limit_f
            ));
        }
    }

    None
}

/// Check option Greek risk (Delta, Gamma, Vega exposure).
#[derive(Debug, Clone)]
pub struct OptionGreekRiskRule;

impl RiskRule for OptionGreekRiskRule {
    fn name(&self) -> &'static str {
        "OptionGreekRiskRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        // Early exit: if all three limits are None, skip
        let max_delta = ctx.config.max_portfolio_delta;
        let max_gamma = ctx.config.max_portfolio_gamma;
        let max_vega = ctx.config.max_portfolio_vega;
        if max_delta.is_none() && max_gamma.is_none() && max_vega.is_none() {
            return Ok(());
        }

        // Early exit: if no option positions exist and order is not Option type, skip
        let has_option_positions = ctx.portfolio.positions.iter().any(|(sym, qty)| {
            if qty.is_zero() {
                return false;
            }
            instruments_get_asset_type(sym, ctx.instruments) == AssetType::Option
        });
        let order_is_option = ctx.instrument.asset_type == AssetType::Option;
        if !has_option_positions && !order_is_option {
            return Ok(());
        }

        // Resolve order price
        let order_price = order
            .price
            .or_else(|| ctx.current_prices.get(&order.symbol).copied());
        let Some(order_price) = order_price else {
            return Ok(());
        };

        // Clone portfolio, simulate applying active orders + this order
        let mut simulated = ctx.portfolio.clone();
        for active_order in ctx.active_orders {
            if active_order.status != OrderStatus::New {
                continue;
            }
            let Some(active_price) = active_order
                .price
                .or_else(|| ctx.current_prices.get(&active_order.symbol).copied())
            else {
                continue;
            };
            apply_order_to_portfolio(&mut simulated, active_order, active_price, ctx.instruments);
        }
        apply_order_to_portfolio(&mut simulated, order, order_price, ctx.instruments);

        let r = ctx.config.option_risk_free_rate;
        let sigma = ctx.config.option_default_volatility;
        let per_underlying = ctx.config.option_greek_per_underlying;

        // Aggregate Greeks
        let mut delta_by_group: HashMap<String, f64> = HashMap::new();
        let mut gamma_by_group: HashMap<String, f64> = HashMap::new();
        let mut vega_by_group: HashMap<String, f64> = HashMap::new();

        for (symbol, quantity) in simulated.positions.iter() {
            if quantity.is_zero() {
                continue;
            }
            let Some(instr) = ctx.instruments.get(symbol) else {
                continue;
            };
            if instr.asset_type != AssetType::Option {
                continue;
            }
            let InstrumentEnum::Option(ref opt) = instr.inner else {
                continue;
            };

            let qty_f = quantity.to_f64().unwrap_or(0.0);
            if qty_f == 0.0 {
                continue;
            }

            // Get underlying price
            let Some(underlying_price_dec) = ctx.current_prices.get(&opt.underlying_symbol).copied() else {
                // Missing underlying price — skip this position
                continue;
            };
            let underlying_price = underlying_price_dec.to_f64().unwrap_or(0.0);
            if underlying_price <= 0.0 {
                continue;
            }

            let strike = opt.strike_price.to_f64().unwrap_or(0.0);
            let t = time_to_expiry(opt.expiry_date, ctx.current_time);

            let greeks = if t <= 0.0 {
                // Expired: use intrinsic delta, gamma/vega = 0
                let delta = match opt.option_type {
                    crate::model::types::OptionType::Call => {
                        if underlying_price > strike { 1.0 } else { 0.0 }
                    }
                    crate::model::types::OptionType::Put => {
                        if underlying_price < strike { -1.0 } else { 0.0 }
                    }
                };
                crate::pricing::bsm::Greeks {
                    delta,
                    gamma: 0.0,
                    vega: 0.0,
                    theta: 0.0,
                    rho: 0.0,
                    price: 0.0,
                }
            } else {
                calculate_greeks(underlying_price, strike, t, r, sigma, opt.option_type)
            };

            let multiplier = opt.multiplier.to_f64().unwrap_or(1.0);
            let scale = qty_f * multiplier;

            let group_key = if per_underlying {
                opt.underlying_symbol.clone()
            } else {
                "__TOTAL__".to_string()
            };

            *delta_by_group.entry(group_key.clone()).or_insert(0.0) += greeks.delta * scale;
            *gamma_by_group.entry(group_key.clone()).or_insert(0.0) += greeks.gamma * scale;
            *vega_by_group.entry(group_key).or_insert(0.0) += greeks.vega * scale;
        }

        // Check limits
        if let Some(limit) = max_delta {
            let limit_f = limit.to_f64().unwrap_or(0.0);
            for (group, &delta) in &delta_by_group {
                if delta.abs() > limit_f {
                    return Err(AkQuantError::OrderError(format!(
                        "Risk: Option Greek breach — portfolio delta {:.2} exceeds limit {:.2} (group: {})",
                        delta, limit_f, group
                    )));
                }
            }
        }
        if let Some(limit) = max_gamma {
            let limit_f = limit.to_f64().unwrap_or(0.0);
            for (group, &gamma) in &gamma_by_group {
                if gamma.abs() > limit_f {
                    return Err(AkQuantError::OrderError(format!(
                        "Risk: Option Greek breach — portfolio gamma {:.4} exceeds limit {:.4} (group: {})",
                        gamma, limit_f, group
                    )));
                }
            }
        }
        if let Some(limit) = max_vega {
            let limit_f = limit.to_f64().unwrap_or(0.0);
            for (group, &vega) in &vega_by_group {
                if vega.abs() > limit_f {
                    return Err(AkQuantError::OrderError(format!(
                        "Risk: Option Greek breach — portfolio vega {:.4} exceeds limit {:.4} (group: {})",
                        vega, limit_f, group
                    )));
                }
            }
        }

        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

fn instruments_get_asset_type(
    symbol: &str,
    instruments: &HashMap<String, crate::model::Instrument>,
) -> AssetType {
    instruments
        .get(symbol)
        .map(|i| i.asset_type)
        .unwrap_or(AssetType::Stock)
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::instrument::{InstrumentEnum, OptionInstrument};
    use crate::model::{Instrument, OrderType, TimeInForce};
    use crate::risk::RiskConfig;
    use std::sync::Arc;

    fn make_option_instrument(
        symbol: &str,
        underlying: &str,
        strike: Decimal,
        option_type: crate::model::types::OptionType,
        multiplier: Decimal,
    ) -> Instrument {
        Instrument {
            asset_type: AssetType::Option,
            inner: InstrumentEnum::Option(OptionInstrument {
                symbol: symbol.to_string(),
                multiplier,
                margin_ratio: Decimal::from_str("0.2").unwrap(),
                tick_size: Decimal::from_str("0.01").unwrap(),
                option_type,
                strike_price: strike,
                expiry_date: 20260101,
                underlying_symbol: underlying.to_string(),
                settlement_type: None,
            }),
        }
    }

    fn make_order(symbol: &str, side: OrderSide, quantity: Decimal, price: Decimal) -> Order {
        let mut order = Order::test_new("test-order", symbol, side, OrderType::Limit, quantity);
        order.price = Some(price);
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
            current_time: 1_700_000_000_000_000_000,
            config,
        }
    }

    #[test]
    fn option_rule_allows_when_no_limits_set() {
        let symbol = "OPT_CALL";
        let instr = make_option_instrument(
            symbol,
            "UL",
            Decimal::from(100),
            crate::model::types::OptionType::Call,
            Decimal::ONE,
        );
        let mut instruments = HashMap::new();
        instruments.insert(symbol.to_string(), instr.clone());
        let mut prices = HashMap::new();
        prices.insert("UL".to_string(), Decimal::from(110));
        prices.insert(symbol.to_string(), Decimal::from(15));
        let portfolio = Portfolio {
            cash: Decimal::from(100_000),
            positions: Arc::new(HashMap::new()),
            available_positions: Arc::new(HashMap::new()),
        };
        let config = RiskConfig::new();
        let order = make_order(symbol, OrderSide::Buy, Decimal::from(10), Decimal::from(15));
        let rule = OptionGreekRiskRule;
        let ctx = make_context(&portfolio, &instr, &instruments, &prices, &config);
        assert!(rule.check(&order, &ctx).is_ok());
    }

    #[test]
    fn option_rule_rejects_delta_breach() {
        let symbol = "OPT_CALL";
        let instr = make_option_instrument(
            symbol,
            "UL",
            Decimal::from(100),
            crate::model::types::OptionType::Call,
            Decimal::ONE,
        );
        let mut instruments = HashMap::new();
        instruments.insert(symbol.to_string(), instr.clone());
        let mut prices = HashMap::new();
        prices.insert("UL".to_string(), Decimal::from(110));
        prices.insert(symbol.to_string(), Decimal::from(15));

        let mut positions = HashMap::new();
        positions.insert(symbol.to_string(), Decimal::from(100));
        let portfolio = Portfolio {
            cash: Decimal::from(100_000),
            positions: Arc::new(positions),
            available_positions: Arc::new(HashMap::new()),
        };

        let mut config = RiskConfig::new();
        config.max_portfolio_delta = Some(Decimal::from(10));
        let order = make_order(symbol, OrderSide::Buy, Decimal::from(10), Decimal::from(15));
        let rule = OptionGreekRiskRule;
        let ctx = make_context(&portfolio, &instr, &instruments, &prices, &config);
        let err = rule.check(&order, &ctx).expect_err("should breach delta");
        assert!(err.to_string().contains("delta"));
    }

    #[test]
    fn option_rule_allows_non_option_order_when_no_option_positions() {
        let mut instruments = HashMap::new();
        let stock_instr = Instrument {
            asset_type: AssetType::Stock,
            inner: InstrumentEnum::Stock(crate::model::instrument::StockInstrument {
                symbol: "AAPL".to_string(),
                lot_size: Decimal::from(100),
                tick_size: Decimal::from_str("0.01").unwrap(),
                expiry_date: None,
            }),
        };
        instruments.insert("AAPL".to_string(), stock_instr.clone());
        let prices = HashMap::new();
        let portfolio = Portfolio {
            cash: Decimal::from(100_000),
            positions: Arc::new(HashMap::new()),
            available_positions: Arc::new(HashMap::new()),
        };
        let mut config = RiskConfig::new();
        config.max_portfolio_delta = Some(Decimal::from(10));
        let order = make_order("AAPL", OrderSide::Buy, Decimal::from(10), Decimal::from(150));
        let rule = OptionGreekRiskRule;
        let ctx = make_context(&portfolio, &stock_instr, &instruments, &prices, &config);
        assert!(rule.check(&order, &ctx).is_ok());
    }

    #[test]
    fn slot_greek_config_fields_default_to_none() {
        let config = RiskConfig::new();
        assert!(config.slot_max_delta.is_none());
        assert!(config.slot_max_gamma.is_none());
        assert!(config.slot_max_vega.is_none());
    }

    #[test]
    fn slot_greek_config_fields_can_be_set() {
        let mut config = RiskConfig::new();
        config.slot_max_delta = Some(Decimal::from_str("50.5").unwrap());
        config.slot_max_gamma = Some(Decimal::from_str("12.3").unwrap());
        config.slot_max_vega = Some(Decimal::from_str("8.7").unwrap());

        assert_eq!(
            config.slot_max_delta.unwrap(),
            Decimal::from_str("50.5").unwrap()
        );
        assert_eq!(
            config.slot_max_gamma.unwrap(),
            Decimal::from_str("12.3").unwrap()
        );
        assert_eq!(
            config.slot_max_vega.unwrap(),
            Decimal::from_str("8.7").unwrap()
        );
    }

    #[test]
    fn slot_greek_config_independent_of_portfolio_limits() {
        let mut config = RiskConfig::new();
        config.max_portfolio_delta = Some(Decimal::from(100));
        config.slot_max_delta = Some(Decimal::from(25));

        // Both can coexist independently
        assert_eq!(config.max_portfolio_delta.unwrap(), Decimal::from(100));
        assert_eq!(config.slot_max_delta.unwrap(), Decimal::from(25));

        // Slot limits can be set without portfolio limits
        let mut config2 = RiskConfig::new();
        config2.slot_max_delta = Some(Decimal::from(10));
        assert!(config2.max_portfolio_delta.is_none());
        assert_eq!(config2.slot_max_delta.unwrap(), Decimal::from(10));
    }

    // --- Tests for check_slot_greek_limit ---

    #[test]
    fn slot_greek_limit_returns_none_when_no_limits_configured() {
        let config = RiskConfig::new();
        let mut positions = HashMap::new();
        positions.insert("OPT_CALL".to_string(), Decimal::from(100));
        let instruments = HashMap::new();
        let prices = HashMap::new();
        let result = check_slot_greek_limit(
            "slot_a",
            &positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        assert!(result.is_none());
    }

    #[test]
    fn slot_greek_limit_returns_none_when_positions_empty() {
        let mut config = RiskConfig::new();
        config.slot_max_delta = Some(Decimal::from(10));
        let positions = HashMap::new();
        let instruments = HashMap::new();
        let prices = HashMap::new();
        let result = check_slot_greek_limit(
            "slot_a",
            &positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        assert!(result.is_none());
    }

    #[test]
    fn slot_greek_limit_returns_none_when_no_option_positions() {
        let mut config = RiskConfig::new();
        config.slot_max_delta = Some(Decimal::from(10));

        let mut positions = HashMap::new();
        positions.insert("AAPL".to_string(), Decimal::from(100));

        let mut instruments = HashMap::new();
        instruments.insert(
            "AAPL".to_string(),
            Instrument {
                asset_type: AssetType::Stock,
                inner: InstrumentEnum::Stock(crate::model::instrument::StockInstrument {
                    symbol: "AAPL".to_string(),
                    lot_size: Decimal::from(100),
                    tick_size: Decimal::from_str("0.01").unwrap(),
                    expiry_date: None,
                }),
            },
        );

        let prices = HashMap::new();
        let result = check_slot_greek_limit(
            "slot_a",
            &positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        assert!(result.is_none());
    }

    #[test]
    fn slot_greek_limit_rejects_delta_breach() {
        let symbol = "OPT_CALL";
        let instr = make_option_instrument(
            symbol,
            "UL",
            Decimal::from(100),
            crate::model::types::OptionType::Call,
            Decimal::ONE,
        );
        let mut instruments = HashMap::new();
        instruments.insert(symbol.to_string(), instr);
        let mut prices = HashMap::new();
        prices.insert("UL".to_string(), Decimal::from(110));

        let mut slot_positions = HashMap::new();
        slot_positions.insert(symbol.to_string(), Decimal::from(100));

        let mut config = RiskConfig::new();
        config.slot_max_delta = Some(Decimal::from(10));

        let result = check_slot_greek_limit(
            "slot_a",
            &slot_positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        assert!(result.is_some());
        let err = result.unwrap();
        assert!(err.contains("delta"));
        assert!(err.contains("slot_a"));
        assert!(err.contains("slot limit"));
    }

    #[test]
    fn slot_greek_limit_allows_within_limit() {
        let symbol = "OPT_CALL";
        let instr = make_option_instrument(
            symbol,
            "UL",
            Decimal::from(100),
            crate::model::types::OptionType::Call,
            Decimal::ONE,
        );
        let mut instruments = HashMap::new();
        instruments.insert(symbol.to_string(), instr);
        let mut prices = HashMap::new();
        prices.insert("UL".to_string(), Decimal::from(110));

        // Small position that should be within delta limit
        let mut slot_positions = HashMap::new();
        slot_positions.insert(symbol.to_string(), Decimal::from(5));

        let mut config = RiskConfig::new();
        config.slot_max_delta = Some(Decimal::from(10));

        let result = check_slot_greek_limit(
            "slot_a",
            &slot_positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        assert!(result.is_none());
    }

    #[test]
    fn slot_greek_limit_rejects_gamma_breach() {
        let symbol = "OPT_CALL";
        let instr = make_option_instrument(
            symbol,
            "UL",
            Decimal::from(100),
            crate::model::types::OptionType::Call,
            Decimal::ONE,
        );
        let mut instruments = HashMap::new();
        instruments.insert(symbol.to_string(), instr);
        let mut prices = HashMap::new();
        prices.insert("UL".to_string(), Decimal::from(110));

        // Large position to breach gamma
        let mut slot_positions = HashMap::new();
        slot_positions.insert(symbol.to_string(), Decimal::from(10000));

        let mut config = RiskConfig::new();
        config.slot_max_gamma = Some(Decimal::from_str("0.01").unwrap());

        let result = check_slot_greek_limit(
            "slot_a",
            &slot_positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        assert!(result.is_some());
        let err = result.unwrap();
        assert!(err.contains("gamma"));
        assert!(err.contains("slot_a"));
    }

    #[test]
    fn slot_greek_limit_rejects_vega_breach() {
        let symbol = "OPT_CALL";
        let instr = make_option_instrument(
            symbol,
            "UL",
            Decimal::from(100),
            crate::model::types::OptionType::Call,
            Decimal::ONE,
        );
        let mut instruments = HashMap::new();
        instruments.insert(symbol.to_string(), instr);
        let mut prices = HashMap::new();
        prices.insert("UL".to_string(), Decimal::from(110));

        // Large position to breach vega
        let mut slot_positions = HashMap::new();
        slot_positions.insert(symbol.to_string(), Decimal::from(10000));

        let mut config = RiskConfig::new();
        config.slot_max_vega = Some(Decimal::from_str("0.01").unwrap());

        let result = check_slot_greek_limit(
            "slot_a",
            &slot_positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        assert!(result.is_some());
        let err = result.unwrap();
        assert!(err.contains("vega"));
        assert!(err.contains("slot_a"));
    }

    #[test]
    fn slot_greek_limit_skips_zero_quantity() {
        let symbol = "OPT_CALL";
        let instr = make_option_instrument(
            symbol,
            "UL",
            Decimal::from(100),
            crate::model::types::OptionType::Call,
            Decimal::ONE,
        );
        let mut instruments = HashMap::new();
        instruments.insert(symbol.to_string(), instr);
        let mut prices = HashMap::new();
        prices.insert("UL".to_string(), Decimal::from(110));

        // Zero quantity should not trigger
        let mut slot_positions = HashMap::new();
        slot_positions.insert(symbol.to_string(), Decimal::ZERO);

        let mut config = RiskConfig::new();
        config.slot_max_delta = Some(Decimal::from(1));

        let result = check_slot_greek_limit(
            "slot_a",
            &slot_positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        assert!(result.is_none());
    }

    #[test]
    fn slot_greek_limit_skips_missing_underlying_price() {
        let symbol = "OPT_CALL";
        let instr = make_option_instrument(
            symbol,
            "UL",
            Decimal::from(100),
            crate::model::types::OptionType::Call,
            Decimal::ONE,
        );
        let mut instruments = HashMap::new();
        instruments.insert(symbol.to_string(), instr);
        // Missing underlying price
        let prices = HashMap::new();

        let mut slot_positions = HashMap::new();
        slot_positions.insert(symbol.to_string(), Decimal::from(100));

        let mut config = RiskConfig::new();
        config.slot_max_delta = Some(Decimal::from(1));

        let result = check_slot_greek_limit(
            "slot_a",
            &slot_positions,
            &instruments,
            &prices,
            1_700_000_000_000_000_000,
            &config,
        );
        // Should not crash, just skip this position (no option data computed)
        assert!(result.is_none());
    }
}
