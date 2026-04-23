# IBKR 数据源配置指南

## 📋 概述

Interactive Brokers (IBKR) 数据源为系统提供券商级别的实时行情数据，支持：

- ✅ **成交量**：实时成交量数据
- ✅ **量比**：自动计算（基于历史5日均量）
- ✅ **换手率**：自动计算（基于流通股本，如果可用）
- ✅ **全球市场**：美股、港股、A股（通过港股通）
- ✅ **完全免费**：无需额外订阅费用（需要 IBKR 账户）

## ⚠️ 适用场景

### ✅ 适用于
- **本地开发环境**：在自己的电脑上运行
- **自有服务器**：在 VPS/云服务器上运行
- **Docker 容器**：可以访问宿主机 TWS/Gateway

### ❌ 不适用于
- **GitHub Actions**：无法运行 TWS/Gateway
- **无状态云函数**：AWS Lambda、Azure Functions 等
- **共享主机**：无法安装和运行 TWS/Gateway

### 💡 替代方案
如果你在 GitHub Actions 或云函数上运行，请使用：
- **A股**：EfinanceFetcher / AkshareFetcher（完美支持量比和换手率）
- **美股/港股**：YfinanceFetcher（基础数据）或 TwelveDataFetcher（付费）

详见：[数据源对比指南](./DATA_SOURCE_COMPARISON.md)

---

## 🚀 快速开始

### 步骤 1: 安装依赖

```bash
pip install ib_insync
```

### 步骤 2: 启动 TWS 或 IB Gateway

#### 选项 A: TWS (Trader Workstation)
1. 下载并安装 TWS：https://www.interactivebrokers.com/en/trading/tws.php
2. 登录你的 IBKR 账户
3. 启用 API 连接：
   - 菜单：`File` → `Global Configuration` → `API` → `Settings`
   - 勾选 `Enable ActiveX and Socket Clients`
   - 设置 `Socket port`: `7497`（实盘）或 `7497`（模拟盘）
   - 勾选 `Read-Only API`（推荐，仅读取数据）
   - 点击 `OK` 并重启 TWS

#### 选项 B: IB Gateway（推荐，轻量级）
1. 下载并安装 IB Gateway：https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
2. 登录你的 IBKR 账户
3. 配置 API：
   - 点击右上角齿轮图标 → `Settings` → `API`
   - 勾选 `Enable ActiveX and Socket Clients`
   - 设置 `Socket port`: `4001`（实盘）或 `4002`（模拟盘）
   - 勾选 `Read-Only API`
   - 点击 `OK`

### 步骤 3: 配置环境变量

在 `.env` 文件中添加：

```bash
# IBKR 数据源配置
IBKR_HOST=127.0.0.1
IBKR_PORT=7497              # TWS=7497, Gateway=4001
IBKR_CLIENT_ID=1
IBKR_TIMEOUT=10
IBKR_PRIORITY=2

# 启用实时行情
ENABLE_REALTIME_QUOTE=true
```

### 步骤 4: 测试连接

```bash
python -c "
from data_provider.ibkr_fetcher import IBKRFetcher

fetcher = IBKRFetcher()
quote = fetcher.get_realtime_quote('AAPL')

if quote:
    print(f'✅ 连接成功！')
    print(f'股票: {quote.name}')
    print(f'价格: \${quote.price:.2f}')
    print(f'成交量: {quote.volume:,}')
    print(f'量比: {quote.volume_ratio}')
else:
    print('❌ 连接失败，请检查配置')
"
```

---

## 🔧 配置说明

### 环境变量

| 变量 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `IBKR_HOST` | TWS/Gateway 地址 | `127.0.0.1` | `127.0.0.1` |
| `IBKR_PORT` | 端口号 | `7497` | TWS=`7497`, Gateway=`4001` |
| `IBKR_CLIENT_ID` | 客户端ID | `1` | `1`（多个连接时递增） |
| `IBKR_TIMEOUT` | 连接超时（秒） | `10` | `10` |
| `IBKR_PRIORITY` | 数据源优先级 | `2` | `2` |

### 端口说明

| 应用 | 实盘端口 | 模拟盘端口 |
|------|----------|------------|
| TWS | 7497 | 7497 |
| IB Gateway | 4001 | 4002 |

---

