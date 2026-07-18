# spec — Governed Quantitative Research Platform (GQRP)

**Type:** personal research / learning infrastructure. Not a product, not financial advice, not a trading strategy.
**Status:** design complete (handoff spec v3), implementation not started.
**Canonical design:** this file. The v3 handoff spec is reproduced/condensed here as the authoritative requirements; §A/§B below add the two pieces the handoff spec omitted (data model, module layout).

---

## 0. Positioning & framing

A **governed research platform** with statistical controls against multiple testing, immutable experiment tracking, and prospective validation. **Most hypotheses will be worthless. The pipeline exists to reject them without fooling itself.**

- **Expected outcome (~12 months):** 40–60 hypotheses, 2–4 clear backtest+viability passes, 0–1 forward-test survivor (likely Sharpe 0.5–0.8, low five-figure capacity). **"No edge found" is a valid deliverable.**
- **Prime directive:** do NOT optimize any component toward making strategies pass. Every gate exists to reject. (§16 non-goals.)
- **Phase 1 = the statistical infrastructure, run manually, with the human as research agent.** The LLM agent layer is deferred to Phase 2 (decision 9) because mechanism-first ordering has no technical enforcement — a model confabulates a plausible mechanism for any primitive set post-hoc. Writing your own memo is the enforcement.

## 1. Market scope

| Parameter | Value |
|---|---|
| Asset class | Crypto (spot, mid-cap) |
| Bar frequency | Daily |
| Rebalance | Weekly |
| Universe | ~50 candidates, hold top 10 |
| Backtest start | 2018-01-01 |
| Capital assumption | $10,000 |
| Cost model | 0.1% taker fee + 0.15% slippage **per side** |

Crypto over equities: free complete history via exchange data, no paid point-in-time constituent data, 24/7 markets, trivial testnet paper trading.

**Seed strategy (pipeline plumbing validation only, NOT the edge):** cross-sectional momentum (20/50-day), vol-targeted sizing, top 10 of 50, weekly rebalance, buffer bands (rotate out only below rank 15). Well-arbed since ~2019; not expected to survive as a real strategy. First *real* hypothesis is funding-rate carry (§15 / decision D-defer-3).

## 2. Universe construction — BUILD FIRST, BLOCKING

Single most common source of fake crypto backtests: survivorship from dead/delisted assets. Universe must be built and frozen before any simulation.

