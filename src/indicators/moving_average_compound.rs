use numpy::PyArray1;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

use super::moving_average_core::EMA;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MACD {
    fast_ema: EMA,
    slow_ema: EMA,
    signal_ema: EMA,
}

#[gen_stub_pymethods]
#[pymethods]
impl MACD {
    #[new]
    pub fn new(fast_period: usize, slow_period: usize, signal_period: usize) -> Self {
        MACD {
            fast_ema: EMA::new(fast_period),
            slow_ema: EMA::new(slow_period),
            signal_ema: EMA::new(signal_period),
        }
    }

    pub fn update(&mut self, value: f64) -> Option<(f64, f64, f64)> {
        let fast = self.fast_ema.update(value)?;
        let slow = self.slow_ema.update(value)?;
        let macd_line = fast - slow;
        let signal_line = self.signal_ema.update(macd_line)?;
        let histogram = macd_line - signal_line;
        Some((macd_line, signal_line, histogram))
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
        let mut macd = Vec::with_capacity(values.len());
        let mut signal = Vec::with_capacity(values.len());
        let mut hist = Vec::with_capacity(values.len());
        for value in values {
            let out = self.update(value);
            if let Some((m, s, h)) = out {
                macd.push(m);
                signal.push(s);
                hist.push(h);
            } else {
                macd.push(f64::NAN);
                signal.push(f64::NAN);
                hist.push(f64::NAN);
            }
        }
        (
            PyArray1::from_vec(py, macd),
            PyArray1::from_vec(py, signal),
            PyArray1::from_vec(py, hist),
        )
    }

