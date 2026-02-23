use crate::event::Event;
use crate::execution::common::CommonMatcher;
use crate::execution::matcher::ExecutionMatcher;
use crate::execution::slippage::SlippageModel;
use crate::model::{ExecutionMode, Instrument, Order};
use rust_decimal::Decimal;

pub struct CryptoMatcher;

impl ExecutionMatcher for CryptoMatcher {
    fn match_order(
        &self,
        order: &mut Order,
        event: &Event,
        instrument: &Instrument,
        execution_mode: ExecutionMode,
        slippage: &dyn SlippageModel,
        volume_limit_pct: Decimal,
        bar_index: usize,
    ) -> Option<Event> {
        CommonMatcher::match_order(
            order,
            event,
            instrument,
            execution_mode,
            slippage,
            volume_limit_pct,
            bar_index,
            false,
        )
    }
}
