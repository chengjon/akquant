use crate::model::Instrument;
use crate::model::types::{AssetType, OptionType};
use crate::portfolio::Portfolio;
use chrono::{Datelike, NaiveDate};
use rust_decimal::Decimal;
use std::collections::HashMap;

use super::handler::{SettlementHandler, SettlementTask};

/// Handles Option Expiration and Settlement
#[derive(Debug, Clone, Default)]
pub struct OptionSettlementHandler;

impl SettlementHandler for OptionSettlementHandler {
    fn check_settlement(
        &self,
        date: NaiveDate,
        portfolio: &Portfolio,
        instruments: &HashMap<String, Instrument>,
        last_prices: &HashMap<String, Decimal>,
    ) -> Vec<SettlementTask> {
        let mut tasks = Vec::new();

        // Convert NaiveDate to YYYYMMDD u32 for comparison
        let (_, year_ce) = date.year_ce();
        let current_date_int = year_ce * 10000
            + date.month() * 100
            + date.day();

        for (symbol, qty) in portfolio.positions.iter() {
            if qty.is_zero() {
                continue;
            }

            if let Some(instr) = instruments.get(symbol)
                && instr.asset_type == AssetType::Option
                    && let Some(expiry_date_int) = instr.expiry_date()
                        && current_date_int >= expiry_date_int {
                            // Expired
                            // Calculate Payoff
                            let strike = instr.strike_price().unwrap_or(Decimal::ZERO);
                            let underlying_price = if let Some(us) = instr.underlying_symbol() {
                                last_prices.get(us.as_str()).copied().unwrap_or(Decimal::ZERO)
                            } else {
                                Decimal::ZERO
                            };

                            let mut payoff_per_unit = Decimal::ZERO;
                            if underlying_price > Decimal::ZERO {
                                match instr.option_type() {
                                    Some(OptionType::Call) => {
                                        if underlying_price > strike {
                                            payoff_per_unit = underlying_price - strike;
                                        }
                                    }
                                    Some(OptionType::Put) => {
                                        if strike > underlying_price {
                                            payoff_per_unit = strike - underlying_price;
                                        }
                                    }
                                    None => {}
                                }
                            }

                            // Total Cash Flow
                            // Long (Qty > 0): Receives Payoff * Multiplier * Qty
                            // Short (Qty < 0): Pays Payoff * Multiplier * Abs(Qty) -> Qty * Payoff * Multiplier
                            let cash_flow = *qty * payoff_per_unit * instr.multiplier();

                            tasks.push(SettlementTask {
                                symbol: symbol.clone(),
                                quantity: *qty, // Full position quantity to close
                                cash_flow,
                                description: format!("Option Expiry for {symbol}"),
                            });
                        }
        }

        tasks
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::instrument::{InstrumentEnum, OptionInstrument};
    use crate::model::types::{AssetType, OptionType};
    use chrono::NaiveDate;
    use rust_decimal_macros::dec;
    use std::sync::Arc;

    fn create_test_option(symbol: &str, expiry_date: u32, option_type: OptionType, strike: Decimal) -> Instrument {
        Instrument {
            asset_type: AssetType::Option,
            inner: InstrumentEnum::Option(OptionInstrument {
                symbol: symbol.to_string(),
                multiplier: dec!(100),
                tick_size: dec!(0.01),
                option_type,
                strike_price: strike,
                expiry_date,
                underlying_symbol: "UNDERLYING".to_string(),
                settlement_type: None,
            }),
        }
    }

    #[test]
    fn test_option_expiry_call_in_the_money() {
        let handler = OptionSettlementHandler;
        let expiry_date = NaiveDate::from_ymd_opt(2024, 1, 1).unwrap();

        let mut positions = HashMap::new();
        positions.insert("OPT_CALL".to_string(), dec!(10)); // 10 Long Calls

        let portfolio = Portfolio {
            cash: dec!(100000),
            positions: Arc::new(positions),
            available_positions: Arc::new(HashMap::new()),
        };

        let mut instruments = HashMap::new();
        instruments.insert(
            "OPT_CALL".to_string(),
            create_test_option("OPT_CALL", 20240101, OptionType::Call, dec!(100)),
        );

        let mut last_prices = HashMap::new();
        last_prices.insert("UNDERLYING".to_string(), dec!(110)); // Underlying > Strike (ITM)

        let tasks = handler.check_settlement(
            expiry_date,
            &portfolio,
            &instruments,
            &last_prices,
        );

        assert_eq!(tasks.len(), 1);
        let task = &tasks[0];
        assert_eq!(task.symbol, "OPT_CALL");
        assert_eq!(task.quantity, dec!(10));

        // Payoff = (110 - 100) = 10
        // Cash Flow = 10 * 100 (multiplier) * 10 (qty) = 10000
        assert_eq!(task.cash_flow, dec!(10000));
    }

    #[test]
    fn test_option_expiry_out_of_the_money() {
        let handler = OptionSettlementHandler;
        let expiry_date = NaiveDate::from_ymd_opt(2024, 1, 1).unwrap();

        let mut positions = HashMap::new();
        positions.insert("OPT_PUT".to_string(), dec!(1));

        let portfolio = Portfolio {
            cash: dec!(10000),
            positions: Arc::new(positions),
            available_positions: Arc::new(HashMap::new()),
        };

        let mut instruments = HashMap::new();
        instruments.insert(
            "OPT_PUT".to_string(),
            create_test_option("OPT_PUT", 20240101, OptionType::Put, dec!(100)),
        );

        let mut last_prices = HashMap::new();
        last_prices.insert("UNDERLYING".to_string(), dec!(110)); // Underlying > Strike (OTM for Put)

        let tasks = handler.check_settlement(
            expiry_date,
            &portfolio,
            &instruments,
            &last_prices,
        );

        // Should not generate tasks if OTM?
        // Wait, check_settlement checks if expiry_date >= current_date.
        // If expired, it generates task regardless of payoff?
        // Logic: if current_date >= expiry_date -> calculate payoff.
        // If payoff > 0, cash_flow > 0.
        // But task is generated anyway?
        // Let's check logic:
        // if current_date_int >= expiry_date_int {
        //     // ... calc payoff ...
        //     tasks.push(SettlementTask { ... })
        // }
        // So yes, it generates task to close position (cash flow 0).

        assert_eq!(tasks.len(), 1);
        let task = &tasks[0];
        assert_eq!(task.cash_flow, dec!(0));
    }
}
