# decisions — resolved & explicitly deferred

Settled. Don't relitigate without new evidence. Format: Decision / Why / How to apply.

## 1. Language & runtime — Python 3.11+
**Decision:** Python 3.11+, `pyproject.toml`, single package `gqrp/`.
**Why:** every load-bearing library (vectorbt, ccxt, purgedcv, skfolio, numpy/pandas) is Python. No reason to fight it.
**How to apply:** `pyproject.toml` with pinned deps; venv or uv. 3.11 for perf + typing.

## 2. Backtest engine — open-source `vectorbt`
**Decision:** `vectorbt` (polakowo), not vectorbtpro, not backtrader.
**Why:** maintained, numpy-native, fast for weekly-rebalance sweeps. Prior-art verified.
**How to apply:** wrap in `backtest/engine.py`; keep vectorbt types out of the rest of the codebase behind that wrapper. **License guardrail:** source-available, non-commercial-sale — this stays a personal research tool; if it ever goes commercial, revisit the engine choice.

## 3. CPCV + overfitting stats — `purgedcv` (AVOID mlfinlab)
**Decision:** adopt `purgedcv` for combinatorial purged CV, PSR, Deflated Sharpe, MinTRL. Cross-check against `skfolio` (CPCV) and `rubenbriones/Probabilistic-Sharpe-Ratio` (formulas). **mlfinlab is banned** (paid closed-source).
**Why:** open, sklearn-compatible, covers §8 + §13 in one dep. mlfinlab can't be a dependency.
**How to apply:** `backtest/cv.py` wires CPCV; `metrics/panel.py` calls purgedcv's DSR/PSR. **Verify purgedcv's license before pinning** (open item O1). Add a unit test asserting our DSR matches the rubenbriones reference on a known input.

## 4. Trial registry — append-only SQLite/WAL, separate process
**Decision:** SQLite in WAL mode, written only by a standalone writer daemon (`registry/server.py`); everyone else uses a **read-only** client (`registry/client.py`).
**Why:** the registry is the statistical spine (§6) — immutability must be structural, not policy. If compromised, nothing else means anything.
**How to apply:** enforce immutability with ALL of: (a) separate OS process owning the DB file, (b) no UPDATE/DELETE anywhere in the writer's code path, (c) `BEFORE UPDATE`/`BEFORE DELETE` triggers that `RAISE(ABORT,...)`, (d) filesystem perms so only the daemon can write. Cumulative-N is **computed** from rows, never a mutable counter. This same read-only client is what any Phase-2 agent gets — no write path is ever added.

## 5. Historical data source — Binance-primary via `data.binance.vision`
**Decision:** ground truth = `data.binance.vision` klines (incl. delisted pairs) + Binance listing/delisting announcements for lifecycle dates. ccxt = live/testnet + current-symbol only. Aggregators (CoinGecko/CMC) = cross-check only, never sole source for a lifecycle date.
**Why:** ccxt cannot supply delisted history or point-in-time availability (§2.1); aggregators have documented gaps exactly where survivorship bias bites. Honest-smaller > large-silently-wrong.
**How to apply:** `data/binance_source.py` + `data/lifecycle.py` build `symbol_lifecycle`; unsourceable assets are **excluded**, not approximated. If a candidate can't be cleanly sourced after both sources → blocking, escalate.

## 6. Holdout enforcement — OS-level, not prompt-level
**Decision:** holdout-window data (2025-01-01 → 2026-09-30) is physically inaccessible to the development process. Enforced at the OS/filesystem layer.
**Why:** §10 — "one evaluation ever" is meaningless if dev code can read holdout data. Prompt instructions don't enforce anything.
**How to apply:** store holdout-partition files outside the dev process's readable path (separate owner + mode `000`, or a separate volume). `discipline/holdout_guard.py` raises loudly if a holdout path is opened during dev. Forward-test tooling reads only post-2026-09-30 data.

## 7. Run-type tagging — structural, no retag path
**Decision:** every trial tagged `research` or `pipeline-validation` at creation (§6.1); `pipeline-validation` excluded from cumulative weighted N; no code path retags/promotes it.
**Why:** stops seed/debug runs from burning statistical budget, and stops post-hoc "that one should have counted."
**How to apply:** tag is a required, immutable column on `trial`. Cumulative-N query filters `run_type='research'`. There is deliberately no update endpoint. An interesting `pipeline-validation` result = a brand-new `research` family from the memo stage.

## 8. Universe scope — Binance-listed only
**Decision:** universe is Binance-listed spot mid-caps; exclude stablecoins, wrapped assets, and anything unsourceable.
**Why:** ground-truth lifecycle dates beat a broader but silently-wrong cross-venue universe.
**How to apply:** `data/universe.py` monthly PIT ranking with config liquidity floor; output hash-locked immutable file referenced by every backtest.

