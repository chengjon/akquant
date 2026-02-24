use rust_decimal::prelude::*;
use std::collections::HashMap;

use crate::analysis::{BacktestResult, PositionSnapshot};
use crate::model::Instrument;
use crate::portfolio::Portfolio;

/// 统计管理器
///
/// 负责维护回测过程中的统计数据，包括：
/// - 权益曲线 (Equity Curve)
/// - 现金曲线 (Cash Curve)
/// - 持仓快照 (Position Snapshots)
/// - 生成最终的回测结果 (BacktestResult)
pub struct StatisticsManager {
    /// 权益曲线 [(timestamp, equity)]
    equity_curve: Vec<(i64, Decimal)>,
    /// 现金曲线 [(timestamp, cash)]
    cash_curve: Vec<(i64, Decimal)>,
    /// 持仓快照 [(timestamp, snapshots)]
    pub snapshots: Vec<(i64, Vec<PositionSnapshot>)>,
}

impl Default for StatisticsManager {
    fn default() -> Self {
        Self::new()
    }
}

impl StatisticsManager {
    /// 创建新的统计管理器
    pub fn new() -> Self {
        Self {
            equity_curve: Vec::new(),
            cash_curve: Vec::new(),
            snapshots: Vec::new(),
        }
    }

    /// 更新权益和现金曲线
    pub fn update(&mut self, timestamp: i64, equity: Decimal, cash: Decimal) {
        self.equity_curve.push((timestamp, equity));
        self.cash_curve.push((timestamp, cash));
    }

    /// 记录持仓快照
    pub fn record_snapshot(
        &mut self,
        timestamp: i64,
        portfolio: &Portfolio,
        instruments: &HashMap<String, Instrument>,
        last_prices: &HashMap<String, Decimal>,
        trade_tracker: &crate::analysis::TradeTracker,
    ) {
        let snapshots = Self::create_snapshot(portfolio, instruments, last_prices, trade_tracker);
        self.snapshots.push((timestamp, snapshots));
    }

    /// 创建持仓快照 (静态方法/无状态)
    pub fn create_snapshot(
        portfolio: &Portfolio,
        instruments: &HashMap<String, Instrument>,
        last_prices: &HashMap<String, Decimal>,
        trade_tracker: &crate::analysis::TradeTracker,
    ) -> Vec<PositionSnapshot> {
        let account_equity = portfolio.calculate_equity(last_prices, instruments);
        let account_equity_f64 = account_equity.to_f64().unwrap_or(0.0);

        let mut current_snapshots = Vec::new();
        for (symbol, &qty) in portfolio.positions.iter() {
            if qty == Decimal::ZERO {
                continue;
            }

            let price = last_prices
                .get(symbol)
                .cloned()
                .unwrap_or(Decimal::ZERO);
            let instr = instruments.get(symbol);
            let multiplier = instr.map(|i| i.multiplier()).unwrap_or(Decimal::ONE);
            let margin_ratio = instr.map(|i| i.margin_ratio()).unwrap_or(Decimal::ZERO);

            // Convert to f64 for snapshot
            let qty_f64 = qty.to_f64().unwrap_or(0.0);
            let price_f64 = price.to_f64().unwrap_or(0.0);

            let market_value = qty.abs() * price * multiplier;
            let market_value_f64 = market_value.to_f64().unwrap_or(0.0);

            let (long_shares, short_shares) = if qty > Decimal::ZERO {
                (qty_f64, 0.0)
            } else {
                (0.0, qty.abs().to_f64().unwrap_or(0.0))
            };

            let margin_dec = market_value * margin_ratio;
            let margin_f64 = margin_dec.to_f64().unwrap_or(0.0);

            let unrealized_pnl = trade_tracker.get_unrealized_pnl(symbol, price, multiplier);
            let unrealized_pnl_f64 = unrealized_pnl.to_f64().unwrap_or(0.0);

            let entry_price = trade_tracker.get_average_price(symbol);
            let entry_price_f64 = entry_price.to_f64().unwrap_or(0.0);

            current_snapshots.push(PositionSnapshot {
                symbol: symbol.clone(),
                quantity: qty_f64,
                entry_price: entry_price_f64,
                long_shares,
                short_shares,
                close: price_f64,
                equity: account_equity_f64,
                market_value: market_value_f64,
                margin: margin_f64,
                unrealized_pnl: unrealized_pnl_f64,
            });
        }
        current_snapshots
    }

    /// 生成最终的回测结果
    pub fn generate_backtest_result(
        &self,
        portfolio: &Portfolio,
        instruments: &HashMap<String, Instrument>,
        last_prices: &HashMap<String, Decimal>,
        order_manager: &crate::order_manager::OrderManager,
        initial_cash: Decimal,
        now_ns: Option<i64>,
    ) -> BacktestResult {
        // Calculate final PnL
        let trade_pnl = order_manager.trade_tracker.calculate_pnl(Some(last_prices.clone()));

        // Prepare data for result creation
        let mut equity_curve = self.equity_curve.clone();
        let mut cash_curve = self.cash_curve.clone();
        let mut snapshots = self.snapshots.clone();

        // Add final snapshot if needed
        if let Some(ts) = now_ns {
            let equity = portfolio.calculate_equity(last_prices, instruments);

            // Append final equity point if not present
            if equity_curve.last().map(|(t, _)| *t != ts).unwrap_or(true) {
                equity_curve.push((ts, equity));
            }

            // Append final cash point if not present
            if cash_curve.last().map(|(t, _)| *t != ts).unwrap_or(true) {
                cash_curve.push((ts, portfolio.cash));
            }

            // Append final position snapshot if not present
            if snapshots.last().map(|(t, _)| *t != ts).unwrap_or(true) {
                let snap = Self::create_snapshot(
                    portfolio,
                    instruments,
                    last_prices,
                    &order_manager.trade_tracker,
                );
                snapshots.push((ts, snap));
            }
        }

        BacktestResult::calculate(crate::analysis::CalculatorInput {
            equity_curve_decimal: equity_curve,
            cash_curve_decimal: cash_curve,
            snapshots,
            trade_pnl,
            trades: order_manager.trade_tracker.closed_trades.to_vec(),
            initial_cash,
            orders: order_manager.get_all_orders(),
            executions: order_manager.trades.clone(),
        })
    }

    // Removed create_backtest_result as it is merged into generate_backtest_result

    /// 获取当前的权益曲线（只读）
    pub fn equity_curve(&self) -> &Vec<(i64, Decimal)> {
        &self.equity_curve
    }

    /// 获取当前的现金曲线（只读）
    pub fn cash_curve(&self) -> &Vec<(i64, Decimal)> {
        &self.cash_curve
    }
}
