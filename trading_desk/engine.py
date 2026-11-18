from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

from trading_desk.models import (
    OrderFillReceipt,
    PortfolioLedgerState,
    Position,
    QuoteSnapshot,
    VirtualOrderRequest,
)


class TransactionalTradingDeskEngine:
    """Deterministic virtual trading desk engine enforcing TTL, idempotency, and accounting invariants."""

    def __init__(self, initial_cash: float = 100_000.0, quote_ttl_seconds: float = 30.0) -> None:
        if initial_cash < 0:
            raise ValueError("initial_cash must be non-negative")
        if quote_ttl_seconds <= 0:
            raise ValueError("quote_ttl_seconds must be positive")
        self.cash: float = round(float(initial_cash), 6)
        self.quote_ttl_seconds: float = float(quote_ttl_seconds)
        self.positions: Dict[str, Position] = {}
        self._quotes: Dict[str, QuoteSnapshot] = {}
        self._idempotency_cache: Dict[str, OrderFillReceipt] = {}

    def update_quote(self, quote: QuoteSnapshot) -> None:
        if quote.price <= 0:
            raise ValueError("Quote price must be positive")
        self._quotes[quote.symbol.upper()] = quote

    def get_quote(self, symbol: str) -> Optional[QuoteSnapshot]:
        return self._quotes.get(symbol.upper())

    def _is_quote_fresh(self, quote: QuoteSnapshot, now: Optional[datetime] = None) -> bool:
        current_time = now or datetime.now(timezone.utc)
        quote_ts = quote.timestamp
        if quote_ts.tzinfo is None:
            quote_ts = quote_ts.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        age_seconds = (current_time - quote_ts).total_seconds()
        return 0 <= age_seconds <= self.quote_ttl_seconds

    def submit_order(
        self,
        request: VirtualOrderRequest,
        now: Optional[datetime] = None,
    ) -> OrderFillReceipt:
        if request.idempotency_key in self._idempotency_cache:
            cached = self._idempotency_cache[request.idempotency_key]
            return OrderFillReceipt(
                order_id=cached.order_id,
                idempotency_key=cached.idempotency_key,
                symbol=cached.symbol,
                side=cached.side,
                quantity=cached.quantity,
                fill_price=cached.fill_price,
                notional_value=cached.notional_value,
                status="DEDUPLICATED",
                reason=f"Duplicate idempotency key: {request.idempotency_key}",
                executed_at=cached.executed_at,
            )

        symbol = request.symbol.upper()
        exec_time = now or datetime.now(timezone.utc)

        if request.quantity <= 0:
            return self._record_rejection(request, symbol, 0.0, "Order quantity must be positive", exec_time)

        quote = self._quotes.get(symbol)
        if quote is None:
            return self._record_rejection(request, symbol, 0.0, f"No quote available for {symbol}", exec_time)

        if not self._is_quote_fresh(quote, now=exec_time):
            return self._record_rejection(
                request,
                symbol,
                quote.price,
                f"Stale quote for {symbol}: exceeded TTL of {self.quote_ttl_seconds}s",
                exec_time,
            )

        notional = round(request.quantity * quote.price, 6)

        if request.side == "BUY":
            if notional > self.cash + 1e-9:
                return self._record_rejection(
                    request,
                    symbol,
                    quote.price,
                    f"Insufficient cash: required {notional:.2f}, available {self.cash:.2f}",
                    exec_time,
                )
            self.cash = round(self.cash - notional, 6)
            existing = self.positions.get(symbol)
            if existing:
                new_qty = existing.quantity + request.quantity
                new_avg = ((existing.quantity * existing.average_cost) + notional) / new_qty
                existing.quantity = new_qty
                existing.average_cost = round(new_avg, 6)
            else:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=request.quantity,
                    average_cost=quote.price,
                )
        elif request.side == "SELL":
            existing = self.positions.get(symbol)
            held_qty = existing.quantity if existing else 0.0
            if request.quantity > held_qty + 1e-9:
                return self._record_rejection(
                    request,
                    symbol,
                    quote.price,
                    f"Short-sell rejected: requested {request.quantity}, held {held_qty}",
                    exec_time,
                )
            self.cash = round(self.cash + notional, 6)
            remaining = round(held_qty - request.quantity, 6)
            if remaining <= 1e-9:
                self.positions.pop(symbol, None)
            else:
                existing.quantity = remaining
        else:
            return self._record_rejection(request, symbol, quote.price, f"Unsupported side: {request.side}", exec_time)

        receipt = OrderFillReceipt(
            order_id=f"ord_{uuid.uuid4().hex[:12]}",
            idempotency_key=request.idempotency_key,
            symbol=symbol,
            side=request.side,
            quantity=request.quantity,
            fill_price=quote.price,
            notional_value=notional,
            status="FILLED",
            executed_at=exec_time,
        )
        self._idempotency_cache[request.idempotency_key] = receipt
        return receipt

    def _record_rejection(
        self,
        request: VirtualOrderRequest,
        symbol: str,
        price: float,
        reason: str,
        exec_time: datetime,
    ) -> OrderFillReceipt:
        receipt = OrderFillReceipt(
            order_id=f"rej_{uuid.uuid4().hex[:12]}",
            idempotency_key=request.idempotency_key,
            symbol=symbol,
            side=request.side,
            quantity=request.quantity,
            fill_price=price,
            notional_value=0.0,
            status="REJECTED",
            reason=reason,
            executed_at=exec_time,
        )
        self._idempotency_cache[request.idempotency_key] = receipt
        return receipt

    def get_ledger_state(self) -> PortfolioLedgerState:
        marked_holdings = 0.0
        for symbol, pos in self.positions.items():
            quote = self._quotes.get(symbol)
            mark_price = quote.price if quote else pos.average_cost
            marked_holdings += pos.quantity * mark_price
        marked_holdings = round(marked_holdings, 6)
        total_equity = round(self.cash + marked_holdings, 6)
        state = PortfolioLedgerState(
            cash=self.cash,
            positions=dict(self.positions),
            marked_holdings=marked_holdings,
            total_equity=total_equity,
        )
        assert state.validate_invariant(), "Accounting invariant violated: cash + marked_holdings != total_equity"
        return state


TradingDeskEngine = TransactionalTradingDeskEngine
