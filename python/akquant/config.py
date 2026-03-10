from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

"""
AKQuant Configuration System.

This module defines the configuration hierarchy for backtests.
It provides a structured way to define simulation parameters, asset properties,
execution rules, and risk constraints.

**Configuration Hierarchy:**

1.  **BacktestConfig** (Top Level): Defines the **Simulation Scenario**.
    *   **"When?"**: `start_time`, `end_time`
    *   **"What assets?"**: `instruments`, `instruments_config`
    *   **"How?"**: `strategy_config` (Strategy & Account settings)
    *   **"Analysis?"**: `bootstrap_samples`, `analysis_config`

2.  **InstrumentConfig** (Asset Level): Defines **Asset Properties**.
    *   **"What is it?"**: `symbol`, `asset_type`, `multiplier`
    *   **"How much leverage?"**: `margin_ratio`
    *   **"What costs?"**: `commission_rate` (overrides global), `slippage`

3.  **StrategyConfig** (Account Level): Defines **Account & Execution**.
    *   **"How much money?"**: `initial_cash`
    *   **"How to execute?"**: `slippage`, `volume_limit_pct`
    *   **"What constraints?"**: `max_long_positions`, `risk`

4.  **RiskConfig** (Risk Level): Defines **Safety Constraints**.
    *   **"How large?"**: `max_position_pct`, `max_order_size`
    *   **"When to stop?"**: `max_account_drawdown`, `stop_loss_threshold`
    *   **"What is forbidden?"**: `restricted_list`

**Usage Example:**

```python
# 1. Define Risk Rules
risk = RiskConfig(max_position_pct=0.1, stop_loss_threshold=0.8)

# 2. Configure Strategy & Account
strategy_conf = StrategyConfig(
    initial_cash=1_000_000,
    commission_rate=0.0003,
    slippage=0.0002,  # 2 bps
    risk=risk
)

# 3. Configure Specific Instruments (Optional)
rb_conf = InstrumentConfig(symbol="RB", asset_type="FUTURES", multiplier=10)

# 4. Create Backtest Configuration
config = BacktestConfig(
    start_time="2023-01-01",
    end_time="2023-12-31",
    strategy_config=strategy_conf,
    instruments=["AAPL", "GOOG"],
    instruments_config={"RB": rb_conf}
)
```
"""


@dataclass
class InstrumentConfig:
    """
    [Asset Level] Configuration for a specific instrument.

    Defines **Asset Properties**.

    *   **"What is it?"**: `symbol`, `asset_type`, `multiplier`
    *   **"How much leverage?"**: `margin_ratio`
    *   **"What costs?"**: `commission_rate` (overrides global), `slippage`

    **Core Properties:**
    :param symbol: Instrument symbol (e.g., "AAPL", "RB2305").
    :param asset_type: Asset type ("STOCK", "FUTURES", "FUND", "OPTION").
                       Default "STOCK".
    :param multiplier: Contract multiplier. Default 1.0.
    :param margin_ratio: Margin ratio (e.g., 0.1 for 10% margin).
                         Default 1.0 (No leverage).
    :param tick_size: Minimum price movement. Default 0.01.
    :param lot_size: Minimum trading unit (round lot). Default 1.

    **Cost & Execution Overrides:**
    These fields override the global settings in `StrategyConfig` for
    this specific asset.
    :param commission_rate: Commission rate (e.g., 0.0003).
    :param min_commission: Minimum commission per order.
    :param stamp_tax_rate: Stamp tax rate (sell side only).
    :param transfer_fee_rate: Transfer fee rate.
    :param slippage: Asset-specific slippage (e.g., 0.0002).

    **Option Specific:**
    :param option_type: "CALL" or "PUT".
    :param strike_price: Strike price.
    :param expiry_date: Expiry date string (YYYY-MM-DD).
    :param underlying_symbol: Underlying asset symbol.
    """

    symbol: str
    asset_type: str = "STOCK"  # STOCK, FUND, FUTURES, OPTION
    multiplier: float = 1.0
    margin_ratio: float = 1.0
    tick_size: float = 0.01
    lot_size: int = 1

    # Costs & Execution (Asset Specific)
    commission_rate: Optional[float] = None
    min_commission: Optional[float] = None
    stamp_tax_rate: Optional[float] = None
    transfer_fee_rate: Optional[float] = None
    slippage: Optional[float] = None

    # Option specific
    option_type: Optional[str] = None  # CALL, PUT
    strike_price: Optional[float] = None
    expiry_date: Optional[str] = None
    underlying_symbol: Optional[str] = None


