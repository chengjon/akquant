use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct SMA {
    period: usize,
    buffer: VecDeque<f64>,
    sum: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl SMA {
    #[new]
    pub fn new(period: usize) -> Self {
        SMA {
            period,
            buffer: VecDeque::with_capacity(period),
            sum: 0.0,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        self.sum += value;

        if self.buffer.len() > self.period
            && let Some(removed) = self.buffer.pop_front()
        {
            self.sum -= removed;
        }

        if self.buffer.len() == self.period {
            Some(self.sum / self.period as f64)
        } else {
            None
        }
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        if self.buffer.len() == self.period {
            Some(self.sum / self.period as f64)
        } else {
            None
        }
    }

    #[getter]
    pub fn is_ready(&self) -> bool {
        self.buffer.len() == self.period
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct EMA {
    period: usize,
    k: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl EMA {
    #[new]
    pub fn new(period: usize) -> Self {
        EMA {
            period,
            k: 2.0 / (period as f64 + 1.0),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        match self.current_value {
            Some(prev) => {
                let next = (value - prev) * self.k + prev;
                self.current_value = Some(next);
            }
            None => {
                self.current_value = Some(value);
            }
        }
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }

    #[getter]
    pub fn is_ready(&self) -> bool {
        self.current_value.is_some()
    }

    #[getter]
    pub fn period(&self) -> usize {
        self.period
    }
}

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

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct WMA {
    period: usize,
    buffer: VecDeque<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl WMA {
    #[new]
    pub fn new(period: usize) -> Self {
        WMA {
            period,
            buffer: VecDeque::with_capacity(period),
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period {
            return None;
        }
        self.value()
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        if self.buffer.len() < self.period {
            return None;
        }
        let mut weighted_sum = 0.0;
        for (idx, val) in self.buffer.iter().enumerate() {
            weighted_sum += *val * (idx as f64 + 1.0);
        }
        let denom = (self.period * (self.period + 1) / 2) as f64;
        Some(weighted_sum / denom)
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

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct TRIMA {
    period: usize,
    buffer: VecDeque<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TRIMA {
    #[new]
    pub fn new(period: usize) -> Self {
        TRIMA {
            period,
            buffer: VecDeque::with_capacity(period),
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period {
            self.buffer.pop_front();
        }
        self.value()
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        if self.buffer.len() < self.period {
            return None;
        }
        let weights = if self.period % 2 == 1 {
            let peak = self.period / 2 + 1;
            (0..self.period)
                .map(|i| if i < peak { i + 1 } else { self.period - i })
                .collect::<Vec<usize>>()
        } else {
            let peak = self.period / 2;
            (0..self.period)
                .map(|i| if i < peak { i + 1 } else { self.period - i })
                .collect::<Vec<usize>>()
        };
        let mut weighted_sum = 0.0;
        let mut denom = 0.0;
        for (value, weight) in self.buffer.iter().zip(weights.iter()) {
            weighted_sum += *value * *weight as f64;
            denom += *weight as f64;
        }
        if denom <= f64::EPSILON {
            None
        } else {
            Some(weighted_sum / denom)
        }
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

    #[getter]
    pub fn value(&self) -> Option<(f64, f64)> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MIDPOINT {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MIDPOINT {
    #[new]
    pub fn new(period: usize) -> Self {
        MIDPOINT {
            period,
            buffer: VecDeque::with_capacity(period),
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
        let max_v = self.buffer.iter().fold(f64::NEG_INFINITY, |a, b| a.max(*b));
        let min_v = self.buffer.iter().fold(f64::INFINITY, |a, b| a.min(*b));
        self.current_value = Some((max_v + min_v) / 2.0);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MAX {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MAX {
    #[new]
    pub fn new(period: usize) -> Self {
        MAX {
            period,
            buffer: VecDeque::with_capacity(period),
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
        let max_v = self.buffer.iter().fold(f64::NEG_INFINITY, |a, b| a.max(*b));
        self.current_value = Some(max_v);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MIN {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MIN {
    #[new]
    pub fn new(period: usize) -> Self {
        MIN {
            period,
            buffer: VecDeque::with_capacity(period),
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
        let min_v = self.buffer.iter().fold(f64::INFINITY, |a, b| a.min(*b));
        self.current_value = Some(min_v);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MAXINDEX {
    period: usize,
    buffer: VecDeque<f64>,
    total_count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MAXINDEX {
    #[new]
    pub fn new(period: usize) -> Self {
        MAXINDEX {
            period,
            buffer: VecDeque::with_capacity(period),
            total_count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.total_count += 1;
        self.buffer.push_back(value);
        if self.buffer.len() > self.period {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period {
            self.current_value = None;
            return None;
        }
        let mut max_idx = 0usize;
        let mut max_v = f64::NEG_INFINITY;
        for (i, v) in self.buffer.iter().enumerate() {
            if *v >= max_v {
                max_v = *v;
                max_idx = i;
            }
        }
        let start = self.total_count - self.period;
        self.current_value = Some((start + max_idx) as f64);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MININDEX {
    period: usize,
    buffer: VecDeque<f64>,
    total_count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MININDEX {
    #[new]
    pub fn new(period: usize) -> Self {
        MININDEX {
            period,
            buffer: VecDeque::with_capacity(period),
            total_count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.total_count += 1;
        self.buffer.push_back(value);
        if self.buffer.len() > self.period {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period {
            self.current_value = None;
            return None;
        }
        let mut min_idx = 0usize;
        let mut min_v = f64::INFINITY;
        for (i, v) in self.buffer.iter().enumerate() {
            if *v <= min_v {
                min_v = *v;
                min_idx = i;
            }
        }
        let start = self.total_count - self.period;
        self.current_value = Some((start + min_idx) as f64);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MINMAXINDEX {
    period: usize,
    buffer: VecDeque<f64>,
    total_count: usize,
    current_value: Option<(f64, f64)>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MINMAXINDEX {
    #[new]
    pub fn new(period: usize) -> Self {
        MINMAXINDEX {
            period,
            buffer: VecDeque::with_capacity(period),
            total_count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<(f64, f64)> {
        self.total_count += 1;
        self.buffer.push_back(value);
        if self.buffer.len() > self.period {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period {
            self.current_value = None;
            return None;
        }
        let mut min_idx = 0usize;
        let mut min_v = f64::INFINITY;
        let mut max_idx = 0usize;
        let mut max_v = f64::NEG_INFINITY;
        for (i, v) in self.buffer.iter().enumerate() {
            if *v <= min_v {
                min_v = *v;
                min_idx = i;
            }
            if *v >= max_v {
                max_v = *v;
                max_idx = i;
            }
        }
        let start = self.total_count - self.period;
        self.current_value = Some(((start + min_idx) as f64, (start + max_idx) as f64));
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<(f64, f64)> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MINMAX {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<(f64, f64)>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MINMAX {
    #[new]
    pub fn new(period: usize) -> Self {
        MINMAX {
            period,
            buffer: VecDeque::with_capacity(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<(f64, f64)> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period {
            self.current_value = None;
            return None;
        }
        let max_v = self.buffer.iter().fold(f64::NEG_INFINITY, |a, b| a.max(*b));
        let min_v = self.buffer.iter().fold(f64::INFINITY, |a, b| a.min(*b));
        self.current_value = Some((min_v, max_v));
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<(f64, f64)> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct SUM {
    period: usize,
    buffer: VecDeque<f64>,
    sum: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SUM {
    #[new]
    pub fn new(period: usize) -> Self {
        SUM {
            period,
            buffer: VecDeque::with_capacity(period),
            sum: 0.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        self.sum += value;
        if self.buffer.len() > self.period
            && let Some(removed) = self.buffer.pop_front()
        {
            self.sum -= removed;
        }
        if self.buffer.len() < self.period {
            self.current_value = None;
            return None;
        }
        self.current_value = Some(self.sum);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct AVGDEV {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl AVGDEV {
    #[new]
    pub fn new(period: usize) -> Self {
        AVGDEV {
            period,
            buffer: VecDeque::with_capacity(period),
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
        let mean = self.buffer.iter().sum::<f64>() / self.period as f64;
        let avgdev =
            self.buffer.iter().map(|v| (*v - mean).abs()).sum::<f64>() / self.period as f64;
        self.current_value = Some(avgdev);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct RANGE {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl RANGE {
    #[new]
    pub fn new(period: usize) -> Self {
        RANGE {
            period,
            buffer: VecDeque::with_capacity(period),
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
        let max_v = self.buffer.iter().fold(f64::NEG_INFINITY, |a, b| a.max(*b));
        let min_v = self.buffer.iter().fold(f64::INFINITY, |a, b| a.min(*b));
        self.current_value = Some(max_v - min_v);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct LN {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LN {
    #[new]
    pub fn new() -> Self {
        LN {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = if value > 0.0 {
            Some(value.ln())
        } else {
            Some(f64::NAN)
        };
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct LOG10 {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LOG10 {
    #[new]
    pub fn new() -> Self {
        LOG10 {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = if value > 0.0 {
            Some(value.log10())
        } else {
            Some(f64::NAN)
        };
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct SQRT {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SQRT {
    #[new]
    pub fn new() -> Self {
        SQRT {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = if value >= 0.0 {
            Some(value.sqrt())
        } else {
            Some(f64::NAN)
        };
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CEIL {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl CEIL {
    #[new]
    pub fn new() -> Self {
        CEIL {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.ceil());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct FLOOR {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl FLOOR {
    #[new]
    pub fn new() -> Self {
        FLOOR {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.floor());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct SIN {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SIN {
    #[new]
    pub fn new() -> Self {
        SIN {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.sin());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct COS {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl COS {
    #[new]
    pub fn new() -> Self {
        COS {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.cos());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct TAN {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TAN {
    #[new]
    pub fn new() -> Self {
        TAN {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.tan());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ASIN {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ASIN {
    #[new]
    pub fn new() -> Self {
        ASIN {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = if (-1.0..=1.0).contains(&value) {
            Some(value.asin())
        } else {
            Some(f64::NAN)
        };
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ACOS {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ACOS {
    #[new]
    pub fn new() -> Self {
        ACOS {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = if (-1.0..=1.0).contains(&value) {
            Some(value.acos())
        } else {
            Some(f64::NAN)
        };
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ATAN {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ATAN {
    #[new]
    pub fn new() -> Self {
        ATAN {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.atan());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct SINH {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SINH {
    #[new]
    pub fn new() -> Self {
        SINH {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.sinh());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct COSH {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl COSH {
    #[new]
    pub fn new() -> Self {
        COSH {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.cosh());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct TANH {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TANH {
    #[new]
    pub fn new() -> Self {
        TANH {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.tanh());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct EXP {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl EXP {
    #[new]
    pub fn new() -> Self {
        EXP {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.exp());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ABS {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ABS {
    #[new]
    pub fn new() -> Self {
        ABS {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.abs());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct SIGN {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SIGN {
    #[new]
    pub fn new() -> Self {
        SIGN {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let sign = if value > 0.0 {
            1.0
        } else if value < 0.0 {
            -1.0
        } else {
            0.0
        };
        self.current_value = Some(sign);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ADD {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ADD {
    #[new]
    pub fn new() -> Self {
        ADD {
            current_value: None,
        }
    }

    pub fn update(&mut self, left: f64, right: f64) -> Option<f64> {
        self.current_value = Some(left + right);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct SUB {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SUB {
    #[new]
    pub fn new() -> Self {
        SUB {
            current_value: None,
        }
    }

    pub fn update(&mut self, left: f64, right: f64) -> Option<f64> {
        self.current_value = Some(left - right);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MULT {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MULT {
    #[new]
    pub fn new() -> Self {
        MULT {
            current_value: None,
        }
    }

    pub fn update(&mut self, left: f64, right: f64) -> Option<f64> {
        self.current_value = Some(left * right);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct DIV {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl DIV {
    #[new]
    pub fn new() -> Self {
        DIV {
            current_value: None,
        }
    }

    pub fn update(&mut self, left: f64, right: f64) -> Option<f64> {
        self.current_value = if right.abs() <= f64::EPSILON {
            Some(f64::NAN)
        } else {
            Some(left / right)
        };
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MAX2 {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MAX2 {
    #[new]
    pub fn new() -> Self {
        MAX2 {
            current_value: None,
        }
    }

    pub fn update(&mut self, left: f64, right: f64) -> Option<f64> {
        self.current_value = Some(left.max(right));
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MIN2 {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MIN2 {
    #[new]
    pub fn new() -> Self {
        MIN2 {
            current_value: None,
        }
    }

    pub fn update(&mut self, left: f64, right: f64) -> Option<f64> {
        self.current_value = Some(left.min(right));
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CLIP {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl CLIP {
    #[new]
    pub fn new() -> Self {
        CLIP {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64, min_value: f64, max_value: f64) -> Option<f64> {
        let lo = min_value.min(max_value);
        let hi = min_value.max(max_value);
        self.current_value = Some(value.clamp(lo, hi));
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ROUND {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ROUND {
    #[new]
    pub fn new() -> Self {
        ROUND {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.round());
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct POW {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl POW {
    #[new]
    pub fn new() -> Self {
        POW {
            current_value: None,
        }
    }

    pub fn update(&mut self, left: f64, right: f64) -> Option<f64> {
        self.current_value = Some(left.powf(right));
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct MOD {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MOD {
    #[new]
    pub fn new() -> Self {
        MOD {
            current_value: None,
        }
    }

    pub fn update(&mut self, left: f64, right: f64) -> Option<f64> {
        self.current_value = if right.abs() <= f64::EPSILON {
            Some(f64::NAN)
        } else {
            Some(left % right)
        };
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CLAMP01 {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl CLAMP01 {
    #[new]
    pub fn new() -> Self {
        CLAMP01 {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value.clamp(0.0, 1.0));
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct SQ {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SQ {
    #[new]
    pub fn new() -> Self {
        SQ {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value * value);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CUBE {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl CUBE {
    #[new]
    pub fn new() -> Self {
        CUBE {
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.current_value = Some(value * value * value);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SMA>()?;
    m.add_class::<EMA>()?;
    m.add_class::<MACD>()?;
    m.add_class::<DEMA>()?;
    m.add_class::<TRIX>()?;
    m.add_class::<TEMA>()?;
    m.add_class::<KAMA>()?;
    m.add_class::<WMA>()?;
    m.add_class::<APO>()?;
    m.add_class::<PPO>()?;
    m.add_class::<TRIMA>()?;
    m.add_class::<T3>()?;
    m.add_class::<HT_TRENDLINE>()?;
    m.add_class::<MAMA>()?;
    m.add_class::<MIDPOINT>()?;
    m.add_class::<MAX>()?;
    m.add_class::<MIN>()?;
    m.add_class::<MAXINDEX>()?;
    m.add_class::<MININDEX>()?;
    m.add_class::<MINMAXINDEX>()?;
    m.add_class::<MINMAX>()?;
    m.add_class::<SUM>()?;
    m.add_class::<AVGDEV>()?;
    m.add_class::<RANGE>()?;
    m.add_class::<LN>()?;
    m.add_class::<LOG10>()?;
    m.add_class::<SQRT>()?;
    m.add_class::<CEIL>()?;
    m.add_class::<FLOOR>()?;
    m.add_class::<SIN>()?;
    m.add_class::<COS>()?;
    m.add_class::<TAN>()?;
    m.add_class::<ASIN>()?;
    m.add_class::<ACOS>()?;
    m.add_class::<ATAN>()?;
    m.add_class::<SINH>()?;
    m.add_class::<COSH>()?;
    m.add_class::<TANH>()?;
    m.add_class::<EXP>()?;
    m.add_class::<ABS>()?;
    m.add_class::<SIGN>()?;
    m.add_class::<ADD>()?;
    m.add_class::<SUB>()?;
    m.add_class::<MULT>()?;
    m.add_class::<DIV>()?;
    m.add_class::<MAX2>()?;
    m.add_class::<MIN2>()?;
    m.add_class::<CLIP>()?;
    m.add_class::<ROUND>()?;
    m.add_class::<POW>()?;
    m.add_class::<MOD>()?;
    m.add_class::<CLAMP01>()?;
    m.add_class::<SQ>()?;
    m.add_class::<CUBE>()?;
    Ok(())
}
