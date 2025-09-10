"""
strategies in auto trading
    1. accept the tender or reject the tender based on the arbitrage opportunity between the tender and the underlying asset   
    2. arbitrage based on conversion between ETF and stocks
    3. arbitrage between ETFs, should hedge the currency risk

"""

import threading
import queue
import logging
import configparser
import pandas as pd
from time import sleep

from RITC.base.OrderBook import ExtendOrderBook, OrderBook
from RITC.datafetcher.ALGODataFetcher import ALGODataFetcher
from RITC.base.ApiTrading import ApiTrading
from RITC.base.NewsBook import TenderBook
from RITC.ALGO.ArbitrageStrategy import ETFArbitrageStrategy
logger = logging.getLogger(__name__)

def load_config() -> dict:
    parser = configparser.ConfigParser()
    parser.read("config.ini")
    config = {
        "convert_fee": float(parser["ALGOTrading"]["convert_fee"]),
        "fee_currency": parser["ALGOTrading"]["fee_currency"],
        "transaction_fee": float(parser["ALGOTrading"]["transaction_fee"]),
        "rebate_fee": float(parser["ALGOTrading"]["rebate_fee"]),
        "slippage_tolerance": float(parser["ALGOTrading"]["slippage_tolerance"]),
        "end_trade_before": int(parser["ALGOTrading"]["end_trade_before"]),
        "arbitrage_order_size": int(parser["ALGOTrading"]["arbitrage_order_size"]),
        "etf_arbitrage_order_size": int(parser["ALGOTrading"]["etf_arbitrage_order_size"]),
        "shock_duration": int(parser["ALGOTrading"]["shock_duration"]),
        "sleep_time": float(parser["ALGOTrading"]["sleep_time"]),
        "conversion_order_size": int(parser["ALGOTrading"]["conversion_order_size"]),
        "cap_gdp": float(parser["ALGOTrading"]["cap_gdp"]),
        "cap_bci": float(parser["ALGOTrading"]["cap_bci"]),
        "floor_gdp": float(parser["ALGOTrading"]["floor_gdp"]),
        "floor_bci": float(parser["ALGOTrading"]["floor_bci"]),
        "ticks_per_period": 1200,
        "strategy1_tender": parser["ALGOTrading"]["strategy1_tender"],
        "strategy2_convertion": parser["ALGOTrading"]["strategy2_convertion"],
        "strategy3_ETF": parser["ALGOTrading"]["strategy3_ETF"],
        "strategy4_profit_loss": parser["ALGOTrading"]["strategy4_profit_loss"],
    }
    return config

def read_parameter(param_file: str) -> dict:
    logger.info("Reading parameters from CSV...")
    df_params = pd.read_csv(param_file, header=0, index_col=0)
    params = dict(zip(df_params.index, df_params['value']))
    logger.info("Downloaded params successfully.")
    return params

# --- Load configuration and parameters ---
config = load_config()
params = read_parameter("tests/params_algotrading.csv")

# --- Initialize order books ---
book_names = ["SAD", "CRY", "ANGER", "FEAR", "JOY_C", "JOY_U"]
books = {name: ExtendOrderBook() for name in book_names}
books["USD"] = OrderBook()
books["CAD"] = OrderBook()

# Set transaction and rebate fees
for name in book_names:
    books[name].set_transaction_fee(config["transaction_fee"])
for name in ["SAD", "CRY", "ANGER", "FEAR"]:
    books[name].set_rebate_fee(config["rebate_fee"])
books["JOY_C"].set_rebate_fee(0)
books["JOY_U"].set_rebate_fee(0)

# Set currency
for name in ["SAD", "CRY", "ANGER", "FEAR", "JOY_C"]:
    books[name].set_currency("cad")
books["JOY_U"].set_currency("usd")

# --- Book dictionary for easy access ---
book_dict = {name: books[name] for name in book_names}

# --- Initialize trading objects ---
data_fetcher = ALGODataFetcher()
data_fetcher.connect()
data_fetcher.get_tick()
book_tender = TenderBook()
strategy_obj = ETFArbitrageStrategy()
strategy_obj.slippage_tolerance = config["slippage_tolerance"]
trading_operator = ApiTrading(data_fetcher)
trading_operator.initialize_portfolio(max_position_usage=0.8)

# --- Strategy and simulation parameters ---
etf_arbitrage_order_size = params.get('etf_arbitrage_order_size', 100)
arbitrage_order_size = params.get('arbitrage_order_size', 100)
transaction_fee = config.get('transaction_fee', 0.001)
conversion_order_size = params.get('conversion_order_size', 100)
ticks_per_period = config.get('ticks_per_period', 100)
end_trade_before = config.get('end_trade_before', 10)
sleep_time = config.get('sleep_time', 0.1)
shock_duration = config.get('shock_duration', 10)
cap_gdp = config.get('cap_gdp', 100)
floor_gdp = config.get('floor_gdp', -100)
cap_bci = config.get('cap_bci', 100)
floor_bci = config.get('floor_bci', -100)
fee_currency = config.get('fee_currency', 'cad')
unhedged_cost = {name: 0.0 for name in book_names}

