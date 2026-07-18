# prior-art — reuse map & license verdicts

Verified July 2026. Legend: **ADOPT** (use as dependency) · **PORT** (copy/adapt small piece, credit) · **WRAP** (thin wrapper) · **AVOID** · **REFERENCE** (read, don't depend).

## Backtest engine (§8, §13)
- **`vectorbt`** (`polakowo/vectorbt`, PyPI `vectorbt`) — **ADOPT.** Open source, maintained (release cadence healthy, ~20 contributors). numpy-native, vectorized, fast for large sweeps. **License nuance:** source-available with a *non-commercial-sale* clause — "may not sell products or services that are primarily this software." Fine for a personal research tool; **do NOT** build a commercial product on it without relicensing (revisit if this ever stops being personal). https://github.com/polakowo/vectorbt
- **`vectorbtpro`** — **AVOID (paid).** Proprietary successor, invite-only paid repo. Not needed for Phase 1 scale.
- **`backtrader`** — REFERENCE only. Event-driven, slower for the weekly-rebalance sweep workload; spec already picks vectorbt.

## Cross-validation + overfitting statistics (§8 metrics, §13 CPCV) — the key reuse win
- **`purgedcv`** (`eslazarev/purged-cross-validation`) — **ADOPT.** Open, scikit-learn splitter-protocol compatible. Implements purging + embargo, expanding/rolling walk-forward, purged & group-purged k-fold, **Combinatorial Purged CV with backtest-path reconstruction**, and **Probabilistic Sharpe Ratio + Deflated Sharpe Ratio + Minimum Track Record Length**. Single library covers both §13 (CPCV) and most of §8. Drops into `cross_val_score`/`GridSearchCV`. **Verify exact license (MIT/BSD expected) before pinning.** https://github.com/eslazarev/purged-cross-validation
- **`mlfinlab`** (Hudson & Thames) — **AVOID.** The canonical López de Prado implementation, but **relicensed to paid closed-source** — cannot be a dependency for this project. It's why `purgedcv` exists.
- **`skfolio`** (BSD-3) — **ADOPT-as-crosscheck.** Portfolio-optimization library with its own CPCV (purging + embargo). Use to cross-validate `purgedcv`'s CPCV path reconstruction and as a fallback if `purgedcv` proves thin. https://skfolio.org
- **`rubenbriones/Probabilistic-Sharpe-Ratio`** — **REFERENCE / PORT.** Clean López de Prado PSR + DSR reference implementation with worked notebook. Use to unit-test our metrics against known values; port the formula if `purgedcv`'s DSR needs verifying. https://github.com/rubenbriones/Probabilistic-Sharpe-Ratio
- **`esvhd/pypbo`** — REFERENCE. Probability of Backtest Overfitting (PBO) — a complementary overfitting metric if we want it later.

## Exchange API + market data (§1, §2, §12)
- **`ccxt`** (MIT) — **ADOPT.** Unified exchange API, free, Binance testnet for paper trading. **Caveat that shapes the whole data layer:** `fetch_ohlcv`/`load_markets` only expose *currently-listed* symbols — it cannot supply delisted-pair history or point-in-time availability. So ccxt = live/testnet + current-symbol history; it is **not** the survivorship-safe source. https://github.com/ccxt/ccxt
- **`data.binance.vision`** — **ADOPT (primary historical source).** Binance's public data dumps of historical klines, **including delisted pairs**, back to listing. This is the ground-truth OHLCV + availability source the universe (§2) is built on. Pair with Binance listing/delisting announcements for `symbol_lifecycle` dates.
- **CoinGecko / CoinMarketCap** — **WRAP as cross-check only** (§2.1 step 2). Documented gaps for delisted mid-caps — never sole source for a lifecycle date.
- **No turnkey survivorship-safe crypto-universe library exists.** Universe construction (§2) is hand-built on the two sources above. This is the confirmed project bottleneck (budget weeks), not a modeling problem.

## Trial registry / append-only store (§6)
- **SQLite WAL** (stdlib `sqlite3`) — **ADOPT** as the append-only store. Immutability from: separate writer process + no UPDATE/DELETE code path + `BEFORE UPDATE/DELETE` triggers that RAISE + filesystem perms. No external dep needed; keep it boring and auditable. (See decision D4.)
- Event-store frameworks (eventstore, Marten, etc.) — **AVOID.** Massive overkill for single-user append-only rows.

## Donor / skeleton
No single donor repo fits — the value here is the *discipline*, not the plumbing, and the plumbing is thin. **Assemble** from the ADOPT list above rather than fork a skeleton. `purgedcv` is the closest thing to a load-bearing external dependency; everything else is glue we own.

## Reference reading
López de Prado, *Advances in Financial Machine Learning* — deflated/probabilistic Sharpe, CPCV, purging/embargo. The mathematical source of truth for §8/§13.
