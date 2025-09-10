"""
This module provides classes for managing a portfolio of financial assets, tracking transactions, and calculating key metrics such as profit, drawdown, and position limits. It supports multi-currency cash accounts, asset-level and portfolio-level risk controls, and conversion between currencies using exchange rates. Main classes include CashAccount, BankAccount (abstract base class), Asset, and Portfolio. Features include multi-currency support, asset and portfolio position limits, realized and unrealized profit calculation, drawdown and portfolio value tracking, and logging for error and info messages. Author: DQ. Date: 2025-01-03.
"""
from typing import Dict, Optional
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class CashAccount:
    def __init__(self, currency: str, cash: float, credit: float = float("inf"), is_tradeable: bool = True) -> None:
        """
        Initializes a new cash account.
        
        :param currency: Currency of the account.
        :param cash: Initial cash balance.
        :param credit: Credit limit for the account. The account can go negative up to the credit limit.
        """

        self.cash = cash
        self.initial_cash = cash
        self.currency = currency.upper()
        self.credit = credit # credit limit for the account. The account can go negative up to the credit limit.

        self.net_limit = float('inf')
        self.gross_limit = float('inf')
        self.limit_name = None

        self.is_strict = False

        self.transactions = []
        self.maximum_transaction_size = float('inf')
        self.is_tradeable = is_tradeable
        
    
    def set_maximum_transaction_size(self, size: float) -> None:
        """
        The maximum transaction size for a single transaction.

        :param size: Maximum transaction size.
        """
        self.maximum_transaction_size = size
    
    def get_cash(self) -> float:
        """
        Returns the cash balance for the account.

        :return: Cash balance.
        """
        return self.cash


    def set_limits(self, gross_limit: float, net_limit: float, is_strict=False, limit_name=None) -> None:
        """
        Sets the position limits for single cash account. (optional, there may be no limits for single cash account)

        :param gross_limit: Gross position limit for the cash account.
        :param net_limit: Net position limit for the cash account.
        """
        self.gross_limit = gross_limit
        self.net_limit = net_limit
        self.is_strict = is_strict
        self.limit_name = limit_name

    def check_limits(self, amount: float) -> bool:
        """
        Checks if a transaction will make the account exceed the position limits.

        :param amount: Amount of the transaction.

        :return: bool, True if the transaction will exceed the limits.
        """
        if abs(self.cash + amount) > self.net_limit:
            return True
        if abs(self.cash) + abs(amount) > self.gross_limit:
            return True
        return False


