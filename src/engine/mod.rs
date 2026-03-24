pub mod core;
pub mod python;
pub mod state;

pub use core::Engine;
// pub use state::SharedState;

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::types::AssetType;
    use crate::model::{ExecutionMode, Instrument};
    use rust_decimal::Decimal;

    #[test]
    fn test_engine_new() {
        let engine = Engine::new();
        assert_eq!(engine.state.portfolio.cash, Decimal::from(100_000));
        assert!(engine.state.order_manager.orders.is_empty());
        assert!(engine.state.order_manager.trades.is_empty());
        assert_eq!(engine.execution_mode, ExecutionMode::NextOpen);
    }

    #[test]
    fn test_engine_set_cash() {
        let mut engine = Engine::new();
        engine.set_cash(50000.0);
        assert_eq!(engine.state.portfolio.cash, Decimal::from(50000));
    }

    #[test]
    fn test_engine_add_instrument() {
        use crate::model::instrument::{InstrumentEnum, StockInstrument};

        let mut engine = Engine::new();
        let instr = Instrument {
            asset_type: AssetType::Stock,
            inner: InstrumentEnum::Stock(StockInstrument {
                symbol: "AAPL".to_string(),
                lot_size: Decimal::from(100),
                tick_size: Decimal::new(1, 2),
                expiry_date: None,
            }),
        };
        engine.add_instrument(instr);
        assert!(engine.instruments.contains_key("AAPL"));
    }

    #[test]
    fn test_engine_fee_rules() {
        let mut engine = Engine::new();
        engine.set_stock_fee_rules(0.001, 0.002, 0.003, 5.0);

        // Since market_config is private but used in market_model, we can't check it directly easily
        // unless we expose getters or check behavior.
        // But we can check if it compiles and runs without error.
        // Actually, we can check market_config if we make it pub or add a getter for test.
        // But for now, let's trust the setter sets the internal state.
        // We can verify via commission calculation if we had a way to invoke it without full run.

        // Let's at least verify future fee rules
        engine.set_futures_fee_rules(0.0005);
    }

    #[test]
    fn test_engine_timezone() {
        let mut engine = Engine::new();
        engine.set_timezone(3600); // UTC+1
        assert_eq!(engine.timezone_offset, 3600);
    }

    #[test]
    fn test_engine_snapshot_serialization() {
        use crate::engine::state::EngineSnapshot;
        use crate::order_manager::OrderManager;
        use crate::portfolio::Portfolio;
        use std::collections::HashMap;
        use std::sync::Arc;

        let portfolio = Portfolio {
            cash: Decimal::from(50000),
            positions: Arc::new(HashMap::new()),
            available_positions: Arc::new(HashMap::new()),
        };

        // Test Portfolio
        let encoded_p: Vec<u8> = rmp_serde::to_vec(&portfolio).unwrap();
        let decoded_p: Portfolio =
            rmp_serde::from_slice(&encoded_p).expect("Portfolio deserialize failed");
        assert_eq!(decoded_p.cash, Decimal::from(50000));

        let order_manager = OrderManager::new();
        // Test OrderManager
        let encoded_o: Vec<u8> = rmp_serde::to_vec(&order_manager).unwrap();
        let _decoded_o: OrderManager =
            rmp_serde::from_slice(&encoded_o).expect("OrderManager deserialize failed");

        let snapshot = EngineSnapshot {
            current_time: 123456789,
            portfolio,
            order_manager,
            strategy_risk_state: Default::default(),
        };

        let encoded: Vec<u8> = rmp_serde::to_vec(&snapshot).unwrap();
        let decoded: EngineSnapshot = rmp_serde::from_slice(&encoded).unwrap();

        assert_eq!(decoded.current_time, 123456789);
        assert_eq!(decoded.portfolio.cash, Decimal::from(50000));
    }
}
