use super::market_data::extract_decimal;
use super::types::{OrderRole, OrderSide, OrderStatus, OrderType, TimeInForce};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use serde::{Deserialize, Serialize};

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize)]
/// 订单.
///
/// :ivar id: 订单ID
/// :ivar symbol: 标的代码
/// :ivar side: 交易方向
/// :ivar order_type: 订单类型
/// :ivar quantity: 数量
/// :ivar price: 价格 (限价单有效)
/// :ivar time_in_force: 订单有效期
/// :ivar trigger_price: 触发价格 (止损/止盈单)
/// :ivar trail_offset: 跟踪止损偏移量
/// :ivar trail_reference_price: 跟踪止损参考价
/// :ivar graph_id: 复杂订单图 ID
/// :ivar parent_order_id: 父订单 ID
/// :ivar order_role: 复杂订单节点角色
/// :ivar status: 订单状态
/// :ivar filled_quantity: 已成交数量
/// :ivar average_filled_price: 成交均价
pub struct Order {
    #[pyo3(get)]
    pub id: String,
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub side: OrderSide,
    #[pyo3(get)]
    pub order_type: OrderType,
    pub quantity: Decimal,
    pub price: Option<Decimal>,
    #[pyo3(get)]
    pub time_in_force: TimeInForce,
    pub trigger_price: Option<Decimal>,
    #[serde(default)]
    pub trail_offset: Option<Decimal>,
    #[serde(default)]
    pub trail_reference_price: Option<Decimal>,
    #[pyo3(get)]
    #[serde(default)]
    pub graph_id: Option<String>,
    #[pyo3(get)]
    #[serde(default)]
    pub parent_order_id: Option<String>,
    #[pyo3(get)]
    #[serde(default)]
    pub order_role: OrderRole,
    #[pyo3(get, set)]
    pub status: OrderStatus,
    pub filled_quantity: Decimal,
    pub average_filled_price: Option<Decimal>,
    #[pyo3(get)]
    pub created_at: i64,
    #[pyo3(get)]
    pub updated_at: i64,
    pub commission: Decimal,
    #[pyo3(get, set)]
    pub tag: String,
    #[pyo3(get)]
    pub reject_reason: String,
    #[pyo3(get)]
    #[serde(default)]
    pub owner_strategy_id: Option<String>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Order {
    /// 创建订单.
    ///
    /// :param id: 订单ID
    /// :param symbol: 标的代码
    /// :param side: 交易方向
    /// :param order_type: 订单类型
    /// :param quantity: 数量
    /// :param price: 价格
    /// :param time_in_force: 订单有效期 (可选，默认 Day)
    /// :param trigger_price: 触发价格 (可选)
    /// :param created_at: 创建时间戳 (可选，默认 0)
    /// :param tag: 订单标签 (可选，默认 "")
    #[new]
    #[pyo3(signature = (id, symbol, side, order_type, quantity, price=None, time_in_force=None, trigger_price=None, created_at=None, tag=None, owner_strategy_id=None, graph_id=None, parent_order_id=None, order_role=None, trail_offset=None, trail_reference_price=None))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        id: String,
        symbol: String,
        side: OrderSide,
        order_type: OrderType,
        quantity: &Bound<'_, PyAny>,
        price: Option<&Bound<'_, PyAny>>,
        time_in_force: Option<TimeInForce>,
        trigger_price: Option<&Bound<'_, PyAny>>,
        created_at: Option<i64>,
        tag: Option<String>,
        owner_strategy_id: Option<String>,
        graph_id: Option<String>,
        parent_order_id: Option<String>,
        order_role: Option<OrderRole>,
        trail_offset: Option<&Bound<'_, PyAny>>,
        trail_reference_price: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let created_at_ts = created_at.unwrap_or(0);
        Ok(Order {
            id,
            symbol,
            side,
            order_type,
            quantity: extract_decimal(quantity)?,
            price: match price {
                Some(p) => Some(extract_decimal(p)?),
                None => None,
            },
            time_in_force: time_in_force.unwrap_or(TimeInForce::Day),
            trigger_price: match trigger_price {
                Some(p) => Some(extract_decimal(p)?),
                None => None,
            },
            trail_offset: match trail_offset {
                Some(v) => Some(extract_decimal(v)?),
                None => None,
            },
            trail_reference_price: match trail_reference_price {
                Some(v) => Some(extract_decimal(v)?),
                None => None,
            },
            graph_id,
            parent_order_id,
            order_role: order_role.unwrap_or_default(),
            status: OrderStatus::New,
            filled_quantity: Decimal::ZERO,
            average_filled_price: None,
            created_at: created_at_ts,
            updated_at: created_at_ts,
            commission: Decimal::ZERO,
            tag: tag.unwrap_or_default(),
            reject_reason: String::new(),
            owner_strategy_id,
        })
    }

