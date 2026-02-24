use serde::{Deserialize, Serialize};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize)]
/// 平仓交易记录.
///
/// :ivar symbol: 标的代码
/// :ivar entry_time: 开仓时间戳 (纳秒)
/// :ivar exit_time: 平仓时间戳 (纳秒)
/// :ivar entry_price: 开仓价格
/// :ivar exit_price: 平仓价格
/// :ivar quantity: 交易数量
/// :ivar side: 方向 ("long" 或 "short")
/// :ivar pnl: 毛利 (扣除佣金前)
/// :ivar net_pnl: 净利 (扣除佣金后)
/// :ivar return_pct: 收益率 (如 0.05 表示 5%)
/// :ivar commission: 佣金
/// :ivar duration_bars: 持仓 K 线数
/// :ivar duration: 持仓时长 (纳秒)
/// :ivar mae: 最大不利变动 (MAE)
/// :ivar mfe: 最大有利变动 (MFE)
/// :ivar entry_tag: 开仓订单标签
/// :ivar exit_tag: 平仓订单标签
/// :ivar entry_portfolio_value: 开仓时账户权益
/// :ivar max_drawdown_pct: 交易期间最大回撤 (%)
pub struct ClosedTrade {
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub entry_time: i64,
    #[pyo3(get)]
    pub exit_time: i64,
    #[pyo3(get)]
    pub entry_price: f64,
    #[pyo3(get)]
    pub exit_price: f64,
    #[pyo3(get)]
    pub quantity: f64,
    #[pyo3(get)]
    pub side: String, // "long" or "short"
    #[pyo3(get)]
    pub pnl: f64, // Gross PnL (aligned with Backtrader)
    #[pyo3(get)]
    pub net_pnl: f64, // Net PnL (pnl - commission)
    #[pyo3(get)]
    pub return_pct: f64,
    #[pyo3(get)]
    pub commission: f64,
    #[pyo3(get)]
    pub duration_bars: usize,
    #[pyo3(get)]
    pub duration: u64, // Duration in nanoseconds
    #[pyo3(get)]
    pub mae: f64, // Maximum Adverse Excursion
    #[pyo3(get)]
    pub mfe: f64, // Maximum Favorable Excursion
    #[pyo3(get)]
    pub entry_tag: String, // Entry order tag
    #[pyo3(get)]
    pub exit_tag: String, // Exit order tag
    #[pyo3(get)]
    pub entry_portfolio_value: f64, // Portfolio value at entry
    #[pyo3(get)]
    pub max_drawdown_pct: f64, // Max drawdown percentage during trade
}

