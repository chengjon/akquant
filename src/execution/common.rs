use crate::event::Event;
use crate::execution::slippage::SlippageModel;
use crate::model::{
    ExecutionMode, Instrument, Order, OrderSide, OrderStatus, OrderType, TimeInForce, Trade,
};
use rust_decimal::Decimal;
use uuid::Uuid;

/// 通用撮合逻辑
pub struct CommonMatcher;

impl CommonMatcher {
    /// 核心撮合逻辑 (支持穿透检查、Bar内止损、价格改善)
    ///
    /// :param order: 订单
    /// :param event: 事件 (Bar/Tick)
    /// :param instrument: 标的定义
    /// :param execution_mode: 撮合模式
    /// :param slippage: 滑点模型
    /// :param volume_limit_pct: 成交量限制比例
    /// :param bar_index: 当前 Bar 索引
    /// :param check_lot_size: 是否检查最小交易单位 (针对股票买入等场景)
    pub fn match_order(
        order: &mut Order,
        event: &Event,
        instrument: &Instrument,
        execution_mode: ExecutionMode,
        slippage: &dyn SlippageModel,
        volume_limit_pct: Decimal,
        bar_index: usize,
        check_lot_size: bool,
    ) -> Option<Event> {
        // 0. 检查最小交易单位 (Lot Size)
        // 仅针对买入订单，且必须存在标的定义
        if check_lot_size && order.side == OrderSide::Buy {
            if order.quantity % instrument.lot_size() != Decimal::ZERO {
                order.status = OrderStatus::Rejected;
                order.reject_reason = format!(
                    "Quantity {} is not a multiple of lot size {}",
                    order.quantity,
                    instrument.lot_size()
                );
                match event {
                    Event::Bar(b) => order.updated_at = b.timestamp,
                    Event::Tick(t) => order.updated_at = t.timestamp,
                    _ => {}
                }
                return Some(Event::ExecutionReport(order.clone(), None));
            }
        }

        match event {
            Event::Bar(bar) => {
                if order.symbol != bar.symbol {
                    return None;
                }

                // 1. Volume Check (Suspension)
                if bar.volume <= Decimal::ZERO {
                    return None;
                }

                // 2. Check Stop Trigger
                let mut is_triggered_now = false;
                let mut trigger_price_val = None;

                if let Some(trigger_price) = order.trigger_price {
                    // Check Gap (Open vs Trigger)
                    let gap_triggered = match order.side {
                        OrderSide::Buy => bar.open >= trigger_price,
                        OrderSide::Sell => bar.open <= trigger_price,
                    };

                    // Check In-Bar (High/Low vs Trigger)
                    let in_bar_triggered = if !gap_triggered {
                        match order.side {
                            OrderSide::Buy => bar.high >= trigger_price,
                            OrderSide::Sell => bar.low <= trigger_price,
                        }
                    } else {
                        false
                    };

                    if gap_triggered || in_bar_triggered {
                        is_triggered_now = true;
                        trigger_price_val = Some(trigger_price);
                        order.trigger_price = None; // Clear trigger

                        // Update Order Type
                        match order.order_type {
                            OrderType::StopMarket => order.order_type = OrderType::Market,
                            OrderType::StopLimit => order.order_type = OrderType::Limit,
                            _ => {}
                        }
                    } else {
                        return None; // Not triggered
                    }
                }

                // 3. Execution Logic
                let mut execute_price: Option<Decimal> = None;

                // Determine Market Base Price
                let market_price = match execution_mode {
                    ExecutionMode::NextOpen => bar.open,
                    ExecutionMode::CurrentClose => bar.close,
                    ExecutionMode::NextAverage => {
                        (bar.open + bar.high + bar.low + bar.close) / Decimal::from(4)
                    }
                    ExecutionMode::NextHighLowMid => (bar.high + bar.low) / Decimal::from(2),
                };

                match order.order_type {
                    OrderType::Market => {
                        // Special handling for Stop-Market triggered IN-BAR
                        if is_triggered_now {
                            if let Some(tp) = trigger_price_val {
                                // Re-check gap to decide price
                                let is_gap = match order.side {
                                    OrderSide::Buy => bar.open >= tp,
                                    OrderSide::Sell => bar.open <= tp,
                                };

                                if is_gap {
                                    execute_price = Some(bar.open);
                                } else {
                                    // In-bar trigger: execute at trigger price
                                    execute_price = Some(tp);
                                }
                            } else {
                                execute_price = Some(market_price);
                            }
                        } else {
                            // Standard Market Order
                            execute_price = Some(market_price);
                        }
                    }
                    OrderType::Limit => {
                        if let Some(limit_price) = order.price {
                            // 3.1 Check Executability (Low/High Penetration)
                            let can_execute = match order.side {
                                OrderSide::Buy => bar.low <= limit_price,
                                OrderSide::Sell => bar.high >= limit_price,
                            };

                            if can_execute {
                                // 3.2 Determine Fill Price
                                let mut final_fill_price = limit_price;

                                // Optimization: If Open is better, take Open
                                match order.side {
                                    OrderSide::Buy => {
                                        if bar.open < limit_price {
                                            final_fill_price = bar.open;
                                        }
                                    }
                                    OrderSide::Sell => {
                                        if bar.open > limit_price {
                                            final_fill_price = bar.open;
                                        }
                                    }
                                }

                                // 3.3 Apply Stop-Limit Constraints (In-Bar Trigger)
                                if is_triggered_now {
                                    if let Some(tp) = trigger_price_val {
                                        let is_gap = match order.side {
                                            OrderSide::Buy => bar.open >= tp,
                                            OrderSide::Sell => bar.open <= tp,
                                        };

                                        if !is_gap {
                                            // Triggered In-Bar.
                                            match order.side {
                                                OrderSide::Buy => {
                                                    if final_fill_price < tp {
                                                        final_fill_price = tp;
                                                    }
                                                    if final_fill_price > limit_price {
                                                        return None;
                                                    }
                                                }
                                                OrderSide::Sell => {
                                                    if final_fill_price > tp {
                                                        final_fill_price = tp;
                                                    }
                                                    if final_fill_price < limit_price {
                                                        return None;
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                                execute_price = Some(final_fill_price);
                            }
                        }
                    }
                    _ => {}
                }

                // 4. Create Trade if executed
                if let Some(price) = execute_price {
                    // Apply Slippage
                    let final_price = slippage.calculate_price(price, order.quantity, order.side);

                    // Check Volume Limit
                    let max_qty = if volume_limit_pct > Decimal::ZERO {
                        bar.volume * volume_limit_pct
                    } else {
                        Decimal::MAX
                    };

                    let trade_qty = (order.quantity - order.filled_quantity).min(max_qty);

                    if trade_qty > Decimal::ZERO {
                        order.status = OrderStatus::Filled;
                        order.updated_at = bar.timestamp;

                        // Check partial fill
                        if trade_qty < order.quantity - order.filled_quantity {
                            order.status = OrderStatus::Submitted;
                        }

                        order.filled_quantity += trade_qty;

                        // Update Average Price
                        let current_filled = order.filled_quantity;
                        let prev_filled = current_filled - trade_qty;
                        let prev_avg = order.average_filled_price.unwrap_or(Decimal::ZERO);
                        let new_avg = (prev_avg * prev_filled + final_price * trade_qty) / current_filled;
                        order.average_filled_price = Some(new_avg);

                        let trade = Trade {
                            id: Uuid::new_v4().to_string(),
                            order_id: order.id.clone(),
                            symbol: order.symbol.clone(),
                            side: order.side,
                            quantity: trade_qty,
                            price: final_price,
                            commission: Decimal::ZERO,
                            timestamp: bar.timestamp,
                            bar_index,
                        };
                        return Some(Event::ExecutionReport(order.clone(), Some(trade)));
                    }
                } else if order.time_in_force == TimeInForce::IOC || order.time_in_force == TimeInForce::FOK {
                    // Cancel IOC/FOK if not filled
                    order.status = OrderStatus::Cancelled;
                    order.updated_at = bar.timestamp;
                    return Some(Event::ExecutionReport(order.clone(), None));
                }
            }
            Event::Tick(tick) => {
                 if order.symbol != tick.symbol {
                    return None;
                }

                // 1. Check Trigger
                if let Some(trigger_price) = order.trigger_price {
                    let triggered = match order.side {
                        OrderSide::Buy => tick.price >= trigger_price,
                        OrderSide::Sell => tick.price <= trigger_price,
                    };
                    if !triggered {
                        return None;
                    }
                     order.trigger_price = None;
                    match order.order_type {
                        OrderType::StopMarket => order.order_type = OrderType::Market,
                        OrderType::StopLimit => order.order_type = OrderType::Limit,
                        _ => {}
                    }
                }

                // 2. Execute
                 let mut execute_price = None;
                 match order.order_type {
                     OrderType::Market => execute_price = Some(tick.price),
                     OrderType::Limit => {
                         if let Some(limit) = order.price {
                             match order.side {
                                 OrderSide::Buy => if tick.price <= limit { execute_price = Some(limit) },
                                 OrderSide::Sell => if tick.price >= limit { execute_price = Some(limit) },
                             }
                             if let Some(_) = execute_price {
                                 execute_price = Some(tick.price);
                             }
                         }
                     }
                     _ => {}
                 }

                 if let Some(price) = execute_price {
                      let final_price = slippage.calculate_price(price, order.quantity, order.side);

                      let trade_qty = order.quantity - order.filled_quantity;

                      if trade_qty > Decimal::ZERO {
                        order.status = OrderStatus::Filled;
                        order.updated_at = tick.timestamp;
                        order.filled_quantity += trade_qty;
                        order.average_filled_price = Some(final_price);
                         let trade = Trade {
                            id: Uuid::new_v4().to_string(),
                            order_id: order.id.clone(),
                            symbol: order.symbol.clone(),
                            side: order.side,
                            quantity: trade_qty,
                            price: final_price,
                            commission: Decimal::ZERO,
                            timestamp: tick.timestamp,
                            bar_index,
                        };
                        return Some(Event::ExecutionReport(order.clone(), Some(trade)));
                      }
                 }
            }
            _ => {}
        }
        None
    }
}
