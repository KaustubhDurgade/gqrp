# architecture — components, data flow, forward-compat seams

Module layout is in `spec.md §B`. This file covers how the pieces fit and — the highest-value part — the **seams that keep Phase-2 additive instead of a rewrite**.

## Components & data flow

```
data.binance.vision + Binance announcements
        │
        ▼
  data/lifecycle.py ──► symbol_lifecycle (ground-truth availability)
        │                       │
        │                       ▼
  data/ohlcv.py ──► ohlcv_bar    data/universe.py ──► universe_snapshot (hash-locked, immutable)
        │                                 │
        └───────────────┬─────────────────┘
                        ▼
            backtest/engine.py (vectorbt)  ◄── consumes a Window object (dev|validation|holdout)
                        │        └── backtest/cv.py (purgedcv CPCV)
                        ▼
            metrics/panel.py (deflated/probabilistic Sharpe via purgedcv, turnover, capacity, factor exposure)
                        │   ▲
                        │   └── registry/client.py  (read-only: cumulative weighted N)
                        ▼
            gates/statistical.py ──► gates/economic.py ──► validation (ONE eval) ──► paper/runner.py (testnet)

  roles/{memo,review,audit}.py  ──►  registry/server.py (append-only writer daemon)
                                      ▲ config logged BEFORE results; run-type tagged at creation
```

Control flow is the §3 pipeline, run manually. Every backtest references an immutable `universe_snapshot` hash and a `Window`; every trial is written to the registry (config first, results after).

## Load-bearing forward-compat seams

**Seam 1 — Registry as a separate process (§6, decision D4).** *The* load-bearing boundary. Everything reads counts through `registry/client.py` (read-only) and writes through the `registry/server.py` daemon's append-only API. Immutability is structural (separate process + no mutate path + triggers + fs perms). **Why it holds under change:** Phase-2 agents get the *same* read-only client — there is never a write path to add. If this boundary is right in Phase 1, the agent layer bolts on without touching the statistical spine.

**Seam 2 — Run-type tag drives N (§6.1, decision D7).** `cumulative_weighted_N = Σ weight where run_type='research'`, computed live. Adding families (human or, later, agent) just inserts tagged trials; the deflated-Sharpe bar rises automatically. No consumer of N changes when the producer of trials changes. No retag endpoint exists by construction.

**Seam 3 — The three research roles are interfaces, not scripts (decision D9).** `roles/memo.py` / `review.py` / `audit.py` expose `propose_memo()`, `adversarial_review()`, `audit()`. In Phase 1 a human fills them (fills a template, runs a checklist). Phase 2 swaps a human for an agent *behind the same interface* — additive, not a rewrite. Defining these as real seams now (even when "implementation" = a Markdown template) is what makes the deferred agent layer cheap later. The memo is hash-locked on commit so the ordering constraint (mechanism before primitives) is checkable regardless of who — or what — wrote it.

**Seam 4 — Window object gates all data access (§10, decision D6).** `backtest/engine.py` never opens files directly; it receives a `Window` from `discipline/windows.py`. The holdout partition is OS-inaccessible during dev (`holdout_guard.py` raises on access). **Why it holds:** moving from single-candidate paper trading to fleet orchestration doesn't change the boundary — it's config + filesystem, orthogonal to how many candidates run.

**Seam 5 — Data-source adapter isolation (decision D5).** `data/binance_source.py` and aggregator cross-checks sit behind `data/lifecycle.py` / `data/ohlcv.py`. Adding a second venue later (or swapping the aggregator) touches only the adapter, not the universe/backtest layers. The rest of the system sees `symbol_lifecycle` + `ohlcv_bar`, never a vendor SDK.

**Seam 6 — vectorbt behind `backtest/engine.py`.** No vectorbt type escapes the wrapper. If the license situation or a perf ceiling ever forces an engine change, it's one module.

## What is deliberately NOT abstracted (YAGNI)
- No orchestration daemon in Phase 1 — scripts + manual steps (decision, §13).
- No plugin system for strategies — the primitive library (§4) is a fixed enumerated set, composed in code.
- No generic event store — plain append-only SQLite (prior-art: event-store frameworks = overkill).
- No multi-user / auth — single researcher.

## Stack rationale (each tied to a requirement)
| Choice | Requirement it serves |
|---|---|
| Python 3.11+ | ecosystem (vectorbt/ccxt/purgedcv all Python) — decision D1 |
| vectorbt (open) | fast weekly-rebalance sweeps over 2018→ history — §8, D2 |
| purgedcv | CPCV + deflated/probabilistic Sharpe without mlfinlab — §8/§13, D3 |
| ccxt + data.binance.vision | free survivorship-safe history + testnet paper — §1/§2/§12, D5 |
| SQLite WAL, separate process | structural registry immutability — §6, D4 |
| OS-level holdout lock | honest "one evaluation ever" — §10, D6 |
