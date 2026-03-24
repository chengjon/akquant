use crate::model::{Instrument, OrderSide};
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use std::collections::HashMap;

#[derive(Clone, Debug)]
pub struct FuturesConfig {
    pub commission_rate: Decimal,
}

impl Default for FuturesConfig {
    fn default() -> Self {
        Self {
            commission_rate: Decimal::from_str("0.000023").unwrap(),
        }
    }
}

/// 计算期货交易费用
pub fn calculate_commission(
    config: &FuturesConfig,
    _instrument: &Instrument,
    _side: OrderSide,
    price: Decimal,
    quantity: Decimal,
    multiplier: Decimal,
) -> Decimal {
    let transaction_value = price * quantity * multiplier;
    transaction_value * config.commission_rate
}

/// 更新期货可用持仓 (T+0)
pub fn update_available_position(
    _config: &FuturesConfig,
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{AssetType, Instrument};

    fn create_future_instrument(symbol: &str) -> Instrument {
        use crate::model::instrument::{FuturesInstrument, InstrumentEnum};
        Instrument {
            asset_type: AssetType::Futures,
            inner: InstrumentEnum::Futures(FuturesInstrument {
                symbol: symbol.to_string(),
                multiplier: Decimal::from(300),
                tick_size: Decimal::from_str("0.2").unwrap(),
                margin_ratio: Decimal::from_str("0.1").unwrap(),
                expiry_date: None,
                settlement_type: None,
                settlement_price: None,
            }),
        }
    }

    #[test]
    fn test_futures_t_plus_zero() {
        let config = FuturesConfig::default();
        let instr = create_future_instrument("IF2206");
        let mut available = HashMap::new();

        // Buy 1. T+0 means available increases immediately.
        update_available_position(
            &config,
            &mut available,
            instr.symbol(),
            Decimal::from(1),
            OrderSide::Buy,
        );
        assert_eq!(*available.get("IF2206").unwrap(), Decimal::from(1));
    }
}
