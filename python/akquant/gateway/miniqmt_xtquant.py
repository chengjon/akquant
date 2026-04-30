# -*- coding: utf-8 -*-
"""
MiniQMT xtquant Bridge — connects MiniQMT gateway to real QMT via xtquant SDK.

This module is only imported when ``qmt_path`` is provided in the gateway config.
If ``xtquant`` is not installed, ``QMTXtQuantBridge`` raises ``ImportError`` on
construction so the caller can fall back to in-memory mode.
"""

from __future__ import annotations

import time
from typing import Any, Callable

# xtquant may be installed but xttrader/xtdata require the QMT client's
# native libraries (xtpythonclient, datacenter) which are only available
# when the QMT desktop app is installed on the machine.
# We import constants and types eagerly (they have no native deps),
# but defer xttrader import to connect() time.

try:
    from xtquant import xtconstant  # type: ignore
    from xtquant.xttype import StockAccount  # type: ignore

    HAS_XTQUANT = True
except ImportError:
    HAS_XTQUANT = False

    class _Stub:  # type: ignore[no-redef]
        """Stub so type-checking passes when xtquant is absent."""

    xtconstant = _Stub()  # type: ignore[assignment]
    StockAccount = _Stub  # type: ignore[assignment,misc]

_xttrader: Any = None


def _get_xttrader() -> Any:
    """Lazy-import xttrader. Raises ImportError if native libs are missing."""
    global _xttrader
    if _xttrader is not None:
        return _xttrader
    from xtquant import xttrader as _xt  # type: ignore

    _xttrader = _xt
    return _xttrader


