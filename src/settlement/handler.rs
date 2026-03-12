use crate::model::Instrument;
use crate::portfolio::Portfolio;
use chrono::NaiveDate;
use rust_decimal::Decimal;
use std::collections::HashMap;
use std::sync::Arc;

/// Task representing a settlement action to be executed
#[derive(Debug, Clone)]
pub struct SettlementTask {
    pub symbol: String,
    pub quantity: Decimal,
    pub cash_flow: Decimal,
    pub description: String,
}

/// Trait for handling settlement logic (e.g., Option Expiry, Futures Delivery)
pub trait SettlementHandler: Send + Sync {
    /// Check for settlement events on a given date and generate tasks
    fn check_settlement(
        &self,
        date: NaiveDate,
        portfolio: &Portfolio,
        instruments: &HashMap<String, Instrument>,
        last_prices: &HashMap<String, Decimal>,
    ) -> Vec<SettlementTask>;

    /// Execute a settlement task on the portfolio
    fn execute(&self, task: SettlementTask, portfolio: &mut Portfolio) {
        if !task.cash_flow.is_zero() {
            portfolio.adjust_cash(task.cash_flow);
        }

        // Remove position (assuming full settlement for now, or use adjust_position for partial)
        // For Option Expiry, we typically close the position.
        // But SettlementTask needs to be flexible.
        // Let's assume the task implies closing the position quantity mentioned.
        // If quantity is the full position, it closes it.
        portfolio.adjust_position(&task.symbol, -task.quantity);

        // Note: available_positions should also be updated.
        // Portfolio::adjust_position updates `positions` map.
        // We might need a method on Portfolio to remove from `available_positions` too if needed,
        // or assume `adjust_position` handles it?
        // Checking `portfolio.rs`: `adjust_position` only updates `positions`.
        // We need to handle `available_positions` if we are closing.
        // Actually `adjust_position` adds to the map. If we add negative, it reduces.

        // However, `available_positions` logic is usually handled by OrderManager (locking).
        // For settlement, we should probably clear both.
        // Let's add a specific method on Portfolio for settlement or handle it here manually if possible.
        // Accessing fields directly is possible since they are pub.

        let avail_pos = Arc::make_mut(&mut portfolio.available_positions);
        if let Some(avail) = avail_pos.get_mut(&task.symbol) {
            *avail -= task.quantity;
            // If zero or less (float issues?), remove?
            // Clean up if zero is done later usually.
        }

        // Clean up zero positions
        let is_zero = portfolio
            .positions
            .get(&task.symbol)
            .is_some_and(rust_decimal::Decimal::is_zero);
        if is_zero {
            let positions = Arc::make_mut(&mut portfolio.positions);
            positions.remove(&task.symbol);

            let avail_pos = Arc::make_mut(&mut portfolio.available_positions);
            avail_pos.remove(&task.symbol);
        }
    }
}
