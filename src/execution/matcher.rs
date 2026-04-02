use crate::event::Event;
use crate::execution::slippage::SlippageModel;
use crate::model::{ExecutionPolicyCore, Instrument, Order};
use rust_decimal::Decimal;

/// 撮合上下文
pub struct MatchContext<'a> {
    pub event: &'a Event,
    pub instrument: &'a Instrument,
    pub execution_policy_core: ExecutionPolicyCore,
    pub slippage: &'a dyn SlippageModel,
    pub volume_limit_pct: Decimal,
    pub bar_index: usize,
    pub last_price: Option<Decimal>,
}

/// 撮合器接口
pub trait ExecutionMatcher: Send + Sync {
    fn match_order(&self, order: &mut Order, ctx: &MatchContext) -> Option<Event>;
}
