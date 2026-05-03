//! Black-Scholes-Merton pricing and Greeks for European options.

use crate::model::types::OptionType;
use chrono::{Datelike, NaiveDate, TimeZone, Utc};

/// Greeks result for a single option contract.
#[derive(Debug, Clone, Copy, Default)]
pub struct Greeks {
    pub delta: f64,
    pub gamma: f64,
    pub theta: f64,
    pub vega: f64,
    pub rho: f64,
    pub price: f64,
}

/// Standard normal PDF.
pub fn normal_pdf(x: f64) -> f64 {
    0.3989422804014327 * (-0.5 * x * x).exp()
}

/// Standard normal CDF (Abramowitz-Stegun approximation 26.2.17).
/// Maximum absolute error ~7.5e-8.
pub fn normal_cdf(x: f64) -> f64 {
    const A1: f64 = 0.319381530;
    const A2: f64 = -0.356563782;
    const A3: f64 = 1.781477937;
    const A4: f64 = -1.821255978;
    const A5: f64 = 1.330274429;

    if x < -8.0 {
        return 0.0;
    }
    if x > 8.0 {
        return 1.0;
    }

    let sign = if x < 0.0 { -1.0 } else { 1.0 };
    let ax = x.abs();
    let t = 1.0 / (1.0 + 0.2316419 * ax);
    let d = normal_pdf(ax);
    let poly = t * (A1 + t * (A2 + t * (A3 + t * (A4 + t * A5))));
    let y = 1.0 - d * poly;

    if sign < 0.0 {
        1.0 - y
    } else {
        y
    }
}

/// European option price via Black-Scholes-Merton.
pub fn bsm_price(s: f64, k: f64, t: f64, r: f64, sigma: f64, option_type: OptionType) -> f64 {
    if t <= 0.0 {
        return intrinsic_value(s, k, option_type);
    }
    if sigma <= 0.0 {
        let intrinsic = intrinsic_value(s, k, option_type);
        return intrinsic * (-r * t).exp();
    }

    let (d1, d2) = calc_d1_d2(s, k, t, r, sigma);
    let nd1 = normal_cdf(d1);
    let nd2 = normal_cdf(d2);
    let nd1_neg = normal_cdf(-d1);
    let nd2_neg = normal_cdf(-d2);
    let discount = (-r * t).exp();

    match option_type {
        OptionType::Call => s * nd1 - k * discount * nd2,
        OptionType::Put => k * discount * nd2_neg - s * nd1_neg,
    }
}

/// Calculate all Greeks for a European option.
pub fn calculate_greeks(
    s: f64,
    k: f64,
    t: f64,
    r: f64,
    sigma: f64,
    option_type: OptionType,
) -> Greeks {
    if t <= 0.0 || sigma <= 0.0 {
        return greeks_at_expiry(s, k, option_type);
    }

    let sqrt_t = t.sqrt();
    let (d1, d2) = calc_d1_d2(s, k, t, r, sigma);
    let nd1 = normal_cdf(d1);
    let nd2 = normal_cdf(d2);
    let pdf_d1 = normal_pdf(d1);
    let discount = (-r * t).exp();

    let gamma = pdf_d1 / (s * sigma * sqrt_t);
    let vega = s * pdf_d1 * sqrt_t; // per 1.0 vol change
    let theta_common = -(s * pdf_d1 * sigma) / (2.0 * sqrt_t);

    let (delta, theta, rho) = match option_type {
        OptionType::Call => (
            nd1,
            theta_common - r * k * discount * nd2,
            k * t * discount * nd2 * 0.01,
        ),
        OptionType::Put => (
            nd1 - 1.0,
            theta_common + r * k * discount * normal_cdf(-d2),
            -k * t * discount * normal_cdf(-d2) * 0.01,
        ),
    };

    let price = bsm_price(s, k, t, r, sigma, option_type);

    Greeks {
        delta,
        gamma,
        theta: theta / 365.0, // convert to per-day
        vega: vega / 100.0,   // convert to per-percent-point
        rho,
        price,
    }
}

/// Convert expiry YYYYMMDD + current nanosecond timestamp to fractional years.
pub fn time_to_expiry(expiry_yyyymmdd: u32, current_time_nanos: i64) -> f64 {
    let year = (expiry_yyyymmdd / 10000) as i32;
    let month = ((expiry_yyyymmdd % 10000) / 100) as u32;
    let day = (expiry_yyyymmdd % 100) as u32;

    let expiry_date = match NaiveDate::from_ymd_opt(year, month, day) {
        Some(d) => d,
        None => return 0.0,
    };

    let current_secs = current_time_nanos / 1_000_000_000;
    let current_dt = Utc.timestamp_opt(current_secs, 0).single().unwrap_or_else(|| {
        Utc.timestamp_opt(0, 0).single().unwrap()
    });
    let current_date = current_dt.date_naive();

    let days_diff = (expiry_date - current_date).num_days();
    if days_diff <= 0 {
        return 0.0;
    }

    days_diff as f64 / 365.25
}

fn intrinsic_value(s: f64, k: f64, option_type: OptionType) -> f64 {
    match option_type {
        OptionType::Call => (s - k).max(0.0),
        OptionType::Put => (k - s).max(0.0),
    }
}

fn calc_d1_d2(s: f64, k: f64, t: f64, r: f64, sigma: f64) -> (f64, f64) {
    let sqrt_t = t.sqrt();
    let d1 = ((s / k).ln() + (r + 0.5 * sigma * sigma) * t) / (sigma * sqrt_t);
    let d2 = d1 - sigma * sqrt_t;
    (d1, d2)
}

