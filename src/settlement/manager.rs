use crate::market::manager::MarketManager;
use crate::model::{Instrument, Order, OrderStatus, TimeInForce};
use crate::portfolio::Portfolio;
use crate::risk::RiskConfig;
use chrono::NaiveDate;
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use std::collections::HashMap;
use std::sync::Arc;

use super::expiry::ExpirySettlementHandler;
use super::handler::SettlementHandler;
use super::option::OptionSettlementHandler;

/// Settlement Context
pub struct SettlementContext<'a> {
    pub date: NaiveDate,
    pub instruments: &'a HashMap<String, Instrument>,
    pub last_prices: &'a HashMap<String, Decimal>,
    pub market_manager: &'a MarketManager,
    pub risk_config: &'a RiskConfig,
}

#[derive(Debug, Clone, Default)]
pub struct SettlementOutcome {
    pub daily_interest: Decimal,
    pub forced_liquidation: bool,
    pub liquidated_symbols: Vec<String>,
}

/// Settlement Manager
/// Centralizes daily settlement logic including T+1 settlement, option expiry, and order expiration.
pub struct SettlementManager {
    option_handler: OptionSettlementHandler,
    expiry_handler: ExpirySettlementHandler,
}

impl SettlementManager {
    #[must_use]
    pub fn new() -> Self {
        Self {
            option_handler: OptionSettlementHandler,
            expiry_handler: ExpirySettlementHandler,
        }
    }

    /// Process daily settlement routine
    /// 1. T+1 Settlement (`MarketManager`)
    /// 2. Option Expiry
    /// 3. Order Expiration (Day orders)
    pub fn process_daily_settlement(
        &self,
        portfolio: &mut Portfolio,
        active_orders: &mut Vec<Order>,
        expired_orders_out: &mut Vec<Order>,
        ctx: &SettlementContext,
    ) -> SettlementOutcome {
        let outcome = self.process_margin_interest_and_liquidation(portfolio, ctx);

        // 1. Market Settlement (T+1 logic)
        // Note: MarketManager::on_day_close handles T+1 by moving positions from 'positions' to 'available_positions'
        // But wait, `portfolio.positions` is T+0/Total, `available_positions` is Sellable.
        // `on_day_close` updates `available_positions`.
        ctx.market_manager.on_day_close(
            &portfolio.positions,
            Arc::make_mut(&mut portfolio.available_positions),
            ctx.instruments,
        );

        // 2. Option Expiry
        let mut tasks = self.option_handler.check_settlement(
            ctx.date,
            portfolio,
            ctx.instruments,
            ctx.last_prices,
        );
        // 3. Futures/Stock Expiry
        tasks.extend(self.expiry_handler.check_settlement(
            ctx.date,
            portfolio,
            ctx.instruments,
            ctx.last_prices,
        ));

        for task in tasks {
            // Execute settlement task
            // 1. Adjust Cash
            if !task.cash_flow.is_zero() {
                portfolio.cash += task.cash_flow;
            }

            // 2. Close Position
            // Remove from total positions
            {
                let positions = Arc::make_mut(&mut portfolio.positions);
                if let Some(qty) = positions.get_mut(&task.symbol) {
                    *qty -= task.quantity;
                    if qty.is_zero() {
                        positions.remove(&task.symbol);
                    }
                }
            }

            // Remove from available positions
            {
                let avail_pos = Arc::make_mut(&mut portfolio.available_positions);
                if let Some(qty) = avail_pos.get_mut(&task.symbol) {
                    *qty -= task.quantity;
                    if qty.is_zero() {
                        avail_pos.remove(&task.symbol);
                    }
                }
            }
        }

        // 4. Order Expiration (Day Orders)
        // Partition orders into expired and kept
        let (expired, kept): (Vec<Order>, Vec<Order>) = active_orders
            .drain(..)
            .partition(|o| o.time_in_force == TimeInForce::Day);

        *active_orders = kept;

        for mut o in expired {
            o.status = OrderStatus::Expired;
            expired_orders_out.push(o);
        }
        outcome
    }