    #[getter]
    /// 获取手续费.
    /// :return: 手续费
    fn get_commission(&self) -> f64 {
        self.commission.to_f64().unwrap_or_default()
    }

    #[getter]
    /// 获取订单数量.
    /// :return: 订单数量
    fn get_quantity(&self) -> f64 {
        self.quantity.to_f64().unwrap_or_default()
    }

    #[getter]
    /// 获取订单价格.
    /// :return: 订单价格 (如果为市价单则返回 None)
    fn get_price(&self) -> Option<f64> {
        self.price.map(|d| d.to_f64().unwrap_or_default())
    }

    #[getter]
    /// 获取触发价格.
    /// :return: 触发价格 (如果未设置则返回 None)
    fn get_trigger_price(&self) -> Option<f64> {
        self.trigger_price.map(|d| d.to_f64().unwrap_or_default())
    }

    #[getter]
    /// 获取跟踪止损偏移量.
    /// :return: 跟踪止损偏移量 (如果未设置则返回 None)
    fn get_trail_offset(&self) -> Option<f64> {
        self.trail_offset.map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    fn set_trail_offset(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        if let Some(v) = value {
            self.trail_offset = Some(extract_decimal(v)?);
        } else {
            self.trail_offset = None;
        }
        Ok(())
    }

    #[getter]
    /// 获取跟踪止损参考价.
    /// :return: 跟踪止损参考价 (如果未设置则返回 None)
    fn get_trail_reference_price(&self) -> Option<f64> {
        self.trail_reference_price
            .map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    fn set_trail_reference_price(
        &mut self,
        value: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        if let Some(v) = value {
            self.trail_reference_price = Some(extract_decimal(v)?);
        } else {
            self.trail_reference_price = None;
        }
        Ok(())
    }

    #[getter]
    /// 获取已成交数量.
    /// :return: 已成交数量
    fn get_filled_quantity(&self) -> f64 {
        self.filled_quantity.to_f64().unwrap_or_default()
    }

    #[setter]
    fn set_filled_quantity(&mut self, value: &Bound<'_, PyAny>) -> PyResult<()> {
        self.filled_quantity = extract_decimal(value)?;
        Ok(())
    }

    #[getter]
    /// 获取成交均价.
    /// :return: 成交均价 (如果未成交则返回 None)
    fn get_average_filled_price(&self) -> Option<f64> {
        self.average_filled_price
            .map(|d| d.to_f64().unwrap_or_default())
    }

    #[setter]
    fn set_average_filled_price(&mut self, value: Option<&Bound<'_, PyAny>>) -> PyResult<()> {
        if let Some(v) = value {
             self.average_filled_price = Some(extract_decimal(v)?);
        } else {
             self.average_filled_price = None;
        }
        Ok(())
    }

    pub fn __repr__(&self) -> String {
        format!(
            "Order(id={}, symbol={}, side={:?}, type={:?}, qty={}, price={:?}, trigger={:?}, trail_offset={:?}, trail_ref={:?}, graph_id={:?}, parent_order_id={:?}, role={:?}, tif={:?}, status={:?}, tag={}, reject_reason={})",
            self.id,
            self.symbol,
            self.side,
            self.order_type,
            self.quantity,
            self.price,
            self.trigger_price,
            self.trail_offset,
            self.trail_reference_price,
            self.graph_id,
            self.parent_order_id,
            self.order_role,
            self.time_in_force,
            self.status,
            self.tag,
            self.reject_reason
        )
    }
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize)]
/// 成交记录.
///
/// :ivar id: 成交ID
/// :ivar order_id: 订单ID
/// :ivar symbol: 标的代码
/// :ivar side: 交易方向
/// :ivar quantity: 成交数量
/// :ivar price: 成交价格
/// :ivar commission: 手续费
/// :ivar timestamp: Unix 时间戳 (纳秒)
pub struct Trade {
    #[pyo3(get)]
    pub id: String,
    #[pyo3(get)]
    pub order_id: String,
    #[pyo3(get)]
    pub symbol: String,
    #[pyo3(get)]
    pub side: OrderSide,
    pub quantity: Decimal,
    pub price: Decimal,
    pub commission: Decimal,
    #[pyo3(get)]
    pub timestamp: i64,
    #[pyo3(get)]
    pub bar_index: usize,
    #[pyo3(get)]
    #[serde(default)]
    pub owner_strategy_id: Option<String>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Trade {
    /// 创建成交记录.
    ///
    /// :param id: 成交ID
    /// :param order_id: 订单ID
    /// :param symbol: 标的代码
    /// :param side: 交易方向
    /// :param quantity: 成交数量
    /// :param price: 成交价格
    /// :param commission: 手续费
    /// :param timestamp: Unix 时间戳 (纳秒)
    /// :param bar_index: K线索引
    #[new]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        id: String,
        order_id: String,
        symbol: String,
        side: OrderSide,
        quantity: &Bound<'_, PyAny>,
        price: &Bound<'_, PyAny>,
        commission: &Bound<'_, PyAny>,
        timestamp: i64,
        bar_index: usize,
        owner_strategy_id: Option<String>,
    ) -> PyResult<Self> {
        Ok(Trade {
            id,
            order_id,
            symbol,
            side,
            quantity: extract_decimal(quantity)?,
            price: extract_decimal(price)?,
            commission: extract_decimal(commission)?,
            timestamp,
            bar_index,
            owner_strategy_id,
        })
    }

