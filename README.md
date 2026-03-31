# 大道量化策略系统

## 快速开始

### 方式一：命令行分析
```bash
python dao_strategy.py BTCUSDT
python dao_strategy.py ETHUSDT
python dao_strategy.py SOLUSDT
```

### 方式二：导入模块
```python
from dao_strategy import main
main("BTCUSDT")
```

## 输出文件

- `data/[标的]_1h.csv` - K线数据
- `reports/[标的]_1h_chan.html` - 交互式K线图
- `reports/[标的]_backtest_report.md` - 回测报告

## 分析功能

1. **均线系统**: MA5/MA10/MA30/MA60/MA120
2. **MACD指标**: 金叉/死叉/底背离/顶背离
3. **缠论分析**: 笔识别、分型标记
4. **回测系统**: 策略胜率、盈亏比统计
5. **预判输出**: 方向、压力位、支撑位、操作建议