## 9. Agent layer — DEFERRED to Phase 2 (human is the research agent)
**Decision:** no LLM agents in the memo/review/audit loop in Phase 1. Human writes memos, does adversarial review, runs audit.
**Why:** mechanism-first ordering has no technical enforcement — a model confabulates a plausible mechanism for any primitive set post-hoc (§0.1). Writing your own memo *is* the enforcement, and serves the learning goal.
**How to apply:** implement the three roles as explicit interfaces in `roles/` (memo/review/audit) that a human fills now — so Phase 2 can swap in agents behind the same seam additively.
**Deferral trigger:** hypothesis *generation* becomes the demonstrated bottleneck after ~1 year of Phase 1 (won't happen at 40–60/yr). Even then, agent-written memos get more skepticism, memo hash-locked before primitive-library access, falsification condition must reference a pre-registered automated test.

## 10. Holdout window — fixed 2025-01-01 → 2026-09-30, locked 2026-07-18
**Decision:** fixed start and end (not open-ended "2025+"), hash-locked at project start.
**Why:** an unbounded window keeps absorbing new data as wall-clock advances, blurring holdout vs forward-test and making "one evaluation ever" ambiguous. End set ~2.5 months out from lock so §14 steps 1–6 run entirely on the future side of the boundary, crossed intentionally.
**How to apply:** window constants in `discipline/windows.py`, hash recorded. Dev running past 2026-09-30 is a schedule signal, not a reason to extend.

## 11. GATE 0 verdict — data sourcing PASSES; D5 approach validated
**Decision:** the project-killing assumption (§2.1 — survivorship-safe delisted history is obtainable) is **confirmed true**. Proceed to Phase 1. Spike run 2026-07-18 against delisted **SRMUSDT**.
**Why:** `data.binance.vision` served SRMUSDT's full daily klines, checksum-verified, coverage **2020-08-11 → 2022-11-28**. Edges match exchange-native lifecycle exactly: first bar = Binance listing (2020-08-11); final bar is a *partial* day (open 2022-11-28 00:00, close 02:59 UTC) = intraday trading halt, matching Binance's 2022-11-25 announcement terminating SRM/USDT spot on 2022-11-28. Aggregator cross-check (CoinGecko) confirms the token existed but exposes **no exchange-specific listing/delisting dates** and caps free history at 365 days — i.e. it *cannot* source the 2020–2022 window at all. This is precisely the gap D5 predicted: aggregators = existence cross-check only, never a lifecycle source.
**How to apply:** `data/binance_source.py` uses the S3 REST listing (`https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/spot/monthly/klines/{SYMBOL}/1d/`) to discover coverage, downloads monthly zips, and **verifies the `.CHECKSUM` (SHA-256) on every file**. A partial final daily bar is the delisting/halt signal; treat the last bar's date as the effective `delisting_date` and cross-check against the Binance announcement. Timestamps are epoch-ms UTC.

## 12. Universe ranking metric — avg daily quote volume, NOT reconstructed market cap
**Decision:** rank the monthly universe by trailing **average daily quote (USD) volume** (Binance-native), not by point-in-time market cap. This overrides spec §2's literal "market-cap ranking" wording. `universe_snapshot.market_cap` stays a nullable field, reserved for a future non-PIT aggregator annotation; it is never used for selection.
**Why:** market cap = price × circulating supply, and Binance klines give price/volume but **not** supply. Point-in-time circulating supply is only available from aggregators, which D5 restricts to cross-check-only and D8 says to exclude-rather-than-approximate. Reconstructing PIT market cap would reintroduce exactly the aggregator-reliability risk the project rejects. Dollar volume is exchange-native, fully PIT, and doubles as the liquidity measure (§2 liquidity floor). User deferred the call 2026-07-18; chosen for internal consistency with D5/D8.
**How to apply:** `data/universe.py` ranks by `avg_daily_quote_volume` over `DEFAULT_LOOKBACK_DAYS` (30). Metric id `avg_daily_quote_volume_v1` is baked into `config_fingerprint` — changing the metric changes every snapshot's `config_hash`. If PIT supply ever becomes cleanly sourceable, that is a new decision, not a silent swap.

---

## Explicitly deferred (with reopening trigger)

- **D-defer-1 — Fleet orchestration** (parallel candidates, auto-kill, monitoring). Trigger: >1 live paper-trading candidate at once is a real problem. Until then, single-candidate manual (§12).
- **D-defer-2 — Negative-KB automation.** Trigger: manual log (`docs/` or a table) becomes unwieldy. Useful as a plain manual log from day one.
- **D-defer-3 — Funding-rate carry / basis** as first *real* hypothesis. Trigger: pipeline validated via seed momentum (build step 6). Strongest-prior mechanism (§15).
- **D-defer-4 — News/sentiment features.** Forward-only in paper trading; historical PIT crypto news is unreliable. Phase 3.
- **D-defer-5 — Equities universe.** Needs paid PIT constituent data. Phase 3.
- **D-defer-6 — Registry writer as a socket-isolated OS daemon.** D4's four immutability mechanisms are (a) separate process owning the file, (b) no mutate path in the writer, (c) UPDATE/DELETE triggers, (d) fs perms. Step 2 shipped (b), (c), and the read-only client; (a) — a standalone writer *process* the dev code talks to over a socket — is **deferred**. Rationale: immutability is already structural via (b)+(c)+RO client (proven: raw UPDATE/DELETE aborted, RO client can't write), and a single human research agent (D9) gives no adversary for process isolation to defend against yet (YAGNI). **Reopening trigger:** the Phase-2 agent layer lands, OR the dev process needs a writable handle for any reason — at that point wrap `RegistryWriter` behind a socket/RPC daemon + mode-`000` fs perms so no other process can open the DB read-write. The RO client is unchanged by this (seam 1 holds).

## Open items
- ~~**O1** — Confirm `purgedcv` exact license.~~ **RESOLVED 2026-07-18:** MIT (LICENSE file "Copyright (c) 2026 Evgenii Lazarev" + PyPI classifier "License :: OSI Approved :: MIT License"). Latest **v0.1.2** (2026-06-13). Safe to pin. Fallback (skfolio + rubenbriones) no longer needed but kept as cross-check per D3.
- ~~**O2** — GATE 0 data-sourcing spike.~~ **RESOLVED 2026-07-18:** PASS. See decision D11.