@dataclass
class RiskConfig:
    """
    [Risk Level] Configuration for Risk Management.

    Defines **Safety Constraints**.

    *   **"How large?"**: `max_position_pct`, `max_order_size`
    *   **"When to stop?"**: `max_account_drawdown`, `stop_loss_threshold`
    *   **"What is forbidden?"**: `restricted_list`

    **Order & Position Limits:**
    :param active: Master switch to enable/disable risk checks. Default True.
    :param safety_margin: Cash buffer to reserve (e.g., 0.0001 to avoid precision
                          issues).
    :param max_order_size: Max quantity per order.
    :param max_order_value: Max value per order.
    :param max_position_size: Max quantity per position.
    :param max_position_pct: Max position value as a percentage of total equity
                             (e.g., 0.1 for 10%).
    :param restricted_list: List of symbols forbidden to trade.
    :param sector_concentration: Tuple (limit, sector_map) to limit sector exposure.

    **Account Level Protections:**
    :param max_account_drawdown: Max allowed drawdown percentage (e.g., 0.2 for 20%).
                                 If breached, may trigger liquidations or stop trading.
    :param max_daily_loss: Max allowed daily loss percentage.
    :param stop_loss_threshold: Net value threshold (e.g., 0.8). If equity drops below
                                initial_cash * threshold, trading is stopped.
    """

    active: bool = True
    safety_margin: float = 0.0001
    max_order_size: Optional[float] = None
    max_order_value: Optional[float] = None
    max_position_size: Optional[float] = None
    restricted_list: Optional[List[str]] = None
    max_position_pct: Optional[float] = None
    sector_concentration: Optional[Union[float, tuple]] = None

    # Account Level Risk
    max_account_drawdown: Optional[float] = None
    max_daily_loss: Optional[float] = None
    stop_loss_threshold: Optional[float] = (
        None  # e.g., 0.8 means stop if equity < 0.8 * initial
    )


