"""
ALGODataFetcher: Specialized data fetcher for algorithmic trading.

This module provides a class for updating multiple order books and a tender book with the latest market data from a trading server. It is designed to be used in algorithmic trading systems and extends ClientDataFetcher with additional logic for handling multiple securities and currencies.

Features:
    - Updates order books for multiple tickers
    - Fetches bid/ask, market conditions, and transaction history
    - Handles tender book updates
    - Uses robust error handling and logging
"""
import logging
from RITC.datafetcher.ClientDataFetcher import ClientDataFetcher

logger = logging.getLogger(__name__)


class ALGODataFetcher(ClientDataFetcher):
    """
    Data fetcher for algorithmic trading. Updates multiple order books and tender book with latest market data.
    """
    def update_market_data(
        self,
        order_books: dict,
        tender_book: 'Tender'
    ) -> None:
        """
        Get data dynamically and update books.
        Args:
            order_books (dict): Dictionary mapping ticker names to OrderBook objects.
            tender_book (Tender): Tender book object.
        """
        tick = self.get_tick()
        self.current_tick = tick

        # List of tickers and their corresponding keys in order_books
        tickers = [
            "SAD", "CRY", "ANGER", "FEAR", "JOY_C", "JOY_U", "USD", "CAD"
        ]

        # Clear all order books
        for ticker in tickers:
            try:
                order_books[ticker].clear_orders()
            except Exception as e:
                logger.warning(f"Failed to clear orders for {ticker}: {e}")

        # Update bid/ask for all tickers
        for ticker in tickers:
            try:
                self.ticker_bid_ask(ticker, order_books[ticker])
            except Exception as e:
                logger.warning(f"Failed to update bid/ask for {ticker}: {e}")

        # Update last price and best bid/ask
        for ticker in tickers:
            try:
                self.get_security_market_condition(ticker, order_books[ticker])
            except Exception as e:
                logger.warning(f"Failed to update market condition for {ticker}: {e}")

        # Update transaction history
        for ticker in tickers:
            try:
                order_book = order_books[ticker]
                last_key = max(order_book.transaction_history.keys()) if order_book.transaction_history else None
                self.get_transactions_history(order_book, ticker, last_key)
            except Exception as e:
                logger.warning(f"Failed to update transaction history for {ticker}: {e}")

        # Update tenders
        try:
            self.get_tenders(tender_book)
        except Exception as e:
            logger.warning(f"Failed to update tenders: {e}")


