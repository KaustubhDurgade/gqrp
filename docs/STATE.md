# STATE — living session handoff

Read first; update before finishing.

**Last updated:** 2026-07-18  **Phase:** Phase 1 step 1 COMPLETE — universe pipeline end-to-end; registry track next

## Now / in progress
Branch `feat/data-pipeline` (3 commits). **Phase 1 step 1 done.** Universe + delisting-aware data pipeline with aggregator cross-check, all proven on live data. Next heavy track = the trial registry (separate session).

**Shipped (step 1):**
- `config.py`, `data/types.py` (`OhlcvBar`, `SymbolLifecycle`, `UniverseRow`, `UniverseSnapshot`).
- `data/binance_source.py` — checksum-verified adapter + `list_all_symbols` (survivorship-safe discovery, paginated).
- `data/lifecycle.py` — lifecycle construction.
- `data/ohlcv.py` — delisting-aware loading (`filter_to_lifecycle`, `average_daily_quote_volume`, both PIT).
- `data/universe.py` — PIT ranking by avg daily quote volume (D12), liquidity floor, stablecoin/wrapped/quote exclusions, **hash-locked immutable snapshot** (0444, content-hash verified on load, refuses overwrite).
- `data/coingecko.py` + `lifecycle.cross_check_existence` — aggregator existence corroboration → sets `verified` (D5; never sources dates). Immutable (`dataclasses.replace`).
- `scripts/build_universe.py` — driver; caps all fetches to pre-holdout months + uses HOLDOUT_START as lifecycle horizon (interim D6 stand-in), refuses `--end` in holdout.
- `tests/` — **54 offline + 1 `@network`**; ruff clean.

**Verification (live evidence this session):**
- Delisting-aware: SRMUSDT (died 2022-11-28) is rank 1 in the 2021-06 snapshot, **rows=0** in 2022-12. No survivorship.
- Immutability: written snapshot is `-r--r--r--`; re-running the same month raises `FileExistsError`; load recomputes+verifies `content_hash`.
- Checksum-verified sourcing confirmed via `pytest -m network`.

## Next concrete step
Start **Phase 1 step 2 — the trial registry** (spec §6, §A; decisions D4, D7). New session (session-split rule). Build:
1. `registry/schema.sql` — append-only `trial` + `trial_result` tables, `research_memo`, `negative_knowledge`; `BEFORE UPDATE`/`BEFORE DELETE` triggers that `RAISE(ABORT)`.
2. `registry/server.py` — standalone append-only writer daemon (the only writer).
3. `registry/client.py` — read-only client; cumulative weighted N = Σ weight where `run_type='research'`, computed live.
4. Enforce config-before-results (separate `trial` then `trial_result` writes) + run-type tagging with no retag path (D7).
Verification bar (CLAUDE.md): prove immutability by showing an UPDATE being rejected.
Non-blocking data-pipeline follow-ups (do only if needed): `--cross-check` flag in the driver; parallel history downloads (full-discovery run is slow — the §2.1 "budget weeks" cost).

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
- **2026-07-18** — **Phase 1 step 1 COMPLETE.** Added `data/coingecko.py` + `lifecycle.cross_check_existence` (aggregator existence corroboration → `verified`, D5; immutable). Live smoke: 13,696 CoinGecko symbols, SRM verified True, fake asset False. 54 offline + 1 network test, ruff clean. Universe pipeline done end-to-end (sourcing → lifecycle → PIT ranking → hash-locked immutable snapshot → cross-check). Next: registry track (step 2).
- **2026-07-18** — **Phase 1 step 1 near-complete.** Added `data/ohlcv.py` (delisting-aware, PIT), `data/universe.py` (PIT ranking + hash-locked immutable snapshot), `binance_source.list_all_symbols` (paginated discovery), `scripts/build_universe.py` driver (holdout-capped). Decision D12: rank by avg daily quote volume, not reconstructed market cap (user deferred; chosen for D5/D8 consistency). 48 offline + 1 network test, ruff clean. Proved delisting-awareness + immutability on live SRMUSDT data. Remaining step-1 item: aggregator cross-check. Then registry track.
- **2026-07-18** — **Phase 1 step 1 foundation.** Branch `feat/data-pipeline`. Built config + data domain types + Binance-native adapter (checksum-verified, vendor-isolated per seam 5) + lifecycle construction. 28 tests (27 offline + 1 live network reproducing GATE 0), ruff clean. Data layer is stdlib-only so it runs without vectorbt/ccxt. Next: `data/ohlcv.py` (delisting-aware loading), aggregator cross-check, `data/universe.py` (hash-locked snapshot). Not committed.
- **2026-07-18** — **GATE 0 PASSED.** Spiked delisted SRMUSDT against `data.binance.vision`: full daily klines, all `.CHECKSUM` (SHA-256) OK, coverage 2020-08-11 → 2022-11-28. Edges match exchange truth exactly — first bar = Binance listing date; partial final bar (open 00:00, close 02:59 UTC 2022-11-28) = intraday halt per the 2022-11-25 delisting announcement (SRM/USDT terminated 2022-11-28). CoinGecko cross-check: token exists but no lifecycle dates + 365-day free-history cap → can't source the window, exactly the gap D5 assumes. Resolved O1: purgedcv MIT, v0.1.2. Recorded D11; O1/O2 closed. Next: Phase 1 step 1 (universe/data pipeline).
- **2026-07-18** — Kickoff: imprinted the v3 handoff spec (personal research project → market phase skipped). Focused prior-art run: verified vectorbt open vs pro, found `purgedcv` (open CPCV+DSR+PSR, replaces banned mlfinlab), confirmed ccxt's survivorship gap → `data.binance.vision` as primary source. Scaffolded spec/decisions/prior-art/architecture/roadmap + AGENTS/CLAUDE. Added the two pieces the handoff spec lacked: data model (spec §A) + module layout (spec §B). Next: run GATE 0 data-sourcing spike before any code.
