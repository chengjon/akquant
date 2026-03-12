use chrono::NaiveTime;
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use std::collections::HashMap;

use crate::market::{
    ChinaMarketConfig, MarketConfig, MarketModel, SessionRange, SimpleMarketConfig, fund, futures,
    option, stock,
};
use crate::model::{Instrument, TradingSession};

/// 市场管理器
/// 负责管理市场配置、市场模型以及相关的费率和交易时段设置
pub struct MarketManager {
    pub config: MarketConfig,
    pub model: Box<dyn MarketModel>,
}

impl MarketManager {
    /// 创建新的市场管理器
    pub fn new() -> Self {
        // 默认初始化所有市场配置，保持向后兼容
        let config = ChinaMarketConfig {
            stock: Some(stock::StockConfig::default()),
            futures: Some(futures::FuturesConfig::default()),
            fund: Some(fund::FundConfig::default()),
            option: Some(option::OptionConfig::default()),
            ..Default::default()
        };

        let config = MarketConfig::China(config);
        Self {
            config: config.clone(),
            model: config.create_model(),
        }
    }

    /// 启用 SimpleMarket (7x24小时, T+0, 无税, 简单佣金)
    ///
    /// :param commission_rate: 佣金率
    pub fn use_simple_market(&mut self, commission_rate: f64) {
        let config = SimpleMarketConfig {
            commission_rate: Decimal::from_f64(commission_rate).unwrap_or(Decimal::ZERO),
            ..Default::default()
        };
        self.config = MarketConfig::Simple(config);
        self.model = self.config.create_model();
    }

    /// 启用 ChinaMarket (支持 T+1/T+0, 印花税, 过户费, 交易时段等)
    pub fn use_china_market(&mut self) {
        let config = ChinaMarketConfig {
            stock: Some(stock::StockConfig::default()),
            futures: Some(futures::FuturesConfig::default()),
            fund: Some(fund::FundConfig::default()),
            option: Some(option::OptionConfig::default()),
            ..Default::default()
        };
        self.config = MarketConfig::China(config);
        self.model = self.config.create_model();
    }

    /// 启用/禁用 T+1 交易规则 (仅针对 ChinaMarket)
    ///
    /// :param enabled: 是否启用 T+1
    pub fn set_t_plus_one(&mut self, enabled: bool) {
        if let MarketConfig::China(ref mut c) = self.config {
            c.stock
                .get_or_insert_with(stock::StockConfig::default)
                .t_plus_one = enabled;
            c.fund
                .get_or_insert_with(fund::FundConfig::default)
                .t_plus_one = enabled;
            self.model = self.config.create_model();
        }
    }

    /// 启用中国期货市场默认配置
    /// - 切换到 ChinaMarket
    /// - 仅启用期货配置
    /// - 保持当前交易时段配置 (需手动设置 set_market_sessions 以匹配特定品种)
    pub fn use_china_futures_market(&mut self) {
        let config = ChinaMarketConfig {
            futures: Some(futures::FuturesConfig::default()),
            ..Default::default()
        };
        self.config = MarketConfig::China(config);
        self.model = self.config.create_model();
    }

    /// 设置股票费率规则
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
        match &mut self.config {
            MarketConfig::China(c) => {
                let stock = c.stock.get_or_insert_with(stock::StockConfig::default);
                stock.commission_rate = Decimal::from_f64(commission_rate).unwrap_or(Decimal::ZERO);
                stock.stamp_tax = Decimal::from_f64(stamp_tax).unwrap_or(Decimal::ZERO);
                stock.transfer_fee = Decimal::from_f64(transfer_fee).unwrap_or(Decimal::ZERO);
                stock.min_commission = Decimal::from_f64(min_commission).unwrap_or(Decimal::ZERO);
            }
            MarketConfig::Simple(c) => {
                c.commission_rate = Decimal::from_f64(commission_rate).unwrap_or(Decimal::ZERO);
                c.stamp_tax = Decimal::from_f64(stamp_tax).unwrap_or(Decimal::ZERO);
                c.transfer_fee = Decimal::from_f64(transfer_fee).unwrap_or(Decimal::ZERO);
                c.min_commission = Decimal::from_f64(min_commission).unwrap_or(Decimal::ZERO);
            }
        }
        self.model = self.config.create_model();
    }

    /// 设置期货费率规则
    ///
    /// :param commission_rate: 佣金率 (如 0.0001)
    pub fn set_future_fee_rules(&mut self, commission_rate: f64) {
        if let MarketConfig::China(ref mut c) = self.config {
            let futures = c
                .futures
                .get_or_insert_with(futures::FuturesConfig::default);
            futures.commission_rate = Decimal::from_f64(commission_rate).unwrap_or(Decimal::ZERO);
            self.model = self.config.create_model();
        }
    }

    /// 设置基金费率规则
    ///
    /// :param commission_rate: 佣金率
    /// :param transfer_fee: 过户费率
    /// :param min_commission: 最低佣金
    pub fn set_fund_fee_rules(
        &mut self,
        commission_rate: f64,
        transfer_fee: f64,
        min_commission: f64,
    ) {
        if let MarketConfig::China(ref mut c) = self.config {
            let fund = c.fund.get_or_insert_with(fund::FundConfig::default);
            fund.commission_rate = Decimal::from_f64(commission_rate).unwrap_or(Decimal::ZERO);
            fund.transfer_fee = Decimal::from_f64(transfer_fee).unwrap_or(Decimal::ZERO);
            fund.min_commission = Decimal::from_f64(min_commission).unwrap_or(Decimal::ZERO);
            self.model = self.config.create_model();
        }
    }

    /// 设置期权费率规则
    ///
    /// :param commission_per_contract: 每张合约佣金 (如 5.0)
    pub fn set_option_fee_rules(&mut self, commission_per_contract: f64) {
        if let MarketConfig::China(ref mut c) = self.config {
            let option = c.option.get_or_insert_with(option::OptionConfig::default);
            option.commission_per_contract =
                Decimal::from_f64(commission_per_contract).unwrap_or(Decimal::ZERO);
            self.model = self.config.create_model();
        }
    }

    /// 设置市场交易时段
    ///
    /// :param sessions: 交易时段列表，每个元素为 (开始时间, 结束时间, 时段类型)
    pub fn set_market_sessions(&mut self, sessions: Vec<(NaiveTime, NaiveTime, TradingSession)>) {
        let mut ranges = Vec::with_capacity(sessions.len());
        for (start, end, session) in sessions {
            ranges.push(SessionRange {
                start,
                end,
                session,
            });
        }
        if let MarketConfig::China(ref mut c) = self.config {
            c.sessions = ranges;
            self.model = self.config.create_model();
        }
    }

    /// 获取当前交易时段状态
    pub fn get_session_status(&self, time: NaiveTime) -> TradingSession {
        self.model.get_session_status(time)
    }

    /// 处理日终逻辑 (T+1 等)
    pub fn on_day_close(
        &self,
        positions: &HashMap<String, Decimal>,
        available_positions: &mut HashMap<String, Decimal>,
        instruments: &HashMap<String, Instrument>,
    ) {
        self.model
            .on_day_close(positions, available_positions, instruments);
    }
}

impl Default for MarketManager {
    fn default() -> Self {
        Self::new()
    }
}
