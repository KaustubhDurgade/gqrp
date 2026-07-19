"""Declared constants — cost model, windows, thresholds, exclusions.

Everything the spec says must be "declared in config" lives here as an immutable
constant. No magic numbers scattered across the codebase (coding-style). These are
research parameters, fixed in advance; changing one is a decision, not a tweak.
"""

from __future__ import annotations

from datetime import date

# ── Market scope (spec §1) ──────────────────────────────────────────────────
ASSET_CLASS = "crypto-spot"
BAR_INTERVAL = "1d"
REBALANCE = "weekly"
UNIVERSE_SIZE = 50          # ~candidates ranked
UNIVERSE_HOLD = 10          # top-N held
BACKTEST_START = date(2018, 1, 1)
CAPITAL_USD = 10_000.0

# ── Cost model (spec §1) — per side ─────────────────────────────────────────
TAKER_FEE = 0.001           # 0.1%
SLIPPAGE = 0.0015           # 0.15%
COST_PER_SIDE = TAKER_FEE + SLIPPAGE

# ── Data windows (spec §10, decision D10 — holdout locked 2026-07-18) ────────
DEV_START = date(2018, 1, 1)
DEV_END = date(2022, 12, 31)
VALIDATION_START = date(2023, 1, 1)
VALIDATION_END = date(2024, 12, 31)
HOLDOUT_START = date(2025, 1, 1)
HOLDOUT_END = date(2026, 9, 30)     # fixed & locked; do NOT extend (D10)

# ── Universe filters (spec §2) ──────────────────────────────────────────────
MIN_AVG_DAILY_QUOTE_VOLUME_USD = 1_000_000.0   # liquidity floor, declared
PRIMARY_QUOTE = "USDT"

# Excluded base assets (spec §2 — no stablecoins, no wrapped). Non-exhaustive but
# declared; add here rather than inline. Matched case-insensitively.
STABLECOINS = frozenset({
    "USDT", "USDC", "BUSD", "TUSD", "DAI", "FDUSD", "USDP", "GUSD",
    "UST", "USTC", "PAX", "SUSD", "USDD", "FRAX", "LUSD", "EUR", "AEUR",
})
WRAPPED_ASSETS = frozenset({
    "WBTC", "WETH", "WBETH", "BTCB", "WBNB", "STETH", "WSTETH", "CBETH",
})

# Binance spot quote assets, longest-first so suffix matching is unambiguous
# (e.g. must try USDT before USDC before BTC). Adapter/lifecycle use this.
KNOWN_QUOTE_ASSETS = (
    "USDT", "FDUSD", "TUSD", "BUSD", "USDC", "DAI",
    "BTC", "ETH", "BNB", "XRP", "TRX", "EUR", "TRY", "BRL", "GBP",
)

# ── Economic viability gate (spec §9) ───────────────────────────────────────
MIN_CAPACITY_USD = 50_000.0

# ── Statistical gate (spec §8) ──────────────────────────────────────────────
DEFLATED_SHARPE_CONFIDENCE = 0.95
