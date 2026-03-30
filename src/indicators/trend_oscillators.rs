use numpy::PyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct STOCH {
    fastk_period: usize,
    slowk_period: usize,
    slowd_period: usize,
    highs: VecDeque<f64>,
    lows: VecDeque<f64>,
    fastk_buffer: VecDeque<f64>,
    slowk_buffer: VecDeque<f64>,
    fastk_sum: f64,
    slowk_sum: f64,
    current_value: Option<(f64, f64)>,
}

#[gen_stub_pymethods]
#[pymethods]
impl STOCH {
    #[new]
    pub fn new(fastk_period: usize, slowk_period: usize, slowd_period: usize) -> Self {
        STOCH {
            fastk_period,
            slowk_period,
            slowd_period,
            highs: VecDeque::with_capacity(fastk_period),
            lows: VecDeque::with_capacity(fastk_period),
            fastk_buffer: VecDeque::with_capacity(slowk_period),
            slowk_buffer: VecDeque::with_capacity(slowd_period),
            fastk_sum: 0.0,
            slowk_sum: 0.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<(f64, f64)> {
        self.highs.push_back(high);
        self.lows.push_back(low);
        if self.highs.len() > self.fastk_period {
            self.highs.pop_front();
            self.lows.pop_front();
        }
        if self.highs.len() < self.fastk_period {
            self.current_value = None;
            return None;
        }

        let highest = self
            .highs
            .iter()
            .fold(f64::NEG_INFINITY, |acc, x| acc.max(*x));
        let lowest = self.lows.iter().fold(f64::INFINITY, |acc, x| acc.min(*x));
        let range = highest - lowest;
        let fastk = if range.abs() <= f64::EPSILON {
            0.0
        } else {
            100.0 * (close - lowest) / range
        };

        self.fastk_buffer.push_back(fastk);
        self.fastk_sum += fastk;
        if self.fastk_buffer.len() > self.slowk_period
            && let Some(removed) = self.fastk_buffer.pop_front()
        {
            self.fastk_sum -= removed;
        }
        if self.fastk_buffer.len() < self.slowk_period {
            self.current_value = None;
            return None;
        }
        let slowk = self.fastk_sum / self.slowk_period as f64;

        self.slowk_buffer.push_back(slowk);
        self.slowk_sum += slowk;
        if self.slowk_buffer.len() > self.slowd_period
            && let Some(removed) = self.slowk_buffer.pop_front()
        {
            self.slowk_sum -= removed;
        }
        if self.slowk_buffer.len() < self.slowd_period {
            self.current_value = None;
            return None;
        }
        let slowd = self.slowk_sum / self.slowd_period as f64;
        self.current_value = Some((slowk, slowd));
        self.current_value
    }

    pub fn update_many_hlc_pair<'py>(
        &mut self,
        py: Python<'py>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<(Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>)> {
        if highs.len() != lows.len() || highs.len() != closes.len() {
            return Err(PyValueError::new_err("highs/lows/closes length mismatch"));
        }
        let mut out_first = Vec::with_capacity(highs.len());
        let mut out_second = Vec::with_capacity(highs.len());
        for (high, (low, close)) in highs
            .into_iter()
            .zip(lows.into_iter().zip(closes.into_iter()))
        {
            if let Some((first, second)) = self.update(high, low, close) {
                out_first.push(first);
                out_second.push(second);
            } else {
                out_first.push(f64::NAN);
                out_second.push(f64::NAN);
            }
        }
        Ok((
            PyArray1::from_vec(py, out_first),
            PyArray1::from_vec(py, out_second),
        ))
    }

    #[getter]
    pub fn value(&self) -> Option<(f64, f64)> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct AROON {
    period: usize,
    highs: VecDeque<f64>,
    lows: VecDeque<f64>,
    current_value: Option<(f64, f64)>,
}

#[gen_stub_pymethods]
#[pymethods]
impl AROON {
    #[new]
    pub fn new(period: usize) -> Self {
        AROON {
            period,
            highs: VecDeque::with_capacity(period),
            lows: VecDeque::with_capacity(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64) -> Option<(f64, f64)> {
        self.highs.push_back(high);
        self.lows.push_back(low);
        if self.highs.len() > self.period {
            self.highs.pop_front();
            self.lows.pop_front();
        }
        if self.highs.len() < self.period {
            self.current_value = None;
            return None;
        }

        let mut idx_high = 0usize;
        let mut val_high = f64::NEG_INFINITY;
        for (idx, value) in self.highs.iter().enumerate() {
            if *value >= val_high {
                val_high = *value;
                idx_high = idx;
            }
        }
        let mut idx_low = 0usize;
        let mut val_low = f64::INFINITY;
        for (idx, value) in self.lows.iter().enumerate() {
            if *value <= val_low {
                val_low = *value;
                idx_low = idx;
            }
        }
        let days_since_high = self.period - 1 - idx_high;
        let days_since_low = self.period - 1 - idx_low;
        let up = 100.0 * (self.period - days_since_high) as f64 / self.period as f64;
        let down = 100.0 * (self.period - days_since_low) as f64 / self.period as f64;
        self.current_value = Some((down, up));
        self.current_value
    }

    pub fn update_many_hl_pair<'py>(
        &mut self,
        py: Python<'py>,
        highs: Vec<f64>,
        lows: Vec<f64>,
    ) -> PyResult<(Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>)> {
        if highs.len() != lows.len() {
            return Err(PyValueError::new_err("highs/lows length mismatch"));
        }
        let mut first = Vec::with_capacity(highs.len());
        let mut second = Vec::with_capacity(highs.len());
        for (high, low) in highs.into_iter().zip(lows.into_iter()) {
            if let Some((f, s)) = self.update(high, low) {
                first.push(f);
                second.push(s);
            } else {
                first.push(f64::NAN);
                second.push(f64::NAN);
            }
        }
        Ok((
            PyArray1::from_vec(py, first),
            PyArray1::from_vec(py, second),
        ))
    }

    #[getter]
    pub fn value(&self) -> Option<(f64, f64)> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct AROONOSC {
    period: usize,
    highs: VecDeque<f64>,
    lows: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl AROONOSC {
    #[new]
    pub fn new(period: usize) -> Self {
        AROONOSC {
            period,
            highs: VecDeque::with_capacity(period),
            lows: VecDeque::with_capacity(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64) -> Option<f64> {
        self.highs.push_back(high);
        self.lows.push_back(low);
        if self.highs.len() > self.period {
            self.highs.pop_front();
            self.lows.pop_front();
        }
        if self.highs.len() < self.period {
            self.current_value = None;
            return None;
        }

        let mut idx_high = 0usize;
        let mut val_high = f64::NEG_INFINITY;
        for (idx, value) in self.highs.iter().enumerate() {
            if *value >= val_high {
                val_high = *value;
                idx_high = idx;
            }
        }
        let mut idx_low = 0usize;
        let mut val_low = f64::INFINITY;
        for (idx, value) in self.lows.iter().enumerate() {
            if *value <= val_low {
                val_low = *value;
                idx_low = idx;
            }
        }
        let days_since_high = self.period - 1 - idx_high;
        let days_since_low = self.period - 1 - idx_low;
        let up = 100.0 * (self.period - days_since_high) as f64 / self.period as f64;
        let down = 100.0 * (self.period - days_since_low) as f64 / self.period as f64;
        self.current_value = Some(up - down);
        self.current_value
    }

    pub fn update_many_hl<'py>(
        &mut self,
        py: Python<'py>,
        highs: Vec<f64>,
        lows: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<f64>>> {
        if highs.len() != lows.len() {
            return Err(PyValueError::new_err("highs/lows length mismatch"));
        }
        let mut out = Vec::with_capacity(highs.len());
        for (high, low) in highs.into_iter().zip(lows.into_iter()) {
            out.push(self.update(high, low).unwrap_or(f64::NAN));
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
pub struct SAR {
    acceleration: f64,
    maximum: f64,
    initialized: bool,
    trend_up: bool,
    sar: f64,
    ep: f64,
    af: f64,
    prev_high: Option<f64>,
    prev_low: Option<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SAR {
    #[new]
    pub fn new(acceleration: f64, maximum: f64) -> Self {
        SAR {
            acceleration,
            maximum,
            initialized: false,
            trend_up: true,
            sar: 0.0,
            ep: 0.0,
            af: acceleration,
            prev_high: None,
            prev_low: None,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64) -> Option<f64> {
        let Some(prev_high) = self.prev_high else {
            self.prev_high = Some(high);
            self.prev_low = Some(low);
            self.current_value = None;
            return None;
        };
        let prev_low = self.prev_low.unwrap_or(low);

        if !self.initialized {
            self.trend_up = high >= prev_high;
            if self.trend_up {
                self.sar = prev_low.min(low);
                self.ep = prev_high.max(high);
            } else {
                self.sar = prev_high.max(high);
                self.ep = prev_low.min(low);
            }
            self.af = self.acceleration;
            self.initialized = true;
            self.prev_high = Some(high);
            self.prev_low = Some(low);
            self.current_value = Some(self.sar);
            return self.current_value;
        }

        let mut sar_next = self.sar + self.af * (self.ep - self.sar);
        if self.trend_up {
            sar_next = sar_next.min(prev_low).min(low);
            if low < sar_next {
                self.trend_up = false;
                sar_next = self.ep;
                self.ep = low;
                self.af = self.acceleration;
            } else if high > self.ep {
                self.ep = high;
                self.af = (self.af + self.acceleration).min(self.maximum);
            }
        } else {
            sar_next = sar_next.max(prev_high).max(high);
            if high > sar_next {
                self.trend_up = true;
                sar_next = self.ep;
                self.ep = high;
                self.af = self.acceleration;
            } else if low < self.ep {
                self.ep = low;
                self.af = (self.af + self.acceleration).min(self.maximum);
            }
        }

        self.sar = sar_next;
        self.prev_high = Some(high);
        self.prev_low = Some(low);
        self.current_value = Some(self.sar);
        self.current_value
    }

    pub fn update_many_hl<'py>(
        &mut self,
        py: Python<'py>,
        highs: Vec<f64>,
        lows: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<f64>>> {
        if highs.len() != lows.len() {
            return Err(PyValueError::new_err("highs/lows length mismatch"));
        }
        let mut out = Vec::with_capacity(highs.len());
        for (high, low) in highs.into_iter().zip(lows.into_iter()) {
            out.push(self.update(high, low).unwrap_or(f64::NAN));
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
pub struct ULTOSC {
    period1: usize,
    period2: usize,
    period3: usize,
    prev_close: Option<f64>,
    bp_values: VecDeque<f64>,
    tr_values: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ULTOSC {
    #[new]
    pub fn new(period1: usize, period2: usize, period3: usize) -> Self {
        ULTOSC {
            period1,
            period2,
            period3,
            prev_close: None,
            bp_values: VecDeque::with_capacity(period3),
            tr_values: VecDeque::with_capacity(period3),
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
        let prev_close = self.prev_close.unwrap_or(close);
        let min_low = low.min(prev_close);
        let max_high = high.max(prev_close);
        let bp = close - min_low;
        let tr = max_high - min_low;
        self.bp_values.push_back(bp);
        self.tr_values.push_back(tr);
        if self.bp_values.len() > self.period3 {
            self.bp_values.pop_front();
            self.tr_values.pop_front();
        }
        self.prev_close = Some(close);
        if self.bp_values.len() < self.period3 {
            self.current_value = None;
            return None;
        }
        let bp1 = self.bp_values.iter().rev().take(self.period1).sum::<f64>();
        let tr1 = self.tr_values.iter().rev().take(self.period1).sum::<f64>();
        let bp2 = self.bp_values.iter().rev().take(self.period2).sum::<f64>();
        let tr2 = self.tr_values.iter().rev().take(self.period2).sum::<f64>();
        let bp3 = self.bp_values.iter().rev().take(self.period3).sum::<f64>();
        let tr3 = self.tr_values.iter().rev().take(self.period3).sum::<f64>();
        if tr1 <= f64::EPSILON || tr2 <= f64::EPSILON || tr3 <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            let avg1 = bp1 / tr1;
            let avg2 = bp2 / tr2;
            let avg3 = bp3 / tr3;
            self.current_value = Some(100.0 * (4.0 * avg1 + 2.0 * avg2 + avg3) / 7.0);
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
    m.add_class::<AROON>()?;
    m.add_class::<AROONOSC>()?;
    m.add_class::<STOCH>()?;
    m.add_class::<SAR>()?;
    m.add_class::<ULTOSC>()?;
    Ok(())
}
