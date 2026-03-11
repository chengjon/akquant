use pyo3::prelude::*;
use pyo3_stub_gen::define_stub_info_gatherer;

mod analysis;
mod clock;
mod context;
mod data;
mod engine;
mod error;
mod event;
pub mod event_manager;
pub mod execution;
pub mod history;
pub mod indicators;
pub mod margin;
pub mod market;
pub mod model;
pub mod order_manager;
pub mod pipeline;
pub mod settlement;
pub mod statistics;
mod portfolio;
mod risk;

use analysis::{BacktestResult, ClosedTrade, PerformanceMetrics, TradePnL};
use context::StrategyContext;
use data::{BarAggregator, DataFeed, from_arrays};
use engine::Engine;
use indicators::{
    ADX, ATR, BollingerBands, CCI, DEMA, EMA, KAMA, MACD, MFI, MOM, NATR, OBV, ROC, RSI, SAR,
    SMA, STOCH, TEMA, TRIX, WILLR,
};
use model::{
    AssetType, Bar, ExecutionMode, Instrument, OptionType, Order, OrderRole, OrderSide,
    OrderStatus, OrderType, SettlementType, Tick, TimeInForce, Trade, TradingSession,
    corporate_action::{CorporateAction, CorporateActionType},
};
use portfolio::Portfolio;
use risk::{RiskConfig, RiskManager};

/// 使用 Rust 实现的 Python 模块
#[pymodule]
fn akquant(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Bar>()?;
    m.add_function(wrap_pyfunction!(from_arrays, m)?)?;
    m.add_class::<Tick>()?;
    m.add_class::<DataFeed>()?;
    m.add_class::<BarAggregator>()?;
    m.add_class::<Engine>()?;
    m.add_class::<StrategyContext>()?;
    m.add_class::<Order>()?;
    m.add_class::<Trade>()?;
    m.add_class::<OrderType>()?;
    m.add_class::<OrderRole>()?;
    m.add_class::<OrderSide>()?;
    m.add_class::<OrderStatus>()?;
    m.add_class::<TimeInForce>()?;
    m.add_class::<AssetType>()?;
    m.add_class::<OptionType>()?;
    m.add_class::<SettlementType>()?;
    m.add_class::<Instrument>()?;
    m.add_class::<CorporateAction>()?;
    m.add_class::<CorporateActionType>()?;
    m.add_class::<ExecutionMode>()?;
    m.add_class::<TradingSession>()?;
    m.add_class::<Portfolio>()?;
    m.add_class::<PerformanceMetrics>()?;
    m.add_class::<BacktestResult>()?;
    m.add_class::<TradePnL>()?;
    m.add_class::<ClosedTrade>()?;
    m.add_class::<RiskManager>()?;
    m.add_class::<RiskConfig>()?;
    m.add_class::<SMA>()?;
    m.add_class::<EMA>()?;
    m.add_class::<MACD>()?;
    m.add_class::<RSI>()?;
    m.add_class::<ROC>()?;
    m.add_class::<MOM>()?;
    m.add_class::<OBV>()?;
    m.add_class::<WILLR>()?;
    m.add_class::<TRIX>()?;
    m.add_class::<DEMA>()?;
    m.add_class::<TEMA>()?;
    m.add_class::<KAMA>()?;
    m.add_class::<NATR>()?;
    m.add_class::<SAR>()?;
    m.add_class::<MFI>()?;
    m.add_class::<CCI>()?;
    m.add_class::<ADX>()?;
    m.add_class::<STOCH>()?;
    m.add_class::<BollingerBands>()?;
    m.add_class::<ATR>()?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
