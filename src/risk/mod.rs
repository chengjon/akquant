pub mod common;
pub mod config;
pub mod futures;
pub mod manager;
pub mod option;
pub mod portfolio;
pub mod rule;
pub mod stock;

pub use config::RiskConfig;
pub use manager::RiskManager;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::instrument::{FuturesInstrument, InstrumentEnum, StockInstrument};
    use crate::model::{
        AssetType, Instrument, Order, OrderSide, OrderStatus, OrderType, TimeInForce,
    };
    use crate::portfolio::Portfolio;
    use rust_decimal::prelude::*;
    use rust_decimal::Decimal;
    use std::collections::HashMap;

    fn create_test_order(symbol: &str, quantity: Decimal, price: Option<Decimal>) -> Order {
        Order {
            id: "test_order".to_string(),
            symbol: symbol.to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            quantity,
            price,
            status: OrderStatus::New,
            time_in_force: TimeInForce::Day,
            trigger_price: None,
            filled_quantity: Decimal::ZERO,
            average_filled_price: None,
            created_at: chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0),
            updated_at: chrono::Utc::now().timestamp_nanos_opt().unwrap_or(0),
            commission: Decimal::ZERO,
            tag: "".to_string(),
            reject_reason: "".to_string(),
        }
    }

    fn create_test_instrument(symbol: &str, asset_type: AssetType) -> Instrument {
        let inner = match asset_type {
            AssetType::Stock => InstrumentEnum::Stock(StockInstrument {
                symbol: symbol.to_string(),
                lot_size: Decimal::from(100),
                tick_size: Decimal::from_str("0.01").unwrap(),
            }),
            AssetType::Futures => InstrumentEnum::Futures(FuturesInstrument {
                symbol: symbol.to_string(),
                multiplier: Decimal::from(10),
                margin_ratio: Decimal::from_str("0.1").unwrap(),
                tick_size: Decimal::from_str("0.2").unwrap(),
                expiry_date: None,
                settlement_type: None,
            }),
            _ => panic!("Unsupported asset type for test"),
        };
        Instrument {
            asset_type,
            inner,
        }
    }

    #[test]
    fn test_risk_manager_basic() {
        let mut manager = RiskManager::default();
        manager.config.max_order_size = Some(Decimal::from(100));
        manager.config.restricted_list = vec!["BAD_STOCK".to_string()];

        let portfolio = Portfolio {
            cash: Decimal::from(100000),
            positions: std::sync::Arc::new(HashMap::new()),
            available_positions: std::sync::Arc::new(HashMap::new()),
        };
        let mut instruments = HashMap::new();
        instruments.insert(
            "AAPL".to_string(),
            create_test_instrument("AAPL", AssetType::Stock),
        );
        instruments.insert(
            "BAD_STOCK".to_string(),
            create_test_instrument("BAD_STOCK", AssetType::Stock),
        );

        // Test valid order
        let order = create_test_order("AAPL", Decimal::from(50), Some(Decimal::from(150)));
        let result = manager.check(&order, &portfolio, instruments.clone(), vec![], None);
        assert!(result.is_none());

        // Test max order size
        let order_large = create_test_order("AAPL", Decimal::from(150), Some(Decimal::from(150)));
        let result = manager.check(&order_large, &portfolio, instruments.clone(), vec![], None);
        assert!(result.is_some());
        assert!(result.unwrap().contains("exceeds limit"));

        // Test restricted list
        let order_restricted =
            create_test_order("BAD_STOCK", Decimal::from(50), Some(Decimal::from(10)));
        let result = manager.check(
            &order_restricted,
            &portfolio,
            instruments.clone(),
            vec![],
            None,
        );
        assert!(result.is_some());
        assert!(result.unwrap().contains("restricted"));
    }
}
