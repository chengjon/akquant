use crate::event::Event;
use crate::execution::common::CommonMatcher;
use crate::execution::matcher::{ExecutionMatcher, MatchContext};
use crate::model::Order;

pub struct OptionMatcher;

impl ExecutionMatcher for OptionMatcher {
    fn match_order(
        &self,
        order: &mut Order,
        ctx: &MatchContext,
    ) -> Option<Event> {
        // Option specific logic
        // Similar to Futures, options are traded in contracts (lots).
        // Usually 1 contract is the minimum.
        CommonMatcher::match_order(
            order,
            ctx,
            false,
        )
    }
}
