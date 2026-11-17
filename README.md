# Transactional AI Trading Desk (Project 15)

Simulated AI trading workstation with SSE quote streaming, REST order idempotency keys, quote freshness TTLs, and atomic SQLite ledger invariants.

## Attribution
Inspired by and attributed to [ed-donner/finally](https://github.com/ed-donner/finally) (C4: AI Coder - FinAlly trading workstation).

## Architecture
- **Quote Streamer (SSE)**: Streams live simulated market quotes with monotonic timestamps and configurable freshness TTLs.
- **Order Router (REST)**: Validates `Idempotency-Key` headers to guarantee at-most-once execution across network retries.
- **Ledger Engine (SQLite)**: Enforces atomic `BEGIN IMMEDIATE` transactions for cash, positions, and realized P&L invariants.
- **AI Desk Assistant**: Advises on portfolio exposure and order sizing within deterministic risk guardrails.

## 6-Stage Workflow
1. **Subscribe**: Client connects to SSE quote stream for watchlisted tickers.
2. **Validate Freshness**: Engine rejects orders referencing quotes older than `QUOTE_TTL_SECONDS`.
3. **Deduplicate**: REST endpoint checks `idempotency_keys` table before execution.
4. **Risk Check**: Verifies sufficient cash (BUY) or settled shares (SELL).
5. **Atomic Commit**: Updates `accounts`, `positions`, and `orders` in a single SQLite transaction.
6. **Broadcast**: Emits updated portfolio snapshot and execution receipt.

## Data Contract
- `Quote(symbol, bid, ask, timestamp_ms, ttl_ms)`
- `OrderRequest(idempotency_key, account_id, symbol, side, qty, quoted_price, quote_ts_ms)`
- `OrderReceipt(order_id, idempotency_key, status, filled_price, cash_balance, replay)`

## Production Controls
- Quote freshness TTL enforcement (`StaleQuoteError`)
- Idempotent REST order submission (`Idempotency-Key` replay returns original receipt)
- Atomic SQLite ledger invariants (no negative cash, no naked short positions)

## Local Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -v
python -m trading_desk.cli
```
