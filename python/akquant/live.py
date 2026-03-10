# -*- coding: utf-8 -*-
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Type, Union, cast

from akquant import Bar, DataFeed, Engine, Instrument, Strategy
from akquant.gateway.factory import create_gateway_bundle
from akquant.gateway.models import UnifiedOrderRequest
from akquant.strategy_loader import resolve_strategy_input


class _StrategyCallbackFanout:
    def __init__(self, strategies: List[Strategy]):
        self._strategies = strategies

    def on_order(self, order: Any) -> None:
        for strategy in self._strategies:
            callback = getattr(strategy, "on_order", None)
            if callback is None:
                continue
            try:
                callback(order)
            except Exception as exc:
                on_error = getattr(strategy, "on_error", None)
                if on_error is not None:
                    try:
                        on_error(exc, "on_order", order)
                    except Exception:
                        pass

    def on_trade(self, trade: Any) -> None:
        for strategy in self._strategies:
            callback = getattr(strategy, "on_trade", None)
            if callback is None:
                continue
            try:
                callback(trade)
            except Exception as exc:
                on_error = getattr(strategy, "on_error", None)
                if on_error is not None:
                    try:
                        on_error(exc, "on_trade", trade)
                    except Exception:
                        pass

    def on_execution_report(self, report: Any) -> None:
        for strategy in self._strategies:
            callback = getattr(strategy, "on_execution_report", None)
            if callback is None:
                continue
            try:
                callback(report)
            except Exception as exc:
                on_error = getattr(strategy, "on_error", None)
                if on_error is not None:
                    try:
                        on_error(exc, "on_execution_report", report)
                    except Exception:
                        pass


