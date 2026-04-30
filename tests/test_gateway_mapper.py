from akquant.gateway import UnifiedErrorType, UnifiedOrderStatus, create_default_mapper


def test_map_order_status() -> None:
    """Map broker raw statuses to unified statuses."""
    mapper = create_default_mapper()
    assert mapper.map_order_status("new") == UnifiedOrderStatus.NEW
    assert mapper.map_order_status("filled") == UnifiedOrderStatus.FILLED
    assert mapper.map_order_status("unknown") == UnifiedOrderStatus.SUBMITTED


def test_classify_error() -> None:
    """Classify broker errors into retry, risk, and non-retry categories."""
    mapper = create_default_mapper()
    assert mapper.classify_error("2001") == UnifiedErrorType.RISK_REJECTED
    assert mapper.classify_error("1001") == UnifiedErrorType.RETRYABLE
    assert (
        mapper.classify_error("x", "network disconnected") == UnifiedErrorType.RETRYABLE
    )


def test_map_structured_events() -> None:
    """Map order, trade and execution report payloads."""
    mapper = create_default_mapper()
    payload = {
        "client_order_id": "c1",
        "broker_order_id": "b1",
        "symbol": "000001.SZ",
        "status": "filled",
        "filled_quantity": 100.0,
        "avg_fill_price": 12.3,
        "timestamp_ns": 123,
    }
    order = mapper.map_order_event(payload)
    trade = mapper.map_trade_event(
        {
            "trade_id": "t1",
            "broker_order_id": "b1",
            "client_order_id": "c1",
            "symbol": "000001.SZ",
            "side": "Buy",
            "quantity": 100.0,
            "price": 12.3,
            "timestamp_ns": 124,
        }
    )
    report = mapper.map_execution_report(payload)
    assert order.status == UnifiedOrderStatus.FILLED
    assert trade.trade_id == "t1"
    assert report.status == UnifiedOrderStatus.FILLED


def test_map_unknown_status_defaults_to_submitted() -> None:
    """Unknown raw status should fall back to SUBMITTED."""
    mapper = create_default_mapper()
    assert mapper.map_order_status("weird_status") == UnifiedOrderStatus.SUBMITTED
    assert mapper.map_order_status("") == UnifiedOrderStatus.SUBMITTED


def test_map_trade_event_with_minimal_fields() -> None:
    """Map trade event with only required fields, defaults for the rest."""
    mapper = create_default_mapper()
    trade = mapper.map_trade_event(
        {
            "trade_id": "t-min",
            "broker_order_id": "b-min",
            "client_order_id": "",
            "symbol": "000001.SZ",
            "side": "buy",
            "quantity": 1.0,
            "price": 10.0,
            "timestamp_ns": 0,
        }
    )
    assert trade.trade_id == "t-min"
    assert trade.client_order_id == ""
