use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

/// 简单移动平均线 (SMA).
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
    /// 创建 SMA 指标.
    ///
    /// :param period: 周期
    #[new]
    pub fn new(period: usize) -> Self {
        SMA {
            period,
            buffer: VecDeque::with_capacity(period),
            sum: 0.0,
        }
    }

    /// 更新指标值.
    ///
    /// :param value: 新数据点
    /// :return: 当前 SMA 值 (如果数据不足则返回 None)
    pub fn update(&mut self, value: f64) -> Option<f64> {
        self.buffer.push_back(value);
        self.sum += value;

        if self.buffer.len() > self.period
            && let Some(removed) = self.buffer.pop_front() {
                self.sum -= removed;
            }

        if self.buffer.len() == self.period {
            Some(self.sum / self.period as f64)
        } else {
            None
        }
    }

    /// 获取当前指标值.
    ///
    /// :return: 当前 SMA 值
    #[getter]
    pub fn value(&self) -> Option<f64> {
        if self.buffer.len() == self.period {
            Some(self.sum / self.period as f64)
        } else {
            None
        }
    }

    /// 检查指标是否就绪.
    ///
    /// :return: 是否已收集足够数据
    #[getter]
    pub fn is_ready(&self) -> bool {
        self.buffer.len() == self.period
    }
}

/// 指数移动平均线 (EMA).
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
    /// 创建 EMA 指标.
    ///
    /// :param period: 周期
    #[new]
    pub fn new(period: usize) -> Self {
        EMA {
            period,
            k: 2.0 / (period as f64 + 1.0),
            current_value: None,
        }
    }

    /// 更新指标值.
    ///
    /// :param value: 新数据点
    /// :return: 当前 EMA 值
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

/// 平滑异同移动平均线 (MACD).
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
    /// 创建 MACD 指标.
    ///
    /// :param fast_period: 快线周期 (通常 12)
    /// :param slow_period: 慢线周期 (通常 26)
    /// :param signal_period: 信号线周期 (通常 9)
    #[new]
    pub fn new(fast_period: usize, slow_period: usize, signal_period: usize) -> Self {
        MACD {
            fast_ema: EMA::new(fast_period),
            slow_ema: EMA::new(slow_period),
            signal_ema: EMA::new(signal_period),
        }
    }

    /// 更新指标值.
    ///
    /// :param value: 新数据点
    /// :return: (DIF, DEA, MACD柱)
    pub fn update(&mut self, value: f64) -> Option<(f64, f64, f64)> {
        let fast = self.fast_ema.update(value)?;
        let slow = self.slow_ema.update(value)?;

        let macd_line = fast - slow;
        let signal_line = self.signal_ema.update(macd_line)?;
        let histogram = macd_line - signal_line;

        Some((macd_line, signal_line, histogram))
    }

    /// 获取当前指标值.
    ///
    /// :return: (DIF, DEA, MACD柱)
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

/// 相对强弱指数 (RSI).
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
    /// 创建 RSI 指标.
    ///
    /// :param period: 周期 (通常 14)
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

    /// 更新指标值.
    ///
    /// :param value: 新数据点 (通常是收盘价)
    /// :return: 当前 RSI 值
    pub fn update(&mut self, value: f64) -> Option<f64> {
        if let Some(prev) = self.prev_price {
            let change = value - prev;
            let gain = if change > 0.0 { change } else { 0.0 };
            let loss = if change < 0.0 { -change } else { 0.0 };

            if self.count < self.period {
                // Initial accumulation phase
                self.avg_gain += gain;
                self.avg_loss += loss;
                self.count += 1;

                if self.count == self.period {
                    // Calculate initial average
                    self.avg_gain /= self.period as f64;
                    self.avg_loss /= self.period as f64;
                }
            } else {
                // Wilder's Smoothing
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
            self.smoothed_tr =
                self.smoothed_tr - (self.smoothed_tr / self.period as f64) + tr;
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

/// 布林带 (Bollinger Bands).
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
    /// 创建布林带指标.
    ///
    /// :param period: 周期 (通常 20)
    /// :param multiplier: 标准差倍数 (通常 2.0)
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

    /// 更新指标值.
    ///
    /// :param value: 新数据点
    /// :return: (上轨, 中轨, 下轨)
    pub fn update(&mut self, value: f64) -> Option<(f64, f64, f64)> {
        self.buffer.push_back(value);
        self.sum += value;
        self.sum_sq += value * value;

        if self.buffer.len() > self.period
            && let Some(removed) = self.buffer.pop_front() {
                self.sum -= removed;
                self.sum_sq -= removed * removed;
            }

        if self.buffer.len() == self.period {
            let mean = self.sum / self.period as f64;
            // Variance = E[X^2] - (E[X])^2
            // Use max(0.0) to avoid negative variance due to floating point errors
            let variance = (self.sum_sq / self.period as f64 - mean * mean).max(0.0);
            let std_dev = variance.sqrt();

            let upper = mean + self.multiplier * std_dev;
            let lower = mean - self.multiplier * std_dev;

            Some((upper, mean, lower))
        } else {
            None
        }
    }

    /// 获取当前指标值.
    ///
    /// :return: (上轨, 中轨, 下轨)
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

/// 平均真实波幅 (ATR).
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
    /// 创建 ATR 指标.
    ///
    /// :param period: 周期 (通常 14)
    #[new]
    pub fn new(period: usize) -> Self {
        ATR {
            period,
            prev_close: None,
            smoothed_tr: 0.0,
            count: 0,
        }
    }

    /// 更新指标值.
    ///
    /// :param high: 最高价
    /// :param low: 最低价
    /// :param close: 收盘价
    /// :return: 当前 ATR 值
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

        // Wilder's Smoothing
        self.smoothed_tr =
            (self.smoothed_tr * (self.period as f64 - 1.0) + tr) / self.period as f64;
        Some(self.smoothed_tr)
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
