"""Tests for MiniQMT xtquant bridge and gateway bridge integration."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from akquant.gateway.models import (
    UnifiedOrderRequest,
    UnifiedOrderSnapshot,
    UnifiedOrderStatus,
)
from akquant.gateway.miniqmt import MiniQMTTraderGateway


# ---------------------------------------------------------------------------
# Symbol format conversion (does not require xtquant)
# ---------------------------------------------------------------------------


class TestSymbolConversion:
    """Test QMTXtQuantBridge symbol format helpers.

    These tests use the static methods directly so they don't need xtquant.
    """

    def test_format_sh_symbol(self) -> None:
        from akquant.gateway.miniqmt_xtquant import QMTXtQuantBridge

        assert QMTXtQuantBridge.format_symbol("600000") == "SH.600000"

    def test_format_sz_symbol(self) -> None:
        from akquant.gateway.miniqmt_xtquant import QMTXtQuantBridge

        assert QMTXtQuantBridge.format_symbol("000001") == "SZ.000001"
        assert QMTXtQuantBridge.format_symbol("300001") == "SZ.300001"

    def test_format_bj_symbol(self) -> None:
        from akquant.gateway.miniqmt_xtquant import QMTXtQuantBridge

        assert QMTXtQuantBridge.format_symbol("430001") == "BJ.430001"
        assert QMTXtQuantBridge.format_symbol("830001") == "BJ.830001"

    def test_format_already_prefixed(self) -> None:
        from akquant.gateway.miniqmt_xtquant import QMTXtQuantBridge

        assert QMTXtQuantBridge.format_symbol("SH.600000") == "SH.600000"

    def test_format_unknown_prefix(self) -> None:
        from akquant.gateway.miniqmt_xtquant import QMTXtQuantBridge

        assert QMTXtQuantBridge.format_symbol("1234") == "1234"

    def test_strip_symbol(self) -> None:
        from akquant.gateway.miniqmt_xtquant import QMTXtQuantBridge

        assert QMTXtQuantBridge.strip_symbol("SH.600000") == "600000"
        assert QMTXtQuantBridge.strip_symbol("SZ.000001") == "000001"

    def test_strip_no_prefix(self) -> None:
        from akquant.gateway.miniqmt_xtquant import QMTXtQuantBridge

        assert QMTXtQuantBridge.strip_symbol("600000") == "600000"


# ---------------------------------------------------------------------------
# xtquant import fallback
# ---------------------------------------------------------------------------


class TestXtquantImportFallback:
    """Verify the module handles missing xtquant gracefully."""

    def test_has_xtquant_flag_exists(self) -> None:
        from akquant.gateway.miniqmt_xtquant import HAS_XTQUANT

        assert isinstance(HAS_XTQUANT, bool)

    def test_bridge_raises_without_xtquant(self) -> None:
        from akquant.gateway.miniqmt_xtquant import HAS_XTQUANT, QMTXtQuantBridge

        if not HAS_XTQUANT:
            with pytest.raises(ImportError, match="xtquant"):
                QMTXtQuantBridge(
                    qmt_path="/fake", account_id="test", gateway=MagicMock()
                )


# ---------------------------------------------------------------------------
# Gateway bridge integration (with mock bridge)
# ---------------------------------------------------------------------------


class TestGatewayBridgeIntegration:
    """Test MiniQMTTraderGateway with a mock bridge attached."""

    def _make_gateway(self) -> MiniQMTTraderGateway:
        return MiniQMTTraderGateway()

    def _make_mock_bridge(self) -> MagicMock:
        bridge = MagicMock()
        bridge.place_native_order.return_value = 12345
        bridge.heartbeat.return_value = True
        bridge.connected = True
        bridge.query_account.return_value = {
            "account_id": "test",
            "equity": 100000.0,
            "cash": 50000.0,
            "available_cash": 40000.0,
        }
        bridge.query_positions.return_value = [
            {
                "symbol": "600000",
                "quantity": 1000,
                "available_quantity": 800,
                "avg_price": 10.5,
            }
        ]
        return bridge

    def test_set_bridge(self) -> None:
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)
        assert gw._bridge is bridge

    def test_connect_with_bridge(self) -> None:
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)
        gw.connect()
        bridge.connect.assert_called_once()
        assert gw.connected

    def test_disconnect_with_bridge(self) -> None:
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)
        gw.disconnect()
        bridge.disconnect.assert_called_once()
        assert not gw.connected

    def test_place_order_routes_through_bridge(self) -> None:
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)

        req = UnifiedOrderRequest(
            client_order_id="test-1",
            symbol="600000",
            side="buy",
            quantity=100,
            price=10.0,
            order_type="limit",
            time_in_force="GTC",
        )
        broker_order_id = gw.place_order(req)

        bridge.place_native_order.assert_called_once_with(
            symbol="600000",
            side="buy",
            quantity=100.0,
            price=10.0,
            order_type="limit",
        )
        assert broker_order_id == "miniqmt-12345"

    def test_place_order_in_memory_without_bridge(self) -> None:
        gw = self._make_gateway()
        req = UnifiedOrderRequest(
            client_order_id="test-2",
            symbol="600000",
            side="buy",
            quantity=100,
            order_type="market",
            time_in_force="IOC",
        )
        broker_order_id = gw.place_order(req)
        assert broker_order_id.startswith("miniqmt-")
        assert "test-2" in broker_order_id

    def test_cancel_order_routes_through_bridge(self) -> None:
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)

        gw.cancel_order("miniqmt-12345")
        bridge.cancel_native_order.assert_called_once_with(12345)

    def test_cancel_order_in_memory_without_bridge(self) -> None:
        gw = self._make_gateway()
        req = UnifiedOrderRequest(
            client_order_id="cancel-test",
            symbol="600000",
            side="buy",
            quantity=100,
            order_type="limit",
            price=10.0,
            time_in_force="GTC",
        )
        broker_id = gw.place_order(req)
        gw.cancel_order(broker_id)
        order = gw.query_order(broker_id)
        assert order is not None
        assert order.status == UnifiedOrderStatus.CANCELLED

    def test_query_account_with_bridge(self) -> None:
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)

        account = gw.query_account()
        assert account is not None
        assert account.account_id == "test"
        assert account.equity == 100000.0
        bridge.query_account.assert_called_once()

    def test_query_positions_with_bridge(self) -> None:
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)

        positions = gw.query_positions()
        assert len(positions) == 1
        assert positions[0].symbol == "600000"
        assert positions[0].quantity == 1000

    def test_heartbeat_with_bridge(self) -> None:
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)

        assert gw.heartbeat() is True
        bridge.heartbeat.return_value = False
        assert gw.heartbeat() is False

    def test_heartbeat_without_bridge(self) -> None:
        gw = self._make_gateway()
        gw.connected = True
        assert gw.heartbeat() is True
        gw.connected = False
        assert gw.heartbeat() is False

    def test_ingest_order_event_with_bridge(self) -> None:
        """Bridge callbacks use ingest_order_event which still works with bridge."""
        gw = self._make_gateway()
        bridge = self._make_mock_bridge()
        gw.set_bridge(bridge)

        received: list[UnifiedOrderSnapshot] = []
        gw.on_order(lambda o: received.append(o))

        gw.ingest_order_event({
            "client_order_id": "cb-1",
            "broker_order_id": "miniqmt-12345",
            "symbol": "600000",
            "status": "submitted",
            "filled_quantity": 0.0,
            "avg_fill_price": 0.0,
            "reject_reason": "",
            "timestamp_ns": time.time_ns(),
        })

        assert len(received) == 1
        assert received[0].symbol == "600000"


# ---------------------------------------------------------------------------
# Native order ID parsing
# ---------------------------------------------------------------------------


class TestNativeOrderIdParsing:
    def test_valid_id(self) -> None:
        assert MiniQMTTraderGateway._parse_native_order_id("miniqmt-12345") == 12345

    def test_invalid_prefix(self) -> None:
        assert MiniQMTTraderGateway._parse_native_order_id("ctp-12345") is None

    def test_non_numeric_tail(self) -> None:
        assert MiniQMTTraderGateway._parse_native_order_id("miniqmt-abc") is None

    def test_empty_string(self) -> None:
        assert MiniQMTTraderGateway._parse_native_order_id("") is None
