use crate::model::market_data::extract_decimal;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rust_decimal::Decimal;
use rust_decimal::prelude::*;

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Default)]
/// 风控配置.
pub struct RiskConfig {
    pub max_order_size: Option<Decimal>,
    pub max_order_value: Option<Decimal>,
    pub max_position_size: Option<Decimal>,
    #[pyo3(get, set)]
    pub restricted_list: Vec<String>,
    #[pyo3(get, set)]
    pub active: bool,
    #[pyo3(get, set)]
    pub check_cash: bool,
    #[pyo3(get, set)]
    pub safety_margin: f64,
}

#[pymethods]
impl RiskConfig {
    #[new]
    pub fn new() -> Self {
        Self {
            max_order_size: None,
            max_order_value: None,
            max_position_size: None,
            restricted_list: Vec::new(),
            active: true,
            check_cash: true,
            safety_margin: 0.0001,
        }
    }

    #[getter]
    pub fn get_max_order_size(&self) -> Option<f64> {
        self.max_order_size.map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_max_order_size(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.max_order_size = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }

    #[getter]
    pub fn get_max_order_value(&self) -> Option<f64> {
        self.max_order_value.map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_max_order_value(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.max_order_value = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }

    #[getter]
    pub fn get_max_position_size(&self) -> Option<f64> {
        self.max_position_size
            .map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_max_position_size(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.max_position_size = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }
}