    #[getter]
    pub fn value(&self) -> Option<(f64, f64, f64)> {
        let fast = self.fast_ema.value()?;
        let slow = self.slow_ema.value()?;
        let macd_line = fast - slow;
        let signal_line = self.signal_ema.value()?;
        let histogram = macd_line - signal_line;
        Some((macd_line, signal_line, histogram))
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct DEMA {
    ema1: EMA,
    ema2: EMA,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl DEMA {
    #[new]
    pub fn new(period: usize) -> Self {
        DEMA {
            ema1: EMA::new(period),
            ema2: EMA::new(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let ema1 = self.ema1.update(value)?;
        let ema2 = self.ema2.update(ema1)?;
        self.current_value = Some(2.0 * ema1 - ema2);
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
pub struct TRIX {
    ema1: EMA,
    ema2: EMA,
    ema3: EMA,
    prev_ema3: Option<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TRIX {
    #[new]
    pub fn new(period: usize) -> Self {
        TRIX {
            ema1: EMA::new(period),
            ema2: EMA::new(period),
            ema3: EMA::new(period),
            prev_ema3: None,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let ema1 = self.ema1.update(value)?;
        let ema2 = self.ema2.update(ema1)?;
        let ema3 = self.ema3.update(ema2)?;
        let Some(prev) = self.prev_ema3 else {
            self.prev_ema3 = Some(ema3);
            self.current_value = None;
            return None;
        };
        if prev.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some((ema3 - prev) / prev * 100.0);
        }
        self.prev_ema3 = Some(ema3);
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
pub struct TEMA {
    ema1: EMA,
    ema2: EMA,
    ema3: EMA,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TEMA {
    #[new]
    pub fn new(period: usize) -> Self {
        TEMA {
            ema1: EMA::new(period),
            ema2: EMA::new(period),
            ema3: EMA::new(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let ema1 = self.ema1.update(value)?;
        let ema2 = self.ema2.update(ema1)?;
        let ema3 = self.ema3.update(ema2)?;
        self.current_value = Some(3.0 * ema1 - 3.0 * ema2 + ema3);
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
pub struct KAMA {
    period: usize,
    prices: VecDeque<f64>,
    fast_sc: f64,
    slow_sc: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl KAMA {
    #[new]
    pub fn new(period: usize) -> Self {
        KAMA {
            period,
            prices: VecDeque::with_capacity(period + 1),
            fast_sc: 2.0 / 3.0,
            slow_sc: 2.0 / 31.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.prices.push_back(value);
        if self.prices.len() > self.period + 1 {
            self.prices.pop_front();
        }
        if self.prices.len() < self.period + 1 {
            self.current_value = None;
            return None;
        }
        let first = *self.prices.front()?;
        let last = *self.prices.back()?;
        let change = (last - first).abs();
        let volatility = self
            .prices
            .iter()
            .zip(self.prices.iter().skip(1))
            .map(|(a, b)| (b - a).abs())
            .sum::<f64>();
        let er = if volatility <= f64::EPSILON {
            0.0
        } else {
            change / volatility
        };
        let sc = (er * (self.fast_sc - self.slow_sc) + self.slow_sc).powi(2);
        let prev = self.current_value.unwrap_or(last);
        let kama = prev + sc * (last - prev);
        self.current_value = Some(kama);
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
pub struct APO {
    slow_period: usize,
    fast_ema: EMA,
    slow_ema: EMA,
    count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl APO {
    #[new]
    pub fn new(fast_period: usize, slow_period: usize) -> Self {
        APO {
            slow_period,
            fast_ema: EMA::new(fast_period),
            slow_ema: EMA::new(slow_period),
            count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let fast = self.fast_ema.update(value)?;
        let slow = self.slow_ema.update(value)?;
        self.count += 1;
        if self.count < self.slow_period {
            self.current_value = None;
            return None;
        }
        self.current_value = Some(fast - slow);
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
pub struct PPO {
    slow_period: usize,
    fast_ema: EMA,
    slow_ema: EMA,
    count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PPO {
    #[new]
    pub fn new(fast_period: usize, slow_period: usize) -> Self {
        PPO {
            slow_period,
            fast_ema: EMA::new(fast_period),
            slow_ema: EMA::new(slow_period),
            count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let fast = self.fast_ema.update(value)?;
        let slow = self.slow_ema.update(value)?;
        self.count += 1;
        if self.count < self.slow_period {
            self.current_value = None;
            return None;
        }
        if slow.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some(100.0 * (fast - slow) / slow);
        }
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
pub struct T3 {
    ema1: EMA,
    ema2: EMA,
    ema3: EMA,
    ema4: EMA,
    ema5: EMA,
    ema6: EMA,
    vfactor: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl T3 {
    #[new]
    pub fn new(period: usize, vfactor: f64) -> Self {
        T3 {
            ema1: EMA::new(period),
            ema2: EMA::new(period),
            ema3: EMA::new(period),
            ema4: EMA::new(period),
            ema5: EMA::new(period),
            ema6: EMA::new(period),
            vfactor,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let e1 = self.ema1.update(value)?;
        let e2 = self.ema2.update(e1)?;
        let e3 = self.ema3.update(e2)?;
        let e4 = self.ema4.update(e3)?;
        let e5 = self.ema5.update(e4)?;
        let e6 = self.ema6.update(e5)?;

        let a = self.vfactor;
        let c1 = -a * a * a;
        let c2 = 3.0 * a * a + 3.0 * a * a * a;
        let c3 = -6.0 * a * a - 3.0 * a - 3.0 * a * a * a;
        let c4 = 1.0 + 3.0 * a + a * a * a + 3.0 * a * a;
        self.current_value = Some(c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3);
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
#[allow(non_camel_case_types)]
pub struct HT_TRENDLINE {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl HT_TRENDLINE {
    #[new]
    pub fn new() -> Self {
        HT_TRENDLINE {
            period: 7,
            buffer: VecDeque::with_capacity(7),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period {
            self.current_value = None;
            return None;
        }
        let weights = [1.0, 2.0, 3.0, 4.0, 3.0, 2.0, 1.0];
        let denom = 16.0;
        let weighted_sum = self
            .buffer
            .iter()
            .zip(weights.iter())
            .map(|(v, w)| *v * *w)
            .sum::<f64>();
        self.current_value = Some(weighted_sum / denom);
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
pub struct MAMA {
    fast_limit: f64,
    slow_limit: f64,
    prev_price: Option<f64>,
    mama: Option<f64>,
    fama: Option<f64>,
    current_value: Option<(f64, f64)>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MAMA {
    #[new]
    pub fn new(fast_limit: f64, slow_limit: f64) -> Self {
        MAMA {
            fast_limit,
            slow_limit,
            prev_price: None,
            mama: None,
            fama: None,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<(f64, f64)> {
        let Some(prev_price) = self.prev_price else {
            self.prev_price = Some(value);
            self.current_value = None;
            return None;
        };
        let base = prev_price.abs().max(1e-12);
        let ratio = ((value - prev_price).abs() / base).clamp(0.0, 1.0);
        let alpha = (self.fast_limit * ratio).clamp(self.slow_limit, self.fast_limit);
        let prev_mama = self.mama.unwrap_or(value);
        let next_mama = alpha * value + (1.0 - alpha) * prev_mama;
        let prev_fama = self.fama.unwrap_or(next_mama);
        let next_fama = (0.5 * alpha) * next_mama + (1.0 - 0.5 * alpha) * prev_fama;
        self.prev_price = Some(value);
        self.mama = Some(next_mama);
        self.fama = Some(next_fama);
        self.current_value = Some((next_mama, next_fama));
        self.current_value
    }

    pub fn update_many_pair<'py>(
        &mut self,
        py: Python<'py>,
        values: Vec<f64>,
    ) -> (Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>) {
        let mut first = Vec::with_capacity(values.len());
        let mut second = Vec::with_capacity(values.len());
        for value in values {
            if let Some((f, s)) = self.update(value) {
                first.push(f);
                second.push(s);
            } else {
                first.push(f64::NAN);
                second.push(f64::NAN);
            }
        }
        (
            PyArray1::from_vec(py, first),
            PyArray1::from_vec(py, second),
        )
    }

    #[getter]
    pub fn value(&self) -> Option<(f64, f64)> {
        self.current_value
    }
}

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<MACD>()?;
    m.add_class::<DEMA>()?;
    m.add_class::<TRIX>()?;
    m.add_class::<TEMA>()?;
    m.add_class::<KAMA>()?;
    m.add_class::<APO>()?;
    m.add_class::<PPO>()?;
    m.add_class::<T3>()?;
    m.add_class::<HT_TRENDLINE>()?;
    m.add_class::<MAMA>()?;
    Ok(())
}
