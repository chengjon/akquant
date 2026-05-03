//! Hilbert Transform cycle indicators (HT series).
//!
//! Implements Ehlers' Hilbert Transform decomposition for extracting
//! instantaneous phase, frequency, and phasor components from price data.

use numpy::PyArray1;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

const DEG2RAD: f64 = std::f64::consts::PI / 180.0;
const RAD2DEG: f64 = 180.0 / std::f64::consts::PI;
const TWO_PI: f64 = 2.0 * std::f64::consts::PI;

/// Shared Hilbert Transform computation engine.
///
/// Uses Ehlers' adaptive Hilbert Transform decomposition with:
/// - 7-bar weighted smoothing
/// - Adaptive detrender
/// - In-phase (I) and quadrature (Q) component extraction
/// - Homodyne discriminator for instantaneous period measurement
#[derive(Debug, Clone)]
struct HilbertEngine {
    // Ring buffers holding last 7 values for each decomposition stage
    smooth: VecDeque<f64>,
    detrender: VecDeque<f64>,
    q1: VecDeque<f64>,
    i1: VecDeque<f64>,
    jI: VecDeque<f64>,
    jQ: VecDeque<f64>,

    // Adaptive period tracking
    period: f64,
    smooth_period: f64,

    // Count of bars processed
    count: usize,

    // Price buffer for initial smoothing (need 4 bars)
    price_buf: VecDeque<f64>,
}

impl HilbertEngine {
    fn new() -> Self {
        HilbertEngine {
            smooth: VecDeque::with_capacity(7),
            detrender: VecDeque::with_capacity(7),
            q1: VecDeque::with_capacity(7),
            i1: VecDeque::with_capacity(7),
            jI: VecDeque::with_capacity(7),
            jQ: VecDeque::with_capacity(7),
            period: 15.0,
            smooth_period: 15.0,
            count: 0,
            price_buf: VecDeque::with_capacity(4),
        }
    }

    /// Push a value into a ring buffer, keeping at most 7 entries.
    #[inline]
    fn push7(buf: &mut VecDeque<f64>, val: f64) {
        buf.push_back(val);
        if buf.len() > 7 {
            buf.pop_front();
        }
    }

    /// Get value at offset from the end (0 = most recent).
    #[inline]
    fn back(buf: &VecDeque<f64>, offset: usize) -> f64 {
        buf.iter().nth_back(offset).copied().unwrap_or(0.0)
    }

    /// Ehlers Hilbert coefficient filter applied to a 7-element buffer.
    /// Uses coefficients: 0.0962, 0.5769, 0.5769, 0.0962 at positions 0,2,4,6.
    #[inline]
    fn hilbert_coeff(buf: &VecDeque<f64>) -> f64 {
        if buf.len() < 7 {
            return 0.0;
        }
        0.0962 * Self::back(buf, 0)
            + 0.5769 * Self::back(buf, 2)
            - 0.5769 * Self::back(buf, 4)
            - 0.0962 * Self::back(buf, 6)
    }

    /// Process one price bar and return (in_phase, quadrature, phase_degrees, period).
    /// Returns None during warmup (~33 bars).
    fn update(&mut self, price: f64) -> Option<(f64, f64, f64, f64)> {
        self.count += 1;

        // Step 1: Smooth price using 4-bar WMA
        Self::push7(&mut self.price_buf, price);
        if self.price_buf.len() < 4 {
            return None;
        }
        let sm = (4.0 * Self::back(&self.price_buf, 0)
            + 3.0 * Self::back(&self.price_buf, 1)
            + 2.0 * Self::back(&self.price_buf, 2)
            + 1.0 * Self::back(&self.price_buf, 3))
            / 10.0;
        Self::push7(&mut self.smooth, sm);

        // Need at least 7 smoothed bars for the Hilbert decomposition
        if self.smooth.len() < 7 {
            return None;
        }

        // Step 2: Adaptive adjustment factor based on period
        let adj = 0.075 * self.period + 0.54;

        // Step 3: Detrender via Hilbert coefficients
        let det = Self::hilbert_coeff(&self.smooth) * adj;
        Self::push7(&mut self.detrender, det);

        if self.detrender.len() < 7 {
            return None;
        }

        // Step 4: Compute Q1 (quadrature) from detrender
        let q1_val = Self::hilbert_coeff(&self.detrender) * adj;
        Self::push7(&mut self.q1, q1_val);

        if self.q1.len() < 7 {
            return None;
        }

        // Step 5: I1 (in-phase) is detrender delayed by 3 bars
        let i1_val = Self::back(&self.detrender, 3);
        Self::push7(&mut self.i1, i1_val);

        if self.i1.len() < 7 {
            return None;
        }

        // Step 6: Apply Hilbert correction to I1 and Q1
        let jI_val = Self::hilbert_coeff(&self.i1) * adj;
        let jQ_val = Self::hilbert_coeff(&self.q1) * adj;
        Self::push7(&mut self.jI, jI_val);
        Self::push7(&mut self.jQ, jQ_val);

        // Step 7: Compute phase from atan2(q1, i1)
        let phase = if i1_val.abs() > f64::EPSILON || q1_val.abs() > f64::EPSILON {
            let mut ph = q1_val.atan2(i1_val) * RAD2DEG;
            if ph < 0.0 {
                ph += 360.0;
            }
            if ph >= 360.0 {
                ph -= 360.0;
            }
            ph
        } else {
            0.0
        };

        // Step 8: Homodyne discriminator for instantaneous period
        let re = i1_val * jI_val + q1_val * jQ_val;
        let im = i1_val * jQ_val - q1_val * jI_val;

        if re.abs() > f64::EPSILON || im.abs() > f64::EPSILON {
            let mut inst_period = TWO_PI / im.atan2(re);
            // Clamp period to reasonable range
            inst_period = inst_period.clamp(1.0, 100.0);
            // EMA smoothing of period (alpha = 0.33)
            self.period = 0.33 * inst_period + 0.67 * self.period;
        }

        // Smooth the period output
        self.smooth_period = 0.33 * self.period + 0.67 * self.smooth_period;

        // Additional warmup: need ~33 bars for stable output
        if self.count < 33 {
            return None;
        }

        Some((i1_val, q1_val, phase, self.smooth_period))
    }
}

