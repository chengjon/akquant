use crate::error::AkQuantError;
use crate::model::{AssetType, Instrument, Order};
use crate::portfolio::Portfolio;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rust_decimal::prelude::*;
use rust_decimal::Decimal;
use std::collections::HashMap;

use super::common::{
    CashMarginRule, MaxOrderSizeRule, MaxOrderValueRule, MaxPositionSizeRule, RestrictedListRule,
};
use super::config::RiskConfig;
use super::futures::FuturesMarginRule;
use super::option::OptionGreekRiskRule;
use super::portfolio::{MaxLeverageRule, MaxPositionPercentRule, SectorConcentrationRule};
use super::rule::RiskRule;
use super::stock::StockAvailablePositionRule;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct RiskManager {
    #[pyo3(get, set)]
    pub config: RiskConfig,

    // Internal fields, not exposed to Python directly (unless we add getters)
    // No #[pyo3(skip)] needed as fields are private by default in #[pyclass]
    common_rules: Vec<Box<dyn RiskRule>>,
    asset_rules: HashMap<AssetType, Vec<Box<dyn RiskRule>>>,
    dynamic_rules: Vec<Box<dyn RiskRule>>,
}

impl Default for RiskManager {
    fn default() -> Self {
        let mut manager = Self {
            config: RiskConfig::new(),
            common_rules: Vec::new(),
            asset_rules: HashMap::new(),
            dynamic_rules: Vec::new(),
        };
        manager.init_rules();
        manager
    }
}

#[pymethods]
impl RiskManager {
    #[new]
    pub fn new() -> Self {
        Self::default()
    }

    pub fn check(
        &self,
        order: &Order,
        portfolio: &Portfolio,
        instruments: HashMap<String, Instrument>,
        active_orders: Vec<Order>,
        current_prices: Option<HashMap<String, f64>>,
    ) -> Option<String> {
        let prices_dec: HashMap<String, Decimal> = if let Some(cp) = current_prices {
            cp.into_iter()
                .map(|(k, v)| (k, Decimal::from_f64(v).unwrap_or(Decimal::ZERO)))
                .collect()
        } else {
            HashMap::new()
        };

        // Create a dummy market model for context
        use crate::market::{SimpleMarket, SimpleMarketConfig};
        let market_model = SimpleMarket::from_config(SimpleMarketConfig::default());

        let ctx = crate::context::EngineContext {
            instruments: &instruments,
            portfolio,
            last_prices: &prices_dec,
            market_model: &market_model,
            execution_mode: crate::model::ExecutionMode::NextOpen,
            bar_index: 0,
            session: crate::model::TradingSession::Continuous,
            active_orders: &active_orders,
        };

        match self.check_internal(order, &ctx) {
            Ok(_) => None,
            Err(e) => Some(e.to_string()),
        }
    }

    /// Add max position percentage rule (0.1 = 10%)
    pub fn add_max_position_percent_rule(&mut self, max_pct: f64) {
        self.dynamic_rules.push(Box::new(MaxPositionPercentRule {
            max_pct: Decimal::from_f64(max_pct).unwrap_or(Decimal::ZERO),
        }));
    }

    /// Add max leverage rule (e.g. 1.5 = 150%)
    pub fn add_max_leverage_rule(&mut self, max_leverage: f64) {
        self.dynamic_rules.push(Box::new(MaxLeverageRule {
            max_leverage: Decimal::from_f64(max_leverage).unwrap_or(Decimal::ZERO),
        }));
    }

    /// Add sector concentration rule
    pub fn add_sector_concentration_rule(&mut self, max_pct: f64, sector_map: HashMap<String, String>) {
        self.dynamic_rules.push(Box::new(SectorConcentrationRule {
            max_pct: Decimal::from_f64(max_pct).unwrap_or(Decimal::ZERO),
            sector_map,
        }));
    }
}

