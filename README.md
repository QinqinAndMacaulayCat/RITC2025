
## parameters
change the parameters below according to the market conditions:

1. if use certain strategy. or change the setting during the heat by command
    - strategy1_tender = True
    - strategy2_convertion = True
    - strategy3_ETF = True
    - strategy4_profit_loss = True

2. common settings
    - max_position_usage = 0.9: the positions we uses won't exceed 90%.
    - strict_limits = True: if true, stop trading once the position exceeds limits, else, still trade 
    - end_trade_before = 5: stop trading n ticks before end of the round, in case unable to close position at the end of the case

3. threshold
    - deviation_threshold_high = 0.5: the profit for each share in our tender strategy. only execute the strategy when the profit exceed this threshold. we set different threshold for assets with different volatility. the higher the volatility, the higher the threshold.
    - slippage_tolerance_high: Slippage in trading refers to the difference between the expected price of a trade and the actual price at which the trade is executed. It typically occurs due to market volatility and liquidity constraints. used to decide if using limit orders. slippage is 

    - deviation_threshold_mid: under mid volatility
    - slippage_tolerance_mid: under mid volatility
    - deviation_threshold_low: under low volatility
    - slippage_tolerance_low: under low volatility

    - cap_gdp: if the difference between GDP this month and the level last year in the same month exceeds this level, we may be JOY_C manually
    - floor_gdp: if lower than (-1) * floor_gdp, we may short JOY_C manually.
    - cap_bci: if the percentage change of BCI exceeds this level, we may be JOY_U manually
    - floor_bci: we may short JOY_U manually.

    - conversion_deviation_threshold = 3: threshold for conversion strategy. Since we face uncertainty for 4 stocks and 1 etf, the threshold should be higher. 
    - ETF_deviation_threshold = 0.5: when profit exceed this threshold, doing arbitrage between JOY_C and JOY_U. 

    - take_profit_line = 0.05: take profit if return rate is higher than this level. applied to all assets, 0.05 means 5%. 
    - stop_loss_line = 0.1: stop loss if return rate is lower than stop loss line. eg. < -10%

    - take_profit_line_ETF = 2: if the per share return of ETF arbitrage strategy higher than this level, close positions. 
    - stop_loss_line_ETF = 30.

4. strategy size
    - arbitrage_order_size = 10000
    - etf_arbitrage_order_size = 10000

5. duration
    - shock_duration = 10: close the positions on ETF after getting the news and build conversion strategy. shock_duration is the lag ticks.
    - etf_duration = 120: in etf strategy, if no take profit or end loss or manual signal, close the positions on ETF after a certain duration. set to be longer as short durations leading to loss.

6. others
    - sleep_time = 0.1: interval between each round
    - volatility_windows = 30: use how many data to calculate volatility
    - volatility_quantile_threshold = 0.8: volitility higher than this level will change the volatility setting of a asset to high. if the volatility of ETF exceeds the threshold, print "volatility warning"
    - volatility_quantile_threshold_low = 0.2: volitility lower than this level will change the volatility setting of a asset to low.
    - volatility_signal_start_tick = 100: the changes above based on volatility only happens after this time point. in case the volatility data is not enough. 



## command

pressure 'esc'

1. b - buy / s - sell
    input
    -  capital asset name: jc - JOY_C, ju - JOYU, s - SAD,
                            c - CRY, a - ANGER, f - FEAR
    -  amount to buy
    -  price type: l - limit, m - market
    -  price: if it's a limit order. 
2. p - pause auto trading
3. r - resume auto trading
4. s1 - stop strategy 1 tender strategy
5. s2 - stop strategy 2 conversion strategy
6. s3 - stop strategy 3 etf arbitragy strategy
7. s4 - stop strategy 4 take profit and end loss strategy
8. r1 - resume strategy1. similar to r2, r3, r4.
9. n - input news. select:
    - g - gdp
    - b - bci
10. ct - correct wront news data introduced by typo. select:
    - g - gdp
    - b - bci
11. e - end the arbitrage before meeting the threshold. select:
    - 2 - strategy2. close the positions of stocks and ETF by doing opposite trading.
    - 3 - strategy3. close the positions of JOY_U and JOY_C.
12. bk - cancel inputting command. 
13. c - close the position of asset. input asset name
14. fc - fast close position of 
    - 1 - ETF pairs or 
    - 2 - all stock positions.
    used in case the program exits and there are unhedged positions. 
15. fo - fast open positions in strategies:
    - 1 - buy JOY_C and sell JOY_U 10000 shares
    - 2 - sell JOY_C and buy JOY_U 10000 shares
16. fb - fast buy 10000 shares of JOY_C
17. fs - fast sell 10000 shares of JOY_C
15. q - fair price of JOY_U calculated based on JOY_C price and FX

