use chrono::NaiveDate;
use indicatif::{ProgressBar, ProgressStyle};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rust_decimal::prelude::*;
use std::collections::{BinaryHeap, HashMap};
use std::sync::{Arc, RwLock};

use crate::analysis::{BacktestResult, PositionSnapshot};
use crate::clock::Clock;
use crate::data::DataFeed;
use crate::event_manager::EventManager;
use crate::execution::{RealtimeExecutionClient, SimulatedExecutionClient};
use crate::history::HistoryBuffer;
use crate::market::corporate_action::CorporateActionManager;
use crate::market::manager::MarketManager;
use crate::model::{
    Bar, ExecutionMode, Instrument, Order, Trade, TradingSession,
    corporate_action::CorporateAction,
};
use crate::portfolio::Portfolio;
use crate::risk::{RiskConfig, RiskManager};
use crate::settlement::SettlementManager;
use crate::statistics::StatisticsManager;

use super::core::Engine;
use super::state::SharedState;

#[gen_stub_pymethods]
#[pymethods]
impl Engine {
    /// 获取订单列表
    #[getter]
    fn get_orders(&self) -> Vec<Order> {
        self.state.order_manager.get_all_orders()
    }

    /// 获取成交列表
    #[getter]
    fn get_trades(&self) -> Vec<Trade> {
        self.state.order_manager.trades.clone()
    }

    /// 获取投资组合
    #[getter]
    fn get_portfolio(&self) -> Portfolio {
        self.state.portfolio.clone()
    }

    /// 获取数据源
    #[getter]
    fn get_feed(&self) -> DataFeed {
        self.state.feed.clone()
    }

    /// 获取持仓快照历史
    #[getter]
    fn get_snapshots(&self) -> Vec<(i64, Vec<PositionSnapshot>)> {
        self.statistics_manager.snapshots.clone()
    }

    /// 设置风控配置
    ///
    /// 由于 PyO3 对嵌套结构体的属性访问可能返回副本，
    /// 提供此方法以显式更新风控配置。
    ///
    /// :param config: 新的风控配置
    fn set_risk_config(&mut self, config: RiskConfig) {
        self.risk_manager.config = config;
    }

    /// 初始化回测引擎.
    ///
    /// :return: Engine 实例
    #[new]
    pub fn new() -> Self {
        let initial_cash = Decimal::from(100_000);
        Engine {
            state: SharedState::new(initial_cash),
            last_prices: HashMap::new(),
            instruments: HashMap::new(),
            current_date: None,
            market_manager: MarketManager::new(),
            corporate_action_manager: CorporateActionManager::new(),
            execution_model: Box::new(SimulatedExecutionClient::new()),
            execution_mode: ExecutionMode::NextOpen,
            clock: Clock::new(),
            timers: BinaryHeap::new(),
            force_session_continuous: false,
            risk_manager: RiskManager::new(),
            timezone_offset: 28800, // Default UTC+8
            history_buffer: Arc::new(RwLock::new(HistoryBuffer::new(10000))), // Default large capacity for MAE/MFE
            initial_cash,
            event_manager: EventManager::new(),
            statistics_manager: StatisticsManager::new(),
            settlement_manager: SettlementManager::new(),
            current_event: None,
            bar_count: 0,
            progress_bar: None,
            strategy_context: None,
        }
    }

    /// 设置历史数据长度
    ///
    /// :param depth: 历史数据长度
    fn set_history_depth(&mut self, depth: usize) {
        self.history_buffer.write().unwrap().set_capacity(depth);
    }

    /// 设置时区偏移 (秒)
    ///
    /// :param offset: 偏移秒数 (例如 UTC+8 为 28800)
    pub fn set_timezone(&mut self, offset: i32) {
        self.timezone_offset = offset;
    }

    /// 启用模拟执行 (回测模式)
    ///
    /// 默认模式。在内存中撮合订单。
    fn use_simulated_execution(&mut self) {
        self.execution_model = Box::new(SimulatedExecutionClient::new());
    }

