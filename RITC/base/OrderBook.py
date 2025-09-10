"""
This module provides a simplified data structure for managing limit order books, 
including core classes for `Order`, `OrderBook`, and `ExtendOrderBook`.

It supports basic order book operations such as insertion, removal, and clearing, 
and provides utilities for tracking historical order activity and computing volume-weighted 
average price (VWAP). This implementation is tailored for use in discrete-time trading simulations 
or educational algorithmic trading systems.

Classes:
    - Order: Represents a single limit order, including metadata.
    - OrderBook: Maintains the bid and ask sides as linked lists and sorted maps.
    - ExtendOrderBook: Inherits from OrderBook, adds VWAP calculation and historical tracking.
"""

import csv
import numpy as np
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Union
import logging

logger = logging.getLogger(__name__)

@dataclass
class Order:
    """
    Represents a single order in the order book.

    Attributes:
        price (float): The price of the order.
        volume (float): Total volume of the order.
        filled_volume (float): The volume already filled.
        order_type (str): 'bid' or 'ask'.
        timestamp (int, optional): Tick timestamp.
        id (int, optional): Unique identifier for the order.
        price_type (str): 'limit' or 'market'.
        vwap (float, optional): Volume Weighted Average Price of filled quantity.
    """
    price: float
    volume: float
    filled_volume: float
    order_type: str
    timestamp: Optional[int] = None
    id: Optional[int] = None
    price_type: str = "limit"
    vwap: Optional[float] = None

    prev: Optional['Order'] = field(default=None, repr=False, compare=False)
    next: Optional['Order'] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        self.order_type = self.order_type.lower()
        self.price_type = self.price_type.lower()
        if self.order_type not in ["bid", "ask"]:
            raise ValueError("Invalid order type. Must be 'bid' or 'ask'.")
        if self.price_type not in ["limit", "market"]:
            raise ValueError("Invalid price type. Must be 'limit' or 'market'.")
        self.initial_volume = self.volume
        self.volume = self.volume - self.filled_volume

    def update_filled_volume(self, volume: float) -> None:
        """
        Update the filled volume of the order.

        Args:
            volume (float): The new filled volume.
        """
        self.filled_volume = volume
        self.volume = self.initial_volume - self.filled_volume

    def update_vwap(self, vwap: float) -> None:
        """
        Update the Volume Weighted Average Price.

        Args:
            vwap (float): New VWAP value.
        """
        self.vwap = vwap


