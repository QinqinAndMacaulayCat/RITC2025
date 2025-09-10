
"""
ArbitrageStrategy Module


This module implements ETF arbitrage strategies for financial trading, including:
- Generating signals for ETF tender acceptance/rejection
- Creating/redeeming ETFs based on basket securities
- Calculating conversion profits between ETFs and baskets
- Arbitraging between two ETFs

"""

from RITC.base.OrderBook import OrderBook
from typing import Dict
from RITC.base.ApiTrading import BankAccountOperationApi
from RITC.base.NewsBook import Tender

class ETFArbitrageStrategy:

    def __init__(self):
        """
        Initializes the ETFArbitrageStrategy instance.
        """
        self.signals = []


    def generate_tender_signal(self, tender_book: Tender,
                               stock_data: Dict[str, OrderBook],
                               weights: Dict[str, float],
                               etf_data: OrderBook, quantity: int,
                               convert_fee: float = 0., fee_currency="CAD",
                               bank_account: BankAccountOperationApi = None,
                               volatilities: Dict[str, float] = None):
        """
        Generate the signal to accept or reject a tender for ETF by checking the convertion profit.

        todo: add the GDP and BCI growth rate to the function

        return: 1 - accept, 0 - reject
        """

        if tender_book.ticker not in ["JOY_U", "JOY_C"]:
            return 0, []

        myaction = "sell" if tender_book.action.lower() == "buy" else "buy"
        profit_info = self.calculate_converter_profit(
            stock_data, weights, etf_data, tender_book.volume,
            convert_fee, fee_currency, myaction, bank_account,
            tender_book.price, volatilities)
        profit = profit_info["profit"]
        signal = 0
        if profit > 0 and profit_info["profit"] / quantity > getattr(self, "deviation_threshold_low", 0):
            signal = 1

        return signal, profit_info["order"]
            
    
    def generate_convert_signal(self, stock_data: Dict[str, OrderBook],
                               weights: Dict[str, float],
                               etf_data: OrderBook, quantity: int,
                               convert_fee: float = 0., fee_currency="CAD",
                               bank_account: BankAccountOperationApi = None,
                               price_shift: float = 0.,
                               create_threshold=100, redeem_threshold=100):
  
        """
        generate the signal to create or redeem the ETF.

        :param stock_data: Dictionary of .
        :param weights: Dictionary of {security: weight} pairs. share of each security needed to create the ETF.
        :param quantity: the number of ETFs to be created or redeemed.
        :param transaction_fee: the fee for each transaction
        :param convert_fee: the percentage fee for converting the assets
        :param bank_account: BankAccountOperationApi object. used to convert cost or profit to cad
        :param price_shift: added to the price of the ETF , which is GDP or BCI growth rate
        :return:
                signal: 1 - create ETF, -1 - redeem ETF, 0 - no action
                Fundamental value as a weighted average of the basket prices. 
        """

        create_ETF_profit = self.calculate_converter_profit(
            stock_data, weights, etf_data, quantity, convert_fee,
            fee_currency, "buy", bank_account, None)
        redeem_ETF_profit = self.calculate_converter_profit(
            stock_data, weights, etf_data, quantity, convert_fee,
            fee_currency, "sell", bank_account, None)

        signal = 0
        if create_ETF_profit["profit"] > 0 and (create_ETF_profit["profit"] / quantity + price_shift > create_threshold):
            signal = 1

        signal2 = 0
        if redeem_ETF_profit["profit"] > 0 and (redeem_ETF_profit["profit"] / quantity - price_shift > redeem_threshold):
            signal2 = -1

        if create_threshold > redeem_threshold:
            return signal, create_ETF_profit["order"]
        else:
            return signal2, redeem_ETF_profit["order"]


    def calculate_converter_profit(self, stock_data: Dict[str, OrderBook],
                                   weights: Dict[str, float],
                                   etf_data: OrderBook,
                                   quantity: int,
                                   convert_fee: float, fee_currency="CAD",
                                   action: str = "buy",
                                   bank_account: BankAccountOperationApi = None,
                                   etf_price=None):
        """
        Calculate the profit of converting a basket of securities to an ETF or vice versa.
        
        :param stock_data: Dictionary of {security: OrderBook} pairs.
        :param weights: Dictionary of {security: weight} pairs.
        :param etf_data: OrderBook of the ETF.
        :param quantity: Number of units to trade.
        :param convert_fee: Fee for converting the basket of securities to the ETF or vice versa.
        :param action: "buy" or "sell" the ETF. means create or redeem the ETF
        :param bank_account: BankAccountOperationApi object. used to convert cost or profit to cad
        :param etf_price: the bid or ask price of the ETF. If not provided, the price will be calculated based on the order book.
        :return: Profit of the conversion and the order details
        """

        return_dict = {"profit": 0, "order": []}
        stock_value = 0
        for stock in stock_data:
            if stock not in weights:
                raise ValueError(f"Stock weight not provided for {stock}")
            result = stock_data[stock].limit_order_assistant(quantity, action, getattr(self, "slippage_tolerance", 0))
            number = stock_data[stock].calculate_total_profit(quantity * weights[stock], result["order_type"], action, result["price"])
            if action == "buy":
                number_cad = bank_account.currency_value_conversion_targetamount("CAD", stock_data[stock].currency, number)
            else:
                number_cad = bank_account.currency_value_conversion(stock_data[stock].currency, "CAD", number)
            stock_value += number_cad
            return_dict["order"].append({
                "ticker": stock,
                "order_type": result["order_type"],
                "price": result["price"],
                "quantity": weights[stock] * quantity,
                "value": number,
                "value_cad": number_cad
            })

        etf_action = "buy" if action == "sell" else "sell"
        if etf_price is None:
            result_etf = etf_data.limit_order_assistant(quantity, etf_action, getattr(self, "slippage_tolerance", 0))
            etf_value = etf_data.calculate_total_profit(quantity, result_etf["order_type"], etf_action, result_etf["price"])
        else:
            result_etf = {"order_type": "limit", "price": etf_price}
            etf_value = etf_price * quantity

        if etf_action == "sell":
            etf_value_cad = bank_account.currency_value_conversion(etf_data.currency, "CAD", etf_value)
        else:
            etf_value_cad = bank_account.currency_value_conversion_targetamount("CAD", etf_data.currency, etf_value)
        return_dict["order"].append({
            "ticker": "ETF",
            "order_type": result_etf["order_type"],
            "price": result_etf["price"],
            "quantity": quantity,
            "value": etf_value,
            "value_cad": etf_value_cad
        })

        convert_fee_cad = bank_account.currency_value_conversion_targetamount("CAD", fee_currency, convert_fee)

        if action == "buy":
            return_dict["profit"] = etf_value_cad - stock_value - quantity * convert_fee_cad
        else:
            return_dict["profit"] = stock_value - etf_value_cad - quantity * convert_fee_cad

        return return_dict
        

    def tender_signal2(self, tender_action, tender_price, tender_volume,
                       order_book: OrderBook, buy_threshold=100, sell_threshold=100):
        """
        Generate the signal to accept or reject a tender based on the tender price and nlv
        

        """
        # sell tender equal to buy for us and should be sold after accepting tendors
        tender_action = tender_action.lower()
        myaction = "buy" if tender_action == "sell" else "sell"
        vwap = order_book.calculate_vwap_market_price(tender_volume, myaction,
                                                              True)
        if tender_action == "buy":
            profit = tender_price - vwap
            if profit > buy_threshold:
                return 1, profit
        else:
            profit = vwap - tender_price
            if profit > sell_threshold:
                return 1, profit

        return 0, 0


    def generate_etf_signal(self, book_joyc: OrderBook, book_joyu: OrderBook, 
                            bank_account: BankAccountOperationApi, 
                            quantity: int, 
                            profit_threshold_buyc=100, profit_threshold_sellc=100,):
        """
        Generate the signal to arbitrage between two ETFs.
        """

        # the profit of buying etf1 and selling etf2
        # use market price as there is no rebase from ETF
        cost1 = book_joyc.calculate_total_profit(quantity, "market", "buy", None)
        profit1 = book_joyu.calculate_total_profit(quantity, "market", "sell", None)
        
        cost1_cad = bank_account.currency_value_conversion(book_joyc.currency, "CAD", cost1)
        profit1_cad = bank_account.currency_value_conversion(book_joyu.currency, "CAD", profit1)

        return1 = profit1_cad - cost1_cad

        signal1 = 0
        if return1 > profit_threshold_buyc:
            signal1 = 1

        # the profit of buying etf2 and selling etf1
        cost2 = book_joyu.calculate_total_profit(quantity, "market", "buy", None)
        profit2 = book_joyc.calculate_total_profit(quantity, "market", "sell", None)
        
        cost2_cad = bank_account.currency_value_conversion(book_joyu.currency, "CAD", cost2)
        profit2_cad = bank_account.currency_value_conversion(book_joyc.currency, "CAD", profit2)

        return2 = profit2_cad - cost2_cad

        signal2 = 0
        if return2 > profit_threshold_sellc:
            signal2 = -1
        
        if signal2 == -1 and signal1 == 1:
            print("conflict signals in ETF trading")
            return 0
        else:
            if signal1 != 0:
                return 1, return1
            elif signal2 != 0:
                return -1, return2
            else:
                return 0, 0


        
        

