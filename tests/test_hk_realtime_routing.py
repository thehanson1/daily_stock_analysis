# -*- coding: utf-8 -*-
"""
Regression tests for Hong Kong realtime quote routing.
"""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

if "litellm" not in sys.modules:
    sys.modules["litellm"] = MagicMock()
if "json_repair" not in sys.modules:
    sys.modules["json_repair"] = MagicMock()

from data_provider.base import DataFetcherManager


class _DummyFetcher:
    def __init__(self, name: str, priority: int, result=None, *, api_ready: bool = False):
        self.name = name
        self.priority = priority
        self.result = result
        self._api_ready = api_ready
        self.calls = []

    def get_realtime_quote(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result

    def is_api_ready(self) -> bool:
        return self._api_ready


class _DummyQuote:
    @staticmethod
    def has_basic_data():
        return True


class TestHKRealtimeRouting(unittest.TestCase):
    """Ensure HK realtime lookup does not fan out into A-share sources."""

    @patch("src.config.get_config")
    def test_manager_routes_hk_suffix_to_hk_specific_sources_only(self, mock_get_config):
        mock_get_config.return_value = SimpleNamespace(
            enable_realtime_quote=True,
            realtime_source_priority="tencent,akshare_sina,efinance,akshare_em,tushare",
        )

        yfinance = _DummyFetcher("YfinanceFetcher", 4, result=_DummyQuote())
        efinance = _DummyFetcher("EfinanceFetcher", 0, result={"should": "not be called"})
        akshare = _DummyFetcher("AkshareFetcher", 1, result=None)
        tushare = _DummyFetcher("TushareFetcher", 2, result={"should": "not be called"})

        manager = DataFetcherManager(fetchers=[efinance, akshare, tushare, yfinance])
        quote = manager.get_realtime_quote("1810.HK")

        self.assertIsNotNone(quote)
        self.assertEqual(yfinance.calls, [(("HK01810",), {})])
        self.assertEqual(akshare.calls, [])
        self.assertEqual(efinance.calls, [])
        self.assertEqual(tushare.calls, [])

    @patch("src.config.get_config")
    def test_manager_prefers_configured_api_fetcher_before_yfinance_for_hk(self, mock_get_config):
        mock_get_config.return_value = SimpleNamespace(
            enable_realtime_quote=True,
            realtime_source_priority="tencent,akshare_sina,efinance,akshare_em,tushare",
        )

        twelvedata = _DummyFetcher("TwelveDataFetcher", 2, result=_DummyQuote(), api_ready=True)
        longbridge = _DummyFetcher("LongbridgeFetcher", 5, result=_DummyQuote(), api_ready=True)
        yfinance = _DummyFetcher("YfinanceFetcher", 0, result=_DummyQuote())
        akshare = _DummyFetcher("AkshareFetcher", 1, result=_DummyQuote())

        manager = DataFetcherManager(fetchers=[yfinance, akshare, longbridge, twelvedata])
        quote = manager.get_realtime_quote("1810.HK")

        self.assertIsNotNone(quote)
        self.assertEqual(twelvedata.calls, [(("HK01810",), {})])
        self.assertEqual(longbridge.calls, [])
        self.assertEqual(yfinance.calls, [])
        self.assertEqual(akshare.calls, [])

    @patch("src.config.get_config")
    def test_manager_keeps_us_index_on_yfinance_first(self, mock_get_config):
        mock_get_config.return_value = SimpleNamespace(
            enable_realtime_quote=True,
            realtime_source_priority="tencent,akshare_sina,efinance,akshare_em,tushare",
        )

        yfinance = _DummyFetcher("YfinanceFetcher", 0, result=_DummyQuote())
        twelvedata = _DummyFetcher("TwelveDataFetcher", 2, result=_DummyQuote(), api_ready=True)
        longbridge = _DummyFetcher("LongbridgeFetcher", 5, result=_DummyQuote(), api_ready=True)

        manager = DataFetcherManager(fetchers=[twelvedata, longbridge, yfinance])
        quote = manager.get_realtime_quote("SPX")

        self.assertIsNotNone(quote)
        self.assertEqual(yfinance.calls, [(("SPX",), {})])
        self.assertEqual(twelvedata.calls, [])
        self.assertEqual(longbridge.calls, [])


if __name__ == "__main__":
    unittest.main()
