"""
RITC package initialization.

This package provides modules for algorithmic trading, including order books, portfolio management, data fetching, volatility analysis, and utility functions.
"""

from .base import ApiTrading, NewsBook, OrderBook, Portfolio, SimulatedTrading, utils, VolAnalysis
from .ALGO import ArbitrageStrategy
from .datafetcher import ALGODataFetcher, ClientDataFetcher

__all__ = [
    "ApiTrading",
    "NewsBook",
    "OrderBook",
    "Portfolio",
    "SimulatedTrading",
    "utils",
    "VolAnalysis",
    "ArbitrageStrategy",
    "ALGODataFetcher",
    "ClientDataFetcher",
]
