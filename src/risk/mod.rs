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
        AssetType, ExecutionMode, Instrument, Order, OrderSide, OrderStatus, OrderType,
        TimeInForce, TradingSession,
    };
    use crate::portfolio::Portfolio;
    use rust_decimal::prelude::*;
    use rust_decimal::Decimal;
    use std::collections::HashMap;
    use std::sync::Arc;

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
            tag: String::new(),
            reject_reason: String::new(),
            owner_strategy_id: None,
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

    #[test]
    fn test_max_drawdown_rule_blocks_orders_after_breach() {
        let mut manager = RiskManager::default();
        manager.add_max_drawdown_rule(0.10);
        manager.config.check_cash = false;

        let mut positions = HashMap::new();
        positions.insert("AAPL".to_string(), Decimal::from(100));

        let portfolio = Portfolio {
            cash: Decimal::from(0),
            positions: Arc::new(positions.clone()),
            available_positions: Arc::new(positions),
        };
        let mut instruments = HashMap::new();
        instruments.insert(
            "AAPL".to_string(),
            create_test_instrument("AAPL", AssetType::Stock),
        );
        let order = create_test_order("AAPL", Decimal::from(10), Some(Decimal::from(100)));
        let market_model = crate::market::SimpleMarket::from_config(
            crate::market::SimpleMarketConfig::default(),
        );

        let mut prices_high = HashMap::new();
        prices_high.insert("AAPL".to_string(), Decimal::from(100));
        let ctx_high = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &prices_high,
            market_model: &market_model,
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 1,
            current_time: 1_700_000_000_000_000_000,
            session: TradingSession::Continuous,
            active_orders: &[],
        };
        assert!(manager.check_internal(&order, &ctx_high).is_ok());

        let mut prices_low = HashMap::new();
        prices_low.insert("AAPL".to_string(), Decimal::from(80));
        let ctx_low = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &prices_low,
            market_model: &market_model,
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 2,
            current_time: 1_700_000_100_000_000_000,
            session: TradingSession::Continuous,
            active_orders: &[],
        };
        let err = manager.check_internal(&order, &ctx_low).unwrap_err().to_string();
        assert!(err.contains("Max drawdown"));
    }

    #[test]
    fn test_max_daily_loss_rule_resets_on_new_day() {
        let mut manager = RiskManager::default();
        manager.add_max_daily_loss_rule(0.05);
        manager.config.check_cash = false;

        let mut positions = HashMap::new();
        positions.insert("AAPL".to_string(), Decimal::from(100));

        let portfolio = Portfolio {
            cash: Decimal::from(0),
            positions: Arc::new(positions.clone()),
            available_positions: Arc::new(positions),
        };
        let mut instruments = HashMap::new();
        instruments.insert(
            "AAPL".to_string(),
            create_test_instrument("AAPL", AssetType::Stock),
        );
        let order = create_test_order("AAPL", Decimal::from(10), Some(Decimal::from(100)));
        let market_model = crate::market::SimpleMarket::from_config(
            crate::market::SimpleMarketConfig::default(),
        );

        let day1_open = 1_700_000_000_000_000_000;
        let mut prices_day1_start = HashMap::new();
        prices_day1_start.insert("AAPL".to_string(), Decimal::from(100));
        let ctx_day1_start = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &prices_day1_start,
            market_model: &market_model,
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 1,
            current_time: day1_open,
            session: TradingSession::Continuous,
            active_orders: &[],
        };
        assert!(manager.check_internal(&order, &ctx_day1_start).is_ok());

        let mut prices_day1_drop = HashMap::new();
        prices_day1_drop.insert("AAPL".to_string(), Decimal::from(94));
        let ctx_day1_drop = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &prices_day1_drop,
            market_model: &market_model,
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 2,
            current_time: day1_open + 10_000_000_000,
            session: TradingSession::Continuous,
            active_orders: &[],
        };
        let err = manager
            .check_internal(&order, &ctx_day1_drop)
            .unwrap_err()
            .to_string();
        assert!(err.contains("Daily loss"));

        let mut prices_day2_start = HashMap::new();
        prices_day2_start.insert("AAPL".to_string(), Decimal::from(100));
        let ctx_day2_start = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &prices_day2_start,
            market_model: &market_model,
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 3,
            current_time: day1_open + 86_400_000_000_000,
            session: TradingSession::Continuous,
            active_orders: &[],
        };
        assert!(manager.check_internal(&order, &ctx_day2_start).is_ok());
    }

    #[test]
    fn test_stop_loss_rule_blocks_below_threshold() {
        let mut manager = RiskManager::default();
        manager.add_stop_loss_rule(0.90);
        manager.config.check_cash = false;

        let mut positions = HashMap::new();
        positions.insert("AAPL".to_string(), Decimal::from(100));

        let portfolio = Portfolio {
            cash: Decimal::from(0),
            positions: Arc::new(positions.clone()),
            available_positions: Arc::new(positions),
        };
        let mut instruments = HashMap::new();
        instruments.insert(
            "AAPL".to_string(),
            create_test_instrument("AAPL", AssetType::Stock),
        );
        let order = create_test_order("AAPL", Decimal::from(10), Some(Decimal::from(100)));
        let market_model = crate::market::SimpleMarket::from_config(
            crate::market::SimpleMarketConfig::default(),
        );

        let mut prices_start = HashMap::new();
        prices_start.insert("AAPL".to_string(), Decimal::from(100));
        let ctx_start = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &prices_start,
            market_model: &market_model,
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 1,
            current_time: 1_700_000_000_000_000_000,
            session: TradingSession::Continuous,
            active_orders: &[],
        };
        assert!(manager.check_internal(&order, &ctx_start).is_ok());

        let mut prices_drop = HashMap::new();
        prices_drop.insert("AAPL".to_string(), Decimal::from(89));
        let ctx_drop = crate::context::EngineContext {
            instruments: &instruments,
            portfolio: &portfolio,
            last_prices: &prices_drop,
            market_model: &market_model,
            execution_mode: ExecutionMode::NextOpen,
            bar_index: 2,
            current_time: 1_700_000_100_000_000_000,
            session: TradingSession::Continuous,
            active_orders: &[],
        };
        let err = manager.check_internal(&order, &ctx_drop).unwrap_err().to_string();
        assert!(err.contains("stop-loss threshold"));
    }
}