    fn process_margin_interest_and_liquidation(
        &self,
        portfolio: &mut Portfolio,
        ctx: &SettlementContext,
    ) -> SettlementOutcome {
        let mut outcome = SettlementOutcome::default();
        if !ctx.risk_config.is_margin_account() {
            return outcome;
        }

        let (_, _, short_market_value) =
            compute_portfolio_metrics(portfolio, ctx.last_prices, ctx.instruments);

        let borrowed_cash = (-portfolio.cash).max(Decimal::ZERO);
        let financing_rate =
            Decimal::from_f64(ctx.risk_config.financing_rate_annual).unwrap_or(Decimal::ZERO);
        let borrow_rate =
            Decimal::from_f64(ctx.risk_config.borrow_rate_annual).unwrap_or(Decimal::ZERO);
        let day_divisor = Decimal::from(365);
        let financing_interest = borrowed_cash * financing_rate / day_divisor;
        let borrow_interest = short_market_value * borrow_rate / day_divisor;
        let total_interest = (financing_interest + borrow_interest).max(Decimal::ZERO);
        if total_interest > Decimal::ZERO {
            portfolio.cash -= total_interest;
            outcome.daily_interest = total_interest;
        }

        if !ctx.risk_config.allow_force_liquidation {
            return outcome;
        }

        let (_, equity, gross_exposure) =
            compute_portfolio_metrics(portfolio, ctx.last_prices, ctx.instruments);
        if gross_exposure <= Decimal::ZERO {
            return outcome;
        }
        let maintenance_ratio = equity / gross_exposure;
        if maintenance_ratio >= ctx.risk_config.maintenance_margin_ratio_decimal() {
            return outcome;
        }

        let mut symbols_to_close: Vec<(String, Decimal)> = portfolio
            .positions
            .iter()
            .filter_map(|(symbol, qty)| {
                if qty.is_zero() {
                    return None;
                }
                let price = ctx.last_prices.get(symbol).copied()?;
                if price <= Decimal::ZERO {
                    return None;
                }
                let multiplier = ctx
                    .instruments
                    .get(symbol)
                    .map(|i| i.multiplier())
                    .unwrap_or(Decimal::ONE);
                Some((symbol.clone(), qty.abs() * price * multiplier))
            })
            .collect();
        let short_first = ctx.risk_config.liquidation_short_first();
        symbols_to_close.sort_by(
            |(left_symbol, left_exposure), (right_symbol, right_exposure)| {
                let left_qty = portfolio
                    .positions
                    .get(left_symbol)
                    .copied()
                    .unwrap_or(Decimal::ZERO);
                let right_qty = portfolio
                    .positions
                    .get(right_symbol)
                    .copied()
                    .unwrap_or(Decimal::ZERO);
                let left_rank = if short_first {
                    if left_qty < Decimal::ZERO { 0 } else { 1 }
                } else if left_qty > Decimal::ZERO {
                    0
                } else {
                    1
                };
                let right_rank = if short_first {
                    if right_qty < Decimal::ZERO { 0 } else { 1 }
                } else if right_qty > Decimal::ZERO {
                    0
                } else {
                    1
                };
                left_rank
                    .cmp(&right_rank)
                    .then_with(|| right_exposure.cmp(left_exposure))
            },
        );

        let symbols_to_close: Vec<String> = symbols_to_close
            .into_iter()
            .map(|(symbol, _)| symbol)
            .collect();
        for symbol in symbols_to_close {
            let qty = portfolio
                .positions
                .get(&symbol)
                .copied()
                .unwrap_or(Decimal::ZERO);
            if qty.is_zero() {
                continue;
            }
            let Some(price) = ctx.last_prices.get(&symbol).copied() else {
                continue;
            };
            let multiplier = ctx
                .instruments
                .get(&symbol)
                .map(|i| i.multiplier())
                .unwrap_or(Decimal::ONE);
            portfolio.cash += qty * price * multiplier;

            {
                let positions = Arc::make_mut(&mut portfolio.positions);
                positions.remove(&symbol);
            }
            {
                let avail_pos = Arc::make_mut(&mut portfolio.available_positions);
                avail_pos.remove(&symbol);
            }
            outcome.liquidated_symbols.push(symbol.clone());

            let (_, next_equity, next_exposure) =
                compute_portfolio_metrics(portfolio, ctx.last_prices, ctx.instruments);
            if next_exposure <= Decimal::ZERO {
                break;
            }
            let next_ratio = next_equity / next_exposure;
            if next_ratio >= ctx.risk_config.maintenance_margin_ratio_decimal() {
                break;
            }
        }
        outcome.forced_liquidation = true;
        outcome
    }
}

