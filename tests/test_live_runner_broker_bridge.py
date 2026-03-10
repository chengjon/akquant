import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, cast

import pytest
from akquant.live import LiveRunner
from akquant.strategy import Strategy


def test_live_runner_broker_bridge_dispatches_events() -> None:
    """Dispatch broker events to strategy callbacks."""

    class _DummyTraderGateway:
        def __init__(self) -> None:
            self._on_order: Callable[[Any], None] | None = None
            self._on_trade: Callable[[Any], None] | None = None
            self._on_execution_report: Callable[[Any], None] | None = None

        def on_order(self, callback: Callable[[Any], None]) -> None:
            self._on_order = callback

        def on_trade(self, callback: Callable[[Any], None]) -> None:
            self._on_trade = callback

        def on_execution_report(self, callback: Callable[[Any], None]) -> None:
            self._on_execution_report = callback

        def emit_order(self, payload: Any) -> None:
            if self._on_order is not None:
                self._on_order(payload)

        def emit_trade(self, payload: Any) -> None:
            if self._on_trade is not None:
                self._on_trade(payload)

        def emit_execution_report(self, payload: Any) -> None:
            if self._on_execution_report is not None:
                self._on_execution_report(payload)

    class _DummyStrategy:
        def __init__(self) -> None:
            self.orders: list[Any] = []
            self.trades: list[Any] = []
            self.reports: list[Any] = []
            self.errors: list[tuple[str, Any]] = []

        def on_order(self, order: Any) -> None:
            self.orders.append(order)

        def on_trade(self, trade: Any) -> None:
            self.trades.append(trade)

        def on_execution_report(self, report: Any) -> None:
            self.reports.append(report)

        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            self.errors.append((source, payload))

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "miniqmt"
    runner._init_broker_bridge_state()
    gateway = _DummyTraderGateway()
    strategy = _DummyStrategy()
    runner._bind_broker_callbacks(gateway, cast(Any, strategy))

    gateway.emit_order({"id": "o1"})
    gateway.emit_trade({"id": "t1"})
    gateway.emit_execution_report({"id": "r1"})
    time.sleep(0.2)
    runner._stop_broker_dispatcher()

    assert strategy.orders == [{"id": "o1"}]
    assert strategy.trades == [{"id": "t1"}]
    assert strategy.reports == [{"id": "r1"}]


def test_live_runner_broker_bridge_forwards_errors() -> None:
    """Forward callback exceptions to strategy on_error."""

    class _DummyTraderGateway:
        def __init__(self) -> None:
            self._on_trade: Callable[[Any], None] | None = None

        def on_order(self, callback: Callable[[Any], None]) -> None:
            return None

        def on_trade(self, callback: Callable[[Any], None]) -> None:
            self._on_trade = callback

        def on_execution_report(self, callback: Callable[[Any], None]) -> None:
            return None

        def emit_trade(self, payload: Any) -> None:
            if self._on_trade is not None:
                self._on_trade(payload)

    class _DummyErrorStrategy:
        def __init__(self) -> None:
            self.errors: list[tuple[str, Any]] = []

        def on_trade(self, trade: Any) -> None:
            raise RuntimeError("trade callback failed")

        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            self.errors.append((source, payload))

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "ptrade"
    runner._init_broker_bridge_state()
    gateway = _DummyTraderGateway()
    strategy = _DummyErrorStrategy()
    runner._bind_broker_callbacks(gateway, cast(Any, strategy))

    gateway.emit_trade({"id": "t2"})
    time.sleep(0.2)
    runner._stop_broker_dispatcher()

    assert strategy.errors
    assert strategy.errors[0][0] == "on_trade"


