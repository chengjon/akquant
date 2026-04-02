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
mod portfolio;
mod risk;
pub mod settlement;
pub mod statistics;

use analysis::{BacktestResult, ClosedTrade, LiquidationAudit, PerformanceMetrics, TradePnL};
use context::StrategyContext;
use data::{BarAggregator, DataFeed, from_arrays};
use engine::Engine;
use model::{
    AssetType, Bar, Instrument, OptionType, Order, OrderRole, OrderSide, OrderStatus, OrderType,
    SettlementType, Tick, TimeInForce, Trade, TradingSession,
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
    m.add_class::<TradingSession>()?;
    m.add_class::<Portfolio>()?;
    m.add_class::<PerformanceMetrics>()?;
    m.add_class::<BacktestResult>()?;
    m.add_class::<TradePnL>()?;
    m.add_class::<ClosedTrade>()?;
    m.add_class::<LiquidationAudit>()?;
    m.add_class::<RiskManager>()?;
    m.add_class::<RiskConfig>()?;
    indicators::register_py_classes(m)?;
    Ok(())
}

define_stub_info_gatherer!(stub_info);