fn compute_portfolio_metrics(
    portfolio: &Portfolio,
    prices: &HashMap<String, Decimal>,
    instruments: &HashMap<String, Instrument>,
) -> (Decimal, Decimal, Decimal) {
    let mut gross_exposure = Decimal::ZERO;
    for (symbol, quantity) in portfolio.positions.iter() {
        if quantity.is_zero() {
            continue;
        }
        let Some(price) = prices.get(symbol).copied() else {
            continue;
        };
        if price <= Decimal::ZERO {
            continue;
        }
        let multiplier = instruments
            .get(symbol)
            .map(|i| i.multiplier())
            .unwrap_or(Decimal::ONE);
        gross_exposure += quantity.abs() * price * multiplier;
    }
    let equity = portfolio.calculate_equity(prices, instruments);
    (portfolio.cash, equity, gross_exposure)
}

impl Default for SettlementManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::instrument::{InstrumentEnum, StockInstrument};
    use crate::model::types::AssetType;
    use std::str::FromStr;

    fn stock_instrument(symbol: &str) -> Instrument {
        Instrument {
            asset_type: AssetType::Stock,
            inner: InstrumentEnum::Stock(StockInstrument {
                symbol: symbol.to_string(),
                lot_size: Decimal::ONE,
                tick_size: Decimal::new(1, 2),
                expiry_date: None,
            }),
        }
    }

    #[test]
    fn test_margin_interest_is_deducted_daily() {
        let mut portfolio = Portfolio {
            cash: Decimal::from(-5000),
            positions: Arc::new(HashMap::new()),
            available_positions: Arc::new(HashMap::new()),
        };
        let mut instruments = HashMap::new();
        instruments.insert("AAA".to_string(), stock_instrument("AAA"));
        let mut prices = HashMap::new();
        prices.insert("AAA".to_string(), Decimal::from(100));
        let mut risk = RiskConfig::new();
        risk.account_mode = "margin".to_string();
        risk.financing_rate_annual = 36.5;
        risk.borrow_rate_annual = 0.0;
        risk.allow_force_liquidation = false;
        let market_manager = MarketManager::new();

        let ctx = SettlementContext {
            date: NaiveDate::from_ymd_opt(2024, 1, 2).expect("valid date"),
            instruments: &instruments,
            last_prices: &prices,
            market_manager: &market_manager,
            risk_config: &risk,
        };
        let outcome = SettlementManager::new().process_daily_settlement(
            &mut portfolio,
            &mut Vec::new(),
            &mut Vec::new(),
            &ctx,
        );
        assert_eq!(portfolio.cash, Decimal::from(-5500));
        assert_eq!(outcome.daily_interest, Decimal::from(500));
        assert!(!outcome.forced_liquidation);
    }

    #[test]
    fn test_margin_liquidation_closes_positions_when_maintenance_breached() {
        let mut pos = HashMap::new();
        pos.insert(
            "AAA".to_string(),
            Decimal::from_str("150").expect("decimal"),
        );
        let mut portfolio = Portfolio {
            cash: Decimal::from(-5000),
            positions: Arc::new(pos),
            available_positions: Arc::new(HashMap::new()),
        };
        let mut instruments = HashMap::new();
        instruments.insert("AAA".to_string(), stock_instrument("AAA"));
        let mut prices = HashMap::new();
        prices.insert("AAA".to_string(), Decimal::from(20));
        let mut risk = RiskConfig::new();
        risk.account_mode = "margin".to_string();
        risk.financing_rate_annual = 0.0;
        risk.borrow_rate_annual = 0.0;
        risk.allow_force_liquidation = true;
        risk.maintenance_margin_ratio = 0.5;
        let market_manager = MarketManager::new();

        let ctx = SettlementContext {
            date: NaiveDate::from_ymd_opt(2024, 1, 2).expect("valid date"),
            instruments: &instruments,
            last_prices: &prices,
            market_manager: &market_manager,
            risk_config: &risk,
        };
        let outcome = SettlementManager::new().process_daily_settlement(
            &mut portfolio,
            &mut Vec::new(),
            &mut Vec::new(),
            &ctx,
        );
        assert!(portfolio.positions.is_empty());
        assert!(portfolio.available_positions.is_empty());
        assert_eq!(portfolio.cash, Decimal::from(-2000));
        assert!(outcome.forced_liquidation);
        assert_eq!(outcome.liquidated_symbols, vec!["AAA".to_string()]);
    }

    #[test]
    fn test_liquidation_priority_controls_close_order() {
        let mut positions = HashMap::new();
        positions.insert("LONG".to_string(), Decimal::from(100));
        positions.insert("SHORT".to_string(), Decimal::from(-50));

        let mut instruments = HashMap::new();
        instruments.insert("LONG".to_string(), stock_instrument("LONG"));
        instruments.insert("SHORT".to_string(), stock_instrument("SHORT"));

        let mut prices = HashMap::new();
        prices.insert("LONG".to_string(), Decimal::from(100));
        prices.insert("SHORT".to_string(), Decimal::from(100));

        let mut risk_short_first = RiskConfig::new();
        risk_short_first.account_mode = "margin".to_string();
        risk_short_first.allow_force_liquidation = true;
        risk_short_first.financing_rate_annual = 0.0;
        risk_short_first.borrow_rate_annual = 0.0;
        risk_short_first.maintenance_margin_ratio = 0.5;
        risk_short_first.liquidation_priority = "short_first".to_string();

        let mut risk_long_first = risk_short_first.clone();
        risk_long_first.liquidation_priority = "long_first".to_string();

        let market_manager = MarketManager::new();
        let date = NaiveDate::from_ymd_opt(2024, 1, 2).expect("valid date");

        let mut portfolio_short_first = Portfolio {
            cash: Decimal::from(2000),
            positions: Arc::new(positions.clone()),
            available_positions: Arc::new(HashMap::new()),
        };
        let ctx_short_first = SettlementContext {
            date,
            instruments: &instruments,
            last_prices: &prices,
            market_manager: &market_manager,
            risk_config: &risk_short_first,
        };
        let outcome_short_first = SettlementManager::new().process_daily_settlement(
            &mut portfolio_short_first,
            &mut Vec::new(),
            &mut Vec::new(),
            &ctx_short_first,
        );
        assert_eq!(
            portfolio_short_first
                .positions
                .get("SHORT")
                .copied()
                .unwrap_or(Decimal::ZERO),
            Decimal::ZERO
        );
        assert_eq!(
            portfolio_short_first
                .positions
                .get("LONG")
                .copied()
                .unwrap_or(Decimal::ZERO),
            Decimal::from(100)
        );
        assert_eq!(
            outcome_short_first.liquidated_symbols,
            vec!["SHORT".to_string()]
        );

        let mut portfolio_long_first = Portfolio {
            cash: Decimal::from(2000),
            positions: Arc::new(positions),
            available_positions: Arc::new(HashMap::new()),
        };
        let ctx_long_first = SettlementContext {
            date,
            instruments: &instruments,
            last_prices: &prices,
            market_manager: &market_manager,
            risk_config: &risk_long_first,
        };
        let outcome_long_first = SettlementManager::new().process_daily_settlement(
            &mut portfolio_long_first,
            &mut Vec::new(),
            &mut Vec::new(),
            &ctx_long_first,
        );
        assert_eq!(
            portfolio_long_first
                .positions
                .get("LONG")
                .copied()
                .unwrap_or(Decimal::ZERO),
            Decimal::ZERO
        );
        assert_eq!(
            portfolio_long_first
                .positions
                .get("SHORT")
                .copied()
                .unwrap_or(Decimal::ZERO),
            Decimal::from(-50)
        );
        assert_eq!(
            outcome_long_first.liquidated_symbols,
            vec!["LONG".to_string()]
        );
    }
}
