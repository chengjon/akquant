use crate::event::Event;
use crate::execution::common::CommonMatcher;
use crate::execution::matcher::{ExecutionMatcher, MatchContext};
use crate::model::Order;

pub struct ForexMatcher;

impl ExecutionMatcher for ForexMatcher {
    fn match_order(&self, order: &mut Order, ctx: &MatchContext) -> Option<Event> {
        CommonMatcher::match_order(order, ctx, false)
    }
}
