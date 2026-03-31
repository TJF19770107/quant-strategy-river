#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大道量化系统 - 批量分析引擎
技术分析 + 缠论 + 龙头因子 + 开仓建议
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime

DATA_DIR = 'data/daily'
REPORT_DIR = 'reports'
os.makedirs(REPORT_DIR, exist_ok=True)

SYMBOLS = ['XRPUSDT', 'ETHUSDT', 'SIRENUSDT', 'TURBOUSDT', 'BNBUSDT', 'BEATUSDT', 'RIVERUSDT']

def analyze_symbol(symbol):
    path = f'{DATA_DIR}/{symbol}_1d.csv'
    if not os.path.exists(path):
        print(f"  [SKIP] {symbol}: 无数据文件")
        return None
    
    df = pd.read_csv(path)
    for col in ['open','high','low','close','volume']:
        df[col] = df[col].astype(float)
    
    # ===== 均线 =====
    df['ma5']  = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean() if len(df) >= 60 else df['close'].rolling(len(df)).mean()
    
    # ===== MACD =====
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['dif'] = ema12 - ema26
    df['dea'] = df['dif'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = (df['dif'] - df['dea']) * 2
    
    # ===== RSI =====
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / (loss + 1e-9)))
    
    # ===== ATR =====
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()
    
    # ===== 成交量均线 =====
    df['vol_ma5']  = df['volume'].rolling(5).mean()
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    
    # ===== 取最新数据 =====
    L = df.iloc[-1]
    current = float(L['close'])
    ma5  = float(L['ma5'])
    ma10 = float(L['ma10'])
    ma20 = float(L['ma20'])
    ma60 = float(L['ma60'])
    dif  = float(L['dif'])
    dea  = float(L['dea'])
    rsi  = float(L['rsi'])
    atr  = float(L['atr'])
    vol  = float(L['volume'])
    vol_ma5 = float(L['vol_ma5'])
    vol_ma20 = float(L['vol_ma20'])
    
    max_price = float(df['high'].max())
    min_price = float(df['low'].min())
    
    # ===== 均线趋势 =====
    if ma5 > ma10 > ma20:
        ma_trend = '多头'
        ma_signal = 'BUY'
    elif ma5 < ma10 < ma20:
        ma_trend = '空头'
        ma_signal = 'SELL'
    else:
        ma_trend = '震荡'
        ma_signal = 'NEUTRAL'
    
    # ===== MACD =====
    macd_trend = 'BUY' if dif > dea else 'SELL'
    macd_desc = 'DIF>DEA 金叉' if dif > dea else 'DIF<DEA 死叉'
    hist_val = float(df['macd_hist'].iloc[-1])
    hist_prev = float(df['macd_hist'].iloc[-2]) if len(df) > 1 else 0
    macd_momentum = '上升' if hist_val > hist_prev else '下降'
    
    # ===== RSI =====
    if rsi >= 70:
        rsi_desc = '超买'
    elif rsi <= 30:
        rsi_desc = '超卖'
    elif rsi >= 55:
        rsi_desc = '偏多'
    elif rsi <= 45:
        rsi_desc = '偏空'
    else:
        rsi_desc = '中性'
    
    # ===== 成交量 =====
    vol_ratio = vol / vol_ma20 if vol_ma20 > 0 else 1.0
    if vol_ratio > 1.5:
        vol_desc = '明显放量'
    elif vol_ratio > 1.1:
        vol_desc = '温和放量'
    elif vol_ratio < 0.7:
        vol_desc = '明显缩量'
    else:
        vol_desc = '正常'
    
    # ===== 支撑阻力（最近60条） =====
    recent = df.tail(60)
    support = float(recent['low'].min())
    resistance = float(recent['high'].max())
    
    # 更精细的支撑阻力（取局部高低点）
    pivot_window = 5
    pivot_highs = []
    pivot_lows  = []
    for i in range(pivot_window, len(df) - pivot_window):
        h = df['high'].iloc[i]
        l = df['low'].iloc[i]
        if h == df['high'].iloc[i-pivot_window:i+pivot_window+1].max():
            pivot_highs.append(h)
        if l == df['low'].iloc[i-pivot_window:i+pivot_window+1].min():
            pivot_lows.append(l)
    
    # 最近的支撑阻力
    near_support = max([p for p in pivot_lows if p < current], default=support)
    near_resist  = min([p for p in pivot_highs if p > current], default=resistance)
    
    # ===== 缠论笔（顶底分型） =====
    highs_idx = []
    lows_idx  = []
    for i in range(2, len(df)-2):
        h = float(df['high'].iloc[i])
        l = float(df['low'].iloc[i])
        if (h > float(df['high'].iloc[i-1]) and h > float(df['high'].iloc[i-2]) and
            h > float(df['high'].iloc[i+1]) and h > float(df['high'].iloc[i+2])):
            highs_idx.append((i, h))
        if (l < float(df['low'].iloc[i-1]) and l < float(df['low'].iloc[i-2]) and
            l < float(df['low'].iloc[i+1]) and l < float(df['low'].iloc[i+2])):
            lows_idx.append((i, l))
    
    # 缠论趋势判断
    if len(lows_idx) >= 3:
        last3_lows = [x[1] for x in lows_idx[-3:]]
        if last3_lows[-1] > last3_lows[-2] > last3_lows[0]:
            chan_trend = '上涨趋势'
            chan_bias  = 'BUY'
        elif last3_lows[-1] < last3_lows[-2] < last3_lows[0]:
            chan_trend = '下跌趋势'
            chan_bias  = 'SELL'
        else:
            chan_trend = '震荡整理'
            chan_bias  = 'NEUTRAL'
    elif len(lows_idx) >= 2:
        if lows_idx[-1][1] > lows_idx[-2][1]:
            chan_trend = '上涨趋势'
            chan_bias  = 'BUY'
        elif lows_idx[-1][1] < lows_idx[-2][1]:
            chan_trend = '下跌趋势'
            chan_bias  = 'SELL'
        else:
            chan_trend = '震荡整理'
            chan_bias  = 'NEUTRAL'
    else:
        chan_trend = '数据不足'
        chan_bias  = 'NEUTRAL'
    
    # 最近笔顶底
    recent_highs = [x[1] for x in highs_idx[-5:]]
    recent_lows  = [x[1] for x in lows_idx[-5:]]
    
    # ===== 龙头因子 =====
    max_rise = (max_price - min_price) / min_price * 100 if min_price > 0 else 0
    
    # 历史波动性
    df['daily_ret'] = df['close'].pct_change()
    volatility = float(df['daily_ret'].std() * 100)  # 日波动率%
    
    # 距历史高点跌幅
    drawdown_from_ath = (current - max_price) / max_price * 100
    
    # 近期表现
    ret_7d  = (current / float(df['close'].iloc[-7]) - 1) * 100 if len(df) >= 7 else 0
    ret_30d = (current / float(df['close'].iloc[-30]) - 1) * 100 if len(df) >= 30 else 0
    
    # 弹性分类
    if max_rise > 500:
        elasticity = '超高弹性(妖股)'
    elif max_rise > 100:
        elasticity = '高弹性'
    elif max_rise > 50:
        elasticity = '中等弹性'
    else:
        elasticity = '低弹性'
    
    # ===== 综合信号得分 =====
    score = 0
    reasons = []
    
    if ma_signal == 'BUY':
        score += 2
        reasons.append('均线多头排列(+2)')
    if macd_trend == 'BUY':
        score += 2
        reasons.append('MACD金叉(+2)')
    if macd_momentum == '上升':
        score += 1
        reasons.append('MACD动能上升(+1)')
    if rsi_desc in ['偏多', '中性']:
        score += 1
        reasons.append(f'RSI{rsi_desc}(+1)')
    if chan_bias == 'BUY':
        score += 2
        reasons.append('缠论上涨趋势(+2)')
    if vol_desc in ['明显放量', '温和放量']:
        score += 1
        reasons.append(f'成交量{vol_desc}(+1)')
    
    # 扣分项
    if rsi_desc == '超买':
        score -= 2
        reasons.append('RSI超买(-2)')
    if ma_signal == 'SELL':
        score -= 1
        reasons.append('均线空头(-1)')
    
    # ===== 开仓建议 =====
    if score >= 6 and chan_bias == 'BUY' and ma_signal == 'BUY':
        # 计算止损止盈
        stop_loss = near_support * 0.98
        risk = current - stop_loss
        tp1 = current + risk * 1.0
        tp2 = current + risk * 2.0
        tp3 = current + risk * 4.0
        rr  = risk_reward = 4.0
        
        entry_ok = True
        entry_reason = '满足全部开仓条件'
    elif score >= 4 and chan_bias == 'BUY':
        stop_loss = near_support * 0.98
        risk = current - stop_loss
        tp1 = current + risk * 1.0
        tp2 = current + risk * 2.0
        tp3 = current + risk * 4.0
        rr  = 4.0
        entry_ok = True
        entry_reason = '基本满足开仓条件(谨慎介入)'
    else:
        stop_loss = near_support * 0.98
        risk = current - stop_loss
        tp1 = current + risk
        tp2 = current + risk * 2
        tp3 = current + risk * 4
        rr  = 4.0
        entry_ok = False
        entry_reason = f'不满足开仓条件(综合得分{score}/8)'
    
    return {
        'symbol': symbol,
        'current': current,
        'max_price': max_price,
        'min_price': min_price,
        'ma5': ma5, 'ma10': ma10, 'ma20': ma20, 'ma60': ma60,
        'ma_trend': ma_trend, 'ma_signal': ma_signal,
        'dif': dif, 'dea': dea, 'macd_trend': macd_trend, 'macd_desc': macd_desc, 'macd_momentum': macd_momentum,
        'rsi': rsi, 'rsi_desc': rsi_desc,
        'atr': atr,
        'vol_ratio': vol_ratio, 'vol_desc': vol_desc,
        'support': support, 'resistance': resistance,
        'near_support': near_support, 'near_resist': near_resist,
        'chan_trend': chan_trend, 'chan_bias': chan_bias,
        'recent_highs': recent_highs, 'recent_lows': recent_lows,
        'max_rise': max_rise, 'volatility': volatility,
        'drawdown_from_ath': drawdown_from_ath,
        'ret_7d': ret_7d, 'ret_30d': ret_30d,
        'elasticity': elasticity,
        'score': score, 'reasons': reasons,
        'entry_ok': entry_ok, 'entry_reason': entry_reason,
        'stop_loss': stop_loss, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'rr': rr,
        'rows': len(df),
        'date_from': str(df['open_time'].iloc[0])[:10] if 'open_time' in df.columns else 'N/A',
        'date_to':   str(df['open_time'].iloc[-1])[:10] if 'open_time' in df.columns else 'N/A',
    }

if __name__ == '__main__':
    print("=== 大道量化系统 - 批量因子分析 ===")
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_results = []
    for sym in SYMBOLS:
        print(f"\n[分析] {sym}...")
        r = analyze_symbol(sym)
        if r:
            all_results.append(r)
            print(f"  当前价: {r['current']:.6f} | 趋势: {r['chan_trend']} | 得分: {r['score']}/8 | 开仓: {'[YES]' if r['entry_ok'] else '[NO]'}")
    
    # 保存JSON结果
    with open('reports/batch_analysis_results.json', 'w', encoding='utf-8') as f:
        # 转换不可序列化的值
        safe_results = []
        for r in all_results:
            sr = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v) 
                  for k, v in r.items() if k not in ['recent_highs','recent_lows','reasons']}
            sr['recent_highs'] = [float(x) for x in r['recent_highs']]
            sr['recent_lows'] = [float(x) for x in r['recent_lows']]
            sr['reasons'] = r['reasons']
            safe_results.append(sr)
        json.dump(safe_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OK] 分析结果已保存 reports/batch_analysis_results.json")
    print(f"共分析 {len(all_results)} 个品种")
