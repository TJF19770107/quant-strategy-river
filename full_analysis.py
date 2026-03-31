"""
大道量化策略系统 - 全流程分析脚本
"""
import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import math
warnings.filterwarnings('ignore')

# JSON序列化修复
class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        try:
            return super().default(obj)
        except:
            return str(obj)

# 尝试导入缠论分析模块
try:
    from chan_theory import ChanTheoryAnalyzer
    CHAN_AVAILABLE = True
except:
    CHAN_AVAILABLE = False
    print("警告: 缠论模块未找到，使用简化分析")

def calculate_ma(df, periods=[5, 10, 30, 60]):
    """计算均线"""
    for p in periods:
        df[f'MA{p}'] = df['close'].rolling(p).mean()
    return df

def calculate_macd(df, fast=12, slow=26, signal=9):
    """计算MACD"""
    ema_fast = df['close'].ewm(span=fast).mean()
    ema_slow = df['close'].ewm(span=slow).mean()
    df['MACD'] = ema_fast - ema_slow
    df['MACD_signal'] = df['MACD'].ewm(span=signal).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']
    return df

def calculate_rsi(df, period=14):
    """计算RSI"""
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_volume_ma(df, period=20):
    """计算成交量均线"""
    df['VOL_MA'] = df['volume'].rolling(period).mean()
    df['VOL_RATIO'] = df['volume'] / df['VOL_MA']
    return df

def analyze_ma_system(df):
    """分析均线系统"""
    latest = df.iloc[-1]
    ma5 = latest.get('MA5', 0)
    ma10 = latest.get('MA10', 0)
    ma30 = latest.get('MA30', 0)
    ma60 = latest.get('MA60', 0)
    
    if ma5 > ma10 > ma30:
        return "多头排列", "看涨"
    elif ma5 < ma10 < ma30:
        return "空头排列", "看跌"
    else:
        return "震荡整理", "观望"

def analyze_macd(df):
    """分析MACD"""
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    macd = latest['MACD']
    signal = latest['MACD_signal']
    hist = latest['MACD_hist']
    
    # 金叉/死叉判断
    if macd > signal and prev['MACD'] <= prev['MACD_signal']:
        return "金叉", "看涨"
    elif macd < signal and prev['MACD'] >= prev['MACD_signal']:
        return "死叉", "看跌"
    elif macd > signal:
        return "多头", "看涨"
    else:
        return "空头", "看跌"

def analyze_rsi(df):
    """分析RSI"""
    latest = df.iloc[-1]
    rsi = latest['RSI']
    
    if rsi < 30:
        return rsi, "超卖", "可能反弹"
    elif rsi > 70:
        return rsi, "超买", "可能回调"
    elif rsi < 50:
        return rsi, "偏弱", "震荡"
    else:
        return rsi, "偏强", "震荡"

def find_support_resistance(df, lookback=50):
    """寻找支撑和阻力位"""
    recent = df.tail(lookback)
    
    # 寻找局部高点和低点
    highs = []
    lows = []
    for i in range(2, len(recent)-2):
        if recent.iloc[i]['high'] > recent.iloc[i-1]['high'] and \
           recent.iloc[i]['high'] > recent.iloc[i+1]['high'] and \
           recent.iloc[i]['high'] > recent.iloc[i-2]['high'] and \
           recent.iloc[i]['high'] > recent.iloc[i+2]['high']:
            highs.append(recent.iloc[i]['high'])
        
        if recent.iloc[i]['low'] < recent.iloc[i-1]['low'] and \
           recent.iloc[i]['low'] < recent.iloc[i+1]['low'] and \
           recent.iloc[i]['low'] < recent.iloc[i-2]['low'] and \
           recent.iloc[i]['low'] < recent.iloc[i+2]['low']:
            lows.append(recent.iloc[i]['low'])
    
    current = df.iloc[-1]['close']
    
    # 找最近的支撑和阻力
    support = max([l for l in lows if l < current], default=current * 0.95)
    resistance = min([h for h in highs if h > current], default=current * 1.05)
    
    return support, resistance

def find_extremes(df):
    """寻找历史高低点"""
    all_time_high = df['high'].max()
    all_time_low = df['low'].min()
    
    # 找到最高点和最低点的日期
    high_idx = df['high'].idxmax()
    low_idx = df['low'].idxmin()
    
    high_date = df.loc[high_idx, 'datetime'] if 'datetime' in df.columns else high_idx
    low_date = df.loc[low_idx, 'datetime'] if 'datetime' in df.columns else low_idx
    
    return {
        'all_time_high': all_time_high,
        'all_time_high_date': str(high_date),
        'all_time_low': all_time_low,
        'all_time_low_date': str(low_date),
        'max_rise_pct': (all_time_high - all_time_low) / all_time_low * 100 if all_time_low > 0 else 0
    }

