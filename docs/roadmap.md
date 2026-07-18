# roadmap — phased plan

Mirrors spec §14. Each phase is a checklist. Phase 1 is everything; Phase 2/3 are gated deferrals.

## GATE 0 — data-sourcing spike (blocks everything) 🔴
The single project-killing assumption: that survivorship-safe delisted history is actually obtainable. Prove it before writing the universe builder.
- [ ] Fetch a known **delisted** Binance pair's daily klines from `data.binance.vision`, confirm coverage back to its listing date.
- [ ] Locate Binance listing/delisting announcement dates for that pair; confirm they line up with the kline coverage edges.
- [ ] Cross-check one aggregator (CoinGecko/CMC) against it; document the gap.
- [ ] **Verdict:** sourceable cleanly? → proceed. Not? → escalate (spec §2.1 step 4), do not approximate.
- [ ] Resolve O1 in passing: confirm `purgedcv` license.

## Phase 1 — statistical infrastructure (manual; human = research agent)
1. **Universe + delisting-aware data pipeline** (blocking) — `data/*`, `scripts/build_universe.py`. Output: hash-locked immutable `universe_snapshot`. *Budget weeks (spec §2.1).*
   - [ ] `symbol_lifecycle` from Binance-native source + aggregator cross-check
   - [ ] delisting-aware `ohlcv_bar` loading
   - [ ] monthly PIT ranking + liquidity floor + stablecoin/wrapped exclusion
   - [ ] immutable hash-locked universe file
2. **Trial registry** — append-only SQLite/WAL, separate writer process, read-only client, run-type tagging, triggers + fs perms (decisions D4, D7).
   - [ ] schema + INSERT-only triggers
   - [ ] writer daemon; read-only counts/cumulative-N client
   - [ ] config-before-results ordering enforced (separate `trial` / `trial_result` writes)
3. **Backtest runner + metrics panel** — `backtest/engine.py` (vectorbt), `backtest/cv.py` (purgedcv CPCV), `metrics/panel.py` (deflated/probabilistic Sharpe, turnover, capacity, factor exposure, DD, skew/kurtosis, subperiod stability).
   - [ ] DSR unit-tested against rubenbriones reference
4. **Gates** — `gates/statistical.py` (deflated Sharpe > 0 @95% vs live cumulative-N), `gates/economic.py` (§9 viability).
5. **Validation/holdout discipline** — `discipline/windows.py` + OS-level `holdout_guard.py` (decisions D6, D10). Fixed window 2025-01-01 → 2026-09-30.
6. **Seed momentum run** through steps 1–5 manually, tagged `pipeline-validation` — validates plumbing, not edge. Roles (`roles/memo|review|audit`) exercised by hand.
7. **Single-candidate paper trading** — `paper/runner.py`, ccxt testnet, manual monitoring, 3–6 months. The only honest statistics in the system; does not wait for Phase 2.

**Phase 1 exit:** pipeline runs end-to-end on the seed strategy; first *real* hypothesis (funding-rate carry, D-defer-3) can enter at the memo stage.

## Phase 2 — deferred (gate: hypothesis throughput is the demonstrated bottleneck)
8. [ ] Memo/adversarial/audit agent pipeline behind the `roles/` seam, cross-family routing (decision D9 caveats apply).
9. [ ] Negative-KB automation (run as a manual log meanwhile — D-defer-2).
10. [ ] Paper-trading fleet orchestration — parallel candidates, auto-kill, monitoring (D-defer-1).

## Phase 3+ — deferred scope
- [ ] Funding-rate carry / basis as first real hypothesis (D-defer-3) — actually early, not Phase 3; listed here for scope-visibility.
- [ ] News/sentiment features, forward-only (D-defer-4).
- [ ] Equities universe (D-defer-5).
