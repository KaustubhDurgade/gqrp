"""Domain types for the data layer (spec §A).

Immutable by default (coding-style). Timestamps are epoch-milliseconds UTC —
the exchange-native ground truth per decision D11. Convenience `date` fields are
derived, never authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

DAY_MS = 86_400_000
# A complete Binance daily kline spans open_time .. open_time + DAY_MS - 1.
COMPLETE_DAY_SPAN_MS = DAY_MS - 1


def ms_to_date(ms: int) -> date:
    """Epoch-ms (UTC) → calendar date."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()


@dataclass(frozen=True, slots=True)
class OhlcvBar:
    """A single daily bar (spec §A `ohlcv_bar`).

    `open_time_ms` / `close_time_ms` are the ground truth; `date` derives from
    `open_time_ms`. `is_partial` flags a truncated final bar — the delisting/halt
    signal established in decision D11.
    """

    symbol: str
    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    source: str

    @property
    def date(self) -> date:
        return ms_to_date(self.open_time_ms)

    @property
    def span_ms(self) -> int:
        return self.close_time_ms - self.open_time_ms

    @property
    def is_partial(self) -> bool:
        """True if this daily bar covers less than a full day (trading halted)."""
        return self.span_ms < COMPLETE_DAY_SPAN_MS


@dataclass(frozen=True, slots=True)
class SymbolLifecycle:
    """Point-in-time availability spine (spec §A `symbol_lifecycle`).

    `delisting_date` is None while the symbol still trades. `source` is
    'binance-native' or 'aggregator-crosscheck'; `verified` is True only once an
    aggregator cross-check has confirmed it (decision D5).
    """

    symbol: str
    venue: str
    listing_date: date
    delisting_date: date | None
    base_asset: str
    quote_asset: str
    is_stablecoin: bool
    is_wrapped: bool
    source: str
    verified: bool

    @property
    def is_delisted(self) -> bool:
        return self.delisting_date is not None

    def was_tradable_on(self, day: date) -> bool:
        """Point-in-time availability check — the whole reason this type exists."""
        if day < self.listing_date:
            return False
        if self.delisting_date is not None and day > self.delisting_date:
            return False
        return True


@dataclass(frozen=True, slots=True)
class UniverseRow:
    """One candidate in a monthly universe reconstruction (spec §A).

    `avg_daily_volume` is the ranking key (decision D12 — Binance-native dollar
    volume, not reconstructed market cap). `market_cap` is nullable, reserved for
    a future aggregator annotation and never used for selection.
    """

    symbol: str
    rank: int
    avg_daily_volume: float
    eligible: bool
    market_cap: float | None = None


@dataclass(frozen=True, slots=True)
class UniverseSnapshot:
    """Immutable, hash-locked monthly universe (spec §A `universe_snapshot`).

    `content_hash` is the sha256 of the canonical serialization and is what every
    backtest references. `config_hash` fingerprints the universe-defining config
    so a parameter change produces a detectably different universe.
    """

    snapshot_date: date
    config_hash: str
    rows: tuple[UniverseRow, ...]
    content_hash: str

    @property
    def eligible_symbols(self) -> tuple[str, ...]:
        return tuple(r.symbol for r in self.rows if r.eligible)
