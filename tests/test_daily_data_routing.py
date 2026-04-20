# -*- coding: utf-8 -*-
"""Regression tests for daily-data market routing."""

from __future__ import annotations

import pandas as pd

from data_provider.base import DataFetcherManager


class _DummyFetcher:
    def __init__(
        self,
        name: str,
        result: pd.DataFrame | None = None,
        error: Exception | None = None,
        *,
        priority: int = 99,
        api_ready: bool = False,
    ):
        self.name = name
        self.priority = priority
        self._result = result
        self._error = error
        self._api_ready = api_ready
        self.called = False

    def get_daily_data(self, stock_code: str, start_date=None, end_date=None, days: int = 30):
        self.called = True
        if self._error is not None:
            raise self._error
        return self._result

    def is_api_ready(self) -> bool:
        return self._api_ready


def test_cn_daily_data_skips_longbridge_fetcher():
    manager = DataFetcherManager.__new__(DataFetcherManager)
    first = _DummyFetcher("EfinanceFetcher", error=RuntimeError("efinance unavailable"))
    longbridge = _DummyFetcher("LongbridgeFetcher", error=AssertionError("should not be called"))
    fallback = _DummyFetcher(
        "BaostockFetcher",
        result=pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-04-07", "2026-04-08"]),
                "open": [1.0, 1.1],
                "high": [1.1, 1.2],
                "low": [0.9, 1.0],
                "close": [1.05, 1.15],
                "volume": [100, 110],
            }
        ),
    )
    manager._fetchers = [first, longbridge, fallback]

    df, source = manager.get_daily_data("600519")

    assert source == "BaostockFetcher"
    assert not df.empty
    assert first.called is True
    assert longbridge.called is False
    assert fallback.called is True


def test_us_daily_data_prefers_configured_api_fetchers_before_yfinance():
    manager = DataFetcherManager.__new__(DataFetcherManager)
    twelvedata = _DummyFetcher(
        "TwelveDataFetcher",
        result=pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-04-07", "2026-04-08"]),
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [1000, 1100],
            }
        ),
        priority=2,
        api_ready=True,
    )
    longbridge = _DummyFetcher(
        "LongbridgeFetcher",
        error=AssertionError("should not be called after Twelve Data succeeds"),
        priority=5,
        api_ready=True,
    )
    yfinance = _DummyFetcher(
        "YfinanceFetcher",
        error=AssertionError("should not be called before configured API fetchers"),
        priority=0,
    )
    manager._fetchers = [yfinance, longbridge, twelvedata]

    df, source = manager.get_daily_data("AAPL")

    assert source == "TwelveDataFetcher"
    assert not df.empty
    assert twelvedata.called is True
    assert longbridge.called is False
    assert yfinance.called is False


def test_us_daily_data_without_api_fetchers_uses_yfinance_only():
    manager = DataFetcherManager.__new__(DataFetcherManager)
    twelvedata = _DummyFetcher(
        "TwelveDataFetcher",
        error=AssertionError("disabled API fetcher should not be called"),
        priority=2,
        api_ready=False,
    )
    longbridge = _DummyFetcher(
        "LongbridgeFetcher",
        error=AssertionError("disabled API fetcher should not be called"),
        priority=5,
        api_ready=False,
    )
    yfinance = _DummyFetcher(
        "YfinanceFetcher",
        result=pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-04-07", "2026-04-08"]),
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [1000, 1100],
            }
        ),
        priority=0,
    )
    manager._fetchers = [yfinance, longbridge, twelvedata]

    df, source = manager.get_daily_data("AAPL")

    assert source == "YfinanceFetcher"
    assert not df.empty
    assert twelvedata.called is False
    assert longbridge.called is False
    assert yfinance.called is True


def test_us_daily_data_falls_back_to_yfinance_after_api_chain_failure():
    manager = DataFetcherManager.__new__(DataFetcherManager)
    twelvedata = _DummyFetcher(
        "TwelveDataFetcher",
        error=RuntimeError("twelvedata unavailable"),
        priority=2,
        api_ready=True,
    )
    longbridge = _DummyFetcher(
        "LongbridgeFetcher",
        error=RuntimeError("longbridge unavailable"),
        priority=5,
        api_ready=True,
    )
    yfinance = _DummyFetcher(
        "YfinanceFetcher",
        result=pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-04-07", "2026-04-08"]),
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [1000, 1100],
            }
        ),
        priority=0,
    )
    manager._fetchers = [yfinance, longbridge, twelvedata]

    df, source = manager.get_daily_data("AAPL")

    assert source == "YfinanceFetcher"
    assert not df.empty
    assert twelvedata.called is True
    assert longbridge.called is True
    assert yfinance.called is True


def test_us_index_daily_data_keeps_yfinance_first():
    manager = DataFetcherManager.__new__(DataFetcherManager)
    yfinance = _DummyFetcher(
        "YfinanceFetcher",
        result=pd.DataFrame(
            {
                "date": pd.to_datetime(["2026-04-07", "2026-04-08"]),
                "open": [5000.0, 5010.0],
                "high": [5010.0, 5020.0],
                "low": [4990.0, 5000.0],
                "close": [5005.0, 5015.0],
                "volume": [1000, 1100],
            }
        ),
        priority=99,
    )
    twelvedata = _DummyFetcher(
        "TwelveDataFetcher",
        error=AssertionError("US indices should not route to Twelve Data first"),
        priority=2,
        api_ready=True,
    )
    longbridge = _DummyFetcher(
        "LongbridgeFetcher",
        error=AssertionError("yfinance success should stop the index chain"),
        priority=5,
        api_ready=True,
    )
    manager._fetchers = [twelvedata, longbridge, yfinance]

    df, source = manager.get_daily_data("SPX")

    assert source == "YfinanceFetcher"
    assert not df.empty
    assert yfinance.called is True
    assert twelvedata.called is False
    assert longbridge.called is False