def test_live_runner_broker_bridge_deduplicates_events() -> None:
    """Deduplicate repeated broker events by semantic keys."""

    class _DummyStrategy:
        def __init__(self) -> None:
            self.orders: list[Any] = []

        def on_order(self, order: Any) -> None:
            self.orders.append(order)

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "miniqmt"
    runner._init_broker_bridge_state()
    strategy = _DummyStrategy()
    payload = SimpleNamespace(
        broker_order_id="b1",
        status="Submitted",
        filled_quantity=0.0,
        timestamp_ns=100,
    )

    runner._queue_broker_event("order", payload)
    runner._queue_broker_event("order", payload)
    runner._drain_broker_events(cast(Any, strategy))

    assert len(strategy.orders) == 1


def test_live_runner_broker_bridge_recovers_from_sync() -> None:
    """Recover order and trade snapshots from trader gateway sync methods."""

    class _DummyTraderGateway:
        def __init__(self) -> None:
            self._on_order: Callable[[Any], None] | None = None
            self._on_trade: Callable[[Any], None] | None = None
            self._on_execution_report: Callable[[Any], None] | None = None
            self.connected = False

        def on_order(self, callback: Callable[[Any], None]) -> None:
            self._on_order = callback

        def on_trade(self, callback: Callable[[Any], None]) -> None:
            self._on_trade = callback

        def on_execution_report(self, callback: Callable[[Any], None]) -> None:
            self._on_execution_report = callback

        def heartbeat(self) -> bool:
            return self.connected

        def connect(self) -> None:
            self.connected = True

        def sync_open_orders(self) -> list[Any]:
            return [
                SimpleNamespace(
                    broker_order_id="b-sync-1",
                    status="Submitted",
                    filled_quantity=0.0,
                    timestamp_ns=101,
                )
            ]

        def sync_today_trades(self) -> list[Any]:
            return [
                SimpleNamespace(
                    trade_id="t-sync-1",
                    broker_order_id="b-sync-1",
                    timestamp_ns=102,
                )
            ]

    class _DummyStrategy:
        def __init__(self) -> None:
            self.orders: list[Any] = []
            self.trades: list[Any] = []

        def on_order(self, order: Any) -> None:
            self.orders.append(order)

        def on_trade(self, trade: Any) -> None:
            self.trades.append(trade)

        def on_execution_report(self, report: Any) -> None:
            return None

        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            return None

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "ptrade"
    runner._init_broker_bridge_state()
    runner._broker_recovery_interval_sec = 0.05
    gateway = _DummyTraderGateway()
    strategy = _DummyStrategy()
    runner._bind_broker_callbacks(gateway, cast(Any, strategy))
    runner._run_broker_recovery_cycle()
    runner._drain_broker_events(cast(Any, strategy))
    runner._stop_broker_dispatcher()

    assert strategy.orders
    assert strategy.trades
    assert "b-sync-1" in runner._broker_order_states
    assert "t-sync-1" in runner._broker_trade_keys


def test_live_runner_syncs_client_broker_order_id_mapping() -> None:
    """Sync id mapping from order, report and trade events."""
    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "miniqmt"
    runner._init_broker_bridge_state()

    runner._update_broker_state(
        "order",
        {
            "client_order_id": "c-map-1",
            "broker_order_id": "b-map-1",
            "status": "Submitted",
        },
    )
    runner._update_broker_state(
        "execution_report",
        {
            "client_order_id": "c-map-1",
            "broker_order_id": "b-map-1",
            "status": "Submitted",
            "timestamp_ns": 1,
        },
    )
    runner._update_broker_state(
        "trade",
        {
            "trade_id": "t-map-1",
            "broker_order_id": "b-map-1",
        },
    )

    assert runner._resolve_broker_order_id("c-map-1") == "b-map-1"
    assert runner._resolve_client_order_id("b-map-1") == "c-map-1"


