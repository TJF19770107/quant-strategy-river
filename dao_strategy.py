#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

"""
大道量化策略系统 - 万能模板 V3.0
===============================
核心功能：
1. 专属品种数据库支持（自动识别）
2. 数据自动更新补齐（3次重试+断点续传）
3. 大道量化策略 + 缠论分析
4. 完整开仓规则（盈亏比≥1:4）
5. GitHub自动上传

使用方式: python dao_strategy.py [标的名称]
唤醒口令: "分析 [标的]" 或 "大道量化"
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ================== 配置区域 ==================
# 品种数据库路径
SYMBOLS_DB_PATH = Path(__file__).parent / "symbols_db.json"

# 加载品种数据库
def load_symbols_db():
    """从数据库加载品种配置"""
    if SYMBOLS_DB_PATH.exists():
        with open(SYMBOLS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"symbols": [], "settings": {}}

SYMBOLS_DB = load_symbols_db()

CONFIG = {
    "data_dir": "data",
    "report_dir": "reports",
    "github_repo": "大道量化策略系统",
    "github_token": os.environ.get("GITHUB_TOKEN", ""),  # GitHub Token
    "kline_count": 1000,
    "proxy": {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"},
    "min_reward_risk_ratio": 4.0,
    "data_retry": 3,
}

def get_symbol_config(symbol: str):
    """获取品种配置"""
    symbol = symbol.upper()
    for s in SYMBOLS_DB.get("symbols", []):
        if s["symbol"].upper() == symbol and s.get("enabled", True):
            return s
    # 未在数据库中，返回默认配置
    return {
        "symbol": symbol,
        "type": "perpetual",
        "exchange": "Binance",
        "api": "fapi",
        "enabled": True,
        "notes": "自动识别"
    }

def add_symbol_to_db(symbol: str, notes: str = "") -> bool:
    """添加新品种到数据库"""
    symbol = symbol.upper()
    db = load_symbols_db()
    
    # 检查是否已存在
    for s in db.get("symbols", []):
        if s["symbol"].upper() == symbol:
            print(f"[DAODAO] 品种 {symbol} 已存在数据库中")
            return False
    
    # 添加新品种
    new_symbol = {
        "symbol": symbol,
        "name": symbol.replace("USDT", ""),
        "type": "perpetual",
        "exchange": "Binance",
        "api": "fapi",
        "enabled": True,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "notes": notes or f"自动添加于 {datetime.now().strftime('%Y-%m-%d')}"
    }
    
    db.setdefault("symbols", []).append(new_symbol)
    
    with open(SYMBOLS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    print(f"[DAODAO] ✅ 品种 {symbol} 已添加到数据库")
    return True

# ================== 1. 数据更新补齐模块 ==================
class DataUpdater:
    """数据更新器 - 自动检测并补齐最新K线（支持3次重试+断点续传）"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.symbol_config = get_symbol_config(self.symbol)
        self.data_path = Path(CONFIG["data_dir"]) / f"{self.symbol}_1h.csv"
        # 根据品种配置选择API
        if self.symbol_config.get("api") == "fapi":
            self.api_url_futures = "https://fapi.binance.com/fapi/v1/klines"
            self.api_url_spot = "https://api.binance.com/api/v3/klines"
            self.api_url = self.api_url_futures
        else:
            self.api_url = "https://api.binance.com/api/v3/klines"
            self.api_url_futures = None
            self.api_url_spot = self.api_url
    
    def load_local_data(self):
        """读取本地数据"""
        import pandas as pd
        
        if not self.data_path.exists():
            return None
        
        df = pd.read_csv(self.data_path)
        df["datetime"] = pd.to_datetime(df["datetime"])
        return df
    
    def get_latest_from_api(self, start_time: int = None, use_fallback: bool = False):
        """从API获取最新数据"""
        import requests
        import pandas as pd
        
        params = {
            "symbol": self.symbol,
            "interval": "1h",
            "limit": 100
        }
        
        if start_time:
            params["startTime"] = start_time
        
        # 尝试合约API
        if not use_fallback:
            try:
                response = requests.get(
                    self.api_url_futures, 
                    params=params, 
                    proxies=CONFIG["proxy"],
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                
                if data and len(data) > 0:
                    print(f"[DAODAO] 使用合约API (fapi) 获取数据")
                    return self._parse_klines_data(data)
            except Exception as e:
                print(f"[DAODAO] 合约API失败，回退到现货API: {e}")
        
        # 回退到现货API
        try:
            response = requests.get(
                self.api_url_spot, 
                params=params, 
                proxies=CONFIG["proxy"],
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return None
            
            print(f"[DAODAO] 使用现货API获取数据")
            return self._parse_klines_data(data)
            
        except Exception as e:
            print(f"[DAODAO] API获取失败: {e}")
            return None
    
    def _parse_klines_data(self, data):
        """解析K线数据"""
        import pandas as pd
        
        df = pd.DataFrame(data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_base_vol", "taker_quote_vol", "ignore"
        ])
        
        df = df[["open_time", "open", "high", "low", "close", "volume"]]
        df.columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df[["datetime", "open", "high", "low", "close", "volume"]]
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col])
        
        return df
    
    def update_and_save(self, retry_count: int = None):
        """更新并保存数据（内置3次自动重试+断点续传）"""
        import pandas as pd
        import time
        
        if retry_count is None:
            retry_count = CONFIG.get("data_retry", 3)
        
        os.makedirs(CONFIG["data_dir"], exist_ok=True)
        
        local_df = self.load_local_data()
        
        if local_df is None:
            # 无本地数据，全量拉取（带重试）
            print(f"[DAODAO] 无本地数据，开始全量拉取...")
            for attempt in range(1, retry_count + 1):
                print(f"[DAODAO] 尝试获取数据 ({attempt}/{retry_count})...")
                df = self.get_latest_from_api()
                if df is not None and len(df) > 0:
                    df.to_csv(self.data_path, index=False, encoding='utf-8')
                    print(f"[DAODAO] ✅ 已保存 {len(df)} 条新数据")
                    return df
                if attempt < retry_count:
                    print(f"[DAODAO] 获取失败，{3}秒后重试...")
                    time.sleep(3)
            raise ValueError(f"无法获取 {self.symbol} 数据，已重试{retry_count}次")
        
        # 检测是否需要更新
        local_latest = local_df["datetime"].max()
        print(f"[DAODAO] 本地最新数据: {local_latest}")
        
        # 尝试获取更新数据（带重试）
        start_ts = int(local_latest.timestamp() * 1000) + 3600000  # 加1小时
        
        for attempt in range(1, retry_count + 1):
            print(f"[DAODAO] 尝试更新数据 ({attempt}/{retry_count})...")
            new_df = self.get_latest_from_api(start_time=start_ts)
            
            if new_df is not None and len(new_df) > 0:
                # 合并数据
                combined = pd.concat([local_df, new_df], ignore_index=True)
                combined = combined.drop_duplicates(subset=["datetime"])
                combined = combined.sort_values("datetime").reset_index(drop=True)
                
                # 保存更新
                combined.to_csv(self.data_path, index=False, encoding='utf-8')
                print(f"[DAODAO] ✅ 数据已更新: {len(local_df)} -> {len(combined)} 条")
                return combined
            else:
                print(f"[DAODAO] 数据已是最新或获取失败")
                break
        
        return local_df  # 返回本地数据
    
    def prepare_data(self):
        """准备数据"""
        return self.update_and_save()


