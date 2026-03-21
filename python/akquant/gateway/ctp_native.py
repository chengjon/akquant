# -*- coding: utf-8 -*-
"""
CTP Gateway Implementation for AKQuant.

This module provides CTP (China Futures) connectivity using openctp-ctp library.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from ..akquant import Bar, BarAggregator, DataFeed

try:
    from openctp_ctp import thostmduserapi as mdapi  # type: ignore
    from openctp_ctp import thosttraderapi as tdapi  # type: ignore

    HAS_OPENCTP = True
except ImportError:
    HAS_OPENCTP = False

    class MockSpi:
        """Mock SPI class for when openctp-ctp is not installed."""

        pass

    class MockMdApi:
        """Mock market API namespace."""

        CThostFtdcMdSpi = MockSpi

    class MockTdApi:
        """Mock trader API namespace."""

        CThostFtdcTraderSpi = MockSpi

    mdapi = MockMdApi  # type: ignore
    tdapi = MockTdApi  # type: ignore


class CTPTraderGateway(tdapi.CThostFtdcTraderSpi):  # type: ignore
    """
    CTP Trading Gateway.

    Handles connection, authentication, login, and settlement confirmation.
    """

    def __init__(
        self,
        front_url: str,
        broker_id: str = "9999",
        user_id: str = "",
        password: str = "",
        auth_code: str = "0000000000000000",
        app_id: str = "simnow_client_test",
    ):
        """
        Initialize the CTP Trader Gateway.

        :param front_url: CTP Front URL
        :param broker_id: Broker ID
        :param user_id: User ID
        :param password: Password
        :param auth_code: Authentication Code
        :param app_id: App ID
        """
        if not HAS_OPENCTP:
            raise ImportError(
                "openctp-ctp is not installed. Please run `pip install openctp-ctp`."
            )

        tdapi.CThostFtdcTraderSpi.__init__(self)
        self.front_url = front_url
        self.broker_id = broker_id
        self.user_id = user_id
        self.password = password
        self.auth_code = auth_code
        self.app_id = app_id

        self.api: Any = None
        self.req_id = 0
        self.connected = False
        self.authenticated = False
        self.login_status = False
        self.ready_to_trade = False
        self.front_id = 0
        self.session_id = 0
        self.order_ref = 1
        self.order_callback: Callable[[dict[str, Any]], None] | None = None
        self.trade_callback: Callable[[dict[str, Any]], None] | None = None
        self.error_callback: Callable[[dict[str, Any]], None] | None = None
        self.order_ref_to_client_order_id: dict[str, str] = {}
        self.order_ref_to_symbol: dict[str, str] = {}

    def start(self) -> None:
        """Start the CTP Trader API in a blocking way (should be run in a thread)."""
        print(f"[CTP-Trade] Connecting to {self.front_url}...")
        try:
            self.api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi()
            self.api.RegisterFront(self.front_url)
            self.api.RegisterSpi(self)
            self.api.SubscribePrivateTopic(tdapi.THOST_TERT_QUICK)
            self.api.SubscribePublicTopic(tdapi.THOST_TERT_QUICK)
            self.api.Init()
            print("[CTP-Trade] API Initialized, joining thread...")
            self.api.Join()
        except Exception as e:
            print(f"[CTP-Trade] ERROR: Failed to start CTP Trader API: {e}")

    def set_order_handler(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set native order event handler."""
        self.order_callback = callback

    def set_trade_handler(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set native trade event handler."""
        self.trade_callback = callback

    def set_error_handler(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set native error event handler."""
        self.error_callback = callback

    def can_trade(self) -> bool:
        """Return whether the trader channel is ready for order requests."""
        return self.connected and self.login_status and self.ready_to_trade

    def insert_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float | None,
        order_type: str,
        time_in_force: str,
    ) -> dict[str, Any]:
        """Send CTP order insert request."""
        if not self.can_trade():
            raise RuntimeError("CTP trader is not ready for trading")
        if self.api is None:
            raise RuntimeError("CTP trader API is not initialized")

        order_ref_text = str(self.order_ref)
        self.order_ref += 1
        self.order_ref_to_client_order_id[order_ref_text] = client_order_id
        self.order_ref_to_symbol[order_ref_text] = symbol

        request = tdapi.CThostFtdcInputOrderField()
        request.BrokerID = self.broker_id
        request.InvestorID = self.user_id
        request.ExchangeID = ""
        request.InstrumentID = symbol
        request.OrderRef = order_ref_text
        request.UserID = self.user_id
        request.Direction = (
            tdapi.THOST_FTDC_D_Buy
            if str(side).strip().lower() == "buy"
            else tdapi.THOST_FTDC_D_Sell
        )
        request.CombOffsetFlag = tdapi.THOST_FTDC_OF_Open
        request.CombHedgeFlag = tdapi.THOST_FTDC_HF_Speculation
        request.VolumeTotalOriginal = int(max(1, round(quantity)))

        order_type_key = str(order_type).strip().lower()
        tif_key = str(time_in_force).strip().upper()
        if order_type_key == "market":
            request.OrderPriceType = tdapi.THOST_FTDC_OPT_AnyPrice
            request.LimitPrice = 0.0
            request.TimeCondition = tdapi.THOST_FTDC_TC_IOC
            request.VolumeCondition = tdapi.THOST_FTDC_VC_AV
        else:
            if price is None or price <= 0:
                raise ValueError("limit price must be positive for non-market orders")
            request.OrderPriceType = tdapi.THOST_FTDC_OPT_LimitPrice
            request.LimitPrice = float(price)
            if tif_key in {"IOC", "FAK", "FOK"}:
                request.TimeCondition = tdapi.THOST_FTDC_TC_IOC
                if tif_key == "FOK":
                    request.VolumeCondition = tdapi.THOST_FTDC_VC_CV
                else:
                    request.VolumeCondition = tdapi.THOST_FTDC_VC_AV
            else:
                request.TimeCondition = tdapi.THOST_FTDC_TC_GFD
                request.VolumeCondition = tdapi.THOST_FTDC_VC_AV

        request.MinVolume = 1
        request.ContingentCondition = tdapi.THOST_FTDC_CC_Immediately
        request.ForceCloseReason = tdapi.THOST_FTDC_FCC_NotForceClose
        request.IsAutoSuspend = 0
        request.UserForceClose = 0

        self.req_id += 1
        ret = self.api.ReqOrderInsert(request, self.req_id)
        if ret != 0:
            self.order_ref_to_client_order_id.pop(order_ref_text, None)
            self.order_ref_to_symbol.pop(order_ref_text, None)
            raise RuntimeError(f"ReqOrderInsert failed with code={ret}")
        return {
            "broker_order_id": self._make_broker_order_id(
                front_id=self.front_id,
                session_id=self.session_id,
                order_ref=order_ref_text,
                order_sys_id="",
            ),
            "order_ref": order_ref_text,
            "front_id": self.front_id,
            "session_id": self.session_id,
            "timestamp_ns": time.time_ns(),
        }

    def cancel_order(self, broker_order_id: str) -> None:
        """Send CTP cancel order request."""
        if not self.can_trade():
            raise RuntimeError("CTP trader is not ready for cancel requests")
        if self.api is None:
            raise RuntimeError("CTP trader API is not initialized")
        parsed = self._parse_broker_order_id(broker_order_id)
        order_ref = parsed.get("order_ref", "")
        if not order_ref:
            raise ValueError(f"invalid broker_order_id={broker_order_id}")
        request = tdapi.CThostFtdcInputOrderActionField()
        request.BrokerID = self.broker_id
        request.InvestorID = self.user_id
        request.OrderRef = order_ref
        request.FrontID = int(parsed.get("front_id") or self.front_id)
        request.SessionID = int(parsed.get("session_id") or self.session_id)
        request.ActionFlag = tdapi.THOST_FTDC_AF_Delete
        request.InstrumentID = self.order_ref_to_symbol.get(order_ref, "")
        self.req_id += 1
        ret = self.api.ReqOrderAction(request, self.req_id)
        if ret != 0:
            raise RuntimeError(f"ReqOrderAction failed with code={ret}")

    def OnFrontConnected(self) -> None:
        """Handle front connection event."""
        print(
            f"[CTP-Trade] OnFrontConnected: Successfully connected to {self.front_url}"
        )
        self.connected = True

        self.req_id += 1
        req = tdapi.CThostFtdcReqAuthenticateField()
        req.BrokerID = self.broker_id
        req.UserID = self.user_id
        req.AppID = self.app_id
        req.AuthCode = self.auth_code
        print(f"[CTP-Trade] Requesting Authentication (ReqID={self.req_id})...")
        if self.api:
            self.api.ReqAuthenticate(req, self.req_id)

    def OnRspAuthenticate(
        self,
        pRspAuthenticateField: Any,
        pRspInfo: Any,
        nRequestID: int,
        bIsLast: bool,
    ) -> None:
        """Handle authentication response."""
        if pRspInfo is not None and pRspInfo.ErrorID != 0:
            print(
                f"[CTP-Trade] Authentication failed. ErrorID={pRspInfo.ErrorID}, "
                f"Msg={pRspInfo.ErrorMsg}"
            )
        else:
            print("[CTP-Trade] Authentication succeed.")

        self.authenticated = True

        self.req_id += 1
        req = tdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = self.broker_id
        req.UserID = self.user_id
        req.Password = self.password
        print(f"[CTP-Trade] Requesting User Login (ReqID={self.req_id})...")
        if self.api:
            self.api.ReqUserLogin(req, self.req_id)

    def OnRspUserLogin(
        self, pRspUserLogin: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool
    ) -> None:
        """Handle login response."""
        if pRspInfo is not None and pRspInfo.ErrorID != 0:
            print(
                f"[CTP-Trade] Login failed. ErrorID={pRspInfo.ErrorID}, "
                f"Msg={pRspInfo.ErrorMsg}"
            )
            return

        print(
            f"[CTP-Trade] Login succeed. TradingDay: {pRspUserLogin.TradingDay}, "
            f"BrokerID: {pRspUserLogin.BrokerID}, UserID: {pRspUserLogin.UserID}"
        )
        self.login_status = True
        self.front_id = int(getattr(pRspUserLogin, "FrontID", 0) or 0)
        self.session_id = int(getattr(pRspUserLogin, "SessionID", 0) or 0)
        max_order_ref = str(getattr(pRspUserLogin, "MaxOrderRef", "")).strip()
        if max_order_ref.isdigit():
            self.order_ref = int(max_order_ref) + 1

        self.req_id += 1
        req = tdapi.CThostFtdcSettlementInfoConfirmField()
        req.BrokerID = self.broker_id
        req.InvestorID = self.user_id
        print("[CTP-Trade] Confirming Settlement Info...")
        if self.api:
            self.api.ReqSettlementInfoConfirm(req, self.req_id)

    def OnRspSettlementInfoConfirm(
        self,
        pSettlementInfoConfirm: Any,
        pRspInfo: Any,
        nRequestID: int,
        bIsLast: bool,
    ) -> None:
        """Handle settlement info confirmation response."""
        if pRspInfo is not None and pRspInfo.ErrorID != 0:
            print(f"[CTP-Trade] Settlement Confirm failed: {pRspInfo.ErrorMsg}")
            self.ready_to_trade = False
        else:
            print("[CTP-Trade] Settlement Info Confirmed.")
            self.ready_to_trade = True

    def OnFrontDisconnected(self, nReason: int) -> None:
        """Handle front disconnection event."""
        print(f"[CTP-Trade] OnFrontDisconnected. [nReason={nReason}]")
        self.connected = False
        self.login_status = False
        self.ready_to_trade = False

    def OnRspOrderInsert(
        self, pInputOrder: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool
    ) -> None:
        """Handle order insert response."""
        if pRspInfo is None or pRspInfo.ErrorID == 0:
            return
        self._emit_rejected_order(
            input_order=pInputOrder,
            error_id=getattr(pRspInfo, "ErrorID", 0),
            error_msg=self._to_text(getattr(pRspInfo, "ErrorMsg", "")),
            source="OnRspOrderInsert",
        )

    def OnErrRtnOrderInsert(self, pInputOrder: Any, pRspInfo: Any) -> None:
        """Handle asynchronous order insert reject."""
        self._emit_rejected_order(
            input_order=pInputOrder,
            error_id=getattr(pRspInfo, "ErrorID", 0),
            error_msg=self._to_text(getattr(pRspInfo, "ErrorMsg", "")),
            source="OnErrRtnOrderInsert",
        )

    def OnRtnOrder(self, pOrder: Any) -> None:
        """Handle order return event."""
        order_ref = self._to_text(getattr(pOrder, "OrderRef", ""))
        order_sys_id = self._to_text(getattr(pOrder, "OrderSysID", "")).strip()
        front_id = int(getattr(pOrder, "FrontID", 0) or self.front_id)
        session_id = int(getattr(pOrder, "SessionID", 0) or self.session_id)
        payload = {
            "client_order_id": self.order_ref_to_client_order_id.get(order_ref, ""),
            "broker_order_id": self._make_broker_order_id(
                front_id=front_id,
                session_id=session_id,
                order_ref=order_ref,
                order_sys_id=order_sys_id,
            ),
            "symbol": self._to_text(getattr(pOrder, "InstrumentID", "")),
            "status": self._map_order_status(getattr(pOrder, "OrderStatus", "")),
            "filled_quantity": float(getattr(pOrder, "VolumeTraded", 0.0) or 0.0),
            "avg_fill_price": float(getattr(pOrder, "LimitPrice", 0.0) or 0.0),
            "reject_reason": self._to_text(getattr(pOrder, "StatusMsg", "")),
            "timestamp_ns": time.time_ns(),
            "order_ref": order_ref,
        }
        if self.order_callback is not None:
            self.order_callback(payload)

    def OnRtnTrade(self, pTrade: Any) -> None:
        """Handle trade return event."""
        order_ref = self._to_text(getattr(pTrade, "OrderRef", ""))
        order_sys_id = self._to_text(getattr(pTrade, "OrderSysID", "")).strip()
        front_id = int(getattr(pTrade, "FrontID", 0) or self.front_id)
        session_id = int(getattr(pTrade, "SessionID", 0) or self.session_id)
        payload = {
            "trade_id": self._to_text(getattr(pTrade, "TradeID", "")),
            "broker_order_id": self._make_broker_order_id(
                front_id=front_id,
                session_id=session_id,
                order_ref=order_ref,
                order_sys_id=order_sys_id,
            ),
            "client_order_id": self.order_ref_to_client_order_id.get(order_ref, ""),
            "symbol": self._to_text(getattr(pTrade, "InstrumentID", "")),
            "side": self._map_direction(getattr(pTrade, "Direction", "")),
            "quantity": float(getattr(pTrade, "Volume", 0.0) or 0.0),
            "price": float(getattr(pTrade, "Price", 0.0) or 0.0),
            "timestamp_ns": time.time_ns(),
            "order_ref": order_ref,
        }
        if self.trade_callback is not None:
            self.trade_callback(payload)

    def _emit_rejected_order(
        self,
        *,
        input_order: Any,
        error_id: Any,
        error_msg: str,
        source: str,
    ) -> None:
        order_ref = self._to_text(getattr(input_order, "OrderRef", ""))
        broker_order_id = self._make_broker_order_id(
            front_id=self.front_id,
            session_id=self.session_id,
            order_ref=order_ref,
            order_sys_id="",
        )
        payload = {
            "client_order_id": self.order_ref_to_client_order_id.get(order_ref, ""),
            "broker_order_id": broker_order_id,
            "symbol": self._to_text(getattr(input_order, "InstrumentID", "")),
            "status": "rejected",
            "filled_quantity": 0.0,
            "avg_fill_price": float(getattr(input_order, "LimitPrice", 0.0) or 0.0),
            "reject_reason": error_msg,
            "timestamp_ns": time.time_ns(),
            "order_ref": order_ref,
            "error_code": str(error_id),
        }
        if self.order_callback is not None:
            self.order_callback(payload)
        if self.error_callback is not None:
            self.error_callback(
                {
                    "event_type": "order_reject",
                    "source": source,
                    "broker_order_id": broker_order_id,
                    "client_order_id": payload["client_order_id"],
                    "symbol": payload["symbol"],
                    "error_code": str(error_id),
                    "error_message": error_msg,
                    "timestamp_ns": payload["timestamp_ns"],
                    "order_ref": order_ref,
                }
            )

    def _make_broker_order_id(
        self,
        *,
        front_id: int,
        session_id: int,
        order_ref: str,
        order_sys_id: str,
    ) -> str:
        base = f"ctp-{front_id}-{session_id}-{order_ref}"
        if order_sys_id:
            return f"{base}-{order_sys_id}"
        return base

    def _parse_broker_order_id(self, broker_order_id: str) -> dict[str, Any]:
        text = str(broker_order_id).strip()
        parts = text.split("-")
        if len(parts) < 4 or parts[0] != "ctp":
            return {}
        return {
            "front_id": int(parts[1]) if parts[1].isdigit() else self.front_id,
            "session_id": int(parts[2]) if parts[2].isdigit() else self.session_id,
            "order_ref": parts[3],
            "order_sys_id": "-".join(parts[4:]) if len(parts) > 4 else "",
        }

    def _map_order_status(self, raw_status: Any) -> str:
        key = self._to_text(raw_status)
        status_map = {
            "0": "filled",
            "1": "partially_filled",
            "2": "partially_filled",
            "3": "submitted",
            "4": "submitted",
            "5": "cancelled",
            "a": "submitted",
            "b": "submitted",
            "c": "submitted",
        }
        if key in status_map:
            return status_map[key]
        return key.lower() if key else "submitted"

    def _map_direction(self, raw_direction: Any) -> str:
        key = self._to_text(raw_direction)
        if key in {"0", "buy", "b"}:
            return "Buy"
        if key in {"1", "sell", "s"}:
            return "Sell"
        return str(raw_direction)

    def _to_text(self, value: Any) -> str:
        if isinstance(value, bytes):
            try:
                return value.decode("gbk", errors="ignore").strip()
            except Exception:
                return value.decode("utf-8", errors="ignore").strip()
        return str(value).strip()