def test_live_runner_cleans_mapping_on_terminal_status() -> None:
    """Cleanup active mapping when order enters terminal status."""
    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "miniqmt"
    runner._init_broker_bridge_state()

    runner._update_broker_state(
        "order",
        {
            "client_order_id": "c-term-1",
            "broker_order_id": "b-term-1",
            "status": "Submitted",
        },
    )
    assert not runner.can_submit_client_order("c-term-1")

    runner._update_broker_state(
        "execution_report",
        {
            "client_order_id": "c-term-1",
            "broker_order_id": "b-term-1",
            "status": "Cancelled",
            "timestamp_ns": 2,
        },
    )

    assert runner.can_submit_client_order("c-term-1")
    assert "b-term-1" in runner._closed_broker_order_ids
    assert runner._resolve_broker_order_id("c-term-1") == ""


def test_live_runner_submitter_checks_idempotency_and_maps() -> None:
    """Install submitter and map ids after broker placement."""

    class _DummyTraderGateway:
        def __init__(self) -> None:
            self.last_client_order_id = ""

        def place_order(self, req: Any) -> str:
            self.last_client_order_id = req.client_order_id
            return f"b-{req.client_order_id}"

    class _DummyStrategy:
        def __init__(self) -> None:
            self.errors: list[tuple[str, Any]] = []

        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            self.errors.append((source, payload))

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "miniqmt"
    runner._init_broker_bridge_state()
    gateway = _DummyTraderGateway()
    strategy = _DummyStrategy()
    runner._install_broker_order_submitter(cast(Any, gateway), cast(Any, strategy))
    strategy_any = cast(Any, strategy)

    broker_order_id = strategy_any.submit_order(
        symbol="000001.SZ",
        side="Buy",
        quantity=10.0,
        client_order_id="coid-1",
    )

    assert broker_order_id == "b-coid-1"
    assert runner._resolve_broker_order_id("coid-1") == "b-coid-1"
    assert runner._resolve_client_order_id("b-coid-1") == "coid-1"


def test_live_runner_submitter_forwards_duplicate_error() -> None:
    """Raise and forward error when submitting duplicate active client order id."""

    class _DummyTraderGateway:
        def place_order(self, req: Any) -> str:
            return f"b-{req.client_order_id}"

    class _DummyStrategy:
        def __init__(self) -> None:
            self.errors: list[tuple[str, Any]] = []

        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            self.errors.append((source, payload))

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "ptrade"
    runner._init_broker_bridge_state()
    runner._sync_order_id_mapping("coid-dup", "b-coid-dup")
    runner._broker_order_states["b-coid-dup"] = {"status": "Submitted"}
    gateway = _DummyTraderGateway()
    strategy = _DummyStrategy()
    runner._install_broker_order_submitter(cast(Any, gateway), cast(Any, strategy))
    strategy_any = cast(Any, strategy)

    try:
        strategy_any.submit_order(
            symbol="000002.SZ",
            side="Sell",
            quantity=5.0,
            client_order_id="coid-dup",
        )
    except RuntimeError as exc:
        assert "duplicate active client_order_id" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for duplicate client_order_id")

    assert strategy.errors
    assert strategy.errors[0][0] == "submit_order"


def test_live_runner_submit_order_supports_buy_and_sell_side() -> None:
    """Unified submit_order should support both buy and sell side."""

    class _DummyTraderGateway:
        def __init__(self) -> None:
            self.last_side = ""
            self.last_client_order_id = ""

        def place_order(self, req: Any) -> str:
            self.last_side = req.side
            self.last_client_order_id = req.client_order_id
            return f"b-{req.side}-{req.client_order_id}"

    class _DummyStrategy:
        def __init__(self) -> None:
            self.errors: list[tuple[str, Any]] = []

        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            self.errors.append((source, payload))

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "miniqmt"
    runner._init_broker_bridge_state()
    gateway = _DummyTraderGateway()
    strategy = _DummyStrategy()
    runner._install_broker_order_submitter(cast(Any, gateway), cast(Any, strategy))
    strategy_any = cast(Any, strategy)

    buy_broker_order_id = strategy_any.submit_order(
        symbol="000001.SZ",
        side="Buy",
        quantity=10.0,
        client_order_id="coid-buy-1",
    )
    sell_broker_order_id = strategy_any.submit_order(
        symbol="000001.SZ",
        side="Sell",
        quantity=5.0,
        client_order_id="coid-sell-1",
    )

    assert buy_broker_order_id == "b-Buy-coid-buy-1"
    assert sell_broker_order_id == "b-Sell-coid-sell-1"
    assert runner._resolve_broker_order_id("coid-buy-1") == "b-Buy-coid-buy-1"
    assert runner._resolve_broker_order_id("coid-sell-1") == "b-Sell-coid-sell-1"