def calculate_risk_reward(entry, stop_loss, take_profit):
    """计算盈亏比"""
    risk = abs(entry - stop_loss)
    reward = abs(take_profit - entry)
    return reward / risk if risk > 0 else 0

def generate_trading_signal(df, support, resistance):
    """生成交易信号"""
    latest = df.iloc[-1]
    current = latest['close']
    
    # 均线判断
    ma_signal = analyze_ma_system(df)[0]
    
    # MACD判断
    macd_signal, macd_bias = analyze_macd(df)
    
    # RSI判断
    rsi, rsi_zone, rsi_action = analyze_rsi(df)
    
    # 综合判断
    bullish_count = 0
    if ma_signal == "多头排列":
        bullish_count += 1
    if macd_signal == "金叉" or macd_signal == "多头":
        bullish_count += 1
    if rsi < 70 and rsi > 30:
        bullish_count += 1
    
    # 计算开仓区间和止损止盈
    atr = df['close'].rolling(14).std().iloc[-1]
    
    # 安全止损位：支撑位下方 or 入场价-2倍ATR
    safe_stop = min(support, current - 2 * atr)
    
    # 目标止盈：阻力位 or 1:4盈亏比
    target_rr = current + 4 * (current - safe_stop)
    
    # 盈亏比计算
    rr_ratio = calculate_risk_reward(current, safe_stop, target_rr)
    
    # 判断是否满足开仓条件
    can_open = False
    signal_reason = []
    
    if bullish_count >= 2 and rr_ratio >= 4:
        can_open = True
        signal_reason.append("满足2项以上看涨条件")
        signal_reason.append("盈亏比≥1:4")
    elif macd_signal == "金叉" and rsi < 60:
        can_open = True
        signal_reason.append("MACD金叉+RSI未超买")
        if rr_ratio >= 4:
            signal_reason.append("盈亏比≥1:4")
    
    return {
        'current_price': current,
        'ma_signal': ma_signal,
        'macd_signal': macd_signal,
        'macd_bias': macd_bias,
        'rsi': rsi,
        'rsi_zone': rsi_zone,
        'bullish_count': bullish_count,
        'can_open': can_open,
        'signal_reason': signal_reason,
        'entry_range': [current * 0.995, current * 1.005],
        'stop_loss': safe_stop,
        'tp1': current + (safe_stop - current) * -1,  # 1:1
        'tp2': current + (safe_stop - current) * -2,  # 1:2
        'take_profit': target_rr,
        'risk_reward_ratio': rr_ratio
    }

