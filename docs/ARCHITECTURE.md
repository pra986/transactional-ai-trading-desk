# Architecture: Transactional AI Trading Desk

## Overview
A simulated AI trading workstation enforcing deterministic financial invariants:
- **SSE Quote Streaming**: Simulated market ticks with explicit timestamp and TTL (`QUOTE_TTL_SECONDS`).
- **Quote Freshness Guard**: Rejects order execution if the referenced quote age exceeds TTL.
- **REST Order Idempotency**: Every order submission requires an `idempotency_key`; duplicate keys return the original committed order without double-charging.
- **Atomic SQLite Ledger**: Cash debits/credits, position updates, and order records commit inside a single `BEGIN IMMEDIATE` SQLite transaction.

## Components
- `trading_desk/models.py`: Pydantic-free/stdlib dataclasses for `Quote`, `OrderRequest`, `OrderResult`, and `Position`.
- `trading_desk/engine.py`: `TradingDeskEngine` managing SQLite schema, quote cache, TTL checks, idempotency table, and atomic execution.
- `trading_desk/cli.py`: CLI entrypoint for running quotes, orders, and ledger inspection.
- `evaluation/eval_cases.json`: Golden test cases covering stale quotes, duplicate idempotency keys, insufficient funds, and valid fills.
