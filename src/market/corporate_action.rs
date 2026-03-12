use crate::analysis::tracker::TradeTracker;
use crate::model::corporate_action::{CorporateAction, CorporateActionType};
use crate::portfolio::Portfolio;
use chrono::NaiveDate;
use std::collections::HashMap;
use std::sync::Arc;

pub struct CorporateActionManager {
    actions: HashMap<NaiveDate, Vec<CorporateAction>>,
}

impl Default for CorporateActionManager {
    fn default() -> Self {
        Self::new()
    }
}

impl CorporateActionManager {
    pub fn new() -> Self {
        Self {
            actions: HashMap::new(),
        }
    }

    pub fn add(&mut self, action: CorporateAction) {
        self.actions.entry(action.date).or_default().push(action);
    }

    pub fn process_date(
        &self,
        date: NaiveDate,
        portfolio: &mut Portfolio,
        trade_tracker: &mut TradeTracker,
    ) {
        if let Some(actions) = self.actions.get(&date) {
            for action in actions {
                match action.action_type {
                    CorporateActionType::Split => {
                        // Split: ratio > 1.0 (e.g. 2.0 means 1 share becomes 2)
                        // Reverse Split: ratio < 1.0 (e.g. 0.5 means 2 shares become 1)
                        // Quantity *= ratio, AvgCost /= ratio
                        let ratio = action.value;

                        let positions = Arc::make_mut(&mut portfolio.positions);
                        if let Some(qty) = positions.get_mut(&action.symbol) {
                            *qty *= ratio;
                        }

                        let available = Arc::make_mut(&mut portfolio.available_positions);
                        if let Some(avail) = available.get_mut(&action.symbol) {
                            *avail *= ratio;
                        }

                        // Update TradeTracker (Inventory Cost Basis)
                        trade_tracker.on_split(&action.symbol, ratio);
                    }
                    CorporateActionType::Dividend => {
                        // Dividend: value is cash per share
                        // Cash += Quantity * value
                        if let Some(qty) = portfolio.positions.get(&action.symbol)
                            && !qty.is_zero()
                        {
                            let dividend_amount = qty * action.value;
                            portfolio.cash += dividend_amount;
                        }
                    }
                }
            }
        }
    }
}
