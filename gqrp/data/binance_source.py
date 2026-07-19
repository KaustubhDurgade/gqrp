"""Binance-native market data adapter (architecture seam 5, decision D5).

Ground truth = `data.binance.vision` daily klines, including delisted pairs.
Every downloaded file is SHA-256-verified against its published `.CHECKSUM`
(decision D11). Only this module knows the vendor's URLs, XML listing format, and
CSV column order; callers get `OhlcvBar` objects.

Stdlib-only by design so the data pipeline runs without the heavy quant deps.
"""

from __future__ import annotations

import hashlib
import io
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from urllib.error import HTTPError

from .types import OhlcvBar

# S3 REST listing endpoint (returns XML); CloudFront front for actual objects.
_S3_LIST_ENDPOINT = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
_DATA_BASE = "https://data.binance.vision"
_HTTP_TIMEOUT_S = 30
_SOURCE = "binance-native"

_MONTH_RE = re.compile(r"-(\d{4}-\d{2})\.zip$")
# S3 ListBucketResult namespace
_S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


class DataSourceError(RuntimeError):
    """Vendor/data problem — surfaced instead of silently swallowed (coding-style)."""


def _http_get(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=_HTTP_TIMEOUT_S) as resp:
            return resp.read()
    except HTTPError as exc:  # noqa: PERF203 — want the URL in the message
        raise DataSourceError(f"HTTP {exc.code} fetching {url}") from exc
    except OSError as exc:
        raise DataSourceError(f"network error fetching {url}: {exc}") from exc


def _monthly_prefix(symbol: str, interval: str) -> str:
    return f"data/spot/monthly/klines/{symbol}/{interval}/"


def _object_url(symbol: str, interval: str, month: str, ext: str) -> str:
    prefix = _monthly_prefix(symbol, interval)
    return f"{_DATA_BASE}/{prefix}{symbol}-{interval}-{month}{ext}"


def list_monthly_klines(symbol: str, interval: str = "1d") -> list[str]:
    """Return available months (``YYYY-MM``), ascending. Empty if none exist.

    The coverage window is exchange-native ground truth: first month ≈ listing,
    last month ≈ delisting/halt (decision D11).
    """
    prefix = _monthly_prefix(symbol, interval)
    url = f"{_S3_LIST_ENDPOINT}?prefix={prefix}"
    xml_bytes = _http_get(url)
    root = ET.fromstring(xml_bytes)
    months: set[str] = set()
    for key_el in root.findall(".//s3:Contents/s3:Key", _S3_NS):
        key = (key_el.text or "").strip()
        if key.endswith(".CHECKSUM"):
            continue
        m = _MONTH_RE.search(key)
        if m:
            months.add(m.group(1))
    return sorted(months)


_KLINES_ROOT = "data/spot/monthly/klines/"


def list_all_symbols() -> list[str]:
    """Every symbol with published spot klines — current *and* delisted.

    Paginates the S3 delimiter listing (CommonPrefixes). This is the survivorship-
    safe symbol universe: delisted pairs appear here because their history is never
    deleted (decision D5/D11). Filtering by quote/liquidity happens downstream.
    Symbol directories are interval-agnostic, so no interval argument is needed.
    """
    root = _KLINES_ROOT
    symbols: set[str] = set()
    marker = ""
    while True:
        url = f"{_S3_LIST_ENDPOINT}?prefix={root}&delimiter=/"
        if marker:
            url += f"&marker={marker}"
        root_el = ET.fromstring(_http_get(url))
        prefixes = root_el.findall(".//s3:CommonPrefixes/s3:Prefix", _S3_NS)
        for pre_el in prefixes:
            pre = (pre_el.text or "").strip().rstrip("/")
            sym = pre.rsplit("/", 1)[-1]
            # Klines with a non-daily interval share the symbol dir; the symbol is
            # the last path segment regardless of interval, so this holds.
            if sym:
                symbols.add(sym)
        truncated = (root_el.findtext("s3:IsTruncated", default="false", namespaces=_S3_NS) or "").strip()
        if truncated.lower() != "true":
            break
        next_marker = root_el.findtext("s3:NextMarker", default="", namespaces=_S3_NS) or ""
        if not next_marker and prefixes:
            next_marker = (prefixes[-1].text or "").strip()
        if not next_marker:
            break
        marker = next_marker
    return sorted(symbols)


def _verify_checksum(zip_bytes: bytes, checksum_text: str, filename: str) -> None:
    """Raise DataSourceError unless SHA-256(zip_bytes) matches the published sum."""
    expected = checksum_text.split()[0].strip().lower() if checksum_text.split() else ""
    if len(expected) != 64:
        raise DataSourceError(f"malformed CHECKSUM for {filename}: {checksum_text!r}")
    actual = hashlib.sha256(zip_bytes).hexdigest()
    if actual != expected:
        raise DataSourceError(
            f"checksum mismatch for {filename}: expected {expected}, got {actual}"
        )


def _fetch_verified_zip(
    symbol: str, interval: str, month: str, cache_dir: Path | None
) -> bytes:
    """Fetch a monthly zip and verify it. Uses cache_dir if the file is present."""
    fname = f"{symbol}-{interval}-{month}.zip"
    cached = cache_dir / fname if cache_dir else None
    if cached and cached.exists():
        return cached.read_bytes()

    zip_bytes = _http_get(_object_url(symbol, interval, month, ".zip"))
    checksum_text = _http_get(
        _object_url(symbol, interval, month, ".zip.CHECKSUM")
    ).decode("utf-8", "replace")
    _verify_checksum(zip_bytes, checksum_text, fname)

    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / fname).write_bytes(zip_bytes)
    return zip_bytes


def _unzip_csv(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not names:
            raise DataSourceError("no CSV inside kline zip")
        return zf.read(names[0]).decode("utf-8")


def parse_klines_csv(csv_text: str, symbol: str, source: str = _SOURCE) -> list[OhlcvBar]:
    """Parse Binance kline CSV → OhlcvBar list. Tolerates an optional header row.

    Column order: open_time, open, high, low, close, volume, close_time,
    quote_asset_volume, count, taker_buy_base, taker_buy_quote, ignore.
    """
    bars: list[OhlcvBar] = []
    for line in csv_text.splitlines():
        line = line.strip()
        if not line:
            continue
        cols = line.split(",")
        if not cols[0].lstrip("-").isdigit():
            continue  # header row
        if len(cols) < 8:
            raise DataSourceError(f"unexpected kline row for {symbol}: {line!r}")
        bars.append(
            OhlcvBar(
                symbol=symbol,
                open_time_ms=int(cols[0]),
                close_time_ms=int(cols[6]),
                open=float(cols[1]),
                high=float(cols[2]),
                low=float(cols[3]),
                close=float(cols[4]),
                volume=float(cols[5]),
                quote_volume=float(cols[7]),
                source=source,
            )
        )
    return bars


def load_klines(
    symbol: str,
    interval: str = "1d",
    months: list[str] | None = None,
    cache_dir: Path | None = None,
) -> list[OhlcvBar]:
    """Load all (or the given) monthly klines for a symbol, ascending by open time.

    Every file is checksum-verified before use. Returns [] if the symbol has no
    published history (never traded on this venue).
    """
    if months is None:
        months = list_monthly_klines(symbol, interval)
    bars: list[OhlcvBar] = []
    for month in months:
        zip_bytes = _fetch_verified_zip(symbol, interval, month, cache_dir)
        bars.extend(parse_klines_csv(_unzip_csv(zip_bytes), symbol))
    bars.sort(key=lambda b: b.open_time_ms)
    return bars