// ---------------------------------------------------------------------------
// HT_DCPERIOD - Dominant Cycle Period
// ---------------------------------------------------------------------------

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
#[allow(non_camel_case_types)]
pub struct HT_DCPERIOD {
    engine: HilbertEngine,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl HT_DCPERIOD {
    #[new]
    pub fn new() -> Self {
        HT_DCPERIOD {
            engine: HilbertEngine::new(),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let result = self.engine.update(value);
        if let Some((_i, _q, _phase, period)) = result {
            self.current_value = Some(period);
            self.current_value
        } else {
            self.current_value = None;
            None
        }
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

// ---------------------------------------------------------------------------
// HT_DCPHASE - Dominant Cycle Phase
// ---------------------------------------------------------------------------

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
#[allow(non_camel_case_types)]
pub struct HT_DCPHASE {
    engine: HilbertEngine,
    current_value: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl HT_DCPHASE {
    #[new]
    pub fn new() -> Self {
        HT_DCPHASE {
            engine: HilbertEngine::new(),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<f64> {
        let result = self.engine.update(value);
        if let Some((_i, _q, phase, _period)) = result {
            self.current_value = Some(phase);
            self.current_value
        } else {
            self.current_value = None;
            None
        }
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

// ---------------------------------------------------------------------------
// HT_PHASOR - Phasor Components (in_phase, quadrature)
// ---------------------------------------------------------------------------

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone)]
#[allow(non_camel_case_types)]
pub struct HT_PHASOR {
    engine: HilbertEngine,
    current_value: Option<(f64, f64)>,
}

#[gen_stub_pymethods]
#[pymethods]
impl HT_PHASOR {
    #[new]
    pub fn new() -> Self {
        HT_PHASOR {
            engine: HilbertEngine::new(),
            current_value: None,
        }
    }

    pub fn update(&mut self, value: f64) -> Option<(f64, f64)> {
        let result = self.engine.update(value);
        if let Some((i, q, _phase, _period)) = result {
            self.current_value = Some((i, q));
            self.current_value
        } else {
            self.current_value = None;
            None
        }
    }

    pub fn update_many_pair<'py>(
        &mut self,
        py: Python<'py>,
        values: Vec<f64>,
    ) -> (Bound<'py, PyArray1<f64>>, Bound<'py, PyArray1<f64>>) {
        let mut in_phase = Vec::with_capacity(values.len());
        let mut quadrature = Vec::with_capacity(values.len());
        for value in values {
            if let Some((i, q)) = self.update(value) {
                in_phase.push(i);
                quadrature.push(q);
            } else {
                in_phase.push(f64::NAN);
                quadrature.push(f64::NAN);
            }
        }
        (
            PyArray1::from_vec(py, in_phase),
            PyArray1::from_vec(py, quadrature),
        )
    }

    #[getter]
    pub fn value(&self) -> Option<(f64, f64)> {
        self.current_value
    }
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<HT_DCPERIOD>()?;
    m.add_class::<HT_DCPHASE>()?;
    m.add_class::<HT_PHASOR>()?;
    Ok(())
}
