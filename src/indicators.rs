use pyo3::prelude::*;

mod momentum;
mod moving_average;
mod trend;
mod volatility;
mod volume;

pub use momentum::{CMO, MOM, ROC, ROCP, ROCR, ROCR100, RSI, WILLR};
pub use moving_average::{
    ABS, ACOS, ADD, APO, ASIN, ATAN, AVGDEV, CEIL, CLAMP01, CLIP, COS, COSH, CUBE, DEMA, DIV, EMA,
    EXP, FLOOR, HT_TRENDLINE, KAMA, LN, LOG10, MACD, MAMA, MAX, MAX2, MAXINDEX, MIDPOINT, MIN,
    MIN2, MININDEX, MINMAX, MINMAXINDEX, MOD, MULT, PPO, POW, RANGE, ROUND, SIGN, SIN, SINH, SMA,
    SQ, SQRT, SUB, SUM, T3, TAN, TANH, TEMA, TRIMA, TRIX, WMA,
};
pub use trend::{
    ADX, ADXR, AROON, AROONOSC, BETA, CCI, CORREL, COVAR, DX, LINEARREG, LINEARREG_ANGLE,
    LINEARREG_INTERCEPT, LINEARREG_R2, LINEARREG_SLOPE, MINUS_DI, PLUS_DI, SAR, STOCH, TSF, ULTOSC,
};
pub use volatility::{
    ATR, AVGPRICE, BollingerBands, MEDPRICE, MIDPRICE, NATR, STDDEV, TRANGE, TYPPRICE, VAR,
    WCLPRICE,
};
pub use volume::{AD, ADOSC, BOP, MFI, OBV};

pub fn register_py_classes(m: &Bound<'_, PyModule>) -> PyResult<()> {
    moving_average::register_classes(m)?;
    momentum::register_classes(m)?;
    trend::register_classes(m)?;
    volatility::register_classes(m)?;
    volume::register_classes(m)?;
    Ok(())
}
