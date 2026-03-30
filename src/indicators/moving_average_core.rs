use numpy::PyArray1;
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

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SMA>()?;
    m.add_class::<EMA>()?;
    m.add_class::<WMA>()?;
    m.add_class::<TRIMA>()?;
    Ok(())
}
