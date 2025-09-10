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