# ================== 2. 策略分析模块 ==================
class DaodaoStrategy:
    """大道量化策略 + 缠论分析"""
    
    def __init__(self, df, symbol: str):
        self.df = df
        self.symbol = symbol
        self.signals = []
        self.chan_analysis = {}
    
    def add_indicators(self):
        """添加技术指标"""
        import pandas as pd
        import numpy as np
        
        df = self.df
        
        # 均线系统
        for period in [5, 10, 20, 30, 60, 120]:
            df[f"ma{period}"] = df["close"].rolling(window=period).mean()
        
        # MACD
        exp1 = df["close"].ewm(span=12, adjust=False).mean()
        exp2 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = exp1 - exp2
        df["signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["signal"]
        
        # 量能
        df["volume_ma5"] = df["volume"].rolling(window=5).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma5"]
        
        # 布林带
        df["bb_mid"] = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["bb_mid"] + 2 * bb_std
        df["bb_lower"] = df["bb_mid"] - 2 * bb_std
        
        # ATR
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift(1)),
                abs(df["low"] - df["close"].shift(1))
            )
        )
        df["atr"] = df["tr"].rolling(window=14).mean()
        
        self.df = df
        return df
    
    def detect_signals(self):
        """检测交易信号"""
        df = self.df
        
        for i in range(1, len(df)):
            # MACD金叉
            if df.iloc[i-1]["macd"] < df.iloc[i-1]["signal"] and \
               df.iloc[i]["macd"] > df.iloc[i]["signal"]:
                self.signals.append({
                    "type": "MACD金叉", "index": i,
                    "datetime": df.iloc[i]["datetime"],
                    "price": df.iloc[i]["close"]
                })
            # MACD死叉
            elif df.iloc[i-1]["macd"] > df.iloc[i-1]["signal"] and \
                 df.iloc[i]["macd"] < df.iloc[i]["signal"]:
                self.signals.append({
                    "type": "MACD死叉", "index": i,
                    "datetime": df.iloc[i]["datetime"],
                    "price": df.iloc[i]["close"]
                })
        
        self.signals = self.signals[-20:] if len(self.signals) > 20 else self.signals
        return self.signals
    
    def run_chan_analysis(self):
        """缠论分析"""
        df = self.df
        tops, bottoms = [], []
        
        for i in range(2, len(df) - 2):
            if df.iloc[i]["high"] > df.iloc[i-1]["high"] and \
               df.iloc[i]["high"] > df.iloc[i-2]["high"] and \
               df.iloc[i]["high"] > df.iloc[i+1]["high"] and \
               df.iloc[i]["high"] > df.iloc[i+2]["high"]:
                tops.append({"datetime": df.iloc[i]["datetime"], "price": df.iloc[i]["high"]})
            
            if df.iloc[i]["low"] < df.iloc[i-1]["low"] and \
               df.iloc[i]["low"] < df.iloc[i-2]["low"] and \
               df.iloc[i]["low"] < df.iloc[i+1]["low"] and \
               df.iloc[i]["low"] < df.iloc[i+2]["low"]:
                bottoms.append({"datetime": df.iloc[i]["datetime"], "price": df.iloc[i]["low"]})
        
        self.chan_analysis = {"tops": tops[-10:], "bottoms": bottoms[-10:]}
        return self.chan_analysis
    
    def detect_trend(self):
        """多空趋势判断"""
        df = self.df
        latest = df.iloc[-1]
        
        score = 0
        if latest.get("ma5", 0) > latest.get("ma10", 0): score += 1
        if latest.get("ma10", 0) > latest.get("ma30", 0): score += 1
        if latest.get("ma30", 0) > latest.get("ma60", 0): score += 1
        if latest.get("ma60", 0) > latest.get("ma120", 0): score += 1
        if latest["macd"] > latest["signal"]: score += 2
        if latest["close"] > latest.get("ma5", 0): score += 1
        
        if score >= 5: return "多头", score
        elif score <= 2: return "空头", score
        else: return "震荡", score
    
    def analyze(self):
        """执行分析"""
        print(f"\n{'='*60}")
        print(f"  [DAODAO] 大道量化策略分析 - {self.symbol}")
        print(f"{'='*60}")
        
        self.add_indicators()
        self.detect_signals()
        self.run_chan_analysis()
        
        trend, score = self.detect_trend()
        latest = self.df.iloc[-1]
        
        print(f"\n[DAODAO] 当前状态:")
        print(f"  趋势: {trend} (评分:{score})")
        print(f"  价格: {latest['close']:.2f}")
        print(f"  MA5: {latest.get('ma5', 0):.2f} | MA10: {latest.get('ma10', 0):.2f}")
        print(f"  MACD: {latest['macd']:.4f} | Signal: {latest['signal']:.4f}")
        
        return {"trend": trend, "score": score, "latest": latest}


