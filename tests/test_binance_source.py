import hashlib
import io
import zipfile

import pytest

from gqrp.data.binance_source import (
    DataSourceError,
    _unzip_csv,
    _verify_checksum,
    parse_klines_csv,
)

# Two real SRMUSDT daily rows (2020-08-11 and the truncated 2022-11-28 halt bar).
_DATA_ROWS = (
    "1597104000000,0.11000000,5.00000000,0.11000000,1.56290000,60097839.17000000,"
    "1597190399999,78655176.41774700,123107,28521156.15000000,37623804.13243200,0\n"
    "1669593600000,0.25675000,0.25768000,0.23855000,0.24442000,991959.60000000,"
    "1669604399999,246832.12941000,1946,375110.70000000,93170.81426100,0\n"
)
_HEADER = ("open_time,open,high,low,close,volume,close_time,quote_volume,count,"
           "taker_buy_base,taker_buy_quote,ignore\n")


def test_parse_rows_without_header():
    bars = parse_klines_csv(_DATA_ROWS, "SRMUSDT")
    assert len(bars) == 2
    assert bars[0].open == 0.11 and bars[0].close == 1.5629
    assert bars[0].quote_volume == 78655176.417747
    assert bars[0].is_partial is False
    assert bars[1].is_partial is True  # 3-hour halt bar


def test_parse_skips_header_row():
    bars = parse_klines_csv(_HEADER + _DATA_ROWS, "SRMUSDT")
    assert len(bars) == 2


def test_parse_blank_lines_ignored():
    assert parse_klines_csv("\n\n" + _DATA_ROWS + "\n", "SRMUSDT")


def test_parse_malformed_row_raises():
    with pytest.raises(DataSourceError):
        parse_klines_csv("1597104000000,0.11,5.0\n", "SRMUSDT")


def _zip_of(csv_text: str, name: str = "SRMUSDT-1d-2020-08.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, csv_text)
    return buf.getvalue()


def test_unzip_extracts_csv():
    assert _unzip_csv(_zip_of(_DATA_ROWS)) == _DATA_ROWS


def test_checksum_verify_passes_on_match():
    zip_bytes = _zip_of(_DATA_ROWS)
    good = f"{hashlib.sha256(zip_bytes).hexdigest()}  SRMUSDT-1d-2020-08.zip"
    _verify_checksum(zip_bytes, good, "SRMUSDT-1d-2020-08.zip")  # no raise


def test_checksum_verify_raises_on_mismatch():
    zip_bytes = _zip_of(_DATA_ROWS)
    bad = f"{'0' * 64}  SRMUSDT-1d-2020-08.zip"
    with pytest.raises(DataSourceError, match="checksum mismatch"):
        _verify_checksum(zip_bytes, bad, "SRMUSDT-1d-2020-08.zip")


def test_checksum_verify_raises_on_malformed():
    with pytest.raises(DataSourceError, match="malformed"):
        _verify_checksum(b"x", "not-a-hash", "f.zip")
