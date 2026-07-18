# AGENTS.md — GQRP (Governed Quantitative Research Platform)

Cross-tool agent briefing. Keep lean — loads every turn. Detail lives in `docs/`.

## What GQRP is
A **governed quantitative research platform** for crypto (spot, mid-cap, daily bars, weekly rebalance). It is research *infrastructure*, not a trading strategy — statistical controls against multiple testing, an immutable trial registry, and prospective validation. **Most hypotheses will be worthless; every gate exists to reject them.** "No edge found" is a valid deliverable. Personal learning/research project — not a product, not financial advice.

## ⛳ Start every session here
1. Read [docs/STATE.md](docs/STATE.md) first — current phase, next concrete step, open items.
2. Skim [docs/decisions.md](docs/decisions.md) — settled; don't relitigate without new evidence.
3. Reference [docs/spec.md](docs/spec.md) (design + data model §A + module layout §B), [docs/architecture.md](docs/architecture.md) (seams), [docs/roadmap.md](docs/roadmap.md), [docs/prior-art.md](docs/prior-art.md) as needed.

## 🔚 Before you finish
Update `docs/STATE.md` (Now + a dated session-log bullet). New decision → `docs/decisions.md` (numbered).

## Conventions
- Python 3.11+, `pyproject.toml`. Small focused files. Immutable data by default.
- External libs behind wrappers: vectorbt in `backtest/engine.py`, data vendors behind `data/*`. No vendor type escapes its module.
- The registry is written **only** by its daemon; everything else uses the read-only client.

## Guardrails (the point of the whole project)
- **Never optimize any component toward making a strategy pass a gate.** (spec §16)
- **Never touch the holdout window** (2025-01-01 → 2026-09-30) during development — OS-enforced, not honor-system (decision D6, D10).
- **Config is logged to the registry BEFORE results are computed.** Run-type tagged at creation; `pipeline-validation` never becomes `research` (D7).
- **The universe must be point-in-time & delisting-aware** — no survivorship. Exclude unsourceable assets rather than approximate (D5, D8).
- Never commit secrets/API keys. Branch before committing; commit/push only when asked. Show verification before claiming success.
