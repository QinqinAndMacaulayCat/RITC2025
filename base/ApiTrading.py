
"""
ApiTrading: Trading API interaction and portfolio management.

This module provides classes and methods to interact with a trading API,
manage a portfolio, place and manage orders, and handle account balances.

Classes:
- CashAccountOperationApi: Extends CashAccount to update cash balance.
- BankAccountOperationApi: Extends BankAccount to manage subaccounts and update balances.
- AssetOperationApi: Extends Asset to update asset data from API.
- ApiTrading: Main class to manage portfolio, place orders, and update information from API.


"""

import configparser
from typing import List
from RITC.base.OrderBook import Order
from RITC.base.Portfolio import CashAccount, BankAccount, Asset, Portfolio
from collections import deque
from time import time

parser = configparser.ConfigParser()
parser.read('config.ini')


class CashAccountOperationApi(CashAccount):
    def update_balance(self, amount: float) -> None:
        self.transactions.append({"amount": amount - self.cash, "balance": amount})
        self.cash = amount



class BankAccountOperationApi(BankAccount):
    def add_subaccount(self, cash: float, currency="CAD", credit=float("inf")) -> None:
        self.subaccounts[currency.upper()] = CashAccountOperationApi(currency.upper(), cash, credit)
    def update_balance(self, account_name: str, amount: float) -> None:
        self.subaccounts[account_name.upper()].update_balance(amount)
    

class AssetOperationApi(Asset):
    def update_data_from_api(self, vwap, position, nlv, realized_profit, unrealized_profit):
        self.vwap = vwap
        self.volume = position
        self.nlv = nlv
        self.realized_profit = realized_profit
        self.unrealized_profit = unrealized_profit
        self.cost = self.vwap * self.volume



