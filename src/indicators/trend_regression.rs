use numpy::PyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::VecDeque;

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

    pub fn update_many_dual<'py>(
        &mut self,
        py: Python<'py>,
        xs: Vec<f64>,
        ys: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<f64>>> {
        if xs.len() != ys.len() {
            return Err(PyValueError::new_err("xs/ys length mismatch"));
        }
        let mut out = Vec::with_capacity(xs.len());
        for (x, y) in xs.into_iter().zip(ys.into_iter()) {
            out.push(self.update(x, y).unwrap_or(f64::NAN));
        }
        Ok(PyArray1::from_vec(py, out))
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

    pub fn update_many_dual<'py>(
        &mut self,
        py: Python<'py>,
        xs: Vec<f64>,
        ys: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<f64>>> {
        if xs.len() != ys.len() {
            return Err(PyValueError::new_err("xs/ys length mismatch"));
        }
        let mut out = Vec::with_capacity(xs.len());
        for (x, y) in xs.into_iter().zip(ys.into_iter()) {
            out.push(self.update(x, y).unwrap_or(f64::NAN));
        }
        Ok(PyArray1::from_vec(py, out))
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

    pub fn update_many_dual<'py>(
        &mut self,
        py: Python<'py>,
        xs: Vec<f64>,
        ys: Vec<f64>,
    ) -> PyResult<Bound<'py, PyArray1<f64>>> {
        if xs.len() != ys.len() {
            return Err(PyValueError::new_err("xs/ys length mismatch"));
        }
        let mut out = Vec::with_capacity(xs.len());
        for (x, y) in xs.into_iter().zip(ys.into_iter()) {
            out.push(self.update(x, y).unwrap_or(f64::NAN));
        }
        Ok(PyArray1::from_vec(py, out))
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
