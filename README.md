> **Note:** The original data source for this project is currently not accessible. 

# RITC Algorithmic Trading Framework

## Overview
RITC is an algorithmic trading simulation framework designed for multi-asset, multi-strategy trading in a simulated market. It supports tender arbitrage, ETF-stock conversion, ETF arbitrage, and risk management strategies. The system is modular, configurable, and supports real-time command input for strategy control and manual trading.

## Features
- Multiple trading strategies: tender arbitrage, conversion, ETF arbitrage, profit/loss management
- Real-time command interface for manual trading and strategy control
- Configurable parameters for market adaptation
- Volatility-based dynamic thresholds
- Fast position open/close utilities

## Installation
1. Clone the repository:
   ```bash
   git clone <https://github.com/QinqinAndMacaulayCat/RITC2025.git>
   cd RITC
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start
1. Edit `config.ini` and `tests/params_algotrading.csv` to set your market and strategy parameters.
2. Run the main strategy script:
   ```bash
   python tests/ALGOStrategy.py
   ```
3. Use keyboard commands (see below) to interact with the simulation in real time.

## Configuration Parameters
Adjust these parameters in `config.ini` and `params_algotrading.csv` to tune strategies and risk management:

- **Strategy Activation**
  - `strategy1_tender`, `strategy2_convertion`, `strategy3_ETF`, `strategy4_profit_loss`: Enable/disable strategies
- **Position & Limits**
  - `max_position_usage`: Maximum portfolio usage (e.g., 0.9 for 90%)
  - `strict_limits`: Stop trading if limits exceeded
  - `end_trade_before`: Stop trading N ticks before round end
- **Thresholds & Volatility**
  - `deviation_threshold_*`, `slippage_tolerance_*`: Profit/slippage thresholds by volatility
  - `cap_gdp`, `floor_gdp`, `cap_bci`, `floor_bci`: Macro event thresholds
  - `conversion_deviation_threshold`, `ETF_deviation_threshold`: Strategy-specific thresholds
  - `take_profit_line`, `stop_loss_line`, `take_profit_line_ETF`, `stop_loss_line_ETF`: Risk management
- **Order Sizes & Timing**
  - `arbitrage_order_size`, `etf_arbitrage_order_size`: Trade sizes
  - `shock_duration`, `etf_duration`: Timing for news and ETF strategies
  - `sleep_time`: Simulation tick interval
- **Volatility Settings**
  - `volatility_windows`, `volatility_quantile_threshold`, `volatility_quantile_threshold_low`, `volatility_signal_start_tick`

## Command Reference
Interact with the simulation using these keyboard commands:

- **Trading**
  - `b` / `s`: Buy/Sell (choose asset, amount, order type, price)
  - `fb` / `fs`: Fast buy/sell 10,000 shares of JOY_C
  - `fo`: Fast open ETF pair positions
  - `fc`: Fast close ETF or stock positions
  - `c`: Close position for a specific asset
- **Strategy Control**
  - `p`: Pause auto trading
  - `r`: Resume auto trading
  - `s1`/`s2`/`s3`/`s4`: Stop strategies 1-4
  - `r1`/`r2`/`r3`/`r4`: Resume strategies 1-4
- **News & Data**
  - `n`: Input news (GDP/BCI)
  - `ct`: Correct news data
  - `q`: Show fair price of JOY_U
- **Other**
  - `bk`: Cancel command input
  - `e`: End arbitrage before threshold (choose strategy)