def test_live_runner_injects_execution_capabilities() -> None:
    """Expose broker-live capabilities after submitter injection."""

    class _DummyTraderGateway:
        def place_order(self, req: Any) -> str:
            return f"b-{req.client_order_id}"

    class _DummyStrategy:
        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            return None

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "ptrade"
    runner._init_broker_bridge_state()
    gateway = _DummyTraderGateway()
    strategy = _DummyStrategy()
    runner._install_broker_order_submitter(cast(Any, gateway), cast(Any, strategy))
    strategy_any = cast(Any, strategy)
    capabilities = strategy_any.get_execution_capabilities()

    assert capabilities["broker_live"] is True
    assert capabilities["client_order_id"] is True


def test_live_runner_does_not_inject_removed_broker_aliases() -> None:
    """Keep unified submit_order as the only injected order entry."""

    class _DummyTraderGateway:
        def place_order(self, req: Any) -> str:
            return f"b-{req.client_order_id}"

    class _DummyStrategy:
        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            return None

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "ptrade"
    runner._init_broker_bridge_state()
    gateway = _DummyTraderGateway()
    strategy = _DummyStrategy()
    runner._install_broker_order_submitter(cast(Any, gateway), cast(Any, strategy))
    strategy_any = cast(Any, strategy)

    assert hasattr(strategy_any, "submit_order")
    assert not hasattr(strategy_any, "submit_broker_order")
    assert not hasattr(strategy_any, "broker_buy")
    assert not hasattr(strategy_any, "broker_sell")


def test_live_runner_builds_strategy_instance_from_class() -> None:
    """Build strategy instance from class input."""

    class _DummyStrategy(Strategy):
        def on_bar(self, bar: Any) -> None:
            _ = bar

    runner = LiveRunner.__new__(LiveRunner)
    runner.strategy_cls = _DummyStrategy
    runner.initialize = None
    runner.on_start = None
    runner.on_stop = None
    runner.on_tick = None
    runner.on_order = None
    runner.on_trade = None
    runner.on_timer = None
    runner.context = {}
    strategy = runner._build_strategy_instance(runner.strategy_cls)
    assert isinstance(strategy, _DummyStrategy)


def test_live_runner_builds_strategy_instance_from_existing_instance() -> None:
    """Reuse provided strategy instance input."""

    class _DummyStrategy(Strategy):
        def on_bar(self, bar: Any) -> None:
            _ = bar

    instance = _DummyStrategy()
    runner = LiveRunner.__new__(LiveRunner)
    runner.strategy_cls = instance
    runner.initialize = None
    runner.on_start = None
    runner.on_stop = None
    runner.on_tick = None
    runner.on_order = None
    runner.on_trade = None
    runner.on_timer = None
    runner.context = {}
    strategy = runner._build_strategy_instance(runner.strategy_cls)
    assert strategy is instance


