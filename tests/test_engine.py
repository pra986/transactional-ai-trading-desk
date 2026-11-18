from datetime import datetime, timedelta, timezone

from trading_desk.engine import TransactionalTradingDeskEngine
from trading_desk.models import QuoteSnapshot, VirtualOrderRequest


def test_insufficient_cash_rejected() -> None:
    now = datetime.now(timezone.utc)
    engine = TransactionalTradingDeskEngine(initial_cash=1_000.0, quote_ttl_seconds=30.0)
    engine.update_quote(QuoteSnapshot(symbol="AAPL", price=200.0, timestamp=now))

    req = VirtualOrderRequest(symbol="AAPL", side="BUY", quantity=10, idempotency_key="k-cash", submitted_at=now)
    receipt = engine.submit_order(req, now=now)

    assert receipt.status == "REJECTED"
    assert "Insufficient cash" in (receipt.reason or "")
    assert engine.get_ledger_state().cash == 1_000.0


def test_short_sell_rejected() -> None:
    now = datetime.now(timezone.utc)
    engine = TransactionalTradingDeskEngine(initial_cash=10_000.0, quote_ttl_seconds=30.0)
    engine.update_quote(QuoteSnapshot(symbol="AAPL", price=200.0, timestamp=now))

    req = VirtualOrderRequest(symbol="AAPL", side="SELL", quantity=5, idempotency_key="k-short", submitted_at=now)
    receipt = engine.submit_order(req, now=now)

    assert receipt.status == "REJECTED"
    assert "Short-sell rejected" in (receipt.reason or "")


def test_duplicate_idempotency_key_deduplicated() -> None:
    now = datetime.now(timezone.utc)
    engine = TransactionalTradingDeskEngine(initial_cash=10_000.0, quote_ttl_seconds=30.0)
    engine.update_quote(QuoteSnapshot(symbol="AAPL", price=100.0, timestamp=now))

    req = VirtualOrderRequest(symbol="AAPL", side="BUY", quantity=5, idempotency_key="k-dup", submitted_at=now)
    first = engine.submit_order(req, now=now)
    second = engine.submit_order(req, now=now)

    assert first.status == "FILLED"
    assert second.status == "DEDUPLICATED"
    assert second.order_id == first.order_id
    assert engine.get_ledger_state().cash == 9_500.0


def test_stale_price_cache_rejected() -> None:
    now = datetime.now(timezone.utc)
    engine = TransactionalTradingDeskEngine(initial_cash=10_000.0, quote_ttl_seconds=30.0)
    engine.update_quote(QuoteSnapshot(symbol="MSFT", price=400.0, timestamp=now - timedelta(seconds=31)))

    req = VirtualOrderRequest(symbol="MSFT", side="BUY", quantity=1, idempotency_key="k-stale", submitted_at=now)
    receipt = engine.submit_order(req, now=now)

    assert receipt.status == "REJECTED"
    assert "Stale quote" in (receipt.reason or "")


def test_accounting_invariant_cash_plus_marked_holdings_equals_total_equity() -> None:
    now = datetime.now(timezone.utc)
    engine = TransactionalTradingDeskEngine(initial_cash=10_000.0, quote_ttl_seconds=30.0)
    engine.update_quote(QuoteSnapshot(symbol="AAPL", price=100.0, timestamp=now))

    buy_req = VirtualOrderRequest(symbol="AAPL", side="BUY", quantity=20, idempotency_key="k-inv-buy", submitted_at=now)
    assert engine.submit_order(buy_req, now=now).status == "FILLED"

    engine.update_quote(QuoteSnapshot(symbol="AAPL", price=125.0, timestamp=now + timedelta(seconds=5)))
    ledger = engine.get_ledger_state()

    assert ledger.cash == 8_000.0
    assert ledger.marked_holdings == 2_500.0
    assert ledger.total_equity == 10_500.0
    assert ledger.cash + ledger.marked_holdings == ledger.total_equity
    assert ledger.validate_invariant()
