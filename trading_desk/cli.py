from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from trading_desk.engine import TransactionalTradingDeskEngine
from trading_desk.models import QuoteSnapshot, VirtualOrderRequest


def run_demo(initial_cash: float = 100_000.0, quote_ttl_seconds: float = 30.0) -> None:
    engine = TransactionalTradingDeskEngine(
        initial_cash=initial_cash,
        quote_ttl_seconds=quote_ttl_seconds,
    )
    now = datetime.now(timezone.utc)

    engine.update_quote(QuoteSnapshot(symbol="AAPL", price=200.0, timestamp=now))
    engine.update_quote(QuoteSnapshot(symbol="MSFT", price=400.0, timestamp=now - timedelta(seconds=60)))

    buy_req = VirtualOrderRequest(symbol="AAPL", side="BUY", quantity=10, idempotency_key="demo-buy-1", submitted_at=now)
    print("BUY 10 AAPL:", engine.submit_order(buy_req, now=now))
    print("DUPLICATE BUY:", engine.submit_order(buy_req, now=now))

    stale_req = VirtualOrderRequest(symbol="MSFT", side="BUY", quantity=5, idempotency_key="demo-stale-1", submitted_at=now)
    print("STALE MSFT BUY:", engine.submit_order(stale_req, now=now))

    ledger = engine.get_ledger_state()
    print(
        f"Ledger -> cash={ledger.cash:.2f}, marked_holdings={ledger.marked_holdings:.2f}, "
        f"total_equity={ledger.total_equity:.2f}, invariant_ok={ledger.validate_invariant()}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Transactional AI Trading Desk CLI Demo")
    parser.add_argument("--cash", type=float, default=100_000.0, help="Initial cash balance")
    parser.add_argument("--ttl", type=float, default=30.0, help="Quote freshness TTL in seconds")
    args = parser.parse_args()
    run_demo(initial_cash=args.cash, quote_ttl_seconds=args.ttl)


if __name__ == "__main__":
    main()