class OrderBook:
    def __init__(self) -> None:
        self.bid_head: Optional[Order] = None
        self.ask_head: Optional[Order] = None
        self.bid_map: Dict[float, List[Order]] = {}
        self.ask_map: Dict[float, List[Order]] = {}
        self.id_set: set = set()
        self.history: Dict[int, Order] = {}
        self.bid_size: float = 0
        self.ask_size: float = 0
        self.transaction_history: Dict[int, Dict[str, Any]] = {}
        self.price_history: OrderedDict = OrderedDict()
        self.liquidity_history: OrderedDict = OrderedDict()
        self.last: float = 0
        self.best_bid: float = 0
        self.best_ask: float = 0
        self.transaction_fee: float = 0.0
        self.rebate_fee: float = 0.0
        self.currency: str = "cad"
    
    def set_currency(self, currency: str = "cad") -> None:
        """
        Set the currency of the order book.
        """
        self.currency = currency
    
    def set_transaction_fee(self, fee: float) -> None:
        """
        Set the transaction fee for the order book.
        """
        self.transaction_fee = fee

    def set_rebate_fee(self, fee: float) -> None:
        """
        Set the rebate fee for the order book.
        """
        self.rebate_fee = fee


    def insert_order(self, order: Order) -> None:
        if order.order_type == 'bid':
            self._insert_bid(order)
        elif order.order_type == 'ask':
            self._insert_ask(order)
        self.history[order.id] = order

    def _insert_bid(self, order: Order) -> None:
        """
        Insert a bid order into the order book. Sort prices in descending order.
        Allow orders with same price but different ids to be inserted.
        """
        
        # Insert as a new order
        if self.bid_head is None:
            self.bid_head = order
            self.bid_map[order.price] = [order]
            return 
        
        current = self.bid_head
        while current and current.price > order.price:
            current = current.next
        if current:
            order.next = current
            order.prev = current.prev
            if current.prev:
                current.prev.next = order
            current.prev = order
        else:
            if self.bid_head is None:
                self.bid_head = order
            else:
                last = self.bid_head
                while last.next:
                    last = last.next
                last.next = order
                order.prev = last
        self.bid_map[order.price] = self.bid_map.get(order.price, []) + [order]

    def _insert_ask(self, order: Order) -> None:
        """
        Insert an ask order into the order book. Sort prices in ascending order.

        """
        if self.ask_head is None:
            self.ask_head = order
            self.ask_map[order.price] = [order]
            return
        
        # Insert as a new order
        current = self.ask_head
        while current and current.price < order.price:
            current = current.next
        if current:
            order.next = current
            order.prev = current.prev
            if current.prev:
                current.prev.next = order
            current.prev = order
        else:
            if self.ask_head is None:
                self.ask_head = order
            else:
                last = self.ask_head
                while last.next:
                    last = last.next
                last.next = order
                order.prev = last
        self.ask_map[order.price] = self.ask_map.get(order.price, [])  + [order]

    
    def record_transaction(self, id: int, period: int, price: float, quantity: float, tick: int) -> None:
        """
        Records a transaction in the transaction history.

        :param id: inr, the id of the order.
        :param price: float, the price of the transaction.
        :param quantity: float, the volume of the transaction.
        :param tick: int, the tick at which the transaction occurred.
        """

        if self.price_history:
            key_ = len(self.price_history)
        else:
            key_ = 0

        self.transaction_history[key_] = {
            "period": period,
            "price": price,
            "quantity": quantity,
            "tick": tick
        }
    
    def get_last_transaction_id(self) -> int:
        """
        Returns the id of the last transaction.
        """
        return max(self.transaction_history.keys())

    
    def update_price_history(self, last_price: float, 
                             best_bid: float, 
                             best_ask: float
                             ) -> None:
        """
        Updates the price history with the current best bid and ask prices.
        """
        if self.price_history:
            key_ = len(self.price_history)
        else:
            key_ = 0

        self.price_history[key_] = {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "last": last_price
        }
        self.last = last_price
        self.best_bid = best_bid
        self.best_ask = best_ask

    def clear_old_history(self, keep_num: int=10000) -> None:
        """
        Clear a part of the history data that is older than the specified number of records.
        """
        self.transaction_history = {key: self.transaction_history[key] for key in sorted(self.transaction_history.keys(), reverse=True)[:keep_num]}
        self.price_history = {key: self.price_history[key] for key in sorted(self.price_history.keys(), reverse=True)[:keep_num]}
        self.liquidity_history = {key: self.liquidity_history[key] for key in sorted(self.liquidity_history.keys(), reverse=True)[:keep_num]}
        self.history = {}

    
    def update_liquidity(self, bid_size: float, ask_size: float) -> None:
        """
        Update the liquidity of the order book.

        :param bid_size: float, the total volume of all bid orders.
        :param ask_size: float, the total volume of all ask orders.
        """
        if self.liquidity_history:
            key_ = len(self.liquidity_history)
        else:
            key_ = 0

        self.liquidity_history[key_] = {
            "bid_size": bid_size,
            "ask_size": ask_size
        }

        self.bid_size = bid_size
        self.ask_size = ask_size


    def get_price_history(self, type="array"):
        """
        Returns the price history
        
        :param type: str, the type of the return value. "array" or "dict"

        """
        if type.lower() == "array":
            return np.array([item["last"] for item in self.price_history.values()])
        
        return self.price_history
    
    def get_n_last_prices(self, n=5) -> np.array:
        """
        Returns the last n prices in the price history.
        """
        return np.array([item["last"] for item in list(self.price_history.values())[-n:]])
        

    def delete_order(self, order_type: str, volume=None, by='price', price=None, id=None) -> None:
        """
        Delete an order by price. If volume is specified, reduce the volume instead of deleting entirely.

        :param order_type: str, the type of the order. "bid" or "ask".
        :param volume: float, the volume to delete.
        :param by: str, the method to delete the order. "price" or "id".
        :param price: float, the price of the order.
        :param id: int, the id of the order.
        """
        order_type = order_type.lower()
        by = by.lower()
        if by == 'price':

            self._delete_order_by_price(price, order_type, volume)
            
        elif by == 'id':
            self._delete_order_by_id(id, order_type)
        else:
            raise ValueError("Invalid method. Must be 'price or 'id'.")
    
    def _delete_order_by_id(self, id: int, order_type='bid') -> None:
        """
        Delete an order by id.
        
        :param id: int, the id of the order.
        :param order_type: str, the type of the order. "bid" or "ask".
        """
        order_type = order_type.lower()
        if order_type == 'bid':
            curr = self.bid_head

        elif order_type == 'ask':
            curr = self.ask_head

        else:
            raise ValueError("Invalid order type. Must be 'bid' or 'ask'.")
        while curr:
            if curr.id == id:
                if curr.prev:
                    curr.prev.next = curr.next
                if curr.next:
                    curr.next.prev = curr.prev

                if order_type == 'bid':
                    if self.bid_head == curr:
                        self.bid_head = curr.next
                elif order_type == 'ask':
                    if self.ask_head == curr:
                        self.ask_head = curr.next
                else:
                    raise ValueError("Invalid order type. Must be 'bid' or 'ask'.")
                return
            curr = curr.next
        

    def _delete_order_by_price(self, price: float, order_type='bid', volume=None) -> None:
        """
        Delete an order by price.
        
        :param price: float, the price of the order.
        :param order_type: str, the type of the order. "bid" or "ask".
        :param volume: float, the volume to delete.
        """
        order_type = order_type.lower()
        if order_type == 'bid':
            current = self.bid_head
        elif order_type == 'ask':
            current = self.ask_head
        else:
            raise ValueError("Invalid order type. Must be 'bid' or 'ask'.")
        
        while current:
            if current.price == price:
                if volume is not None:
                    if current.volume > volume:

                        current.update_filled_volume(current.filled_volume + volume)
                        volume = 0
                    else:
                        volume -= current.volume
                        if current.prev:
                            current.prev.next = current.next
                        if current.next:
                            current.next.prev = current.prev

                        if order_type == 'bid':
                            if self.bid_head == current:
                                self.bid_head = current.next
                        elif order_type == 'ask':
                            if self.ask_head == current:
                                self.ask_head = current.next
                        else:
                            pass
                            
                        if order_type == 'bid':
                            self.bid_map[price].remove(current)
                        elif order_type == 'ask':
                            self.ask_map[price].remove(current)

                else:
                    if current.prev:
                        current.prev.next = current.next
                    if current.next:
                        current.next.prev = current.prev
                    
                    if order_type == 'bid':
                        if self.bid_head == current:
                            self.bid_head = current.next
                    elif order_type == 'ask':
                        if self.ask_head == current:
                            self.ask_head = current.next
                    else:
                        pass

                    if order_type == 'bid':
                        del self.bid_map[price]
                    elif order_type == 'ask':
                        del self.ask_map[price]
                return
            current = current.next

    def clear_orders(self) -> None:
        """
        Clear all orders from the order book. 
        Won't clear the history.
        """
        self.bid_head = None
        self.ask_head = None
        self.bid_map.clear()
        self.ask_map.clear()

    def print_orders(self):
        print("Bid Orders:")
        current = self.bid_head
        while current:
            print(f"Price: {current.price}, Volume: {current.volume}")
            current = current.next
        print("\nAsk Orders:")
        current = self.ask_head
        while current:
            print(f"Price: {current.price}, Volume: {current.volume}")
            current = current.next

    def save_history_to_csv(self, filename: str = "order_history.csv") -> None:
        """
        Save the order history to a CSV file.
        """
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Order Type", "Price", "Volume"])  # Write header
            for order in self.history.values():
                writer.writerow([order.timestamp, order.order_type, order.price, order.volume])