    #[getter]
    /// 获取成交数量.
    /// :return: 成交数量
    fn get_quantity(&self) -> f64 {
        self.quantity.to_f64().unwrap_or_default()
    }

    #[getter]
    /// 获取成交价格.
    /// :return: 成交价格
    fn get_price(&self) -> f64 {
        self.price.to_f64().unwrap_or_default()
    }

    #[getter]
    /// 获取手续费.
    /// :return: 手续费
    fn get_commission(&self) -> f64 {
        self.commission.to_f64().unwrap_or_default()
    }

    pub fn __repr__(&self) -> String {
        format!(
            "Trade(id={}, order_id={}, symbol={}, side={:?}, qty={}, price={}, time={}, bar={})",
            self.id,
            self.order_id,
            self.symbol,
            self.side,
            self.quantity,
            self.price,
            self.timestamp,
            self.bar_index
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Serialize)]
    struct LegacyOrder {
        id: String,
        symbol: String,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Option<Decimal>,
        time_in_force: TimeInForce,
        trigger_price: Option<Decimal>,
        status: OrderStatus,
        filled_quantity: Decimal,
        average_filled_price: Option<Decimal>,
        created_at: i64,
        updated_at: i64,
        commission: Decimal,
        tag: String,
        reject_reason: String,
    }

    #[derive(Serialize)]
    struct LegacyTrade {
        id: String,
        order_id: String,
        symbol: String,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal,
        timestamp: i64,
        bar_index: usize,
    }

    #[test]
    fn test_order_deserialize_legacy_without_owner_strategy_id() {
        let legacy = LegacyOrder {
            id: "o1".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            order_type: OrderType::Limit,
            quantity: Decimal::from(10),
            price: Some(Decimal::from(100)),
            time_in_force: TimeInForce::Day,
            trigger_price: None,
            status: OrderStatus::New,
            filled_quantity: Decimal::ZERO,
            average_filled_price: None,
            created_at: 1,
            updated_at: 1,
            commission: Decimal::ZERO,
            tag: String::new(),
            reject_reason: String::new(),
        };
        let bytes = rmp_serde::to_vec(&legacy).expect("serialize legacy order");
        let order: Order =
            rmp_serde::from_slice(&bytes).expect("deserialize order from legacy payload");
        assert!(order.owner_strategy_id.is_none());
        assert!(order.trail_offset.is_none());
        assert!(order.trail_reference_price.is_none());
        assert!(order.graph_id.is_none());
        assert!(order.parent_order_id.is_none());
        assert_eq!(order.order_role, OrderRole::Standalone);
    }

    #[test]
    fn test_trade_deserialize_legacy_without_owner_strategy_id() {
        let legacy = LegacyTrade {
            id: "t1".to_string(),
            order_id: "o1".to_string(),
            symbol: "AAPL".to_string(),
            side: OrderSide::Buy,
            quantity: Decimal::from(10),
            price: Decimal::from(100),
            commission: Decimal::ZERO,
            timestamp: 1,
            bar_index: 0,
        };
        let bytes = rmp_serde::to_vec(&legacy).expect("serialize legacy trade");
        let trade: Trade =
            rmp_serde::from_slice(&bytes).expect("deserialize trade from legacy payload");
        assert!(trade.owner_strategy_id.is_none());
    }
}
