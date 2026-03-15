#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${AKQUANT_CONDA_ENV:-akquant}"

conda run -n "${ENV_NAME}" maturin develop
conda run -n "${ENV_NAME}" ruff check python/akquant tests
conda run -n "${ENV_NAME}" mypy python/akquant
conda run -n "${ENV_NAME}" pytest tests/test_engine.py -k "engine_oco_avoids_same_batch_double_fill"
conda run -n "${ENV_NAME}" pytest tests/test_engine.py -k "engine_bracket_activates_exit_orders"
conda run -n "${ENV_NAME}" pytest tests/test_strategy_extras.py -k "oco_group_prefers_engine_registration_when_available or oco_group_falls_back_to_deferred_engine_queue_on_runtime_error"
conda run -n "${ENV_NAME}" pytest tests/test_strategy_extras.py -k "bracket_prefers_engine_registration_when_available or bracket_falls_back_to_deferred_engine_queue_on_runtime_error"