## 📊 支持的市场

### 美股
```python
quote = fetcher.get_realtime_quote('AAPL')   # 苹果
quote = fetcher.get_realtime_quote('TSLA')   # 特斯拉
```

### 港股
```python
quote = fetcher.get_realtime_quote('0700.HK')  # 腾讯
quote = fetcher.get_realtime_quote('9988.HK')  # 阿里巴巴
```

### A股（通过港股通）
```python
quote = fetcher.get_realtime_quote('600519')  # 贵州茅台
quote = fetcher.get_realtime_quote('000001')  # 平安银行
```

**注意**：A股需要通过港股通访问，可能需要额外的市场数据订阅。

---

## 🎯 数据字段

### 基础字段（直接从 IBKR 获取）
- ✅ `price`: 最新价格
- ✅ `volume`: 成交量
- ✅ `open_price`: 开盘价
- ✅ `high`: 最高价
- ✅ `low`: 最低价
- ✅ `pre_close`: 昨收价
- ✅ `change_pct`: 涨跌幅
- ✅ `change_amount`: 涨跌额
- ✅ `amplitude`: 振幅

### 计算字段
- ✅ `volume_ratio`: 量比（当前成交量 / 过去5日平均成交量）
- ⚠️ `turnover_rate`: 换手率（需要流通股本数据，可能不可用）

---

## ⚠️ 注意事项

### 1. 市场数据订阅
- IBKR 需要订阅相应市场的实时数据
- 美股：需要订阅 US Securities Snapshot and Futures Value Bundle
- 港股：需要订阅 SEHK Real-Time
- 查看订阅：https://www.interactivebrokers.com/en/trading/market-data.php

### 2. 连接限制
- 同一个 `CLIENT_ID` 只能有一个连接
- 如果需要多个连接，使用不同的 `CLIENT_ID`
- TWS/Gateway 需要保持运行状态

### 3. API 权限
- 建议启用 `Read-Only API`，仅读取数据
- 不要在生产环境中使用交易权限

### 4. 性能优化
- IBKR API 有请求频率限制
- 系统会自动缓存合约信息
- 量比计算需要额外的历史数据请求

---

## 🐛 故障排查

### 问题 1: 连接失败
```
[IBKRFetcher] 连接失败: Connection refused
```

**解决方案**：
1. 确认 TWS/Gateway 正在运行
2. 检查端口号是否正确（TWS=7497, Gateway=4001）
3. 确认 API 设置中已启用 Socket Clients

### 问题 2: 未获取到数据
```
[IBKRFetcher] AAPL 未获取到有效价格
```

**解决方案**：
1. 确认已订阅相应市场的实时数据
2. 检查股票代码是否正确
3. 确认市场是否开盘

### 问题 3: 量比为 None
```
volume_ratio=None
```

**解决方案**：
- 量比需要历史数据计算
- 新上市股票可能没有足够的历史数据
- 检查 IBKR 历史数据权限

### 问题 4: ib_insync 未安装
```
[IBKRFetcher] ib_insync 未安装
```

**解决方案**：
```bash
pip install ib_insync
```

---

## 📚 相关资源

- **IBKR API 文档**：https://interactivebrokers.github.io/tws-api/
- **ib_insync 文档**：https://ib-insync.readthedocs.io/
- **市场数据订阅**：https://www.interactivebrokers.com/en/trading/market-data.php
- **TWS 下载**：https://www.interactivebrokers.com/en/trading/tws.php
- **IB Gateway 下载**：https://www.interactivebrokers.com/en/trading/ibgateway-stable.php

---

## 💡 最佳实践

### 1. 使用 IB Gateway 而非 TWS
- IB Gateway 更轻量级
- 占用资源更少
- 更适合自动化运行

### 2. 启用 Read-Only API
- 防止误操作
- 提高安全性

### 3. 合理设置优先级
```bash
# A股优先使用免费数据源
REALTIME_SOURCE_PRIORITY=efinance,akshare_em

# 美股/港股使用 IBKR
IBKR_PRIORITY=2
```

### 4. 监控连接状态
- 系统会自动重连
- 检查日志中的连接状态

---

## 🎉 完成

现在你可以使用 IBKR 数据源获取高质量的实时行情数据了！

如有问题，请查看日志或提交 Issue。