- Monthly market-cap ranking, reconstructed **point-in-time** (never today's top-50 projected backward).
- Liquidity threshold filter (min daily volume, declared in config).
- Exchange availability per date.
- **Delisting records** — dead assets stay in the universe until they died; loss realized.
- Exclude stablecoins and wrapped assets.
- Output: **immutable dated universe file, hash-locked, referenced by every backtest.**

### 2.1 Data sourcing (the actual bottleneck — budget weeks)
Sourcing priority:
1. **Primary: exchange-native, single venue.** Binance historical listing/delisting dates = ground truth. Narrower universe, far more reliable than aggregators. See decision D5 for concrete source (`data.binance.vision`).
2. **Secondary: cross-check aggregator (CoinGecko/CMC) against (1)** — never sole source for any asset's lifecycle dates.
3. **If neither cleanly covers an asset, exclude it.** Smaller honest universe > larger silently-wrong one.
4. Still unsourceable after the above → **blocking, escalate, do not approximate.**

## 3. Pipeline — Phase 1 (manual)

```
YOU write research memo (§4)
  → YOU (or a different model, pasted) adversarially review (§5)
  → HUMAN GATE #1 (mechanism plausible?)
  → Implementation: 3–5 variants
  → Trial registry (append-only, config logged BEFORE results, N incremented)
  → Backtest runner (development data ONLY, 2018–2022)
  → YOU run audit checklist (§7) — ideally a day later
  → Metrics panel + statistical gate (§8)
  → Economic viability gate (§9)
  → Validation set (2023–2024) — ONE evaluation per idea family
  → Single-candidate paper trading (forward-only, 3–6 months, §12)
  → HUMAN GATE #2 (real capital)
```
You are research agent, adversarial reviewer, and auditor — each as a distinct honest pass. No orchestrated agent handoff (that's Phase 2, deferred).

## 4. Research memo format
```
FAMILY ID:
MECHANISM:            (persistent market mechanism; counterparty story is one valid
                       answer — also structural: delayed info diffusion, microstructure,
                       liquidity constraints, risk transfer, forced rebalancing, benchmark effects)
OBSERVABLE PREDICTION: (specific, testable, stated before any code exists)
NECESSARY ASSUMPTIONS:
POSSIBLE FAILURE MODES:
FALSIFICATION CONDITION: (what result abandons the mechanism? "nothing" ⇒ reject as untestable)
IMPLEMENTATION SKETCH: (primitives, and why the mechanism implies them)
```
**Ordering constraint:** mechanism first, primitives chosen *because of* it. Phase 1 enforcement = you writing it honestly in order. No technical enforcement exists (that's the reason the agent layer is deferred).

**Primitive library** — Base: momentum, mean reversion, breakout, vol expansion, vol contraction, carry, seasonality, liquidity, volume, funding, cross-sectional ranking, regime filter. Transforms: lag, normalize, z-score, percentile, decay, smoothing. Risk: vol targeting, inverse vol, equal risk, beta neutral, market neutral.

## 5. Adversarial review checklist (before Gate #1)
Simply beta? · Momentum clone renamed? · Fees erase it? · Single-regime dependent? · Implicit future info? · Is the mechanism actually implied by the primitives? · Related family already rejected (§11)? → Output: **kill**, or **pass-with-concerns** to human gate.

## 6. Trial registry — the statistical spine
- Append-only. **Separate process.** Read access to counts only; **never** write access to history (for you *and* any future agent).
- Config logged **before** results are computed/visible.
- Immutability enforced at filesystem/process level, **not by policy** (decision D4).

**Hierarchical trial accounting** (fixed in advance, never adjusted):

| Level | Weight |
|---|---|
| Idea family | 1.0 |
| Implementation variant | 0.5 |
| Hyperparameter change | 0.2 |

Not formally rigorous — the point is removing your ability to argue post-hoc that "those 800 sweeps don't count."

### 6.1 Run-type tagging (declared at creation, before execution)
- `pipeline-validation` — logged for audit trail, **excluded from cumulative weighted N** (the deflated-Sharpe threshold).
- `research` — counts normally per the weight table.

Abuse guards (structural, not policy): no code path retags/promotes `pipeline-validation` → `research`; its output can't be cited as evidence anywhere; if it looks interesting, that's a **new** `research` family starting from the memo, N incrementing from there.

## 7. Audit checklist (against backtest code + results, before metrics)
Lookahead/leakage · survivorship & delisting handling · point-in-time correctness of all inputs · fee/slippage realism · return concentration (80% from one quarter?) · regime breakdown (survives excluding best regime?) · sensitivity to removing top-N trades. Phase 1: run it yourself, ideally after a day away.

## 8. Metrics panel
Deflated Sharpe (vs cumulative weighted N) · Probabilistic Sharpe · turnover · capacity · exposure concentration · factor exposure (incl. beta to BTC & to total crypto mcap) · max drawdown · skew · kurtosis · stability across subperiods.
Reference: López de Prado, *Advances in Financial Machine Learning*. Implementation: `purgedcv` (decision D3).
**Statistical gate default: deflated Sharpe > 0 at 95% confidence given cumulative weighted N.**

## 9. Economic viability gate (after metrics, before forward test)
Reject if: capacity < $50k (default) · alpha small vs realistic costs · turnover so high the edge is a rounding error on fees · complexity unjustified by return. (Example death: Sharpe 1.1, 5% annual, 800% turnover, $30k capacity — statistically fine, not a business.)

## 10. Validation discipline
- **Development 2018–2022:** unlimited passes.
- **Validation 2023–2024:** exactly ONE evaluation per idea family.
- **Final holdout 2025-01-01 → 2026-09-30** (fixed, hash-locked at project start, **locked 2026-07-18**): touched once ever, at the end. Everything after 2026-09-30 is forward-test territory (§12), never backtested. **No filesystem access to the holdout window during development — enforced at OS level** (decision D6). Development running well past the boundary is a schedule signal, not a reason to extend the lock.

**Quarantine/reopening record:** FAMILY / REASON REJECTED / REASON FOR REOPENING / MATERIAL HYPOTHESIS CHANGE / WHY NOT PARAMETER TUNING. Valid: implementation bug, wrong data vendor, new literature, structural market change. **Invalid: "it almost passed."** Reopening resets the family's trial count.

## 11. Negative knowledge base (consulted before proposing new work)
Record: MECHANISM / REJECTION TYPE [mechanism-invalid | regime-dependent | fee-killed | capacity-killed | implementation-bug] / EVIDENCE / RELATED FAMILIES / CONFIDENCE. Only `mechanism-invalid` and `regime-dependent` suppress future proposals — the others are incidental and say nothing about the mechanism.

## 12. Forward testing & change control
The only stage where statistics are unambiguously honest.
- **Phase 1 — single-candidate paper trading:** one candidate, manual monitoring, 3–6 months, ccxt exchange testnet, no auto-kill. Runs from day one (build step 7).
- **Phase 2 — fleet orchestration (deferred):** parallel candidates, auto-kill, monitoring. Build only when >1 live candidate is a real problem.

**Change taxonomy** (classify honestly — misfiling a logic change as a bugfix is the failure this prevents):
- **Operational** (retries, API failures, timestamp parsing, outages) → no reset.
- **Execution model** (slippage, fees, partial fills) → re-run historical tests, **increment registry**; forward test need not reset if hypothesis unchanged.
- **Decision logic** (entry/exit/ranking/sizing/filters) → **immediate full pipeline reset**.

## 13. Implementation defaults
See `decisions.md` for the resolved, verified versions. Summary: Python 3.11+ · backtest `vectorbt` (open) · exchange `ccxt` · CV combinatorial purged (`purgedcv`) · paper `ccxt` testnet · registry append-only SQLite/WAL as separate process · Phase-1 orchestration = none (manual scripts).

## 14. Build order
**Phase 1:** 1) Universe + delisting-aware data pipeline (Binance-primary) — blocking · 2) Trial registry w/ immutability + run-type tagging · 3) Backtest runner + metrics panel · 4) Statistical + economic gates · 5) Validation/holdout discipline (OS-enforced, fixed window) · 6) Run seed momentum through 1–5 manually, tagged `pipeline-validation` · 7) Single-candidate paper trading.
**Phase 2 (deferred, gate on throughput being the bottleneck):** 8) Memo/adversarial/audit agent pipeline · 9) Negative-KB automation (useful as a manual log earlier) · 10) Paper-trading fleet orchestration.

