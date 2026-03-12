use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

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

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

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

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

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

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct LINEARREG {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LINEARREG {
    #[new]
    pub fn new(period: usize) -> Self {
        LINEARREG {
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
        let n = self.period as f64;
        let sum_x = n * (n - 1.0) / 2.0;
        let sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0;
        let sum_y = self.buffer.iter().sum::<f64>();
        let sum_xy = self
            .buffer
            .iter()
            .enumerate()
            .map(|(i, y)| i as f64 * *y)
            .sum::<f64>();
        let denom = n * sum_x2 - sum_x * sum_x;
        if denom.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
            return self.current_value;
        }
        let slope = (n * sum_xy - sum_x * sum_y) / denom;
        let intercept = (sum_y - slope * sum_x) / n;
        self.current_value = Some(intercept + slope * (n - 1.0));
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
pub struct LINEARREG_SLOPE {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LINEARREG_SLOPE {
    #[new]
    pub fn new(period: usize) -> Self {
        LINEARREG_SLOPE {
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
        let n = self.period as f64;
        let sum_x = n * (n - 1.0) / 2.0;
        let sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0;
        let sum_y = self.buffer.iter().sum::<f64>();
        let sum_xy = self
            .buffer
            .iter()
            .enumerate()
            .map(|(i, y)| i as f64 * *y)
            .sum::<f64>();
        let denom = n * sum_x2 - sum_x * sum_x;
        if denom.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
            return self.current_value;
        }
        self.current_value = Some((n * sum_xy - sum_x * sum_y) / denom);
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
pub struct LINEARREG_INTERCEPT {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LINEARREG_INTERCEPT {
    #[new]
    pub fn new(period: usize) -> Self {
        LINEARREG_INTERCEPT {
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
        let n = self.period as f64;
        let sum_x = n * (n - 1.0) / 2.0;
        let sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0;
        let sum_y = self.buffer.iter().sum::<f64>();
        let sum_xy = self
            .buffer
            .iter()
            .enumerate()
            .map(|(i, y)| i as f64 * *y)
            .sum::<f64>();
        let denom = n * sum_x2 - sum_x * sum_x;
        if denom.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
            return self.current_value;
        }
        let slope = (n * sum_xy - sum_x * sum_y) / denom;
        self.current_value = Some((sum_y - slope * sum_x) / n);
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
pub struct LINEARREG_ANGLE {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LINEARREG_ANGLE {
    #[new]
    pub fn new(period: usize) -> Self {
        LINEARREG_ANGLE {
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
        let n = self.period as f64;
        let sum_x = n * (n - 1.0) / 2.0;
        let sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0;
        let sum_y = self.buffer.iter().sum::<f64>();
        let sum_xy = self
            .buffer
            .iter()
            .enumerate()
            .map(|(i, y)| i as f64 * *y)
            .sum::<f64>();
        let denom = n * sum_x2 - sum_x * sum_x;
        if denom.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
            return self.current_value;
        }
        let slope = (n * sum_xy - sum_x * sum_y) / denom;
        self.current_value = Some(slope.atan().to_degrees());
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
pub struct TSF {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl TSF {
    #[new]
    pub fn new(period: usize) -> Self {
        TSF {
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
        let n = self.period as f64;
        let sum_x = n * (n - 1.0) / 2.0;
        let sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0;
        let sum_y = self.buffer.iter().sum::<f64>();
        let sum_xy = self
            .buffer
            .iter()
            .enumerate()
            .map(|(i, y)| i as f64 * *y)
            .sum::<f64>();
        let denom = n * sum_x2 - sum_x * sum_x;
        if denom.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
            return self.current_value;
        }
        let slope = (n * sum_xy - sum_x * sum_y) / denom;
        let intercept = (sum_y - slope * sum_x) / n;
        self.current_value = Some(intercept + slope * n);
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
pub struct CORREL {
    period: usize,
    buffer_x: VecDeque<f64>,
    buffer_y: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl CORREL {
    #[new]
    pub fn new(period: usize) -> Self {
        CORREL {
            period,
            buffer_x: VecDeque::with_capacity(period),
            buffer_y: VecDeque::with_capacity(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, x: f64, y: f64) -> Option<f64> {
        self.buffer_x.push_back(x);
        self.buffer_y.push_back(y);
        if self.buffer_x.len() > self.period {
            self.buffer_x.pop_front();
            self.buffer_y.pop_front();
        }
        if self.buffer_x.len() < self.period {
            self.current_value = None;
            return None;
        }
        let n = self.period as f64;
        let sum_x = self.buffer_x.iter().sum::<f64>();
        let sum_y = self.buffer_y.iter().sum::<f64>();
        let sum_xy = self
            .buffer_x
            .iter()
            .zip(self.buffer_y.iter())
            .map(|(a, b)| *a * *b)
            .sum::<f64>();
        let sum_x2 = self.buffer_x.iter().map(|v| v * v).sum::<f64>();
        let sum_y2 = self.buffer_y.iter().map(|v| v * v).sum::<f64>();
        let num = n * sum_xy - sum_x * sum_y;
        let den_x = n * sum_x2 - sum_x * sum_x;
        let den_y = n * sum_y2 - sum_y * sum_y;
        let den = (den_x * den_y).sqrt();
        if den <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some(num / den);
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
pub struct BETA {
    period: usize,
    buffer_x: VecDeque<f64>,
    buffer_y: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl BETA {
    #[new]
    pub fn new(period: usize) -> Self {
        BETA {
            period,
            buffer_x: VecDeque::with_capacity(period),
            buffer_y: VecDeque::with_capacity(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, x: f64, y: f64) -> Option<f64> {
        self.buffer_x.push_back(x);
        self.buffer_y.push_back(y);
        if self.buffer_x.len() > self.period {
            self.buffer_x.pop_front();
            self.buffer_y.pop_front();
        }
        if self.buffer_x.len() < self.period {
            self.current_value = None;
            return None;
        }
        let n = self.period as f64;
        let sum_x = self.buffer_x.iter().sum::<f64>();
        let sum_y = self.buffer_y.iter().sum::<f64>();
        let sum_xy = self
            .buffer_x
            .iter()
            .zip(self.buffer_y.iter())
            .map(|(a, b)| *a * *b)
            .sum::<f64>();
        let sum_y2 = self.buffer_y.iter().map(|v| v * v).sum::<f64>();
        let cov_num = n * sum_xy - sum_x * sum_y;
        let var_y_num = n * sum_y2 - sum_y * sum_y;
        if var_y_num.abs() <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            self.current_value = Some(cov_num / var_y_num);
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
pub struct COVAR {
    period: usize,
    buffer_x: VecDeque<f64>,
    buffer_y: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl COVAR {
    #[new]
    pub fn new(period: usize) -> Self {
        COVAR {
            period,
            buffer_x: VecDeque::with_capacity(period),
            buffer_y: VecDeque::with_capacity(period),
            current_value: None,
        }
    }

    pub fn update(&mut self, x: f64, y: f64) -> Option<f64> {
        self.buffer_x.push_back(x);
        self.buffer_y.push_back(y);
        if self.buffer_x.len() > self.period {
            self.buffer_x.pop_front();
            self.buffer_y.pop_front();
        }
        if self.buffer_x.len() < self.period {
            self.current_value = None;
            return None;
        }
        let mean_x = self.buffer_x.iter().sum::<f64>() / self.period as f64;
        let mean_y = self.buffer_y.iter().sum::<f64>() / self.period as f64;
        let cov = self
            .buffer_x
            .iter()
            .zip(self.buffer_y.iter())
            .map(|(a, b)| (*a - mean_x) * (*b - mean_y))
            .sum::<f64>()
            / self.period as f64;
        self.current_value = Some(cov);
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
pub struct LINEARREG_R2 {
    period: usize,
    buffer: VecDeque<f64>,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl LINEARREG_R2 {
    #[new]
    pub fn new(period: usize) -> Self {
        LINEARREG_R2 {
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

        let n = self.period as f64;
        let sum_x = n * (n - 1.0) / 2.0;
        let sum_x2 = n * (n - 1.0) * (2.0 * n - 1.0) / 6.0;
        let sum_y = self.buffer.iter().sum::<f64>();
        let sum_xy = self
            .buffer
            .iter()
            .enumerate()
            .map(|(i, y)| i as f64 * *y)
            .sum::<f64>();
        let sum_y2 = self.buffer.iter().map(|v| v * v).sum::<f64>();

        let num = n * sum_xy - sum_x * sum_y;
        let den_x = n * sum_x2 - sum_x * sum_x;
        let den_y = n * sum_y2 - sum_y * sum_y;
        let den = (den_x * den_y).sqrt();
        if den <= f64::EPSILON {
            self.current_value = Some(f64::NAN);
        } else {
            let r = num / den;
            self.current_value = Some(r * r);
        }
        self.current_value
    }

    #[getter]
    pub fn value(&self) -> Option<f64> {
        self.current_value
    }
}

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<CCI>()?;
    m.add_class::<ADX>()?;
    m.add_class::<DX>()?;
    m.add_class::<ADXR>()?;
    m.add_class::<AROON>()?;
    m.add_class::<AROONOSC>()?;
    m.add_class::<STOCH>()?;
    m.add_class::<SAR>()?;
    m.add_class::<PLUS_DI>()?;
    m.add_class::<MINUS_DI>()?;
    m.add_class::<ULTOSC>()?;
    m.add_class::<LINEARREG>()?;
    m.add_class::<LINEARREG_SLOPE>()?;
    m.add_class::<LINEARREG_INTERCEPT>()?;
    m.add_class::<LINEARREG_ANGLE>()?;
    m.add_class::<TSF>()?;
    m.add_class::<CORREL>()?;
    m.add_class::<BETA>()?;
    m.add_class::<COVAR>()?;
    m.add_class::<LINEARREG_R2>()?;
    Ok(())
}
