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
    #[pyo3(get, set)]
    pub account_mode: String,
    #[pyo3(get, set)]
    pub enable_short_sell: bool,
    #[pyo3(get, set)]
    pub initial_margin_ratio: f64,
    #[pyo3(get, set)]
    pub maintenance_margin_ratio: f64,
    #[pyo3(get, set)]
    pub financing_rate_annual: f64,
    #[pyo3(get, set)]
    pub borrow_rate_annual: f64,
    #[pyo3(get, set)]
    pub allow_force_liquidation: bool,
    #[pyo3(get, set)]
    pub liquidation_priority: String,
    pub max_portfolio_delta: Option<Decimal>,
    pub max_portfolio_gamma: Option<Decimal>,
    pub max_portfolio_vega: Option<Decimal>,
    pub slot_max_delta: Option<Decimal>,
    pub slot_max_gamma: Option<Decimal>,
    pub slot_max_vega: Option<Decimal>,
    #[pyo3(get, set)]
    pub option_risk_free_rate: f64,
    #[pyo3(get, set)]
    pub option_default_volatility: f64,
    #[pyo3(get, set)]
    pub option_greek_per_underlying: bool,
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
            account_mode: "cash".to_string(),
            enable_short_sell: false,
            initial_margin_ratio: 1.0,
            maintenance_margin_ratio: 0.3,
            financing_rate_annual: 0.08,
            borrow_rate_annual: 0.10,
            allow_force_liquidation: true,
            liquidation_priority: "short_first".to_string(),
            max_portfolio_delta: None,
            max_portfolio_gamma: None,
            max_portfolio_vega: None,
            slot_max_delta: None,
            slot_max_gamma: None,
            slot_max_vega: None,
            option_risk_free_rate: 0.02,
            option_default_volatility: 0.25,
            option_greek_per_underlying: true,
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

    #[getter]
    pub fn get_max_portfolio_delta(&self) -> Option<f64> {
        self.max_portfolio_delta
            .map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_max_portfolio_delta(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.max_portfolio_delta = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }

    #[getter]
    pub fn get_max_portfolio_gamma(&self) -> Option<f64> {
        self.max_portfolio_gamma
            .map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_max_portfolio_gamma(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.max_portfolio_gamma = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }

    #[getter]
    pub fn get_max_portfolio_vega(&self) -> Option<f64> {
        self.max_portfolio_vega
            .map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_max_portfolio_vega(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.max_portfolio_vega = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }

    #[getter]
    pub fn get_slot_max_delta(&self) -> Option<f64> {
        self.slot_max_delta.map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_slot_max_delta(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.slot_max_delta = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }

    #[getter]
    pub fn get_slot_max_gamma(&self) -> Option<f64> {
        self.slot_max_gamma.map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_slot_max_gamma(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.slot_max_gamma = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }

    #[getter]
    pub fn get_slot_max_vega(&self) -> Option<f64> {
        self.slot_max_vega.map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    pub fn set_slot_max_vega(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        self.slot_max_vega = match value {
            Some(v) => Some(extract_decimal(v)?),
            None => None,
        };
        Ok(())
    }
}

impl RiskConfig {
    pub fn is_margin_account(&self) -> bool {
        self.account_mode.eq_ignore_ascii_case("margin")
    }

    pub fn stock_initial_margin_ratio(&self) -> Decimal {
        Decimal::from_f64(self.initial_margin_ratio).unwrap_or(Decimal::ONE)
    }

    pub fn maintenance_margin_ratio_decimal(&self) -> Decimal {
        Decimal::from_f64(self.maintenance_margin_ratio).unwrap_or(Decimal::ZERO)
    }

    pub fn liquidation_short_first(&self) -> bool {
        !self.liquidation_priority.eq_ignore_ascii_case("long_first")
    }
}