class CTPMarketGateway(mdapi.CThostFtdcMdSpi):  # type: ignore
    """
    CTP Market Data Gateway.

    Subscribes to market data and pushes Ticks (as Bars) to AKQuant DataFeed.
    """

    def __init__(
        self,
        feed: DataFeed,
        front_url: str,
        symbols: List[str],
        use_aggregator: bool = True,
    ):
        """
        Initialize the Market Gateway.

        :param feed: AKQuant DataFeed instance
        :param front_url: CTP Front URL (e.g., tcp://180.168.146.187:10131)
        :param symbols: List of symbols to subscribe (e.g., ["au2310", "rb2310"])
        :param use_aggregator: If True, uses BarAggregator to generate 1-min bars.
                               If False, pushes each tick as a Bar immediately.
        """
        if not HAS_OPENCTP:
            raise ImportError(
                "openctp-ctp is not installed. Please run `pip install openctp-ctp`."
            )

        mdapi.CThostFtdcMdSpi.__init__(self)
        self.feed = feed
        self.front_url = front_url
        self.symbols = symbols
        self.use_aggregator = use_aggregator

        self.api: Any = None
        self.req_id = 0
        self.connected = False
        self.last_volume: Dict[str, float] = {}

        self.aggregator: Optional[BarAggregator]
        if self.use_aggregator:
            self.aggregator = BarAggregator(feed)
        else:
            self.aggregator = None

    def start(self) -> None:
        """Start the CTP Market API in a blocking way (should be run in a thread)."""
        print(f"[CTP] Connecting to {self.front_url}...")
        try:
            self.api = mdapi.CThostFtdcMdApi.CreateFtdcMdApi()
            self.api.RegisterFront(self.front_url)
            self.api.RegisterSpi(self)
            self.api.Init()
            print("[CTP] API Initialized, joining thread...")
            self.api.Join()
        except Exception as e:
            print(f"[CTP] ERROR: Failed to start CTP API: {e}")

    def OnFrontConnected(self) -> None:
        """Handle front connection event."""
        print(f"[CTP] OnFrontConnected: Successfully connected to {self.front_url}")
        self.connected = True

        req = mdapi.CThostFtdcReqUserLoginField()
        self.req_id += 1
        print(f"[CTP] Requesting User Login (ReqID={self.req_id})...")
        if self.api:
            self.api.ReqUserLogin(req, self.req_id)

    def OnFrontDisconnected(self, nReason: int) -> None:
        """Handle front disconnection event."""
        print(f"[CTP] OnFrontDisconnected. [nReason={nReason}]")
        self.connected = False

    def OnRspUserLogin(
        self, pRspUserLogin: Any, pRspInfo: Any, nRequestID: int, bIsLast: bool
    ) -> None:
        """Handle login response."""
        if pRspInfo is not None and pRspInfo.ErrorID != 0:
            print(
                f"[CTP] Login failed. ErrorID={pRspInfo.ErrorID}, "
                f"Msg={pRspInfo.ErrorMsg}"
            )
            return

        print(
            f"[CTP] Login succeed. TradingDay: {pRspUserLogin.TradingDay}, "
            f"BrokerID: {pRspUserLogin.BrokerID}, UserID: {pRspUserLogin.UserID}"
        )

        print(f"[CTP] Subscribing to {self.symbols}...")
        self.req_id += 1
        if self.api:
            ret = self.api.SubscribeMarketData(
                [s.encode("utf-8") for s in self.symbols], len(self.symbols)
            )
            if ret == 0:
                print("[CTP] Subscribe request sent successfully.")
            else:
                print(f"[CTP] Subscribe request failed with code {ret}")

    def OnRspSubMarketData(
        self,
        pSpecificInstrument: Any,
        pRspInfo: Any,
        nRequestID: int,
        bIsLast: bool,
    ) -> None:
        """Handle subscribe response."""
        if pRspInfo is not None and pRspInfo.ErrorID != 0:
            print(
                f"[CTP] Subscribe failed for [{pSpecificInstrument.InstrumentID}]: "
                f"{pRspInfo.ErrorMsg}"
            )
            return
        print(f"[CTP] Subscribe succeed for [{pSpecificInstrument.InstrumentID}]")

    def OnRtnDepthMarketData(self, pDepthMarketData: Any) -> None:
        """Process market data tick."""
        symbol = pDepthMarketData.InstrumentID
        price = pDepthMarketData.LastPrice
        volume = pDepthMarketData.Volume

        if price > 1e7 or price <= 0:
            return

        now_ns = time.time_ns()

        if self.use_aggregator and self.aggregator:
            self.aggregator.on_tick(symbol, price, float(volume), now_ns)
        else:
            last_vol = self.last_volume.get(symbol, volume)
            delta_vol = volume - last_vol
            self.last_volume[symbol] = volume

            if delta_vol < 0:
                delta_vol = volume

            bar = Bar(
                timestamp=now_ns,
                symbol=symbol,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=float(delta_vol),
                extra={},
            )

            self.feed.add_bar(bar)  # type: ignore
