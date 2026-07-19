"""CoinGecko aggregator adapter — existence cross-check ONLY (decision D5).

GATE 0 established that CoinGecko exposes no exchange-specific listing/delisting
dates and caps free history at 365 days, so it is *never* a source for lifecycle
dates. Its sole role here: independently corroborate that a base asset exists, so
a Binance-native lifecycle can be marked `verified`. Symbol matching is by ticker
and therefore weak (tickers collide) — this is corroboration, not proof.

Vendor-isolated (seam 5): only this module knows CoinGecko's URLs and payloads.
"""

from __future__ import annotations

import json
import urllib.request
from urllib.error import HTTPError

_COINS_LIST_URL = "https://api.coingecko.com/api/v3/coins/list"
_HTTP_TIMEOUT_S = 30


class AggregatorError(RuntimeError):
    """Aggregator/network problem — surfaced, not swallowed (coding-style)."""


def _http_get_json(url: str):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise AggregatorError(f"HTTP {exc.code} fetching {url}") from exc
    except (OSError, ValueError) as exc:
        raise AggregatorError(f"error fetching {url}: {exc}") from exc


def list_coin_symbols() -> set[str]:
    """Return the set of lowercase base-asset tickers known to CoinGecko.

    Used for an existence check against Binance base assets. Raises AggregatorError
    on network/format failure so the caller decides how to proceed (rather than
    silently treating everything as unverified).
    """
    data = _http_get_json(_COINS_LIST_URL)
    if not isinstance(data, list):
        raise AggregatorError(f"unexpected /coins/list payload: {type(data).__name__}")
    return {
        str(coin["symbol"]).strip().lower()
        for coin in data
        if isinstance(coin, dict) and coin.get("symbol")
    }
