pub mod china;
pub mod core;
pub mod corporate_action;
pub mod fund;
pub mod futures;
pub mod manager;
pub mod option;
pub mod simple;
pub mod stock;

pub use china::{ChinaMarket, ChinaMarketConfig, SessionRange};
pub use core::{MarketConfig, MarketModel};
pub use simple::{SimpleMarket, SimpleMarketConfig};

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{AssetType, Instrument, OrderSide, TradingSession};
    use chrono::NaiveTime;
    use rust_decimal::prelude::*;
    use rust_decimal::Decimal;

    #[test]
    fn test_china_market_session() {
        let market = ChinaMarket::new();

        // 9:15 -> CallAuction
        assert_eq!(
            market.get_session_status(NaiveTime::from_hms_opt(9, 15, 0).unwrap()),
            TradingSession::CallAuction
        );
        // 9:30 -> Continuous
        assert_eq!(
            market.get_session_status(NaiveTime::from_hms_opt(9, 30, 0).unwrap()),
            TradingSession::Continuous
        );
        // 12:00 -> Break
        assert_eq!(
            market.get_session_status(NaiveTime::from_hms_opt(12, 0, 0).unwrap()),
            TradingSession::Break
        );
        // 18:00 -> Closed
        assert_eq!(
            market.get_session_status(NaiveTime::from_hms_opt(18, 0, 0).unwrap()),
            TradingSession::Closed
        );
    }

    #[test]
    #[should_panic(expected = "Futures market configuration not found")]
    fn test_china_market_missing_config_panic() {
        // Create config with only Stock enabled
        let mut config = ChinaMarketConfig::default();
        config.stock = Some(stock::StockConfig::default());
        // futures is None by default

        let market = ChinaMarket::from_config(config);

        // Create a Futures instrument
        use crate::model::instrument::{FuturesInstrument, InstrumentEnum};
        let instr = Instrument {
            asset_type: AssetType::Futures,
            inner: InstrumentEnum::Futures(FuturesInstrument {
                symbol: "IF2206".to_string(),
                multiplier: Decimal::from(300),
                tick_size: Decimal::from_str("0.2").unwrap(),
                margin_ratio: Decimal::from_str("0.1").unwrap(),
                expiry_date: None,
                settlement_type: None,
            }),
        };

        // This should panic because futures config is missing
        market.calculate_commission(
            &instr,
            OrderSide::Buy,
            Decimal::from(4000),
            Decimal::from(1),
        );
    }
}