class LiveRunner:
    """
    Live/Paper Trading Runner.

    Encapsulates the boilerplate code for setting up the engine, data feed,
    instruments, and gateways for live or paper trading.
    """

    def __init__(
        self,
        strategy_cls: Optional[
            Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]
        ],
        instruments: List[Instrument],
        strategy_source: Optional[Union[str, bytes]] = None,
        strategy_loader: Optional[str] = None,
        strategy_loader_options: Optional[Dict[str, Any]] = None,
        strategy_id: Optional[str] = None,
        strategies_by_slot: Optional[
            Dict[str, Union[Type[Strategy], Strategy, Callable[[Any, Bar], None]]]
        ] = None,
        md_front: str = "",
        td_front: Optional[str] = None,
        broker_id: str = "",
        user_id: str = "",
        password: str = "",
        app_id: str = "",
        auth_code: str = "",
        use_aggregator: bool = True,
        broker: str = "ctp",
        trading_mode: str = "paper",
        gateway_options: Optional[Dict[str, Any]] = None,
        initialize: Optional[Callable[[Any], None]] = None,
        on_start: Optional[Callable[[Any], None]] = None,
        on_stop: Optional[Callable[[Any], None]] = None,
        on_tick: Optional[Callable[[Any, Any], None]] = None,
        on_order: Optional[Callable[[Any, Any], None]] = None,
        on_trade: Optional[Callable[[Any, Any], None]] = None,
        on_timer: Optional[Callable[[Any, str], None]] = None,
        context: Optional[Dict[str, Any]] = None,
        strategy_max_order_value: Optional[Dict[str, float]] = None,
        strategy_max_order_size: Optional[Dict[str, float]] = None,
        strategy_max_position_size: Optional[Dict[str, float]] = None,
        strategy_max_daily_loss: Optional[Dict[str, float]] = None,
        strategy_max_drawdown: Optional[Dict[str, float]] = None,
        strategy_reduce_only_after_risk: Optional[Dict[str, bool]] = None,
        strategy_risk_cooldown_bars: Optional[Dict[str, int]] = None,
        strategy_priority: Optional[Dict[str, int]] = None,
        strategy_risk_budget: Optional[Dict[str, float]] = None,
        portfolio_risk_budget: Optional[float] = None,
        risk_budget_mode: str = "order_notional",
        risk_budget_reset_daily: bool = False,
        on_broker_event: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Initialize the LiveRunner.

        :param strategy_cls: Strategy class/instance, or function-style on_bar callback.
        :param strategy_id: Primary strategy id for slot ownership (default "_default").
        :param strategies_by_slot: Optional slot->strategy mapping
                                   for multi-slot runtime.
        :param instruments: List of instruments to trade.
        :param md_front: CTP Market Data Front URL.
        :param td_front: CTP Trade Front URL (optional).
        :param broker_id: CTP Broker ID (optional).
        :param user_id: CTP User ID (optional).
        :param password: CTP Password (optional).
        :param app_id: CTP App ID (optional).
        :param auth_code: CTP Auth Code (optional).
        :param use_aggregator: Whether to use BarAggregator (default True).
        :param initialize: Optional function-style initialize callback.
        :param on_start: Optional function-style on_start callback.
        :param on_stop: Optional function-style on_stop callback.
        :param on_tick: Optional function-style on_tick callback.
        :param on_order: Optional function-style on_order callback.
        :param on_trade: Optional function-style on_trade callback.
        :param on_timer: Optional function-style on_timer callback.
        :param context: Optional context dict injected into function-style strategy.
        :param on_broker_event: Optional broker event observer callback.
        """
        self.strategy_cls = strategy_cls
        self.strategy_source = strategy_source
        self.strategy_loader = strategy_loader
        self.strategy_loader_options = strategy_loader_options
        self.strategy_id = (strategy_id or "_default").strip() or "_default"
        self.strategies_by_slot = strategies_by_slot or {}
        self.instruments = instruments
        self.md_front = md_front
        self.td_front = td_front
        self.broker_id = broker_id
        self.user_id = user_id
        self.password = password
        self.app_id = app_id
        self.auth_code = auth_code
        self.use_aggregator = use_aggregator
        self.broker = broker
        self.trading_mode = trading_mode
        self.gateway_options = gateway_options or {}
        self.initialize = initialize
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_tick = on_tick
        self.on_order = on_order
        self.on_trade = on_trade
        self.on_timer = on_timer
        self.context = context or {}
        self.strategy_max_order_value = self._normalize_strategy_float_map(
            strategy_max_order_value
        )
        self.strategy_max_order_size = self._normalize_strategy_float_map(
            strategy_max_order_size
        )
        self.strategy_max_position_size = self._normalize_strategy_float_map(
            strategy_max_position_size
        )
        self.strategy_max_daily_loss = self._normalize_strategy_float_map(
            strategy_max_daily_loss
        )
        self.strategy_max_drawdown = self._normalize_strategy_float_map(
            strategy_max_drawdown
        )
        self.strategy_reduce_only_after_risk = self._normalize_strategy_bool_map(
            strategy_reduce_only_after_risk
        )
        self.strategy_risk_cooldown_bars = self._normalize_strategy_int_map(
            strategy_risk_cooldown_bars
        )
        self.strategy_priority = self._normalize_strategy_int_map(strategy_priority)
        self.strategy_risk_budget = self._normalize_strategy_float_map(
            strategy_risk_budget
        )
        self.portfolio_risk_budget = (
            float(portfolio_risk_budget) if portfolio_risk_budget is not None else None
        )
        self.risk_budget_mode = risk_budget_mode
        self.risk_budget_reset_daily = bool(risk_budget_reset_daily)
        self.on_broker_event = on_broker_event
        self._init_broker_bridge_state()

        self.feed = DataFeed.create_live()  # type: ignore
        self.engine = Engine()

    def run(
        self,
        cash: float = 1_000_000.0,
        show_progress: bool = False,
        duration: Optional[str] = None,
    ) -> None:
        """
        Run the live/paper trading session.

        :param cash: Initial cash (default 1,000,000).
        :param show_progress: Whether to show progress bar (default False).
        :param duration: Optional run duration string (e.g., "1m", "1h", "60s").
                         If set, strategy will stop after this duration.
        """
        print("[LiveRunner] Configuring Engine...")
        self.engine.add_data(self.feed)
        self.engine.set_cash(cash)

        for instrument in self.instruments:
            self.engine.add_instrument(instrument)

        if self.trading_mode == "broker_live":
            self.engine.use_realtime_execution()
        else:
            self.engine.use_simulated_execution()

        self.engine.use_china_futures_market()
        self.engine.set_force_session_continuous(True)

        symbols = [inst.symbol for inst in self.instruments]
        gateway_kwargs = self._build_gateway_kwargs()
        bundle = create_gateway_bundle(
            broker=self.broker,
            feed=self.feed,
            symbols=symbols,
            use_aggregator=self.use_aggregator,
            **gateway_kwargs,
        )

        print(f"[LiveRunner] Starting {self.broker} market gateway...")
        self._start_gateway_thread(bundle.market_gateway.start, f"{self.broker}-market")

        if self.trading_mode == "broker_live":
            if bundle.trader_gateway is None:
                raise ValueError(
                    "trading_mode='broker_live' requires a trader gateway configuration"
                )
            print(f"[LiveRunner] Starting {self.broker} trader gateway...")
            self._start_gateway_thread(
                bundle.trader_gateway.start, f"{self.broker}-trader"
            )

        time.sleep(2.0)

        # Create Strategy Instances
        strategy_instance, slot_strategy_instances, effective_strategy_id = (
            self._build_strategy_topology()
        )
        self._configure_strategy_slots(
            strategy_instance, slot_strategy_instances, effective_strategy_id
        )
        if bundle.trader_gateway is not None:
            strategy_targets = [strategy_instance, *slot_strategy_instances.values()]
            callback_target: Any = (
                _StrategyCallbackFanout(strategy_targets)
                if len(strategy_targets) > 1
                else strategy_instance
            )
            self._bind_broker_callbacks(bundle.trader_gateway, callback_target)
            for target in strategy_targets:
                self._install_broker_order_submitter(bundle.trader_gateway, target)

        # Apply duration limit if specified
        if duration:
            print(f"[LiveRunner] Auto-stop enabled: {duration}")
            self._apply_time_limit(strategy_instance, duration)

        print("[LiveRunner] Running Strategy (Press Ctrl+C to stop)...")
        try:
            self.engine.run(strategy_instance, show_progress=show_progress)
        except KeyboardInterrupt:
            print("\n[LiveRunner] Stopping by User (or Duration Limit)...")
        except Exception as e:
            print(f"\n[LiveRunner] Stopping due to Error: {e}")
            import traceback

            traceback.print_exc()
        finally:
            self._stop_broker_dispatcher()
            self._print_summary()

    def _build_strategy_instance(self, strategy_input: Any) -> Strategy:
        resolved_strategy_input = resolve_strategy_input(
            strategy=cast(
                Optional[Union[type[Strategy], Strategy, Callable[[Any, Bar], None]]],
                strategy_input,
            ),
            strategy_source=getattr(self, "strategy_source", None),
            strategy_loader=getattr(self, "strategy_loader", None),
            strategy_loader_options=getattr(self, "strategy_loader_options", None),
        )
        if isinstance(resolved_strategy_input, type) and issubclass(
            resolved_strategy_input, Strategy
        ):
            return cast(Strategy, resolved_strategy_input())
        if isinstance(resolved_strategy_input, Strategy):
            return resolved_strategy_input
        if callable(resolved_strategy_input):
            from akquant.backtest import FunctionalStrategy

            return FunctionalStrategy(
                initialize=self.initialize,
                on_bar=cast(Callable[[Any, Bar], None], resolved_strategy_input),
                on_start=self.on_start,
                on_stop=self.on_stop,
                on_tick=self.on_tick,
                on_order=self.on_order,
                on_trade=self.on_trade,
                on_timer=self.on_timer,
                context=self.context,
            )
        raise TypeError("strategy must be Strategy type/instance or callable")

    def _build_strategy_topology(self) -> tuple[Strategy, Dict[str, Strategy], str]:
        strategy_instance = self._build_strategy_instance(self.strategy_cls)
        slot_strategy_instances: Dict[str, Strategy] = {}
        for slot_key, slot_input in self.strategies_by_slot.items():
            slot_key_str = str(slot_key).strip()
            if not slot_key_str:
                raise ValueError("strategy slot id cannot be empty")
            slot_strategy_instances[slot_key_str] = self._build_strategy_instance(
                slot_input
            )
        return strategy_instance, slot_strategy_instances, self.strategy_id

    def _configure_strategy_slots(
        self,
        strategy_instance: Strategy,
        slot_strategy_instances: Dict[str, Strategy],
        effective_strategy_id: str,
    ) -> None:
        configured_slot_ids = [effective_strategy_id]
        for slot_id in slot_strategy_instances.keys():
            if slot_id not in configured_slot_ids:
                configured_slot_ids.append(slot_id)

        setattr(strategy_instance, "_owner_strategy_id", effective_strategy_id)
        for slot_id, slot_strategy in slot_strategy_instances.items():
            setattr(slot_strategy, "_owner_strategy_id", slot_id)

        strategy_targets = [strategy_instance, *slot_strategy_instances.values()]
        if self.context:
            for target in strategy_targets:
                if hasattr(target, "_context"):
                    continue
                for key, value in self.context.items():
                    setattr(target, key, value)

        if hasattr(self.engine, "set_strategy_slots"):
            cast(Any, self.engine).set_strategy_slots(configured_slot_ids)
        if hasattr(self.engine, "set_default_strategy_id"):
            cast(Any, self.engine).set_default_strategy_id(effective_strategy_id)
        if hasattr(self.engine, "set_strategy_for_slot"):
            for slot_index, slot_id in enumerate(configured_slot_ids):
                assigned = (
                    strategy_instance
                    if slot_id == effective_strategy_id
                    else slot_strategy_instances[slot_id]
                )
                cast(Any, self.engine).set_strategy_for_slot(slot_index, assigned)
        self._apply_strategy_risk_controls(configured_slot_ids)

    def _normalize_strategy_float_map(
        self, values: Optional[Dict[str, float]]
    ) -> Dict[str, float]:
        if values is None:
            return {}
        if not isinstance(values, dict):
            raise TypeError("strategy map must be a dict when provided")
        normalized: Dict[str, float] = {}
        for key, value in values.items():
            key_str = str(key).strip()
            if not key_str:
                raise ValueError("strategy id cannot be empty")
            normalized[key_str] = float(value)
        return normalized

    def _normalize_strategy_int_map(
        self, values: Optional[Dict[str, int]]
    ) -> Dict[str, int]:
        if values is None:
            return {}
        if not isinstance(values, dict):
            raise TypeError("strategy map must be a dict when provided")
        normalized: Dict[str, int] = {}
        for key, value in values.items():
            key_str = str(key).strip()
            if not key_str:
                raise ValueError("strategy id cannot be empty")
            normalized[key_str] = int(value)
        return normalized

    def _normalize_strategy_bool_map(
        self, values: Optional[Dict[str, bool]]
    ) -> Dict[str, bool]:
        if values is None:
            return {}
        if not isinstance(values, dict):
            raise TypeError("strategy map must be a dict when provided")
        normalized: Dict[str, bool] = {}
        for key, value in values.items():
            key_str = str(key).strip()
            if not key_str:
                raise ValueError("strategy id cannot be empty")
            normalized[key_str] = bool(value)
        return normalized

    def _validate_strategy_map_keys(
        self, values: Dict[str, Any], configured_slot_ids: List[str], field_name: str
    ) -> None:
        if not values:
            return
        unknown = sorted(set(values.keys()).difference(set(configured_slot_ids)))
        if unknown:
            unknown_text = ", ".join(unknown)
            raise ValueError(
                f"{field_name} contains unknown strategy ids: {unknown_text}"
            )

    def _apply_strategy_risk_controls(self, configured_slot_ids: List[str]) -> None:
        strategy_max_order_value = cast(
            Dict[str, float], getattr(self, "strategy_max_order_value", {})
        )
        strategy_max_order_size = cast(
            Dict[str, float], getattr(self, "strategy_max_order_size", {})
        )
        strategy_max_position_size = cast(
            Dict[str, float], getattr(self, "strategy_max_position_size", {})
        )
        strategy_max_daily_loss = cast(
            Dict[str, float], getattr(self, "strategy_max_daily_loss", {})
        )
        strategy_max_drawdown = cast(
            Dict[str, float], getattr(self, "strategy_max_drawdown", {})
        )
        strategy_reduce_only_after_risk = cast(
            Dict[str, bool], getattr(self, "strategy_reduce_only_after_risk", {})
        )
        strategy_risk_cooldown_bars = cast(
            Dict[str, int], getattr(self, "strategy_risk_cooldown_bars", {})
        )
        strategy_priority = cast(Dict[str, int], getattr(self, "strategy_priority", {}))
        strategy_risk_budget = cast(
            Dict[str, float], getattr(self, "strategy_risk_budget", {})
        )
        portfolio_risk_budget = cast(
            Optional[float], getattr(self, "portfolio_risk_budget", None)
        )
        risk_budget_mode = str(getattr(self, "risk_budget_mode", "order_notional"))
        risk_budget_reset_daily = bool(getattr(self, "risk_budget_reset_daily", False))

        self._validate_strategy_map_keys(
            strategy_max_order_value,
            configured_slot_ids,
            "strategy_max_order_value",
        )
        self._validate_strategy_map_keys(
            strategy_max_order_size,
            configured_slot_ids,
            "strategy_max_order_size",
        )
        self._validate_strategy_map_keys(
            strategy_max_position_size,
            configured_slot_ids,
            "strategy_max_position_size",
        )
        self._validate_strategy_map_keys(
            strategy_max_daily_loss,
            configured_slot_ids,
            "strategy_max_daily_loss",
        )
        self._validate_strategy_map_keys(
            strategy_max_drawdown,
            configured_slot_ids,
            "strategy_max_drawdown",
        )
        self._validate_strategy_map_keys(
            strategy_reduce_only_after_risk,
            configured_slot_ids,
            "strategy_reduce_only_after_risk",
        )
        self._validate_strategy_map_keys(
            strategy_risk_cooldown_bars,
            configured_slot_ids,
            "strategy_risk_cooldown_bars",
        )
        self._validate_strategy_map_keys(
            strategy_priority,
            configured_slot_ids,
            "strategy_priority",
        )
        self._validate_strategy_map_keys(
            strategy_risk_budget,
            configured_slot_ids,
            "strategy_risk_budget",
        )

        if strategy_max_order_value and hasattr(
            self.engine, "set_strategy_max_order_value_limits"
        ):
            cast(Any, self.engine).set_strategy_max_order_value_limits(
                strategy_max_order_value
            )
        if strategy_max_order_size and hasattr(
            self.engine, "set_strategy_max_order_size_limits"
        ):
            cast(Any, self.engine).set_strategy_max_order_size_limits(
                strategy_max_order_size
            )
        if strategy_max_position_size and hasattr(
            self.engine, "set_strategy_max_position_size_limits"
        ):
            cast(Any, self.engine).set_strategy_max_position_size_limits(
                strategy_max_position_size
            )
        if strategy_max_daily_loss and hasattr(
            self.engine, "set_strategy_max_daily_loss_limits"
        ):
            cast(Any, self.engine).set_strategy_max_daily_loss_limits(
                strategy_max_daily_loss
            )
        if strategy_max_drawdown and hasattr(
            self.engine, "set_strategy_max_drawdown_limits"
        ):
            cast(Any, self.engine).set_strategy_max_drawdown_limits(
                strategy_max_drawdown
            )
        if strategy_reduce_only_after_risk and hasattr(
            self.engine, "set_strategy_reduce_only_after_risk"
        ):
            cast(Any, self.engine).set_strategy_reduce_only_after_risk(
                strategy_reduce_only_after_risk
            )
        if strategy_risk_cooldown_bars and hasattr(
            self.engine, "set_strategy_risk_cooldown_bars"
        ):
            cast(Any, self.engine).set_strategy_risk_cooldown_bars(
                strategy_risk_cooldown_bars
            )
        if strategy_priority and hasattr(self.engine, "set_strategy_priorities"):
            cast(Any, self.engine).set_strategy_priorities(strategy_priority)
        if strategy_risk_budget and hasattr(
            self.engine, "set_strategy_risk_budget_limits"
        ):
            cast(Any, self.engine).set_strategy_risk_budget_limits(strategy_risk_budget)
        if hasattr(self.engine, "set_portfolio_risk_budget_limit"):
            cast(Any, self.engine).set_portfolio_risk_budget_limit(
                portfolio_risk_budget
            )
        if risk_budget_mode not in {"order_notional", "trade_notional"}:
            raise ValueError(
                "risk_budget_mode must be 'order_notional' or 'trade_notional'"
            )
        if hasattr(self.engine, "set_risk_budget_mode"):
            cast(Any, self.engine).set_risk_budget_mode(risk_budget_mode)
        if hasattr(self.engine, "set_risk_budget_reset_daily"):
            cast(Any, self.engine).set_risk_budget_reset_daily(risk_budget_reset_daily)

    def _build_gateway_kwargs(self) -> Dict[str, Any]:
        kwargs = dict(self.gateway_options)
        if self.md_front:
            kwargs.setdefault("md_front", self.md_front)
        if self.td_front:
            kwargs.setdefault("td_front", self.td_front)
        if self.broker_id:
            kwargs.setdefault("broker_id", self.broker_id)
        if self.user_id:
            kwargs.setdefault("user_id", self.user_id)
        if self.password:
            kwargs.setdefault("password", self.password)
        if self.app_id:
            kwargs.setdefault("app_id", self.app_id)
        if self.auth_code:
            kwargs.setdefault("auth_code", self.auth_code)
        return kwargs

    def _start_gateway_thread(self, target: Any, name: str) -> None:
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()

    def _init_broker_bridge_state(self) -> None:
        if not hasattr(self, "on_broker_event"):
            self.on_broker_event = None
        self._broker_event_lock = threading.Lock()
        self._broker_events: list[tuple[str, Any]] = []
        self._broker_event_keys: set[str] = set()
        self._broker_order_states: dict[str, Any] = {}
        self._client_to_broker_order_ids: dict[str, str] = {}
        self._broker_to_client_order_ids: dict[str, str] = {}
        self._client_to_strategy_ids: dict[str, str] = {}
        self._broker_to_strategy_ids: dict[str, str] = {}
        self._closed_broker_order_ids: set[str] = set()
        self._broker_trade_keys: set[str] = set()
        self._broker_report_keys: set[str] = set()
        self._broker_dispatch_stop: threading.Event | None = None
        self._broker_dispatch_thread: threading.Thread | None = None
        self._broker_recovery_stop: threading.Event | None = None
        self._broker_recovery_thread: threading.Thread | None = None
        self._broker_recovery_interval_sec = 1.0
        self._broker_trader_gateway: Any = None
        self._broker_submit_seq = 0
        self._broker_submit_lock = threading.Lock()

    def _bind_broker_callbacks(self, trader_gateway: Any, strategy: Strategy) -> None:
        self._broker_trader_gateway = trader_gateway
        if hasattr(trader_gateway, "on_order"):
            trader_gateway.on_order(
                lambda order: self._queue_broker_event("order", order)
            )
        if hasattr(trader_gateway, "on_trade"):
            trader_gateway.on_trade(
                lambda trade: self._queue_broker_event("trade", trade)
            )
        if hasattr(trader_gateway, "on_execution_report"):
            trader_gateway.on_execution_report(
                lambda report: self._queue_broker_event("execution_report", report)
            )
        self._start_broker_dispatcher(strategy)

    def _install_broker_order_submitter(
        self, trader_gateway: Any, strategy: Strategy
    ) -> None:
        def _submit_order(
            symbol: str,
            side: str,
            quantity: float,
            price: float | None = None,
            client_order_id: str | None = None,
            order_type: str = "Market",
            time_in_force: str = "GTC",
            trigger_price: float | None = None,
            tag: str | None = None,
            extra: dict[str, Any] | None = None,
        ) -> str:
            _ = trigger_price
            _ = tag
            if extra:
                raise RuntimeError("extra broker fields are not supported")
            request_client_order_id = client_order_id or self._next_client_order_id()
            owner_strategy_id = str(getattr(strategy, "_owner_strategy_id", "_default"))
            if not self.can_submit_client_order(request_client_order_id):
                exc = RuntimeError(
                    f"duplicate active client_order_id: {request_client_order_id}"
                )
                self._notify_strategy_error(
                    strategy,
                    exc,
                    "submit_order",
                    {
                        "client_order_id": request_client_order_id,
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                    },
                )
                raise exc
            request = UnifiedOrderRequest(
                client_order_id=request_client_order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                time_in_force=time_in_force,
            )
            broker_order_id = str(trader_gateway.place_order(request))
            self._sync_order_id_mapping(request_client_order_id, broker_order_id)
            self._bind_order_owner(
                request_client_order_id, broker_order_id, owner_strategy_id
            )
            return broker_order_id

        setattr(strategy, "submit_order", _submit_order)
        setattr(strategy, "can_submit_client_order", self.can_submit_client_order)
        setattr(strategy, "get_execution_capabilities", self.get_execution_capabilities)

    def _start_broker_dispatcher(self, strategy: Strategy) -> None:
        self._stop_broker_dispatcher()
        self._broker_dispatch_stop = threading.Event()
        self._broker_dispatch_thread = threading.Thread(
            target=self._broker_dispatch_loop,
            args=(strategy,),
            name=f"{self.broker}-broker-dispatch",
            daemon=True,
        )
        self._broker_dispatch_thread.start()
        self._start_broker_recovery(strategy)

    def _stop_broker_dispatcher(self) -> None:
        self._stop_broker_recovery()
        if self._broker_dispatch_stop is not None:
            self._broker_dispatch_stop.set()
        if self._broker_dispatch_thread is not None:
            self._broker_dispatch_thread.join(timeout=1.0)
        self._broker_dispatch_stop = None
        self._broker_dispatch_thread = None

    def _start_broker_recovery(self, strategy: Strategy) -> None:
        self._stop_broker_recovery()
        self._broker_recovery_stop = threading.Event()
        self._broker_recovery_thread = threading.Thread(
            target=self._broker_recovery_loop,
            args=(strategy,),
            name=f"{self.broker}-broker-recovery",
            daemon=True,
        )
        self._broker_recovery_thread.start()

    def _stop_broker_recovery(self) -> None:
        if self._broker_recovery_stop is not None:
            self._broker_recovery_stop.set()
        if self._broker_recovery_thread is not None:
            self._broker_recovery_thread.join(timeout=1.0)
        self._broker_recovery_stop = None
        self._broker_recovery_thread = None

    def _queue_broker_event(self, event_name: str, payload: Any) -> None:
        event_key = self._make_event_key(event_name, payload)
        with self._broker_event_lock:
            if event_key in self._broker_event_keys:
                return
            self._broker_event_keys.add(event_key)
            self._broker_events.append((event_name, payload))

    def _broker_dispatch_loop(self, strategy: Strategy) -> None:
        while (
            self._broker_dispatch_stop is not None
            and not self._broker_dispatch_stop.is_set()
        ):
            self._drain_broker_events(strategy)
            time.sleep(0.05)
        self._drain_broker_events(strategy)

    def _drain_broker_events(self, strategy: Strategy) -> None:
        with self._broker_event_lock:
            events = list(self._broker_events)
            self._broker_events.clear()
            self._broker_event_keys.clear()
        for event_name, payload in events:
            self._update_broker_state(event_name, payload)
            if self.on_broker_event is not None:
                try:
                    self.on_broker_event(
                        {
                            "event_type": event_name,
                            "owner_strategy_id": self._resolve_owner_strategy_id(
                                payload
                            ),
                            "payload": self._payload_to_dict(payload),
                        }
                    )
                except Exception:
                    pass
            if event_name == "order":
                self._safe_strategy_callback(strategy, "on_order", payload)
            elif event_name == "trade":
                self._safe_strategy_callback(strategy, "on_trade", payload)
            elif event_name == "execution_report":
                self._safe_strategy_callback(strategy, "on_execution_report", payload)

    def _broker_recovery_loop(self, strategy: Strategy) -> None:
        while (
            self._broker_recovery_stop is not None
            and not self._broker_recovery_stop.is_set()
        ):
            self._run_broker_recovery_cycle()
            self._drain_broker_events(strategy)
            time.sleep(self._broker_recovery_interval_sec)

    def _run_broker_recovery_cycle(self) -> None:
        gateway = self._broker_trader_gateway
        if gateway is None:
            return
        heartbeat = getattr(gateway, "heartbeat", None)
        if callable(heartbeat):
            try:
                alive = heartbeat()
            except Exception:
                alive = False
            if not alive:
                connect = getattr(gateway, "connect", None)
                if callable(connect):
                    try:
                        connect()
                    except Exception:
                        return
        sync_open_orders = getattr(gateway, "sync_open_orders", None)
        if callable(sync_open_orders):
            try:
                for order in sync_open_orders():
                    self._queue_broker_event("order", order)
            except Exception:
                pass
        sync_today_trades = getattr(gateway, "sync_today_trades", None)
        if callable(sync_today_trades):
            try:
                for trade in sync_today_trades():
                    self._queue_broker_event("trade", trade)
            except Exception:
                pass

    def _update_broker_state(self, event_name: str, payload: Any) -> None:
        if event_name == "order":
            broker_order_id = str(self._payload_field(payload, "broker_order_id"))
            client_order_id = str(self._payload_field(payload, "client_order_id"))
            self._sync_order_id_mapping(client_order_id, broker_order_id)
            if broker_order_id:
                self._broker_order_states[broker_order_id] = payload
                status = self._payload_field(payload, "status")
                if self._is_terminal_status(status):
                    self._close_order_mapping(client_order_id, broker_order_id)
        elif event_name == "trade":
            trade_key = str(self._payload_field(payload, "trade_id"))
            broker_order_id = str(self._payload_field(payload, "broker_order_id"))
            client_order_id = str(self._payload_field(payload, "client_order_id"))
            if not client_order_id and broker_order_id:
                client_order_id = self._resolve_client_order_id(broker_order_id)
            self._sync_order_id_mapping(client_order_id, broker_order_id)
            if trade_key:
                self._broker_trade_keys.add(trade_key)
        elif event_name == "execution_report":
            broker_order_id = str(self._payload_field(payload, "broker_order_id"))
            client_order_id = str(self._payload_field(payload, "client_order_id"))
            self._sync_order_id_mapping(client_order_id, broker_order_id)
            status = self._payload_field(payload, "status")
            if self._is_terminal_status(status):
                self._close_order_mapping(client_order_id, broker_order_id)
            report_key = (
                f"{self._payload_field(payload, 'broker_order_id')}-"
                f"{self._payload_field(payload, 'status')}-"
                f"{self._payload_field(payload, 'timestamp_ns')}"
            )
            if report_key:
                self._broker_report_keys.add(report_key)

    def _make_event_key(self, event_name: str, payload: Any) -> str:
        if event_name == "trade":
            trade_id = str(self._payload_field(payload, "trade_id"))
            if trade_id:
                return f"trade:{trade_id}"
        if event_name == "order":
            broker_order_id = str(self._payload_field(payload, "broker_order_id"))
            status = str(self._payload_field(payload, "status"))
            filled_quantity = str(self._payload_field(payload, "filled_quantity"))
            timestamp_ns = str(self._payload_field(payload, "timestamp_ns"))
            return f"order:{broker_order_id}:{status}:{filled_quantity}:{timestamp_ns}"
        if event_name == "execution_report":
            broker_order_id = str(self._payload_field(payload, "broker_order_id"))
            status = str(self._payload_field(payload, "status"))
            timestamp_ns = str(self._payload_field(payload, "timestamp_ns"))
            return f"execution_report:{broker_order_id}:{status}:{timestamp_ns}"
        return f"{event_name}:{id(payload)}"

    def _payload_field(self, payload: Any, field: str) -> Any:
        if isinstance(payload, dict):
            return payload.get(field, "")
        return getattr(payload, field, "")

    def _next_client_order_id(self) -> str:
        with self._broker_submit_lock:
            self._broker_submit_seq += 1
            return f"{self.broker}-coid-{self._broker_submit_seq}"

    def _sync_order_id_mapping(
        self,
        client_order_id: str,
        broker_order_id: str,
    ) -> None:
        if client_order_id and broker_order_id:
            self._client_to_broker_order_ids[client_order_id] = broker_order_id
            self._broker_to_client_order_ids[broker_order_id] = client_order_id

    def _bind_order_owner(
        self, client_order_id: str, broker_order_id: str, owner_strategy_id: str
    ) -> None:
        if client_order_id:
            self._client_to_strategy_ids[client_order_id] = owner_strategy_id
        if broker_order_id:
            self._broker_to_strategy_ids[broker_order_id] = owner_strategy_id

    def _resolve_owner_strategy_id(self, payload: Any) -> str:
        owner_strategy_id = str(
            self._payload_field(payload, "owner_strategy_id")
        ).strip()
        if owner_strategy_id:
            return owner_strategy_id
        broker_order_id = str(self._payload_field(payload, "broker_order_id")).strip()
        client_order_id = str(self._payload_field(payload, "client_order_id")).strip()
        if not client_order_id and broker_order_id:
            client_order_id = self._resolve_client_order_id(broker_order_id)
        if client_order_id:
            mapped = self._client_to_strategy_ids.get(client_order_id, "").strip()
            if mapped:
                return mapped
        if broker_order_id:
            mapped = self._broker_to_strategy_ids.get(broker_order_id, "").strip()
            if mapped:
                return mapped
        return "_default"

    def _payload_to_dict(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            return dict(payload)
        if hasattr(payload, "__dict__"):
            return dict(getattr(payload, "__dict__"))
        return {}

    def _resolve_client_order_id(self, broker_order_id: str) -> str:
        return self._broker_to_client_order_ids.get(broker_order_id, "")

    def _resolve_broker_order_id(self, client_order_id: str) -> str:
        return self._client_to_broker_order_ids.get(client_order_id, "")

    def _close_order_mapping(self, client_order_id: str, broker_order_id: str) -> None:
        if client_order_id:
            self._client_to_broker_order_ids.pop(client_order_id, None)
            self._client_to_strategy_ids.pop(client_order_id, None)
        if broker_order_id:
            self._broker_to_client_order_ids.pop(broker_order_id, None)
            self._broker_to_strategy_ids.pop(broker_order_id, None)
            self._closed_broker_order_ids.add(broker_order_id)

    def _is_terminal_status(self, status: Any) -> bool:
        status_text = str(status).strip().lower()
        return status_text in {"filled", "cancelled", "canceled", "rejected"}

    def can_submit_client_order(self, client_order_id: str) -> bool:
        """Check whether a client order id can be submitted again."""
        broker_order_id = self._resolve_broker_order_id(client_order_id)
        if not broker_order_id:
            return True
        if broker_order_id in self._closed_broker_order_ids:
            return True
        snapshot = self._broker_order_states.get(broker_order_id)
        if snapshot is None:
            return False
        status = self._payload_field(snapshot, "status")
        return self._is_terminal_status(status)

    def get_execution_capabilities(self) -> dict[str, Any]:
        """Return execution capabilities for broker live mode."""
        return {
            "broker_live": True,
            "client_order_id": True,
            "order_type": True,
            "time_in_force_str": True,
            "broker_extra_fields": [],
        }

    def _notify_strategy_error(
        self,
        strategy: Strategy,
        error: Exception,
        source: str,
        payload: Any,
    ) -> None:
        on_error = getattr(strategy, "on_error", None)
        if on_error is None:
            return
        try:
            on_error(error, source, payload)
        except Exception:
            pass

    def _safe_strategy_callback(
        self,
        strategy: Strategy,
        callback_name: str,
        payload: Any,
    ) -> None:
        callback = getattr(strategy, callback_name, None)
        if callback is None:
            return
        try:
            callback(payload)
        except Exception as exc:
            on_error = getattr(strategy, "on_error", None)
            if on_error is not None and callback_name != "on_error":
                on_error(exc, callback_name, payload)

    def _apply_time_limit(self, strategy: Strategy, duration_str: str) -> None:
        """Inject time check into strategy methods."""
        import re

        # Parse duration
        duration_sec = 0
        match = re.match(r"^(\d+)([smh]?)$", duration_str)
        if match:
            val, unit = match.groups()
            val = int(val)
            if unit == "s" or unit == "":
                duration_sec = val
            elif unit == "m":
                duration_sec = val * 60
            elif unit == "h":
                duration_sec = val * 3600
        else:
            print(
                f"[LiveRunner] Warning: Invalid duration format '{duration_str}', "
                "ignoring."
            )
            return

        start_time = time.time()

        # Patch on_bar
        original_on_bar = strategy.on_bar

        def wrapped_on_bar(bar: Bar) -> None:
            if time.time() - start_time > duration_sec:
                raise KeyboardInterrupt(f"Duration {duration_str} reached")
            original_on_bar(bar)

        # Use setattr to bypass mypy method assignment check
        setattr(strategy, "on_bar", wrapped_on_bar)

        # Patch on_tick if it exists/is overridden
        if hasattr(strategy, "on_tick"):
            original_on_tick = strategy.on_tick

            def wrapped_on_tick(tick: Any) -> None:
                if time.time() - start_time > duration_sec:
                    raise KeyboardInterrupt(f"Duration {duration_str} reached")
                original_on_tick(tick)

            setattr(strategy, "on_tick", wrapped_on_tick)

    def _print_summary(self) -> None:
        try:
            results = self.engine.get_results()
            print("\n" + "=" * 50)
            print("TRADING SUMMARY (Manual Stop)")
            print("=" * 50)
            print(f"Total Return: {results.metrics.total_return_pct:.2%}")
            print(f"Annualized Return: {results.metrics.annualized_return:.2%}")
            print(f"Max Drawdown: {results.metrics.max_drawdown_pct:.2%}")
            print(f"Sharpe Ratio: {results.metrics.sharpe_ratio:.4f}")
            print(f"Win Rate: {results.metrics.win_rate:.2%}")
            print(f"Total Trades: {len(results.trades)}")
            print("=" * 50)

            # Print Current Positions if available
            if results.snapshots:
                last_snapshots = results.snapshots[-1][1]
                print("\nCurrent Positions:")
                has_pos = False
                for s in last_snapshots:
                    if abs(s.quantity) > 0:
                        print(f"  {s.symbol}: {s.quantity}")
                        has_pos = True
                if not has_pos:
                    print("  (None)")
        except Exception as e:
            print(f"Error generating summary: {e}")
