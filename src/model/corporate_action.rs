use chrono::NaiveDate;
use pyo3::prelude::*;
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

#[pyclass(eq, eq_int, from_py_object)]
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum CorporateActionType {
    Split,    // 拆股/合股
    Dividend, // 分红
}

impl pyo3_stub_gen::PyStubType for CorporateActionType {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::with_module("akquant.CorporateActionType", "akquant".into())
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CorporateAction {
    #[pyo3(get, set)]
    pub symbol: String,
    #[pyo3(get, set)]
    pub date: NaiveDate, // 除权除息日 (Ex-Date)
    #[pyo3(get, set)]
    pub action_type: CorporateActionType,
    pub value: Decimal, // Split: ratio (e.g., 2.0 for 1-to-2 split), Dividend: amount per share
}

use pyo3_stub_gen::derive::*;

#[gen_stub_pymethods]
#[pymethods]
impl CorporateAction {
    #[new]
    pub fn new(
        symbol: String,
        date: NaiveDate,
        action_type: CorporateActionType,
        value: &Bound<'_, PyAny>,
    ) -> PyResult<Self> {
        use crate::model::market_data::extract_decimal;
        let val = extract_decimal(value)?;
        Ok(Self {
            symbol,
            date,
            action_type,
            value: val,
        })
    }

    #[getter]
    fn get_value(&self) -> f64 {
        use rust_decimal::prelude::ToPrimitive;
        self.value.to_f64().unwrap_or(0.0)
    }

    #[setter]
    fn set_value(&mut self, value: &Bound<'_, PyAny>) -> PyResult<()> {
        use crate::model::market_data::extract_decimal;
        self.value = extract_decimal(value)?;
        Ok(())
    }
}