class ApiTrading(Portfolio):
    order_timestamps = deque()
    def __init__(self, data_fetcher):
        super().__init__()
        self.session = data_fetcher.session
        self.url = data_fetcher.url
        self.data_fetcher = data_fetcher
        self.history_orders, self.completed_orders = {}, set()
        self.active_orders, self.cancelled_orders = set(), set()
        self.accepted_tenders, self.rejected_tenders = set(), set()
        self.bank_account = BankAccountOperationApi()

    def can_place_order(self, ordernum=0):
        current_time = time()
        while self.order_timestamps and current_time - self.order_timestamps[0] > 1:
            self.order_timestamps.popleft()
        return (len(self.order_timestamps) + ordernum) < self.MAX_ORDERS_PER_SECOND - 2

    def initialize_portfolio(self, max_position_usage: float = 1) -> None:
        self.initialize_assets()
        self.set_limits()
        self.max_usage = self.bank_account.max_usage = max_position_usage
        self.MAX_ORDERS_PER_SECOND = int(parser["ALGOTrading"]["MAX_ORDERS_PER_SECOND"])

    def initialize_assets(self):
        data = self.data_fetcher.get_basic_security_info()
        limits = self.data_fetcher.get_initial_limits()
        is_strict = bool(parser["ALGOTrading"]["strict_limits"])
        self.set_limits(is_strict)
        for security, info in data.items():
            t = info['type'].lower()
            if t == "currency":
                self.bank_account.add_subaccount(info["position"], security.upper(), float("inf") if info["is_shortable"] else 0)
                self.bank_account.subaccounts[security.upper()].set_maximum_transaction_size(info["max_trade_size"])
                if info["currency"] != security:
                    self.bank_account.set_foreign_exchange_rate(info["currency"], security, info["start_price"], info["start_price"])
                limit_ = limits.get(info["limit_name"], None)
                if limit_:
                    self.bank_account.set_subaccount_limits(security.upper(), limit_["gross_limit"], limit_["net_limit"], is_strict, info["limit_name"])
            elif t in ["stock", "index"]:
                self.add_asset(security.upper(), info["currency"], info["max_trade_size"], info["min_trade_size"], info["is_shortable"], info["is_tradeable"], 1 / info["limit_unit"], info["start_price"], info["trading_fee"], info["limit_order_rebate"])
                limit_ = limits.get(info["limit_name"], None)
                if limit_:
                    self.assets[security.upper()].set_limits(limit_["gross_limit"], limit_["net_limit"], is_strict, info["limit_name"])
            else:
                print(f"Unknown security type '{t}', please add new method.")
    
    def add_asset(self, name, currency: str = "CAD", maximum_trade_size: int = 1000000,
                  minimum_trade_size: int = 0, is_shortable=True, is_tradeable=True,
                  limit_multiplier=1, start_price=None, trading_fee=0., limit_order_rebate=0.):
        self.assets[name] = AssetOperationApi(name, currency.upper(), maximum_trade_size, minimum_trade_size, is_shortable, is_tradeable, limit_multiplier, start_price, trading_fee, limit_order_rebate)

    def set_limits(self, if_strict=False):
        data = self.data_fetcher.get_initial_limits()
        for asset in data:
            t = asset.lower()
            if t == "cash":
                self.bank_account.set_total_limits(data[asset]["gross_limit"], data[asset]["net_limit"], if_strict, "cash")
            elif t == "stock":
                self.gross_limit = data[asset]["gross_limit"]
                self.net_limit = data[asset]["net_limit"]
                self.if_strict = if_strict
                self.limit_name = "stock"

    
    def update_all_information(self):
        self.update_order_status()
        self.update_position()
        self.update_limits_quota()

    

    def place_order(self, ticker: str, type: str,
                    quantity: int, action: str,
                    price=None) -> Order:
        """
        place an order.

        :param ticker: The ticker of the security. 
        :param type: The type of the order (LIMIT, MARKET).
        :param quantity: The quantity of shares in the order.
        :param action: The action of the order (buy/sell).
        :param price: The price of the order if it is a limit order.

        """
        if quantity == 0:
            return -1

        if self.assets[ticker.upper()].is_tradeable is False:
            print(f"{ticker} is not tradeable. Order placement failed.")
            return -1
        
        # if the order is not shortable, check if the position is enough to place the order
        if self.assets[ticker.upper()].is_shortable is False and action.lower() == "sell":
            if self.assets[ticker.upper()].get_volume() < 0:
                print(f"{ticker} is not shortable. Order placement failed.")
                return -1
            else:
                if self.assets[ticker.upper()].get_volume() + quantity < 0:
                    print(f"Order quantity exceeds the position for {ticker}. Limiting the quantity to the position.")
                    quantity = self.assets[ticker.upper()].get_volume()
                else:
                    pass

        
        if quantity > self.assets[ticker.upper()].maximum_trade_size:
            print(f"Order quantity exceeds the maximum trade size for {ticker}. Limiting the quantity to the maximum trade size.")
            quantity = self.assets[ticker.upper()].maximum_trade_size

        payload = {
            "ticker": ticker.upper(),
            "type": type.upper(),
            "quantity": quantity,
            "action": action.upper(),
            "dry_run": 0
        }

        if price is not None:
            payload["price"] = price
        
        resp = self.session.post(self.url + "/orders", params=payload)

        if resp.status_code == 200:
            resp = resp.json()
            # print(f"{action} {ticker} order of {quantity} shares with {type} type has been placed at {price} successfully.The order id is {resp['order_id']}.")

            
            order_ = Order(resp['price'], 
                  resp['quantity'], 
                  resp['quantity_filled'],
                  "bid" if resp['action'].lower() == 'buy' else "ask", 
                  resp['tick'],
                  resp['order_id'],
                  resp['type'],
                  resp['vwap']
                  )
            self.history_orders[order_.id] = order_
            if order_.volume == 0:
                # print(f"{type} order of {quantity} shares {ticker} listed at {str(price)} has been completed at price{resp['vwap']} at tick {resp['tick']}.")
                self.completed_orders.add(order_.id)  # order is completed immediately
            else:
                self.active_orders.add(order_.id)  # order is still waited to be completed

            self.order_timestamps.append(time())
            # update position information
            return order_
        
        elif resp.status_code == 500:
            resp = resp.json()
            message = resp["message"]
            print(f"{ticker} Order placement failed. Internal server error {message}. Please try again.")
            return -1
        else:
            resp = resp.json()
            message = resp["message"]
            print(f"{ticker} Order placement failed. unknown error{message}, please check API documentation.")
            return -1
    
    def place_currency_order(self, ticker: str, action: str, quantity: float) -> int:
        """
        place an order for currency exchange."""

        if self.bank_account.subaccounts[ticker].is_tradeable is False:
            print(f"{ticker} is not tradeable. Order placement failed.")
            return -1

        if quantity > self.bank_account.subaccounts[ticker].maximum_transaction_size:
            # print(f"Order quantity exceeds the maximum trade size for {ticker}. Limiting the quantity to the maximum trade size.")
            quantity = self.bank_account.subaccounts[ticker.upper()].maximum_transaction_size

        payload = {
            "ticker": ticker.upper(),
            "type": "MARKET",
            "quantity": quantity,
            "action": action.upper(),
            "dry_run": 0
        }
        
        resp = self.session.post(self.url + "/orders", params=payload)

        if resp.status_code == 200:
            resp = resp.json()
            # print(f"{action} {ticker} order of {quantity} shares with market price has been placed successfully.The order id is {resp['order_id']}.")
            return quantity
        
        elif resp.status_code == 500:
            resp = resp.json()
            message = resp["message"]
            print(f"{ticker} Order placement failed. Internal server error {message}. Please try again.")
            return -1
        else:
            resp = resp.json()
            message = resp["message"]
            print(f"{ticker} Order placement failed. unknown error{message}, please check API documentation.")
            return -1
    


    def dry_run(self, ticker: str, quantity: int, action: str) -> None:
        """
        
        dry_run: Whether to actually place the order or not. 0/1.
          1- Simulates the order execution and returns the result as if the order was executed.
          
        only market orders are supported for dry run.

        """
        payload = {
            "ticker": ticker.upper(),
            "quantity": quantity,
            "action": action.upper(),
            "dry_run": 1
        }
        resp = self.session.post(self.url + "/orders", params=payload)

        if resp.status_code == 200:
            resp = resp.json()
        else:
            print(f"{ticker} Order placement failed. unknown error, please check API documentation.")

        
    def cancel_order(self, order_id: int):
        """
        cancel an order.
        caution: the order just placed may not reach the server yet, so the order may not be cancelled.
        :param order_id: The id of the order to cancel.
        """
        resp = self.session.delete(self.url + "/orders/" + str(order_id))
        if resp.status_code == 200:
            if resp.json()['success']:
                print(f"Order id {order_id} was cancelled successfully.")
                self.cancelled_orders.add(order_id)

                if order_id in self.active_orders:
                    self.active_orders.remove(order_id) 

            else:
                print("Order cancellation failed.")

        elif resp.status_code == 401:
            print("Order cancellation failed.Unauthorized access. Please check your credentials.")
        else:
            print(f"fail to cancel order: error {resp.status_code}, {resp.json()}.")
        
    def close_position(self, ticker: str, volume: int = None) -> None:
        
        """
        close a position.

        :param ticker: The ticker of the security to close the position for.
        :param volume: The volume to close. If None, closes the entire position. else closes the specified volume.  
        """
        action = "sell" if self.assets[ticker.upper()].get_volume() > 0 else "buy"

        if volume is None:
            volume = abs(self.assets[ticker.upper()].get_volume())

        print(f"close position: {volume}")
        order = self.place_order(ticker, "MARKET", volume, action)
        return order

    def accept_tender_check_limits(self, tender_id: int, asset_name: str, 
                                   volume: float, price=None) -> int:
        """
        check a tender before accepting it.

        return 1 if the tender is accepted, -1 if the tender is rejected.
        """
        if self.check_limits(asset_name, volume):
            print(f"The position will exceed the limit if the tender is accepted. The tender will not be accepted.")
            return -1
        else:

            result = self.accept_tender(tender_id, price)
            return result


    def accept_tender(self, tender_id: int, price=None):
        """
        accept a tender.

        :param tender_id: The id of the tender to accept.
        :param price: The price to accept the tender at. required only if the tender is not fixed-bid
        """

        if price is None:
            payload = {}
        else:
            payload = {
                "price": price,
            }

        resp = self.session.post(self.url + "/tenders/" + str(tender_id), params=payload)

        if resp.status_code == 200:
            if resp.json()['success']:
                print(f"Tender id {tender_id} accepted successfully.")
                self.accepted_tenders.add(tender_id)
                return 1
            else:
                print("Tender acceptance failed.")
                return -1
        else:
            print(f"Tender API error: {resp.json()}. Tender acceptance failed.")
            return -1

    def reject_tender(self, tender_id: int):
        """
        reject a tender.
        
        :param tender_id: The id of the tender to reject.
        """

        resp = self.session.delete(self.url + "/tenders/" + str(tender_id))

        if resp.status_code == 200:
            if resp.json()['success']:
                print(f"Tender id {tender_id} rejected successfully.")
                self.rejected_tenders.add(tender_id)
            else:
                print("Tender rejection failed.")

        else:
            print(f"API error : {resp.json()}. Tender rejection failed.")

    
    def place_lease(self, ticker: str, 
                    from1: str=None, quantity1: int=None,
                    from2: str=None, quantity2: int=None, 
                    from3: str=None, quantity3: int=None):
        """
        place a lease.

        :param ticker: lease name. eg "ETF-Creation", "ETF-Redemption"
        """

        payload = {"ticker": ticker}
        if from1:
            payload["from1"] = from1
            payload["quantity1"] = quantity1
        if from2:
            payload["from2"] = from2
            payload["quantity2"] = quantity2
        if from3:
            payload["from3"] = from3
            payload["quantity3"] = quantity3

        resp = self.session.post(self.url + "/leases", params=payload)
        if resp.status_code == 200:
            print(f"Lease {ticker} placed successfully.")
        else:
            print("API error: lease placement failed.")
        


    def bulk_cancel_orders(self, cancel_all: bool, query: str, ticker: str=None,
                           ids: List[int]=None) -> List[int]:
        """
        cancel all orders.

        :param cancel_all: Whether to cancel all orders or not. True- Cancels all orders.
        :param ticker: The ticker of the security to cancel orders for.
        :param ids: The ids of the orders to cancel.
        :param query: The query to filter orders to cancel. For example, Ticker='CL' AND Price>124.23 AND Volume<0 will cancel all open sell orders for CL priced above 124.23.
        return : the ids of the orders that were cancelled.
        """
        payload = {
            "cancel_all": 1 if cancel_all else 0,
            "query": query,}
        
        if ticker:
            payload["ticker"] = ticker
        else:
            payload["ticker"] = ""

        if ids:
            payload["ids"] = ",".join(ids)
        else:
            payload["ids"] = ""


        resp = self.session.post(self.url + "/commands/cancel", 
                                   params=payload) 

        if resp.status_code == 200:

            print(f"All orders satisfied the query {query} cancelled successfully."
                   f"cancelled order ids: {resp.json()['cancelled_order_ids']}.")

            for order_id in resp.json()["cancelled_order_ids"]:
                self.cancelled_orders.add(order_id)

                if order_id in self.active_orders:
                    self.active_orders.remove(order_id)

            return resp.json()["cancelled_order_ids"]
        else:
            print(f"bulk cancel error {resp.status_code}: {resp.json()}.")
            return -1



    def update_order_status(self):
        """
        update the status of active orders.
        check if the order has been completed or partially completed 

        """
        copy_ = self.active_orders.copy()
        for order_id in copy_:
            
            resp = self.data_fetcher.check_order_status(order_id)
            if resp:
                if resp["quantity"] <= resp["quantity_filled"]: # if all the quantity has been filled
                    print(f"Order {order_id} has been completed.")
                    self.history_orders[order_id].update_filled_volume(resp["quantity_filled"])
                    self.history_orders[order_id].update_vwap(resp["vwap"])

                    self.completed_orders.add(order_id)
                    self.active_orders.remove(order_id)
                elif resp["quantity_filled"] > self.history_orders[order_id].filled_volume: 
                    print(f"Order {order_id} has been partially completed.")
                    self.history_orders[order_id].update_filled_volume(resp["quantity_filled"])
                    self.history_orders[order_id].update_vwap(resp["vwap"])
                else: 
                    pass
    
    def update_position(self):
        """
        update the current position using the data from the API.
        """
        data = self.data_fetcher.get_position_data()

        for security in data:
            if data[security]['type'].lower() == "currency":

                self.bank_account.update_balance(security.upper(), 
                                                 data[security]["position"])
                                                            
            elif data[security]['type'].lower() == "stock" or data[security]['type'].lower() == "index":
                self.assets[security.upper()].update_data_from_api(data[security]["vwap"],
                                                                    data[security]["position"],
                                                                    data[security]["nlv"],
                                                                    data[security]["realized"],
                                                                    data[security]["unrealized"],
                                                                    )

            else:
                print("Unknown security type, please add new method.")
    
    def update_limits_quota(self):
        """
        update the limits and quotas for the portfolio.
        """
        data = self.data_fetcher.get_limits()

        for asset in data:
            if asset.lower() == "cash":
                self.bank_account.gross_position = data[asset]["gross"]
                self.bank_account.net_position = data[asset]["net"]
                self.bank_account.gross_fine = data[asset]["gross_fine"]
                self.bank_account.net_fine = data[asset]["net_fine"]

            elif asset.lower() == "stock":
                self.gross_position = data[asset]["gross"]
                self.net_position = data[asset]["net"]
                self.gross_fine = data[asset]["gross_fine"]
                self.net_fine = data[asset]["net_fine"]
            else:
                for asset in self.assets:
                    limit_name = self.assets[asset].limit_name
                    self.assets[asset].gross_position = data[limit_name]["gross"]
                    self.assets[asset].net_position = data[limit_name]["net"]
                    self.assets[asset].gross_fine = data[limit_name]["gross_fine"]
                    self.assets[asset].net_fine = data[limit_name]["net_fine"]


                for account in self.bank_account.subaccounts:
                    limit_name = self.bank_account.subaccounts[account].limit_name
                    self.bank_account.subaccounts[account].gross_position = data[limit_name]["gross"]
                    self.bank_account.subaccounts[account].net_position = data[limit_name]["net"]
                    self.bank_account.subaccounts[account].gross_fine = data[limit_name]["gross_fine"]
                    self.bank_account.subaccounts[account].net_fine = data[limit_name]["net_fine"]