/// Implied volatility via Newton-Raphson.
/// Returns None if iteration fails to converge.
pub fn implied_volatility(
    market_price: f64,
    s: f64,
    k: f64,
    t: f64,
    r: f64,
    option_type: OptionType,
    initial_guess: Option<f64>,
    max_iterations: Option<u32>,
    tolerance: Option<f64>,
) -> Option<f64> {
    if t <= 0.0 {
        return None;
    }

    let mut sigma = initial_guess.unwrap_or(0.2);
    let max_iter = max_iterations.unwrap_or(100);
    let tol = tolerance.unwrap_or(1e-8);

    for _ in 0..max_iter {
        let price = bsm_price(s, k, t, r, sigma, option_type);
        let diff = price - market_price;
        if diff.abs() < tol {
            return Some(sigma);
        }
        let (_, d1) = calc_d1_d2(s, k, t, r, sigma);
        let vega = s * normal_pdf(d1) * t.sqrt();
        if vega < 1e-20 {
            return None;
        }
        sigma -= diff / vega;
        if sigma <= 0.0 {
            sigma = 0.001;
        }
    }

    None
}

fn greeks_at_expiry(s: f64, k: f64, option_type: OptionType) -> Greeks {
    let iv = intrinsic_value(s, k, option_type);
    let delta = match option_type {
        OptionType::Call => if s > k { 1.0 } else { 0.0 },
        OptionType::Put => if s < k { -1.0 } else { 0.0 },
    };
    Greeks {
        delta,
        gamma: 0.0,
        theta: 0.0,
        vega: 0.0,
        rho: 0.0,
        price: iv,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normal_cdf_known_values() {
        assert!((normal_cdf(0.0) - 0.5).abs() < 1e-7);
        assert!((normal_cdf(1.96) - 0.975).abs() < 0.001);
        assert!((normal_cdf(-1.96) - 0.025).abs() < 0.001);
    }

    #[test]
    fn test_bsm_put_call_parity() {
        let s = 100.0;
        let k = 100.0;
        let t = 1.0;
        let r = 0.02;
        let sigma = 0.2;
        let call = bsm_price(s, k, t, r, sigma, OptionType::Call);
        let put = bsm_price(s, k, t, r, sigma, OptionType::Put);
        let parity = call - put - (s - k * (-r * t).exp());
        assert!(parity.abs() < 1e-10, "Put-call parity violated: {}", parity);
    }

    #[test]
    fn test_greeks_atm_call_delta() {
        let g = calculate_greeks(100.0, 100.0, 0.25, 0.02, 0.2, OptionType::Call);
        assert!(g.delta > 0.45 && g.delta < 0.55, "ATM call delta should be ~0.5, got {}", g.delta);
        assert!(g.gamma > 0.0, "Gamma should be positive");
    }

    #[test]
    fn test_greeks_zero_expiry() {
        let g_itm = calculate_greeks(110.0, 100.0, 0.0, 0.02, 0.2, OptionType::Call);
        assert!((g_itm.delta - 1.0).abs() < 1e-10);
        let g_otm = calculate_greeks(90.0, 100.0, 0.0, 0.02, 0.2, OptionType::Call);
        assert!(g_otm.delta.abs() < 1e-10);
    }

    #[test]
    fn test_time_to_expiry_conversion() {
        // expiry 20250101, current = 20240101 => ~1 year
        let current_nanos = chrono::NaiveDate::from_ymd_opt(2024, 1, 1).unwrap()
            .and_hms_opt(0, 0, 0).unwrap()
            .and_utc().timestamp() as i64 * 1_000_000_000;
        let t = time_to_expiry(20250101, current_nanos);
        assert!(t > 0.99 && t < 1.01, "Expected ~1 year, got {}", t);
    }

    #[test]
    fn test_iv_atm_call() {
        // Roundtrip: price with sigma=0.25, then solve for IV
        let s = 100.0;
        let k = 100.0;
        let t = 0.25;
        let r = 0.02;
        let sigma = 0.25;
        let price = bsm_price(s, k, t, r, sigma, OptionType::Call);
        let iv = implied_volatility(price, s, k, t, r, OptionType::Call, None, None, None);
        assert!(iv.is_some(), "IV should converge for ATM call");
        assert!(
            (iv.unwrap() - sigma).abs() < 1e-6,
            "IV roundtrip failed: expected {}, got {}",
            sigma,
            iv.unwrap()
        );
    }

    #[test]
    fn test_iv_deep_itm() {
        // Deep ITM call: S=150, K=100
        let s = 150.0;
        let k = 100.0;
        let t = 1.0;
        let r = 0.02;
        let sigma = 0.3;
        let price = bsm_price(s, k, t, r, sigma, OptionType::Call);
        let iv = implied_volatility(price, s, k, t, r, OptionType::Call, None, None, None);
        assert!(iv.is_some(), "IV should converge for deep ITM");
        assert!(
            (iv.unwrap() - sigma).abs() < 1e-6,
            "Deep ITM IV roundtrip failed: expected {}, got {}",
            sigma,
            iv.unwrap()
        );
    }

    #[test]
    fn test_iv_zero_expiry() {
        let price = 5.0;
        let iv = implied_volatility(price, 100.0, 100.0, 0.0, 0.02, OptionType::Call, None, None, None);
        assert!(iv.is_none(), "T=0 should return None");
    }
}