# ================== 3. 开仓计算模块 ==================
class EntryCalculator:
    """开仓计算器"""
    
    def __init__(self, df, symbol: str):
        self.df = df
        self.symbol = symbol
        self.min_ratio = CONFIG["min_reward_risk_ratio"]
    
    def find_sr_levels(self):
        """支撑压力位"""
        df = self.df
        recent = df.tail(20)
        
        resistance_1 = recent["high"].max()
        support_1 = recent["low"].min()
        
        mid = df.tail(50)
        resistance_2 = mid["high"].max()
        support_2 = mid["low"].min()
        
        return {"resistance_1": resistance_1, "resistance_2": resistance_2,
                "support_1": support_1, "support_2": support_2}
    
    def calculate_long_entry(self, current_price: float, resistance: float, 
                            support: float, atr: float):
        """计算做多方案"""
        
        # 开仓价：回踩到支撑附近
        entry = current_price
        
        # 止损：强支撑下方（2倍ATR）
        stop_loss = support - (atr * 2)
        
        # 止盈1：第一压力位
        tp1 = resistance
        
        # 止盈2：突破后继续涨
        tp2 = resistance + (resistance - support) * 0.618
        
        # 盈亏比
        risk = entry - stop_loss
        reward1 = tp1 - entry
        reward2 = tp2 - entry
        
        rr1 = reward1 / risk if risk > 0 else 0
        rr2 = reward2 / risk if risk > 0 else 0
        
        return {
            "direction": "做多",
            "entry_price": entry,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "rr1": rr1,
            "rr2": rr2,
            "qualified": max(rr1, rr2) >= self.min_ratio
        }
    
    def analyze_entry(self, trend: str, current_price: float, atr: float):
        """分析开仓机会"""
        sr = self.find_sr_levels()
        
        if trend == "多头":
            plan = self.calculate_long_entry(
                current_price, sr["resistance_1"], sr["support_1"], atr
            )
            
            rr = max(plan["rr1"], plan["rr2"])
            
            if rr >= 10:
                recommendation = "【强烈做多】盈亏比1:10+，必开！"
            elif rr >= 5:
                recommendation = "【积极做多】盈亏比1:5+，建议开仓"
            elif rr >= 4:
                recommendation = "【可以做多】盈亏比1:4，合格可开"
            else:
                recommendation = "【暂不开仓】盈亏比不足1:4"
            
            plan["recommendation"] = recommendation
            return {"plan": plan, "support": sr["support_1"], "resistance": sr["resistance_1"]}
        
        elif trend == "空头":
            return {"plan": None, "support": sr["support_1"], "resistance": sr["resistance_1"],
                    "reason": "空头趋势，不做逆势多单"}
        
        else:
            return {"plan": None, "support": sr["support_1"], "resistance": sr["resistance_1"],
                    "reason": "震荡趋势，等待突破确认"}


