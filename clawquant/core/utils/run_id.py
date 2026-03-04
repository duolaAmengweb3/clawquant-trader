"""Run ID generation and directory management."""

import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_RUNS_DIR = os.getenv("RUNS_DIR", "runs")


def generate_run_id(
    strategy_name: str,
    symbol: str,
    extra_tag: str | None = None,
) -> str:
    """Generate a unique run identifier.

    Format: ``{strategy}_{symbol_clean}_{YYYYMMDD}_{uuid[:8]}``

    Parameters
    ----------
    strategy_name:
        Name of the strategy (e.g. ``"sma_cross"``).
    symbol:
        Trading pair (e.g. ``"BTC/USDT"``).
    extra_tag:
        Optional extra tag appended before the UUID segment.

    Returns
    -------
    str
        A human-readable, filesystem-safe run ID.
    """
    # Clean the symbol: replace non-alphanumeric chars with underscore, lowercase
    symbol_clean = re.sub(r"[^a-zA-Z0-9]", "_", symbol).strip("_").lower()
    strategy_clean = re.sub(r"[^a-zA-Z0-9_]", "", strategy_name).strip("_").lower()
    date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:8]

    parts = [strategy_clean, symbol_clean, date_str]
    if extra_tag:
        tag_clean = re.sub(r"[^a-zA-Z0-9_]", "", extra_tag).lower()
        parts.append(tag_clean)
    parts.append(short_uuid)

    return "_".join(parts)


def ensure_run_dir(run_id: str) -> Path:
    """Create and return the directory ``{RUNS_DIR}/{run_id}/``.

    Parameters
    ----------
    run_id:
        The run identifier (as produced by :func:`generate_run_id`).

    Returns
    -------
    Path
        Absolute path to the created directory.
    """
    run_dir = Path(_RUNS_DIR) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir.resolve()
