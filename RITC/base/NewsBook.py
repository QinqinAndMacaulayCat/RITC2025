
"""

This module provides two main classes:
1. `NewsBook` for managing and storing news items, including CSV input/output.
2. `TenderBook` for managing buy/sell tenders submitted by agents, including expiry management.

Classes:
    - NewsBook: Stores news items with title, content, and tick.
    - Tender: Represents a buy/sell offer with volume, price, and expiry.
    - TenderBook: Tracks all tenders (historical and active) and handles expiry cleanup.
"""

import csv
from dataclasses import dataclass


class NewsBook:
    """Manages storage and access of news items."""

    def __init__(self):
        self.news_items = []
        self.news_number = 0

    def add_news(self, title: str, content: str, tick: int):
        """Adds a news item to the book.

        Args:
            title (str): Title of the news.
            content (str): Content of the news.
            tick (int): Tick at which the news was released.
        """
        self.news_items.append({
            "title": title,
            "content": content,
            "tick": tick
        })
        self.news_number += 1

    def get_all_news(self):
        """Returns all stored news items.

        Returns:
            list[dict]: List of news dictionaries with keys 'title', 'content', and 'tick'.
        """
        return self.news_items

    def save_to_csv(self, file_path: str):
        """Saves all news items to a CSV file.

        Args:
            file_path (str): Path to the CSV file to save.
        """
        with open(file_path, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=["title", "content", "tick"])
            writer.writeheader()
            writer.writerows(self.news_items)

    def load_from_csv(self, file_path: str):
        """Loads news items from a CSV file.

        Args:
            file_path (str): Path to the CSV file to load.
        """
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            self.news_items = list(reader)
            self.news_number = len(self.news_items)


@dataclass
class Tender:
    """Represents a buy/sell offer (tender) submitted by an agent.

    Attributes:
        id (str): Unique identifier for the tender.
        ticker (str): Ticker symbol of the security.
        volume (int): Number of shares.
        price (float): Price per share.
        action (str): 'BUY' or 'SELL'.
        tick (int): Tick when submitted.
        expire (int): Tick when the tender expires.
        fixed (bool): Whether the price is fixed or submitted.
    """

    id: str
    ticker: str
    volume: int
    price: float
    action: str
    tick: int
    expire: int
    fixed: bool = True

    def __post_init__(self):
        self.valid = (self.tick < self.expire)

    def __str__(self):
        return (
            f"Tender {self.id}: {self.action} {self.volume} shares of "
            f"{self.ticker} at {self.price} until tick {self.expire}"
        )


class TenderBook:
    """Manages historical and current tenders."""

    def __init__(self):
        self.history_tenders = {}  # All tenders ever added
        self.tenders = {}  # Currently valid tenders

    def add_tender(self, tender: Tender):
        """Adds a tender to the book.

        Args:
            tender (Tender): Tender object to be added.
        """
        self.tenders[tender.id] = tender
        self.history_tenders[tender.id] = tender

    def delete_tender(self, tender_id: str):
        """Deletes a tender by ID.

        Args:
            tender_id (str): ID of the tender to delete.
        """
        if tender_id in self.tenders:
            del self.tenders[tender_id]
        else:
            print("Tender not found.")

    def clear_tenders(self):
        """Clears all currently valid tenders."""
        self.tenders = {}

    def clear_expired_tenders(self, current_tick: int):
        """Removes expired tenders based on current tick.

        Args:
            current_tick (int): Current time tick.
        """
        self.tenders = {
            tid: tender for tid, tender in self.tenders.items()
            if tender.expire >= current_tick
        }