def test_live_runner_builds_functional_strategy_instance() -> None:
    """Build functional strategy wrapper from callable input."""
    events: list[str] = []

    def initialize(ctx: Any) -> None:
        events.append("initialize")
        ctx.seed = 7

    def on_start(ctx: Any) -> None:
        _ = ctx
        events.append("on_start")

    def on_stop(ctx: Any) -> None:
        _ = ctx
        events.append("on_stop")

    def on_bar(ctx: Any, bar: Any) -> None:
        _ = bar
        events.append(f"bar:{getattr(ctx, 'seed', 0)}")

    runner = LiveRunner.__new__(LiveRunner)
    runner.strategy_cls = on_bar
    runner.initialize = initialize
    runner.on_start = on_start
    runner.on_stop = on_stop
    runner.on_tick = None
    runner.on_order = None
    runner.on_trade = None
    runner.on_timer = None
    runner.context = {"flag": "ok"}
    strategy = runner._build_strategy_instance(runner.strategy_cls)

    assert isinstance(strategy, Strategy)
    assert getattr(strategy, "flag") == "ok"
    assert events == ["initialize"]
    strategy.on_start()
    strategy.on_bar(cast(Any, SimpleNamespace(symbol="TEST")))
    strategy.on_stop()
    assert events == ["initialize", "on_start", "bar:7", "on_stop"]


def test_live_runner_builds_strategy_instance_from_strategy_source(
    tmp_path: Path,
) -> None:
    """Build strategy instance from configured strategy_source."""
    strategy_file = tmp_path / "live_source_strategy.py"
    strategy_file.write_text(
        "\n".join(
            [
                "from akquant.strategy import Strategy",
                "",
                "class Strategy(Strategy):",
                "    def __init__(self):",
                "        self.calls = 0",
                "",
                "    def on_bar(self, bar):",
                "        self.calls += 1",
            ]
        ),
        encoding="utf-8",
    )

    runner = LiveRunner.__new__(LiveRunner)
    runner.strategy_cls = None
    runner.strategy_source = str(strategy_file)
    runner.strategy_loader = "python_plain"
    runner.strategy_loader_options = None
    runner.initialize = None
    runner.on_start = None
    runner.on_stop = None
    runner.on_tick = None
    runner.on_order = None
    runner.on_trade = None
    runner.on_timer = None
    runner.context = {}
    strategy = runner._build_strategy_instance(runner.strategy_cls)

    assert isinstance(strategy, Strategy)
    assert type(strategy).__name__ == "Strategy"


def test_live_runner_builds_strategy_from_encrypted_external_loader() -> None:
    """Build strategy instance using encrypted_external loader callback."""

    class _LoadedStrategy(Strategy):
        def on_bar(self, bar: Any) -> None:
            _ = bar

    def _decrypt_loader(source: Any, options: dict[str, Any]) -> type[Strategy]:
        _ = source
        _ = options
        return _LoadedStrategy

    runner = LiveRunner.__new__(LiveRunner)
    runner.strategy_cls = None
    runner.strategy_source = b"cipher"
    runner.strategy_loader = "encrypted_external"
    runner.strategy_loader_options = {"decrypt_and_load": _decrypt_loader}
    runner.initialize = None
    runner.on_start = None
    runner.on_stop = None
    runner.on_tick = None
    runner.on_order = None
    runner.on_trade = None
    runner.on_timer = None
    runner.context = {}
    strategy = runner._build_strategy_instance(runner.strategy_cls)

    assert isinstance(strategy, _LoadedStrategy)


def test_live_runner_rejects_missing_strategy_and_source() -> None:
    """Live runner should fail when both strategy and source are missing."""
    runner = LiveRunner.__new__(LiveRunner)
    runner.strategy_cls = None
    runner.strategy_source = None
    runner.strategy_loader = None
    runner.strategy_loader_options = None
    runner.initialize = None
    runner.on_start = None
    runner.on_stop = None
    runner.on_tick = None
    runner.on_order = None
    runner.on_trade = None
    runner.on_timer = None
    runner.context = {}
    with pytest.raises(ValueError, match="Strategy must be provided"):
        runner._build_strategy_instance(runner.strategy_cls)


