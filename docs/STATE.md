# STATE — living session handoff

Read first; update before finishing.

**Last updated:** 2026-07-18  **Phase:** Phase 1 step 1 — data pipeline foundation landed; universe builder next

## Now / in progress
Branch `feat/data-pipeline` (uncommitted). Data-layer foundation built + tested (28 tests, incl. live network integration). Not yet: aggregator cross-check, `data/ohlcv.py`, `data/universe.py`, hash-locked snapshot.

**Shipped this session:**
- `pyproject.toml` (stdlib-only core so the data layer runs with no heavy install; quant deps behind `[quant]` extra, `purgedcv==0.1.2` pinned).
- `gqrp/config.py` — declared constants (cost model, dev/val/holdout windows per D10, liquidity floor, stablecoin/wrapped exclusions, quote-asset list).
- `gqrp/data/types.py` — frozen `OhlcvBar` (+`is_partial`, `date`) and `SymbolLifecycle` (+`was_tradable_on` PIT check).
- `gqrp/data/binance_source.py` — vendor-isolated adapter (seam 5): S3 REST listing, monthly-zip download, **per-file SHA-256 `.CHECKSUM` verification**, CSV parse (header-tolerant), optional disk cache.
- `gqrp/data/lifecycle.py` — `classify_symbol` (base/quote/stablecoin/wrapped), `infer_delisting_date` (partial-final-bar OR stale coverage), `build_lifecycle`.
- `tests/` — 27 offline unit tests + 1 `@network` integration test reproducing the GATE 0 SRMUSDT verdict end-to-end. All pass; ruff clean.

**Verification bar met (CLAUDE.md):** `SymbolLifecycle.was_tradable_on` returns True through `delisting_date` and False after — a delisted asset stays in the universe until it died. Locked by `test_types.test_lifecycle_tradable_window`. Live checksum-verified sourcing confirmed by `pytest -m network`.

## Next concrete step
Continue Phase 1 step 1:
1. `data/ohlcv.py` — delisting-aware bar loading that consumes `symbol_lifecycle` (drop bars after `delisting_date`; never fabricate post-delisting data).
2. Aggregator cross-check in `data/lifecycle.py` (CoinGecko) → set `verified=True` / `source='aggregator-crosscheck'` where confirmed; recall from GATE 0 that CoinGecko gives existence only, not lifecycle dates + 365-day free cap — so cross-check is existence/plausibility, not date-sourcing.
3. `data/universe.py` — monthly PIT ranking + liquidity floor + exclusions → **immutable hash-locked `universe_snapshot`** (spec §A).
4. `scripts/build_universe.py` driver.
Session note: this is the data/universe track (session-split rule) — registry + backtest are separate sessions.

## Open / unresolved
- None blocking. (O1, O2 resolved 2026-07-18 — see decisions.md.)

## Done (resolved — see decisions.md)
- Stack: Python 3.11+, vectorbt (open), ccxt, purgedcv, SQLite/WAL registry (D1–D5).
- mlfinlab banned (paid); purgedcv adopted for CPCV + deflated/probabilistic Sharpe.
- Data ground truth = `data.binance.vision` + Binance announcements; aggregators cross-check only.
- Registry immutability + holdout access = structural/OS-level, not policy (D4, D6).
- Agent layer deferred to Phase 2; human is research agent (D9). Holdout window fixed & locked (D10).
- Forward-compat seams named (architecture.md): registry process, run-type→N, role interfaces, Window object, data-source adapter, engine wrapper.

## Session log (newest last)
- **2026-07-18** — **Phase 1 step 1 foundation.** Branch `feat/data-pipeline`. Built config + data domain types + Binance-native adapter (checksum-verified, vendor-isolated per seam 5) + lifecycle construction. 28 tests (27 offline + 1 live network reproducing GATE 0), ruff clean. Data layer is stdlib-only so it runs without vectorbt/ccxt. Next: `data/ohlcv.py` (delisting-aware loading), aggregator cross-check, `data/universe.py` (hash-locked snapshot). Not committed.
- **2026-07-18** — **GATE 0 PASSED.** Spiked delisted SRMUSDT against `data.binance.vision`: full daily klines, all `.CHECKSUM` (SHA-256) OK, coverage 2020-08-11 → 2022-11-28. Edges match exchange truth exactly — first bar = Binance listing date; partial final bar (open 00:00, close 02:59 UTC 2022-11-28) = intraday halt per the 2022-11-25 delisting announcement (SRM/USDT terminated 2022-11-28). CoinGecko cross-check: token exists but no lifecycle dates + 365-day free-history cap → can't source the window, exactly the gap D5 assumes. Resolved O1: purgedcv MIT, v0.1.2. Recorded D11; O1/O2 closed. Next: Phase 1 step 1 (universe/data pipeline).
- **2026-07-18** — Kickoff: imprinted the v3 handoff spec (personal research project → market phase skipped). Focused prior-art run: verified vectorbt open vs pro, found `purgedcv` (open CPCV+DSR+PSR, replaces banned mlfinlab), confirmed ccxt's survivorship gap → `data.binance.vision` as primary source. Scaffolded spec/decisions/prior-art/architecture/roadmap + AGENTS/CLAUDE. Added the two pieces the handoff spec lacked: data model (spec §A) + module layout (spec §B). Next: run GATE 0 data-sourcing spike before any code.
