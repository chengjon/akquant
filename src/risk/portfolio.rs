use crate::error::AkQuantError;
use crate::model::{Order, OrderSide};
use rust_decimal::Decimal;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use super::rule::{RiskCheckContext, RiskRule};

/// Check max position value as percentage of total equity
#[derive(Debug, Clone)]
pub struct MaxPositionPercentRule {
    pub max_pct: Decimal,
}

impl RiskRule for MaxPositionPercentRule {
    fn name(&self) -> &'static str {
        "MaxPositionPercentRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        let equity = ctx
            .portfolio
            .calculate_equity(ctx.current_prices, ctx.instruments);

        if equity.is_zero() {
            // Avoid division by zero, maybe allow if equity is zero (startup)?
            // Or fail? Usually fail if no equity.
            return Ok(());
        }

        // Get current position
        let current_pos = ctx
            .portfolio
            .positions
            .get(&order.symbol)
            .copied()
            .unwrap_or(Decimal::ZERO);

        let multiplier = ctx.instrument.multiplier();

        // Determine price
        let price = if let Some(p) = order.price {
            p
        } else {
            *ctx.current_prices
                .get(&order.symbol)
                .unwrap_or(&Decimal::ZERO)
        };

        if price.is_zero() {
            return Ok(());
        }

        // Calculate new position size
        let new_pos = match order.side {
            OrderSide::Buy => current_pos + order.quantity,
            OrderSide::Sell => current_pos - order.quantity,
        };

        let new_pos_value = (new_pos * price * multiplier).abs();
        let current_pct = new_pos_value / equity;

        if current_pct > self.max_pct {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Position value ratio {:.2}% exceeds limit {:.2}% for {}",
                current_pct * Decimal::from(100),
                self.max_pct * Decimal::from(100),
                order.symbol
            )));
        }

        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::instrument::{InstrumentEnum, StockInstrument};
    use crate::model::{
        AssetType, Instrument, Order, OrderSide, OrderStatus, OrderType, TimeInForce,
    };
    use crate::portfolio::Portfolio;
    use rust_decimal::prelude::*;
    use std::sync::Arc;

    fn create_test_order(
        symbol: &str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
    ) -> Order {
        Order {
            id: "test".to_string(),
            symbol: symbol.to_string(),
            side,
            order_type: OrderType::Limit,
            quantity,
            price: Some(price),
            status: OrderStatus::New,
            time_in_force: TimeInForce::Day,
            trigger_price: None,
            trail_offset: None,
            trail_reference_price: None,
            graph_id: None,
            parent_order_id: None,
            order_role: crate::model::OrderRole::Standalone,
            filled_quantity: Decimal::ZERO,
            average_filled_price: None,
            created_at: 0,
            updated_at: 0,
            commission: Decimal::ZERO,
            tag: String::new(),
            reject_reason: String::new(),
            owner_strategy_id: None,
        }
    }

    fn create_context<'a>(
        portfolio: &'a Portfolio,
        instrument: &'a Instrument,
        instruments: &'a HashMap<String, Instrument>,
        active_orders: &'a [Order],
        current_prices: &'a HashMap<String, Decimal>,
        config: &'a crate::risk::RiskConfig,
    ) -> RiskCheckContext<'a> {
        RiskCheckContext {
            portfolio,
            instrument,
            instruments,
            active_orders,
            current_prices,
            current_time: 0,
            config,
        }
    }

    #[test]
    fn test_max_position_percent_rule() {
        let mut positions = HashMap::new();
        positions.insert("AAPL".to_string(), Decimal::from(100)); // 100 * 100 = 10,000

        let portfolio = Portfolio {
            cash: Decimal::from(90000), // Total Equity = 100,000
            positions: Arc::new(positions),
            available_positions: Arc::new(HashMap::new()),
        };

        let mut prices = HashMap::new();
        prices.insert("AAPL".to_string(), Decimal::from(100));

        let mut instruments = HashMap::new();
        let instr = Instrument {
            asset_type: AssetType::Stock,
            inner: InstrumentEnum::Stock(StockInstrument {
                symbol: "AAPL".to_string(),
                lot_size: Decimal::from(100),
                tick_size: Decimal::new(1, 2),
            }),
        };
        instruments.insert("AAPL".to_string(), instr.clone());

        let config = crate::risk::RiskConfig::new();

        let rule = MaxPositionPercentRule {
            max_pct: Decimal::from_str("0.15").unwrap(),
        }; // 15%

        // 1. Buy 200 AAPL (20,000 value). Total AAPL = 30,000. Equity = 100,000. Ratio = 30%. Fail.
        let order = create_test_order(
            "AAPL",
            OrderSide::Buy,
            Decimal::from(200),
            Decimal::from(100),
        );
        let ctx = create_context(&portfolio, &instr, &instruments, &[], &prices, &config);

        let res = rule.check(&order, &ctx);
        assert!(res.is_err());

        // 2. Buy 20 AAPL (2,000 value). Total AAPL = 12,000. Ratio = 12%. Pass.
        let order2 = create_test_order(
            "AAPL",
            OrderSide::Buy,
            Decimal::from(20),
            Decimal::from(100),
        );
        let res2 = rule.check(&order2, &ctx);
        assert!(res2.is_ok());
    }
}

