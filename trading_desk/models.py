from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Literal, Optional


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    price: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "market_cache"


@dataclass(frozen=True)
class VirtualOrderRequest:
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    idempotency_key: str
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class OrderFillReceipt:
    order_id: str
    idempotency_key: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    fill_price: float
    notional_value: float
    status: Literal["FILLED", "REJECTED", "DEDUPLICATED"]
    reason: Optional[str] = None
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Position:
    symbol: str
    quantity: float
    average_cost: float


@dataclass
class PortfolioLedgerState:
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    marked_holdings: float = 0.0
    total_equity: float = 0.0

    def validate_invariant(self, tolerance: float = 1e-6) -> bool:
        return abs((self.cash + self.marked_holdings) - self.total_equity) <= tolerance


Quote = QuoteSnapshot
OrderRequest = VirtualOrderRequest
OrderResult = OrderFillReceipt