## 15. Deferred scope (Phase 3+)
News/sentiment (forward-only in paper trading; historical PIT news unreliable) · equities universe (needs paid PIT constituent data) · **crypto funding-rate carry / basis** — strongest first *real* hypothesis (mechanical, obvious counterparty = leveraged longs, market-neutral, under-arbed on smaller venues).

## 16. Non-goals
Beating S&P on raw return (wrong bar — leverage does that trivially) · intraday/HFT/latency-sensitive · novel signal discovery on daily OHLCV (well is dry) · **any component that makes strategies more likely to pass a gate.**

---

# §A. Data model (first pass)

Entities and their shapes. Storage per decision D4 (registry) / D5 (market data). Timestamps UTC.

- **`symbol_lifecycle`** — `symbol, venue, listing_date, delisting_date|null, base_asset, quote_asset, is_stablecoin, is_wrapped, source (binance-native|aggregator-crosscheck), verified`. Ground-truth spine for point-in-time availability.
- **`ohlcv_bar`** — `symbol, date, open, high, low, close, volume, quote_volume, source`. Daily. Delisted symbols retain bars up to `delisting_date`.
- **`universe_snapshot`** (immutable, hash-locked) — `snapshot_date, config_hash`, and rows `(symbol, rank, market_cap, avg_daily_volume, eligible)`. One file per monthly reconstruction; hash referenced by every backtest.
- **`research_memo`** (append-only, hash-locked) — the §4 fields + `family_id, memo_hash, committed_at`. Hash locks the memo before implementation.
- **`trial`** (registry, append-only) — `trial_id, family_id, parent_trial_id|null, level (family|variant|hyperparam), weight (1.0|0.5|0.2), run_type (research|pipeline-validation), config_json, config_hash, data_window (development|validation|holdout), created_at, status`.
- **`trial_result`** (registry, append-only, written AFTER `trial`) — `trial_id, metrics_json, gate_verdicts_json, created_at`. Separation enforces "config before results."
- **`negative_knowledge`** — §11 fields + `family_id, created_at`.
- **`paper_trade_run`** — `candidate_id, family_id, venue (testnet), started_at, ended_at|null, status, change_log_json` (each entry classified per §12 taxonomy).

**Cumulative weighted N** (drives the deflated-Sharpe bar) = `Σ weight` over `trial` rows where `run_type = 'research'`. Computed live from the registry; never stored as a mutable counter.

# §B. Module layout

```
gqrp/
  pyproject.toml
  gqrp/
    config.py                 # cost model, windows, thresholds, liquidity floor — all declared
    data/
      binance_source.py       # data.binance.vision klines + REST listing/delisting
      lifecycle.py            # symbol_lifecycle construction + aggregator cross-check
      universe.py             # point-in-time monthly ranking, hash-lock, immutable file
      ohlcv.py                # delisting-aware bar loading
    registry/                 # SEPARATE PROCESS (architecture seam #1)
      server.py               # append-only writer daemon
      client.py               # read-only counts / cumulative-N client
      schema.sql              # append-only tables + INSERT-only triggers
    backtest/
      engine.py               # vectorbt wrapper; consumes a Window object
      cv.py                   # purgedcv CPCV wiring
    metrics/
      panel.py                # deflated/probabilistic Sharpe (purgedcv) + turnover/capacity/etc.
    gates/
      statistical.py          # deflated Sharpe > 0 @95% vs live cumulative-N
      economic.py             # §9 viability
    discipline/
      windows.py              # dev/validation/holdout boundaries (config)
      holdout_guard.py        # OS-level access enforcement (decision D6)
    roles/                    # architecture seam #3 — human fills these in Phase 1
      memo.py                 # propose_memo(): §4 template + hash-lock
      review.py               # adversarial_review(): §5 checklist
      audit.py                # audit(): §7 checklist
    paper/
      runner.py               # single-candidate ccxt testnet, manual monitoring
  scripts/
    build_universe.py         # BLOCKING first deliverable
    run_backtest.py
  data/                       # gitignored: raw pulls + immutable universe files; holdout partition OS-locked
  docs/
```
