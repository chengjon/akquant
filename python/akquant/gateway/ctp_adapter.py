import time
from typing import Any, Callable, Sequence

from ..akquant import DataFeed
from .ctp_native import CTPMarketGateway, CTPTraderGateway
from .mapper import BrokerEventMapper, create_default_mapper
from .models import (
    UnifiedAccount,
    UnifiedExecutionReport,
    UnifiedOrderRequest,
    UnifiedOrderSnapshot,
    UnifiedOrderStatus,
    UnifiedPosition,
    UnifiedTrade,
)


class CTPMarketAdapter:
    """CTP market adapter implementing unified market gateway protocol."""

    def __init__(
        self,
        feed: DataFeed,
        front_url: str,
        symbols: Sequence[str],
        use_aggregator: bool = True,
    ) -> None:
        """Initialize CTP market adapter."""
        self.front_url = front_url
        self.symbols = list(symbols)
        self.gateway = CTPMarketGateway(
            feed=feed,
            front_url=front_url,
            symbols=list(symbols),
            use_aggregator=use_aggregator,
        )
        self.tick_callback: Callable[[dict[str, Any]], None] | None = None
        self.bar_callback: Callable[[dict[str, Any]], None] | None = None

    def connect(self) -> None:
        """Connect and start market stream."""
        self.gateway.start()

    def disconnect(self) -> None:
        """Disconnect market stream."""
        if hasattr(self.gateway, "api") and self.gateway.api:
            self.gateway.api.Release()

    def subscribe(self, symbols: Sequence[str]) -> None:
        """Update subscribed symbols."""
        self.symbols = list(symbols)
        self.gateway.symbols = list(symbols)

    def unsubscribe(self, symbols: Sequence[str]) -> None:
        """Remove symbols from subscription list."""
        removed = set(symbols)
        self.symbols = [s for s in self.symbols if s not in removed]
        self.gateway.symbols = list(self.symbols)

    def on_tick(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register tick callback."""
        self.tick_callback = callback

    def on_bar(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register bar callback."""
        self.bar_callback = callback

    def start(self) -> None:
        """Start market adapter."""
        self.connect()


class CTPTraderAdapter:
    """CTP trader adapter implementing unified trader gateway protocol."""

    def __init__(
        self,
        front_url: str,
        broker_id: str = "9999",
        user_id: str = "",
        password: str = "",
        auth_code: str = "0000000000000000",
        app_id: str = "simnow_client_test",
        execution_semantics_mode: str = "strict",
    ) -> None:
        """Initialize CTP trader adapter."""
        normalized_mode = str(execution_semantics_mode).strip().lower()
        if normalized_mode not in {"strict", "compatible"}:
            raise ValueError(
                "execution_semantics_mode must be 'strict' or 'compatible'"
            )
        self.execution_semantics_mode = normalized_mode
        self.mapper: BrokerEventMapper = create_default_mapper()
        self.order_callback: Callable[[UnifiedOrderSnapshot], None] | None = None
        self.trade_callback: Callable[[UnifiedTrade], None] | None = None
        self.execution_callback: Callable[[UnifiedExecutionReport], None] | None = None
        self.orders: dict[str, UnifiedOrderSnapshot] = {}
        self.trades: list[UnifiedTrade] = []
        self.client_to_broker_order_ids: dict[str, str] = {}
        self.broker_to_client_order_ids: dict[str, str] = {}
        self.order_ref_to_client_order_ids: dict[str, str] = {}
        self.pending_reject_reasons: dict[str, str] = {}
        self._order_seq = 0
        self.gateway = CTPTraderGateway(
            front_url=front_url,
            broker_id=broker_id,
            user_id=user_id,
            password=password,
            auth_code=auth_code,
            app_id=app_id,
        )
        if hasattr(self.gateway, "set_order_handler"):
            self.gateway.set_order_handler(self._handle_native_order_event)
        if hasattr(self.gateway, "set_trade_handler"):
            self.gateway.set_trade_handler(self._handle_native_trade_event)
        if hasattr(self.gateway, "set_error_handler"):
            self.gateway.set_error_handler(self._handle_native_error_event)

    def connect(self) -> None:
        """Connect and start trader stream."""
        self.gateway.start()

    def disconnect(self) -> None:
        """Disconnect trader stream."""
        if hasattr(self.gateway, "api") and self.gateway.api:
            self.gateway.api.Release()

    def place_order(self, req: UnifiedOrderRequest) -> str:
        """Place order through CTP trader channel."""
        existing_broker_order_id = self.client_to_broker_order_ids.get(
            req.client_order_id
        )
        if existing_broker_order_id is not None:
            existing = self.orders.get(existing_broker_order_id)
            if existing is not None and existing.status in (
                UnifiedOrderStatus.NEW,
                UnifiedOrderStatus.SUBMITTED,
                UnifiedOrderStatus.PARTIALLY_FILLED,
            ):
                return existing_broker_order_id
            if existing is not None and self._is_terminal_status(existing.status):
                self._unlink_order_mapping(
                    client_order_id=req.client_order_id,
                    broker_order_id=existing_broker_order_id,
                )
        if not self.heartbeat():
            raise RuntimeError("CTP trader is not connected")
        native_result = self.gateway.insert_order(
            client_order_id=req.client_order_id,
            symbol=req.symbol,
            side=req.side,
            quantity=req.quantity,
            price=req.price,
            order_type=req.order_type,
            time_in_force=req.time_in_force,
        )
        self._order_seq += 1
        now_ns = int(native_result.get("timestamp_ns", time.time_ns()))
        broker_order_id = str(
            native_result.get(
                "broker_order_id", f"ctp-{req.client_order_id}-{self._order_seq}"
            )
        )
        order_ref = str(native_result.get("order_ref", "")).strip()
        if order_ref:
            self.order_ref_to_client_order_ids[order_ref] = req.client_order_id
        snapshot = UnifiedOrderSnapshot(
            client_order_id=req.client_order_id,
            broker_order_id=broker_order_id,
            symbol=req.symbol,
            status=UnifiedOrderStatus.SUBMITTED,
            timestamp_ns=now_ns,
        )
        self.orders[broker_order_id] = snapshot
        self._sync_order_mapping(req.client_order_id, broker_order_id)
        self._emit_order(snapshot)
        report = UnifiedExecutionReport(
            broker_order_id=broker_order_id,
            client_order_id=req.client_order_id,
            status=UnifiedOrderStatus.SUBMITTED,
            symbol=req.symbol,
            timestamp_ns=now_ns,
        )
        self._emit_execution_report(report)
        return broker_order_id

    def cancel_order(self, broker_order_id: str) -> None:
        """Cancel order through CTP trader channel."""
        self.gateway.cancel_order(broker_order_id)
        if self.execution_semantics_mode != "compatible":
            return
        order = self.orders.get(broker_order_id)
        if order is None:
            return
        order.status = UnifiedOrderStatus.CANCELLED
        order.timestamp_ns = time.time_ns()
        self._emit_order(order)
        report = UnifiedExecutionReport(
            broker_order_id=order.broker_order_id,
            client_order_id=order.client_order_id,
            status=order.status,
            symbol=order.symbol,
            filled_quantity=order.filled_quantity,
            avg_fill_price=order.avg_fill_price,
            reject_reason=order.reject_reason,
            timestamp_ns=order.timestamp_ns,
        )
        self._emit_execution_report(report)
        self._cleanup_terminal_order_mapping(order)

    def query_order(self, broker_order_id: str) -> UnifiedOrderSnapshot | None:
        """Query order status from broker."""
        return self.orders.get(broker_order_id)

    def query_trades(self, since: int | None = None) -> list[UnifiedTrade]:
        """Query trade fills from broker."""
        if since is None:
            return list(self.trades)
        return [t for t in self.trades if t.timestamp_ns >= since]

    def query_account(self) -> UnifiedAccount | None:
        """Query account snapshot from broker."""
        return None

    def query_positions(self) -> list[UnifiedPosition]:
        """Query position snapshots from broker."""
        return []

    def on_order(self, callback: Callable[[UnifiedOrderSnapshot], None]) -> None:
        """Register order callback."""
        self.order_callback = callback

    def on_trade(self, callback: Callable[[UnifiedTrade], None]) -> None:
        """Register trade callback."""
        self.trade_callback = callback

    def on_execution_report(
        self, callback: Callable[[UnifiedExecutionReport], None]
    ) -> None:
        """Register execution report callback."""
        self.execution_callback = callback

    def sync_open_orders(self) -> list[UnifiedOrderSnapshot]:
        """Sync open order snapshots from broker."""
        open_statuses = (
            UnifiedOrderStatus.NEW,
            UnifiedOrderStatus.SUBMITTED,
            UnifiedOrderStatus.PARTIALLY_FILLED,
        )
        return [
            order for order in self.orders.values() if order.status in open_statuses
        ]

    def sync_today_trades(self) -> list[UnifiedTrade]:
        """Sync today's trade fills from broker."""
        return []

    def heartbeat(self) -> bool:
        """Return whether trader connection is alive."""
        can_trade = getattr(self.gateway, "can_trade", None)
        if callable(can_trade):
            return bool(can_trade())
        return bool(getattr(self.gateway, "connected", False))

    def start(self) -> None:
        """Start trader adapter."""
        self.connect()

    def ingest_order_event(self, payload: dict[str, Any]) -> UnifiedOrderSnapshot:
        """Map and consume broker order event."""
        snapshot = self.mapper.map_order_event(payload)
        self.orders[snapshot.broker_order_id] = snapshot
        self._sync_order_mapping(
            client_order_id=snapshot.client_order_id,
            broker_order_id=snapshot.broker_order_id,
        )
        if self.order_callback is not None:
            self.order_callback(snapshot)
        report = self.mapper.map_execution_report(payload)
        if self.execution_callback is not None:
            self.execution_callback(report)
        self._cleanup_terminal_order_mapping(snapshot)
        return snapshot

    def ingest_trade_event(self, payload: dict[str, Any]) -> UnifiedTrade:
        """Map and consume broker trade event."""
        trade = self.mapper.map_trade_event(payload)
        self._sync_order_mapping(
            client_order_id=trade.client_order_id,
            broker_order_id=trade.broker_order_id,
        )
        self.trades.append(trade)
        if self.trade_callback is not None:
            self.trade_callback(trade)
        return trade

    def _emit_order(self, order: UnifiedOrderSnapshot) -> None:
        if self.order_callback is not None:
            self.order_callback(order)

    def _emit_execution_report(self, report: UnifiedExecutionReport) -> None:
        if self.execution_callback is not None:
            self.execution_callback(report)

    def _sync_order_mapping(self, client_order_id: str, broker_order_id: str) -> None:
        if client_order_id and broker_order_id:
            self.client_to_broker_order_ids[client_order_id] = broker_order_id
            self.broker_to_client_order_ids[broker_order_id] = client_order_id

    def _unlink_order_mapping(self, client_order_id: str, broker_order_id: str) -> None:
        if client_order_id:
            self.client_to_broker_order_ids.pop(client_order_id, None)
        if broker_order_id:
            self.broker_to_client_order_ids.pop(broker_order_id, None)

    def _cleanup_terminal_order_mapping(self, snapshot: UnifiedOrderSnapshot) -> None:
        if self._is_terminal_status(snapshot.status):
            self._unlink_order_mapping(
                client_order_id=snapshot.client_order_id,
                broker_order_id=snapshot.broker_order_id,
            )

    def _is_terminal_status(self, status: UnifiedOrderStatus) -> bool:
        return status in (
            UnifiedOrderStatus.FILLED,
            UnifiedOrderStatus.CANCELLED,
            UnifiedOrderStatus.REJECTED,
        )

    def _handle_native_order_event(self, payload: dict[str, Any]) -> None:
        data = dict(payload)
        order_ref = str(data.get("order_ref", "")).strip()
        client_order_id = str(data.get("client_order_id", "")).strip()
        if not client_order_id and order_ref:
            client_order_id = self.order_ref_to_client_order_ids.get(order_ref, "")
            if client_order_id:
                data["client_order_id"] = client_order_id
        broker_order_id = str(data.get("broker_order_id", "")).strip()
        if not broker_order_id:
            return
        pending_reject_reason = self.pending_reject_reasons.pop(
            broker_order_id, ""
        ).strip()
        if pending_reject_reason and not str(data.get("reject_reason", "")).strip():
            data["reject_reason"] = pending_reject_reason
        self.ingest_order_event(data)

    def _handle_native_trade_event(self, payload: dict[str, Any]) -> None:
        data = dict(payload)
        order_ref = str(data.get("order_ref", "")).strip()
        client_order_id = str(data.get("client_order_id", "")).strip()
        if not client_order_id and order_ref:
            client_order_id = self.order_ref_to_client_order_ids.get(order_ref, "")
            if client_order_id:
                data["client_order_id"] = client_order_id
        broker_order_id = str(data.get("broker_order_id", "")).strip()
        if not broker_order_id:
            return
        self.ingest_trade_event(data)

    def _handle_native_error_event(self, payload: dict[str, Any]) -> None:
        data = dict(payload)
        broker_order_id = str(data.get("broker_order_id", "")).strip()
        if not broker_order_id:
            return
        if self.execution_semantics_mode == "compatible":
            self.ingest_order_event(
                {
                    "client_order_id": str(data.get("client_order_id", "")).strip(),
                    "broker_order_id": broker_order_id,
                    "symbol": str(data.get("symbol", "")).strip(),
                    "status": "rejected",
                    "filled_quantity": 0.0,
                    "avg_fill_price": 0.0,
                    "reject_reason": str(data.get("error_message", "")).strip(),
                    "timestamp_ns": int(data.get("timestamp_ns", time.time_ns())),
                }
            )
            return
        reject_reason = str(data.get("error_message", "")).strip()
        if reject_reason:
            self.pending_reject_reasons[broker_order_id] = reject_reason
