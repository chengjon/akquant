//! Candlestick pattern recognition indicators (CDL series).
//!
//! Each pattern returns: +100 (bullish), -100 (bearish), 0 (no pattern).

use std::collections::VecDeque;

use numpy::PyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

// --- Common OHLC ring buffer ---

#[derive(Debug, Clone)]
struct OhlcBar {
    open: f64,
    high: f64,
    low: f64,
    close: f64,
}

fn push_bar(buf: &mut VecDeque<OhlcBar>, bar: OhlcBar, max: usize) {
    buf.push_back(bar);
    while buf.len() > max {
        buf.pop_front();
    }
}

fn body(o: f64, c: f64) -> f64 {
    (c - o).abs()
}

fn upper_shadow(o: f64, h: f64, c: f64) -> f64 {
    h - o.max(c)
}

fn lower_shadow(o: f64, l: f64, c: f64) -> f64 {
    o.min(c) - l
}

fn is_bullish(o: f64, c: f64) -> bool {
    c > o
}

fn is_bearish(o: f64, c: f64) -> bool {
    c < o
}

fn range(h: f64, l: f64) -> f64 {
    h - l
}

fn is_doji(o: f64, h: f64, l: f64, c: f64) -> bool {
    let r = range(h, l);
    r > f64::EPSILON && body(o, c) <= r * 0.1
}