    /// 启用实盘执行 (CTP/Broker 模式)
    ///
    /// 模拟对接 CTP 或其他 Broker API。
    /// 在此模式下，订单会被标记为 Submitted 并等待回调 (目前仅模拟发送)。
    fn use_realtime_execution(&mut self) {
        self.execution_model = Box::new(RealtimeExecutionClient::new());
    }

    /// 注册自定义撮合器 (Python)
    ///
    /// :param asset_type: 资产类型
    /// :param matcher: Python 撮合器对象 (需实现 match 方法)
    fn register_custom_matcher(&mut self, asset_type: crate::model::AssetType, matcher: Py<PyAny>) {
        use crate::execution::PyExecutionMatcher;
        let py_matcher = Box::new(PyExecutionMatcher::new(matcher));
        self.execution_model.register_matcher(asset_type, py_matcher);
    }

    /// 设置撮合模式
    ///
    /// :param mode: 撮合模式 (ExecutionMode.CurrentClose 或 ExecutionMode.NextOpen)
    /// :type mode: ExecutionMode
    fn set_execution_mode(&mut self, mode: ExecutionMode) {
        self.execution_mode = mode;
    }

    /// 启用 SimpleMarket (7x24小时, T+0, 无税, 简单佣金)
    ///
    /// :param commission_rate: 佣金率
    fn use_simple_market(&mut self, commission_rate: f64) {
        self.market_manager.use_simple_market(commission_rate);
    }

    /// 启用 ChinaMarket (支持 T+1/T+0, 印花税, 过户费, 交易时段等)
    fn use_china_market(&mut self) {
        self.market_manager.use_china_market();
    }

    /// 启用/禁用 T+1 交易规则 (仅针对 ChinaMarket)
    ///
    /// :param enabled: 是否启用 T+1
    /// :type enabled: bool
    fn set_t_plus_one(&mut self, enabled: bool) {
        self.market_manager.set_t_plus_one(enabled);
    }

    /// 强制连续交易时段
    ///
    /// :param enabled: 是否强制连续交易 (忽略午休等)
    fn set_force_session_continuous(&mut self, enabled: bool) {
        self.force_session_continuous = enabled;
    }

    /// 添加公司行为 (除权除息)
    ///
    /// :param action: 公司行为对象
    fn add_corporate_action(&mut self, action: CorporateAction) {
        self.corporate_action_manager.add(action);
    }

    /// 启用中国期货市场默认配置
    /// - 切换到 ChinaMarket
    /// - 设置 T+0
    /// - 保持当前交易时段配置 (需手动设置 set_market_sessions 以匹配特定品种)
    fn use_china_futures_market(&mut self) {
        self.market_manager.use_china_futures_market();
    }

    fn process_option_expiry(&mut self, _local_date: NaiveDate) {
        // Deprecated: logic moved to SettlementManager
    }

    /// 设置股票费率规则 (按交易金额比例)
    ///
    /// :param commission_rate: 佣金率 (如 0.0003)
    /// :param stamp_tax: 印花税率 (如 0.001)
    /// :param transfer_fee: 过户费率 (如 0.00002)
    /// :param min_commission: 最低佣金 (如 5.0)
    pub fn set_stock_fee_rules(
        &mut self,
        commission_rate: f64,
        stamp_tax: f64,
        transfer_fee: f64,
        min_commission: f64,
    ) {
        self.market_manager.set_stock_fee_rules(
            commission_rate,
            stamp_tax,
            transfer_fee,
            min_commission,
        );
    }

    /// 设置期货费率规则
    ///
    /// :param commission_rate: 佣金率 (如 0.0001)
    pub fn set_future_fee_rules(&mut self, commission_rate: f64) {
        self.market_manager.set_future_fee_rules(commission_rate);
    }

