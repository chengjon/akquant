use super::market_data::extract_decimal;
use super::types::{AssetType, OptionType, SettlementType};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use rust_decimal::Decimal;
use rust_decimal::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StockInstrument {
    pub symbol: String,
    pub lot_size: Decimal,
    pub tick_size: Decimal,
    // Add other stock-specific fields if needed
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FundInstrument {
    pub symbol: String,
    pub lot_size: Decimal,
    pub tick_size: Decimal,
    // Add other fund-specific fields if needed
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FuturesInstrument {
    pub symbol: String,
    pub multiplier: Decimal,
    pub margin_ratio: Decimal,
    pub tick_size: Decimal,
    pub expiry_date: Option<u32>,
    pub settlement_type: Option<SettlementType>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptionInstrument {
    pub symbol: String,
    pub multiplier: Decimal,
    pub tick_size: Decimal,
    pub option_type: OptionType,
    pub strike_price: Decimal,
    pub expiry_date: u32,
    pub underlying_symbol: String,
    pub settlement_type: Option<SettlementType>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CryptoInstrument {
    pub symbol: String,
    pub lot_size: Decimal, // Usually small (e.g. 0.0001)
    pub tick_size: Decimal,
    pub multiplier: Decimal, // Usually 1.0 for Spot, but contract size for futures
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ForexInstrument {
    pub symbol: String,
    pub lot_size: Decimal, // Standard lot is 100,000 units
    pub tick_size: Decimal, // Pip size (e.g. 0.0001)
    pub multiplier: Decimal, // Usually 1.0
}

#[gen_stub_pyclass]
#[pyclass(from_py_object)]
#[derive(Debug, Clone, Serialize, Deserialize)]
/// 交易标的
///
/// :ivar symbol: 代码
/// :ivar asset_type: 资产类型
/// :ivar multiplier: 合约乘数
/// :ivar margin_ratio: 保证金比率
/// :ivar tick_size: 最小变动价位
pub struct Instrument {
    #[pyo3(get)]
    pub asset_type: AssetType,
    pub inner: InstrumentEnum,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum InstrumentEnum {
    Stock(StockInstrument),
    Fund(FundInstrument),
    Futures(FuturesInstrument),
    Option(OptionInstrument),
    Crypto(CryptoInstrument),
    Forex(ForexInstrument),
}

#[gen_stub_pymethods]
#[pymethods]
impl Instrument {
    /// 创建交易标的
    ///
    /// :param symbol: 代码
    /// :param asset_type: 资产类型
    /// :param multiplier: 合约乘数
    /// :param margin_ratio: 保证金比率
    /// :param tick_size: 最小变动价位
    /// :param option_type: 期权类型 (可选)
    /// :param strike_price: 行权价 (可选)
    /// :param expiry_date: 到期日 (可选)
    /// :param lot_size: 最小交易单位 (可选, 默认为1)
    /// :param underlying_symbol: 标的代码 (可选)
    /// :param settlement_type: 结算方式 (可选)
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (symbol, asset_type, multiplier=None, margin_ratio=None, tick_size=None, option_type=None, strike_price=None, expiry_date=None, lot_size=None, underlying_symbol=None, settlement_type=None))]
    pub fn new(
        symbol: String,
        asset_type: AssetType,
        multiplier: Option<&Bound<'_, PyAny>>,
        margin_ratio: Option<&Bound<'_, PyAny>>,
        tick_size: Option<&Bound<'_, PyAny>>,
        option_type: Option<OptionType>,
        strike_price: Option<&Bound<'_, PyAny>>,
        expiry_date: Option<u32>,
        lot_size: Option<&Bound<'_, PyAny>>,
        underlying_symbol: Option<String>,
        settlement_type: Option<SettlementType>,
    ) -> PyResult<Self> {
        let multiplier_val = multiplier.map(extract_decimal).transpose()?.unwrap_or(Decimal::ONE);
        let margin_val = margin_ratio.map(extract_decimal).transpose()?.unwrap_or(Decimal::ONE);
        let tick_val = tick_size.map(extract_decimal).transpose()?.unwrap_or(Decimal::new(1, 2));
        let lot_val = lot_size.map(extract_decimal).transpose()?.unwrap_or(Decimal::ONE);

        let inner = match asset_type {
            AssetType::Stock => InstrumentEnum::Stock(StockInstrument {
                symbol: symbol.clone(),
                lot_size: lot_val,
                tick_size: tick_val,
            }),
            AssetType::Fund => InstrumentEnum::Fund(FundInstrument {
                symbol: symbol.clone(),
                lot_size: lot_val,
                tick_size: tick_val,
            }),
            AssetType::Futures => InstrumentEnum::Futures(FuturesInstrument {
                symbol: symbol.clone(),
                multiplier: multiplier_val,
                margin_ratio: margin_val,
                tick_size: tick_val,
                expiry_date,
                settlement_type,
            }),
            AssetType::Option => InstrumentEnum::Option(OptionInstrument {
                symbol: symbol.clone(),
                multiplier: multiplier_val,
                tick_size: tick_val,
                option_type: option_type.unwrap_or(OptionType::Call),
                strike_price: strike_price.map(extract_decimal).transpose()?.unwrap_or(Decimal::ZERO),
                expiry_date: expiry_date.unwrap_or(0),
                underlying_symbol: underlying_symbol.unwrap_or_default(),
                settlement_type,
            }),
            AssetType::Crypto => InstrumentEnum::Crypto(CryptoInstrument {
                symbol: symbol.clone(),
                lot_size: lot_val,
                tick_size: tick_val,
                multiplier: multiplier_val,
            }),
            AssetType::Forex => InstrumentEnum::Forex(ForexInstrument {
                symbol: symbol.clone(),
                lot_size: lot_val,
                tick_size: tick_val,
                multiplier: multiplier_val,
            }),
        };

        Ok(Instrument {
            asset_type,
            inner,
        })
    }

    #[getter]
    pub fn get_symbol(&self) -> String {
        self.symbol().to_string()
    }

    #[getter]
    pub fn get_multiplier(&self) -> f64 {
        self.multiplier().to_f64().unwrap_or(1.0)
    }

    #[getter]
    pub fn get_margin_ratio(&self) -> f64 {
        self.margin_ratio().to_f64().unwrap_or(1.0)
    }

    #[getter]
    pub fn get_lot_size(&self) -> f64 {
        self.lot_size().to_f64().unwrap_or(1.0)
    }

    #[getter]
    pub fn get_tick_size(&self) -> f64 {
        self.tick_size().to_f64().unwrap_or(0.01)
    }
}

// Add public accessors for internal Rust usage to avoid breaking changes everywhere immediately
impl Instrument {
    pub fn symbol(&self) -> &str {
        match &self.inner {
            InstrumentEnum::Stock(s) => &s.symbol,
            InstrumentEnum::Fund(f) => &f.symbol,
            InstrumentEnum::Futures(f) => &f.symbol,
            InstrumentEnum::Option(o) => &o.symbol,
            InstrumentEnum::Crypto(c) => &c.symbol,
            InstrumentEnum::Forex(f) => &f.symbol,
        }
    }

    pub fn multiplier(&self) -> Decimal {
        match &self.inner {
            InstrumentEnum::Futures(f) => f.multiplier,
            InstrumentEnum::Option(o) => o.multiplier,
            InstrumentEnum::Crypto(c) => c.multiplier,
            InstrumentEnum::Forex(f) => f.multiplier,
            _ => Decimal::ONE,
        }
    }

    pub fn margin_ratio(&self) -> Decimal {
        match &self.inner {
            InstrumentEnum::Futures(f) => f.margin_ratio,
            InstrumentEnum::Forex(_) => Decimal::new(1, 2), // 0.01 default for Forex
            _ => Decimal::ONE,
        }
    }

    pub fn lot_size(&self) -> Decimal {
        match &self.inner {
            InstrumentEnum::Stock(s) => s.lot_size,
            InstrumentEnum::Fund(f) => f.lot_size,
            InstrumentEnum::Crypto(c) => c.lot_size,
            InstrumentEnum::Forex(f) => f.lot_size,
            _ => Decimal::ONE,
        }
    }

    pub fn tick_size(&self) -> Decimal {
        match &self.inner {
            InstrumentEnum::Stock(s) => s.tick_size,
            InstrumentEnum::Fund(f) => f.tick_size,
            InstrumentEnum::Futures(f) => f.tick_size,
            InstrumentEnum::Option(o) => o.tick_size,
            InstrumentEnum::Crypto(c) => c.tick_size,
            InstrumentEnum::Forex(f) => f.tick_size,
        }
    }

    pub fn expiry_date(&self) -> Option<u32> {
        match &self.inner {
            InstrumentEnum::Futures(f) => f.expiry_date,
            InstrumentEnum::Option(o) => Some(o.expiry_date),
            _ => None,
        }
    }

    pub fn underlying_symbol(&self) -> Option<&String> {
        match &self.inner {
            InstrumentEnum::Option(o) => Some(&o.underlying_symbol),
            _ => None,
        }
    }

    pub fn strike_price(&self) -> Option<Decimal> {
        match &self.inner {
            InstrumentEnum::Option(o) => Some(o.strike_price),
            _ => None,
        }
    }

    pub fn option_type(&self) -> Option<OptionType> {
        match &self.inner {
            InstrumentEnum::Option(o) => Some(o.option_type),
            _ => None,
        }
    }
}
