use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct OBV {
    prev_close: Option<f64>,
    current_obv: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl OBV {
    #[new]
    pub fn new() -> Self {
        OBV {
            prev_close: None,
            current_obv: 0.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, close: f64, volume: f64) -> Option<f64> {
        if let Some(prev_close) = self.prev_close {
            if close > prev_close {
                self.current_obv += volume;
            } else if close < prev_close {
                self.current_obv -= volume;
            }
        } else {
            self.current_obv = 0.0;
        }
        self.prev_close = Some(close);
        self.current_value = Some(self.current_obv);
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
pub struct MFI {
    period: usize,
    prev_typical: Option<f64>,
    pos_flows: VecDeque<f64>,
    neg_flows: VecDeque<f64>,
    pos_sum: f64,
    neg_sum: f64,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl MFI {
    #[new]
    pub fn new(period: usize) -> Self {
        MFI {
            period,
            prev_typical: None,
            pos_flows: VecDeque::with_capacity(period),
            neg_flows: VecDeque::with_capacity(period),
            pos_sum: 0.0,
            neg_sum: 0.0,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64, volume: f64) -> Option<f64> {
        let typical = (high + low + close) / 3.0;
        let raw_flow = typical * volume;
        let Some(prev_typical) = self.prev_typical else {
            self.prev_typical = Some(typical);
            self.current_value = None;
            return None;
        };
        let mut pos = 0.0;
        let mut neg = 0.0;
        if typical > prev_typical {
            pos = raw_flow;
        } else if typical < prev_typical {
            neg = raw_flow;
        }
        self.pos_flows.push_back(pos);
        self.neg_flows.push_back(neg);
        self.pos_sum += pos;
        self.neg_sum += neg;
        if self.pos_flows.len() > self.period {
            if let Some(removed) = self.pos_flows.pop_front() {
                self.pos_sum -= removed;
            }
            if let Some(removed) = self.neg_flows.pop_front() {
                self.neg_sum -= removed;
            }
        }
        self.prev_typical = Some(typical);
        if self.pos_flows.len() < self.period {
            self.current_value = None;
            return None;
        }
        if self.neg_sum <= f64::EPSILON {
            if self.pos_sum <= f64::EPSILON {
                self.current_value = Some(50.0);
            } else {
                self.current_value = Some(100.0);
            }
        } else {
            let mr = self.pos_sum / self.neg_sum;
            self.current_value = Some(100.0 - (100.0 / (1.0 + mr)));
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
pub struct BOP {
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl BOP {
    #[new]
    pub fn new() -> Self {
        BOP {
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<f64> {
        let denom = high - low;
        let value = if denom.abs() <= f64::EPSILON {
            0.0
        } else {
            (close - open) / denom
        };
        self.current_value = Some(value);
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
pub struct AD {
    current_value: Option<f64>,
    current_ad: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl AD {
    #[new]
    pub fn new() -> Self {
        AD {
            current_value: None,
            current_ad: 0.0,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64, volume: f64) -> Option<f64> {
        let denom = high - low;
        let mfm = if denom.abs() <= f64::EPSILON {
            0.0
        } else {
            ((close - low) - (high - close)) / denom
        };
        let mfv = mfm * volume;
        self.current_ad += mfv;
        self.current_value = Some(self.current_ad);
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
pub struct ADOSC {
    slow_period: usize,
    current_ad: f64,
    fast_ema: Option<f64>,
    slow_ema: Option<f64>,
    k_fast: f64,
    k_slow: f64,
    count: usize,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl ADOSC {
    #[new]
    pub fn new(fast_period: usize, slow_period: usize) -> Self {
        ADOSC {
            slow_period,
            current_ad: 0.0,
            fast_ema: None,
            slow_ema: None,
            k_fast: 2.0 / (fast_period as f64 + 1.0),
            k_slow: 2.0 / (slow_period as f64 + 1.0),
            count: 0,
            current_value: None,
        }
    }

    pub fn update(&mut self, high: f64, low: f64, close: f64, volume: f64) -> Option<f64> {
        let denom = high - low;
        let mfm = if denom.abs() <= f64::EPSILON {
            0.0
        } else {
            ((close - low) - (high - close)) / denom
        };
        let mfv = mfm * volume;
        self.current_ad += mfv;
        self.count += 1;
        self.fast_ema = Some(match self.fast_ema {
            Some(prev) => prev + self.k_fast * (self.current_ad - prev),
            None => self.current_ad,
        });
        self.slow_ema = Some(match self.slow_ema {
            Some(prev) => prev + self.k_slow * (self.current_ad - prev),
            None => self.current_ad,
        });
        if self.count < self.slow_period {
            self.current_value = None;
            return None;
        }
        self.current_value = Some(self.fast_ema? - self.slow_ema?);
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<OBV>()?;
    m.add_class::<MFI>()?;
    m.add_class::<BOP>()?;
    m.add_class::<AD>()?;
    m.add_class::<ADOSC>()?;
    Ok(())
}