def analyze_symbol(symbol):
    """分析单个币种"""
    print(f"\n{'='*50}")
    print(f"分析 {symbol}")
    print('='*50)
    
    # 读取数据
    filepath = f"data/{symbol}_1h.csv"
    if not os.path.exists(filepath):
        print(f"  数据文件不存在: {filepath}")
        return None
    
    df = pd.read_csv(filepath)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    
    print(f"  数据范围: {df['datetime'].min()} 至 {df['datetime'].max()}")
    print(f"  数据条数: {len(df)}")
    
    # 计算技术指标
    df = calculate_ma(df)
    df = calculate_macd(df)
    df = calculate_rsi(df)
    df = calculate_volume_ma(df)
    
    # 基础分析
    latest = df.iloc[-1]
    current_price = latest['close']
    
    print(f"\n  当前价格: {current_price}")
    
    # 均线分析
    ma_signal, ma_bias = analyze_ma_system(df)
    print(f"  均线系统: {ma_signal} ({ma_bias})")
    
    # MACD分析
    macd_signal, macd_bias = analyze_macd(df)
    print(f"  MACD: {macd_signal} ({macd_bias})")
    
    # RSI分析
    rsi, rsi_zone, rsi_action = analyze_rsi(df)
    print(f"  RSI: {rsi:.2f} ({rsi_zone})")
    
    # 支撑阻力
    support, resistance = find_support_resistance(df)
    print(f"  支撑位: {support}")
    print(f"  阻力位: { resistance}")
    
    # 历史高低点
    extremes = find_extremes(df)
    print(f"  历史最高: {extremes['all_time_high']} ({extremes['all_time_high_date']})")
    print(f"  历史最低: {extremes['all_time_low']} ({extremes['all_time_low_date']})")
    
    # 缠论分析（如果可用）
    chan_result = None
    if CHAN_AVAILABLE:
        try:
            analyzer = ChanTheoryAnalyzer(df)
            chan_result = analyzer.full_analysis()
            print(f"\n  === 缠论分析 ===")
            print(f"  分笔数: {chan_result['summary'].get('fenbi_count', 0)}")
            print(f"  线段数: {chan_result['summary'].get('xianduan_count', 0)}")
            print(f"  中枢数: {chan_result['summary'].get('zhongshu_count', 0)}")
            print(f"  趋势: {chan_result['summary'].get('trend', '未知')}")
            print(f"  信号: {chan_result['summary'].get('active_signals', '无')}")
        except Exception as e:
            print(f"  缠论分析出错: {e}")
    
    # 交易信号
    signal = generate_trading_signal(df, support, resistance)
    print(f"\n  === 交易信号 ===")
    print(f"  可开仓: {'是' if signal['can_open'] else '否'}")
    print(f"  开仓区间: {signal['entry_range'][0]:.6f} - {signal['entry_range'][1]:.6f}")
    print(f"  止损位: {signal['stop_loss']:.6f}")
    print(f"  TP1(1:1): {signal['tp1']:.6f}")
    print(f"  TP2(1:2): {signal['tp2']:.6f}")
    print(f"  目标位(1:4): {signal['take_profit']:.6f}")
    print(f"  盈亏比: 1:{signal['risk_reward_ratio']:.2f}")
    
    if signal['signal_reason']:
        print(f"  信号原因: {', '.join(signal['signal_reason'])}")
    
    # 构建龙头因子
    profile = {
        'symbol': symbol,
        'type': 'perpetual',
        'exchange': 'Binance',
        'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_info': {
            'start_date': str(df['datetime'].min()),
            'end_date': str(df['datetime'].max()),
            'total_bars': len(df)
        },
        'price_info': {
            'current_price': current_price,
            'all_time_high': extremes['all_time_high'],
            'all_time_low': extremes['all_time_low'],
            'support': support,
            'resistance': resistance
        },
        'technical_signals': {
            'ma_system': ma_signal,
            'macd': macd_signal,
            'rsi': rsi,
            'volume_ratio': latest['VOL_RATIO']
        },
        'dragon_factors': {
            'volatility_type': '高弹性' if extremes['max_rise_pct'] > 200 else '中等弹性',
            'max_rise_pct': extremes['max_rise_pct'],
            'trend_type': '上涨趋势' if ma_signal == '多头排列' else ('下跌趋势' if ma_signal == '空头排列' else '震荡整理'),
            'momentum': macd_bias,
            'signal_strength': '强' if signal['bullish_count'] >= 2 else '弱'
        },
        'trading_signal': signal
    }
    
    if chan_result:
        profile['chan_theory'] = chan_result['summary']
    
    return profile

def main():
    symbols = ['BEATUSDT', 'AIAUSDT', 'MYXUSDT', 'COAIUSDT']
    
    print("=" * 60)
    print("大道量化 - 全流程分析")
    print("=" * 60)
    
    results = {}
    
    for symbol in symbols:
        try:
            profile = analyze_symbol(symbol)
            if profile:
                results[symbol] = profile
                
                # 保存profile
                os.makedirs('dragon_tokens', exist_ok=True)
                with open(f"dragon_tokens/{symbol}_profile.json", 'w', encoding='utf-8') as f:
                    json.dump(profile, f, indent=2, ensure_ascii=False, cls=NpEncoder)
                print(f"\n  已保存: dragon_tokens/{symbol}_profile.json")
        except Exception as e:
            print(f"分析 {symbol} 出错: {e}")
            import traceback
            traceback.print_exc()
    
    # 生成汇总报告
    print("\n" + "=" * 60)
    print("汇总报告")
    print("=" * 60)
    
    summary = []
    for symbol, profile in results.items():
        signal = profile['trading_signal']
        summary.append({
            'symbol': symbol,
            'current_price': profile['price_info']['current_price'],
            'trend': profile['dragon_factors']['trend_type'],
            'support': profile['price_info']['support'],
            'resistance': profile['price_info']['resistance'],
            'can_open': signal['can_open'],
            'rr_ratio': signal['risk_reward_ratio']
        })
    
    # 打印汇总表格
    print("\n| 币种 | 当前价 | 趋势 | 支撑 | 阻力 | 可开仓 | 盈亏比 |")
    print("|------|--------|------|------|------|--------|--------|")
    for s in summary:
        print("| {} | {} | {} | {} | {} | {} | 1:{} |".format(
            s['symbol'], s['current_price'], s['trend'], 
            round(s['support'], 6), round(s['resistance'], 6),
            '是' if s['can_open'] else '否',
            round(s['rr_ratio'], 1)
        ))
    
    # 保存汇总
    with open("reports/summary.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, cls=NpEncoder)
    
    print("\n分析完成!")
    return results

if __name__ == "__main__":
    main()
