use numpy::PyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

#[path = "trend_directional.rs"]
mod trend_directional;
#[path = "trend_oscillators.rs"]
mod trend_oscillators;
#[path = "trend_regression.rs"]
mod trend_regression;

pub use trend_directional::{ADX, ADXR, DX, MINUS_DI, PLUS_DI};
pub use trend_oscillators::{AROON, AROONOSC, SAR, STOCH, ULTOSC};
pub use trend_regression::{
    BETA, CORREL, COVAR, LINEARREG, LINEARREG_ANGLE, LINEARREG_INTERCEPT, LINEARREG_R2,
    LINEARREG_SLOPE, TSF,
};

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CCI {
    period: usize,
    c: f64,
    typical_prices: VecDeque<f64>,
    sum: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl CCI {
    #[new]
    pub fn new(period: usize, c: f64) -> Self {
        CCI {
            period,
            c,
            typical_prices: VecDeque::with_capacity(period),
            sum: 0.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let typical_price = (high + low + close) / 3.0;
        self.typical_prices.push_back(typical_price);
        self.sum += typical_price;
        if self.typical_prices.len() > self.period
            && let Some(removed) = self.typical_prices.pop_front()
        {
            self.sum -= removed;
        }
        if self.typical_prices.len() < self.period {
            self.current_value = None;
            return None;
        }
        let sma = self.sum / self.period as f64;
        let mean_deviation = self
            .typical_prices
            .iter()
            .map(|x| (x - sma).abs())
            .sum::<f64>()
            / self.period as f64;
        if mean_deviation <= f64::EPSILON || self.c <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some((typical_price - sma) / (self.c * mean_deviation));
        }
        self.current_value
    }

    pub fn update_many_hlc<'py>(
        &mut self,
        py: Python<'py>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<f64>>> {
        if highs.len() != lows.len() || highs.len() != closes.len() {
            return Err(PyValueError::new_err("highs/lows/closes length mismatch"));
        }
        let mut out = Vec::with_capacity(highs.len());
        for (high, (low, close)) in highs
            .into_iter()
            .zip(lows.into_iter().zip(closes.into_iter()))
        {
            out.push(self.update(high, low, close).unwrap_or(f64::NAN));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<CCI>()?;
    trend_directional::register_classes(m)?;
    trend_oscillators::register_classes(m)?;
    trend_regression::register_classes(m)?;
    Ok(())
}