def test_live_runner_builds_strategy_topology_with_slots() -> None:
    """Build primary and slot strategies with explicit strategy ids."""

    def on_bar(ctx: Any, bar: Any) -> None:
        _ = ctx
        _ = bar

    def slot_on_bar(ctx: Any, bar: Any) -> None:
        _ = ctx
        _ = bar

    runner = LiveRunner.__new__(LiveRunner)
    runner.strategy_cls = on_bar
    runner.strategy_id = "alpha"
    runner.strategies_by_slot = {"beta": slot_on_bar}
    runner.initialize = None
    runner.on_start = None
    runner.on_stop = None
    runner.on_tick = None
    runner.on_order = None
    runner.on_trade = None
    runner.on_timer = None
    runner.context = {}
    strategy, slots, strategy_id = runner._build_strategy_topology()

    assert isinstance(strategy, Strategy)
    assert strategy_id == "alpha"
    assert set(slots.keys()) == {"beta"}
    assert isinstance(slots["beta"], Strategy)


def test_live_runner_configures_engine_slots_for_primary_and_secondary() -> None:
    """Configure slot metadata and strategy binding on engine."""

    class _DummyEngine:
        def __init__(self) -> None:
            self.slot_ids: list[str] = []
            self.default_strategy_id = ""
            self.slot_strategies: dict[int, Any] = {}

        def set_strategy_slots(self, slot_ids: list[str]) -> None:
            self.slot_ids = slot_ids

        def set_default_strategy_id(self, strategy_id: str) -> None:
            self.default_strategy_id = strategy_id

        def set_strategy_for_slot(self, slot_index: int, strategy: Any) -> None:
            self.slot_strategies[slot_index] = strategy

    class _DummyStrategy(Strategy):
        def on_bar(self, bar: Any) -> None:
            _ = bar

    runner = LiveRunner.__new__(LiveRunner)
    runner.engine = cast(Any, _DummyEngine())
    runner.context = {"shared_flag": "ok"}
    primary = _DummyStrategy()
    secondary = _DummyStrategy()
    runner._configure_strategy_slots(primary, {"beta": secondary}, "alpha")
    engine = cast(_DummyEngine, runner.engine)

    assert engine.slot_ids == ["alpha", "beta"]
    assert engine.default_strategy_id == "alpha"
    assert engine.slot_strategies[0] is primary
    assert engine.slot_strategies[1] is secondary
    assert getattr(primary, "_owner_strategy_id") == "alpha"
    assert getattr(secondary, "_owner_strategy_id") == "beta"
    assert getattr(primary, "shared_flag") == "ok"
    assert getattr(secondary, "shared_flag") == "ok"


