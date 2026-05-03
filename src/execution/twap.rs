use crate::event::Event;
use crate::model::{Order, OrderSide, PriceBasis};
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use std::collections::HashMap;

/// Per-order TWAP state tracking how many bars have elapsed.
pub struct TwapState {
    pub num_bars: u32,
    pub bars_elapsed: u32,
    pub symbol: String,
    pub side: OrderSide,
}

/// Manages TWAP order state: tracks bars elapsed per parent order.
///
/// TWAP orders stay in the normal order queue. The scheduler computes the
/// per-bar slice quantity so the SimulatedExecutionClient can cap fills.
pub struct TwapScheduler {
    states: HashMap<String, TwapState>,
}

impl TwapScheduler {
    pub fn new() -> Self {
        Self {
            states: HashMap::new(),
        }
    }

    /// Register a TWAP order for tracking.
    pub fn register(&mut self, order: &Order, num_bars: u32) {
        if num_bars == 0 {
            return;
        }
        self.states.insert(
            order.id.clone(),
            TwapState {
                num_bars,
                bars_elapsed: 0,
                symbol: order.symbol.clone(),
                side: order.side,
            },
        );
    }

    /// Cancel tracking for a TWAP order.
    pub fn cancel(&mut self, order_id: &str) {
        self.states.remove(order_id);
    }

    /// Check if an order is a tracked TWAP order.
    pub fn is_twap(&self, order_id: &str) -> bool {
        self.states.contains_key(order_id)
    }

    /// Check if an order has a TWAP fill policy (engine-level or per-order).
    pub fn is_twap_order(order: &Order, engine_basis: PriceBasis) -> bool {
        let basis = order
            .fill_policy_override
            .map_or(engine_basis, |p| p.price_basis);
        basis == PriceBasis::TwapWindow
    }

    /// Get the TWAP config (num_bars) for an order.
    pub fn get_twap_bars(order: &Order, engine_twap_bars: u32) -> u32 {
        order
            .fill_policy_override
            .map_or(engine_twap_bars, |p| p.twap_bars)
    }

    /// Called once per bar event. Increments bar counters for all active TWAP orders.
    pub fn on_bar(&mut self) {
        for state in self.states.values_mut() {
            state.bars_elapsed += 1;
        }
    }

    /// Compute the maximum fill quantity for a TWAP order on this bar.
    /// `remaining_qty` = order.quantity - order.filled_quantity
    pub fn slice_quantity(
        &self,
        order_id: &str,
        remaining_qty: Decimal,
    ) -> Option<Decimal> {
        let state = self.states.get(order_id)?;
        let bars_remaining = state.num_bars.saturating_sub(state.bars_elapsed);
        if bars_remaining == 0 || remaining_qty <= Decimal::ZERO {
            return Some(Decimal::ZERO);
        }
        // Even split: remaining / bars_remaining
        let slice = remaining_qty / Decimal::from(bars_remaining);
        Some(slice.min(remaining_qty))
    }

    /// Remove a completed TWAP order from tracking.
    pub fn remove(&mut self, order_id: &str) {
        self.states.remove(order_id);
    }
}
