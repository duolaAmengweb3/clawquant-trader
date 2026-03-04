"""Multi-symbol time alignment for OHLCV DataFrames."""

from __future__ import annotations

import logging
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)


def align_dataframes(
    dfs: Dict[str, pd.DataFrame],
) -> Dict[str, pd.DataFrame]:
    """Align multiple OHLCV DataFrames to a common set of timestamps.

    Steps:
    1. Index every DataFrame by its ``timestamp`` column.
    2. Find the intersection of timestamps across all symbols.
    3. Reindex each DataFrame to only those common timestamps.
    4. Drop any row where **any** symbol has a NaN value.
    5. Return a dict of aligned DataFrames (all same length / timestamps).

    Parameters
    ----------
    dfs:
        ``{symbol: DataFrame}`` where each DataFrame has a ``timestamp``
        column and OHLCV price columns.

    Returns
    -------
    Dict[str, pd.DataFrame]
        Aligned DataFrames with identical timestamps.
    """
    if not dfs:
        return {}

    if len(dfs) == 1:
        symbol, df = next(iter(dfs.items()))
        return {symbol: df.reset_index(drop=True)}

    # 1. Set timestamp as index for each DF
    indexed: Dict[str, pd.DataFrame] = {}
    for sym, df in dfs.items():
        tmp = df.copy()
        tmp = tmp.set_index("timestamp").sort_index()
        indexed[sym] = tmp

    # 2. Common timestamp intersection
    common_idx = None
    for tmp in indexed.values():
        if common_idx is None:
            common_idx = tmp.index
        else:
            common_idx = common_idx.intersection(tmp.index)

    if common_idx is None or common_idx.empty:
        logger.warning("No common timestamps found across symbols.")
        empty = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return {sym: empty.copy() for sym in dfs}

    # 3. Reindex
    reindexed: Dict[str, pd.DataFrame] = {}
    for sym, tmp in indexed.items():
        reindexed[sym] = tmp.reindex(common_idx)

    # 4. Drop rows where any symbol has NaN
    nan_mask = None
    for tmp in reindexed.values():
        row_has_nan = tmp.isna().any(axis=1)
        if nan_mask is None:
            nan_mask = row_has_nan
        else:
            nan_mask = nan_mask | row_has_nan

    clean_idx = common_idx[~nan_mask] if nan_mask is not None else common_idx

    # 5. Build final output
    result: Dict[str, pd.DataFrame] = {}
    for sym in dfs:
        out = reindexed[sym].loc[clean_idx].copy()
        out = out.reset_index()  # moves timestamp back to a column
        result[sym] = out.reset_index(drop=True)

    logger.info(
        "Aligned %d symbols to %d common timestamps",
        len(result),
        len(clean_idx),
    )
    return result