# Import missing modules
import queue
import keyboard
from time import sleep

# Initialize command queue
command_queue = queue.Queue()



def update_data():
    data_fetcher.update_market_data(
        books["SAD"], books["CRY"], books["ANGER"], books["FEAR"], books["JOY_C"], books["JOY_U"], books["USD"], books["CAD"], book_tender)
    trading_operator.update_all_information()
    # update exchange rate
    trading_operator.bank_account.set_foreign_exchange_rate(
        "CAD", "USD", books["USD"].bid_head.price, books["USD"].ask_head.price)

def hedge_currency():
    # 0. hedge the currency
    usd_ = trading_operator.bank_account.subaccounts["USD"].get_cash()
    usd_action = "sell" if usd_ > 0 else "buy"
    while abs(usd_) > 0:
        actual_execute = trading_operator.place_currency_order("USD", usd_action, abs(usd_))
        if actual_execute == -1:
            print("fail to hedge the currency")
            break
        
        usd_ = abs(usd_) - abs(actual_execute)
            
    usd_value = trading_operator.get_asset_nlv("JOY_U") + trading_operator.bank_account.get_subaccount_cash("USD")

    if usd_value > 1000:
        trading_operator.place_currency_order("USD", "sell", usd_value)
    elif usd_value < -1000:
        trading_operator.place_currency_order("USD", "buy", abs(usd_value))
    else:
        pass # ignore the small amount of currency risk


def print_result():

    print(f"total return of conversion:  \
        {total_profit_in_conversion - total_cost_in_conversion},\
            total cost in conversion: {total_cost_in_conversion},\
                total profit in conversion: {total_profit_in_conversion}")
    print(f"total return of ETF arbitrage:  \
        {total_profit_in_etf_arbitrage - total_cost_in_etf_arbitrage},\
        total cost in ETF arbitrage: {total_cost_in_etf_arbitrage},\
        total profit in ETF arbitrage: {total_profit_in_etf_arbitrage}")
    print(f"total return of tender arbitrage:  \
        {total_profit_in_tender - total_cost_in_tender},\
        total cost in tender arbitrage: {total_cost_in_tender},\
        total profit in tender arbitrage: {total_profit_in_tender}")    

    
def strategy1():
    # 1. accept the tender or reject the tender
    global total_cost_in_tender
    global total_profit_in_tender
    global unhedged_tenders

    if strategy1_tender:
        update_data()
        if data_fetcher.end:
            return 0
        if book_tender.tenders:
            for tender_id in book_tender.tenders:
                if not trading_operator.can_place_order(2):
                    # if the order rate limit is reached, do not accept the tender
                    continue

                tender = book_tender.tenders[tender_id]
                # input tender volumne, and check if it's profitable to accept the tender 
                
                # strategy 1: check the arbitrage opportunity for the same asset
                book_stock = book_dict[tender.ticker]
                usd_bid = books["USD"].best_bid if tender.ticker == "JOY_U" else 1
                usd_ask = books["USD"].best_ask if tender.ticker == "JOY_U" else 1
                
                buy_threshold = params['buy_' + tender.ticker + '_tender_threshold']
                sell_threshold = params['sell_' + tender.ticker + '_tender_threshold']

                signal_tender, profit_tender = \
                      strategy_obj.tender_signal2( tender.action, tender.price,
                                                    tender.volume, book_stock, 
                                                    buy_threshold,
                                                    sell_threshold)
                    
                if signal_tender == 1:
                    print("******activate tender arbitrage strategy******")
                    print(f"accept the tender, ticker: {tender.ticker}, action: {tender.action}, volume: {tender.volume}, price: {tender.price}")
                    # accept the tender
                    order_result_tender = trading_operator.accept_tender_check_limits(tender_id, tender.ticker, 
                                                                tender.volume)
                    if order_result_tender == -1:
                        print("fail to accept the tender")
                    else:
                        action_type = "sell" if tender.action.lower() == "buy" else "buy"
                        # close positions directly
                        if action_type == "sell":
                            total_cost_in_tender += tender.price * tender.volume * usd_ask
                        else:
                            total_profit_in_tender += tender.price * tender.volume * usd_bid

                        perc_ = params['tender_close_percentage_' + tender.ticker]

                        quantity_tobe_filled = tender.volume * perc_
                        total_ = 0
                        fail_time = 0
                        while quantity_tobe_filled > 0:
                            if fail_time > 5:
                                break

                            order_result = trading_operator.place_order(tender.ticker, "market", 
                                                        quantity_tobe_filled,
                                                        action_type,  None)
                            
                            if order_result != -1:
                                total_ += order_result.initial_volume * order_result.vwap
                                quantity_tobe_filled -= order_result.initial_volume
                            else:
                                fail_time += 1
                                continue

                        if quantity_tobe_filled == 0:
                            print(f"liquidate {tender.volume * perc_} shares of \
                                   the stock {tender.ticker} position successfully")
                            
                            if action_type == "buy":
                                total_cost_in_tender += (total_ + transaction_fee * tender.volume * perc_)
                                unhedged_tenders[tender.ticker] -= tender.volume * (1 - perc_)
                                unhedged_cost[tender.ticker] -= tender.volume * (1 - perc_) * tender.price
                            else:
                                total_profit_in_tender += total_
                                total_cost_in_tender += transaction_fee * tender.volume * perc_
                                unhedged_tenders[tender.ticker] += tender.volume * (1 - perc_)
                                unhedged_cost[tender.ticker] += tender.volume * (1 - perc_) * tender.price

                            
                        else:
                            print(f"!!!!!!!!fail to liquidate the stock position, {"sell" if tender.action.lower() == "buy" else "buy"} the \
                                {quantity_tobe_filled} shares of {tender.ticker} position manually") 
                            if action_type == "buy":
                                unhedged_tenders[tender.ticker] -= (tender.volume * (1 - perc_) + quantity_tobe_filled)
                                unhedged_cost[tender.ticker] -= (tender.volume * (1 - perc_) + quantity_tobe_filled) * tender.price
                            else:
                                unhedged_tenders[tender.ticker] += (tender.volume * (1 - perc_) + quantity_tobe_filled)
                                unhedged_cost[tender.ticker] += (tender.volume * (1 - perc_) + quantity_tobe_filled) * tender.price