// --- CDLDOJI ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLDOJI {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLDOJI {
    #[new]
    pub fn new() -> Self {
        CDLDOJI {
            bars: VecDeque::with_capacity(1),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 1);
        let bar = &self.bars[0];
        let result = if is_doji(bar.open, bar.high, bar.low, bar.close) {
            100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLHAMMER ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLHAMMER {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLHAMMER {
    #[new]
    pub fn new() -> Self {
        CDLHAMMER {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        // Prior bar should be bearish (downtrend context)
        let downtrend = is_bearish(prev.open, prev.close);
        let r = range(cur.high, cur.low);
        let result = if downtrend
            && r > f64::EPSILON
            && body(cur.open, cur.close) <= r * 0.33
            && lower_shadow(cur.open, cur.low, cur.close) >= r * 0.6
            && upper_shadow(cur.open, cur.high, cur.close) <= r * 0.1
        {
            100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLHANGINGMAN ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLHANGINGMAN {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLHANGINGMAN {
    #[new]
    pub fn new() -> Self {
        CDLHANGINGMAN {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let uptrend = is_bullish(prev.open, prev.close);
        let r = range(cur.high, cur.low);
        let result = if uptrend
            && r > f64::EPSILON
            && body(cur.open, cur.close) <= r * 0.33
            && lower_shadow(cur.open, cur.low, cur.close) >= r * 0.6
            && upper_shadow(cur.open, cur.high, cur.close) <= r * 0.1
        {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLENGULFING ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDL_ENGULFING {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDL_ENGULFING {
    #[new]
    pub fn new() -> Self {
        CDL_ENGULFING {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let result = if is_bearish(prev.open, prev.close)
            && is_bullish(cur.open, cur.close)
            && cur.open <= prev.close
            && cur.close >= prev.open
        {
            100 // Bullish engulfing
        } else if is_bullish(prev.open, prev.close)
            && is_bearish(cur.open, cur.close)
            && cur.open >= prev.close
            && cur.close <= prev.open
        {
            -100 // Bearish engulfing
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLHARAMI ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDL_HARAMI {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDL_HARAMI {
    #[new]
    pub fn new() -> Self {
        CDL_HARAMI {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let prev_body_top = prev.open.max(prev.close);
        let prev_body_bot = prev.open.min(prev.close);
        let cur_body_top = cur.open.max(cur.close);
        let cur_body_bot = cur.open.min(cur.close);
        let result = if is_bearish(prev.open, prev.close)
            && is_bullish(cur.open, cur.close)
            && cur_body_top < prev_body_top
            && cur_body_bot > prev_body_bot
        {
            100
        } else if is_bullish(prev.open, prev.close)
            && is_bearish(cur.open, cur.close)
            && cur_body_top < prev_body_top
            && cur_body_bot > prev_body_bot
        {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLMORNINGSTAR ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDL_MORNINGSTAR {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDL_MORNINGSTAR {
    #[new]
    pub fn new() -> Self {
        CDL_MORNINGSTAR {
            bars: VecDeque::with_capacity(3),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 3);
        if self.bars.len() < 3 {
            self.current_value = None;
            return None;
        }
        let b0 = &self.bars[self.bars.len() - 3];
        let b1 = &self.bars[self.bars.len() - 2];
        let b2 = &self.bars[self.bars.len() - 1];
        let b0_body = body(b0.open, b0.close);
        let b2_body = body(b2.open, b2.close);
        let result = if is_bearish(b0.open, b0.close)
            && b0_body > f64::EPSILON
            && body(b1.open, b1.close) <= b0_body * 0.33 // Small body (star)
            && is_bullish(b2.open, b2.close)
            && b2_body > f64::EPSILON
            && b2.close >= (b0.open + b0.close) / 2.0
        {
            100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLEVENINGSTAR ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDL_EVENINGSTAR {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDL_EVENINGSTAR {
    #[new]
    pub fn new() -> Self {
        CDL_EVENINGSTAR {
            bars: VecDeque::with_capacity(3),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 3);
        if self.bars.len() < 3 {
            self.current_value = None;
            return None;
        }
        let b0 = &self.bars[self.bars.len() - 3];
        let b1 = &self.bars[self.bars.len() - 2];
        let b2 = &self.bars[self.bars.len() - 1];
        let b0_body = body(b0.open, b0.close);
        let b2_body = body(b2.open, b2.close);
        let result = if is_bullish(b0.open, b0.close)
            && b0_body > f64::EPSILON
            && body(b1.open, b1.close) <= b0_body * 0.33
            && is_bearish(b2.open, b2.close)
            && b2_body > f64::EPSILON
            && b2.close <= (b0.open + b0.close) / 2.0
        {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDL3BLACKCROWS ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDL_3BLACKCROWS {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDL_3BLACKCROWS {
    #[new]
    pub fn new() -> Self {
        CDL_3BLACKCROWS {
            bars: VecDeque::with_capacity(3),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 3);
        if self.bars.len() < 3 {
            self.current_value = None;
            return None;
        }
        let b0 = &self.bars[self.bars.len() - 3];
        let b1 = &self.bars[self.bars.len() - 2];
        let b2 = &self.bars[self.bars.len() - 1];
        let result = if is_bearish(b0.open, b0.close)
            && is_bearish(b1.open, b1.close)
            && is_bearish(b2.open, b2.close)
            && b1.open < b0.open
            && b1.close > b0.close // Opens within prior body
            && b2.open < b1.open
            && b2.close > b1.close
        {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDL3WHITESOLDIERS ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDL_3WHITESOLDIERS {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDL_3WHITESOLDIERS {
    #[new]
    pub fn new() -> Self {
        CDL_3WHITESOLDIERS {
            bars: VecDeque::with_capacity(3),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 3);
        if self.bars.len() < 3 {
            self.current_value = None;
            return None;
        }
        let b0 = &self.bars[self.bars.len() - 3];
        let b1 = &self.bars[self.bars.len() - 2];
        let b2 = &self.bars[self.bars.len() - 1];
        let result = if is_bullish(b0.open, b0.close)
            && is_bullish(b1.open, b1.close)
            && is_bullish(b2.open, b2.close)
            && b1.open > b0.open
            && b1.close < b0.close // Opens within prior body
            && b2.open > b1.open
            && b2.close < b1.close
        {
            100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLSHOOTINGSTAR ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDL_SHOOTINGSTAR {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDL_SHOOTINGSTAR {
    #[new]
    pub fn new() -> Self {
        CDL_SHOOTINGSTAR {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let uptrend = is_bullish(prev.open, prev.close);
        let r = range(cur.high, cur.low);
        let result = if uptrend
            && r > f64::EPSILON
            && body(cur.open, cur.close) <= r * 0.33
            && upper_shadow(cur.open, cur.high, cur.close) >= r * 0.6
            && lower_shadow(cur.open, cur.low, cur.close) <= r * 0.1
        {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLPIERCING ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLPIERCING {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLPIERCING {
    #[new]
    pub fn new() -> Self {
        CDLPIERCING {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let prev_mid = (prev.open + prev.close) / 2.0;
        let result = if is_bearish(prev.open, prev.close)
            && is_bullish(cur.open, cur.close)
            && cur.open < prev.low  // Gap down
            && cur.close > prev_mid  // Close above midpoint
            && cur.close < prev.open // But not above prior open
        {
            100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLDARKCLOUDCOVER ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLDARKCLOUDCOVER {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLDARKCLOUDCOVER {
    #[new]
    pub fn new() -> Self {
        CDLDARKCLOUDCOVER {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let prev_mid = (prev.open + prev.close) / 2.0;
        let result = if is_bullish(prev.open, prev.close)
            && is_bearish(cur.open, cur.close)
            && cur.open > prev.high // Gap up
            && cur.close < prev_mid  // Close below midpoint
            && cur.close > prev.open // But above prior open
        {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLHARAMICROSS ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLHARAMICROSS {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLHARAMICROSS {
    #[new]
    pub fn new() -> Self {
        CDLHARAMICROSS {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let prev_body_top = prev.open.max(prev.close);
        let prev_body_bot = prev.open.min(prev.close);
        let cur_body_top = cur.open.max(cur.close);
        let cur_body_bot = cur.open.min(cur.close);
        let result = if is_doji(cur.open, cur.high, cur.low, cur.close)
            && prev_body_top > cur_body_top
            && prev_body_bot < cur_body_bot
        {
            if is_bullish(prev.open, prev.close) {
                -100 // Bearish reversal signal
            } else {
                100 // Bullish reversal signal
            }
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLMARUBOZU ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLMARUBOZU {
    current_value: Option<i32>,
}

#[pymethods]
impl CDLMARUBOZU {
    #[new]
    pub fn new() -> Self {
        CDLMARUBOZU { current_value: None }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        let r = range(high, low);
        let result = if r > f64::EPSILON {
            let us = upper_shadow(open, high, close);
            let ls = lower_shadow(open, low, close);
            if us / r <= 0.05 && ls / r <= 0.05 {
                if is_bullish(open, close) {
                    100
                } else if is_bearish(open, close) {
                    -100
                } else {
                    0
                }
            } else {
                0
            }
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLKICKING ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLKICKING {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLKICKING {
    #[new]
    pub fn new() -> Self {
        CDLKICKING {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let is_marubozu = |b: &OhlcBar| -> bool {
            let r = range(b.high, b.low);
            r > f64::EPSILON
                && upper_shadow(b.open, b.high, b.close) / r <= 0.05
                && lower_shadow(b.open, b.low, b.close) / r <= 0.05
        };
        let result = if is_marubozu(prev) && is_marubozu(cur) {
            let gap = prev.close - cur.open; // For bullish: prev bearish close < cur bullish open
            if is_bearish(prev.open, prev.close)
                && is_bullish(cur.open, cur.close)
                && gap.abs() > f64::EPSILON
            {
                100
            } else if is_bullish(prev.open, prev.close)
                && is_bearish(cur.open, cur.close)
                && gap.abs() > f64::EPSILON
            {
                -100
            } else {
                0
            }
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLSPINNINGTOP ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLSPINNINGTOP {
    current_value: Option<i32>,
}

#[pymethods]
impl CDLSPINNINGTOP {
    #[new]
    pub fn new() -> Self {
        CDLSPINNINGTOP { current_value: None }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        let r = range(high, low);
        let result = if r > f64::EPSILON {
            let b = body(open, close);
            let us = upper_shadow(open, high, close);
            let ls = lower_shadow(open, low, close);
            // Small body (≤30% of range) and both shadows present (≥10% each)
            if b <= r * 0.3 && b > r * 0.05 && us >= r * 0.1 && ls >= r * 0.1 {
                if is_bullish(open, close) {
                    100
                } else if is_bearish(open, close) {
                    -100
                } else {
                    100 // Neutral doji-ish
                }
            } else {
                0
            }
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLRISEFALL3METHODS ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLRISEFALL3METHODS {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLRISEFALL3METHODS {
    #[new]
    pub fn new() -> Self {
        CDLRISEFALL3METHODS {
            bars: VecDeque::with_capacity(5),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 5);
        if self.bars.len() < 5 {
            self.current_value = None;
            return None;
        }
        let b0 = &self.bars[self.bars.len() - 5];
        let b1 = &self.bars[self.bars.len() - 4];
        let b2 = &self.bars[self.bars.len() - 3];
        let b3 = &self.bars[self.bars.len() - 2];
        let b4 = &self.bars[self.bars.len() - 1];

        // Rising 3 Methods: bullish + 3 small bearish + bullish
        let rising = is_bullish(b0.open, b0.close)
            && is_bearish(b1.open, b1.close)
            && is_bearish(b2.open, b2.close)
            && is_bearish(b3.open, b3.close)
            && is_bullish(b4.open, b4.close)
            && b4.close > b0.close
            && b1.open < b0.high && b1.close > b0.low
            && b3.open < b0.high && b3.close > b0.low;

        // Falling 3 Methods: bearish + 3 small bullish + bearish
        let falling = is_bearish(b0.open, b0.close)
            && is_bullish(b1.open, b1.close)
            && is_bullish(b2.open, b2.close)
            && is_bullish(b3.open, b3.close)
            && is_bearish(b4.open, b4.close)
            && b4.close < b0.close
            && b1.open > b0.low && b1.close < b0.high
            && b3.open > b0.low && b3.close < b0.high;

        let result = if rising {
            100
        } else if falling {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLTHRUSTING ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLTHRUSTING {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLTHRUSTING {
    #[new]
    pub fn new() -> Self {
        CDLTHRUSTING {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let prev_mid = (prev.open + prev.close) / 2.0;
        let result = if is_bearish(prev.open, prev.close)
            && is_bullish(cur.open, cur.close)
            && cur.open < prev.close  // Opens below prior close
            && cur.close >= prev.close // Closes above prior close
            && cur.close < prev_mid    // But below midpoint
        {
            -100 // Bearish continuation
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLINNECK ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLINNECK {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLINNECK {
    #[new]
    pub fn new() -> Self {
        CDLINNECK {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let result = if is_bearish(prev.open, prev.close)
            && is_bullish(cur.open, cur.close)
            && cur.open < prev.close
            && (cur.close - prev.close).abs() <= body(prev.open, prev.close) * 0.05
        {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- CDLONNECK ---

#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
pub struct CDLONNECK {
    bars: VecDeque<OhlcBar>,
    current_value: Option<i32>,
}

#[pymethods]
impl CDLONNECK {
    #[new]
    pub fn new() -> Self {
        CDLONNECK {
            bars: VecDeque::with_capacity(2),
            current_value: None,
        }
    }

    pub fn update(&mut self, open: f64, high: f64, low: f64, close: f64) -> Option<i32> {
        push_bar(&mut self.bars, OhlcBar { open, high, low, close }, 2);
        if self.bars.len() < 2 {
            self.current_value = None;
            return None;
        }
        let prev = &self.bars[self.bars.len() - 2];
        let cur = &self.bars[self.bars.len() - 1];
        let result = if is_bearish(prev.open, prev.close)
            && is_bullish(cur.open, cur.close)
            && cur.open < prev.close
            && (cur.close - prev.low).abs() <= body(prev.open, prev.close) * 0.05
        {
            -100
        } else {
            0
        };
        self.current_value = Some(result);
        Some(result)
    }

    pub fn update_many_ohlc<'py>(
        &mut self,
        py: Python<'py>,
        opens: Vec<f64>,
        highs: Vec<f64>,
        lows: Vec<f64>,
        closes: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<i32>>> {
        let n = opens.len();
        if highs.len() != n || lows.len() != n || closes.len() != n {
            return Err(PyValueError::new_err("OHLC length mismatch"));
        }
        let mut out = Vec::with_capacity(n);
        for i in 0..n {
            out.push(self.update(opens[i], highs[i], lows[i], closes[i]).unwrap_or(0));
        }
        Ok(PyArray1::from_vec(py, out))
    }

    #[getter]
    pub fn value(&self) -> Option<i32> {
        self.current_value
    }
}

// --- Registration ---

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<CDLDOJI>()?;
    m.add_class::<CDLHAMMER>()?;
    m.add_class::<CDLHANGINGMAN>()?;
    m.add_class::<CDL_ENGULFING>()?;
    m.add_class::<CDL_HARAMI>()?;
    m.add_class::<CDL_MORNINGSTAR>()?;
    m.add_class::<CDL_EVENINGSTAR>()?;
    m.add_class::<CDL_3BLACKCROWS>()?;
    m.add_class::<CDL_3WHITESOLDIERS>()?;
    m.add_class::<CDL_SHOOTINGSTAR>()?;
    m.add_class::<CDLPIERCING>()?;
    m.add_class::<CDLDARKCLOUDCOVER>()?;
    m.add_class::<CDLHARAMICROSS>()?;
    m.add_class::<CDLMARUBOZU>()?;
    m.add_class::<CDLKICKING>()?;
    m.add_class::<CDLSPINNINGTOP>()?;
    m.add_class::<CDLRISEFALL3METHODS>()?;
    m.add_class::<CDLTHRUSTING>()?;
    m.add_class::<CDLINNECK>()?;
    m.add_class::<CDLONNECK>()?;
    Ok(())
}