    /// 设置基金费率规则
    ///
    /// :param commission_rate: 佣金率
    /// :param transfer_fee: 过户费率
    /// :param min_commission: 最低佣金
    fn set_fund_fee_rules(&mut self, commission_rate: f64, transfer_fee: f64, min_commission: f64) {
        self.market_manager.set_fund_fee_rules(commission_rate, transfer_fee, min_commission);
    }

    /// 设置期权费率规则
    ///
    /// :param commission_per_contract: 每张合约佣金 (如 5.0)
    fn set_option_fee_rules(&mut self, commission_per_contract: f64) {
        self.market_manager.set_option_fee_rules(commission_per_contract);
    }

    /// 设置加密货币费率规则 (按金额比例)
    ///
    /// :param commission_rate: 佣金率 (如 0.001)
    fn set_crypto_fee_rules(&mut self, commission_rate: f64) {
        // Crypto fees are usually percentage based, similar to Stock/Future
        // For now, reuse stock fee rules logic or future logic?
        // Let's assume simple percentage fee for now.
        // Actually, we should probably add specific methods in MarketManager.
        // For now, let's map it to stock rules but with zero tax/transfer fee.
        self.market_manager.set_stock_fee_rules(commission_rate, 0.0, 0.0, 0.0);
    }

    /// 设置外汇费率规则 (按金额比例)
    ///
    /// :param commission_rate: 佣金率 (如 0.00005)
    fn set_forex_fee_rules(&mut self, commission_rate: f64) {
        self.market_manager.set_stock_fee_rules(commission_rate, 0.0, 0.0, 0.0);
    }

    /// 设置滑点模型
    ///
    /// :param type: 滑点类型 ("fixed" 或 "percent")
    /// :param value: 滑点值 (固定金额 或 百分比如 0.001)
    fn set_slippage(&mut self, type_: String, value: f64) -> PyResult<()> {
        let val = Decimal::from_f64(value).unwrap_or(Decimal::ZERO);
        match type_.as_str() {
            "fixed" => {
                self.execution_model
                    .set_slippage_model(Box::new(crate::execution::FixedSlippage { delta: val }));
            }
            "percent" => {
                self.execution_model
                    .set_slippage_model(Box::new(crate::execution::PercentSlippage { rate: val }));
            }
            "zero" | "none" => {
                self.execution_model
                    .set_slippage_model(Box::new(crate::execution::ZeroSlippage));
            }
            _ => {
                return Err(PyValueError::new_err(
                    "Invalid slippage type. Use 'fixed', 'percent', or 'zero'",
                ));
            }
        }
        Ok(())
    }

    /// 设置成交量限制
    ///
    /// :param limit: 限制比例 (0.0-1.0), 0.0 为不限制
    fn set_volume_limit(&mut self, limit: f64) {
        self.execution_model.set_volume_limit(limit);
    }

    /// 设置市场交易时段
    ///
    /// :param sessions: 交易时段列表，每个元素为 (开始时间, 结束时间, 时段类型)
    /// :type sessions: List[Tuple[str, str, TradingSession]]
    ///
    /// 示例::
    ///
    /// ```python
    /// engine.set_market_sessions([
    ///     ("09:30:00", "11:30:00", TradingSession.Normal),
    ///     ("13:00:00", "15:00:00", TradingSession.Normal)
    /// ])
    /// ```
    fn set_market_sessions(
        &mut self,
        sessions: Vec<(String, String, TradingSession)>,
    ) -> PyResult<()> {
        let mut ranges = Vec::with_capacity(sessions.len());
        for (start, end, session) in sessions {
            let start_time = Self::parse_time_string(&start)?;
            let end_time = Self::parse_time_string(&end)?;
            ranges.push((start_time, end_time, session));
        }
        self.market_manager.set_market_sessions(ranges);
        Ok(())
    }

    /// 添加交易标的
    ///
    /// :param instrument: 交易标的对象
    /// :type instrument: Instrument
    pub fn add_instrument(&mut self, instrument: Instrument) {
        self.instruments
            .insert(instrument.symbol().to_string(), instrument);
    }