def strategy2():
    global total_cost_in_conversion
    global total_profit_in_conversion

    # 2. arbitrage based on convertion
    # 2.1 only arbitrage when the strategy is activated

    unhedged_stock_in_conversion = 0
    unhedged_etf_in_conversion = 0
    if strategy2_convertion:
        update_data()
        if data_fetcher.end:
            return 0
        
        if ticks_per_period - data_fetcher.current_tick > 50:

            if not trading_operator.can_place_order(5):
                # if can't liquid ETF and stocks, do not arbitrage
                return 0
            
            # 2.2 conversion may not be profitable if the position of ETF needed to be converted is too large, stop checking the conversion
            if (abs(trading_operator.assets["JOY_C"].volume) <= conversion_order_size * params['conversion_tolerance']) \
                and (abs(trading_operator.assets["CRY"].volume) <= conversion_order_size * params['conversion_tolerance']) \
                and (abs(trading_operator.assets["SAD"].volume) <= conversion_order_size * params['conversion_tolerance']) \
                and (abs(trading_operator.assets["ANGER"].volume) <= conversion_order_size * params['conversion_tolerance']) \
                and (abs(trading_operator.assets["FEAR"].volume) <= conversion_order_size * params['conversion_tolerance']):
                
                # 2.3 check the arbitrage opportunity for conversion joy_c
        
                signal_convert1, order_info_convert1 = strategy_obj.generate_convert_signal(
                    {"SAD": books["SAD"], "CRY": books["CRY"], "ANGER": books["ANGER"], "FEAR": books["FEAR"]},
                    {"SAD": 1, "CRY": 1, "ANGER": 1, "FEAR": 1},
                    books["JOY_C"],
                    arbitrage_order_size,
                    0, fee_currency,
                    trading_operator.bank_account,
                    price_shift=0,
                    create_threshold=params['create_JOY_C_threshold_shortc'],
                    redeem_threshold=params['redeem_JOY_C_threshold_longc'],
                )

                if signal_convert1 == -1:
                    # redeem ETF and buy ETF now
                    unhedged_etf_in_conversion += conversion_order_size
                    unhedged_stock_in_conversion -= conversion_order_size
                elif signal_convert1 == 1:
                    # create ETF and sell ETF now
                    unhedged_etf_in_conversion -= conversion_order_size
                    unhedged_stock_in_conversion += conversion_order_size
                else:
                    pass
                # convert the stocks to ETF and close out ETF
                # first, check the limits.
                if unhedged_etf_in_conversion != 0:
                    asset_quantity = {}
                    for stock in order_info_convert1:
                        if stock["ticker"] != "ETF":
                            asset_quantity[stock["ticker"]] = stock["quantity"]
                        else:
                            asset_quantity["JOY_C"] = unhedged_etf_in_conversion
                        
                    exceed_limit = trading_operator.check_bulk_limits(asset_quantity)
                    if not exceed_limit:
                        print("******activate convert arbitrage strategy******")
                        joyc_action = "sell" if unhedged_etf_in_conversion < 0 else "buy"
                        order_result1 = trading_operator.place_order("JOY_C", "market", abs(unhedged_etf_in_conversion), joyc_action, None)
                        
                        if joyc_action == "buy":
                            total_cost_in_conversion += order_result1.initial_volume * order_result1.vwap + transaction_fee * abs(order_result1.volume)
                        else:
                            total_profit_in_conversion += order_result1.initial_volume * order_result1.vwap
                            total_cost_in_conversion += transaction_fee * abs(order_result1.volume)

                        stock_action = "sell" if joyc_action == "buy" else "buy"
                        for stock in order_info_convert1:
                            if stock["ticker"] != "ETF":
                                order_result = trading_operator.place_order(stock["ticker"], stock["order_type"], 
                                stock["quantity"], stock_action, stock["price"])

                                if order_result == -1:
                                    print(f"!!!!!!fail to place order for {stock['ticker']}, \
                                        try to {stock_action} {stock["quantity"]} manually!!!!!!")
                                else:
                                    if stock_action == "buy":
                                        total_cost_in_conversion += order_result.initial_volume * order_result.vwap + transaction_fee * abs(order_result.volume) 
                                    else:
                                        total_profit_in_conversion += order_result.initial_volume * order_result.vwap
                                        total_cost_in_conversion += transaction_fee * abs(order_result.volume) 
                        if order_result1 != -1:
                            
                            if unhedged_etf_in_conversion < 0:
                                print(f"!!!!!! convert stocks to {unhedged_etf_in_conversion} shares JOY_C !!!!!!")
                            elif unhedged_etf_in_conversion > 0:
                                print(f"!!!!!! redeem {abs(unhedged_etf_in_conversion)} of JOY_C !!!!!!")
                            else:
                                pass
                        else:
                            print(f"fail to build JOYC position, {unhedged_etf_in_conversion} shares of JOYC position should be built manually")
                
