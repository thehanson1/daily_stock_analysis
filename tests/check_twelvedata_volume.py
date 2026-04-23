#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 Twelve Data 账户是否返回成交量数据

使用方法：
    python tests/check_twelvedata_volume.py

需要配置：
    .env 文件中设置 TWELVEDATA_API_KEY
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from data_provider.twelvedata_fetcher import TwelveDataFetcher


def check_volume_support():
    """检查 Twelve Data 账户的成交量支持情况"""
    
    print("=" * 60)
    print("Twelve Data 成交量支持检查")
    print("=" * 60)
    
    # 初始化 fetcher
    fetcher = TwelveDataFetcher()
    
    # 检查 API Key 配置
    api_key = os.getenv("TWELVEDATA_API_KEY", "").strip()
    if not api_key:
        print("❌ 未配置 TWELVEDATA_API_KEY")
        print("\n请在 .env 文件中添加：")
        print("TWELVEDATA_API_KEY=your_api_key_here")
        return
    
    print(f"✅ API Key 已配置: {api_key[:8]}...{api_key[-4:]}")
    
    # 检查是否可用
    if not fetcher.is_api_ready():
        print("❌ Twelve Data 未启用")
        print("\n请检查配置：")
        print("- TWELVEDATA_API_KEY 是否正确")
        print("- TWELVEDATA_US_HK_ENABLE 是否为 true（默认）")
        return
    
    print("✅ Twelve Data 已启用\n")
    
    # 测试股票列表
    test_stocks = [
        ("AAPL", "美股 - 苹果"),
        ("TSLA", "美股 - 特斯拉"),
        ("0700.HK", "港股 - 腾讯"),
        ("9988.HK", "港股 - 阿里巴巴"),
    ]
    
    print("测试股票实时行情（成交量数据）：")
    print("-" * 60)
    
    for stock_code, description in test_stocks:
        print(f"\n📊 {description} ({stock_code})")
        print("-" * 40)
        
        try:
            quote = fetcher.get_realtime_quote(stock_code)
            
            if quote is None:
                print("❌ 未获取到行情数据")
                continue
            
            # 检查基础字段
            print(f"✅ 价格: ${quote.price:.2f}" if quote.price else "❌ 价格: 无")
            print(f"✅ 涨跌幅: {quote.change_pct:.2f}%" if quote.change_pct else "❌ 涨跌幅: 无")
            
            # 检查成交量
            if quote.volume is not None and quote.volume > 0:
                print(f"✅ 成交量: {quote.volume:,}")
            else:
                print("❌ 成交量: 无数据")
            
            # 检查量比
            if quote.volume_ratio is not None:
                print(f"✅ 量比: {quote.volume_ratio:.2f}")
            else:
                print("⚠️  量比: 无数据（需要历史数据计算）")
            
            # 检查换手率
            if quote.turnover_rate is not None:
                print(f"✅ 换手率: {quote.turnover_rate:.2f}%")
            else:
                print("⚠️  换手率: 无数据（需要 statistics 接口权限）")
            
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    print("\n" + "=" * 60)
    print("检查完成")
    print("=" * 60)
    
    # 总结
    print("\n📋 说明：")
    print("1. ✅ 表示数据正常返回")
    print("2. ❌ 表示数据缺失或错误")
    print("3. ⚠️  表示需要额外权限或计算")
    print("\n💡 关于成交量：")
    print("- 免费账户：通常支持基础成交量")
    print("- 付费账户：支持完整成交量和统计数据")
    print("- 量比：需要历史数据计算（可能需要额外请求）")
    print("- 换手率：需要 statistics 接口（部分套餐支持）")
    
    print("\n🔗 升级账户：https://twelvedata.com/pricing")


if __name__ == "__main__":
    check_volume_support()
