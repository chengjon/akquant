use crate::model::Instrument;
use rust_decimal::Decimal;

fn checked_mul_or_cap(lhs: Decimal, rhs: Decimal) -> Decimal {
    lhs.checked_mul(rhs).unwrap_or(Decimal::MAX)
}

fn checked_add_or_cap(lhs: Decimal, rhs: Decimal) -> Decimal {
    lhs.checked_add(rhs).unwrap_or(Decimal::MAX)
}

/// Trait for calculating margin requirements for a position.
pub trait MarginCalculator: Send + Sync {
    /// Calculate the margin required for a position.
    ///
    /// # Arguments
    /// * `quantity` - The position quantity (positive for long, negative for short).
    /// * `price` - The current price of the instrument.
    /// * `instrument` - The instrument details.
    /// * `underlying_price` - The price of the underlying asset (optional, for derivatives).
    ///
    /// # Returns
    /// The required margin amount (always non-negative).
    fn calculate_margin(
        &self,
        quantity: Decimal,
        price: Decimal,
        instrument: &Instrument,
        underlying_price: Option<Decimal>,
    ) -> Decimal;
}

/// Default calculator for linear instruments (Stocks, Funds).
/// Margin = Quantity * Price * Multiplier * MarginRatio
#[derive(Debug, Clone, Copy, Default)]
pub struct LinearMarginCalculator;

impl MarginCalculator for LinearMarginCalculator {
    fn calculate_margin(
        &self,
        quantity: Decimal,
        price: Decimal,
        instrument: &Instrument,
        _underlying_price: Option<Decimal>,
    ) -> Decimal {
        let multiplier = instrument.multiplier().abs();
        let margin_ratio = instrument.margin_ratio().abs();
        let notional = checked_mul_or_cap(quantity.abs(), price.abs());
        let gross = checked_mul_or_cap(notional, multiplier);
        checked_mul_or_cap(gross, margin_ratio)
    }
}

/// Calculator for Futures.
/// Same as Linear, but conceptually distinct for potential future complexity (e.g. spread margin).
#[derive(Debug, Clone, Copy, Default)]
pub struct FuturesMarginCalculator;

impl MarginCalculator for FuturesMarginCalculator {
    fn calculate_margin(
        &self,
        quantity: Decimal,
        price: Decimal,
        instrument: &Instrument,
        _underlying_price: Option<Decimal>,
    ) -> Decimal {
        let multiplier = instrument.multiplier().abs();
        let margin_ratio = instrument.margin_ratio().abs();
        let notional = checked_mul_or_cap(quantity.abs(), price.abs());
        let gross = checked_mul_or_cap(notional, multiplier);
        checked_mul_or_cap(gross, margin_ratio)
    }
}

/// Calculator for Options.
/// Handles Long (usually 0 margin) and Short (complex margin) positions.
#[derive(Debug, Clone, Copy, Default)]
pub struct OptionMarginCalculator;

impl MarginCalculator for OptionMarginCalculator {
    fn calculate_margin(
        &self,
        quantity: Decimal,
        price: Decimal,
        instrument: &Instrument,
        underlying_price: Option<Decimal>,
    ) -> Decimal {
        use rust_decimal::prelude::*;

        if quantity > Decimal::ZERO {
            Decimal::ZERO
        } else {
            let abs_qty = quantity.abs();
            let underlying_price = underlying_price.unwrap_or(Decimal::ZERO).abs();
            let multiplier = instrument.multiplier().abs();
            let margin_ratio = instrument.margin_ratio().abs();
            let option_price = price.abs();

            let margin_per_unit = if underlying_price > Decimal::ZERO {
                checked_add_or_cap(
                    option_price,
                    checked_mul_or_cap(underlying_price, margin_ratio),
                )
            } else {
                checked_mul_or_cap(option_price, checked_add_or_cap(Decimal::ONE, margin_ratio))
            };

            checked_mul_or_cap(checked_mul_or_cap(margin_per_unit, multiplier), abs_qty)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::instrument::{FuturesInstrument, InstrumentEnum, OptionInstrument};
    use crate::model::types::{AssetType, OptionType};

    #[test]
    fn linear_margin_caps_on_overflow() {
        let instrument = Instrument {
            asset_type: AssetType::Futures,
            inner: InstrumentEnum::Futures(FuturesInstrument {
                symbol: "FUT".to_string(),
                multiplier: Decimal::MAX,
                margin_ratio: Decimal::MAX,
                tick_size: Decimal::ONE,
                expiry_date: None,
                settlement_type: None,
                settlement_price: None,
            }),
        };

        let calc = LinearMarginCalculator;
        let margin = calc.calculate_margin(Decimal::MAX, Decimal::MAX, &instrument, None);
        assert_eq!(margin, Decimal::MAX);
    }

    #[test]
    fn option_margin_caps_on_overflow() {
        let instrument = Instrument {
            asset_type: AssetType::Option,
            inner: InstrumentEnum::Option(OptionInstrument {
                symbol: "OPT".to_string(),
                multiplier: Decimal::MAX,
                margin_ratio: Decimal::MAX,
                tick_size: Decimal::ONE,
                option_type: OptionType::Call,
                strike_price: Decimal::ZERO,
                expiry_date: 0,
                underlying_symbol: "UL".to_string(),
                settlement_type: None,
            }),
        };

        let calc = OptionMarginCalculator;
        let margin = calc.calculate_margin(
            Decimal::NEGATIVE_ONE,
            Decimal::MAX,
            &instrument,
            Some(Decimal::MAX),
        );
        assert_eq!(margin, Decimal::MAX);
    }
}
