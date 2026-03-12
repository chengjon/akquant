use std::collections::HashMap;
use std::sync::{Arc, RwLock};

use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

use crate::analysis::TradeTracker;
use crate::history::HistoryBuffer;
use crate::market::MarketModel;
use crate::model::{Instrument, Order, OrderStatus, Trade};
use crate::portfolio::Portfolio;

/// 订单管理器
/// 负责管理订单列表、成交记录及状态流转
#[derive(Clone, Serialize, Deserialize)]
pub struct OrderManager {
    /// 历史订单 (已完成)
    pub orders: Vec<Order>,
    /// 当前活跃订单 (未完成)
    pub active_orders: Vec<Order>,
    /// 历史成交记录
    pub trades: Vec<Trade>,
    /// 当前步生成的成交 (用于通知策略)
    pub current_step_trades: Vec<Trade>,
    /// 交易追踪器 (用于计算 PnL 和统计)
    pub trade_tracker: TradeTracker,
}

impl OrderManager {
    pub fn new() -> Self {
        OrderManager {
            orders: Vec::new(),
            active_orders: Vec::new(),
            trades: Vec::new(),
            current_step_trades: Vec::new(),
            trade_tracker: TradeTracker::new(),
        }
    }

    /// 添加新订单 (例如从 OrderValidated 事件)
    pub fn add_active_order(&mut self, order: Order) {
        self.active_orders.push(order);
    }

    /// 处理执行报告 (ExecutionReport)
    /// 更新活跃订单状态
    pub fn on_execution_report(&mut self, report: Order) {
        // Find existing order
        if let Some(existing) = self.active_orders.iter_mut().find(|o| o.id == report.id) {
            existing.status = report.status;
            existing.filled_quantity = report.filled_quantity;
            existing.average_filled_price = report.average_filled_price;
            existing.updated_at = report.updated_at;
            existing.reject_reason = report.reject_reason;
        } else {
            // If it's a new order report (e.g. Rejected immediately), add to active so it can be moved to history later
            if report.status == OrderStatus::Rejected
                || report.status == OrderStatus::New
                || report.status == OrderStatus::PartiallyFilled
                || report.status == OrderStatus::Submitted
            {
                self.active_orders.push(report);
            }
        }
    }

    /// 清理已完成的订单 (Filled, Cancelled, Expired, Rejected)
    /// 将其移入历史列表
    pub fn cleanup_finished_orders(&mut self) {
        let (finished, active): (Vec<Order>, Vec<Order>) =
            self.active_orders.drain(..).partition(|o| {
                o.status == OrderStatus::Filled
                    || o.status == OrderStatus::Cancelled
                    || o.status == OrderStatus::Expired
                    || o.status == OrderStatus::Rejected
            });

        self.orders.extend(finished);
        self.active_orders = active;
    }

    /// 获取所有订单 (历史 + 活跃)
    pub fn get_all_orders(&self) -> Vec<Order> {
        let mut all = self.orders.clone();
        all.extend(self.active_orders.clone());
        all
    }

    /// 处理成交列表
    /// 包括资金调整、持仓更新、PnL 计算等
    pub fn process_trades(
        &mut self,
        mut trades: Vec<Trade>,
        portfolio: &mut Portfolio,
        instruments: &HashMap<String, Instrument>,
        market_model: &dyn MarketModel,
        history_buffer: &Arc<RwLock<HistoryBuffer>>,
        last_prices: &HashMap<String, Decimal>,
    ) {
        // Filter out zero quantity trades (just in case)
        trades.retain(|t| t.quantity > Decimal::ZERO);

        for mut trade in trades {
            // 2. Calculate Final Commission
            let instr_opt = instruments.get(&trade.symbol);
            if let Some(instr) = instr_opt {
                trade.commission = market_model.calculate_commission(
                    instr,
                    trade.side,
                    trade.price,
                    trade.quantity,
                );
            }

            // 3. Update Portfolio
            portfolio.adjust_cash(-trade.commission);

            let multiplier = instr_opt.map(|i| i.multiplier()).unwrap_or(Decimal::ONE);
            let cost = trade.price * trade.quantity * multiplier;

            if trade.side == crate::model::OrderSide::Buy {
                portfolio.adjust_cash(-cost);
                portfolio.adjust_position(&trade.symbol, trade.quantity);
            } else {
                portfolio.adjust_cash(cost); // Sell adds cash
                portfolio.adjust_position(&trade.symbol, -trade.quantity);
            }

            // Update available positions (T+1/T+0 rules)
            if let Some(instr) = instr_opt {
                market_model.update_available_position(
                    Arc::make_mut(&mut portfolio.available_positions),
                    instr,
                    trade.quantity,
                    trade.side,
                );
            }

            // 4. Update Order Commission
            // Note: filled_quantity and average_filled_price are updated via ExecutionReport
            // in on_execution_report, so we don't need to accumulate them here to avoid double counting.
            if let Some(order) = self
                .active_orders
                .iter_mut()
                .find(|o| o.id == trade.order_id)
            {
                order.commission += trade.commission;

                // Check if fully filled
                // Note: We don't change status to Filled here immediately because
                // execution report might come later or we want to wait for it?
                // Actually Engine logic relied on ExecutionReport to set status to Filled.
                // But here we are processing trade first?
                // In Engine::run, ExecutionReport updates status, THEN process_trades is called.
                // So status might already be Filled if this is the last trade.
                // But if we generated trade internally (simulated), we might need to update status.
                // However, SimulatedExecutionClient sends ExecutionReport with status Filled.
                // So we should rely on that.
                // But we update filled_qty here just in case?
                // Actually, if we rely on ExecutionReport for status, we should be fine.
                // The order update logic in on_execution_report handles it.
                // We just update commission here maybe?
            }

            // 5. Track Trade (PnL)
            let order_tag = self
                .active_orders
                .iter()
                .find(|o| o.id == trade.order_id)
                .map(|o| o.tag.as_str());

            // Get history for MAE/MFE
            // Need to lock history buffer
            let history_guard = history_buffer.read().unwrap();
            let symbol_history = history_guard.get_history(&trade.symbol);

            // Calculate Portfolio Value for % metrics
            let portfolio_value = portfolio.calculate_equity(last_prices, instruments);

            self.trade_tracker
                .process_trade(&trade, order_tag, symbol_history, portfolio_value);

            // 6. Record Trade
            self.trades.push(trade.clone());
            self.current_step_trades.push(trade);
        }
    }
}

impl Default for OrderManager {
    fn default() -> Self {
        Self::new()
    }
}
