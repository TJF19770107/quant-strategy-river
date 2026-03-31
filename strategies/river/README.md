# RIVER 策略模块

大道量化系统 - RIVER 高低点突破 + ML 历史规律 + 高盈亏比交易策略

## 策略核心

1. **RIVER高低点突破**: 20周期窗口,捕捉趋势转折点
2. **ML历史规律模型**: 基于24根K线特征预测上涨概率
3. **高盈亏比交易**: 固定止损2%,止盈8% (1:4盈亏比)
4. **三重过滤**: ML概率 > 55% + RIVER突破 + 放量确认 (1.2倍)

## BTCUSDT 回测结果 (v1.0)

| 指标 | 数值 |
|------|------|
| 总收益率 | 1,394.92% (14倍) |
| 最大回撤 | 66.44% |
| 胜率 | 25.39% |
| 交易次数 | 449次 |
| 盈亏比 | 3.51 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 策略主入口 (命令行) |
| `daodao_core_v1.py` | 核心策略 v1.0 - 基础版本 |
| `daodao_core_v2_optimized.py` | 优化版 v2.0 - 五重过滤 |
| `daodao_core_v2_1_balanced.py` | 平衡版 v2.1 - 收益与回撤平衡 |
| `daodao_core_v3_ultra_optimized.py` | 极致优化版 v3.0 - 七重过滤 |
| `version_manager.py` | 策略版本管理器 |
| `multi_symbol_adapter.py` | 多品种适配器 |
| `river_ml_strategy.py` | ML策略模块 |

## 使用方法

```bash
# 运行 BTC 回测 (使用默认配置)
python main.py run --symbol BTCUSDT --data ../../data/BTCUSDT_1h.csv

# 自动优化参数
python main.py run --symbol BTCUSDT --data ../../data/BTCUSDT_1h.csv --optimize

# 测试新品种
python main.py new --symbol ETHUSDT --data ../../data/ETHUSDT_1h.csv

# 列出所有策略
python main.py list

# 对比策略
python main.py compare Daodao_RiverML_v1.0 Daodao_RiverML_v1.1
```

## 版本说明

- **v1.0** - 基础策略,14倍收益
- **v2.0** - 五重过滤,优化回撤控制
- **v2.1** - 平衡版,收益与风险平衡
- **v3.0** - 七重过滤,极致优化

## 核心心法

```
应无所住而生其心
不预测,只识别;不预判,只跟随
心不住于涨跌,不住于多空,不住于盈亏,不住于境相
以K线为相,以量价为证,以结构为凭,以历史为镜
```