class BankAccount(ABC):
    """
    Class to store details of a bank account with multiple subaccounts for different currencies.
    """
    def __init__(self) -> None:
        self.main_currency: str = "cad"
        self.exchange_rates: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.gross_limits: float = float('inf')
        self.net_limit: float = float('inf')
        self.if_strict: bool = False
        self.limit_name: Optional[str] = None
        self.subaccounts: Dict[str, CashAccount] = {}
        self.gross_fine: float = 0
        self.net_fine: float = 0
        self.gross_position: float = 0
        self.net_position: float = 0
        self.max_usage: float = 1

    @abstractmethod
    def add_subaccount(self, cash: float, currency: str = "cad", credit: float = float("inf")) -> None:
        """
        Adds a new subaccount to the bank account. 
        needed to be implemented in the subclass and set the subaccounts according to the subclass's data structure.
        it's currently inherited by BankAccountOperationApi and BankAccountOperationSimulated
        """
        pass
    
    def set_primary_currency(self, currency: str) -> None:
        """
        Sets the primary currency for the bank account. 
        The value of the bank account will be calculated in this currency.

        :param currency: Primary currency.
        """

        self.main_currency = currency.upper()

    def set_total_limits(self, gross_limit: float, net_limit: float, if_strict=False, limit_name=None) -> None:
        """
        Sets the position limits for all cash accounts.

        :param gross_limit: Gross position limit for all cash accounts. sum of absolute value of all cash accounts. 
        :param net_limit: Net position limit for all cash accounts. the sum of all cash accounts, positive for long, negative for short.
        :param if_strict: If True, the limits are strictly enforced. Trades that exceed the limits will be rejected. else print caution.

        """
        self.gross_limits = gross_limit
        self.net_limit = net_limit
        self.if_strict = if_strict
        self.limit_name = limit_name
    
    def set_subaccount_limits(self, currency: str, 
                                    gross_limit: float, 
                                    net_limit: float, 
                                    is_strict=False, 
                                    limit_name=None) -> None:
        """
        Sets the position limits for a specific subaccount.
        
        :param currency: Currency of the subaccount.
        :param gross_limit: Gross position limit for the subaccount.
        :param net_limit: Net position limit for the subaccount.
        :param is_strict: If True, the limits are strictly enforced. Trades that exceed the limits will be rejected.
        """
        
        self.subaccounts[currency.upper()].set_limits(gross_limit, net_limit, is_strict, limit_name)
    

    def get_subaccount_cash(self, account_name: str) -> float:
        """
        Returns the cash balance for a specific subaccount.
        """
        return self.subaccounts[account_name].get_cash()
    

    def check_portfolio_limits(self, account_name: str, amount: float) -> bool:
        """
        Checks if a transaction will make the account exceed the limits for all cash accounts.
        todo : roughly calculate the total cash in all subaccounts
        """
        if abs(self.get_value() + amount) > self.net_limit or \
              (abs(self.get_value()) + abs(amount) > self.gross_limits):
            return True
        return False
    
    def check_limits(self, account_name: str, amount: float) -> bool:
        """
        Checks if a transaction will make the account exceed the limits for a specific subaccount or the portfolio.
        """
        return (self.check_portfolio_limits(account_name, amount) or self.subaccounts[account_name].check_limits(amount))


    def set_foreign_exchange_rate(self, base_currency: str, 
                                        quote_currency: str, 
                                        bid_rate: float, 
                                        ask_rate: float) -> None:
        """
        Sets the foreign exchange rate between two currencies.

        :param base_currency: Base currency.
        :param quote_currency: Quote currency.
        :param bid_rate: Bid exchange rate. The bank buys 1 quote_currency for bid_rate * base_currency. it's the currency clients can get selling foreign currency. eg. sell 1 dollar, get 7.3 RMB
        :param ask_rate: Ask exchange rate. The bank sells 1 quote_currency for ask_rate * base_currency. eg. for client, buy 1 dollar, pay 7.5 RMB. normally higher than bid rate.

        """
        self.exchange_rates[base_currency.upper()] = {quote_currency.upper(): {"bid": bid_rate, "ask": ask_rate}}

    
    def get_exchange_rate(self, base_currency: str,
                                quote_currency: str, 
                                action: str='buy') -> float:
        """
        returns the exchange rate between two currencies.

        :param base_currency: Base currency.
        :param quote_currency: Quote currency.
        :param action: 'buy' or 'sell' the quote currency, if 'buy', returns the ask rate, if 'sell', returns the bid rate. 

        """

        action = action.lower()
        base_currency = base_currency.upper()
        quote_currency = quote_currency.upper()

        if base_currency == quote_currency:
            return 1
        
        if action not in ["buy", "sell"]:
            raise ValueError("Invalid action. Must be 'buy' or 'sell'.")
        
        try:
            return self.exchange_rates[base_currency][quote_currency][\
                "bid" if action == "sell" else "ask"]
        except KeyError:
            try:
                return 1 / self.exchange_rates[quote_currency][base_currency]["ask" if action == "sell" else "bid"]
            except KeyError:
                raise ValueError(f"Exchange rate not found for {base_currency} \
                                 to {quote_currency}. Please add the exchange rate first.")
            
        
    def get_value(self, primary_currency: str=None) -> float:
        """
        Returns the total value of the bank account in the primary currency.

        :param primary_currency: Primary currency to convert the value to. If None, the main currency of the account is used.
        """
        total_value = 0
        if primary_currency is None:
            primary_currency = self.main_currency
        else:
            primary_currency = primary_currency.upper()

        for account_name, account in self.subaccounts.items():
            if account_name.upper() == primary_currency: # don't need to convert
                total_value += account.get_cash()
            else:
                if account.get_cash() > 0: # need to sell the foreign currency 
                    total_value += self.currency_value_conversion(account_name.upper(), primary_currency, account.get_cash())
                else: # need to buy the foreign currency
                    total_value -= self.currency_value_conversion(primary_currency, account_name.upper(), abs(account.get_cash()))


        return total_value

    
    def currency_value_conversion(self, from_currency: str,
                                        to_currency: str, 
                                        initial_value: float) -> float:
        """
        Converts an amount from one currency to another.

        :param from_currency: Currency to convert from.
        :param to_currency: Currency to convert to.
        :param initial_value: Initial value to convert.
 

        :return: Converted value: how much the target currency can buy with the initial value of the source currency

        """
        if initial_value > 0:
            rate = self.get_exchange_rate(from_currency, 
                                          to_currency, 
                                          action='buy')
        else:
            rate = self.get_exchange_rate(from_currency, 
                                          to_currency, 
                                          action='sell')

        return initial_value / rate
    
    def currency_value_conversion_targetamount(self, from_currency: str,
                                        to_currency: str, 
                                        target_value: float) -> float:
        """
        Converts an amount from one currency to another.

        :param from_currency: Currency to convert from.
        :param to_currency: Currency to convert to.
        :param target_value: Target value to convert to.
 

        :return: Converted value: how much the source currency needed with the target value of the target currency

        """
        rate = self.get_exchange_rate(from_currency, 
                                      to_currency, 
                                      action='buy')
        return target_value * rate



