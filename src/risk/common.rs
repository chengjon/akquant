use crate::error::AkQuantError;
use crate::model::{AssetType, Order, OrderSide};
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use std::collections::HashMap;

use super::rule::{RiskCheckContext, RiskRule};

const RISK_OVERFLOW_PREFIX: &str = "AKQ-RISK-OVERFLOW";

fn risk_overflow_error(symbol: &str, field: &str) -> AkQuantError {
    AkQuantError::OrderError(format!(
        "[{RISK_OVERFLOW_PREFIX}] overflow while calculating margin for {symbol} at {field}",
    ))
}

fn checked_add_or_cap(lhs: Decimal, rhs: Decimal) -> Decimal {
    lhs.checked_add(rhs).unwrap_or(Decimal::MAX)
}

fn checked_sub_or_zero(lhs: Decimal, rhs: Decimal) -> Decimal {
    lhs.checked_sub(rhs).unwrap_or(Decimal::ZERO)
}

fn checked_mul_or_err(
    lhs: Decimal,
    rhs: Decimal,
    symbol: &str,
    field: &str,
) -> Result<Decimal, AkQuantError> {
    lhs.checked_mul(rhs)
        .ok_or_else(|| risk_overflow_error(symbol, field))
}

fn checked_sub_or_err(
    lhs: Decimal,
    rhs: Decimal,
    symbol: &str,
    field: &str,
) -> Result<Decimal, AkQuantError> {
    lhs.checked_sub(rhs)
        .ok_or_else(|| risk_overflow_error(symbol, field))
}

/// Check restricted list
#[derive(Debug, Clone)]
pub struct RestrictedListRule;

impl RiskRule for RestrictedListRule {
    fn name(&self) -> &'static str {
        "RestrictedListRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        if ctx.config.restricted_list.contains(&order.symbol) {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Symbol {} is restricted",
                order.symbol
            )));
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

/// Check max order size
#[derive(Debug, Clone)]
pub struct MaxOrderSizeRule;

impl RiskRule for MaxOrderSizeRule {
    fn name(&self) -> &'static str {
        "MaxOrderSizeRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        if let Some(max_size) = ctx.config.max_order_size
            && order.quantity > max_size
        {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Order quantity {} exceeds limit {}",
                order.quantity, max_size
            )));
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

/// Check max order value
#[derive(Debug, Clone)]
pub struct MaxOrderValueRule;

impl RiskRule for MaxOrderValueRule {
    fn name(&self) -> &'static str {
        "MaxOrderValueRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        if let Some(max_value) = ctx.config.max_order_value {
            let price = if let Some(p) = order.price {
                Some(p)
            } else {
                ctx.current_prices.get(&order.symbol).copied()
            };

