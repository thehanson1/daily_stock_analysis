# -*- coding: utf-8 -*-
"""Unit tests for TwelveDataFetcher."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from data_provider.realtime_types import RealtimeSource
from data_provider.twelvedata_fetcher import TwelveDataFetcher


def _make_fetcher() -> TwelveDataFetcher:
    fetcher = TwelveDataFetcher()
    fetcher._available = True
    fetcher._api_key = "demo-key"
    fetcher._timeout_seconds = 10
    fetcher._us_hk_enable = True
    return fetcher


def test_fetch_raw_data_uses_time_series_endpoint_for_hk_stock():
    fetcher = _make_fetcher()

    with patch.object(fetcher, "_resolve_symbol", return_value="00700.HK"), patch.object(
        fetcher,
        "_request",
        return_value={
            "values": [
                {
                    "datetime": "2026-04-07",
                    "open": "500.1",
                    "high": "505.0",
                    "low": "498.0",
                    "close": "503.2",
                    "volume": "1234567",
                }
            ]
        },
    ) as mock_request:
        df = fetcher._fetch_raw_data("0700", "2026-04-01", "2026-04-10")

    assert not df.empty
    mock_request.assert_called_once_with(
        "time_series",
        {
            "symbol": "00700.HK",
            "interval": "1day",
            "start_date": "2026-04-01",
            "end_date": "2026-04-10",
            "outputsize": 5000,
            "order": "asc",
            "format": "JSON",
        },
    )


def test_get_stock_name_uses_symbol_search_result():
    fetcher = _make_fetcher()

    with patch.object(
        fetcher,
        "_find_symbol_entry",
        return_value={"symbol": "00700.HK", "instrument_name": "Tencent Holdings Ltd"},
    ):
        name = fetcher.get_stock_name("HK00700")

    assert name == "Tencent Holdings Ltd"
    assert fetcher._symbol_cache["HK00700"] == "00700.HK"
    assert fetcher._stock_name_cache["HK00700"] == "Tencent Holdings Ltd"


def test_get_realtime_quote_returns_unified_quote():
    fetcher = _make_fetcher()
    fetcher._stock_name_cache["AAPL"] = "Apple Inc."

    with patch.object(fetcher, "_resolve_symbol", return_value="AAPL"), patch.object(
        fetcher,
        "_request",
        return_value={"price": "201.23"},
    ) as mock_request:
        quote = fetcher.get_realtime_quote("AAPL")

    assert quote is not None
    assert quote.code == "AAPL"
    assert quote.name == "Apple Inc."
    assert quote.price == 201.23
    assert quote.source == RealtimeSource.TWELVEDATA
    mock_request.assert_called_once_with("price", {"symbol": "AAPL", "dp": 4})


def test_normalize_data_rejects_missing_volume():
    fetcher = _make_fetcher()

    df = pd.DataFrame(
        [
            {
                "datetime": "2026-04-07",
                "open": "100.0",
                "high": "101.0",
                "low": "99.0",
                "close": "100.5",
            }
        ]
    )

    with pytest.raises(Exception, match="缺少关键字段"):
        fetcher._normalize_data(df, "AAPL")