class Asset:
    """
    Class to store details of a single asset(stock or ETF) in the portfolio.
    """
    def __init__(self, name: str,
                 currency: str = "CAD",
                 maximum_trade_size: int = 1000000,
                 minimum_trade_size: int = 0,
                 is_shortable: bool = True,
                 is_tradeable: bool = True,
                 limit_multiplier: int = 1,
                 start_price: Optional[float] = None,
                 trading_fee: float = 0.,
                 limit_order_rebate: float = 0.,
                 liquidity: str = "high"
                 ) -> None:
        
        """
        Initializes a new asset.
        
        :param name: Name of the asset.
        :param currency: Currency of the asset.
        :param maximum_trade_size: Maximum trade size for the asset each time.
        :param minimum_trade_size: Minimum trade size for the asset each time.
        :param is_shortable: If True, the asset can be shorted.
        :param is_tradeable: If True, the asset can be traded.


        """
        self.name = name.upper()
        self.currency = currency.upper()
        self.cost = 0 # total cost of the asset
        self.volume = 0 # current position
        self.vwap = 0 # or average cost
        self.realized_profit = 0 # current realized profit
        self.unrealized_profit = 0 # current unrealized profit
        self.best_bid = 0 # current best bid price
        self.best_ask = 0
        self.rebate = 0 # limit order rebate
        self.nlv = 0 # net liquidation value

        self.maximum_trade_size = maximum_trade_size
        self.minimum_trade_size = minimum_trade_size
        self.is_tradeable = is_tradeable
        self.start_price = start_price # initial price of the asset

        if not is_tradeable: 
            self.maximum_trade_size = 0
            self.minimum_trade_size = 0

        self.is_shortable = is_shortable
        self.gross_limit = float('inf')
        self.net_limit = float('inf')
        self.is_strict = False
        self.limit_name = None
        self.limit_multiplier = limit_multiplier # Multiplier for position limits. Default is 1. If set to 2, the contribution of this asset to the position limits will be doubled.
        self.commission_rate = trading_fee
        self.rebate_rate = limit_order_rebate

    def set_limits(self, gross_limit: float, 
                   net_limit: float, 
                   is_strict=False, 
                   limit_name=None) -> None:
        """
        Sets the position limits for single asset(optional). The asset may also obey the limits of the portfolio.

        :param gross_limit: Gross position limit for the asset.
        :param net_limit: Net position limit for the asset.

        """
        self.gross_limit = gross_limit
        self.net_limit = net_limit
        self.is_strict= is_strict
        self.limit_name = limit_name
    
    def get_volume(self,) -> float:
        return self.volume

    def get_cost(self,) -> float:
        return self.cost
    
    def get_currency(self,) -> str:
        return self.currency
    
    def get_average_cost(self,) -> float:
        return self.vwap
    
    def get_realized_profit(self,) -> float:
        return self.realized_profit
    
    def get_unrealized_profit(self,) -> float:
        return self.unrealized_profit
    
    def get_nlv(self,) -> float:
        return self.nlv
    


