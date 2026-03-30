#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
大道量化系统 - SIRENUSDT 多空闭环策略
遵循：本觉无染，不贪不恐，不住相
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.spatial.distance import euclidean

# ====== 只需修改这里 ======
SYMBOL = "SIRENUSDT"
DATA_FILE = f"{SYMBOL}_1h_database.csv"
INITIAL_CAPITAL = 10000.0
# =========================

# 心法
print("=" * 60)
print("大道量化系统 - SIRENUSDT")
print("=" * 60)
print("心法：本觉无染，不贪不恐，不住相")
print("思维：第一性原理，极简结构，顺势而为")
print("=" * 60)

# 加载数据库
df = pd.read_csv(DATA_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])
print(f"\n【数据加载】{DATA_FILE}")
print(f"K线数量: {len(df)}")
print(f"时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
print(f"价格范围: {df['close'].min():.4f} ~ {df['close'].max():.4f}")


# 缠论顶底分型（5根K线）
def add_fractal(df):
    df["high_prev2"] = df["high"].shift(2)
    df["high_prev1"] = df["high"].shift(1)
    df["high_next1"] = df["high"].shift(-1)
    df["high_next2"] = df["high"].shift(-2)

    df["low_prev2"] = df["low"].shift(2)
    df["low_prev1"] = df["low"].shift(1)
    df["low_next1"] = df["low"].shift(-1)
    df["low_next2"] = df["low"].shift(-2)

    df["top"] = (
        (df["high"] > df["high_prev1"]) & (df["high"] > df["high_prev2"]) &
        (df["high"] > df["high_next1"]) & (df["high"] > df["high_next2"])
    )

    df["bottom"] = (
        (df["low"] < df["low_prev1"]) & (df["low"] < df["low_prev2"]) &
        (df["low"] < df["low_next1"]) & (df["low"] < df["low_next2"])
    )
    return df


# 提取K线特征（4维特征向量）
def get_feature(df, i):
    return [
        df.loc[i, "close"] / df.loc[i-2:i, "close"].mean(),  # 价格相对位置
        df.loc[i, "volume"] / df.loc[i-5:i, "volume"].mean(),  # 成交量相对强度
        df.loc[i, "high"] - df.loc[i, "low"],  # 振幅
        (df.loc[i, "close"] - df.loc[i, "open"]) / df.loc[i, "open"]  # K线涨跌幅
    ]


# 匹配最相似历史K线（欧氏距离）
def find_similar(df, i, window=10):
    current = get_feature(df, i)
    best_sim = float('inf')
    best_idx = -1

    for j in range(window, i - window):
        try:
            fea = get_feature(df, j)
            d = euclidean(current, fea)
            if d < best_sim:
                best_sim = d
                best_idx = j
        except:
            continue
    return best_idx


# 大道多空闭环策略
def run_dao_strategy(df):
    df = add_fractal(df)

    df["long_entry"] = 0  # 开多
    df["long_exit"] = 0   # 平多
    df["short_entry"] = 0  # 开空
    df["short_exit"] = 0   # 平空

    print("\n【策略运行】相似K线匹配 + 缠论分型")

    for i in range(15, len(df) - 15):
        sim_idx = find_similar(df, i)
        if sim_idx == -1:
            continue

        # 计算相似历史未来涨跌（9小时后）
        future_return = df.loc[sim_idx+3 : sim_idx+12, "close"].pct_change().sum()

        # 开多信号：底分型 + 历史上涨概率高
        if df.loc[i, "bottom"] and future_return > 0.015:
            df.loc[i, "long_entry"] = 1

        # 平多信号：顶分型 + 历史下跌趋势
        if df.loc[i, "top"] and future_return < -0.008:
            df.loc[i, "long_exit"] = 1

        # 开空信号：顶分型 + 历史下跌概率高
        if df.loc[i, "top"] and future_return < -0.015:
            df.loc[i, "short_entry"] = 1

        # 平空信号：底分型 + 历史上涨趋势
        if df.loc[i, "bottom"] and future_return > 0.008:
            df.loc[i, "short_exit"] = 1

    return df


# 大道回测系统（严格风控）
def backtest_with_risk_control(df):
    capital = INITIAL_CAPITAL
    position = 0  # 0空仓 1多 -1空
    trades = []
    equity_curve = [capital]

    consecutive_losses = 0
    is_paused = False

    for i in range(len(df)):
        price = df.loc[i, "close"]
        ts = df.loc[i, "timestamp"]

        # 连续亏损保护
        if consecutive_losses >= 3:
            is_paused = True

        if is_paused:
            # 暂停期间不平仓，等待自然结束
            continue

        # 开多
        if df.loc[i, "long_entry"] == 1 and position == 0:
            position = 1
            entry_price = price
            trades.append(("开多", ts, price, capital))
            print(f"开多: {ts}, 价格: {price:.4f}")

        # 平多
        elif df.loc[i, "long_exit"] == 1 and position == 1:
            ret = (price - entry_price) / entry_price
            capital = capital * (1 + ret)
            consecutive_losses = 0 if ret > 0 else consecutive_losses + 1
            position = 0
            trades.append(("平多", ts, price, capital))
            print(f"平多: {ts}, 价格: {price:.4f}, 收益率: {ret*100:.2f}%")

        # 开空
        elif df.loc[i, "short_entry"] == 1 and position == 0:
            position = -1
            entry_price = price
            trades.append(("开空", ts, price, capital))
            print(f"开空: {ts}, 价格: {price:.4f}")

        # 平空
        elif df.loc[i, "short_exit"] == 1 and position == -1:
            ret = (entry_price - price) / entry_price
            capital = capital * (1 + ret)
            consecutive_losses = 0 if ret > 0 else consecutive_losses + 1
            position = 0
            trades.append(("平空", ts, price, capital))
            print(f"平空: {ts}, 价格: {price:.4f}, 收益率: {ret*100:.2f}%")

        # 计算权益曲线
        equity = capital if position == 0 else (
            capital * (price / entry_price) if position == 1 else
            capital * (entry_price / price)
        )
        equity_curve.append(equity)

    final_capital = equity_curve[-1]
    total_return = (final_capital / INITIAL_CAPITAL - 1) * 100

    return trades, final_capital, total_return, equity_curve


# 生成回测报告
def generate_report(trades, final_capital, total_return, equity_curve):
    print("\n" + "=" * 60)
    print("【大道量化系统 - 回测报告】")
    print("=" * 60)
    print(f"初始资金: ${INITIAL_CAPITAL:.2f}")
    print(f"最终资金: ${final_capital:.2f}")
    print(f"总收益率: {total_return:.2f}%")
    print(f"总交易次数: {len(trades)}")

    # 统计多空交易
    long_trades = [t for t in trades if t[0] in ["开多", "平多"]]
    short_trades = [t for t in trades if t[0] in ["开空", "平空"]]
    print(f"多仓交易: {len(long_trades) // 2} 次")
    print(f"空仓交易: {len(short_trades) // 2} 次")

    # 计算最大回撤
    max_drawdown = 0
    peak = equity_curve[0]
    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    print(f"最大回撤: {max_drawdown * 100:.2f}%")
    print("=" * 60)


# 绘制K线图 + 4色交易标记
def plot_strategy(df, trades):
    le = [t[1] for t in trades if t[0] == "开多"]
    lp = [t[2] for t in trades if t[0] == "开多"]
    lx = [t[1] for t in trades if t[0] == "平多"]
    xp = [t[2] for t in trades if t[0] == "平多"]

    se = [t[1] for t in trades if t[0] == "开空"]
    sp = [t[2] for t in trades if t[0] == "开空"]
    sx = [t[1] for t in trades if t[0] == "平空"]
    sq = [t[2] for t in trades if t[0] == "平空"]

    fig = go.Figure(data=[go.Candlestick(
        x=df["timestamp"], open=df["open"], high=df["high"], low=df["low"], close=df["close"],
        name="K线"
    )])

    fig.add_scatter(x=le, y=lp, mode="markers", marker=dict(color="#00FF00", size=10), name="开多")
    fig.add_scatter(x=lx, y=xp, mode="markers", marker=dict(color="#FF0000", size=10), name="平多")
    fig.add_scatter(x=se, y=sp, mode="markers", marker=dict(color="#9400D3", size=10), name="开空")
    fig.add_scatter(x=sx, y=sq, mode="markers", marker=dict(color="#0000FF", size=10), name="平空")

    fig.update_layout(
        title=f"大道量化系统 - {SYMBOL} 多空闭环策略",
        xaxis=dict(rangeslider=dict(visible=False)),
        height=800
    )

    output_file = f"{SYMBOL}_dao_cycle_strategy.html"
    fig.write_html(output_file)
    print(f"\n【可视化】图表已保存: {output_file}")


# 主运行
if __name__ == "__main__":
    # 运行策略
    df = run_dao_strategy(df)

    # 回测
    trades, final_capital, total_return, equity_curve = backtest_with_risk_control(df)

    # 生成报告
    generate_report(trades, final_capital, total_return, equity_curve)

    # 绘制图表
    plot_strategy(df, trades)

    print("\n【完成】交易即修行，不贪不恐，不住相")