class QMTXtQuantBridge:
    """Bridge between AKQuant's MiniQMT gateway and the xtquant SDK.

    Responsibilities:
    - Connect to the local QMT client via ``xttrader.connect``.
    - Register a ``TraderCallback`` that forwards QMT events to
      ``MiniQMTTraderGateway.ingest_order_event`` /
      ``MiniQMTTraderGateway.ingest_trade_event``.
    - Convert symbol format (``"600000"`` ↔ ``"SH.600000"``).
    - Map QMT order-status constants to AKQuant unified status strings.
    - Place / cancel orders through ``xttrader``.
    """

    # QMT status value → AKQuant unified status string
    STATUS_MAP: dict[int, str] = {}

    def __init__(
        self,
        qmt_path: str,
        account_id: str,
        gateway: Any,
    ) -> None:
        if not HAS_XTQUANT:
            raise ImportError(
                "xtquant is not installed. Install it via your QMT distribution "
                "or run without qmt_path to use in-memory mode."
            )
        import warnings
        warnings.warn(
            "QMTXtQuantBridge is scheduled for migration to the "
            "miniQMT project. Once miniQMT Phase A is complete, "
            "this module will be replaced by an HTTP bridge client. "
            "See docs/zh/reference/miniqmt-bridge-transfer-plan.md.",
            FutureWarning,
            stacklevel=2,
        )
        self.gateway = gateway
        self._qmt_path = qmt_path
        self._account_id = account_id

        # Build status map from xtconstant (deferred so import errors surface above)
        self.STATUS_MAP = {
            xtconstant.ORDER_UNCONFIRMED: "submitted",
            xtconstant.ORDER_CONFIRMED: "submitted",
            xtconstant.ORDER_SUCCEEDED: "filled",
            xtconstant.ORDER_CANCELLED: "cancelled",
            xtconstant.ORDER_REJECTED: "rejected",
            xtconstant.ORDER_PARTSUCC: "partially_filled",
        }

        self._session_id: int = 0
        self._account = StockAccount(account_id)
        self._connected = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to QMT client and register callbacks."""
        xt = _get_xttrader()
        self._session_id = xt.connect(self._qmt_path)
        callback = _QMTCallback(self)
        xt.register_callback(self._session_id, callback)
        self._connected = True

    def disconnect(self) -> None:
        """Disconnect from QMT client."""
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Symbol conversion
    # ------------------------------------------------------------------

    @staticmethod
    def format_symbol(symbol: str) -> str:
        """AKQuant → QMT: ``'600000'`` → ``'SH.600000'``."""
        if "." in symbol:
            return symbol
        if symbol.startswith("6"):
            return f"SH.{symbol}"
        if symbol.startswith("0") or symbol.startswith("3"):
            return f"SZ.{symbol}"
        if symbol.startswith("4") or symbol.startswith("8"):
            return f"BJ.{symbol}"
        return symbol

    @staticmethod
    def strip_symbol(qmt_code: str) -> str:
        """QMT → AKQuant: ``'SH.600000'`` → ``'600000'``."""
        if "." in qmt_code:
            return qmt_code.split(".", 1)[1]
        return qmt_code

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_native_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        price: float | None,
        order_type: str,
        broker_options: dict[str, Any] | None = None,
    ) -> int:
        """Place order via xtquant. Returns native QMT order_id."""
        qmt_symbol = self.format_symbol(symbol)

        qmt_side = (
            xtconstant.STOCK_BUY if side.lower() == "buy"
            else xtconstant.STOCK_SELL
        )

        if order_type.lower() == "market":
            qmt_type = xtconstant.MARKET_BEST5_TO_CANCEL
            qmt_price = 0.0
        else:
            qmt_type = xtconstant.FIX_PRICE
            qmt_price = float(price or 0.0)

        xt = _get_xttrader()
        order_id = xt.order_stock(
            self._account,
            qmt_symbol,
            qmt_side,
            int(max(1, round(quantity))),
            qmt_type,
            qmt_price,
            "akquant",
            "akquant-order",
        )
        return int(order_id)

    def cancel_native_order(self, order_id: int) -> None:
        """Cancel order via xtquant."""
        xt = _get_xttrader()
        xt.cancel_order_stock(self._session_id, order_id)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def query_account(self) -> dict[str, Any] | None:
        """Query account assets from QMT."""
        try:
            xt = _get_xttrader()
            asset = xt.query_stock_assets(self._account)
            if asset is None:
                return None
            return {
                "account_id": self._account_id,
                "equity": float(asset.total_asset),
                "cash": float(asset.cash),
                "available_cash": float(asset.m_dAvailFund),
            }
        except Exception:
            return None

    def query_positions(self) -> list[dict[str, Any]]:
        """Query positions from QMT."""
        try:
            xt = _get_xttrader()
            positions = xt.query_stock_positions(self._account)
            if positions is None:
                return []
            result = []
            for p in positions:
                result.append({
                    "symbol": self.strip_symbol(p.stock_code),
                    "quantity": float(p.volume),
                    "available_quantity": float(p.can_use_volume),
                    "avg_price": float(p.avg_price),
                })
            return result
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Callback dispatch (called by _QMTCallback)
    # ------------------------------------------------------------------

    def _on_stock_order(self, order: Any) -> None:
        """Forward QMT order callback to gateway."""
        symbol = self.strip_symbol(getattr(order, "stock_code", ""))
        status_val = getattr(order, "order_status", -1)
        status = self.STATUS_MAP.get(status_val, "submitted")

        self.gateway.ingest_order_event({
            "client_order_id": str(getattr(order, "strategy_id", "") or getattr(order, "order_remark", "") or ""),
            "broker_order_id": f"miniqmt-{order.order_id}",
            "symbol": symbol,
            "status": status,
            "filled_quantity": float(getattr(order, "traded_volume", 0)),
            "avg_fill_price": float(getattr(order, "traded_price", 0)),
            "reject_reason": str(getattr(order, "order_remark", "") or ""),
            "timestamp_ns": int(getattr(order, "order_time", 0) * 1e9) or time.time_ns(),
        })

    def _on_stock_trade(self, trade: Any) -> None:
        """Forward QMT trade callback to gateway."""
        symbol = self.strip_symbol(getattr(trade, "stock_code", ""))
        trade_side = getattr(trade, "order_type", 0)

        self.gateway.ingest_trade_event({
            "trade_id": str(getattr(trade, "traded_id", "")),
            "broker_order_id": f"miniqmt-{trade.order_id}",
            "client_order_id": str(getattr(trade, "strategy_id", "") or getattr(trade, "order_remark", "") or ""),
            "symbol": symbol,
            "side": "buy" if trade_side in (xtconstant.STOCK_BUY,) else "sell",
            "quantity": float(getattr(trade, "traded_volume", 0)),
            "price": float(getattr(trade, "traded_price", 0)),
            "timestamp_ns": int(getattr(trade, "traded_time", 0) * 1e9) or time.time_ns(),
        })

    def heartbeat(self) -> bool:
        """Check if QMT connection is alive."""
        return self._connected


class _QMTCallback:
    """Callback handler registered with xttrader. Forwards events to bridge."""

    def __init__(self, bridge: QMTXtQuantBridge) -> None:
        self._bridge = bridge

    def on_stock_order(self, order: Any) -> None:
        self._bridge._on_stock_order(order)

    def on_stock_trade(self, trade: Any) -> None:
        self._bridge._on_stock_trade(trade)

    def on_stock_position(self, position: Any) -> None:
        pass  # handled via query

    def on_stock_asset(self, asset: Any) -> None:
        pass  # handled via query

    def on_order_stock_async_response(
        self, response: Any
    ) -> None:
        pass  # order async response handled via on_stock_order
