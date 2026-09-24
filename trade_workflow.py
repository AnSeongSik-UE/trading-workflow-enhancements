"""Synthetic example of trade history formatting and exit-signal decisions.

This module has no brokerage connection and never places an order.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol


def parse_api_amount(value: object) -> int:
    """Treat an empty API amount as zero; reject unexpected nonnumeric data."""
    if value is None or str(value).strip() == "":
        return 0
    try:
        return int(str(value).replace(",", "").strip())
    except ValueError as exc:
        raise ValueError("The API amount must be an integer") from exc


def format_amount(value: int) -> str:
    return f"{value:,}"


@dataclass(frozen=True)
class HistoryRow:
    day: date
    buy_amount: int
    sell_amount: int
    realized_result: int
    fee: int
    tax: int


@dataclass(frozen=True)
class HistoryView:
    rows: tuple[HistoryRow, ...]
    total_buy: str
    total_sell: str
    total_realized: str
    total_cost: str


class HistoryClient(Protocol):
    def fetch_daily_history(self, start: date, end: date) -> list[dict[str, object]]:
        """Return daily records without exposing any account identifier."""


def load_history(client: HistoryClient, start: date, end: date) -> HistoryView:
    """Request a date range and prepare values for a UI history table."""
    if start > end:
        raise ValueError("The start date must not be later than the end date")

    rows = tuple(
        HistoryRow(
            day=date.fromisoformat(str(raw["day"])),
            buy_amount=parse_api_amount(raw.get("buy_amount")),
            sell_amount=parse_api_amount(raw.get("sell_amount")),
            realized_result=parse_api_amount(raw.get("realized_result")),
            fee=parse_api_amount(raw.get("fee")),
            tax=parse_api_amount(raw.get("tax")),
        )
        for raw in client.fetch_daily_history(start, end)
    )

    return HistoryView(
        rows=rows,
        total_buy=format_amount(sum(row.buy_amount for row in rows)),
        total_sell=format_amount(sum(row.sell_amount for row in rows)),
        total_realized=format_amount(sum(row.realized_result for row in rows)),
        total_cost=format_amount(sum(row.fee + row.tax for row in rows)),
    )


@dataclass(frozen=True)
class ExitSignal:
    reason: str
    quantity: int


def decide_exit(
    profit_rate: Decimal,
    stop_loss: Decimal,
    take_profit: Decimal,
    quantity: int,
) -> ExitSignal | None:
    """Return an intent only. A caller must separately review any real order."""
    try:
        profit_rate = Decimal(profit_rate)
        stop_loss = Decimal(stop_loss)
        take_profit = Decimal(take_profit)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Rates must be numeric") from exc
    if not all(rate.is_finite() for rate in (profit_rate, stop_loss, take_profit)):
        raise ValueError("Rates must be finite")
    if stop_loss >= 0 or take_profit <= 0:
        raise ValueError("Use a negative stop-loss and a positive take-profit")
    if quantity <= 0:
        raise ValueError("Quantity must be positive")

    if profit_rate < stop_loss:
        return ExitSignal("stop_loss", quantity)
    if profit_rate > take_profit:
        return ExitSignal("take_profit", quantity)
    return None


class DemoHistoryClient:
    """Fixed sample values; this class does not call a network API."""

    def fetch_daily_history(self, start: date, end: date) -> list[dict[str, object]]:
        sample = [
            {
                "day": "2026-01-02",
                "buy_amount": "120000",
                "sell_amount": "124000",
                "realized_result": "4000",
                "fee": "100",
                "tax": "200",
            },
            {
                "day": "2026-01-05",
                "buy_amount": "80000",
                "sell_amount": "79000",
                "realized_result": "-1000",
                "fee": "100",
                "tax": "100",
            },
        ]
        return [row for row in sample if start <= date.fromisoformat(str(row["day"])) <= end]


if __name__ == "__main__":
    view = load_history(DemoHistoryClient(), date(2026, 1, 1), date(2026, 1, 31))
    print("Daily records:", len(view.rows))
    print("Realized result:", view.total_realized)
    print("Fees and tax:", view.total_cost)
    print("Example exit intent:", decide_exit(Decimal("-3"), Decimal("-2"), Decimal("5"), 1))