def strategy3():
    
    global total_profit_in_etf_arbitrage
    global total_cost_in_etf_arbitrage
    global unhedged_initial_value_etf
    global unhedged_etf_in_arbitrage
    # 3. arbitrage between ETFs

    if strategy3_ETF:
        update_data()
        if data_fetcher.end:
            return 0
        if trading_operator.can_place_order(2):
            # if can't liquid ETF and stocks, do not arbitrage
            longc_multiplier = params['etf_position_multiplier_longc']
            shortc_multiplier = params['etf_position_multiplier_shortc']
            longc_threshold = params['etf_deviation_threshold_longc']
            shortc_threshold = params['etf_deviation_threshold_shortc']
            if (trading_operator.assets["JOY_C"].volume < etf_arbitrage_order_size * (longc_multiplier - 1) and \
                trading_operator.assets["JOY_C"].volume > (- etf_arbitrage_order_size * (shortc_multiplier - 1))) or \
                (trading_operator.assets["JOY_U"].volume < etf_arbitrage_order_size * (shortc_multiplier - 1) and\
                    trading_operator.assets["JOY_U"].volume > (- etf_arbitrage_order_size * (longc_multiplier - 1))):

                signal_etf, order_info = strategy_obj.generate_etf_signal(
                    books["JOY_C"], books["JOY_U"], trading_operator.bank_account,
                    etf_arbitrage_order_size, longc_threshold, shortc_threshold)
                
                if signal_etf == 1:
                    # buy joyc and sell joyu
                    print(f"******activate ETF arbitrage strategy: buy joyc and sell joyu for {etf_arbitrage_order_size}shares******")
                    
                    order_1 = trading_operator.place_order("JOY_C", "market", etf_arbitrage_order_size, "buy", None)
                    order_2 = trading_operator.place_order("JOY_U", "market", etf_arbitrage_order_size, "sell", None)

                    if order_1 != -1 and order_2 != -1:
                        total_cost_in_etf_arbitrage += order_1.initial_volume * order_1.vwap + transaction_fee * (order_1.initial_volume + order_2.initial_volume)
                        total_profit_in_etf_arbitrage += (order_2.initial_volume * order_2.vwap * books["USD"].best_bid)
                        unhedged_initial_value_etf += (- order_1.initial_volume * order_1.vwap + order_2.initial_volume * order_2.vwap * books["USD"].best_bid)
                    else:
                        print("...fail to activate ETF arbitrage strategy: buy joyc and sell joyu...")
                        if order_1 != -1:
                            trading_operator.place_order("JOY_C", "market", etf_arbitrage_order_size, "sell", None)
                        if order_2 == -1:
                            trading_operator.place_order("JOY_U", "market", etf_arbitrage_order_size, "buy", None)

                elif signal_etf == -1:
                    # sell joyc and buy joyu
                    print(f"******activate ETF arbitrage strategy: sell joyc and buy joyu for {etf_arbitrage_order_size}shares******")
                    order_1 = trading_operator.place_order("JOY_C", "market", etf_arbitrage_order_size, "sell", None)
                    order_2 = trading_operator.place_order("JOY_U", "market", etf_arbitrage_order_size, "buy", None)

                    if order_1 != -1 and order_2 != -1:

                        total_profit_in_etf_arbitrage += order_1.initial_volume * order_1.vwap 
                        total_cost_in_etf_arbitrage += order_2.initial_volume * order_2.vwap * books["USD"].best_ask + transaction_fee * (order_1.initial_volume + order_2.initial_volume)
                        unhedged_initial_value_etf += (order_1.initial_volume * order_1.vwap - order_2.initial_volume * order_2.vwap * books["USD"].best_ask)
                    else:
                        print("fail to activate ETF arbitrage strategy: sell joyc and buy joyu")
                        if order_1 != -1:
                            trading_operator.place_order("JOY_C", "market", etf_arbitrage_order_size, "buy", None)
                        if order_2 == -1:
                            trading_operator.place_order("JOY_U", "market", etf_arbitrage_order_size, "sell", None)

                else:
                    pass
                
    update_data()
    unhedged_etf_in_arbitrage =  -(trading_operator.assets["JOY_U"].volume)
    if abs(unhedged_etf_in_arbitrage) > 0:
        etfclose = False
    else:
        etfclose = True 
    # 3.2 liquidiate the ETF position after the arbitrage. won't be influenced by the activation of the strategy
    if not etfclose:
        update_data()
        current_value_c = unhedged_etf_in_arbitrage * books["JOY_C"].best_bid if unhedged_etf_in_arbitrage > 0 else unhedged_etf_in_arbitrage * books["JOY_C"].best_ask
        current_value_u = trading_operator.assets["JOY_U"].volume * books["JOY_U"].best_bid if trading_operator.assets["JOY_U"].volume > 0 else trading_operator.assets["JOY_U"].volume * books["JOY_U"].best_ask

        if current_value_u > 0:
            current_value_u_cad = books["USD"].best_bid * current_value_u
        else:
            current_value_u_cad = books["USD"].best_ask * current_value_u
        
        current_value = current_value_c + current_value_u_cad
        # print("JOY_C", current_value_c)
        # print("JOY_U", current_value_u_cad)
    
        return_ = (current_value - unhedged_initial_value_etf) / abs(unhedged_etf_in_arbitrage)
        print("return", return_)
        if  return_ > params['take_profit_line_etf']:
            print(f"ETF arbitrage portfolio take profit")
            etfclose = True
        elif return_ < params['stop_loss_line_etf'] * (-1):

            print(f"ETF arbitrage portfolio stop loss")
            etfclose = True

        else:
            pass

        if etfclose:

            if unhedged_etf_in_arbitrage > 0:
                result1 = trading_operator.place_order("JOY_C", "market", unhedged_etf_in_arbitrage, "sell", None)
                result2 = trading_operator.place_order("JOY_U", "market", unhedged_etf_in_arbitrage, "buy", None)
                total_profit_in_etf_arbitrage = result1.initial_volume * result1.vwap
                total_cost_in_etf_arbitrage = result2.initial_volume * result2.vwap * books["USD"].best_ask + transaction_fee * (result1.initial_volume + result2.initial_volume)
            else:
                result1 = trading_operator.place_order("JOY_C", "market", abs(unhedged_etf_in_arbitrage), "buy", None)
                result2 = trading_operator.place_order("JOY_U", "market", abs(unhedged_etf_in_arbitrage), "sell", None)
                total_profit_in_etf_arbitrage = result2.initial_volume * result2.vwap * books["USD"].best_bid
                total_cost_in_etf_arbitrage = result1.initial_volume * result1.vwap + transaction_fee * (result1.initial_volume + result2.initial_volume)
            if result1 != -1 and result2 != -1:
                print("liquidate the ETF position after the arbitrage")
            else:
                print("fail to liquidate the ETF position after the arbitrage")
                if result1 == -1:
                    print("fail to liquidate JOY_C position in ETF arbitrage")
                
                if result2 == -1:
                    print("fail to liquidate JOY_U position in ETF arbitrage")
            unhedged_initial_value_etf = 0