@dataclass
class StrategyConfig:
    """
    [Account Level] Configuration for strategy execution environment.

    Defines **Account & Execution**.

    *   **"How much money?"**: `initial_cash`
    *   **"How to execute?"**: `slippage`, `volume_limit_pct`
    *   **"What constraints?"**: `max_long_positions`, `risk`

    **Capital & Costs:**
    :param initial_cash: Initial capital for the backtest. Default 100,000.0.
    :param commission_rate: Default commission rate (e.g., 0.0003).
    :param stamp_tax_rate: Default stamp tax rate (sell side).
    :param transfer_fee_rate: Default transfer fee rate.
    :param min_commission: Default minimum commission.

    **Execution Behavior:**
    :param enable_fractional_shares: Allow fractional share trading. Default False.
    :param round_fill_price: Round execution price to tick size. Default True.
    :param slippage: Global slippage model (Percentage). 0.0002 means 2 bps slippage.
                     Applied to all trades unless overridden in `InstrumentConfig`.
    :param volume_limit_pct: Max participation rate. 0.25 means order size is
                             capped at 25% of the bar's volume. Default 0.25.
    :param exit_on_last_bar: Auto-close all positions at the end of backtest.
                             Default True.
    :param indicator_mode: Indicator execution mode. "incremental" updates indicator
                           state on each bar; "precompute" prepares full series before
                           run.

    **Constraints & Risk:**
    :param max_long_positions: Max number of simultaneous long positions.
    :param max_short_positions: Max number of simultaneous short positions.
    :param risk: `RiskConfig` object containing detailed risk rules.
    """

    # Capital Management
    initial_cash: float = 100000.0

    # Fees & Commission (Default / Fallback)
    commission_rate: float = 0.0  # Commission rate (e.g. 0.0003 for 0.03%)
    stamp_tax_rate: float = 0.0  # Stamp tax rate (e.g. 0.001, sell only)
    transfer_fee_rate: float = 0.0  # Transfer fee rate
    min_commission: float = 0.0  # Minimum commission per order (e.g. 5.0)

    # Execution
    enable_fractional_shares: bool = False
    round_fill_price: bool = True
    slippage: float = 0.0  # Global slippage (e.g., 0.0002 for 2 bps)
    volume_limit_pct: float = 0.25  # Max participation rate (e.g., 25% of bar volume)

    # Position Sizing Constraints
    max_long_positions: Optional[int] = None
    max_short_positions: Optional[int] = None

    # Other
    exit_on_last_bar: bool = True
    indicator_mode: str = "precompute"

    # Risk Config
    risk: Optional[RiskConfig] = None

    # Multi-Strategy Topology & Risk Controls
    strategy_id: Optional[str] = None
    strategies_by_slot: Optional[Dict[str, Any]] = None
    strategy_source: Optional[str] = None
    strategy_loader: Optional[str] = None
    strategy_loader_options: Optional[Dict[str, Any]] = None
    strategy_max_order_value: Optional[Dict[str, float]] = None
    strategy_max_order_size: Optional[Dict[str, float]] = None
    strategy_max_position_size: Optional[Dict[str, float]] = None
    strategy_max_daily_loss: Optional[Dict[str, float]] = None
    strategy_max_drawdown: Optional[Dict[str, float]] = None
    strategy_reduce_only_after_risk: Optional[Dict[str, bool]] = None
    strategy_risk_cooldown_bars: Optional[Dict[str, int]] = None
    strategy_priority: Optional[Dict[str, int]] = None
    strategy_risk_budget: Optional[Dict[str, float]] = None
    portfolio_risk_budget: Optional[float] = None


@dataclass
class BacktestConfig:
    """
    [Top Level] Configuration for the entire Backtest Simulation.

    Defines the **SIMULATION SCENARIO**.

    *   **"When?"**: `start_time`, `end_time`
    *   **"What assets?"**: `instruments`, `instruments_config`
    *   **"How?"**: `strategy_config` (Strategy & Account settings)
    *   **"Analysis?"**: `bootstrap_samples`, `analysis_config`

    **Time & Scope:**
    :param start_time: Backtest start time (e.g., "2020-01-01").
    :param end_time: Backtest end time.
    :param strategy_config: Configuration for the strategy/account.

    **Asset Selection:**
    :param instruments: Quick list of symbols to trade (using default properties).
                        Example: `["AAPL", "MSFT"]`.
    :param instruments_config: Detailed configuration for specific assets.
                               List of `InstrumentConfig` or Dict
                               `{symbol: InstrumentConfig}`.
                               Use this for Futures, Options, or non-standard Stocks.

    **Environment:**
    :param benchmark: Benchmark symbol for performance comparison.
    :param timezone: Exchange timezone. Default "Asia/Shanghai".
    :param show_progress: Show progress bar. Default True.
    :param history_depth: Auto-load N bars of history before strategy starts.

    **Analysis:**
    :param bootstrap_samples: Number of bootstrap samples for statistical significance.
    :param bootstrap_sample_size: Size of each bootstrap sample.
    :param analysis_config: Dictionary for extra analysis settings (e.g., plotting).
    """

    strategy_config: StrategyConfig
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # Asset Selection
    instruments: Optional[List[str]] = None  # Quick list of symbols (Default props)
    instruments_config: Optional[
        Union[List[InstrumentConfig], Dict[str, InstrumentConfig]]
    ] = None  # Detailed props (Overrides defaults)

    benchmark: Optional[str] = None
    timezone: str = "Asia/Shanghai"
    show_progress: bool = True
    history_depth: int = 0

    # Analysis & Bootstrap
    bootstrap_samples: int = 1000
    bootstrap_sample_size: Optional[int] = None
    analysis_config: Optional[Dict[str, Any]] = None


# Global instance
strategy_config = StrategyConfig()
