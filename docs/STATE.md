# STATE — living session handoff

Read first; update before finishing.

**Last updated:** 2026-07-18  **Phase:** Phase 1 step 2 COMPLETE — trial registry (append-only, structural immutability); backtest/metrics track next

## Now / in progress
Branch `feat/data-pipeline` (3 commits + uncommitted registry). **Phase 1 steps 1 & 2 done.** Universe pipeline + the trial registry, both proven on live data. Registry not yet committed. Next heavy track = backtest runner + metrics/gates (separate session).

**Shipped (step 2 — the trial registry, spec §6/§A, D4/D7):**
- `registry/schema.sql` — append-only `trial`, `trial_result`, `research_memo`, `negative_knowledge`; `BEFORE UPDATE`/`BEFORE DELETE` triggers `RAISE(ABORT)` on every history table. Weight table (family=1.0/variant=0.5/hyperparam=0.2) enforced by a CHECK tying weight↔level. `trial_result` FK+PK to `trial` makes "config before results" and "one result per trial" structural.
- `registry/types.py` — immutable `Trial`/`TrialResult`/`ResearchMemo`/`NegativeKnowledge`; `weight_for(level)` derives weight (callers never pass it).
- `registry/server.py` — `RegistryWriter`: the sole writer, append-only API only (no update/delete method exists → no retag path, D7). WAL; checkpoints on close so a RO client can open.
- `registry/client.py` — `RegistryReader`: opens `mode=ro` (driver rejects all writes — the same client a Phase-2 agent gets, seam 1). `cumulative_weighted_n()` = Σ weight where `run_type='research'`, computed live; `pipeline-validation` excluded.
- `tests/test_registry.py` — 15 tests (round-trip, config-before-results, one-result-per-trial, weight-from-level, N-excludes-pipeline-validation, UPDATE/DELETE trigger rejection, RO-client-cannot-write, memo hash-lock, negative-knowledge). **69 offline + 1 network total, ruff clean.**

**Verification (live evidence this session):** raw `UPDATE trial SET run_type=...` → `trial is append-only: UPDATE forbidden (D4)`; raw `DELETE` → rejected; RO client write → `attempt to write a readonly database`; cumulative N = 1.5 with a pipeline-validation trial correctly excluded.

**Not-yet-done (registry follow-ups, non-blocking):** the socket-isolated writer *daemon* (D4's "separate OS process") is not wired — immutability holds via triggers + no-mutate-path + RO client regardless of process topology; process isolation is a deferred hardening. No `paper_trade_run` table yet (Phase 1 paper-trading step). No `holdout` write-guard in the registry (that's `discipline/holdout_guard.py`, D6).

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
Continue **Phase 1 step 3 — backtest runner + metrics/gates** (spec §8/§9; decisions D2, D3). Discipline layer (sub-step 1) is DONE; remaining sub-steps need the `quant` optional-deps installed and are a fresh session (session-split rule):
1. ~~`discipline/windows.py` + `discipline/holdout_guard.py` — Window object + OS-level holdout enforcement (D6/D10).~~ **DONE this session** (stdlib-only, committed).
2. `backtest/engine.py` — vectorbt wrapper (consumes a `Window`; no vectorbt type escapes it, seam 6) + `backtest/cv.py` — purgedcv CPCV wiring.
3. `metrics/panel.py` — deflated/probabilistic Sharpe via purgedcv; **unit test asserting DSR matches the rubenbriones reference** (D3). Reads live cumulative-N from `registry/client.py`.
4. `gates/statistical.py` (deflated Sharpe > 0 @95% vs live N) + `gates/economic.py` (§9 viability).
Needs the `quant` optional-deps installed (numpy/pandas/vectorbt/purgedcv) — data+registry are stdlib-only, this track is not.
Verification bar (CLAUDE.md): show DSR matching the reference implementation.

