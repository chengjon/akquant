use crate::error::AkQuantError;
use crate::model::Order;

use super::rule::{RiskCheckContext, RiskRule};

/// Placeholder for specific futures margin rule
/// Currently generic CashMarginRule covers basic margin checks.
#[derive(Debug, Clone)]
pub struct FuturesMarginRule;

impl RiskRule for FuturesMarginRule {
    fn name(&self) -> &'static str {
        "FuturesMarginRule"
    }

    fn check(&self, _order: &Order, _ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        // TODO: Implement advanced futures margin logic (e.g. maintenance margin vs initial margin)
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}
