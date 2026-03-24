use crate::error::AkQuantError;
use crate::model::{AssetType, Order, OrderSide};
use rust_decimal::Decimal;
use rust_decimal::prelude::*;

use super::rule::{RiskCheckContext, RiskRule};

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
        if ctx.config.check_cash && order.side == OrderSide::Buy {
            let mut required_margin = Decimal::ZERO;
            let mut price_found = false;

            // Get instrument info for multiplier and margin_ratio
            let multiplier = ctx.instrument.multiplier();
            let margin_ratio = ctx.instrument.margin_ratio();

            // Determine price for current order
            if let Some(p) = order.price {
                required_margin = p * order.quantity * multiplier * margin_ratio;
                price_found = true;
            } else if let Some(p) = ctx.current_prices.get(&order.symbol) {
                required_margin = *p * order.quantity * multiplier * margin_ratio;
                price_found = true;
            }

            if price_found {
                // Check Active Buy Orders for committed margin
                let mut committed_margin = Decimal::ZERO;
                let mut pending_sell_release = Decimal::ZERO;
                for o in ctx.active_orders {
                    if o.side == OrderSide::Buy && o.status == crate::model::OrderStatus::New {
                        let (o_mult, o_margin_ratio) =
                            if let Some(instr) = ctx.instruments.get(&o.symbol) {
                                (instr.multiplier(), instr.margin_ratio())
                            } else {
                                (Decimal::ONE, Decimal::ONE)
                            };

                        if let Some(p) = o.price {
                            committed_margin += p * o.quantity * o_mult * o_margin_ratio;
                        } else if let Some(p) = ctx.current_prices.get(&o.symbol) {
                            committed_margin += *p * o.quantity * o_mult * o_margin_ratio;
                        }
                    } else if o.side == OrderSide::Sell
                        && o.status == crate::model::OrderStatus::New
                        && let Some(instr) = ctx.instruments.get(&o.symbol)
                        && matches!(instr.asset_type, AssetType::Stock | AssetType::Fund)
                    {
                        if let Some(p) = o.price {
                            pending_sell_release += p * o.quantity;
                        } else if let Some(p) = ctx.current_prices.get(&o.symbol) {
                            pending_sell_release += *p * o.quantity;
                        }
                    }
                }

                // Calculate Free Margin
                let free_margin = ctx
                    .portfolio
                    .calculate_free_margin(ctx.current_prices, ctx.instruments);

                // Apply Safety Margin (default 0.0001 or user config)
                let safety_margin = ctx.config.safety_margin;
                // Safety factor = 1.0 - margin (e.g., 0.9999)
                let safety_factor = Decimal::from_f64(1.0 - safety_margin)
                    .unwrap_or(Decimal::from_f64(0.9999).unwrap());

                // Available Margin = (Free Margin - Committed Margin + Pending Sell Release) * Safety Factor
                // Note: Free Margin already accounts for Used Margin of existing positions
                let available_margin =
                    (free_margin - committed_margin + pending_sell_release) * safety_factor;

                if required_margin > available_margin {
                    return Err(AkQuantError::OrderError(format!(
                        "Risk: Insufficient margin. Required: {required_margin}, Available: {available_margin} (Free: {free_margin}, Committed: {committed_margin}, PendingSellRelease: {pending_sell_release}, Safety: {safety_margin})",
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
