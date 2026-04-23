#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速检查 Twelve Data 账户信息和权限

使用方法：
    python scripts/check_twelvedata_account.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import requests


def check_account():
    """检查 Twelve Data 账户信息"""
    
    api_key = os.getenv("TWELVEDATA_API_KEY", "").strip()
    
    if not api_key:
        print("❌ 未配置 TWELVEDATA_API_KEY")
        print("\n请在 .env 文件中添加：")
        print("TWELVEDATA_API_KEY=your_api_key_here")
        print("\n获取 API Key: https://twelvedata.com/account/api-keys")
        return
    
    print("=" * 70)
    print("Twelve Data 账户信息检查")
    print("=" * 70)
    print(f"\n🔑 API Key: {api_key[:8]}...{api_key[-4:]}\n")
    
    # 1. 检查 API 配额
    print("📊 检查 API 配额...")
    print("-" * 70)
    
    try:
        response = requests.get(
            "https://api.twelvedata.com/quota",
            params={"apikey": api_key},
            timeout=10
        )
        response.raise_for_status()
        quota = response.json()
        
        if quota.get("status") == "error":
            print(f"❌ 错误: {quota.get('message')}")
            return
        
        print(f"✅ 套餐类型: {quota.get('plan', {}).get('name', 'Unknown')}")
        print(f"✅ 每日配额: {quota.get('plan', {}).get('daily_quota', 'N/A')}")
        print(f"✅ 每分钟配额: {quota.get('plan', {}).get('minute_quota', 'N/A')}")
        print(f"✅ 今日已用: {quota.get('current_usage', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 配额检查失败: {e}")
    
    # 2. 测试实时行情（检查成交量）
    print("\n\n📈 测试实时行情（AAPL - 苹果）...")
    print("-" * 70)
    
    try:
        response = requests.get(
            "https://api.twelvedata.com/quote",
            params={
                "symbol": "AAPL",
                "apikey": api_key,
                "dp": 4
            },
            timeout=10
        )
        response.raise_for_status()
        quote = response.json()
        
        if quote.get("status") == "error":
            print(f"❌ 错误: {quote.get('message')}")
        else:
            print(f"✅ 股票名称: {quote.get('name', 'N/A')}")
            print(f"✅ 当前价格: ${quote.get('close', 'N/A')}")
            print(f"✅ 涨跌幅: {quote.get('percent_change', 'N/A')}%")
            
            # 关键：检查成交量
            volume = quote.get('volume')
            if volume is not None and volume != "":
                print(f"✅ 成交量: {volume:,} 股")
                print("\n🎉 你的账户支持成交量数据！")
            else:
                print("❌ 成交量: 无数据")
                print("\n⚠️  你的账户可能不支持成交量数据")
                print("   需要升级到支持实时数据的套餐")
            
            # 检查其他字段
            print(f"\n其他字段:")
            print(f"  - 开盘价: {quote.get('open', 'N/A')}")
            print(f"  - 最高价: {quote.get('high', 'N/A')}")
            print(f"  - 最低价: {quote.get('low', 'N/A')}")
            print(f"  - 昨收价: {quote.get('previous_close', 'N/A')}")
            
    except Exception as e:
        print(f"❌ 实时行情测试失败: {e}")
    
    # 3. 测试历史数据（检查成交量）
    print("\n\n📅 测试历史数据（AAPL - 最近5天）...")
    print("-" * 70)
    
    try:
        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": "AAPL",
                "interval": "1day",
                "outputsize": 5,
                "apikey": api_key
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "error":
            print(f"❌ 错误: {data.get('message')}")
        else:
            values = data.get('values', [])
            if values:
                print(f"✅ 获取到 {len(values)} 条历史数据")
                
                # 检查第一条数据的成交量
                first = values[0]
                volume = first.get('volume')
                if volume is not None and volume != "":
                    print(f"✅ 历史成交量: {volume} 股")
                    print("\n🎉 你的账户支持历史成交量数据！")
                else:
                    print("❌ 历史成交量: 无数据")
                
                # 显示最新一条数据
                print(f"\n最新数据 ({first.get('datetime', 'N/A')}):")
                print(f"  - 收盘价: {first.get('close', 'N/A')}")
                print(f"  - 成交量: {first.get('volume', 'N/A')}")
            else:
                print("❌ 未获取到历史数据")
                
    except Exception as e:
        print(f"❌ 历史数据测试失败: {e}")
    
    # 4. 测试 statistics 接口（换手率需要）
    print("\n\n📊 测试 statistics 接口（换手率计算需要）...")
    print("-" * 70)
    
    try:
        response = requests.get(
            "https://api.twelvedata.com/statistics",
            params={
                "symbol": "AAPL",
                "apikey": api_key
            },
            timeout=10
        )
        response.raise_for_status()
        stats = response.json()
        
        if stats.get("status") == "error":
            code = stats.get("code")
            message = stats.get("message", "")
            
            if code == 403 or "not available" in message.lower():
                print("⚠️  statistics 接口不可用")
                print("   你的套餐不支持此接口，无法自动计算换手率")
                print("   需要升级到 Pro 或更高套餐")
            else:
                print(f"❌ 错误: {message}")
        else:
            stock_stats = stats.get('stock_statistics', {})
            float_shares = stock_stats.get('float_shares')
            shares_outstanding = stock_stats.get('shares_outstanding')
            
            if float_shares or shares_outstanding:
                print(f"✅ 流通股本: {float_shares or 'N/A'}")
                print(f"✅ 总股本: {shares_outstanding or 'N/A'}")
                print("\n🎉 你的账户支持 statistics 接口，可以计算换手率！")
            else:
                print("⚠️  statistics 接口返回数据不完整")
                
    except Exception as e:
        print(f"⚠️  statistics 接口测试失败: {e}")
        print("   可能你的套餐不支持此接口")
    
    # 总结
    print("\n\n" + "=" * 70)
    print("检查总结")
    print("=" * 70)
    print("\n📋 数据支持情况：")
    print("  ✅ = 支持")
    print("  ❌ = 不支持")
    print("  ⚠️  = 部分支持或需要升级")
    
    print("\n💡 关于量比和换手率：")
    print("  - 量比：需要历史成交量数据（通过 time_series 接口计算）")
    print("  - 换手率：需要 statistics 接口（Pro 套餐及以上）")
    
    print("\n🔗 相关链接：")
    print("  - 套餐对比: https://twelvedata.com/pricing")
    print("  - API 文档: https://twelvedata.com/docs")
    print("  - 账户管理: https://twelvedata.com/account")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    check_account()
