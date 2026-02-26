from typing import TYPE_CHECKING, Optional

from .config import RiskConfig as PyRiskConfig
from .log import get_logger

if TYPE_CHECKING:
    from .akquant import Engine

logger = get_logger()


def apply_risk_config(engine: "Engine", config: Optional[PyRiskConfig]) -> None:
    """
    Apply Python-side RiskConfig to the Rust Engine's RiskManager.

    :param engine: The backtest engine instance.
    :param config: The Python RiskConfig object.
    """
    if config is None:
        return

    # Get the Rust RiskConfig object from the engine's risk manager
    # Assuming engine.risk_manager.config is accessible and mutable
    # Or we can create a new one and assign it

    rust_config = engine.risk_manager.config

    if config.max_order_size is not None:
        rust_config.max_order_size = config.max_order_size

    if config.max_order_value is not None:
        rust_config.max_order_value = config.max_order_value

    if config.max_position_size is not None:
        rust_config.max_position_size = config.max_position_size

    if config.restricted_list is not None:
        rust_config.restricted_list = config.restricted_list

    if config.active is not None:
        rust_config.active = config.active

    if config.safety_margin is not None:
        rust_config.safety_margin = config.safety_margin

    # Use the dedicated setter method to ensure the update propagates to the Engine
    # Direct attribute assignment (engine.risk_manager.config = ...) might only
    # update a copy
    if hasattr(engine, "set_risk_config"):
        engine.set_risk_config(rust_config)
    else:
        # Fallback for older versions or if method is missing
        engine.risk_manager.config = rust_config

    # Apply dynamic rules (max_position_pct, sector_concentration)
    # These are not part of Rust RiskConfig struct but are handled by RiskManager
    rm = engine.risk_manager

    # Apply dynamic rules (max_position_pct, sector_concentration)
    # These are not part of Rust RiskConfig struct but are handled by RiskManager
    rm = engine.risk_manager

    if config.max_position_pct is not None:
        if hasattr(rm, "add_max_position_percent_rule"):
            rm.add_max_position_percent_rule(config.max_position_pct)
        else:
            logger.warning(
                "RiskManager does not support add_max_position_percent_rule."
            )

    if config.sector_concentration is not None:
        if hasattr(rm, "add_sector_concentration_rule"):
            if (
                isinstance(config.sector_concentration, (list, tuple))
                and len(config.sector_concentration) == 2
            ):
                rm.add_sector_concentration_rule(
                    config.sector_concentration[0], config.sector_concentration[1]
                )
            else:
                logger.warning(
                    "sector_concentration must be a tuple (limit, sector_map). "
                    "Rule ignored."
                )
        else:
            logger.warning(
                "RiskManager does not support add_sector_concentration_rule."
            )

    if config.max_account_drawdown is not None:
        if hasattr(rm, "add_max_drawdown_rule"):
            rm.add_max_drawdown_rule(config.max_account_drawdown)
        else:
            logger.warning("RiskManager does not support add_max_drawdown_rule.")

    if config.max_daily_loss is not None:
        if hasattr(rm, "add_max_daily_loss_rule"):
            rm.add_max_daily_loss_rule(config.max_daily_loss)
        else:
            logger.warning("RiskManager does not support add_max_daily_loss_rule.")

    if config.stop_loss_threshold is not None:
        if hasattr(rm, "add_stop_loss_rule"):
            rm.add_stop_loss_rule(config.stop_loss_threshold)
        else:
            logger.warning("RiskManager does not support add_stop_loss_rule.")

    # Update the engine's risk manager with the new rules
    # This is critical if engine.risk_manager returns a copy/clone
    engine.risk_manager = rm