# ================== 4. 报告生成模块 ==================
class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.report_dir = Path(CONFIG["report_dir"])
        self.report_dir.mkdir(exist_ok=True)
    
    def generate_html(self, df, chan_data, signals):
        """生成K线图"""
        import pandas as pd
        import json
        
        chart_data = df.tail(200).copy()
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.symbol} 大道量化分析</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; text-align: center; }}
        .chart {{ background: #16213e; border-radius: 10px; padding: 15px; margin: 20px 0; }}
        .stats {{ display: flex; justify-content: space-around; flex-wrap: wrap; }}
        .stat-box {{ background: #0f3460; padding: 15px; margin: 10px; border-radius: 8px; min-width: 150px; text-align: center; }}
        .stat-label {{ color: #aaa; font-size: 12px; }}
        .stat-value {{ color: #00d4ff; font-size: 24px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>大道量化策略系统 - {self.symbol} 分析</h1>
        <div class="stats">
            <div class="stat-box"><div class="stat-label">当前价格</div><div class="stat-value">{chart_data.iloc[-1]["close"]:.2f}</div></div>
            <div class="stat-box"><div class="stat-label">MA5</div><div class="stat-value">{chart_data.iloc[-1]["ma5"]:.2f}</div></div>
            <div class="stat-box"><div class="stat-label">MA10</div><div class="stat-value">{chart_data.iloc[-1]["ma10"]:.2f}</div></div>
            <div class="stat-box"><div class="stat-label">MACD</div><div class="stat-value">{chart_data.iloc[-1]["macd"]:.4f}</div></div>
        </div>
        <div class="chart" id="mainChart"></div>
        <script>
            var trace1 = {{
                type: 'candlestick',
                x: {json.dumps([str(d) for d in chart_data['datetime']])},
                open: {json.dumps(chart_data['open'].tolist())},
                high: {json.dumps(chart_data['high'].tolist())},
                low: {json.dumps(chart_data['low'].tolist())},
                close: {json.dumps(chart_data['close'].tolist())},
                name: 'K线',
                increasing: {{line: {{color: '#ff4444'}}}},
                decreasing: {{line: {{color: '#44ff44'}}}}
            }};
            var trace2 = {{type: 'scatter', mode: 'lines', x: {json.dumps([str(d) for d in chart_data['datetime']])}, y: {json.dumps(chart_data['ma5'].tolist())}, name: 'MA5', line: {{color: '#ff00ff', width: 1}}}};
            var trace3 = {{type: 'scatter', mode: 'lines', x: {json.dumps([str(d) for d in chart_data['datetime']])}, y: {json.dumps(chart_data['ma10'].tolist())}, name: 'MA10', line: {{color: '#00ffff', width: 1}}}};
            var trace4 = {{type: 'scatter', mode: 'lines', x: {json.dumps([str(d) for d in chart_data['datetime']])}, y: {json.dumps(chart_data['ma30'].tolist())}, name: 'MA30', line: {{color: '#ffff00', width: 1}}}};
            var layout = {{title: '{self.symbol} 1小时K线', paper_bgcolor: '#16213e', plot_bgcolor: '#16213e', font: {{color: '#eee'}}, xaxis: {{rangeslider: {{visible: false}}}}, yaxis: {{title: '价格'}}}};
            Plotly.newPlot('mainChart', [trace1, trace2, trace3, trace4], layout);
        </script>
    </div>
</body>
</html>'''
        
        output_path = self.report_dir / f"{self.symbol}_1h_chan.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[DAODAO] K线图: {output_path}")
        return output_path
    
    def generate_report(self, trend: str, entry_data: dict, latest_price: float):
        """生成分析报告"""
        report = f'''# {self.symbol} 策略分析报告

## 一、当前市场状态

| 项目 | 数值 |
|------|------|
| 当前价格 | **{latest_price:.2f}** |
| 多空判断 | **{trend}** |
| 支撑位 | {entry_data.get('support', 0):.2f} |
| 压力位 | {entry_data.get('resistance', 0):.2f} |

---

## 二、开仓计划

'''
        
        plan = entry_data.get("plan")
        
        if plan:
            rr = max(plan["rr1"], plan["rr2"])
            risk_pct = (plan["entry_price"] - plan["stop_loss"]) / plan["entry_price"] * 100
            tp1_pct = (plan["tp1"] - plan["entry_price"]) / plan["entry_price"] * 100
            tp2_pct = (plan["tp2"] - plan["entry_price"]) / plan["entry_price"] * 100
            
            report += f'''### 开仓参数

| 项目 | 数值 |
|------|------|
| 开仓方向 | **{plan['direction']}** |
| 开仓价格 | `{plan['entry_price']:.2f}` |
| 止损价格 | `{plan['stop_loss']:.2f}` (-{risk_pct:.2f}%) |
| 第一止盈 | `{plan['tp1']:.2f}` (+{tp1_pct:.2f}%) |
| 第二止盈 | `{plan['tp2']:.2f}` (+{tp2_pct:.2f}%) |

### 盈亏比

| 目标 | 盈亏比 | 达标 |
|------|--------|------|
| 第一止盈 | 1:{plan['rr1']:.2f} | {'✓' if plan['rr1'] >= 4 else '✗'} |
| 第二止盈 | 1:{plan['rr2']:.2f} | {'✓' if plan['rr2'] >= 4 else '✗'} |

### 操作建议

**{plan['recommendation']}**

'''
        else:
            reason = entry_data.get("reason", "不符合开仓条件")
            report += f'''### 当前状态
{reason}

**建议：观望**

'''
        
        report += f'''---

## 三、核心原则

> **无动无静，无生无灭，无去无来，无是非，无住无往。**
> 
> **应无所住而生其心。不预测，只识别；不预判，只跟随。**
> 
> **只做顺势多单，盈亏比≥1:4方可开仓**

---
*大道量化策略系统 · {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
'''
        
        output_path = self.report_dir / f"{self.symbol}_backtest_report.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[DAODAO] 报告: {output_path}")
        return output_path


# ================== 5. GitHub上传 ==================
class GitHubUploader:
    """GitHub上传器"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.report_dir = Path(CONFIG["report_dir"])
    
    def upload(self):
        """上传到GitHub"""
        if not CONFIG["github_token"]:
            print("[DAODAO] 未设置GitHub Token，跳过上传")
            return None
        
        # TODO: 实现完整的GitHub API上传
        print("[DAODAO] GitHub上传功能开发中...")
        return None


# ================== 主程序 ==================
def main(symbol: str = "BTCUSDT"):
    """主函数"""
    # 显示品种数据库信息
    db_info = SYMBOLS_DB.get("symbols", [])
    enabled_symbols = [s["symbol"] for s in db_info if s.get("enabled", True)]
    
    print(f"\n{'='*60}")
    print(f"  [DAODAO] 大道量化策略系统 V3.0 (万能模板)")
    print(f"  标的: {symbol}")
    print(f"  品种库: {enabled_symbols}")
    print(f"{'='*60}")
    
    # 1. 数据更新补齐
    print(f"\n[1/4] 数据更新中...")
    updater = DataUpdater(symbol)
    df = updater.prepare_data()
    
    # 2. 策略分析
    print(f"\n[2/4] 策略分析中...")
    strategy = DaodaoStrategy(df, symbol)
    analysis = strategy.analyze()
    
    # 3. 开仓计算
    print(f"\n[3/4] 开仓计算中...")
    calculator = EntryCalculator(df, symbol)
    latest = analysis["latest"]
    entry_data = calculator.analyze_entry(
        analysis["trend"], 
        latest["close"],
        latest.get("atr", latest["close"] * 0.02)
    )
    
    plan = entry_data.get("plan")
    if plan:
        print(f"\n[DAODAO] 开仓方案:")
        print(f"  方向: {plan['direction']}")
        print(f"  开仓价: {plan['entry_price']:.2f}")
        print(f"  止损: {plan['stop_loss']:.2f}")
        print(f"  止盈1: {plan['tp1']:.2f} (1:{plan['rr1']:.2f})")
        print(f"  止盈2: {plan['tp2']:.2f} (1:{plan['rr2']:.2f})")
        print(f"  建议: {plan['recommendation']}")
    else:
        print(f"\n[DAODAO] {entry_data.get('reason', '暂不开仓')}")
    
    # 4. 生成报告
    print(f"\n[4/4] 生成报告...")
    reporter = ReportGenerator(symbol)
    reporter.generate_html(df, strategy.chan_analysis, strategy.signals)
    reporter.generate_report(analysis["trend"], entry_data, latest["close"])
    
    # 5. GitHub上传（预留）
    uploader = GitHubUploader(symbol)
    uploader.upload()
    
    print(f"\n{'='*60}")
    print(f"  [DAODAO] 分析完成!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="大道量化策略系统 V2.1")
    parser.add_argument("symbol", nargs="?", default="BTCUSDT", help="标的代码")
    args = parser.parse_args()
    
    main(args.symbol)
