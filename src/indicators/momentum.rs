use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct RSI {
    period: usize,
    prev_price: Option<f64>,
    avg_gain: f64,
    avg_loss: f64,
    count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl RSI {
    #[new]
    pub fn new(period: usize) -> Self {
        RSI {
            period,
            prev_price: None,
            avg_gain: 0.0,
            avg_loss: 0.0,
            count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        if let Some(prev) = self.prev_price {
            let change = value - prev;
            let gain = if change > 0.0 { change } else { 0.0 };
            let loss = if change < 0.0 { -change } else { 0.0 };

            if self.count < self.period {
                self.avg_gain += gain;
                self.avg_loss += loss;
                self.count += 1;

                if self.count == self.period {
                    self.avg_gain /= self.period as f64;
                    self.avg_loss /= self.period as f64;
                }
            } else {
                self.avg_gain =
                    (self.avg_gain * (self.period as f64 - 1.0) + gain) / self.period as f64;
                self.avg_loss =
                    (self.avg_loss * (self.period as f64 - 1.0) + loss) / self.period as f64;
            }
        }

        self.prev_price = Some(value);

        if self.count < self.period {
            return None;
        }

        let rs = if self.avg_loss == 0.0 {
            100.0
        } else {
            self.avg_gain / self.avg_loss
        };

        let rsi = 100.0 - (100.0 / (1.0 + rs));
        self.current_value = Some(rsi);
        Some(rsi)
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct ROC {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ROC {
    #[new]
    pub fn new(period: usize) -> Self {
        ROC {
            period,
            buffer: VecDeque::with_capacity(period + 1),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period + 1 {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period + 1 {
            self.current_value = None;
            return None;
        }
        let base = *self.buffer.front()?;
        if base.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some((value - base) / base * 100.0);
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
pub struct ROCP {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ROCP {
    #[new]
    pub fn new(period: usize) -> Self {
        ROCP {
            period,
            buffer: VecDeque::with_capacity(period + 1),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period + 1 {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period + 1 {
            self.current_value = None;
            return None;
        }
        let base = *self.buffer.front()?;
        if base.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some((value - base) / base);
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
pub struct ROCR {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ROCR {
    #[new]
    pub fn new(period: usize) -> Self {
        ROCR {
            period,
            buffer: VecDeque::with_capacity(period + 1),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period + 1 {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period + 1 {
            self.current_value = None;
            return None;
        }
        let base = *self.buffer.front()?;
        if base.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some(value / base);
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
pub struct ROCR100 {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ROCR100 {
    #[new]
    pub fn new(period: usize) -> Self {
        ROCR100 {
            period,
            buffer: VecDeque::with_capacity(period + 1),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period + 1 {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period + 1 {
            self.current_value = None;
            return None;
        }
        let base = *self.buffer.front()?;
        if base.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some((value / base) * 100.0);
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
pub struct MOM {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MOM {
    #[new]
    pub fn new(period: usize) -> Self {
        MOM {
            period,
            buffer: VecDeque::with_capacity(period + 1),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        if self.buffer.len() > self.period + 1 {
            self.buffer.pop_front();
        }
        if self.buffer.len() < self.period + 1 {
            self.current_value = None;
            return None;
        }
        let base = *self.buffer.front()?;
        self.current_value = Some(value - base);
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
pub struct WILLR {
    period: usize,
    highs: VecDeque<f64>,
    lows: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl WILLR {
    #[new]
    pub fn new(period: usize) -> Self {
        WILLR {
            period,
            highs: VecDeque::with_capacity(period),
            lows: VecDeque::with_capacity(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64) -> Option<f64> {
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
        let highest = self
            .highs
            .iter()
            .fold(f64::NEG_INFINITY, |acc, x| acc.max(*x));
        let lowest = self.lows.iter().fold(f64::INFINITY, |acc, x| acc.min(*x));
        let range = highest - lowest;
        if range.abs() <= f64::EPSILON {
            self.current_value = Some(0.0);
        } else {
            self.current_value = Some(-100.0 * (highest - close) / range);
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
pub struct CMO {
    period: usize,
    prev_close: Option<f64>,
    gains: VecDeque<f64>,
    losses: VecDeque<f64>,
    gain_sum: f64,
    loss_sum: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl CMO {
    #[new]
    pub fn new(period: usize) -> Self {
        CMO {
            period,
            prev_close: None,
            gains: VecDeque::with_capacity(period),
            losses: VecDeque::with_capacity(period),
            gain_sum: 0.0,
            loss_sum: 0.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, close: f64) -> Option<f64> {
        let Some(prev) = self.prev_close else {
            self.prev_close = Some(close);
            self.current_value = None;
            return None;
        };
        let delta = close - prev;
        let gain = delta.max(0.0);
        let loss = (-delta).max(0.0);
        self.gains.push_back(gain);
        self.losses.push_back(loss);
        self.gain_sum += gain;
        self.loss_sum += loss;
        if self.gains.len() > self.period {
            if let Some(removed) = self.gains.pop_front() {
                self.gain_sum -= removed;
            }
            if let Some(removed) = self.losses.pop_front() {
                self.loss_sum -= removed;
            }
        }
        self.prev_close = Some(close);
        if self.gains.len() < self.period {
            self.current_value = None;
            return None;
        }
        let denom = self.gain_sum + self.loss_sum;
        if denom <= f64::EPSILON {
            self.current_value = Some(0.0);
        } else {
            self.current_value = Some(100.0 * (self.gain_sum - self.loss_sum) / denom);
        }
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RSI>()?;
    m.add_class::<ROC>()?;
    m.add_class::<ROCP>()?;
    m.add_class::<ROCR>()?;
    m.add_class::<ROCR100>()?;
    m.add_class::<MOM>()?;
    m.add_class::<WILLR>()?;
    m.add_class::<CMO>()?;
    Ok(())
}