/// Check max total leverage (Gross Exposure / Equity)
#[derive(Debug, Clone)]
pub struct MaxLeverageRule {
    pub max_leverage: Decimal,
}

impl RiskRule for MaxLeverageRule {
    fn name(&self) -> &'static str {
        "MaxLeverageRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        let equity = ctx
            .portfolio
            .calculate_equity(ctx.current_prices, ctx.instruments);

        if equity.is_zero() {
            return Ok(());
        }

        // Calculate current gross exposure
        let mut total_exposure = Decimal::ZERO;

        // 1. Existing positions
        for (symbol, quantity) in ctx.portfolio.positions.iter() {
            // Skip the symbol being traded (will handle with new quantity)
            if symbol == &order.symbol {
                continue;
            }

            if !quantity.is_zero()
                && let Some(price) = ctx.current_prices.get(symbol)
            {
                let mult = if let Some(inst) = ctx.instruments.get(symbol) {
                    inst.multiplier()
                } else {
                    Decimal::ONE
                };
                total_exposure += (quantity * price * mult).abs();
            }
        }

        // 2. New position for the traded symbol
        let current_pos_qty = ctx
            .portfolio
            .positions
            .get(&order.symbol)
            .copied()
            .unwrap_or(Decimal::ZERO);

        let new_qty = match order.side {
            OrderSide::Buy => current_pos_qty + order.quantity,
            OrderSide::Sell => current_pos_qty - order.quantity,
        };

        let price = if let Some(p) = order.price {
            p
        } else {
            *ctx.current_prices
                .get(&order.symbol)
                .unwrap_or(&Decimal::ZERO)
        };
        let multiplier = ctx.instrument.multiplier();

        total_exposure += (new_qty * price * multiplier).abs();

        // 3. Active orders (approximate)
        // Note: strictly speaking, we should include ALL active orders.
        // But for simplicity and performance, maybe we only check the current order's impact?
        // User requirement implies "Total Leverage Circuit Breaker", so we should be strict.
        // Let's iterate active orders.
        for o in ctx.active_orders {
            if o.symbol == order.symbol {
                // Skip orders for the same symbol as we are calculating the "resulting" position
                // Actually, this is complex. If I have a buy order pending, and I place another buy order.
                // The "new_qty" above only accounts for *filled* position + *current* order.
                // It does NOT account for *other pending orders*.
                // To be safe, we should add exposure from other pending orders.
                continue;
            }

            // For other symbols, add their potential exposure
            if let Some(p) = ctx.current_prices.get(&o.symbol) {
                let mult = if let Some(inst) = ctx.instruments.get(&o.symbol) {
                    inst.multiplier()
                } else {
                    Decimal::ONE
                };
                // Conservatively add full value of pending order
                total_exposure += (o.quantity * p * mult).abs();
            }
        }

        let leverage = total_exposure / equity;

        if leverage > self.max_leverage {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Total leverage {:.2} exceeds limit {:.2}",
                leverage, self.max_leverage
            )));
        }

        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

/// Check sector concentration
#[derive(Debug, Clone)]
pub struct SectorConcentrationRule {
    pub max_pct: Decimal,
    pub sector_map: HashMap<String, String>,
}

impl RiskRule for SectorConcentrationRule {
    fn name(&self) -> &'static str {
        "SectorConcentrationRule"
    }

    fn check(&self, order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        let equity = ctx
            .portfolio
            .calculate_equity(ctx.current_prices, ctx.instruments);

        if equity.is_zero() {
            return Ok(());
        }

        // Identify sector of current order
        let Some(target_sector) = self.sector_map.get(&order.symbol) else {
            // If symbol has no sector, skip check or fail?
            // Usually skip or classify as "Unknown".
            return Ok(());
        };

        let mut sector_exposure = Decimal::ZERO;

        // 1. Existing positions in the same sector
        for (symbol, quantity) in ctx.portfolio.positions.iter() {
            if symbol == &order.symbol {
                continue; // Handle with new qty
            }

            if let Some(s) = self.sector_map.get(symbol)
                && s == target_sector
                && let Some(price) = ctx.current_prices.get(symbol)
            {
                let mult = if let Some(inst) = ctx.instruments.get(symbol) {
                    inst.multiplier()
                } else {
                    Decimal::ONE
                };
                sector_exposure += (quantity * price * mult).abs();
            }
        }

        // 2. New position for the traded symbol
        let current_pos_qty = ctx
            .portfolio
            .positions
            .get(&order.symbol)
            .copied()
            .unwrap_or(Decimal::ZERO);

        let new_qty = match order.side {
            OrderSide::Buy => current_pos_qty + order.quantity,
            OrderSide::Sell => current_pos_qty - order.quantity,
        };

        let price = if let Some(p) = order.price {
            p
        } else {
            *ctx.current_prices
                .get(&order.symbol)
                .unwrap_or(&Decimal::ZERO)
        };
        let multiplier = ctx.instrument.multiplier();

        sector_exposure += (new_qty * price * multiplier).abs();

        let concentration = sector_exposure / equity;

        if concentration > self.max_pct {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Sector '{}' concentration {:.2}% exceeds limit {:.2}%",
                target_sector,
                concentration * Decimal::from(100),
                self.max_pct * Decimal::from(100)
            )));
        }

        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