def test_live_runner_applies_strategy_risk_controls_for_slots() -> None:
    """Apply strategy-level risk controls using configured slot ids."""

    class _DummyEngine:
        def __init__(self) -> None:
            self.slot_ids: list[str] = []
            self.default_strategy_id = ""
            self.slot_strategies: dict[int, Any] = {}
            self.max_order_value_limits: dict[str, float] = {}
            self.max_order_size_limits: dict[str, float] = {}
            self.max_position_size_limits: dict[str, float] = {}
            self.max_daily_loss_limits: dict[str, float] = {}
            self.max_drawdown_limits: dict[str, float] = {}
            self.reduce_only_flags: dict[str, bool] = {}
            self.cooldown_bars: dict[str, int] = {}
            self.strategy_priorities: dict[str, int] = {}
            self.strategy_risk_budget_limits: dict[str, float] = {}
            self.portfolio_risk_budget_limit: float | None = None
            self.risk_budget_mode = ""
            self.risk_budget_reset_daily = False

        def set_strategy_slots(self, slot_ids: list[str]) -> None:
            self.slot_ids = slot_ids

        def set_default_strategy_id(self, strategy_id: str) -> None:
            self.default_strategy_id = strategy_id

        def set_strategy_for_slot(self, slot_index: int, strategy: Any) -> None:
            self.slot_strategies[slot_index] = strategy

        def set_strategy_max_order_value_limits(self, limits: dict[str, float]) -> None:
            self.max_order_value_limits = limits

        def set_strategy_max_order_size_limits(self, limits: dict[str, float]) -> None:
            self.max_order_size_limits = limits

        def set_strategy_max_position_size_limits(
            self, limits: dict[str, float]
        ) -> None:
            self.max_position_size_limits = limits

        def set_strategy_max_daily_loss_limits(self, limits: dict[str, float]) -> None:
            self.max_daily_loss_limits = limits

        def set_strategy_max_drawdown_limits(self, limits: dict[str, float]) -> None:
            self.max_drawdown_limits = limits

        def set_strategy_reduce_only_after_risk(self, flags: dict[str, bool]) -> None:
            self.reduce_only_flags = flags

        def set_strategy_risk_cooldown_bars(self, bars: dict[str, int]) -> None:
            self.cooldown_bars = bars

        def set_strategy_priorities(self, priorities: dict[str, int]) -> None:
            self.strategy_priorities = priorities

        def set_strategy_risk_budget_limits(self, limits: dict[str, float]) -> None:
            self.strategy_risk_budget_limits = limits

        def set_portfolio_risk_budget_limit(self, limit: float | None) -> None:
            self.portfolio_risk_budget_limit = limit

        def set_risk_budget_mode(self, mode: str) -> None:
            self.risk_budget_mode = mode

        def set_risk_budget_reset_daily(self, enabled: bool) -> None:
            self.risk_budget_reset_daily = enabled

    class _DummyStrategy(Strategy):
        def on_bar(self, bar: Any) -> None:
            _ = bar

    runner = LiveRunner.__new__(LiveRunner)
    runner.engine = cast(Any, _DummyEngine())
    runner.context = {}
    runner.strategy_max_order_value = {"alpha": 1000.0, "beta": 2000.0}
    runner.strategy_max_order_size = {"alpha": 10.0, "beta": 20.0}
    runner.strategy_max_position_size = {"alpha": 100.0, "beta": 200.0}
    runner.strategy_max_daily_loss = {"alpha": 0.02, "beta": 0.03}
    runner.strategy_max_drawdown = {"alpha": 0.1, "beta": 0.15}
    runner.strategy_reduce_only_after_risk = {"alpha": True, "beta": False}
    runner.strategy_risk_cooldown_bars = {"alpha": 3, "beta": 5}
    runner.strategy_priority = {"alpha": 1, "beta": 2}
    runner.strategy_risk_budget = {"alpha": 50000.0, "beta": 60000.0}
    runner.portfolio_risk_budget = 120000.0
    runner.risk_budget_mode = "order_notional"
    runner.risk_budget_reset_daily = True
    primary = _DummyStrategy()
    secondary = _DummyStrategy()
    runner._configure_strategy_slots(primary, {"beta": secondary}, "alpha")
    engine = cast(_DummyEngine, runner.engine)

    assert engine.max_order_value_limits == {"alpha": 1000.0, "beta": 2000.0}
    assert engine.max_order_size_limits == {"alpha": 10.0, "beta": 20.0}
    assert engine.max_position_size_limits == {"alpha": 100.0, "beta": 200.0}
    assert engine.max_daily_loss_limits == {"alpha": 0.02, "beta": 0.03}
    assert engine.max_drawdown_limits == {"alpha": 0.1, "beta": 0.15}
    assert engine.reduce_only_flags == {"alpha": True, "beta": False}
    assert engine.cooldown_bars == {"alpha": 3, "beta": 5}
    assert engine.strategy_priorities == {"alpha": 1, "beta": 2}
    assert engine.strategy_risk_budget_limits == {"alpha": 50000.0, "beta": 60000.0}
    assert engine.portfolio_risk_budget_limit == 120000.0
    assert engine.risk_budget_mode == "order_notional"
    assert engine.risk_budget_reset_daily is True


