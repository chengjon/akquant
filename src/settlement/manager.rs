use crate::market::manager::MarketManager;
use crate::model::{Instrument, Order, OrderStatus, TimeInForce};
use crate::portfolio::Portfolio;
use chrono::NaiveDate;
use rust_decimal::Decimal;
use std::collections::HashMap;
use std::sync::Arc;

use super::handler::SettlementHandler;
use super::option::OptionSettlementHandler;

/// Settlement Context
pub struct SettlementContext<'a> {
    pub date: NaiveDate,
    pub instruments: &'a HashMap<String, Instrument>,
    pub last_prices: &'a HashMap<String, Decimal>,
    pub market_manager: &'a MarketManager,
}

/// Settlement Manager
/// Centralizes daily settlement logic including T+1 settlement, option expiry, and order expiration.
pub struct SettlementManager {
    option_handler: OptionSettlementHandler,
}

impl SettlementManager {
    pub fn new() -> Self {
        Self {
            option_handler: OptionSettlementHandler,
        }
    }

    /// Process daily settlement routine
    /// 1. T+1 Settlement (MarketManager)
    /// 2. Option Expiry
    /// 3. Order Expiration (Day orders)
    pub fn process_daily_settlement(
        &self,
        portfolio: &mut Portfolio,
        active_orders: &mut Vec<Order>,
        expired_orders_out: &mut Vec<Order>,
        ctx: &SettlementContext,
    ) {
        // 1. Market Settlement (T+1 logic)
        // Note: MarketManager::on_day_close handles T+1 by moving positions from 'positions' to 'available_positions'
        // But wait, `portfolio.positions` is T+0/Total, `available_positions` is Sellable.
        // `on_day_close` updates `available_positions`.
        ctx.market_manager.on_day_close(
            &portfolio.positions,
            Arc::make_mut(&mut portfolio.available_positions),
            ctx.instruments,
        );

        // 2. Option Expiry
        let tasks = self.option_handler.check_settlement(
            ctx.date,
            portfolio,
            ctx.instruments,
            ctx.last_prices,
        );

        for task in tasks {
            // Execute settlement task
            // 1. Adjust Cash
            if !task.cash_flow.is_zero() {
                portfolio.cash += task.cash_flow;
            }

            // 2. Close Position
            // Remove from total positions
            {
                let positions = Arc::make_mut(&mut portfolio.positions);
                if let Some(qty) = positions.get_mut(&task.symbol) {
                    *qty -= task.quantity;
                    if qty.is_zero() {
                        positions.remove(&task.symbol);
                    }
                }
            }

            // Remove from available positions
            {
                let avail_pos = Arc::make_mut(&mut portfolio.available_positions);
                if let Some(qty) = avail_pos.get_mut(&task.symbol) {
                    *qty -= task.quantity;
                    if qty.is_zero() {
                        avail_pos.remove(&task.symbol);
                    }
                }
            }
        }

        // 3. Order Expiration (Day Orders)
        // Partition orders into expired and kept
        let (expired, kept): (Vec<Order>, Vec<Order>) = active_orders
            .drain(..)
            .partition(|o| o.time_in_force == TimeInForce::Day);

        *active_orders = kept;

        for mut o in expired {
            o.status = OrderStatus::Expired;
            expired_orders_out.push(o);
        }
    }
}

impl Default for SettlementManager {
    fn default() -> Self {
        Self::new()
    }
}