Non-blocking follow-ups (do only if needed): registry writer *daemon* process-isolation (D4 hardening); `paper_trade_run` table; `--cross-check` flag in `build_universe.py`; parallel history downloads (full-discovery run is slow — §2.1 "budget weeks").

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
- **2026-07-18** — **Phase 1 step 3 started — discipline layer (seam 4).** Built `discipline/windows.py` (`Window` object; dev/validation/holdout from config; **D10 hash-lock** `LOCKED_WINDOWS_HASH` + `verify_windows_locked()` tripwire) and `discipline/holdout_guard.py` (D6: `assert_range_allowed`/`assert_day_allowed`/`assert_path_outside_holdout`, `HoldoutAccessError`; real enforcement = fs perms, this is the loud in-process complement). Stdlib-only. 15 tests → **84 offline + 1 network, ruff clean.** Live proof: windows match locked hash; a range crossing into 2025 and a holdout day both REJECTED; boundary edit breaks the lock. Remaining step 3 (engine/cv/metrics/gates) needs `quant` deps → next session.
- **2026-07-18** — **Phase 1 step 2 COMPLETE — the trial registry.** Built `registry/{schema.sql,types.py,server.py,client.py}` (spec §6/§A, D4/D7). Structural immutability, not policy: `BEFORE UPDATE`/`BEFORE DELETE` triggers `RAISE(ABORT)` on all four history tables; writer (`RegistryWriter`) has no mutate method → no retag path (D7); reader (`RegistryReader`) opens `mode=ro` → driver rejects all writes (same client Phase-2 agents get, seam 1). Weight derived from level via a CHECK-enforced table; `trial_result` FK+PK makes config-before-results and one-result-per-trial structural. `cumulative_weighted_n` computed live, `pipeline-validation` excluded. 15 registry tests → **69 offline + 1 network, ruff clean.** Live proof: raw UPDATE/DELETE both aborted with "append-only … forbidden (D4)"; RO client write → "readonly database"; N=1.5 excluding a pipeline-validation trial. Deferred (non-blocking): socket-isolated writer daemon (immutability already structural). Next: backtest/metrics track (step 3).
- **2026-07-18** — **Phase 1 step 1 COMPLETE.** Added `data/coingecko.py` + `lifecycle.cross_check_existence` (aggregator existence corroboration → `verified`, D5; immutable). Live smoke: 13,696 CoinGecko symbols, SRM verified True, fake asset False. 54 offline + 1 network test, ruff clean. Universe pipeline done end-to-end (sourcing → lifecycle → PIT ranking → hash-locked immutable snapshot → cross-check). Next: registry track (step 2).
- **2026-07-18** — **Phase 1 step 1 near-complete.** Added `data/ohlcv.py` (delisting-aware, PIT), `data/universe.py` (PIT ranking + hash-locked immutable snapshot), `binance_source.list_all_symbols` (paginated discovery), `scripts/build_universe.py` driver (holdout-capped). Decision D12: rank by avg daily quote volume, not reconstructed market cap (user deferred; chosen for D5/D8 consistency). 48 offline + 1 network test, ruff clean. Proved delisting-awareness + immutability on live SRMUSDT data. Remaining step-1 item: aggregator cross-check. Then registry track.
- **2026-07-18** — **Phase 1 step 1 foundation.** Branch `feat/data-pipeline`. Built config + data domain types + Binance-native adapter (checksum-verified, vendor-isolated per seam 5) + lifecycle construction. 28 tests (27 offline + 1 live network reproducing GATE 0), ruff clean. Data layer is stdlib-only so it runs without vectorbt/ccxt. Next: `data/ohlcv.py` (delisting-aware loading), aggregator cross-check, `data/universe.py` (hash-locked snapshot). Not committed.
- **2026-07-18** — **GATE 0 PASSED.** Spiked delisted SRMUSDT against `data.binance.vision`: full daily klines, all `.CHECKSUM` (SHA-256) OK, coverage 2020-08-11 → 2022-11-28. Edges match exchange truth exactly — first bar = Binance listing date; partial final bar (open 00:00, close 02:59 UTC 2022-11-28) = intraday halt per the 2022-11-25 delisting announcement (SRM/USDT terminated 2022-11-28). CoinGecko cross-check: token exists but no lifecycle dates + 365-day free-history cap → can't source the window, exactly the gap D5 assumes. Resolved O1: purgedcv MIT, v0.1.2. Recorded D11; O1/O2 closed. Next: Phase 1 step 1 (universe/data pipeline).
- **2026-07-18** — Kickoff: imprinted the v3 handoff spec (personal research project → market phase skipped). Focused prior-art run: verified vectorbt open vs pro, found `purgedcv` (open CPCV+DSR+PSR, replaces banned mlfinlab), confirmed ccxt's survivorship gap → `data.binance.vision` as primary source. Scaffolded spec/decisions/prior-art/architecture/roadmap + AGENTS/CLAUDE. Added the two pieces the handoff spec lacked: data model (spec §A) + module layout (spec §B). Next: run GATE 0 data-sourcing spike before any code.