def strategy4():
    # 4. take profit and stop loss
    global total_cost_in_tender
    global total_profit_in_tender
    global unhedged_tenders

    if strategy4_profit_loss:
        update_data()
        if data_fetcher.end:
            return 0

        for asset in unhedged_tenders:
            tender_left = unhedged_tenders[asset]
            tender_cost = unhedged_cost[asset]
            if tender_left == 0:
                continue

            take_profit_line = params['take_profit_line_' + asset]
            stop_loss_line = params['stop_loss_line_' + asset]
            book_ = book_dict[asset]
            if tender_cost != 0:
                if tender_left > 0:
                    return_rate = (tender_left * book_.best_bid - tender_cost) / tender_cost
                else:
                    return_rate = (tender_left * book_.best_ask - tender_cost) / abs(tender_cost)
            # print(f"return rate of {asset}: {return_rate}")
            if  return_rate > take_profit_line or return_rate < stop_loss_line * (-1):
                action_ = 'sell' if tender_left > 0 else 'buy'
                order_result = trading_operator.place_order(asset, "market", abs(tender_left), action_, None)
                if tender_left > 0:
                    usd_ = books["USD"].best_bid if asset == "JOY_U" else 1
                    total_profit_in_tender += order_result.initial_volume * order_result.vwap * usd_
                    total_cost_in_tender += transaction_fee * order_result.initial_volume
                else:
                    usd_ = books["USD"].best_ask if asset == "JOY_U" else 1
                    total_cost_in_tender += order_result.initial_volume * order_result.vwap * usd_ + transaction_fee * order_result.initial_volume

                if return_rate > take_profit_line:
                    print(f"{asset} take profit")
                else:
                    print(f"{asset} stop loss")
                unhedged_tenders[asset] = 0

            else:
                pass


