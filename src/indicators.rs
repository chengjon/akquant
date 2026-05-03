use pyo3::prelude::*;

mod candlestick;
mod hilbert;
mod momentum;
mod moving_average;
mod trend;
mod volatility;
mod volume;

pub use hilbert::{HT_DCPERIOD, HT_DCPHASE, HT_PHASOR};
pub use momentum::{CMO, MOM, ROC, ROCP, ROCR, ROCR100, RSI, WILLR};
pub use moving_average::{
    ABS, ACOS, ADD, APO, ASIN, ATAN, AVGDEV, CEIL, CLAMP01, CLIP, COS, COSH, CUBE, DEG2RAD, DEMA,
    DIV, EMA, EXP, EXPM1, FLOOR, HT_TRENDLINE, INV_SQRT, KAMA, LN, LOG1P, LOG10, MACD, MAMA, MAX,
    MAX2, MAXINDEX, MIDPOINT, MIN, MIN2, MININDEX, MINMAX, MINMAXINDEX, MOD, MULT, POW, PPO, RANGE,
    RECIP, ROUND, SIGN, SIN, SINH, SMA, SQ, SQRT, SUB, SUM, T3, TAN, TANH, TEMA, TRIMA, TRIX, WMA,
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
    candlestick::register_classes(m)?;
    hilbert::register_classes(m)?;
    moving_average::register_classes(m)?;
    momentum::register_classes(m)?;
    trend::register_classes(m)?;
    volatility::register_classes(m)?;
    volume::register_classes(m)?;
    Ok(())
}