    /// 设置初始资金
    ///
    /// :param cash: 初始资金数额
    /// :type cash: float
    pub fn set_cash(&mut self, cash: f64) {
        let val = Decimal::from_f64(cash).unwrap_or(Decimal::ZERO);
        self.state.portfolio.cash = val;
        self.initial_cash = val;
    }

    /// 添加数据源
    ///
    /// :param feed: 数据源对象
    /// :type feed: DataFeed
    fn add_data(&mut self, feed: DataFeed) {
        self.state.feed = feed;
    }

    /// 批量添加 K 线数据
    ///
    /// :param bars: K 线列表
    fn add_bars(&mut self, bars: Vec<Bar>) -> PyResult<()> {
        self.state.feed.add_bars(bars)
    }

    /// 运行回测
    ///
    /// :param strategy: 策略对象
    /// :param show_progress: 是否显示进度条
    /// :type strategy: object
    /// :type show_progress: bool
    /// :return: 回测结果摘要
    /// :rtype: str
    fn run(
        &mut self,
        py: Python<'_>,
        strategy: &Bound<'_, PyAny>,
        show_progress: bool,
    ) -> PyResult<String> {
        // Configure history buffer if strategy has _history_depth set
        if let Ok(depth_attr) = strategy.getattr("_history_depth") {
            if let Ok(depth) = depth_attr.extract::<usize>() {
                if depth > 0 {
                    self.set_history_depth(depth);
                }
            }
        }

        // Trigger Strategy on_start
        if let Err(e) = strategy.call_method0("on_start") {
            return Err(e);
        }

        // Progress Bar Initialization
        let total_events = self.state.feed.len_hint().unwrap_or(0);
        let pb = if show_progress {
            let pb = if total_events > 0 {
                let pb = ProgressBar::new(total_events as u64);
                pb.set_style(
                    ProgressStyle::default_bar()
                        .template(
                            "{spinner:.green} [{elapsed_precise}] [{bar:40.cyan/blue}] {pos}/{len} ({eta})",
                        )
                        .unwrap()
                        .progress_chars("#>-"),
                );
                pb
            } else {
                let pb = ProgressBar::new_spinner();
                pb.set_style(
                    ProgressStyle::default_spinner()
                        .template("{spinner:.green} [{elapsed_precise}] {pos} events processed")
                        .unwrap(),
                );
                pb
            };
            Some(pb)
        } else {
            None
        };
        self.progress_bar = pb;

        // Record initial equity
        if let Some(_) = self.state.feed.peek_timestamp() {
            let _equity = self
                .state
                .portfolio
                .calculate_equity(&self.last_prices, &self.instruments);
        }

        // Initialize Pipeline
        let mut pipeline = self.build_pipeline();

        // Run Pipeline
        if let Err(e) = pipeline.run(self, py, strategy) {
            // Clean up pb if error
            self.progress_bar = None;
            return Err(e);
        }

        // Final cleanup
        self.state.order_manager.cleanup_finished_orders();

        // Record final snapshot if we have data
        if self.current_date.is_some() {
            if let Some(timestamp) = self.clock.timestamp() {
                self.statistics_manager.record_snapshot(
                    timestamp,
                    &self.state.portfolio,
                    &self.instruments,
                    &self.last_prices,
                    &self.state.order_manager.trade_tracker,
                );
            }
        }

        if let Some(pb) = &self.progress_bar {
            pb.finish_with_message("Backtest completed");
        }

        let count = self.bar_count;
        self.progress_bar = None;

        Ok(format!(
            "Backtest finished. Processed {} events. Total Trades: {}",
            count,
            self.state.order_manager.trades.len()
        ))
    }

    /// 获取回测结果
    ///
    /// :return: BacktestResult
    fn get_results(&self) -> BacktestResult {
        self.statistics_manager.generate_backtest_result(
            &self.state.portfolio,
            &self.instruments,
            &self.last_prices,
            &self.state.order_manager,
            self.initial_cash,
            self.clock.timestamp(),
        )
    }
}
