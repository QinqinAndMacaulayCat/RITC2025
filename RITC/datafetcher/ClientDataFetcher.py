"""
ClientDataFetcher: Base class for fetching market, news, and asset data from a remote trading server.

This module provides an abstract interface and utility methods for connecting to a trading API, retrieving market data, news, security information, positions, limits, transactions, tenders, and leases. It is designed to be subclassed for specific algorithmic trading or simulation use cases.

Features:
    - Connects to server and manages session
    - Fetches tick, heat info, security info, positions, limits, and transactions
    - Handles news, tenders, and leases
    - Robust error handling and logging

"""
import configparser
import requests
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from RITC.base.OrderBook import OrderBook, Order
from RITC.base.utils import ApiException
from RITC.base.NewsBook import NewsBook, Tender, TenderBook

logger = logging.getLogger(__name__)

class ClientDataFetcher(ABC):
    """
    Base class for fetching data from the server.
    """
    def __init__(self) -> None:
        self.session: Optional[requests.Session] = None
        self.current_tick: int = 0
        self.end: bool = False
        parse = configparser.ConfigParser()
        parse.read("config.ini")
        self.API_KEY: Dict[str, str] = {'X-API-key': str(parse['localhost']['API_KEY'])}
        self.url: str = str(parse['localhost']['url'])

    @abstractmethod
    def update_all_data(self, order_book: OrderBook, news_book: NewsBook) -> None:
        """
        Get data dynamically. Should be implemented by the subclass.
        Args:
            order_book (OrderBook): The order book to store the data.
            news_book (NewsBook): The news book to store the data.
        """
        pass

    def connect(self) -> None:
        """
        Connect to the server.
        """
        self.session = requests.Session()
        self.session.headers.update(self.API_KEY)

    def close(self) -> None:
        """
        Close the connection.
        """
        if self.session:
            self.session.close()

    def get_tick(self) -> int:
        """
        Returns the current 'tick' of the running case.
        Returns:
            int: Current tick.
        """
        resp = self.session.get(self.url + '/case')
        if resp.ok:
            case = resp.json()
            if case["status"] != "ACTIVE":
                self.end = True
            self.current_tick = case['tick']
            return case['tick']
        else:
            logger.error('Authorization error. please check API key.')
            raise ApiException('Authorization error. please check API key.')
    
    def get_heat_info(self) -> Dict[str, Any]:
        """
        get the new heat information of the case.

        :return: heat information
        """

        resp = self.session.get(self.url + "/case")
        if resp.ok:
            resp = resp.json()
            info = {
                "period": resp["period"],
                "ticks_per_period": resp["ticks_per_period"],
                "total_periods": resp["total_periods"],
                "status": resp["status"],
                "is_enforce_trading_limits": resp["is_enforce_trading_limits"],
            }
            return info
        else:
            logger.error('Authorization error. please check API key.')
            raise ApiException('Authorization error. please check API key.')
        
    
    @abstractmethod
    def get_news(self, news_book: NewsBook) -> None:
        """
        Get news if there is new one.
        Args:
            news_book (NewsBook): The news book to store the data.
        """
        pass


    def get_basic_security_info(self) -> Dict[str, Any]:
        """
        get the basic information of the security which will not change during the case.

        :return: basic information
        """

        resp = self.session.get(self.url + "/securities")
        if resp.ok:
            resp = resp.json()
            securities: Dict[str, Any] = {}
            for security in resp:
                securities[security["ticker"].upper()] = {
                    "currency": security["currency"],
                    "type": security["type"].upper(),
                    "limit_name": security["limits"][0]["name"],
                    "limit_unit": security["limits"][0]["units"],
                    "is_shortable": security["is_shortable"],
                    "is_tradeable": security["is_tradeable"],
                    "min_trade_size": security["min_trade_size"],
                    "max_trade_size": security["max_trade_size"],
                    "start_price": security["start_price"],
                    "position": security["position"],
                    "max_orders_per_second": security["api_orders_per_second"],
                    "trading_fee": security["trading_fee"],
                    "limit_order_rebate": security["limit_order_rebate"]
                }
            return securities
        else:
            logger.error('Authorization error. please check API key.')
            raise ApiException('Authorization error. please check API key.')
    
    def get_position_data(self) -> Dict[str, Any]:
        """
        get current positions of the case.

        :return: positions
        """
 
        resp = self.session.get(self.url + "/securities")
        if resp.ok:
            resp = resp.json()
            securities: Dict[str, Any] = {}
            for security in resp:
                securities[security["ticker"].upper()] = {
                    "vwap": security["vwap"],
                    "position": security["position"],
                    "nlv": security["nlv"],
                    "realized": security["realized"],
                    "unrealized": security["unrealized"],
                    "type": security["type"].lower()
                }
            return securities
        else:
            logger.error('Authorization error. please check API key.')
            raise ApiException('Authorization error. please check API key.')
    
    def check_order_status(self, order_id: int) -> Dict[str, Any]:
        """
        check the status of an order.

        :param order_id: The id of the order to check the status of.
        """
        resp = self.session.get(self.url + "/orders/" + str(order_id))
        if resp.status_code == 200:
            resp = resp.json()
            return resp
        else:
            logger.error(f"API error {resp.status_code}: {resp.json()}. Order status check failed.")
            return {}

    def ticker_bid_ask(self, 
                       ticker: str,
                       order_book: OrderBook):
        """
        get bid ask and volume. 

        :param ticker: the ticker of the security.
        :param order_book: the order book to store the data

        """

        payload = {"ticker": ticker.upper()}
        resp = self.session.get(self.url + "/securities/book", 
                                params=payload)

        if resp.ok:
            book = resp.json().copy()

            if len(book['bids']) != 0:
                for i in range(len(book['bids'])):
                    if book["bids"][i]["status"] == "OPEN":
                        order_book.insert_order(
                            Order(book["bids"][i]["price"], 
                                book["bids"][i]["quantity"],
                                filled_volume=book["bids"][i]["quantity_filled"],
                                order_type="bid",
                                timestamp=self.current_tick, 
                                id = book["bids"][i]["order_id"]))

            if len(book['asks']) != 0:
                for i in range(len(book['asks'])):
                    if book["asks"][i]["status"] == "OPEN":
                        order_book.insert_order(
                            Order(book["asks"][i]["price"], 
                                book["asks"][i]["quantity"],
                                filled_volume=book["asks"][i]["quantity_filled"],
                                order_type="ask",
                                timestamp=self.current_tick, 
                                id = book["asks"][i]["order_id"]))
        else:
            raise ApiException("Authorization error. \
                               please check API key.")
    
    
    def get_initial_limits(self):
        """
        get the limits of the case.

        :return: gross_limit, net_limit
        """

        resp = self.session.get(self.url + "/limits")
        
        if resp.ok:
            resp = resp.json()
            assets = {}
        
            for asset in resp:
                if "CASH" in asset["name"]:
                    assets["cash"] = {"gross_limit": asset["gross_limit"],
                                      "net_limit": asset["net_limit"]}
                elif "STOCK" in asset["name"]:
                    assets["stock"] = {"gross_limit": asset["gross_limit"],
                                        "net_limit": asset["net_limit"]}
                else:
                    assets[asset["name"]] = {"gross_limit": asset["gross_limit"],
                                                "net_limit": asset["net_limit"]}
            return assets
        else:
            raise ApiException("Authorization error. \
                               please check API key.")
    
    def get_limits(self,):
        """
        get the limits, total positions and current fine of portfolio

        :return: gross_limit, net_limit, 
                gross(position), net, 
                gross_fine, net_fine
        """

        resp = self.session.get(self.url + "/limits")

        if resp.ok:
            resp = resp.json()
            assets = {}
            for asset in resp:
                dict_ = {"gross_limit": asset["gross_limit"],
                                      "net_limit": asset["net_limit"],
                                      "gross": asset["gross"],
                                      "net": asset["net"],
                                      "gross_fine": asset["gross_fine"],
                                      "net_fine": asset["net_fine"]}
                
                if "CASH" in asset["name"]:
                    assets["cash"] = dict_
                elif "STOCK" in asset["name"] or "INDEX" in asset["name"]:
                    assets["stock"] = dict_

                else:
                    assets[asset["name"]] = dict_
    
            return assets 
        else:
            raise ApiException("Authorization error. \
                               please check API key.")

    def get_security_market_condition(self, 
                             ticker: str, 
                             order_book: OrderBook):
        """
        get the historical data of the security.
        including last price, best bid, best ask.

        :param ticker: the ticker of the security.
        :return: historical data
        """

        payload = {"ticker": ticker}
        resp = self.session.get(self.url + "/securities", 
                                params=payload)

        if resp.ok:
            data = resp.json()[0]
    
            order_book.update_price_history(data["last"], 
                                        data["bid"], 
                                        data["ask"],
                                        )
            order_book.update_liquidity(data["bid_size"],
                                        data["ask_size"])

        else:
            raise ApiException('Authorization error. please check API key.')
        
    
    def get_transactions_history(self, order_book: OrderBook, ticker: str, 
                                 after: int=None, period: int=None, limit: int=None):
        """
        get the transactions history of the case. (not limited to our transactions)

        :param after: Retrieve only data with an id value greater than this value.
        :param period: Period to retrieve data from. Defaults to the current period.
        :param limit: Ticks to include, counting backwards from the most recent tick. Defaults to retrieving the entire period.

        :return: transactions history
        """
        payload = {"ticker": ticker} 

        if after is not None:
            payload["after"] = after
        if period is not None:
            payload["period"] = period
        if limit is not None:
            payload["limit"] = limit

        resp = self.session.get(self.url + "/securities/tas",
                                params=payload)
        
        if resp.ok:
            transactions = resp.json()

            for transaction in transactions:
                order_book.record_transaction(transaction["id"],
                                               transaction["period"],
                                                  transaction["price"],
                                                    transaction["quantity"],
                                                    transaction["tick"])
            return transactions
                
        else:
            raise ApiException('Authorization error. please check API key.')
        
    def get_assets_log(self):
        """
        get the assets log of the case.

        :return: assets log
        """

        resp = self.session.get(self.url + "/assets/history")
        if resp.ok:
            assets = resp.json()
            return assets
        else:
            raise ApiException('Authorization error. please check API key.')
    
    def get_assets(self):
        """
        get the assets of the case.

        it's used to get lease, converter ratios but not for normal securities and currencies which are read in get_security_basic_info
            
        :return: assets
        """

        resp = self.session.get(self.url + "/assets")
        if resp.ok:
            resp = resp.json()

            assets = {}
            for asset in resp:
                assets[asset["ticker"]] = {"type": asset["type"],
                                           "total_quantity": asset["total_quantity"],
                                           "available_quantity": asset["available_quantity"],
                                           "is_available": asset["is_available"],
                                           "convert_to": asset["convert_to"],
                                           "convert_from": asset["convert_from"],
                                           "ticks_per_conversion": asset["ticks_per_conversion"],
                                           "ticks_per_lease": asset["ticks_per_lease"],
                                           "lease_price": asset["lease_price"],
                                           "description": asset["description"],
                                           "containment": asset["containment"],}
            return assets
        else:
            raise ApiException('Authorization error. please check API key.')

    def get_tenders(self, tender_book: TenderBook):
        """
        get the tenders of the security.

        :return: tenders
        """

        resp = self.session.get(self.url + "/tenders")
        if resp.ok:
            tenders = resp.json()
            
            if len(tenders) > 0:
                for tender in tenders:
                    if (tender["tender_id"] not in tender_book.tenders.keys()):
                        
                        tender_book.add_tender(Tender(tender["tender_id"],
                                                tender["ticker"],
                                                tender["quantity"],
                                                tender["price"],
                                                tender["action"],
                                                tender["tick"],
                                                tender["expires"], 
                                                fixed=tender["is_fixed_bid"]))
                    else:
                        pass # the tender has been read before. 
                
                # delete expired tenders
                expired = set(tender_book.tenders.keys()) - set([tender["tender_id"] for tender in tenders])
                if len(expired) != 0:
                    for tender_id in expired:
                        tender_book.delete_tender(tender_id)

            else:
                tender_book.clear_tenders() # the tender is expired. no valid tender now.

        else:
            raise ApiException('Authorization error. please check API key.')
        
    
    def get_leases(self):
        """
        get the leases of the case.

        :return: leases
        """

        resp = self.session.get(self.url + "/leases")
        if resp.ok:
            leases = resp.json()
            print(leases)
            return leases
        else:
            raise ApiException('Authorization error. please check API key.')
        
