use crate::event::Event;
use crate::execution::common::CommonMatcher;
use crate::execution::matcher::{ExecutionMatcher, MatchContext};
use crate::model::Order;

pub struct FuturesMatcher;

impl ExecutionMatcher for FuturesMatcher {
    fn match_order(&self, order: &mut Order, ctx: &MatchContext) -> Option<Event> {
        // Futures specific logic
        // Futures typically allow fractional lot sizes or just 1 contract.
        // We usually don't enforce "Round Lot" for futures in the same way as Stocks (Buy Only 100).
        // So check_lot_size = false, or true if we want strict multiples of lot_size (usually 1).
        // Let's set true but assuming lot_size is 1 for futures, or strict multiple check is desired.
        // Actually, for futures, `quantity` must be integer multiple of `lot_size` (usually 1).
        // Unlike stocks where you can sell 1 share (odd lot) but buy 100.
        // Let's assume strict check for both sides? CommonMatcher only checks Buy side if check_lot_size=true.
        // So for futures, we might want custom check or just rely on CommonMatcher's Buy check if lot_size=1.

        CommonMatcher::match_order(
            order, ctx,
            false, // Don't enforce "Buy Only Lot Size" rule specific to A-shares. Futures can buy/sell any integer lot.
        )
    }
}
