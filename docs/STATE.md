# STATE — living session handoff

Read first; update before finishing.

**Last updated:** 2026-07-18  **Phase:** kickoff complete, implementation not started

## Now / in progress
Nothing in progress. Docs scaffolded. Ready to start GATE 0.

## Next concrete step
**Run GATE 0 — the data-sourcing spike** (roadmap.md, blocks everything else):
Fetch a known **delisted** Binance pair's daily klines from `data.binance.vision` and confirm coverage back to its listing date, before writing any universe code. This proves the one project-killing assumption (spec §2.1). Concretely: pick a delisted pair, pull its daily klines from the public dump, verify the coverage window against Binance's delisting announcement, cross-check one aggregator, record the verdict. Resolve open item O1 (confirm `purgedcv` license) while networked.

## Open / unresolved
- **O1** — confirm `purgedcv` exact license before pinning (decisions.md). Fallback: skfolio CPCV + ported DSR/PSR.
- **O2 / GATE 0** — data-sourcing spike not yet run. This is the real risk; everything downstream assumes it passes.

## Done (resolved — see decisions.md)
- Stack: Python 3.11+, vectorbt (open), ccxt, purgedcv, SQLite/WAL registry (D1–D5).
- mlfinlab banned (paid); purgedcv adopted for CPCV + deflated/probabilistic Sharpe.
- Data ground truth = `data.binance.vision` + Binance announcements; aggregators cross-check only.
- Registry immutability + holdout access = structural/OS-level, not policy (D4, D6).
- Agent layer deferred to Phase 2; human is research agent (D9). Holdout window fixed & locked (D10).
- Forward-compat seams named (architecture.md): registry process, run-type→N, role interfaces, Window object, data-source adapter, engine wrapper.

## Session log (newest last)
- **2026-07-18** — Kickoff: imprinted the v3 handoff spec (personal research project → market phase skipped). Focused prior-art run: verified vectorbt open vs pro, found `purgedcv` (open CPCV+DSR+PSR, replaces banned mlfinlab), confirmed ccxt's survivorship gap → `data.binance.vision` as primary source. Scaffolded spec/decisions/prior-art/architecture/roadmap + AGENTS/CLAUDE. Added the two pieces the handoff spec lacked: data model (spec §A) + module layout (spec §B). Next: run GATE 0 data-sourcing spike before any code.