            if let Some(p) = price {
                let value = p * order.quantity;
                if value > max_value {
                    return Err(AkQuantError::OrderError(format!(
                        "Risk: Order value {value} exceeds limit {max_value}",
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

/// Check max position size
#[derive(Debug, Clone)]
pub struct MaxPositionSizeRule;

impl RiskRule for MaxPositionSizeRule {
    fn name(&self) -> &'static str {
        "MaxPositionSizeRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        if let Some(max_pos) = ctx.config.max_position_size {
            let current_pos = ctx
                .portfolio
                .positions
                .get(&order.symbol)
                .copied()
                .unwrap_or(Decimal::ZERO);
            let new_pos = match order.side {
                OrderSide::Buy => current_pos + order.quantity,
                OrderSide::Sell => current_pos - order.quantity,
            };
            if new_pos.abs() > max_pos {
                return Err(AkQuantError::OrderError(format!(
                    "Risk: Resulting position {new_pos} exceeds limit {max_pos}",
                )));
            }
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

/// Check cash / margin sufficiency
#[derive(Debug, Clone)]
pub struct CashMarginRule;

impl RiskRule for CashMarginRule {
    fn name(&self) -> &'static str {
        "CashMarginRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        if ctx.config.check_cash {
            let order_price = if let Some(p) = order.price {
                p
            } else if let Some(p) = ctx.current_prices.get(&order.symbol) {
                *p
            } else {
                return Ok(());
            };

            let mut prices_for_order = ctx.current_prices.clone();
            prices_for_order.insert(order.symbol.clone(), order_price);

            let required_margin =
                calc_required_margin_delta(order, ctx, &prices_for_order, ctx.portfolio)?;

            if required_margin.is_zero() {
                return Ok(());
            }

            let mut projected_portfolio = ctx.portfolio.clone();
            let mut committed_margin = Decimal::ZERO;
            for o in ctx.active_orders {
                if o.status != crate::model::OrderStatus::New {
                    continue;
                }
                let active_price = if let Some(p) = o.price {
                    p
                } else if let Some(p) = ctx.current_prices.get(&o.symbol) {
                    *p
                } else {
                    continue;
                };
                let mut prices_for_active = ctx.current_prices.clone();
                prices_for_active.insert(o.symbol.clone(), active_price);
                committed_margin = checked_add_or_cap(
                    committed_margin,
                    calc_required_margin_delta(o, ctx, &prices_for_active, &projected_portfolio)?,
                );

                let positions = std::sync::Arc::make_mut(&mut projected_portfolio.positions);
                let entry = positions.entry(o.symbol.clone()).or_insert(Decimal::ZERO);
                match o.side {
                    OrderSide::Buy => *entry += o.quantity,
                    OrderSide::Sell => *entry -= o.quantity,
                }
            }

            let free_margin = ctx
                .portfolio
                .calculate_free_margin(ctx.current_prices, ctx.instruments);
            let safety_margin = ctx.config.safety_margin;
            let safety_factor = Decimal::from_f64(1.0 - safety_margin)
                .unwrap_or(Decimal::from_f64(0.9999).unwrap());
            let available_margin = checked_sub_or_zero(
                free_margin
                    .checked_mul(safety_factor)
                    .unwrap_or(Decimal::ZERO),
                committed_margin,
            )
            .max(Decimal::ZERO);

            if required_margin > available_margin {
                return Err(AkQuantError::OrderError(format!(
                    "Risk: Insufficient margin. Required: {required_margin}, Available: {available_margin} (Free: {free_margin}, Committed: {committed_margin}, Safety: {safety_margin})",
                )));
            }
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

fn stock_margin_delta(
    order: &Order,
    current_pos: Decimal,
    price: Decimal,
    multiplier: Decimal,
    initial_margin_ratio: Decimal,
) -> Result<Decimal, AkQuantError> {
    let current_abs = current_pos.abs();
    let safe_price = price.abs();
    let safe_multiplier = multiplier.abs();
    let safe_initial_margin_ratio = initial_margin_ratio.abs();
    let next_pos = match order.side {
        OrderSide::Buy => current_pos + order.quantity,
        OrderSide::Sell => current_pos - order.quantity,
    };
    let next_abs = next_pos.abs();
    let current_notional = checked_mul_or_err(
        current_abs,
        safe_price,
        &order.symbol,
        "current_abs * price",
    )?;
    let current_gross = checked_mul_or_err(
        current_notional,
        safe_multiplier,
        &order.symbol,
        "current_notional * multiplier",
    )?;
    let current_margin = checked_mul_or_err(
        current_gross,
        safe_initial_margin_ratio,
        &order.symbol,
        "current_gross * initial_margin_ratio",
    )?;

    let next_notional =
        checked_mul_or_err(next_abs, safe_price, &order.symbol, "next_abs * price")?;
    let next_gross = checked_mul_or_err(
        next_notional,
        safe_multiplier,
        &order.symbol,
        "next_notional * multiplier",
    )?;
    let next_margin = checked_mul_or_err(
        next_gross,
        safe_initial_margin_ratio,
        &order.symbol,
        "next_gross * initial_margin_ratio",
    )?;

    Ok(checked_sub_or_zero(next_margin, current_margin).max(Decimal::ZERO))
}

fn calc_required_margin_delta(
    order: &Order,
    ctx: &RiskCheckContext,
    prices: &HashMap<String, Decimal>,
    portfolio: &crate::portfolio::Portfolio,
) -> Result<Decimal, AkQuantError> {
    if let Some(instr) = ctx.instruments.get(&order.symbol) {
        if ctx.config.is_margin_account()
            && (instr.asset_type == AssetType::Stock || instr.asset_type == AssetType::Fund)
        {
            let price = prices
                .get(&order.symbol)
                .copied()
                .unwrap_or_else(|| order.price.unwrap_or(Decimal::ZERO));
            if price <= Decimal::ZERO {
                return Ok(Decimal::ZERO);
            }
            let current_pos = portfolio
                .positions
                .get(&order.symbol)
                .copied()
                .unwrap_or(Decimal::ZERO);
            return stock_margin_delta(
                order,
                current_pos,
                price,
                instr.multiplier(),
                ctx.config.stock_initial_margin_ratio(),
            );
        }
    }

    let mut projected_portfolio = portfolio.clone();
    let base_used = projected_portfolio.calculate_used_margin(prices, ctx.instruments);
    if base_used == Decimal::MAX {
        return Err(risk_overflow_error(&order.symbol, "base_used_margin"));
    }
    {
        let positions = std::sync::Arc::make_mut(&mut projected_portfolio.positions);
        let entry = positions
            .entry(order.symbol.clone())
            .or_insert(Decimal::ZERO);
        match order.side {
            OrderSide::Buy => *entry += order.quantity,
            OrderSide::Sell => *entry -= order.quantity,
        }
    }
    let next_used = projected_portfolio.calculate_used_margin(prices, ctx.instruments);
    if next_used == Decimal::MAX {
        return Err(risk_overflow_error(&order.symbol, "next_used_margin"));
    }
    let delta = checked_sub_or_err(next_used, base_used, &order.symbol, "next_used - base_used")?;
    Ok(delta.max(Decimal::ZERO))
}