#[derive(Debug, Clone)]
pub struct MaxDrawdownRule {
    pub limit: Decimal,
    peak_equity: Arc<Mutex<Option<Decimal>>>,
}

impl MaxDrawdownRule {
    pub fn new(limit: Decimal) -> Self {
        Self {
            limit,
            peak_equity: Arc::new(Mutex::new(None)),
        }
    }
}

impl RiskRule for MaxDrawdownRule {
    fn name(&self) -> &'static str {
        "MaxDrawdownRule"
    }

    fn check(&self, _order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        let equity = ctx
            .portfolio
            .calculate_equity(ctx.current_prices, ctx.instruments);

        if equity <= Decimal::ZERO {
            return Ok(());
        }

        let mut peak_guard = self.peak_equity.lock().unwrap();
        let peak = peak_guard.unwrap_or(equity);
        let new_peak = if equity > peak { equity } else { peak };
        *peak_guard = Some(new_peak);

        if new_peak <= Decimal::ZERO {
            return Ok(());
        }

        let drawdown = (new_peak - equity) / new_peak;
        if drawdown > self.limit {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Max drawdown {:.2}% exceeds limit {:.2}%",
                drawdown * Decimal::from(100),
                self.limit * Decimal::from(100),
            )));
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

#[derive(Debug, Clone)]
struct DailyLossState {
    day_key: i64,
    start_equity: Decimal,
}

#[derive(Debug, Clone)]
pub struct MaxDailyLossRule {
    pub limit: Decimal,
    state: Arc<Mutex<Option<DailyLossState>>>,
}

impl MaxDailyLossRule {
    pub fn new(limit: Decimal) -> Self {
        Self {
            limit,
            state: Arc::new(Mutex::new(None)),
        }
    }
}

impl RiskRule for MaxDailyLossRule {
    fn name(&self) -> &'static str {
        "MaxDailyLossRule"
    }

    fn check(&self, _order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        let equity = ctx
            .portfolio
            .calculate_equity(ctx.current_prices, ctx.instruments);
        if equity <= Decimal::ZERO {
            return Ok(());
        }

        let day_key = ctx.current_time / 86_400_000_000_000;
        let mut state_guard = self.state.lock().unwrap();
        let state = state_guard.get_or_insert(DailyLossState {
            day_key,
            start_equity: equity,
        });

        if state.day_key != day_key {
            state.day_key = day_key;
            state.start_equity = equity;
        }

        if state.start_equity <= Decimal::ZERO {
            return Ok(());
        }

        let daily_loss = (state.start_equity - equity) / state.start_equity;
        if daily_loss > self.limit {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Daily loss {:.2}% exceeds limit {:.2}%",
                daily_loss * Decimal::from(100),
                self.limit * Decimal::from(100),
            )));
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}

#[derive(Debug, Clone)]
pub struct StopLossRule {
    pub threshold: Decimal,
    initial_equity: Arc<Mutex<Option<Decimal>>>,
}

impl StopLossRule {
    pub fn new(threshold: Decimal) -> Self {
        Self {
            threshold,
            initial_equity: Arc::new(Mutex::new(None)),
        }
    }
}

impl RiskRule for StopLossRule {
    fn name(&self) -> &'static str {
        "StopLossRule"
    }

    fn check(&self, _order: &Order, ctx: &RiskCheckContext) -> Result<(), AkQuantError> {
        let equity = ctx
            .portfolio
            .calculate_equity(ctx.current_prices, ctx.instruments);
        if equity <= Decimal::ZERO {
            return Ok(());
        }

        let mut init_guard = self.initial_equity.lock().unwrap();
        let base = *init_guard.get_or_insert(equity);
        let trigger_equity = base * self.threshold;

        if equity < trigger_equity {
            return Err(AkQuantError::OrderError(format!(
                "Risk: Equity {equity:.4} below stop-loss threshold {trigger_equity:.4}",
            )));
        }
        Ok(())
    }

    fn clone_box(&self) -> Box<dyn RiskRule> {
        Box::new(self.clone())
    }
}