def test_live_runner_rejects_unknown_strategy_ids_in_risk_controls() -> None:
    """Reject strategy-level maps containing ids outside configured slots."""

    class _DummyEngine:
        def set_strategy_slots(self, slot_ids: list[str]) -> None:
            _ = slot_ids

        def set_default_strategy_id(self, strategy_id: str) -> None:
            _ = strategy_id

        def set_strategy_for_slot(self, slot_index: int, strategy: Any) -> None:
            _ = slot_index
            _ = strategy

    class _DummyStrategy(Strategy):
        def on_bar(self, bar: Any) -> None:
            _ = bar

    runner = LiveRunner.__new__(LiveRunner)
    runner.engine = cast(Any, _DummyEngine())
    runner.context = {}
    runner.strategy_max_order_value = {"ghost": 123.0}
    runner.strategy_max_order_size = {}
    runner.strategy_max_position_size = {}
    runner.strategy_max_daily_loss = {}
    runner.strategy_max_drawdown = {}
    runner.strategy_reduce_only_after_risk = {}
    runner.strategy_risk_cooldown_bars = {}
    runner.strategy_priority = {}
    runner.strategy_risk_budget = {}
    runner.portfolio_risk_budget = None
    runner.risk_budget_mode = "order_notional"
    runner.risk_budget_reset_daily = False
    primary = _DummyStrategy()
    secondary = _DummyStrategy()

    try:
        runner._configure_strategy_slots(primary, {"beta": secondary}, "alpha")
        assert False, "expected ValueError for unknown strategy id"
    except ValueError as exc:
        assert "unknown strategy ids: ghost" in str(exc)


def test_live_runner_submitter_binds_owner_strategy_id_mapping() -> None:
    """Bind strategy owner mapping when submit_order is called."""

    class _DummyTraderGateway:
        def place_order(self, req: Any) -> str:
            return f"b-{req.client_order_id}"

    class _DummyStrategy:
        def __init__(self) -> None:
            self._owner_strategy_id = "alpha"
            self.errors: list[tuple[str, Any]] = []

        def on_error(self, error: Exception, source: str, payload: Any = None) -> None:
            self.errors.append((source, payload))

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "miniqmt"
    runner._init_broker_bridge_state()
    gateway = _DummyTraderGateway()
    strategy = _DummyStrategy()
    runner._install_broker_order_submitter(cast(Any, gateway), cast(Any, strategy))
    strategy_any = cast(Any, strategy)
    broker_order_id = strategy_any.submit_order(
        symbol="000001.SZ",
        side="Buy",
        quantity=10.0,
        client_order_id="coid-owner-1",
    )

    assert broker_order_id == "b-coid-owner-1"
    assert runner._client_to_strategy_ids["coid-owner-1"] == "alpha"
    assert runner._broker_to_strategy_ids["b-coid-owner-1"] == "alpha"


def test_live_runner_emits_observable_broker_events_with_owner_strategy_id() -> None:
    """Emit broker event snapshots with resolved owner strategy id."""
    observed: list[dict[str, Any]] = []

    class _DummyStrategy:
        def __init__(self) -> None:
            self.orders: list[Any] = []

        def on_order(self, order: Any) -> None:
            self.orders.append(order)

    runner = LiveRunner.__new__(LiveRunner)
    runner.broker = "miniqmt"
    runner._init_broker_bridge_state()
    runner.on_broker_event = observed.append
    runner._client_to_strategy_ids["coid-obs-1"] = "beta"
    strategy = _DummyStrategy()
    payload = {
        "client_order_id": "coid-obs-1",
        "broker_order_id": "b-obs-1",
        "status": "Submitted",
    }
    runner._queue_broker_event("order", payload)
    runner._drain_broker_events(cast(Any, strategy))

    assert observed
    event = observed[0]
    assert event["event_type"] == "order"
    assert event["owner_strategy_id"] == "beta"
    assert event["payload"]["client_order_id"] == "coid-obs-1"
