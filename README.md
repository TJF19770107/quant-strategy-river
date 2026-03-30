# 大道量化策略系统

> 大道至简,顺势而为

## 项目简介

大道量化策略系统是一个基于 BTC 1小时K线的量化交易策略系统,遵循大道心法:

```
无动无静,无生无灭,无去无来,无是非,无住无往。
直观,屏息注念,一念不生,湛于末时。
了了分明,一尘不染。
```

## 核心原则

- **应无所住而生其心**
- 不预测,只识别;不预判,只跟随
- 心不住于涨跌,不住于多空,不住于盈亏,不住于境相
- 以K线为相,以量价为证,以结构为凭,以历史为镜

## 项目结构

```
quant-strategy-river/
├── strategies/           # 策略核心代码
│   ├── river/           # RIVER 策略模块
│   └── siven/           # SIVEN 策略模块
├── data/                # 数据文件 (已忽略,不提交)
│   ├── fetch_btc_1h.py  # K线拉取脚本
│   └── sample/          # 示例数据
├── docs/                # 知识库文档
│   └── 策略说明/
├── config/              # 配置文件
│   └── 数据库配置/
├── scripts/             # 工具脚本
│   └── backup_data_to_cloud.py
├── reports/             # 分析报告
├── visualizations/      # 可视化文件
└── backups/             # 数据备份 (已忽略,不提交)
```

## 版本历史

- **v3.0** - 大道量化策略系统,合并 RIVER、SIVEN 策略
- **v2.x** - 策略优化与回测
- **v1.x** - 基础策略框架

## 策略模块

### RIVER 策略 (`strategies/river/`)

RIVER 高低点突破 + ML 历史规律 + 高盈亏比交易策略

| 文件 | 说明 |
|------|------|
| `main.py` | 策略主入口 |
| `daodao_core_v1.py` | 核心策略 v1.0 |
| `daodao_core_v2_optimized.py` | 优化版 v2.0 |
| `daodao_core_v2_1_balanced.py` | 平衡版 v2.1 |
| `daodao_core_v3_ultra_optimized.py` | 极致优化版 v3.0 |
| `version_manager.py` | 策略版本管理器 |
| `multi_symbol_adapter.py` | 多品种适配器 |
| `river_ml_strategy.py` | ML策略模块 |

### SIVEN 策略 (`strategies/siven/`)

SIRENUSDT 多空闭环策略 - 相似K线匹配 + 缠论分型

| 文件 | 说明 |
|------|------|
| `siren_strategy.py` | SIREN 多空闭环策略 |

## 快速开始

### 1. 拉取K线数据

```bash
# 使用代理拉取BTC 1小时K线
python data/fetch_btc_1h.py --proxy http://127.0.0.1:7897

# 增量更新
python data/fetch_btc_1h.py
```

### 2. 运行策略回测

```bash
# 进入 RIVER 策略目录
cd strategies/river

# 运行 BTC 回测
python main.py run --symbol BTCUSDT --data ../../data/BTCUSDT_1h.csv

# 自动优化参数
python main.py run --symbol BTCUSDT --data ../../data/BTCUSDT_1h.csv --optimize

# 列出所有策略
python main.py list
```

### 3. 数据备份

```bash
# 创建备份并提示手动上传到云盘
python scripts/backup_data_to_cloud.py
```

### 4. 数据安全

- 原始数据文件不会提交到 Git (已配置 .gitignore)
- 建议定期备份到云盘 (百度网盘/阿里云盘)

## 文档

- [大道量化系统说明](docs/大道量化系统说明.md)
- [配置文件说明](config/配置说明.md)

## 作者

TJF19770107

## 许可证

MIT License
