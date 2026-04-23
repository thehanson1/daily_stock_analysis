#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IBKR 连接测试脚本

使用方法：
    python tests/test_ibkr_connection.py

前提条件：
    1. 已安装 ib_insync: pip install ib_insync
    2. TWS 或 IB Gateway 正在运行
    3. 已配置 .env 文件中的 IBKR_* 变量
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def test_ibkr_connection():
    """测试 IBKR 连接和数据获取"""
    
    print("=" * 70)
    print("IBKR 数据源连接测试")
    print("=" * 70)
    
    # 检查配置
    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = os.getenv("IBKR_PORT", "7497")
    client_id = os.getenv("IBKR_CLIENT_ID", "1")
    
    print(f"\n📋 配置信息：")
    print(f"  - Host: {host}")
    print(f"  - Port: {port}")
    print(f"  - Client ID: {client_id}")
    
    # 检查依赖
    print(f"\n📦 检查依赖...")
    try:
        import ib_insync
        print(f"  ✅ ib_insync 已安装 (版本: {ib_insync.__version__})")
    except ImportError:
        print(f"  ❌ ib_insync 未安装")
        print(f"\n安装方法：")
        print(f"  pip install ib_insync")
        return
    
    # 初始化 fetcher
    print(f"\n🔌 初始化 IBKR 数据源...")
    try:
        from data_provider.ibkr_fetcher import IBKRFetcher
        fetcher = IBKRFetcher()
        print(f"  ✅ 初始化成功")
    except Exception as e:
        print(f"  ❌ 初始化失败: {e}")
        return
    
    # 测试股票列表
    test_stocks = [
        ("AAPL", "美股 - 苹果"),
        ("TSLA", "美股 - 特斯拉"),
        ("0700.HK", "港股 - 腾讯"),
    ]
    
    print(f"\n📊 测试实时行情...")
    print("-" * 70)
    
    for stock_code, description in test_stocks:
        print(f"\n{description} ({stock_code})")
        print("-" * 40)
        
        try:
            quote = fetcher.get_realtime_quote(stock_code)
            
            if quote is None:
                print("❌ 未获取到行情数据")
                print("   可能原因：")
                print("   1. TWS/Gateway 未运行")
                print("   2. 未订阅该市场的实时数据")
                print("   3. 股票代码错误")
                continue
            
            # 显示数据
            print(f"✅ 股票名称: {quote.name}")
            print(f"✅ 当前价格: ${quote.price:.2f}" if quote.price else "❌ 价格: 无")
            print(f"✅ 涨跌幅: {quote.change_pct:.2f}%" if quote.change_pct else "⚠️  涨跌幅: 无")
            
            if quote.volume is not None and quote.volume > 0:
                print(f"✅ 成交量: {quote.volume:,} 股")
            else:
                print("⚠️  成交量: 无数据")
            
            if quote.volume_ratio is not None:
                print(f"✅ 量比: {quote.volume_ratio:.2f}")
            else:
                print("⚠️  量比: 无数据（需要历史数据计算）")
            
            if quote.turnover_rate is not None:
                print(f"✅ 换手率: {quote.turnover_rate:.2f}%")
            else:
                print("⚠️  换手率: 无数据（需要流通股本数据）")
            
            print(f"✅ 数据源: {quote.source.value}")
            
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)
    
    print("\n💡 提示：")
    print("  - 如果连接失败，请确认 TWS/Gateway 正在运行")
    print("  - 如果未获取到数据，请检查市场数据订阅")
    print("  - 量比需要历史数据，首次获取可能较慢")
    print("  - 换手率需要流通股本数据，可能不可用")
    
    print("\n📚 相关文档：")
    print("  - IBKR 配置指南: docs/IBKR_SETUP.md")
    print("  - 市场数据订阅: https://www.interactivebrokers.com/en/trading/market-data.php")


if __name__ == "__main__":
    test_ibkr_connection()
