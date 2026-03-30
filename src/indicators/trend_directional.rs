use numpy::PyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ADX {
    period: usize,
    prev_high: Option<f64>,
    prev_low: Option<f64>,
    prev_close: Option<f64>,
    smoothed_tr: f64,
    smoothed_plus_dm: f64,
    smoothed_minus_dm: f64,
    trend_count: usize,
    dx_values: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ADX {
    #[new]
    pub fn new(period: usize) -> Self {
        ADX {
            period,
            prev_high: None,
            prev_low: None,
            prev_close: None,
            smoothed_tr: 0.0,
            smoothed_plus_dm: 0.0,
            smoothed_minus_dm: 0.0,
            trend_count: 0,
            dx_values: VecDeque::with_capacity(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let Some(prev_high) = self.prev_high else {
            self.prev_high = Some(high);
            self.prev_low = Some(low);
            self.prev_close = Some(close);
            return None;
        };
        let prev_low = self.prev_low.unwrap_or(low);
        let prev_close = self.prev_close.unwrap_or(close);

        let up_move = high - prev_high;
        let down_move = prev_low - low;
        let plus_dm = if up_move > down_move && up_move > 0.0 {
            up_move
        } else {
            0.0
        };
        let minus_dm = if down_move > up_move && down_move > 0.0 {
            down_move
        } else {
            0.0
        };

        let tr = (high - low)
            .max((high - prev_close).abs())
            .max((low - prev_close).abs());

        self.prev_high = Some(high);
        self.prev_low = Some(low);
        self.prev_close = Some(close);

        if self.trend_count < self.period {
            self.smoothed_tr += tr;
            self.smoothed_plus_dm += plus_dm;
            self.smoothed_minus_dm += minus_dm;
            self.trend_count += 1;

            if self.trend_count < self.period {
                return None;
            }
        } else {
            self.smoothed_tr = self.smoothed_tr - (self.smoothed_tr / self.period as f64) + tr;
            self.smoothed_plus_dm =
                self.smoothed_plus_dm - (self.smoothed_plus_dm / self.period as f64) + plus_dm;
            self.smoothed_minus_dm =
                self.smoothed_minus_dm - (self.smoothed_minus_dm / self.period as f64) + minus_dm;
        }

        if self.smoothed_tr <= f64::EPSILON {
            self.current_value = Some(0.0);
            return self.current_value;
        }

        let plus_di = 100.0 * self.smoothed_plus_dm / self.smoothed_tr;
        let minus_di = 100.0 * self.smoothed_minus_dm / self.smoothed_tr;
        let di_sum = plus_di + minus_di;
        let dx = if di_sum <= f64::EPSILON {
            0.0
        } else {
            100.0 * (plus_di - minus_di).abs() / di_sum
        };

        if self.current_value.is_none() {
            self.dx_values.push_back(dx);
            if self.dx_values.len() < self.period {
                return None;
            }
            let dx_mean = self.dx_values.iter().sum::<f64>() / self.period as f64;
            self.current_value = Some(dx_mean);
            return self.current_value;
        }

        if let Some(prev_adx) = self.current_value {
            let adx = ((prev_adx * (self.period as f64 - 1.0)) + dx) / self.period as f64;
            self.current_value = Some(adx);
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

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct DX {
    period: usize,
    prev_high: Option<f64>,
    prev_low: Option<f64>,
    prev_close: Option<f64>,
    smoothed_tr: f64,
    smoothed_plus_dm: f64,
    smoothed_minus_dm: f64,
    count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl DX {
    #[new]
    pub fn new(period: usize) -> Self {
        DX {
            period,
            prev_high: None,
            prev_low: None,
            prev_close: None,
            smoothed_tr: 0.0,
            smoothed_plus_dm: 0.0,
            smoothed_minus_dm: 0.0,
            count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let Some(prev_high) = self.prev_high else {
            self.prev_high = Some(high);
            self.prev_low = Some(low);
            self.prev_close = Some(close);
            return None;
        };
        let prev_low = self.prev_low.unwrap_or(low);
        let prev_close = self.prev_close.unwrap_or(close);
        let up_move = high - prev_high;
        let down_move = prev_low - low;
        let plus_dm = if up_move > down_move && up_move > 0.0 {
            up_move
        } else {
            0.0
        };
        let minus_dm = if down_move > up_move && down_move > 0.0 {
            down_move
        } else {
            0.0
        };
        let tr = (high - low)
            .max((high - prev_close).abs())
            .max((low - prev_close).abs());
        self.prev_high = Some(high);
        self.prev_low = Some(low);
        self.prev_close = Some(close);
        if self.count < self.period {
            self.smoothed_tr += tr;
            self.smoothed_plus_dm += plus_dm;
            self.smoothed_minus_dm += minus_dm;
            self.count += 1;
            if self.count < self.period {
                return None;
            }
        } else {
            self.smoothed_tr = self.smoothed_tr - (self.smoothed_tr / self.period as f64) + tr;
            self.smoothed_plus_dm =
                self.smoothed_plus_dm - (self.smoothed_plus_dm / self.period as f64) + plus_dm;
            self.smoothed_minus_dm =
                self.smoothed_minus_dm - (self.smoothed_minus_dm / self.period as f64) + minus_dm;
        }
        if self.smoothed_tr <= f64::EPSILON {
            self.current_value = Some(0.0);
            return self.current_value;
        }
        let plus_di = 100.0 * self.smoothed_plus_dm / self.smoothed_tr;
        let minus_di = 100.0 * self.smoothed_minus_dm / self.smoothed_tr;
        let di_sum = plus_di + minus_di;
        if di_sum <= f64::EPSILON {
            self.current_value = Some(0.0);
        } else {
            self.current_value = Some(100.0 * (plus_di - minus_di).abs() / di_sum);
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

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ADXR {
    period: usize,
    adx: ADX,
    adx_values: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ADXR {
    #[new]
    pub fn new(period: usize) -> Self {
        ADXR {
            period,
            adx: ADX::new(period),
            adx_values: VecDeque::with_capacity(period + 1),
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let adx_now = self.adx.update(high, low, close)?;
        self.adx_values.push_back(adx_now);
        if self.adx_values.len() > self.period + 1 {
            self.adx_values.pop_front();
        }
        if self.adx_values.len() <= self.period {
            self.current_value = None;
            return None;
        }
        let adx_prev = *self.adx_values.front()?;
        self.current_value = Some((adx_now + adx_prev) / 2.0);
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

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
#[allow(non_camel_case_types)]
pub struct PLUS_DI {
    period: usize,
    prev_high: Option<f64>,
    prev_low: Option<f64>,
    prev_close: Option<f64>,
    smoothed_tr: f64,
    smoothed_plus_dm: f64,
    count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PLUS_DI {
    #[new]
    pub fn new(period: usize) -> Self {
        PLUS_DI {
            period,
            prev_high: None,
            prev_low: None,
            prev_close: None,
            smoothed_tr: 0.0,
            smoothed_plus_dm: 0.0,
            count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let Some(prev_high) = self.prev_high else {
            self.prev_high = Some(high);
            self.prev_low = Some(low);
            self.prev_close = Some(close);
            return None;
        };
        let prev_low = self.prev_low.unwrap_or(low);
        let prev_close = self.prev_close.unwrap_or(close);
        let up_move = high - prev_high;
        let down_move = prev_low - low;
        let plus_dm = if up_move > down_move && up_move > 0.0 {
            up_move
        } else {
            0.0
        };
        let tr = (high - low)
            .max((high - prev_close).abs())
            .max((low - prev_close).abs());
        self.prev_high = Some(high);
        self.prev_low = Some(low);
        self.prev_close = Some(close);
        if self.count < self.period {
            self.smoothed_tr += tr;
            self.smoothed_plus_dm += plus_dm;
            self.count += 1;
            if self.count < self.period {
                return None;
            }
        } else {
            self.smoothed_tr = self.smoothed_tr - (self.smoothed_tr / self.period as f64) + tr;
            self.smoothed_plus_dm =
                self.smoothed_plus_dm - (self.smoothed_plus_dm / self.period as f64) + plus_dm;
        }
        if self.smoothed_tr <= f64::EPSILON {
            self.current_value = Some(0.0);
        } else {
            self.current_value = Some(100.0 * self.smoothed_plus_dm / self.smoothed_tr);
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

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
#[allow(non_camel_case_types)]
pub struct MINUS_DI {
    period: usize,
    prev_high: Option<f64>,
    prev_low: Option<f64>,
    prev_close: Option<f64>,
    smoothed_tr: f64,
    smoothed_minus_dm: f64,
    count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MINUS_DI {
    #[new]
    pub fn new(period: usize) -> Self {
        MINUS_DI {
            period,
            prev_high: None,
            prev_low: None,
            prev_close: None,
            smoothed_tr: 0.0,
            smoothed_minus_dm: 0.0,
            count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let Some(prev_high) = self.prev_high else {
            self.prev_high = Some(high);
            self.prev_low = Some(low);
            self.prev_close = Some(close);
            return None;
        };
        let prev_low = self.prev_low.unwrap_or(low);
        let prev_close = self.prev_close.unwrap_or(close);
        let up_move = high - prev_high;
        let down_move = prev_low - low;
        let minus_dm = if down_move > up_move && down_move > 0.0 {
            down_move
        } else {
            0.0
        };
        let tr = (high - low)
            .max((high - prev_close).abs())
            .max((low - prev_close).abs());
        self.prev_high = Some(high);
        self.prev_low = Some(low);
        self.prev_close = Some(close);
        if self.count < self.period {
            self.smoothed_tr += tr;
            self.smoothed_minus_dm += minus_dm;
            self.count += 1;
            if self.count < self.period {
                return None;
            }
        } else {
            self.smoothed_tr = self.smoothed_tr - (self.smoothed_tr / self.period as f64) + tr;
            self.smoothed_minus_dm =
                self.smoothed_minus_dm - (self.smoothed_minus_dm / self.period as f64) + minus_dm;
        }
        if self.smoothed_tr <= f64::EPSILON {
            self.current_value = Some(0.0);
        } else {
            self.current_value = Some(100.0 * self.smoothed_minus_dm / self.smoothed_tr);
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
    m.add_class::<ADX>()?;
    m.add_class::<DX>()?;
    m.add_class::<ADXR>()?;
    m.add_class::<PLUS_DI>()?;
    m.add_class::<MINUS_DI>()?;
    Ok(())
}
