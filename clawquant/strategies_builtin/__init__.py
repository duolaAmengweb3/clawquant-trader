"""Built-in strategies shipped with ClawQuant Trader."""

from clawquant.strategies_builtin.bollinger_bands import BollingerBandsStrategy
from clawquant.strategies_builtin.breakout import BreakoutStrategy
from clawquant.strategies_builtin.dca import DCAStrategy
from clawquant.strategies_builtin.grid import GridStrategy
from clawquant.strategies_builtin.ma_crossover import MACrossoverStrategy
from clawquant.strategies_builtin.macd import MACDStrategy
from clawquant.strategies_builtin.rsi_reversal import RSIReversalStrategy

__all__ = [
    "BollingerBandsStrategy",
    "BreakoutStrategy",
    "DCAStrategy",
    "GridStrategy",
    "MACrossoverStrategy",
    "MACDStrategy",
    "RSIReversalStrategy",
]
