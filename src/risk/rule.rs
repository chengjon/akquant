use crate::error::AkQuantError;
use crate::model::{Instrument, Order};
use crate::portfolio::Portfolio;
use rust_decimal::Decimal;
use std::collections::HashMap;
use std::fmt::Debug;

use super::RiskConfig;

/// Context for risk checks
pub struct RiskCheckContext<'a> {
    pub portfolio: &'a Portfolio,
    pub instrument: &'a Instrument,
    pub instruments: &'a HashMap<String, Instrument>,
    pub active_orders: &'a [Order],
    pub current_prices: &'a HashMap<String, Decimal>,
    pub current_time: i64,
    pub config: &'a RiskConfig,
}

/// Trait for risk check rules
pub trait RiskRule: Send + Sync + Debug {
    /// Check if the order passes the risk rule
    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError>;

    /// Get the name of the rule
    fn name(&self) -> &'static str;

    /// Clone the rule
    fn clone_box(&self) -> Box<dyn RiskRule>;
}

impl Clone for Box<dyn RiskRule> {
    fn clone(&self) -> Box<dyn RiskRule> {
        self.clone_box()
    }
}
