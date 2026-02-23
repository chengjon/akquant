use crate::event::Event;
use crate::execution::common::CommonMatcher;
use crate::execution::matcher::ExecutionMatcher;
use crate::execution::slippage::SlippageModel;
use crate::model::{ExecutionMode, Instrument, Order};
use rust_decimal::Decimal;

pub struct StockMatcher;

impl ExecutionMatcher for StockMatcher {
    fn match_order(
        &self,
        order: &mut Order,
        event: &Event,
        instrument: &Instrument,
        execution_mode: ExecutionMode,
        slippage: &dyn SlippageModel,
        volume_limit_pct: Decimal,
        bar_index: usize,
    ) -> Option<Event> {
        // Stock: Check Lot Size for Buy orders (e.g. A-Share 100 shares)
        CommonMatcher::match_order(
            order,
            event,
            instrument,
            execution_mode,
            slippage,
            volume_limit_pct,
            bar_index,
            true, // check_lot_size = true for Stock
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{InstrumentEnum, OrderSide, OrderType, OrderStatus, TimeInForce, StockInstrument};
    use rust_decimal_macros::dec;

    fn create_order(side: OrderSide, type_: OrderType, price: Option<Decimal>, stop: Option<Decimal>) -> Order {
        Order {
            id: "1".to_string(),
            symbol: "AAPL".to_string(),
            side,
            order_type: type_,
            quantity: dec!(100),
            price,
            trigger_price: stop,
            status: OrderStatus::New,
            filled_quantity: Decimal::ZERO,
            average_filled_price: None,
            time_in_force: TimeInForce::Day,
            created_at: 0,
            updated_at: 0,
            commission: Decimal::ZERO,
            tag: "".to_string(),
            reject_reason: "".to_string(),
        }
    }

    fn create_instrument() -> Instrument {
        Instrument {
            asset_type: crate::model::AssetType::Stock,
            inner: InstrumentEnum::Stock(StockInstrument {
                symbol: "AAPL".to_string(),
                lot_size: dec!(100),
                tick_size: dec!(0.01),
            }),
        }
    }

    #[test]
    fn test_buy_stop_in_bar() {
        let matcher = StockMatcher;
        let mut order = create_order(OrderSide::Buy, OrderType::StopMarket, None, Some(dec!(105)));
        let instr = create_instrument();

        let bar = crate::model::Bar {
            timestamp: 100,
            symbol: "AAPL".to_string(),
            open: dec!(100),
            high: dec!(110),
            low: dec!(90),
            close: dec!(108),
            volume: dec!(1000),
            extra: Default::default(),
        };

        let event = Event::Bar(bar);
        let res = matcher.match_order(
            &mut order,
            &event,
            &instr,
            ExecutionMode::NextOpen,
            &crate::execution::slippage::ZeroSlippage,
            Decimal::ZERO,
            0
        );

        assert!(res.is_some());
        if let Some(Event::ExecutionReport(o, Some(t))) = res {
            assert_eq!(o.status, OrderStatus::Filled);
            assert_eq!(t.price, dec!(105)); // Executed at Trigger
        } else {
            panic!("Unexpected result");
        }
    }

    #[test]
    fn test_buy_limit_check_low() {
        let matcher = StockMatcher;
        let mut order = create_order(OrderSide::Buy, OrderType::Limit, Some(dec!(90)), None);
        let instr = create_instrument();

        // Bar Low is 95. Limit is 90. Should NOT fill.
        let bar = crate::model::Bar {
            timestamp: 100,
            symbol: "AAPL".to_string(),
            open: dec!(100),
            high: dec!(110),
            low: dec!(95),
            close: dec!(98),
            volume: dec!(1000),
            extra: Default::default(),
        };

        let event = Event::Bar(bar);
        let res = matcher.match_order(
            &mut order,
            &event,
            &instr,
            ExecutionMode::NextOpen,
            &crate::execution::slippage::ZeroSlippage,
            Decimal::ZERO,
            0
        );

        assert!(res.is_none());
    }
}