def auto_trading():
    global shock_end_tick_bci
    global shock_end_tick_gdp
    global total_cost_in_conversion
    global total_cost_in_etf_arbitrage

    data_fetcher.get_tick()
    
    if data_fetcher.end:
        return 0 
    print("start auto trading")
    while data_fetcher.current_tick < ticks_per_period - end_trade_before:

        if pausing: # if pausing, do not automatically trade. manually input resume to restart
            sleep(sleep_time)
            continue
            
        if not trading_operator.can_place_order(1):
            # if the order rate limit is reached, wait for a while
            sleep(sleep_time)
            continue

        # 0.2 shock and news influence
        if shock_end_tick_gdp < shock_start_tick_gdp and data_fetcher.current_tick - shock_start_tick_gdp > shock_duration:
            if shock_gdp > cap_gdp:
                print(f"!!!!!positive gdp shock {shock_gdp}")
            elif shock_gdp < floor_gdp * (-1):
                print(f"!!!!!negative gdp shock {shock_gdp}")
            
        if shock_end_tick_bci < shock_start_tick_bci and data_fetcher.current_tick - shock_start_tick_bci > shock_duration:
            if shock_bci > cap_bci:
                print(f"!!!!!positive bci shock {shock_bci}")
            elif shock_bci < floor_bci * (-1):
                print(f"!!!!!negative bci shock {shock_bci}")


        # 1. accept the tender or reject the tender

        strategy1()

        # 2. arbitrage based on convertion
        strategy2()

        # 3. arbitrage between ETFs
        strategy3()

        # 4. take profit and stop loss
        strategy4()
        
        trading_operator.update_position()
        usd_ = trading_operator.bank_account.subaccounts["USD"].get_cash()
        usd_action = "sell" if usd_ > 0 else "buy"
        while abs(usd_) > 0:
            actual_execute = trading_operator.place_currency_order("USD", usd_action, abs(usd_))
            if actual_execute == -1:
                print("fail to hedge the currency")
                break
            
            usd_ = abs(usd_) - abs(actual_execute)
        sleep(sleep_time)

        

    ## close all the positions before the end of the case
    for asset in trading_operator.assets:
        trading_operator.close_position(asset)


def listen_for_commands():

    """ Wait for spacebar press before accepting user input """
    global pausing
    while True:
        keyboard.wait("esc")  # Wait until spacebar is pressed
        
        # Clear any old commands before accepting new input
        with command_queue.mutex:
            command_queue.queue.clear()
        
        command = input("\nEnter command: ").strip().lower()
        command_queue.put(command)

