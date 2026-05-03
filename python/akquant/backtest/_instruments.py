"""Backtest instrument parsing helpers."""

import datetime as dt_module
from typing import Any, List, Literal, Optional, Tuple, Union

import pandas as pd

from ..akquant import AssetType, TradingSession
from ..strategy import (
    InstrumentAssetTypeName,
    InstrumentOptionTypeName,
    InstrumentSettlementMode,
)


def _parse_asset_type_name(value: Any) -> Literal["futures", "stock", "fund", "option"]:
    if isinstance(value, AssetType):
        if value == AssetType.Futures:
            return "futures"
        if value == AssetType.Stock:
            return "stock"
        if value == AssetType.Fund:
            return "fund"
        if value == AssetType.Option:
            return "option"
        raise ValueError(f"Unsupported asset_type: {value}")
    if isinstance(value, str):
        v_lower = value.lower()
        if v_lower in {"future", "futures"}:
            return "futures"
        if v_lower == "stock":
            return "stock"
        if v_lower == "fund":
            return "fund"
        if v_lower == "option":
            return "option"
    raise ValueError(f"Unsupported asset_type: {value}")


def _normalize_expiry_date_yyyymmdd(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("expiry_date does not support bool")
    if isinstance(value, int):
        yyyymmdd = value
    elif isinstance(value, pd.Timestamp):
        if pd.isna(value):
            raise ValueError("expiry_date timestamp is NaT")
        yyyymmdd = int(value.strftime("%Y%m%d"))
    elif isinstance(value, dt_module.datetime):
        yyyymmdd = int(value.date().strftime("%Y%m%d"))
    elif isinstance(value, dt_module.date):
        yyyymmdd = int(value.strftime("%Y%m%d"))
    elif isinstance(value, str):
        raise TypeError(
            "expiry_date no longer supports str, please use date/datetime/"
            "Timestamp/int(YYYYMMDD)"
        )
    else:
        raise TypeError(
            "expiry_date must be date/datetime/pandas.Timestamp/int(YYYYMMDD)"
        )
    text = str(yyyymmdd)
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"expiry_date must be YYYYMMDD, got: {value}")
    year = int(text[0:4])
    month = int(text[4:6])
    day = int(text[6:8])
    dt_module.date(year, month, day)
    return yyyymmdd


def _asset_type_to_upper_name(
    value: Union[str, AssetType],
) -> InstrumentAssetTypeName:
    parsed = _parse_asset_type_name(value)
    if parsed == "futures":
        return "FUTURES"
    if parsed == "fund":
        return "FUND"
    if parsed == "option":
        return "OPTION"
    return "STOCK"


def _option_type_to_upper_name(value: Any) -> Optional[InstrumentOptionTypeName]:
    if value is None:
        return None
    text = str(value).upper()
    if "CALL" in text:
        return "CALL"
    if "PUT" in text:
        return "PUT"
    raise ValueError(f"Unsupported option_type: {value}")


def _settlement_type_to_upper_name(value: Any) -> Optional[InstrumentSettlementMode]:
    if value is None:
        return None
    text = str(value).upper()
    if "FORCE" in text and "CLOSE" in text:
        return "FORCE_CLOSE"
    if "SETTLEMENT_PRICE" in text:
        return "SETTLEMENT_PRICE"
    if "CASH" in text:
        return "CASH"
    raise ValueError(f"Unsupported settlement_type: {value}")


def _parse_trading_session(value: Any) -> Any:
    if isinstance(value, TradingSession):
        return value
    call_auction = getattr(
        TradingSession, "CallAuction", getattr(TradingSession, "Normal", None)
    )
    pre_open = getattr(
        TradingSession, "PreOpen", getattr(TradingSession, "PreMarket", None)
    )
    continuous = getattr(
        TradingSession, "Continuous", getattr(TradingSession, "Normal", None)
    )
    break_session = getattr(
        TradingSession, "Break", getattr(TradingSession, "Normal", None)
    )
    post_close = getattr(
        TradingSession, "PostClose", getattr(TradingSession, "PostMarket", None)
    )
    closed = getattr(
        TradingSession, "Closed", getattr(TradingSession, "PostMarket", None)
    )
    v_lower = str(value).strip().lower()
    mapping = {
        "call_auction": call_auction,
        "callauction": call_auction,
        "pre_open": pre_open,
        "preopen": pre_open,
        "continuous": continuous,
        "break": break_session,
        "post_close": post_close,
        "postclose": post_close,
        "closed": closed,
    }
    if v_lower in mapping and mapping[v_lower] is not None:
        return mapping[v_lower]
    raise ValueError(f"Unsupported trading session: {value}")


def _china_futures_session_template(
    profile: str,
) -> List[Tuple[str, str, str]]:
    normalized = str(profile).strip().upper()
    commodity_day_template: List[Tuple[str, str, str]] = [
        ("09:00", "10:15", "continuous"),
        ("10:15", "10:30", "break"),
        ("10:30", "11:30", "continuous"),
        ("11:30", "13:30", "break"),
        ("13:30", "15:00", "continuous"),
    ]
    cffex_stock_index_day_template: List[Tuple[str, str, str]] = [
        ("09:30", "11:30", "continuous"),
        ("11:30", "13:00", "break"),
        ("13:00", "15:00", "continuous"),
    ]
    cffex_bond_day_template: List[Tuple[str, str, str]] = [
        ("09:30", "11:30", "continuous"),
        ("11:30", "13:00", "break"),
        ("13:00", "15:15", "continuous"),
    ]
    if normalized in {"CN_FUTURES_DAY", "CN_FUTURES_COMMODITY_DAY"}:
        return commodity_day_template
    if normalized == "CN_FUTURES_CFFEX_STOCK_INDEX_DAY":
        return cffex_stock_index_day_template
    if normalized == "CN_FUTURES_CFFEX_BOND_DAY":
        return cffex_bond_day_template
    if normalized == "CN_FUTURES_NIGHT_23":
        return [("21:00", "23:00", "continuous")] + commodity_day_template
    if normalized == "CN_FUTURES_NIGHT_01":
        return [
            ("21:00", "23:59", "continuous"),
            ("00:00", "01:00", "continuous"),
        ] + commodity_day_template
    if normalized == "CN_FUTURES_NIGHT_0230":
        return [
            ("21:00", "23:59", "continuous"),
            ("00:00", "02:30", "continuous"),
        ] + commodity_day_template
    raise ValueError(f"Unsupported china futures session profile: {profile}")
