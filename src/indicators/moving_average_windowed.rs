use numpy::PyArray1;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

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

pub fn register_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
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
    Ok(())
}