def process_commands():
    """ Process commands from the queue and modify trading behavior """

    global pausing
    global last_GDP_Q1
    global last_GDP_Q2
    global last_GDP_Q3
    global last_GDP_Q4
    global last_BCI
    global shock_bci
    global shock_gdp
    global GDP_Q1
    global GDP_Q2
    global GDP_Q3
    global GDP_Q4
    global BCI
    global shock_start_tick_gdp
    global shock_start_tick_bci
    global strategy1_tender
    global strategy2_convertion
    global strategy3_ETF
    global strategy4_profit_loss


    while True:
        if not command_queue.empty():
            command = command_queue.get()
            try:
                if command == "p":
                    pausing = True
                    print("\nTrading PAUSED. Press SPACE to enter 'resume'.")
                elif command == "r":
                    pausing = False
                    print("\nTrading RESUMED.")
                
                elif command == "b" or command == "s":
                    action = command.lower()
                    ticker = input("Enter ticker jc - JOY_C, ju - JOYU, s - SAD, c - CRY, a - ANGER, f - FEAR").strip().lower()
                    ticker_dict = {"jc": "JOY_C", "ju": "JOY_U", "s": "SAD", "c": "CRY", "a": "ANGER", "f": "FEAR"}
                    ticker = ticker_dict[ticker]
                    action = "buy" if action == "b" else "sell"
                    try:

                        quantity = int(input("Enter quantity: ").strip())
                        type = input("Enter order type l or m (limit/market): ").strip().lower()
                        
                        if type == "l":
                            price = float(input("Enter price: ").strip())
                            order_result = trading_operator.place_order(ticker, "limit", quantity, action, price)
                        elif type == "m":
                            order_result = trading_operator.place_order(ticker, "market", quantity, action, 0)
                        else:
                            print("\nInvalid order type. Use 'l' as 'limit' or 'm' as 'market'. ")

                        if order_result == -1:
                            print("\nFailed to place manual order.")
                        else:
                            print(f"\nPlacing manual order: {ticker} ({quantity} shares).")

                    except ValueError:
                        print("\nInvalid input. Please check your values and try again.")

                elif command == "ct":
                    indicator = input("\nCorrect b - BCI or g - GDP? ").strip().lower()
                        
                    if indicator == "b":
                        value = float(input(f"Enter new {indicator.upper()} value: ").strip())
                        BCI = value
                        shock_bci = BCI / last_BCI - 1 if last_BCI != 0 else 0
                        
                        print(f"\nBCI corrected to {BCI}.")
                        print(f"\nShock of BCI: {shock_bci}.")

                    elif indicator == "g":
                        quarter = input("Enter new quarter(1,2,3,4): ").strip()
                        if quarter not in ["1", "2", "3", "4"]:
                            print("\nInvalid quarter. Please enter a valid quarter.")
                        
                        else:
                            if quarter == "1":
                                value = float(input(f"Enter new {indicator.upper()} value for Q1: ").strip())
                                GDP_Q1 = value
                                shock_gdp = GDP_Q1 - last_GDP_Q1
                            elif quarter == "2":
                                value = float(input(f"Enter new {indicator.upper()} value for Q2: ").strip())
                                GDP_Q2 = value
                                shock_gdp = GDP_Q2 - last_GDP_Q2
                            elif quarter == "3":
                                value = float(input(f"Enter new {indicator.upper()} value for Q3: ").strip())
                                GDP_Q3 = value
                                shock_gdp = GDP_Q3 - last_GDP_Q3
                            elif quarter == "4":
                                value = float(input(f"Enter new {indicator.upper()} value for Q4: ").strip())
                                GDP_Q4 = value
                                shock_gdp = GDP_Q4 - last_GDP_Q4
                            shock_gdp /= 100
                            
                            print(f"\nGDP corrected to {value}.")
                            print(f"\nShock of GDP: {shock_gdp}.")

                    else:
                        print("\nInvalid input. Please enter 'BCI' or 'GDP' or input 'bk' to cancel.")
                        
                elif command == "n":
                    # input GDP and BCI updates into a single command
                    news_type = input("\nUpdate g - gdp or b - bci? ").strip().lower()

                    if news_type in ["g", "b"]:

                        value = float(input(f"Enter new {news_type.upper()} value: ").strip())
                        
                        if news_type == "g":
                            quarter = input("Enter new quarter(1,2,3,4): ").strip() 
                            if quarter not in ["1", "2", "3", "4"]:
                                print("\nInvalid quarter. Please enter a valid quarter.")
                                
                            else:

                                if quarter == "1":
                                    last_GDP_Q1 = GDP_Q1
                                    GDP_Q1 = value
                                    last_GDP_Q1 = value if last_GDP_Q1 == 0 else last_GDP_Q1
                                    shock_gdp = GDP_Q1 - last_GDP_Q1
                                    
                                elif quarter == "2":
                                    last_GDP_Q2 = GDP_Q2
                                    GDP_Q2 = value
                                    last_GDP_Q2 = value if last_GDP_Q2 == 0 else last_GDP_Q2
                                    shock_gdp = GDP_Q2 - last_GDP_Q2
                                elif quarter == "3":
                                    last_GDP_Q3 = GDP_Q3
                                    GDP_Q3 = value
                                    last_GDP_Q3 = value if last_GDP_Q3 == 0 else last_GDP_Q3
                                    shock_gdp = GDP_Q3 - last_GDP_Q3
                                elif quarter == "4":
                                    last_GDP_Q4 = GDP_Q4
                                    GDP_Q4 = value
                                    last_GDP_Q4 = value if last_GDP_Q4 == 0 else last_GDP_Q4
                                    shock_gdp = GDP_Q4 - last_GDP_Q4

                                shock_start_tick_gdp = data_fetcher.current_tick
                                shock_gdp = shock_gdp / 100
                            
                            print(f"\nGDP updated to {value}.")
                            print(f"\nShock of GDP: {shock_gdp}.")

                        elif news_type == "b":  # news_type == "bci"
                            last_BCI = BCI
                            BCI = value
                            last_BCI = value if last_BCI == 0 else last_BCI
                            shock_start_tick_bci = data_fetcher.current_tick
                            shock_bci = BCI / last_BCI - 1 if last_BCI != 0 else 0
                            print(f"\nBCI updated to {BCI}.")
                            print(f"\nShock of BCI: {shock_bci}.")
                        
                        else:
                            print("\nInvalid selection. Please enter 'GDP' or 'BCI'. or input back to cancel.")

                
                elif command == "bk":
                    print("\n recall command")
                
                elif command == "c":
                    asset = input("Enter asset to close jc - JOY_C, ju - JOYU, s - SAD, c - CRY, a - ANGER, f - FEAR: ").strip().lower()
                    
                    if asset == 'jc':
                        asset = "JOY_C"
                    elif asset == 'ju':
                        asset = "JOY_U"
                    elif asset == 's':
                        asset = "SAD"
                    elif asset == 'c':
                        asset = "CRY"
                    elif asset == 'a':
                        asset = "ANGER"
                    elif asset == 'f':
                        asset = "FEAR"
                    else:
                        print("\nInvalid asset. Please enter a valid asset.")

                    trading_operator.close_position(asset)
                    print(f"\nClose the position of {asset}.")

                elif command == "s1":
                    strategy1_tender = False
                    print("\nStop using strategy 1.")
                elif command == "s2":
                    strategy2_convertion = False
                    print("\nStop using strategy 2.")
                elif command == "s3":
                    strategy3_ETF = False
                    print("\nStop using strategy 3.")
                elif command == "s4":
                    strategy4_profit_loss = False
                    print("\nStop using strategy 4.")
                
                elif command == "r1":
                    strategy1_tender = True
                    print("\nResume using strategy 1.")
                elif command == "r2":
                    strategy2_convertion = True
                    print("\nResume using strategy 2.")
                elif command == "r3":
                    strategy3_ETF = True
                    print("\nResume using strategy 3.")
                elif command == "r4":
                    strategy4_profit_loss = True
                    print("\nResume using strategy 4.")

                elif command == "q":
                    # calculate the fair price of JOY_U based on the price of JOY_C and currency exchange rate
                    fair_price = trading_operator.bank_account.currency_value_conversion(
                        "CAD", "USD", (books["JOY_C"].bid_head.price + books["JOY_C"].ask_head.price) / 2)
                    print("the fair price of JOY_U is: ", fair_price)
 
                elif command == "fc": 
                    asset = input("fast close 1 - JOY_C and JOY_U, 2 - SAD, CRY, ANGER, FEAR: ").strip().lower()
                    if asset == "1":
                        unhedged_etf_in_arbitrage = (-trading_operator.assets["JOY_U"].volume)
                        if unhedged_etf_in_arbitrage > 0:
                            trading_operator.place_order("JOY_C", "market", unhedged_etf_in_arbitrage, "sell", None)
                            trading_operator.place_order("JOY_U", "market", unhedged_etf_in_arbitrage, "buy", None)
                        else:
                            trading_operator.place_order("JOY_C", "market", abs(unhedged_etf_in_arbitrage), "buy", None)
                            trading_operator.place_order("JOY_U", "market", abs(unhedged_etf_in_arbitrage), "sell", None)
                    
                    elif asset == "2":

                        volumes = [int(trading_operator.assets['SAD'].volume), int(trading_operator.assets['CRY'].volume),
                                int(trading_operator.assets['ANGER'].volume), int(trading_operator.assets['FEAR'].volume)]
                        most_common = max(set(volumes), key=volumes.count)
                        unhedged_stock_in_conversion = most_common
                        stock_action = "sell" if unhedged_stock_in_conversion > 0 else "buy"
                        for stock in ["SAD", "CRY", "ANGER", "FEAR"]:
                            if abs(unhedged_stock_in_conversion) > 0:
                                order_result = trading_operator.place_order(stock, "market", abs(unhedged_stock_in_conversion), stock_action, None)
                        if stock_action == "sell":
                            trading_operator.place_order("JOY_C", "market", abs(unhedged_stock_in_conversion), "buy", None)
                        else:
                            trading_operator.place_order("JOY_C", "market", abs(unhedged_stock_in_conversion), "sell", None)
                    else:
                        print("invalid asset")
                
                elif command == "fo":
                    index_ = input("Enter the strategy to open positions: 1 - buy JOY_C sell JOY_U, 2 - sell JOY_C buy JOY_U ").strip()
                    if index_ == "1":
                        trading_operator.place_order("JOY_C", "market", 10000, "buy", None)
                        trading_operator.place_order("JOY_U", "market", 10000, "sell", None)
                    elif index_ == "2":
                        trading_operator.place_order("JOY_C", "market", 10000, "sell", None)
                        trading_operator.place_order("JOY_U", "market", 10000, "buy", None)

                elif command == 'fb':
                        # buy 10000 shares of JOY_C
                        trading_operator.place_order("JOY_C", "market", 10000, "buy", None)
                elif command == 'fs':
                    trading_operator.place_order("JOY_C", "market", 10000, "sell", None)


                else:
                    print("\nInvalid command. ")
            except Exception as e:
                print(e)


def main():
    
    if not data_fetcher.end:
        input_thread = threading.Thread(target=listen_for_commands, daemon=True)
        input_thread.start()

        command_thread = threading.Thread(target=process_commands, daemon=True)
        command_thread.start()

        read_parameter()
        auto_trading()
        
        print_result()
    else:
        print("The case is ended.")

data_fetcher.close()