#[gen_stub_pymethods]
#[pymethods]
impl ClosedTrade {
    pub fn __repr__(&self) -> String {
        format!("{:?}", self)
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
/// 绩效指标.
///
/// :ivar total_return: 总收益 (数值)
/// :ivar annualized_return: 年化收益率
/// :ivar max_drawdown: 最大回撤 (百分比, 如 0.15 表示 15%)
/// :ivar max_drawdown_value: 最大回撤金额
/// :ivar max_drawdown_pct: 最大回撤百分比 (如 15.0 表示 15%)
/// :ivar sharpe_ratio: 夏普比率
/// :ivar sortino_ratio: 索提诺比率
/// :ivar calmar_ratio: 卡玛比率
/// :ivar volatility: 年化波动率
/// :ivar ulcer_index: 溃疡指数
/// :ivar upi: 溃疡绩效指数 (UPI)
/// :ivar equity_r2: 权益曲线 R^2 (拟合度)
/// :ivar std_error: 标准误差
/// :ivar win_rate: 胜率 (0.0-1.0)
/// :ivar initial_market_value: 初始市值
/// :ivar end_market_value: 结束市值
/// :ivar total_return_pct: 总收益率 (%)
/// :ivar start_time: 开始时间戳 (纳秒)
/// :ivar end_time: 结束时间戳 (纳秒)
/// :ivar duration: 持续时间 (纳秒)
/// :ivar total_bars: 总 K 线数
/// :ivar exposure_time_pct: 市场暴露时间百分比
/// :ivar var_95: 95% VaR (在风险价值)
/// :ivar var_99: 99% VaR
/// :ivar cvar_95: 95% CVaR (条件在风险价值)
/// :ivar cvar_99: 99% CVaR
pub struct PerformanceMetrics {
    #[pyo3(get)]
    pub total_return: f64,
    #[pyo3(get)]
    pub annualized_return: f64,
    #[pyo3(get)]
    pub max_drawdown: f64,
    #[pyo3(get)]
    pub max_drawdown_value: f64,
    #[pyo3(get)]
    pub max_drawdown_pct: f64, // Same as max_drawdown but explicit
    #[pyo3(get)]
    pub sharpe_ratio: f64,
    #[pyo3(get)]
    pub sortino_ratio: f64,
    #[pyo3(get)]
    pub calmar_ratio: f64,
    #[pyo3(get)]
    pub volatility: f64,
    #[pyo3(get)]
    pub ulcer_index: f64,
    #[pyo3(get)]
    pub upi: f64,
    #[pyo3(get)]
    pub equity_r2: f64,
    #[pyo3(get)]
    pub std_error: f64,
    #[pyo3(get)]
    pub win_rate: f64,
    #[pyo3(get)]
    pub initial_market_value: f64,
    #[pyo3(get)]
    pub end_market_value: f64,
    #[pyo3(get)]
    pub total_return_pct: f64,
    #[pyo3(get)]
    pub start_time: i64,
    #[pyo3(get)]
    pub end_time: i64,
    #[pyo3(get)]
    pub duration: u64,
    #[pyo3(get)]
    pub total_bars: usize,

    // New risk metrics
    #[pyo3(get)]
    pub exposure_time_pct: f64,
    #[pyo3(get)]
    pub var_95: f64,
    #[pyo3(get)]
    pub var_99: f64,
    #[pyo3(get)]
    pub cvar_95: f64,
    #[pyo3(get)]
    pub cvar_99: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl PerformanceMetrics {
    pub fn __repr__(&self) -> String {
        format!("{:?}", self)
    }

    pub fn __getitem__(&self, py: Python, key: &str) -> PyResult<Py<PyAny>> {
        let v = match key {
            "total_return" => self.total_return.into_pyobject(py).unwrap().into_any().unbind(),
            "annualized_return" => self.annualized_return.into_pyobject(py).unwrap().into_any().unbind(),
            "max_drawdown" => self.max_drawdown.into_pyobject(py).unwrap().into_any().unbind(),
            "max_drawdown_value" => self.max_drawdown_value.into_pyobject(py).unwrap().into_any().unbind(),
            "max_drawdown_pct" => self.max_drawdown_pct.into_pyobject(py).unwrap().into_any().unbind(),
            "sharpe_ratio" => self.sharpe_ratio.into_pyobject(py).unwrap().into_any().unbind(),
            "sortino_ratio" => self.sortino_ratio.into_pyobject(py).unwrap().into_any().unbind(),
            "calmar_ratio" => self.calmar_ratio.into_pyobject(py).unwrap().into_any().unbind(),
            "volatility" => self.volatility.into_pyobject(py).unwrap().into_any().unbind(),
            "ulcer_index" => self.ulcer_index.into_pyobject(py).unwrap().into_any().unbind(),
            "upi" => self.upi.into_pyobject(py).unwrap().into_any().unbind(),
            "equity_r2" => self.equity_r2.into_pyobject(py).unwrap().into_any().unbind(),
            "std_error" => self.std_error.into_pyobject(py).unwrap().into_any().unbind(),
            "win_rate" => self.win_rate.into_pyobject(py).unwrap().into_any().unbind(),
            "initial_market_value" => self.initial_market_value.into_pyobject(py).unwrap().into_any().unbind(),
            "end_market_value" => self.end_market_value.into_pyobject(py).unwrap().into_any().unbind(),
            "total_return_pct" => self.total_return_pct.into_pyobject(py).unwrap().into_any().unbind(),
            "start_time" => self.start_time.into_pyobject(py).unwrap().into_any().unbind(),
            "end_time" => self.end_time.into_pyobject(py).unwrap().into_any().unbind(),
            "duration" => self.duration.into_pyobject(py).unwrap().into_any().unbind(),
            "total_bars" => self.total_bars.into_pyobject(py).unwrap().into_any().unbind(),
            "exposure_time_pct" => self.exposure_time_pct.into_pyobject(py).unwrap().into_any().unbind(),
            "var_95" => self.var_95.into_pyobject(py).unwrap().into_any().unbind(),
            "var_99" => self.var_99.into_pyobject(py).unwrap().into_any().unbind(),
            "cvar_95" => self.cvar_95.into_pyobject(py).unwrap().into_any().unbind(),
            "cvar_99" => self.cvar_99.into_pyobject(py).unwrap().into_any().unbind(),
            _ => return Err(pyo3::exceptions::PyKeyError::new_err(format!("Key '{}' not found", key))),
        };
        Ok(v)
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize)]
/// 交易盈亏统计 (FIFO).
///
/// :ivar gross_pnl: 总毛利 (扣除佣金前)
/// :ivar net_pnl: 总净利 (扣除佣金后)
/// :ivar total_commission: 总佣金
/// :ivar total_closed_trades: 总平仓交易次数
/// :ivar won_count: 盈利次数
/// :ivar lost_count: 亏损次数
/// :ivar won_pnl: 盈利总额
/// :ivar lost_pnl: 亏损总额
/// :ivar win_rate: 胜率 (0.0-1.0)
/// :ivar loss_rate: 亏损率 (0.0-1.0)
/// :ivar unrealized_pnl: 未实现盈亏
/// :ivar avg_pnl: 平均单笔盈亏
/// :ivar avg_return_pct: 平均单笔收益率 (%)
/// :ivar avg_trade_bars: 平均持仓 K 线数
/// :ivar avg_profit: 平均单笔盈利
/// :ivar avg_profit_pct: 平均单笔盈利百分比
/// :ivar avg_winning_trade_bars: 平均盈利交易持仓 K 线数
/// :ivar avg_loss: 平均单笔亏损
/// :ivar avg_loss_pct: 平均单笔亏损百分比
/// :ivar avg_losing_trade_bars: 平均亏损交易持仓 K 线数
/// :ivar largest_win: 最大单笔盈利
/// :ivar largest_win_pct: 最大单笔盈利百分比
/// :ivar largest_win_bars: 最大单笔盈利持仓 K 线数
/// :ivar largest_loss: 最大单笔亏损
/// :ivar largest_loss_pct: 最大单笔亏损百分比
/// :ivar largest_loss_bars: 最大单笔亏损持仓 K 线数
/// :ivar max_wins: 最大连胜次数
/// :ivar max_losses: 最大连败次数
/// :ivar profit_factor: 盈亏比
/// :ivar total_profit: 总盈利 (同 won_pnl)
/// :ivar total_loss: 总亏损 (同 lost_pnl)
/// :ivar sqn: 系统质量数 (System Quality Number)
/// :ivar kelly_criterion: 凯利公式比例
pub struct TradePnL {
    #[pyo3(get)]
    pub gross_pnl: f64,
    #[pyo3(get)]
    pub net_pnl: f64,
    #[pyo3(get)]
    pub total_commission: f64,
    #[pyo3(get)]
    pub total_closed_trades: usize,
    #[pyo3(get)]
    pub won_count: usize,
    #[pyo3(get)]
    pub lost_count: usize,
    #[pyo3(get)]
    pub won_pnl: f64,
    #[pyo3(get)]
    pub lost_pnl: f64,
    #[pyo3(get)]
    pub win_rate: f64,
    #[pyo3(get)]
    pub loss_rate: f64,
    #[pyo3(get)]
    pub unrealized_pnl: f64,

    // New fields
    #[pyo3(get)]
    pub avg_pnl: f64,
    #[pyo3(get)]
    pub avg_return_pct: f64,
    #[pyo3(get)]
    pub avg_trade_bars: f64,
    #[pyo3(get)]
    pub avg_profit: f64,
    #[pyo3(get)]
    pub avg_profit_pct: f64,
    #[pyo3(get)]
    pub avg_winning_trade_bars: f64,
    #[pyo3(get)]
    pub avg_loss: f64,
    #[pyo3(get)]
    pub avg_loss_pct: f64,
    #[pyo3(get)]
    pub avg_losing_trade_bars: f64,
    #[pyo3(get)]
    pub largest_win: f64,
    #[pyo3(get)]
    pub largest_win_pct: f64,
    #[pyo3(get)]
    pub largest_win_bars: f64,
    #[pyo3(get)]
    pub largest_loss: f64,
    #[pyo3(get)]
    pub largest_loss_pct: f64,
    #[pyo3(get)]
    pub largest_loss_bars: f64,
    #[pyo3(get)]
    pub max_wins: usize,
    #[pyo3(get)]
    pub max_losses: usize,
    #[pyo3(get)]
    pub profit_factor: f64,
    #[pyo3(get)]
    pub total_profit: f64, // Same as won_pnl
    #[pyo3(get)]
    pub total_loss: f64, // Same as lost_pnl
    #[pyo3(get)]
    pub sqn: f64,
    #[pyo3(get)]
    pub kelly_criterion: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl TradePnL {
    pub fn __repr__(&self) -> String {
        format!("{:?}", self)
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize)]
/// 每日持仓快照.
///
/// :ivar symbol: 标的代码
/// :ivar quantity: 持仓数量
/// :ivar entry_price: 开仓均价
/// :ivar long_shares: 多头持仓数量
/// :ivar short_shares: 空头持仓数量
/// :ivar close: 收盘价
/// :ivar equity: 账户权益
/// :ivar market_value: 市值
/// :ivar margin: 保证金
/// :ivar unrealized_pnl: 未实现盈亏
pub struct PositionSnapshot {
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub quantity: f64,
    #[pyo3(get)]
    pub entry_price: f64,
    #[pyo3(get)]
    pub long_shares: f64,
    #[pyo3(get)]
    pub short_shares: f64,
    #[pyo3(get)]
    pub close: f64,
    #[pyo3(get)]
    pub equity: f64,
    #[pyo3(get)]
    pub market_value: f64,
    #[pyo3(get)]
    pub margin: f64,
    #[pyo3(get)]
    pub unrealized_pnl: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl PositionSnapshot {
    pub fn __repr__(&self) -> String {
        format!("{:?}", self)
    }
}
