# -*- coding: utf-8 -*-
"""
Tests for fundamental adapter helpers.
"""

import os
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.fundamental_adapter import (
    AkshareFundamentalAdapter,
    UsSecFundamentalAdapter,
    _extract_latest_row,
)


class TestFundamentalAdapter(unittest.TestCase):
    def test_extract_latest_row_returns_none_when_code_mismatch(self) -> None:
        df = pd.DataFrame(
            {
                "股票代码": ["600000", "000001"],
                "值": [1, 2],
            }
        )
        row = _extract_latest_row(df, "600519")
        self.assertIsNone(row)

    def test_extract_latest_row_fallback_when_no_code_column(self) -> None:
        df = pd.DataFrame({"值": [1, 2]})
        row = _extract_latest_row(df, "600519")
        self.assertIsNotNone(row)
        self.assertEqual(row["值"], 1)

    def test_dragon_tiger_no_match_with_code_column_is_ok(self) -> None:
        adapter = AkshareFundamentalAdapter()
        df = pd.DataFrame(
            {
                "股票代码": ["600000"],
                "日期": ["2026-01-01"],
            }
        )
        with patch.object(adapter, "_call_df_candidates", return_value=(df, "stock_lhb_stock_statistic_em", [])):
            result = adapter.get_dragon_tiger_flag("600519")
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["is_on_list"])
        self.assertEqual(result["recent_count"], 0)

    def test_dragon_tiger_match_is_ok(self) -> None:
        adapter = AkshareFundamentalAdapter()
        today = pd.Timestamp.now().strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "股票代码": ["600519"],
                "日期": [today],
            }
        )
        with patch.object(adapter, "_call_df_candidates", return_value=(df, "stock_lhb_stock_statistic_em", [])):
            result = adapter.get_dragon_tiger_flag("600519")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["is_on_list"])
        self.assertGreaterEqual(result["recent_count"], 1)

    def test_northbound_flow_converts_to_yi(self) -> None:
        adapter = AkshareFundamentalAdapter()
        df = pd.DataFrame({"当日净流入": [1_230_000_000]})
        with patch.object(adapter, "_call_df_candidates", return_value=(df, "stock_hsgt_north_net_flow_in_em", [])):
            result = adapter.get_northbound_flow()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["net_inflow"], 12.3)

    def test_us_sec_adapter_extracts_growth_filings_and_institution(self) -> None:
        adapter = UsSecFundamentalAdapter()
        now = pd.Timestamp.now()
        recent_10q = (now - pd.Timedelta(days=20)).strftime("%Y-%m-%d")
        recent_form4 = (now - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        recent_13g = (now - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        older_quarter = (now - pd.Timedelta(days=110)).strftime("%Y-%m-%d")

        submissions = {
            "cik": "320193",
            "filings": {
                "recent": {
                    "form": ["10-Q", "4", "13G"],
                    "filingDate": [recent_10q, recent_form4, recent_13g],
                    "accessionNumber": [
                        "0000320193-26-000010",
                        "0000320193-26-000011",
                        "0000320193-26-000012",
                    ],
                    "primaryDocument": ["a10q.htm", "xslF345X05/form4.xml", "schedule13g.htm"],
                }
            },
        }
        companyfacts = {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {
                                    "start": "2025-10-01",
                                    "end": "2025-12-31",
                                    "val": 120.0,
                                    "form": "10-Q",
                                    "filed": recent_10q,
                                },
                                {
                                    "start": "2025-07-01",
                                    "end": "2025-09-30",
                                    "val": 100.0,
                                    "form": "10-Q",
                                    "filed": older_quarter,
                                },
                            ]
                        }
                    },
                    "NetIncomeLoss": {
                        "units": {
                            "USD": [
                                {
                                    "start": "2025-10-01",
                                    "end": "2025-12-31",
                                    "val": 24.0,
                                    "form": "10-Q",
                                    "filed": recent_10q,
                                },
                                {
                                    "start": "2025-07-01",
                                    "end": "2025-09-30",
                                    "val": 20.0,
                                    "form": "10-Q",
                                    "filed": older_quarter,
                                },
                            ]
                        }
                    },
                    "GrossProfit": {
                        "units": {
                            "USD": [
                                {
                                    "start": "2025-10-01",
                                    "end": "2025-12-31",
                                    "val": 48.0,
                                    "form": "10-Q",
                                    "filed": recent_10q,
                                }
                            ]
                        }
                    },
                    "StockholdersEquity": {
                        "units": {
                            "USD": [
                                {
                                    "end": "2025-12-31",
                                    "val": 400.0,
                                    "form": "10-Q",
                                    "filed": recent_10q,
                                }
                            ]
                        }
                    },
                }
            }
        }

        with patch.object(
            adapter,
            "_load_ticker_map",
            return_value={"AAPL": {"cik": "0000320193", "title": "Apple Inc."}},
        ), patch.object(adapter, "_get_json", side_effect=[submissions, companyfacts]):
            result = adapter.get_fundamental_bundle("AAPL")

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["growth"]["revenue_yoy"], 20.0)
        self.assertEqual(result["growth"]["net_profit_yoy"], 20.0)
        self.assertEqual(result["growth"]["roe"], 24.0)
        self.assertEqual(result["growth"]["gross_margin"], 40.0)
        self.assertEqual(result["earnings"]["latest_filing_form"], "10-Q")
        self.assertEqual(result["institution"]["insider_form4_count_90d"], 1)
        self.assertEqual(result["institution"]["ownership_disclosure_count_180d"], 1)

    def test_us_sec_adapter_extracts_china_exposure_from_filing_text(self) -> None:
        adapter = UsSecFundamentalAdapter()
        recent_10k = "2026-02-01"
        submissions = {
            "cik": "1045810",
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "filingDate": [recent_10k],
                    "accessionNumber": ["0001045810-26-000001"],
                    "primaryDocument": ["annual.htm"],
                }
            },
        }
        filing_text = """
        <html><body>
        Greater China revenue remained material during the fiscal year.
        Our supply chain and manufacturing partners in China continued to support production.
        Export controls affecting China remained a material risk factor.
        </body></html>
        """

        with patch.object(
            adapter,
            "_load_ticker_map",
            return_value={"NVDA": {"cik": "0001045810", "title": "NVIDIA Corporation"}},
        ), patch.object(adapter, "_get_json", return_value=submissions), \
                patch.object(adapter, "_get_text", return_value=filing_text):
            result = adapter.get_china_exposure_summary("NVDA")

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["level"], "high")
        self.assertIn("revenue", result["signals"])
        self.assertIn("supply_chain", result["signals"])
        self.assertTrue(result["evidence"])


    # --- #1034: get_fundamental_bundle fail-open regression ---

    def test_fundamental_bundle_all_sources_fail_returns_not_supported(self):
        """所有数据源失败时应返回 not_supported 而非抛异常。"""
        adapter = AkshareFundamentalAdapter()
        with patch.object(adapter, "_call_df_candidates", return_value=(None, None, ["stock_financial_abstract:ImportError"])):
            result = adapter.get_fundamental_bundle("600519")
        self.assertEqual(result["status"], "not_supported")
        self.assertIn("stock_financial_abstract:ImportError", result["errors"])
        self.assertEqual(result["growth"], {})
        self.assertEqual(result["earnings"], {})
        self.assertIsInstance(result["source_chain"], list)

    def test_fundamental_bundle_partial_growth_only(self):
        """仅 growth 数据源成功时应返回 partial。"""
        adapter = AkshareFundamentalAdapter()
        fin_df = pd.DataFrame({
            "股票代码": ["600519"],
            "营业收入同比": [15.3],
            "净利润同比": [20.1],
            "净资产收益率": [28.5],
            "毛利率": [91.2],
        })
        call_count = 0
        def _mock_call(candidates):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (fin_df, "stock_financial_abstract", [])
            return (None, None, [f"source{call_count}:ConnectionError"])
        with patch.object(adapter, "_call_df_candidates", side_effect=_mock_call):
            result = adapter.get_fundamental_bundle("600519")
        self.assertEqual(result["status"], "partial")
        self.assertIn("revenue_yoy", result["growth"])
        self.assertAlmostEqual(result["growth"]["revenue_yoy"], 15.3)
        self.assertGreater(len(result["source_chain"]), 0)
        self.assertGreater(len(result["errors"]), 0)

    def test_fundamental_bundle_full_data(self):
        """所有数据源成功时应返回 ok。"""
        adapter = AkshareFundamentalAdapter()
        fin_df = pd.DataFrame({
            "股票代码": ["600519"],
            "营业收入同比": [15.3],
            "净利润同比": [20.1],
            "净资产收益率": [28.5],
            "毛利率": [91.2],
        })
        forecast_df = pd.DataFrame({
            "股票代码": ["600519"],
            "预告": ["预计净利润增长20%-30%"],
        })
        inst_df = pd.DataFrame({
            "股票代码": ["600519"],
            "机构持仓比例": [5.2],
        })
        call_count = 0
        def _mock_call(candidates):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (fin_df, "stock_financial_abstract", [])
            if call_count == 2:
                return (forecast_df, "stock_yjyg_em", [])
            if call_count == 3:
                return (inst_df, "stock_rpdc_em", [])
            return (None, None, [])
        with patch.object(adapter, "_call_df_candidates", side_effect=_mock_call):
            result = adapter.get_fundamental_bundle("600519")
        self.assertEqual(result["status"], "partial")
        self.assertIn("growth", result["source_chain"][0])

    # --- #1034: get_capital_flow fail-open regression ---

    def test_capital_flow_all_sources_fail_returns_not_supported(self):
        """所有资金流数据源失败时应返回 not_supported 而非抛异常。"""
        adapter = AkshareFundamentalAdapter()
        with patch.object(adapter, "_call_df_candidates", return_value=(None, None, ["stock_individual_fund_flow:HTTPError"])):
            result = adapter.get_capital_flow("600519")
        self.assertEqual(result["status"], "not_supported")
        self.assertIn("stock_individual_fund_flow:HTTPError", result["errors"])
        self.assertEqual(result["stock_flow"], {})

    def test_capital_flow_partial_stock_only(self):
        """仅个股资金流成功时应返回 partial。"""
        adapter = AkshareFundamentalAdapter()
        stock_df = pd.DataFrame({
            "股票代码": ["600519"],
            "主力净流入": [5000000],
            "5日": [20000000],
            "10日": [40000000],
        })
        call_count = 0
        def _mock_call(candidates):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (stock_df, "stock_individual_fund_flow", [])
            return (None, None, [f"sector{call_count}:ConnectionError"])
        with patch.object(adapter, "_call_df_candidates", side_effect=_mock_call):
            result = adapter.get_capital_flow("600519")
        self.assertEqual(result["status"], "partial")
        self.assertIn("main_net_inflow", result["stock_flow"])
        self.assertGreater(len(result["source_chain"]), 0)

    def test_capital_flow_full_data(self):
        """个股和板块资金流均成功时应包含完整数据。"""
        adapter = AkshareFundamentalAdapter()
        stock_df = pd.DataFrame({
            "股票代码": ["600519"],
            "主力净流入": [5000000],
            "5日": [20000000],
            "10日": [40000000],
        })
        sector_df = pd.DataFrame({
            "板块": ["白酒", "新能源", "半导体"],
            "净流入": [100000000, -50000000, 30000000],
        })
        call_count = 0
        def _mock_call(candidates):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (stock_df, "stock_individual_fund_flow", [])
            return (sector_df, "stock_sector_fund_flow_rank", [])
        with patch.object(adapter, "_call_df_candidates", side_effect=_mock_call):
            result = adapter.get_capital_flow("600519")
        self.assertIn("main_net_inflow", result["stock_flow"])
        self.assertGreater(len(result["sector_rankings"]["top"]), 0)
        self.assertGreater(len(result["sector_rankings"]["bottom"]), 0)

    def test_capital_flow_empty_df_returns_not_supported(self):
        """空 DataFrame 返回 not_supported。"""
        adapter = AkshareFundamentalAdapter()
        empty_df = pd.DataFrame()
        with patch.object(adapter, "_call_df_candidates", return_value=(empty_df, None, [])):
            result = adapter.get_capital_flow("600519")
        self.assertEqual(result["status"], "not_supported")


if __name__ == "__main__":
    unittest.main()
