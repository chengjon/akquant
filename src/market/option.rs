use crate::model::{Instrument, OrderSide};
use rust_decimal::Decimal;
use std::collections::HashMap;

#[derive(Clone, Debug)]
pub struct OptionConfig {
    pub commission_per_contract: Decimal,
}

impl Default for OptionConfig {
    fn default() -> Self {
        Self {
            commission_per_contract: Decimal::from(5),
        }
    }
}

/// 计算期权交易费用 (按张收取)
pub fn calculate_commission(
    config: &OptionConfig,
    _instrument: &Instrument,
    _side: OrderSide,
    _price: Decimal,
    quantity: Decimal,
    _multiplier: Decimal,
) -> Decimal {
    quantity * config.commission_per_contract
}

/// 更新期权可用持仓 (T+0)
pub fn update_available_position(
    _config: &OptionConfig,
    available_positions: &mut HashMap<String, Decimal>,
    symbol: &str,
    quantity: Decimal,
    side: OrderSide,
) {
    match side {
        OrderSide::Buy => {
            available_positions
                .entry(symbol.to_string())
                .or_insert(Decimal::ZERO);
            if let Some(pos) = available_positions.get_mut(symbol) {
                *pos += quantity;
            }
        }
        OrderSide::Sell => {
            available_positions
                .entry(symbol.to_string())
                .or_insert(Decimal::ZERO);
            if let Some(pos) = available_positions.get_mut(symbol) {
                *pos -= quantity;
            }
        }
    }
}
