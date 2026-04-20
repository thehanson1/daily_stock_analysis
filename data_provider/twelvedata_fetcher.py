# -*- coding: utf-8 -*-
"""
===================================
TwelveDataFetcher - Twelve Data API 数据源 (Priority 2)
===================================

数据来源：Twelve Data API (https://twelvedata.com)
特点：无需开户，API Key 即可访问美股/港股历史日线与最新价格
定位：美股/港股 API 优先链候选数据源
"""

import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import BaseFetcher, DataFetchError, STANDARD_COLUMNS, normalize_stock_code
from .realtime_types import RealtimeSource, UnifiedRealtimeQuote, safe_float
from .us_index_mapping import is_us_stock_code

logger = logging.getLogger(__name__)


class TwelveDataFetcher(BaseFetcher):
    """Twelve Data 美股/港股 API 数据源。"""

    name = "TwelveDataFetcher"
    priority = int(os.getenv("TWELVEDATA_PRIORITY", "2"))

    BASE_URL = "https://api.twelvedata.com"
    DEFAULT_TIMEOUT = 10
    _FALSEY_VALUES = {"0", "false", "no", "off"}

    def __init__(self):
        self._api_key: str = ""
        self._available: Optional[bool] = None
        self._timeout_seconds = self.DEFAULT_TIMEOUT
        self._us_hk_enable = True
        self._symbol_cache: Dict[str, str] = {}
        self._stock_name_cache: Dict[str, str] = {}

    def _load_runtime_config(self) -> None:
        api_key = (os.getenv("TWELVEDATA_API_KEY") or "").strip()
        timeout_seconds = int(os.getenv("TWELVEDATA_TIMEOUT_SECONDS", str(self.DEFAULT_TIMEOUT)) or self.DEFAULT_TIMEOUT)
        enabled = (os.getenv("TWELVEDATA_US_HK_ENABLE", "true") or "true").strip().lower() not in self._FALSEY_VALUES

        try:
            from src.config import get_config

            config = get_config()
            api_key = (getattr(config, "twelvedata_api_key", None) or api_key or "").strip()
            timeout_seconds = int(
                getattr(config, "twelvedata_timeout_seconds", timeout_seconds) or timeout_seconds
            )
            enabled = bool(getattr(config, "twelvedata_us_hk_enable", enabled))
        except Exception:
            logger.debug("[TwelveDataFetcher] 使用环境变量作为运行时配置")

        self._api_key = api_key
        self._timeout_seconds = max(1, int(timeout_seconds))
        self._us_hk_enable = enabled

    def _is_available(self) -> bool:
        if self._available is not None:
            return self._available

        self._load_runtime_config()
        self._available = bool(self._api_key and self._us_hk_enable)
        return self._available

    def is_api_ready(self) -> bool:
        """供 DataFetcherManager 判断是否应纳入 US/HK API 优先链。"""
        return self._is_available()

    @staticmethod
    def _is_hk_code(stock_code: str) -> bool:
        normalized = (stock_code or "").strip().upper()
        if normalized.endswith(".HK"):
            base = normalized[:-3]
            return base.isdigit() and 1 <= len(base) <= 5
        if normalized.startswith("HK"):
            digits = normalized[2:]
            return digits.isdigit() and 1 <= len(digits) <= 5
        return normalized.isdigit() and 1 <= len(normalized) <= 5

    @classmethod
    def _is_supported_market(cls, stock_code: str) -> bool:
        normalized = normalize_stock_code(stock_code).strip().upper()
        return is_us_stock_code(normalized) or cls._is_hk_code(normalized)

    @staticmethod
    def _extract_hk_digits(stock_code: str) -> str:
        normalized = normalize_stock_code(stock_code).strip().upper()
        if normalized.endswith(".HK"):
            digits = normalized[:-3]
        elif normalized.startswith("HK"):
            digits = normalized[2:]
        else:
            digits = normalized
        return (digits or "").zfill(5)

    def _candidate_search_terms(self, stock_code: str) -> List[str]:
        normalized = normalize_stock_code(stock_code).strip().upper()
        if is_us_stock_code(normalized):
            return [normalized]

        hk_digits = self._extract_hk_digits(normalized)
        return [
            hk_digits,
            hk_digits.lstrip("0") or "0",
            f"HK{hk_digits}",
            f"{hk_digits}.HK",
        ]

    @staticmethod
    def _country_matches(entry: Dict[str, Any], expected_country: str) -> bool:
        country = str(entry.get("country") or "").strip().lower()
        expected = expected_country.strip().lower()
        if not country:
            return False
        aliases = {
            "united states": {"united states", "us", "usa"},
            "hong kong": {"hong kong", "hk"},
        }
        expected_aliases = aliases.get(expected, {expected})
        return country in expected_aliases or any(alias in country for alias in expected_aliases)

    def _select_symbol_entry(
        self,
        entries: List[Dict[str, Any]],
        stock_code: str,
    ) -> Optional[Dict[str, Any]]:
        normalized = normalize_stock_code(stock_code).strip().upper()
        if not entries:
            return None

        if is_us_stock_code(normalized):
            for entry in entries:
                symbol = str(entry.get("symbol") or "").strip().upper()
                if symbol == normalized and self._country_matches(entry, "united states"):
                    return entry
            for entry in entries:
                symbol = str(entry.get("symbol") or "").strip().upper()
                if symbol == normalized:
                    return entry
            return None

        if self._is_hk_code(normalized):
            target_digits = (self._extract_hk_digits(normalized).lstrip("0") or "0")
            for entry in entries:
                symbol = str(entry.get("symbol") or "").strip().upper()
                if not symbol.endswith(".HK"):
                    continue
                symbol_digits = (symbol.split(".", 1)[0].lstrip("0") or "0")
                if symbol_digits == target_digits:
                    return entry
            for entry in entries:
                symbol = str(entry.get("symbol") or "").strip().upper()
                if symbol.endswith(".HK"):
                    return entry
        return None

    def _find_symbol_entry(self, stock_code: str) -> Optional[Dict[str, Any]]:
        if not self._is_available():
            return None

        for search_term in self._candidate_search_terms(stock_code):
            try:
                payload = self._request(
                    "symbol_search",
                    {
                        "symbol": search_term,
                        "outputsize": 20,
                        "show_plan": "false",
                    },
                )
            except Exception as exc:
                logger.debug(
                    "[TwelveDataFetcher] symbol_search 失败: code=%s search_term=%s reason=%s",
                    stock_code,
                    search_term,
                    exc,
                )
                continue
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, list) or not data:
                continue
            entry = self._select_symbol_entry(data, stock_code)
            if entry is not None:
                return entry
        return None

    def _resolve_symbol(self, stock_code: str) -> str:
        normalized = normalize_stock_code(stock_code).strip().upper()
        cached_symbol = self._symbol_cache.get(normalized)
        if cached_symbol:
            return cached_symbol

        if is_us_stock_code(normalized):
            self._symbol_cache[normalized] = normalized
            return normalized

        entry = self._find_symbol_entry(normalized)
        if entry is not None:
            resolved_symbol = str(entry.get("symbol") or "").strip().upper()
            if resolved_symbol:
                self._symbol_cache[normalized] = resolved_symbol
                instrument_name = str(entry.get("instrument_name") or "").strip()
                if instrument_name:
                    self._stock_name_cache[normalized] = instrument_name
                return resolved_symbol

        fallback_symbol = f"{self._extract_hk_digits(normalized)}.HK"
        self._symbol_cache[normalized] = fallback_symbol
        return fallback_symbol

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((requests.RequestException, DataFetchError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._is_available():
            raise DataFetchError("[TwelveDataFetcher] 未配置 TWELVEDATA_API_KEY 或已禁用")

        request_params = {**params, "apikey": self._api_key}
        try:
            response = requests.get(
                f"{self.BASE_URL}/{endpoint}",
                params=request_params,
                timeout=self._timeout_seconds,
                headers={"Authorization": f"apikey {self._api_key}"},
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise DataFetchError(f"[TwelveDataFetcher] 请求超时: {exc}") from exc
        except requests.RequestException as exc:
            raise DataFetchError(f"[TwelveDataFetcher] 网络请求失败: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise DataFetchError("[TwelveDataFetcher] 返回非 JSON 响应") from exc

        if isinstance(payload, dict) and payload.get("status") == "error":
            code = payload.get("code")
            message = payload.get("message") or "unknown error"
            raise DataFetchError(f"[TwelveDataFetcher] API 错误 code={code}: {message}")

        return payload

    def get_stock_name(self, stock_code: str) -> str:
        normalized = normalize_stock_code(stock_code).strip().upper()
        cached_name = self._stock_name_cache.get(normalized, "")
        if cached_name:
            return cached_name

        try:
            entry = self._find_symbol_entry(normalized)
        except Exception as exc:
            logger.debug("[TwelveDataFetcher] symbol_search 获取名称失败: code=%s reason=%s", normalized, exc)
            return ""

        if entry is None:
            return ""

        instrument_name = str(entry.get("instrument_name") or "").strip()
        resolved_symbol = str(entry.get("symbol") or "").strip().upper()
        if resolved_symbol:
            self._symbol_cache[normalized] = resolved_symbol
        if instrument_name:
            self._stock_name_cache[normalized] = instrument_name
        return instrument_name

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if not self._is_supported_market(stock_code):
            raise DataFetchError(f"[TwelveDataFetcher] 不支持的市场代码: {stock_code}")

        symbol = self._resolve_symbol(stock_code)
        logger.info("[TwelveDataFetcher] 请求历史日线: symbol=%s code=%s", symbol, stock_code)

        payload = self._request(
            "time_series",
            {
                "symbol": symbol,
                "interval": "1day",
                "start_date": start_date,
                "end_date": end_date,
                "outputsize": 5000,
                "order": "asc",
                "format": "JSON",
            },
        )

        values = payload.get("values") if isinstance(payload, dict) else None
        if not values:
            raise DataFetchError(f"[TwelveDataFetcher] 历史日线为空: symbol={symbol}")

        df = pd.DataFrame(values)
        if df.empty:
            raise DataFetchError(f"[TwelveDataFetcher] 历史日线 DataFrame 为空: symbol={symbol}")
        return df

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        normalized = df.copy()
        normalized = normalized.rename(columns={"datetime": "date"})
        if "date" not in normalized.columns:
            raise DataFetchError("[TwelveDataFetcher] 缺少 date/datetime 字段")

        missing_columns = [column for column in ("open", "high", "low", "close", "volume") if column not in normalized.columns]
        if missing_columns:
            raise DataFetchError(f"[TwelveDataFetcher] 历史日线缺少关键字段: {', '.join(missing_columns)}")

        for column in ("open", "high", "low", "close", "volume"):
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

        normalized = normalized.sort_values("date", ascending=True).reset_index(drop=True)
        normalized["amount"] = None
        normalized["pct_chg"] = normalized["close"].pct_change() * 100
        normalized["pct_chg"] = normalized["pct_chg"].fillna(0).round(2)

        for column in STANDARD_COLUMNS:
            if column not in normalized.columns:
                normalized[column] = None
        return normalized[STANDARD_COLUMNS]

    def get_realtime_quote(self, stock_code: str) -> Optional[UnifiedRealtimeQuote]:
        if not self._is_available() or not self._is_supported_market(stock_code):
            return None

        normalized = normalize_stock_code(stock_code).strip().upper()
        symbol = self._resolve_symbol(normalized)
        logger.info("[TwelveDataFetcher] 请求实时价格: symbol=%s code=%s", symbol, normalized)

        try:
            payload = self._request("price", {"symbol": symbol, "dp": 4})
        except Exception as exc:
            logger.warning(
                "[TwelveDataFetcher] 实时价格失败，将交由后续 fetcher fallback: symbol=%s reason=%s",
                symbol,
                exc,
            )
            return None

        price = safe_float(payload.get("price")) if isinstance(payload, dict) else None
        if price is None or price <= 0:
            logger.warning(
                "[TwelveDataFetcher] 实时价格缺失，将交由后续 fetcher fallback: symbol=%s",
                symbol,
            )
            return None

        return UnifiedRealtimeQuote(
            code=normalized,
            name=self._stock_name_cache.get(normalized, ""),
            source=RealtimeSource.TWELVEDATA,
            price=price,
        )
