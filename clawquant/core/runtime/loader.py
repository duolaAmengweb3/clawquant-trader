"""Strategy discovery, loading, and validation.

Scans ``strategies_builtin/`` and ``strategies_user/`` directories, imports
Python modules, and finds all concrete ``BaseStrategy`` subclasses.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Type

import numpy as np
import pandas as pd

from clawquant.core.runtime.base_strategy import BaseStrategy
from clawquant.core.runtime.models import MarketState, PortfolioState, StrategyMetadata

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent  # clawquant/
BUILTIN_DIR: Path = _PACKAGE_ROOT / "strategies_builtin"
USER_DIR: Path = _PACKAGE_ROOT / "strategies_user"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _import_module_from_file(filepath: Path, module_name: str | None = None):
    """Import a Python file as a module and return it."""
    if module_name is None:
        module_name = f"_clawquant_dyn_{filepath.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(filepath))
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        sys.modules.pop(module_name, None)
        return None
    return mod


def _find_strategy_classes(module) -> List[Type[BaseStrategy]]:
    """Return all concrete BaseStrategy subclasses defined in *module*."""
    classes: List[Type[BaseStrategy]] = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, BaseStrategy)
            and obj is not BaseStrategy
            and not inspect.isabstract(obj)
        ):
            classes.append(obj)
    return classes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def discover_strategies() -> Dict[str, Type[BaseStrategy]]:
    """Scan built-in and user strategy directories.

    Returns a mapping of ``strategy_name -> strategy_class``.
    """
    result: Dict[str, Type[BaseStrategy]] = {}

    for directory in (BUILTIN_DIR, USER_DIR):
        if not directory.is_dir():
            continue
        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            mod = _import_module_from_file(py_file)
            if mod is None:
                continue
            for cls in _find_strategy_classes(mod):
                try:
                    meta = cls.metadata()
                    result[meta.name] = cls
                except Exception:  # noqa: BLE001
                    pass

    return result


def load_strategy(name: str) -> BaseStrategy:
    """Instantiate a strategy by name.

    Supports the special ``file:/path/to/strategy.py`` syntax to load a
    strategy from an arbitrary filesystem path.

    Parameters
    ----------
    name:
        Either a registered strategy name (e.g. ``"ma_crossover"``) or a
        ``file:`` URI pointing to a Python file.

    Returns
    -------
    An instantiated ``BaseStrategy`` subclass.

    Raises
    ------
    ValueError
        If the strategy cannot be found or loaded.
    """
    # Handle file: protocol
    if name.startswith("file:"):
        filepath = Path(name[5:])
        if not filepath.is_file():
            raise ValueError(f"Strategy file not found: {filepath}")
        mod = _import_module_from_file(filepath)
        if mod is None:
            raise ValueError(f"Failed to import strategy file: {filepath}")
        classes = _find_strategy_classes(mod)
        if not classes:
            raise ValueError(
                f"No BaseStrategy subclass found in {filepath}"
            )
        return classes[0]()

    # Lookup by name
    strategies = discover_strategies()
    if name not in strategies:
        available = ", ".join(sorted(strategies.keys())) or "(none)"
        raise ValueError(
            f"Strategy '{name}' not found. Available: {available}"
        )
    return strategies[name]()


def list_strategies() -> List[StrategyMetadata]:
    """Return metadata for every discovered strategy."""
    result: List[StrategyMetadata] = []
    for cls in discover_strategies().values():
        try:
            result.append(cls.metadata())
        except Exception:  # noqa: BLE001
            pass
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _make_synthetic_ohlcv(bars: int = 100) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame for validation."""
    np.random.seed(42)
    close = 100.0 + np.cumsum(np.random.randn(bars) * 0.5)
    close = np.maximum(close, 1.0)  # keep prices positive
    high = close + np.abs(np.random.randn(bars) * 0.3)
    low = close - np.abs(np.random.randn(bars) * 0.3)
    low = np.maximum(low, 0.5)
    open_ = low + (high - low) * np.random.rand(bars)
    volume = np.random.rand(bars) * 1000 + 100

    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def validate_strategy(strategy_cls: Type[BaseStrategy]) -> dict:
    """Run comprehensive validation checks on a strategy class.

    Returns
    -------
    dict with keys:
    * ``valid`` (bool)
    * ``errors`` (List[str])
    * ``warnings`` (List[str])
    """
    errors: List[str] = []
    warnings: List[str] = []

    # ---- Check it is a proper subclass --------------------------------
    if not (inspect.isclass(strategy_cls) and issubclass(strategy_cls, BaseStrategy)):
        errors.append("Class is not a subclass of BaseStrategy.")
        return {"valid": False, "errors": errors, "warnings": warnings}

    if inspect.isabstract(strategy_cls):
        missing = sorted(
            m for m in strategy_cls.__abstractmethods__  # type: ignore[attr-defined]
        )
        errors.append(f"Class is abstract; missing methods: {missing}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # ---- Check all 6 methods are implemented (not just pass) ----------
    required_methods = [
        "metadata",
        "compute_indicators",
        "generate_signals",
        "position_sizing",
        "risk_controls",
        "explain",
    ]
    for method_name in required_methods:
        method = getattr(strategy_cls, method_name, None)
        if method is None:
            errors.append(f"Missing method: {method_name}")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    # ---- Check metadata() returns valid StrategyMetadata ---------------
    try:
        meta = strategy_cls.metadata()
        if not isinstance(meta, StrategyMetadata):
            errors.append(
                f"metadata() returned {type(meta).__name__}, expected StrategyMetadata"
            )
        else:
            # Check params_schema has defaults
            schema = meta.params_schema
            if not isinstance(schema, dict):
                errors.append("params_schema is not a dict")
            else:
                props = schema.get("properties", {})
                if not props:
                    warnings.append("params_schema has no properties defined")
                for prop_name, prop_def in props.items():
                    if "default" not in prop_def:
                        errors.append(
                            f"params_schema property '{prop_name}' has no default value"
                        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"metadata() raised {type(exc).__name__}: {exc}")

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    # ---- Instantiate and run with synthetic data ----------------------
    try:
        instance = strategy_cls()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Failed to instantiate strategy: {exc}")
        return {"valid": False, "errors": errors, "warnings": warnings}

    df = _make_synthetic_ohlcv(100)
    params = _defaults_from_schema(meta.params_schema)

    # compute_indicators
    try:
        df_ind = instance.compute_indicators(df.copy(), params)
        if not isinstance(df_ind, pd.DataFrame):
            errors.append("compute_indicators() did not return a DataFrame")
        else:
            # Check OHLCV columns are untouched
            for col in ("open", "high", "low", "close", "volume"):
                if col not in df_ind.columns:
                    errors.append(f"compute_indicators() dropped OHLCV column '{col}'")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"compute_indicators() raised {type(exc).__name__}: {exc}")
        df_ind = df.copy()

    # generate_signals
    try:
        signals = instance.generate_signals(df_ind, params)
        if not isinstance(signals, pd.Series):
            errors.append(
                f"generate_signals() returned {type(signals).__name__}, expected pd.Series"
            )
        else:
            if len(signals) != len(df_ind):
                errors.append(
                    f"generate_signals() length {len(signals)} != DataFrame length {len(df_ind)}"
                )
            unique_vals = set(signals.dropna().unique())
            invalid = unique_vals - {-1, 0, 1}
            if invalid:
                errors.append(
                    f"generate_signals() contains invalid values: {invalid}. "
                    f"Allowed: {{-1, 0, 1}}"
                )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"generate_signals() raised {type(exc).__name__}: {exc}")

    # position_sizing
    try:
        ps = PortfolioState(
            cash=10000.0,
            equity=10000.0,
            total_value=10000.0,
        )
        size = instance.position_sizing(1, ps, params)
        if not isinstance(size, (int, float)):
            errors.append(
                f"position_sizing() returned {type(size).__name__}, expected float"
            )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"position_sizing() raised {type(exc).__name__}: {exc}")

    # risk_controls
    try:
        ms = MarketState(
            symbol="TEST/USDT",
            current_price=100.0,
            bar_index=0,
            timestamp=datetime.now(tz=timezone.utc),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1000.0,
        )
        actions = instance.risk_controls(ps, ms, params)
        if not isinstance(actions, list):
            errors.append(
                f"risk_controls() returned {type(actions).__name__}, expected list"
            )
        else:
            valid_actions = {"REDUCE", "FLATTEN", "SKIP", "NONE"}
            for i, action in enumerate(actions):
                if not isinstance(action, dict):
                    errors.append(f"risk_controls()[{i}] is not a dict")
                elif "action" not in action or "reason" not in action:
                    errors.append(
                        f"risk_controls()[{i}] missing 'action' or 'reason' key"
                    )
                elif action["action"] not in valid_actions:
                    errors.append(
                        f"risk_controls()[{i}] action '{action['action']}' not in {valid_actions}"
                    )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"risk_controls() raised {type(exc).__name__}: {exc}")

    # explain
    try:
        explanation = instance.explain({"signal": 1, "price": 100.0})
        if not isinstance(explanation, dict):
            errors.append(
                f"explain() returned {type(explanation).__name__}, expected dict"
            )
        else:
            if "reasons" not in explanation:
                warnings.append("explain() output missing 'reasons' key")
            if "key_metrics" not in explanation:
                warnings.append("explain() output missing 'key_metrics' key")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"explain() raised {type(exc).__name__}: {exc}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def _defaults_from_schema(schema: dict) -> dict:
    """Extract default parameter values from a JSON Schema."""
    params: dict = {}
    for prop_name, prop_def in schema.get("properties", {}).items():
        if "default" in prop_def:
            params[prop_name] = prop_def["default"]
    return params
