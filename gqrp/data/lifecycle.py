"""Symbol lifecycle construction (spec §2.1, decision D5/D11).

Derives point-in-time availability (`SymbolLifecycle`) from Binance-native klines.
Listing = first bar's date. Delisting is inferred from two exchange-native signals:
a *partial* final daily bar (intraday halt — the SRMUSDT pattern, D11) or coverage
that stops well before the present. Aggregator cross-check (D5) is a separate,
later step; until then `verified=False` and `source='binance-native'`.
"""

from __future__ import annotations

from datetime import date, timedelta

from .. import config
from .types import OhlcvBar, SymbolLifecycle

# Daily dumps lag ~1–2 days; anything quieter than this without fresh bars is
# treated as delisted at its last bar. Generous to avoid false delistings.
_STALE_THRESHOLD_DAYS = 5


def classify_symbol(symbol: str) -> tuple[str, str, bool, bool]:
    """Split a Binance symbol into (base, quote, is_stablecoin, is_wrapped).

    Matches the longest known quote suffix (config.KNOWN_QUOTE_ASSETS is ordered
    so USDT is tried before USDC before BTC, etc.).
    """
    sym = symbol.upper()
    for quote in config.KNOWN_QUOTE_ASSETS:
        if sym.endswith(quote) and len(sym) > len(quote):
            base = sym[: -len(quote)]
            is_stable = base in config.STABLECOINS
            is_wrapped = base in config.WRAPPED_ASSETS
            return base, quote, is_stable, is_wrapped
    raise ValueError(f"cannot parse quote asset from symbol {symbol!r}")


def infer_delisting_date(bars: list[OhlcvBar], *, today: date) -> date | None:
    """Delisting date, or None if the symbol appears to still trade.

    Signals (either triggers delisting):
      1. The final daily bar is partial → intraday trading halt (decision D11).
      2. Coverage stops more than _STALE_THRESHOLD_DAYS before `today`.
    """
    if not bars:
        return None
    last = bars[-1]
    if last.is_partial:
        return last.date
    if last.date < today - timedelta(days=_STALE_THRESHOLD_DAYS):
        return last.date
    return None


def build_lifecycle(
    symbol: str,
    bars: list[OhlcvBar],
    *,
    today: date,
    venue: str = "binance",
    source: str = "binance-native",
    verified: bool = False,
) -> SymbolLifecycle:
    """Construct a SymbolLifecycle from a symbol's full Binance-native history.

    Raises DataSourceError-free ValueError if there are no bars (an unsourceable
    asset must be excluded, not approximated — spec §2.1 step 3).
    """
    if not bars:
        raise ValueError(f"no bars for {symbol!r} — exclude, do not approximate (spec §2.1)")
    base, quote, is_stablecoin, is_wrapped = classify_symbol(symbol)
    ordered = sorted(bars, key=lambda b: b.open_time_ms)
    return SymbolLifecycle(
        symbol=symbol,
        venue=venue,
        listing_date=ordered[0].date,
        delisting_date=infer_delisting_date(ordered, today=today),
        base_asset=base,
        quote_asset=quote,
        is_stablecoin=is_stablecoin,
        is_wrapped=is_wrapped,
        source=source,
        verified=verified,
    )
