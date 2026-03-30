use numpy::PyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct BollingerBands {
    period: usize,
    multiplier: f64,
    buffer: VecDeque<f64>,
    sum: f64,
    sum_sq: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl BollingerBands {
    #[new]
    pub fn new(period: usize, multiplier: f64) -> Self {
        BollingerBands {
            period,
            multiplier,
            buffer: VecDeque::with_capacity(period),
            sum: 0.0,
            sum_sq: 0.0,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<(f64, f64, f64)> {
        self.buffer.push_back(value);
        self.sum += value;
        self.sum_sq += value * value;
        if self.buffer.len() > self.period
            && let Some(removed) = self.buffer.pop_front()
        {
            self.sum -= removed;
            self.sum_sq -= removed * removed;
        }
        if self.buffer.len() == self.period {
            let mean = self.sum / self.period as f64;
            let variance = (self.sum_sq / self.period as f64 - mean * mean).max(0.0);
            let std_dev = variance.sqrt();
            let upper = mean + self.multiplier * std_dev;
            let lower = mean - self.multiplier * std_dev;
            Some((upper, mean, lower))
        } else {
            None
        }
    }

    pub fn update_many<'py>(
        &mut self,
        py: Python<'py>,
        values: Vec<f64>,
    ) -> (
        Bound<'py, PyArray1<f64>>,
        Bound<'py, PyArray1<f64>>,
        Bound<'py, PyArray1<f64>>,
    ) {
        let mut upper = Vec::with_capacity(values.len());
        let mut middle = Vec::with_capacity(values.len());
        let mut lower = Vec::with_capacity(values.len());
        for value in values {
            if let Some((u, m, l)) = self.update(value) {
                upper.push(u);
                middle.push(m);
                lower.push(l);
            } else {
                upper.push(f64::NAN);
                middle.push(f64::NAN);
                lower.push(f64::NAN);
            }
        }
        (
            PyArray1::from_vec(py, upper),
            PyArray1::from_vec(py, middle),
            PyArray1::from_vec(py, lower),
        )
    }

    #[getter]
    pub fn value(&self) -> Option<(f64, f64, f64)> {
        if self.buffer.len() == self.period {
            let mean = self.sum / self.period as f64;
            let variance = (self.sum_sq / self.period as f64 - mean * mean).max(0.0);
            let std_dev = variance.sqrt();
            let upper = mean + self.multiplier * std_dev;
            let lower = mean - self.multiplier * std_dev;
            Some((upper, mean, lower))
        } else {
            None
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ATR {
    period: usize,
    prev_close: Option<f64>,
    smoothed_tr: f64,
    count: usize,
}

#[gen_stub_pymethods]
#[pymethods]
impl ATR {
    #[new]
    pub fn new(period: usize) -> Self {
        ATR {
            period,
            prev_close: None,
            smoothed_tr: 0.0,
            count: 0,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let tr = match self.prev_close {
            Some(pc) => {
                let hl = high - low;
                let hpc = (high - pc).abs();
                let lpc = (low - pc).abs();
                hl.max(hpc).max(lpc)
            }
            None => high - low,
        };
        self.prev_close = Some(close);
        if self.count < self.period {
            self.smoothed_tr += tr;
            self.count += 1;
            if self.count == self.period {
                self.smoothed_tr /= self.period as f64;
                return Some(self.smoothed_tr);
            } else {
                return None;
            }
        }
        self.smoothed_tr =
            (self.smoothed_tr * (self.period as f64 - 1.0) + tr) / self.period as f64;
        Some(self.smoothed_tr)
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
        if self.count >= self.period {
            Some(self.smoothed_tr)
        } else {
            None
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct NATR {
    atr: ATR,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl NATR {
    #[new]
    pub fn new(period: usize) -> Self {
        NATR {
            atr: ATR::new(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let atr = self.atr.update(high, low, close)?;
        if close.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some(100.0 * atr / close);
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
pub struct TRANGE {
    prev_close: Option<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TRANGE {
    #[new]
    pub fn new() -> Self {
        TRANGE {
            prev_close: None,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let tr = match self.prev_close {
            Some(prev_close) => {
                let hl = high - low;
                let hpc = (high - prev_close).abs();
                let lpc = (low - prev_close).abs();
                hl.max(hpc).max(lpc)
            }
            None => high - low,
        };
        self.prev_close = Some(close);
        self.current_value = Some(tr);
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
pub struct STDDEV {
    period: usize,
    nbdev: f64,
    buffer: VecDeque<f64>,
    sum: f64,
    sum_sq: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl STDDEV {
    #[new]
    pub fn new(period: usize, nbdev: f64) -> Self {
        STDDEV {
            period,
            nbdev,
            buffer: VecDeque::with_capacity(period),
            sum: 0.0,
            sum_sq: 0.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        self.sum += value;
        self.sum_sq += value * value;
        if self.buffer.len() > self.period
            && let Some(removed) = self.buffer.pop_front()
        {
            self.sum -= removed;
            self.sum_sq -= removed * removed;
        }
        if self.buffer.len() < self.period {
            self.current_value = None;
            return None;
        }
        let mean = self.sum / self.period as f64;
        let variance = (self.sum_sq / self.period as f64 - mean * mean).max(0.0);
        self.current_value = Some(variance.sqrt() * self.nbdev);
        self.current_value
    }

    pub fn update_many<'py>(
        &mut self,
        py: Python<'py>,
        values: Vec<f64>,
    ) -> Bound<'py, PyArray1<f64>> {
        let mut out = Vec::with_capacity(values.len());
        for value in values {
            out.push(self.update(value).unwrap_or(f64::NAN));
        }
        PyArray1::from_vec(py, out)
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct VAR {
    period: usize,
    nbdev: f64,
    buffer: VecDeque<f64>,
    sum: f64,
    sum_sq: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl VAR {
    #[new]
    pub fn new(period: usize, nbdev: f64) -> Self {
        VAR {
            period,
            nbdev,
            buffer: VecDeque::with_capacity(period),
            sum: 0.0,
            sum_sq: 0.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        self.sum += value;
        self.sum_sq += value * value;
        if self.buffer.len() > self.period
            && let Some(removed) = self.buffer.pop_front()
        {
            self.sum -= removed;
            self.sum_sq -= removed * removed;
        }
        if self.buffer.len() < self.period {
            self.current_value = None;
            return None;
        }
        let mean = self.sum / self.period as f64;
        let variance = (self.sum_sq / self.period as f64 - mean * mean).max(0.0);
        self.current_value = Some(variance * self.nbdev * self.nbdev);
        self.current_value
    }

    pub fn update_many<'py>(
        &mut self,
        py: Python<'py>,
        values: Vec<f64>,
    ) -> Bound<'py, PyArray1<f64>> {
        let mut out = Vec::with_capacity(values.len());
        for value in values {
            out.push(self.update(value).unwrap_or(f64::NAN));
        }
        PyArray1::from_vec(py, out)
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BollingerBands>()?;
    m.add_class::<ATR>()?;
    m.add_class::<NATR>()?;
    m.add_class::<TRANGE>()?;
    m.add_class::<STDDEV>()?;
    m.add_class::<VAR>()?;
    Ok(())
}