impl RiskManager {
    fn init_rules(&mut self) {
        // Common rules
        self.common_rules.push(Box::new(RestrictedListRule));
        self.common_rules.push(Box::new(MaxOrderSizeRule));
        self.common_rules.push(Box::new(MaxOrderValueRule));
        self.common_rules.push(Box::new(MaxPositionSizeRule));
        self.common_rules.push(Box::new(CashMarginRule));

        // Stock rules
        self.asset_rules
            .entry(AssetType::Stock)
            .or_default()
            .push(Box::new(StockAvailablePositionRule));
        self.asset_rules
            .entry(AssetType::Fund)
            .or_default()
            .push(Box::new(StockAvailablePositionRule));

        // Futures rules
        self.asset_rules
            .entry(AssetType::Futures)
            .or_default()
            .push(Box::new(FuturesMarginRule));

        // Option rules
        self.asset_rules
            .entry(AssetType::Option)
            .or_default()
            .push(Box::new(OptionGreekRiskRule));
    }

    pub fn check_and_adjust(
        &self,
        order: &mut Order,
        ctx: &crate::context::EngineContext,
    ) -> Result<(), AkQuantError> {
        // 1. Initial Check
        if let Err(err) = self.check_internal(order, ctx) {
            let err_msg = err.to_string();
            // Check for insufficient cash/margin to attempt auto-reduction
            // This logic was moved from OrderManager
            if (err_msg.contains("Insufficient cash") || err_msg.contains("Insufficient margin"))
                && order.side == crate::model::OrderSide::Buy
                && let Some(instr) = ctx.instruments.get(&order.symbol) {
                    // Get price (Limit or Last)
                    let price = if let Some(p) = order.price {
                        p
                    } else {
                        *ctx.last_prices
                            .get(&order.symbol)
                            .unwrap_or(&Decimal::ZERO)
                    };

                    if price > Decimal::ZERO {
                        let multiplier = instr.multiplier();
                        let margin_ratio = instr.margin_ratio();

                        // Cost per unit = Price * Multiplier * MarginRatio
                        // For Stock, MarginRatio is usually 1.0 (or 100% cash)
                        let cost_per_unit = price * multiplier * margin_ratio;

                        if cost_per_unit > Decimal::ZERO {
                            // Calculate max quantity based on available cash/margin
                            // Note: Portfolio::cash is used here. Ideally should use Free Margin for futures.
                            // But for simple "Insufficient cash" check, let's use cash.
                            // If we want to support margin trading correctly here, we should check what check_internal failed on.

                            // For now, let's use a simplified calculation similar to old OrderManager
                            let max_qty_raw = ctx.portfolio.cash / cost_per_unit;

                            // Buffer for commission (e.g. 1% buffer -> 0.9999 safety factor from config)
                            let safety_margin = self.config.safety_margin;
                            let safety_factor = Decimal::from_f64(1.0 - safety_margin)
                                .unwrap_or(Decimal::from_f64(0.9999).unwrap());

                            let max_qty_raw = max_qty_raw * safety_factor;

                            let lot_size = instr.lot_size();
                            let mut new_qty = max_qty_raw.floor();
                            if lot_size > Decimal::ZERO {
                                new_qty = new_qty - (new_qty % lot_size);
                            }

                            if new_qty > Decimal::ZERO && new_qty < order.quantity {
                                order.quantity = new_qty;
                                // Re-check with new quantity
                                return self.check_internal(order, ctx);
                            }
                        }
                    }
                }
            return Err(err);
        }
        Ok(())
    }

    pub fn check_internal(
        &self,
        order: &Order,
        ctx: &crate::context::EngineContext,
    ) -> Result<(), AkQuantError> {
        if !self.config.active {
            return Ok(());
        }

        let instrument = ctx.instruments.get(&order.symbol).ok_or_else(|| {
            AkQuantError::OrderError(format!("Instrument not found for {}", order.symbol))
        })?;

        let risk_ctx = crate::risk::rule::RiskCheckContext {
            portfolio: ctx.portfolio,
            instrument,
            instruments: ctx.instruments,
            active_orders: ctx.active_orders,
            current_prices: ctx.last_prices,
            config: &self.config,
        };

        // Check common rules
        for rule in &self.common_rules {
            rule.check(order, &risk_ctx)?;
        }

        // Check asset-specific rules
        if let Some(rules) = self.asset_rules.get(&instrument.asset_type) {
            for rule in rules {
                rule.check(order, &risk_ctx)?;
            }
        }

        // Check dynamic rules
        for rule in &self.dynamic_rules {
            rule.check(order, &risk_ctx)?;
        }

        Ok(())
    }
}
