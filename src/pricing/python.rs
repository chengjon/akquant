//! Python bindings for option pricing and Greeks.

use pyo3::prelude::*;

use super::bsm;
use crate::model::types::OptionType;

/// Result of option Greeks calculation.
#[pyclass(get_all)]
#[derive(Debug, Clone, Copy)]
pub struct PyGreeksResult {
    pub delta: f64,
    pub gamma: f64,
    pub theta: f64,
    pub vega: f64,
    pub rho: f64,
    pub price: f64,
}

/// Calculate option Greeks via Black-Scholes-Merton model.
///
/// Parameters:
/// - underlying_price: Current price of the underlying asset
/// - strike: Strike price of the option
/// - time_to_expiry_years: Time to expiration in years
/// - risk_free_rate: Annualized risk-free rate (e.g. 0.02 for 2%)
/// - volatility: Annualized volatility (e.g. 0.25 for 25%)
/// - option_type: "CALL" or "PUT"
#[pyfunction]
#[pyo3(signature = (underlying_price, strike, time_to_expiry_years, risk_free_rate, volatility, option_type))]
pub fn calculate_option_greeks(
    underlying_price: f64,
    strike: f64,
    time_to_expiry_years: f64,
    risk_free_rate: f64,
    volatility: f64,
    option_type: &str,
) -> PyResult<PyGreeksResult> {
    let ot = parse_option_type(option_type)?;
    let g = bsm::calculate_greeks(
        underlying_price,
        strike,
        time_to_expiry_years,
        risk_free_rate,
        volatility,
        ot,
    );
    Ok(PyGreeksResult {
        delta: g.delta,
        gamma: g.gamma,
        theta: g.theta,
        vega: g.vega,
        rho: g.rho,
        price: g.price,
    })
}

/// Calculate implied volatility via Newton-Raphson iteration.
///
/// Parameters:
/// - market_price: Observed market price of the option
/// - underlying_price: Current price of the underlying asset
/// - strike: Strike price of the option
/// - time_to_expiry_years: Time to expiration in years
/// - risk_free_rate: Annualized risk-free rate (e.g. 0.02 for 2%)
/// - option_type: "CALL" or "PUT"
/// - initial_guess: Optional starting volatility (default 0.2)
/// - max_iterations: Optional max iterations (default 100)
/// - tolerance: Optional convergence tolerance (default 1e-8)
///
/// Returns implied volatility as a float, or None if convergence fails.
#[pyfunction]
#[pyo3(signature = (market_price, underlying_price, strike, time_to_expiry_years, risk_free_rate, option_type, initial_guess=None, max_iterations=None, tolerance=None))]
pub fn calculate_implied_volatility(
    market_price: f64,
    underlying_price: f64,
    strike: f64,
    time_to_expiry_years: f64,
    risk_free_rate: f64,
    option_type: &str,
    initial_guess: Option<f64>,
    max_iterations: Option<u32>,
    tolerance: Option<f64>,
) -> PyResult<Option<f64>> {
    let ot = parse_option_type(option_type)?;
    Ok(bsm::implied_volatility(
        market_price,
        underlying_price,
        strike,
        time_to_expiry_years,
        risk_free_rate,
        ot,
        initial_guess,
        max_iterations,
        tolerance,
    ))
}

fn parse_option_type(s: &str) -> PyResult<OptionType> {
    match s.to_uppercase().as_str() {
        "CALL" => Ok(OptionType::Call),
        "PUT" => Ok(OptionType::Put),
        _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
            "option_type must be 'CALL' or 'PUT', got '{}'",
            s
        ))),
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyGreeksResult>()?;
    m.add_function(wrap_pyfunction!(calculate_option_greeks, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_implied_volatility, m)?)?;
    Ok(())
}