class ExtendOrderBook(OrderBook):

    def __init__(self) -> None:
        super().__init__()
        self.bid_ask_spreads: List[float] = []  # array to store historical bid-ask spreads
        self.history_volatilities: List[float] = []  # list to store historical volatilities

    def get_moving_average(self, window: int = 5) -> Union[np.ndarray, None]:
        """
        Calculate the moving average of the order book prices.
        """
        if len(self.price_history) < window:
            return None

        prices = self.get_price_history(type="array")
        return np.convolve(prices, np.ones(window) / window, mode='valid')

    def get_bid_ask_spread(self) -> Union[float, None]:
        """
        Calculate the bid-ask spread.
        """
        if self.bid_head is None or self.ask_head is None:
            return None
        return self.ask_head.price - self.bid_head.price
    
    def monitor_bid_ask_spread(self) -> bool:
        """
        Check if the current Bid-Ask Spread has widened compared to historical spreads.
        """
        if len(self.bid_ask_spreads) < 2:
            return False  # Not enough data to make a decision
        current_spread = self.bid_ask_spreads[-1]
        avg_spread = np.mean(self.bid_ask_spreads)
        std_spread = np.std(self.bid_ask_spreads)
        return current_spread > avg_spread + 2 * std_spread
    
    def monitor_extreme_price(self) -> bool:
        """
        Check if the current price is an extreme value compared to historical prices.
        """
        if not self.price_history:
            return False
        prices = np.array([item["last"] for item in self.price_history.values()])
        current_price = prices[-1]
        avg_price = np.mean(prices)
        std_price = np.std(prices)
        return abs(current_price - avg_price) > 2 * std_price

    
    def get_sigma(self, window: int = 100) -> Union[float, None]:
        """
        Calculate the historical volatility using the bid-ask spread.
        """
        if len(self.bid_ask_spreads) < window:
            return None
        return float(np.std(self.bid_ask_spreads[-window:]))
    
        
    def get_total_bid_volume(self):
        """
        Calculate the total volume of all bid orders.
        """
        total_volume = 0
        current = self.bid_head
        while current:
            total_volume += current.volume
            current = current.next
        return total_volume
    
    def get_total_ask_volume(self):
        """
        Calculate the total volume of all ask orders.
        """
        total_volume = 0
        current = self.ask_head
        while current:
            total_volume += current.volume
            current = current.next
        return total_volume
    

    def calculate_vwap_market_price(self, quantity: int, action: str, consider_cost: bool = True) -> Union[float, None]:
        """
        to fill a certain quantity of shares, what's the average price of the shares.

        :param quantity: int, the quantity of shares to fill.
        :param action: str, the action to take. "buy" or "sell".
        :param consider_cost: bool, whether to consider the cost of trading.
        return the average price of the shares. if not enough shares to fill the order, return None. 
                when the action is "buy", the price is the cost, when the action is "sell", the price is the revenue.
        """
        if consider_cost and self.transaction_fee == 0:
            logger.warning("Transaction fee is not set. Please set the transaction fee.")

        action = action.lower()
        if action not in ["buy", "sell"]:
            raise ValueError("Invalid action. Must be 'buy' or 'sell'.")

        total_cost = 0
        unfilled_quantity = quantity

        if action == "buy":
            current = self.ask_head
        else:
            current = self.bid_head
            
        while unfilled_quantity > 0 and current:
            if current.volume < unfilled_quantity:
                total_cost += current.price * current.volume
                unfilled_quantity -= current.volume
            else:
                total_cost += current.price * unfilled_quantity
                unfilled_quantity = 0
            current = current.next


        if unfilled_quantity > 0:
            logger.warning("Not enough market depth to fill the order.")
            return None
        else:
            if consider_cost:
                if action == "buy":
                    return total_cost / quantity + self.transaction_fee # cost for buying
                else:
                    return total_cost / quantity - self.transaction_fee # profit for selling
            else:
                return total_cost / quantity
    
    def stress_testing_market_price(self, quantity: int, quantity_stress_factor: float, price_stress_factor: float, action: str, consider_cost: bool = True) -> Union[float, None]:
        """
        Perform stress testing on a specific order.
        :param quantity: int, the quantity of shares to fill.
        :param quantity_stress_factor: float, the factor to stress the quantity.  <1
        :param price_stress_factor: float, the factor to stress the price. the percentage of price change. 
        :param action: str, the action to take. "buy" or "sell".
        :param consider_cost: bool, whether to consider the cost of trading.

        :return the average price of the shares. if not enough shares to fill the order, return None. 
                
        """
        if consider_cost and self.transaction_fee == 0:
            logger.warning("Transaction fee is not set. Please set the transaction fee.")

        action = action.lower()
        if action not in ["buy", "sell"]:
            raise ValueError("Invalid action. Must be 'buy' or 'sell'.")

        total_cost = 0
        unfilled_quantity = quantity

        if action == "buy":
            current = self.ask_head
            price_stress_factor = 1 + price_stress_factor
        else:
            current = self.bid_head
            price_stress_factor = 1 - price_stress_factor
            
        while unfilled_quantity > 0 and current:
            if current.volume * quantity_stress_factor < unfilled_quantity:
                total_cost += current.price * price_stress_factor * current.volume * price_stress_factor
                unfilled_quantity -= current.volume * price_stress_factor
            else:
                total_cost += current.price * price_stress_factor * unfilled_quantity
                unfilled_quantity = 0
            current = current.next

        if unfilled_quantity > 0:
            logger.warning("Not enough market depth to fill the order.")
            return None
        else:
            if consider_cost:
                if action == "buy":
                    return total_cost / quantity + self.transaction_fee
                else:
                    return total_cost / quantity - self.transaction_fee
            else:
                return total_cost / quantity
            
        
    def limit_order_assistant(self, trade_volume, side="buy", slippage_tolerance=0.01):
        """
        Decide whether to use a limit order or market order, and suggest the limit price if applicable.

        :param order_book: Dictionary with 'bids' and 'asks', each being a list of [price, volume].
                        Example: {"bids": [[99, 100], [98.5, 200]], "asks": [[100.5, 150], [101, 300]]}
        :param trade_volume: The total volume you want to trade.
        :param side: "buy" or "sell", indicating the trade direction.
        :param slippage_tolerance: Maximum acceptable slippage as a fraction of the current market price. 
            if the slippage is less than the tolerance, use market order. else use limit order to avoid slippage.
        :return: Dictionary with decision and price details:
                {"order_type": "market" or "limit", "limit_price": suggested_price or None}.
        """
        if side not in ["buy", "sell"]:
            raise ValueError("Invalid side. Choose 'buy' or 'sell'.")

        if side == "buy":
            market_price = self.ask_head.price
        else:
            market_price = self.bid_head.price

        average_price = self.calculate_vwap_market_price(trade_volume, side, consider_cost=False)

        slippage = abs(average_price - market_price) if average_price else float("inf")

        if slippage <= slippage_tolerance:
            return {"order_type": "market", "price": None}

        # Determine a limit price based on cumulative volume
        cumulative_volume = 0
        limit_price = None
        current = self.ask_head if side == "buy" else self.bid_head
        while current and cumulative_volume < trade_volume:
            cumulative_volume += current.volume
            limit_price = current.price
            current = current.next

        return {"order_type": "limit", "price": limit_price}
    
    def calculate_total_profit(self, trade_volume, order_type="market",
                                  action="buy", price=None) -> float:
          """
          Calculate the total cost or the profit of an order 
          which consider both the transaction fee and the rebate
          """
          if order_type not in ["market", "limit"]:
                raise ValueError("Invalid order type. Must be 'market' or 'limit'.")
    
          if order_type == "market":
                if action == "buy":
                    price = self.calculate_vwap_market_price(trade_volume, "buy", consider_cost=True)
                    return price * trade_volume
                else:
                    price = self.calculate_vwap_market_price(trade_volume, "sell", consider_cost=True)
                    return price * trade_volume
          else:
                if action == "buy":
                    return (price + self.transaction_fee - self.rebate_fee) * trade_volume 
                else:
                    return (price - self.transaction_fee + self.rebate_fee) * trade_volume
    
    def calculate_volatility(self, window=30):
        """Calculate the volatility as the standard deviation of price changes over a rolling window."""
        if len(self.price_history) < window:

            return None, None
        
        # Extract the last `window` prices
        prices = self.get_price_history(type="array")[-window:]
        # Calculate log returns
        log_returns = np.diff(np.log(prices))
        
        # Calculate the rolling standard deviation (volatility)
        volatility = np.std(log_returns)
        
        # Append the latest volatility to the history_volatilities list
        self.history_volatilities.append(volatility)
    
        # Calculate the position of current volatility in historical volatility

        sorted_history = sorted(self.history_volatilities)  # Sort in ascending order
        rank = sum(1 for v in sorted_history if v <= volatility)  # Find its orde
        position_in_history = rank / len(sorted_history)
        
        return volatility, position_in_history

    
