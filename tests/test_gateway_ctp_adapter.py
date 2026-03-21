from typing import Any, cast

from akquant.gateway.ctp_adapter import CTPTraderAdapter
from akquant.gateway.mapper import create_default_mapper
from akquant.gateway.models import UnifiedOrderRequest, UnifiedOrderStatus


def _build_adapter(
    connected: bool = True, execution_semantics_mode: str = "strict"
) -> CTPTraderAdapter:
    class Gateway:
        def __init__(self, connected_flag: bool) -> None:
            self.connected = connected_flag
            self.login_status = connected_flag
            self.ready_to_trade = connected_flag

        def can_trade(self) -> bool:
            return self.connected and self.login_status and self.ready_to_trade

        def insert_order(self, **kwargs: object) -> dict[str, object]:
            client_order_id = str(kwargs.get("client_order_id", ""))
            return {
                "broker_order_id": f"ctp-1-2-{client_order_id}",
                "order_ref": f"ref-{client_order_id}",
                "timestamp_ns": 1,
            }

        def cancel_order(self, broker_order_id: str) -> None:
            _ = broker_order_id

    adapter = CTPTraderAdapter.__new__(CTPTraderAdapter)
    adapter.mapper = create_default_mapper()
    adapter.order_callback = None
    adapter.trade_callback = None
    adapter.execution_callback = None
    adapter.orders = {}
    adapter.trades = []
    adapter.client_to_broker_order_ids = {}
    adapter.broker_to_client_order_ids = {}
    adapter.order_ref_to_client_order_ids = {}
    adapter.pending_reject_reasons = {}
    adapter.execution_semantics_mode = execution_semantics_mode
    adapter._order_seq = 0
    adapter.gateway = cast(Any, Gateway(connected))
    return adapter


def test_ctp_adapter_place_and_cancel_order() -> None:
    """Cancel request should rely on native order callback to reach terminal state."""
    adapter = _build_adapter(connected=True)
    order_ids: list[str] = []
    report_ids: list[str] = []
    adapter.on_order(lambda order: order_ids.append(order.broker_order_id))
    adapter.on_execution_report(
        lambda report: report_ids.append(report.broker_order_id)
    )

    broker_order_id = adapter.place_order(
        UnifiedOrderRequest(
            client_order_id="c1",
            symbol="au2606",
            side="Buy",
            quantity=1.0,
        )
    )
    adapter.cancel_order(broker_order_id)
    adapter._handle_native_order_event(
        {
            "broker_order_id": broker_order_id,
            "client_order_id": "c1",
            "symbol": "au2606",
            "status": "cancelled",
            "timestamp_ns": 2,
        }
    )

    assert broker_order_id.startswith("ctp-1-2-c1")
    assert order_ids[0] == broker_order_id
    assert report_ids[0] == broker_order_id
    assert report_ids[-1] == broker_order_id
    assert adapter.query_order(broker_order_id) is not None


def test_ctp_adapter_deduplicates_active_client_order_id() -> None:
    """Duplicate active client_order_id should return existing broker order id."""
    adapter = _build_adapter(connected=True)
    req = UnifiedOrderRequest(
        client_order_id="dup-c1",
        symbol="ag2606",
        side="Buy",
        quantity=1.0,
    )
    first = adapter.place_order(req)
    second = adapter.place_order(req)

    assert first == second
    assert len(adapter.orders) == 1


def test_ctp_adapter_ingest_events_update_state() -> None:
    """Ingested order/trade events should update adapter state."""
    adapter = _build_adapter(connected=True)
    trades: list[str] = []
    adapter.on_trade(lambda trade: trades.append(trade.trade_id))

    snapshot = adapter.ingest_order_event(
        {
            "client_order_id": "c2",
            "broker_order_id": "b2",
            "symbol": "rb2605",
            "status": "submitted",
            "timestamp_ns": 1,
        }
    )
    trade = adapter.ingest_trade_event(
        {
            "trade_id": "t2",
            "broker_order_id": "b2",
            "client_order_id": "c2",
            "symbol": "rb2605",
            "side": "Buy",
            "quantity": 1.0,
            "price": 100.0,
            "timestamp_ns": 2,
        }
    )

    assert snapshot.broker_order_id == "b2"
    assert trade.trade_id == "t2"
    assert trades == ["t2"]
    assert adapter.query_trades()[-1].trade_id == "t2"