class Portfolio:
    def __init__(self) -> None:
        """
        Initializes an empty portfolio.

        """
        self.assets = {}  # Dictionary to store asset details, keyed by asset name.
        self.bank_account = None # Bank account object for the portfolio.
        self.gross_limit = float('inf')  # Gross position limit for all assets(except cash).
        self.net_limit = float('inf')  # Net position limit for all assets (except cash).
        self.is_strict = False  # If True, the limits are strictly enforced. Trades that exceed the limits will be rejected.
        self.limit_name = None
        # Transaction history and profit tracking
        self.transactions = []  # Store all transactions (buy/sell).

        self.max_value = 0  # Track maximum portfolio value for drawdown calculation.
        self.max_drawdown = 0 # todo : track the maximum drawdown
        self.commission_rate = 0. # Commission rate for transactions.
        self.penalty_rate = 0. # Penalty rate for exceeding position limits.
        self.gross_fine = 0
        self.net_fine = 0
        self.gross_position = 0
        self.net_position = 0
        self.max_usage = 1


    def set_commission_rate(self, rate: float, asset_name: str=None) -> None:
        """
        Sets the commission rate. eg. 0.002 for each share
        no unit
        """
        if asset_name is None:
            self.commission_rate = self.assets[asset_name].commission_rate
        else:
            self.commission_rate = rate
    
    def set_penalty_rate(self, rate: float) -> None:
        """
        Sets the penalty rate. if the position exceeds the limits, the penalty will be charged.

        """
        self.penalty_rate = rate

    def set_limits(self, gross_limit: float, net_limit: float, is_strict=False, limit_name=None):
        """
        Sets the position limits for the portfolio. any asset in the portfolio should obey the limits.

        :param gross_limit: Gross position limit.
        :param net_limit: Net position limit.
        :param strict_limit: If True, the limits are strictly enforced. 
        Trades that exceed the limits will be rejected.
        """
        self.gross_limit = gross_limit
        self.net_limit = net_limit
        self.is_strict = is_strict
        self.limit_name = limit_name

    @abstractmethod
    def initialize_portfolio(self, ) -> None:
        """
        Initializes the portfolio with multiple stocks.

        """
        pass


    @abstractmethod
    def add_asset(self, asset_name: str, currency: str="CAD") -> None:
        """
        Adds and initialize a new asset to the portfolio.
        need to be implemented in the subclass, either PortfolioOperationApi or PortfolioOperationSimulated

        :param asset_name: Name of the asset to add.

        """
        pass
    

    def cal_commission(self, volume: float) -> float:
        """
        Calculate the commission for a transaction.

        :param volume: Volume of the transaction.
        :return: Commission for the transaction.
        """
        return abs(volume) * self.commission_rate

    def get_total_realized_profit(self, target_currency: str=None) -> float:
        """
        Returns the total realized profit from all transactions. The profit is converted to the target currency.
        if the target currency is None, return the total realized profit based on the main currency of the bank account.
        :return: Total realized profit.
        """
        if target_currency is None:
            target_currency = self.bank_account.main_currency
        else:
            target_currency = target_currency.upper()

        realized_profit = 0
        for asset_name in self.assets:
            if self.assets[asset_name].get_currency() == target_currency:
                realized_profit += self.assets[asset_name].get_realized_profit()
            else:
                if self.assets[asset_name].get_realized_profit() > 0:
                    realized_profit += self.bank_account.currency_value_conversion(
                        self.assets[asset_name].get_currency(), 
                        target_currency, 
                        self.assets[asset_name].get_realized_profit())
                else:
                    realized_profit -= self.bank_account.currency_value_conversion(target_currency, 
                                                        self.assets[asset_name].get_currency(), 
                                                        abs(self.assets[asset_name].get_realized_profit()))

        return realized_profit

    
    def get_total_unrealized_profit(self, target_currency: str=None) -> float:
        """
        Returns the total unrealized profit from the current portfolio.
        """
        if target_currency is None:
            target_currency = self.bank_account.main_currency
        else:
            target_currency = target_currency.upper()

        unrealized_profit = 0
        for asset_name in self.assets:
            if self.assets[asset_name].get_currency() == target_currency:
                unrealized_profit += self.assets[asset_name].get_unrealized_profit()
            else:

                if self.assets[asset_name].get_unrealized_profit() > 0:
                    unrealized_profit += self.bank_account.currency_value_conversion(
                        self.assets[asset_name].get_currency(), 
                        target_currency, 
                        self.assets[asset_name].get_unrealized_profit())
                else:
                    pass
                    # unrealized_profit -= self.bank_account.currency_value_conversion(target_currency, 
                    #                                     self.assets[asset_name].get_currency(), 
                    #                                     abs(self.assets[asset_name].get_unrealized_profit()))
        return unrealized_profit


    def check_portfolio_limits(self, asset_name: str, 
                     volume: float) -> bool:
        """
        Checks if adding a transaction will make the portfolio exceed the position limits.

        :param asset_name: Name of the asset to check.
        :param volume: Volume of the transaction.

        :return: bool, True if the transaction will exceed the limits.

        """

        gross_position = 0
        net_position = 0

        for (name_, asset_obj) in self.assets.items():
            if name_ == asset_name.upper():
                gross_position += abs(asset_obj.get_volume() + volume) 
                net_position += (asset_obj.get_volume() + volume)
            else:
                gross_position += abs(asset_obj.get_volume())
                net_position += asset_obj.get_volume()

        if gross_position > self.gross_limit * self.max_usage:
            return True

        if abs(net_position) > self.net_limit * self.max_usage:
            return True
        
        return False
    

    def check_limits(self, asset_name: str,
                            volume: float) -> bool:
        """
        Checks if adding a transaction will make the asset exceed its position limits.

        :param asset_name: Name of the asset to check.
        :param volume: Volume of the transaction.

        :return: bool, True if the transaction will exceed the limits.

        """
        # if exceed the position limits
        if abs(self.assets[asset_name].get_volume()) + volume > self.assets[asset_name].gross_limit * self.max_usage:
            return True

        if abs(self.assets[asset_name].get_volume() + volume) > self.assets[asset_name].net_limit * self.max_usage:
            return True
        
        # if exceed the limits for portfolio
        
        if self.check_portfolio_limits(asset_name, volume):
            return True

        return False
    
    def check_bulk_limits(self, asset_quantity: Dict[str, int]) -> bool:
        """
        Checks if adding multiple transactions will make any asset exceed its position limits.

        """
        for (name_, quantity) in asset_quantity.items():
            if self.check_limits(name_, quantity):
                return True


    def check_bulk_portfolio_limits(self, asset_quantity: Dict[str, int]) -> bool:    
        """
        Checks if adding multiple transactions will make the portfolio exceed the position limits.

        """
        gross_position = self.gross_position
        net_position = self.net_position

        for (name_, quantity) in asset_quantity.items():
            if self.assets[name_].get_volume() * quantity < 0:
                if abs(self.assets[name_].get_volume()) > abs(quantity):
                    gross_position -= abs(quantity)
                    net_position += quantity
                else:
                    gross_position = gross_position \
                                     - abs(self.assets[name_].get_volume()) \
                                     + abs(quantity + self.assets[name_].get_volume())
                    net_position += quantity
            
            else:
                gross_position += abs(quantity)
                net_position += quantity
        
 
        if gross_position > self.gross_limit * self.max_usage:
            return True

        if abs(net_position) > self.net_limit * self.max_usage:
            return True
        
        return False

    def compress_position(self, asset_quantity: Dict[str, int],) -> Dict[str, int]:
        """
        suppose multiple orders will be executed. Adjust the position to obey the limits.

        :param asset_quantity: dict of asset name and the volume of the asset to be traded. quantity can be negative mean selling
        :param position_usage: the percentage of the position to be used. eg. 0.8 means 80% of the position will be used. 
                                1 means 100% of the position will be used.

        """
        if not self.check_bulk_limits(asset_quantity):
            return {name_:  quantity for (name_, quantity) in asset_quantity.items()}
        else:
            ratio = self.adjust_position(asset_quantity)
            return {name_: int(ratio * quantity) for (name_, quantity) in asset_quantity.items()}
    
    def adjust_position(self, asset_quantity: Dict[str, int]) -> Dict[str, int]:

        """
        Adjust the position to obey the limits.

        todo : not precise in gross position adjustment

        :param asset_quantity: dict of asset name and the volume of the asset to be traded.


        """
        
        max_gross = self.gross_limit * self.max_usage
        max_net = self.net_limit * self.max_usage
        gross_position = self.gross_position 
        net_position = self.net_position 
        ratio = 1

        if abs(net_position) > max_net or gross_position > max_gross:
            return 0

        total_net_position = sum(asset_quantity.values())

        if total_net_position * net_position > 0:
            ratio = min((max_net - abs(net_position)) / abs(total_net_position), 1)
        else:
            if abs(net_position + total_net_position) > max_net:
                ratio = min((abs(max_net) + abs(net_position)) / abs(total_net_position), 1)
            else:
                ratio = 1

        total_gross_position = 0
        for (name_, quantity) in asset_quantity.items():
            if quantity * self.assets[name_].get_volume() > 0:
                total_gross_position += abs(quantity)
            else:
                total_gross_position -= abs(quantity)
        
        if total_gross_position > (max_gross - gross_position):
            ratio = min(ratio, (max_gross - gross_position) / total_gross_position)
        
        return ratio


    def get_portfolio_cost(self, currency: str=None) -> float:
        """
        Calculates the total value of the portfolio.

        :return: Total portfolio value.
        """
        if currency is None:
            currency = self.bank_account.main_currency
        else:
            currency = currency.upper()
        
        total_value = 0
        for details in self.assets.values():
            if details.get_currency() == currency:
                total_value += details.get_cost()
            else:
                if details.get_cost() > 0:
                    total_value += self.bank_account.currency_value_conversion(details.get_currency(),
                                                                            currency, 
                                                                            details.get_cost())
                else:
                    total_value -= self.bank_account.currency_value_conversion(currency,
                                                                            details.get_currency(), 
                                                                            abs(details.get_cost()))

        return total_value
    
    def get_asset_position(self, asset_name: str) -> float:
        """
        Returns the volume of a specific asset in the portfolio.

        Args:
            asset_name (str): Name of the asset to query.

        Returns:
            float: Volume of the asset.

        Raises:
            KeyError: If asset does not exist in the portfolio.
        """
        try:
            return self.assets[asset_name].get_volume()
        except KeyError:
            logger.error(f"Asset '{asset_name}' does not exist in the portfolio.")
            raise
    
    def get_asset_nlv(self, asset_name: str) -> float:
        """
        Returns the net liquidation value of a specific asset in the portfolio.

        Args:
            asset_name (str): Name of the asset to query.

        Returns:
            float: Net liquidation value of the asset.

        Raises:
            KeyError: If asset does not exist in the portfolio.
        """
        try:
            return self.assets[asset_name].get_nlv()
        except KeyError:
            logger.error(f"Asset '{asset_name}' does not exist in the portfolio.")
            raise
    

    def display_portfolio(self) -> None:
        """
        Logs the portfolio details.
        """
        logger.info("Portfolio:")
        for asset_name, details in self.assets.items():
            logger.info(f"Asset: {asset_name}, Cost: {details.get_cost()}, Volume: {details.get_volume()}, "
                        f"Average Cost: {details.get_average_cost()}, nlv: {details.get_nlv()}, Realized Profit: {details.get_realized_profit()}, "
                        f"Unrealized Profit: {details.get_unrealized_profit()}")

    def get_transactions(self):
        """
        Returns the history of all transactions (buy/sell).

        :return: List of all transactions.
        """
        return self.transactions
    
    def get_portfolio_value(self, target_currency='cad') -> float:
        """
        Returns the total value of the portfolio.

        :return: Total portfolio value.
        """

        return self.get_portfolio_cost(target_currency) + \
               self.get_total_unrealized_profit(target_currency) + \
               self.bank_account.get_value(target_currency)


    def get_drawdown(self) -> float:
        """
        Calculates the maximum drawdown based on the portfolio's value.

        :return: Maximum drawdown.
        """
        if self.max_value == 0:
            return 0  # No drawdown if the portfolio has no recorded value

        
        drawdown = (self.max_value - self.get_portfolio_value()) / self.max_value
        return drawdown


    def get_gross_position(self):
        """
        Returns the total gross position of the portfolio.
        assets with higher limit multiplier will contribute more to the gross position.

        :return: Gross position.
        """
        return sum(abs(details.get_volume()*details.limit_multiplier) for details in self.assets.values())
    
    def get_net_position(self):
        """
        Returns the total net position of the portfolio.

        :return: Net position.
        """
        return sum(details.get_volume()*details.limit_multiplier for details in self.assets.values())
    
    