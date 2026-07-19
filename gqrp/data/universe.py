"""Point-in-time universe construction (spec §2, decision D5/D8/D12).

Builds a monthly universe by ranking Binance-native symbols on trailing average
daily quote (USD) volume — decision D12, chosen over reconstructed market cap
because point-in-time circulating supply is unsourceable within the D5
ground-truth constraint. The output is an **immutable, hash-locked**
`UniverseSnapshot`: written once, made read-only, and content-verified on load so
every backtest can trust the universe it references.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path

from .. import config
from .ohlcv import average_daily_quote_volume
from .types import OhlcvBar, SymbolLifecycle, UniverseRow, UniverseSnapshot

_SCHEMA_VERSION = 1
_RANKING_METRIC = "avg_daily_quote_volume_v1"  # decision D12; bump if the metric changes
DEFAULT_LOOKBACK_DAYS = 30


def config_fingerprint(
    *, lookback_days: int, top_n: int, min_volume: float, primary_quote: str
) -> str:
    """sha256 of every parameter that defines the universe.

    A change to any of these yields a different `config_hash`, so a snapshot built
    under different rules is never silently confused with another.
    """
    payload = {
        "ranking_metric": _RANKING_METRIC,
        "lookback_days": lookback_days,
        "top_n": top_n,
        "min_avg_daily_quote_volume_usd": min_volume,
        "primary_quote": primary_quote,
        "stablecoins": sorted(config.STABLECOINS),
        "wrapped": sorted(config.WRAPPED_ASSETS),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def _is_candidate(lc: SymbolLifecycle, snapshot_date: date, primary_quote: str) -> bool:
    """Point-in-time eligibility before the liquidity floor (spec §2 exclusions)."""
    return (
        lc.was_tradable_on(snapshot_date)
        and lc.quote_asset == primary_quote
        and not lc.is_stablecoin
        and not lc.is_wrapped
    )


def _canonical_blob(snapshot_date: date, config_hash: str, rows: tuple[UniverseRow, ...]) -> str:
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "snapshot_date": snapshot_date.isoformat(),
        "config_hash": config_hash,
        "rows": [
            {
                "symbol": r.symbol,
                "rank": r.rank,
                "avg_daily_volume": r.avg_daily_volume,
                "eligible": r.eligible,
                "market_cap": r.market_cap,
            }
            for r in rows
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _content_hash(snapshot_date: date, config_hash: str, rows: tuple[UniverseRow, ...]) -> str:
    return hashlib.sha256(_canonical_blob(snapshot_date, config_hash, rows).encode()).hexdigest()


def build_snapshot(
    snapshot_date: date,
    lifecycles: list[SymbolLifecycle],
    bars_by_symbol: dict[str, list[OhlcvBar]],
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    top_n: int = config.UNIVERSE_SIZE,
    min_volume: float = config.MIN_AVG_DAILY_QUOTE_VOLUME_USD,
    primary_quote: str = config.PRIMARY_QUOTE,
) -> UniverseSnapshot:
    """Reconstruct the universe as of `snapshot_date` (point-in-time, no lookahead).

    A symbol contributes only its history up to `snapshot_date`; delisted symbols
    tradable on that date are included (no survivorship). Rows are the top `top_n`
    candidates with data, ranked by trailing avg daily quote volume; `eligible`
    marks those clearing the liquidity floor.
    """
    scored: list[tuple[str, float]] = []
    for lc in lifecycles:
        if not _is_candidate(lc, snapshot_date, primary_quote):
            continue
        avg = average_daily_quote_volume(
            bars_by_symbol.get(lc.symbol, []), as_of=snapshot_date, lookback_days=lookback_days
        )
        if avg is None:
            continue  # unsourceable in-window → excluded, not approximated (spec §2.1)
        scored.append((lc.symbol, avg))

    # Rank by volume desc, symbol asc as a deterministic tie-break.
    scored.sort(key=lambda t: (-t[1], t[0]))
    rows = tuple(
        UniverseRow(
            symbol=sym,
            rank=i + 1,
            avg_daily_volume=avg,
            eligible=avg >= min_volume,
        )
        for i, (sym, avg) in enumerate(scored[:top_n])
    )

    config_hash = config_fingerprint(
        lookback_days=lookback_days, top_n=top_n, min_volume=min_volume, primary_quote=primary_quote
    )
    return UniverseSnapshot(
        snapshot_date=snapshot_date,
        config_hash=config_hash,
        rows=rows,
        content_hash=_content_hash(snapshot_date, config_hash, rows),
    )


def snapshot_path(out_dir: Path, snapshot_date: date) -> Path:
    return out_dir / f"universe-{snapshot_date.isoformat()}.json"


def write_snapshot(snapshot: UniverseSnapshot, out_dir: Path) -> Path:
    """Write the snapshot once as a read-only, hash-locked file.

    Refuses to overwrite an existing snapshot — a hash-locked universe is
    immutable (spec §2). Re-run under a new config → new content, but the same
    date+config must never be silently rewritten.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(out_dir, snapshot.snapshot_date)
    if path.exists():
        raise FileExistsError(f"universe snapshot already exists (immutable): {path}")

    blob = _canonical_blob(snapshot.snapshot_date, snapshot.config_hash, snapshot.rows)
    doc = json.loads(blob)
    doc["content_hash"] = snapshot.content_hash
    path.write_text(json.dumps(doc, indent=2, sort_keys=True))
    os.chmod(path, 0o444)  # read-only at the filesystem level
    return path


def load_snapshot(path: Path) -> UniverseSnapshot:
    """Load and verify a snapshot; raises if the content hash doesn't match."""
    doc = json.loads(Path(path).read_text())
    snapshot_date = date.fromisoformat(doc["snapshot_date"])
    config_hash = doc["config_hash"]
    rows = tuple(
        UniverseRow(
            symbol=r["symbol"],
            rank=r["rank"],
            avg_daily_volume=r["avg_daily_volume"],
            eligible=r["eligible"],
            market_cap=r.get("market_cap"),
        )
        for r in doc["rows"]
    )
    recomputed = _content_hash(snapshot_date, config_hash, rows)
    stored = doc.get("content_hash")
    if recomputed != stored:
        raise ValueError(
            f"universe snapshot hash mismatch for {path}: "
            f"stored {stored}, recomputed {recomputed} (file tampered or corrupt)"
        )
    return UniverseSnapshot(
        snapshot_date=snapshot_date, config_hash=config_hash, rows=rows, content_hash=stored
    )