def test_ctp_adapter_native_event_flow_advances_status() -> None:
    """Native order and trade events should update unified state."""
    adapter = _build_adapter(connected=True)
    adapter.order_ref_to_client_order_ids["42"] = "c42"

    adapter._handle_native_order_event(
        {
            "order_ref": "42",
            "broker_order_id": "ctp-1-2-42",
            "symbol": "au2606",
            "status": "partially_filled",
            "filled_quantity": 1.0,
            "avg_fill_price": 500.0,
            "timestamp_ns": 10,
        }
    )
    adapter._handle_native_trade_event(
        {
            "order_ref": "42",
            "trade_id": "t42",
            "broker_order_id": "ctp-1-2-42",
            "symbol": "au2606",
            "side": "Buy",
            "quantity": 1.0,
            "price": 500.0,
            "timestamp_ns": 11,
        }
    )
    adapter._handle_native_order_event(
        {
            "order_ref": "42",
            "broker_order_id": "ctp-1-2-42",
            "symbol": "au2606",
            "status": "filled",
            "filled_quantity": 1.0,
            "avg_fill_price": 500.0,
            "timestamp_ns": 12,
        }
    )

    snapshot = adapter.query_order("ctp-1-2-42")
    assert snapshot is not None
    assert snapshot.status == UnifiedOrderStatus.FILLED
    assert adapter.query_trades()[-1].trade_id == "t42"


def test_ctp_adapter_native_error_maps_to_rejected() -> None:
    """Native reject event should wait for order callback to mark rejected."""
    adapter = _build_adapter(connected=True)
    adapter.place_order(
        UnifiedOrderRequest(
            client_order_id="r1",
            symbol="ag2606",
            side="Buy",
            quantity=1.0,
        )
    )
    adapter._handle_native_error_event(
        {
            "broker_order_id": "ctp-1-2-r1",
            "client_order_id": "r1",
            "symbol": "ag2606",
            "error_message": "insufficient funds",
            "timestamp_ns": 13,
        }
    )
    snapshot_before = adapter.query_order("ctp-1-2-r1")
    assert snapshot_before is not None
    assert snapshot_before.status == UnifiedOrderStatus.SUBMITTED
    adapter._handle_native_order_event(
        {
            "broker_order_id": "ctp-1-2-r1",
            "client_order_id": "r1",
            "symbol": "ag2606",
            "status": "rejected",
            "timestamp_ns": 14,
        }
    )

    snapshot = adapter.query_order("ctp-1-2-r1")
    assert snapshot is not None
    assert snapshot.status == UnifiedOrderStatus.REJECTED
    assert snapshot.reject_reason == "insufficient funds"


def test_ctp_adapter_compatible_mode_rejects_on_error_event() -> None:
    """Compatible mode should immediately mark rejected on native error event."""
    adapter = _build_adapter(connected=True, execution_semantics_mode="compatible")
    adapter.place_order(
        UnifiedOrderRequest(
            client_order_id="r2",
            symbol="ag2606",
            side="Buy",
            quantity=1.0,
        )
    )
    adapter._handle_native_error_event(
        {
            "broker_order_id": "ctp-1-2-r2",
            "client_order_id": "r2",
            "symbol": "ag2606",
            "error_message": "risk blocked",
            "timestamp_ns": 15,
        }
    )

    snapshot = adapter.query_order("ctp-1-2-r2")
    assert snapshot is not None
    assert snapshot.status == UnifiedOrderStatus.REJECTED
    assert snapshot.reject_reason == "risk blocked"


def test_ctp_adapter_place_order_requires_connection() -> None:
    """Placing order without connection should fail fast."""
    adapter = _build_adapter(connected=False)
    try:
        adapter.place_order(
            UnifiedOrderRequest(
                client_order_id="c3",
                symbol="au2606",
                side="Sell",
                quantity=1.0,
            )
        )
    except RuntimeError as exc:
        assert "not connected" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for disconnected ctp trader")


def test_ctp_adapter_sync_open_orders_excludes_terminal_orders() -> None:
    """Cancelled orders should be excluded from open order sync."""
    adapter = _build_adapter(connected=True)
    broker_order_id = adapter.place_order(
        UnifiedOrderRequest(
            client_order_id="c4",
            symbol="ag2606",
            side="Buy",
            quantity=1.0,
        )
    )
    open_orders = adapter.sync_open_orders()
    assert any(order.broker_order_id == broker_order_id for order in open_orders)

    adapter.cancel_order(broker_order_id)
    adapter._handle_native_order_event(
        {
            "broker_order_id": broker_order_id,
            "client_order_id": "c4",
            "symbol": "ag2606",
            "status": "cancelled",
            "timestamp_ns": 3,
        }
    )
    open_orders_after_cancel = adapter.sync_open_orders()
    assert all(
        order.broker_order_id != broker_order_id for order in open_orders_after_cancel
    )
