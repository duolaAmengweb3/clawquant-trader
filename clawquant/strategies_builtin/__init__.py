"""Built-in strategies shipped with ClawQuant Trader."""

from clawquant.strategies_builtin.dca import DCAStrategy
from clawquant.strategies_builtin.grid import GridStrategy
from clawquant.strategies_builtin.ma_crossover import MACrossoverStrategy

__all__ = [
    "DCAStrategy",
    "GridStrategy",
    "MACrossoverStrategy",
]
