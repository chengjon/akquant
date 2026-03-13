from typing import Any

from .utils import parse_duration_to_bars


def auto_configure_model(strategy: Any) -> None:
    """应用模型校验配置（如滚动训练窗口参数）."""
    if strategy._model_configured:
        return

    if strategy.model and strategy.model.validation_config:
        cfg = strategy.model.validation_config
        try:
            train_window = parse_duration_to_bars(cfg.train_window, cfg.frequency)
            step = parse_duration_to_bars(cfg.rolling_step, cfg.frequency)
            strategy.set_rolling_window(train_window, step)
        except Exception as e:
            print(f"Failed to configure model validation: {e}")

    strategy._model_configured = True


def on_train_signal(strategy: Any, context: Any) -> None:
    """滚动训练信号回调."""
    if strategy.model:
        try:
            X_df, _ = strategy.get_rolling_data()

            if (
                strategy.model.validation_config
                and strategy.model.validation_config.verbose
            ):
                ts_str = ""
                if strategy.current_bar:
                    ts_str = strategy.format_time(strategy.current_bar.timestamp)
                print(f"[{ts_str}] Auto-training triggered | Train Size: {len(X_df)}")

            X, y = strategy.prepare_features(X_df, mode="training")
            strategy.model.fit(X, y)
        except NotImplementedError:
            pass
        except Exception as e:
            print(f"Auto-training failed at bar {strategy._bar_count}: {e}")
