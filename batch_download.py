#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大道量化系统 - 批量日线数据下载器
支持永续合约(fapi) + 现货(api) 双通道自动切换
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
import requests
import pandas as pd
from datetime import datetime

PROXY = {'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'}
DATA_DIR = 'data/daily'
os.makedirs(DATA_DIR, exist_ok=True)

SYMBOLS = ['XRPUSDT', 'ETHUSDT', 'SIRENUSDT', 'TURBOUSDT', 'BNBUSDT', 'BEATUSDT', 'RIVERUSDT']

def fetch_klines(symbol, interval='1d', limit=1000, use_fapi=True):
    if use_fapi:
        url = 'https://fapi.binance.com/fapi/v1/klines'
    else:
        url = 'https://api.binance.com/api/v3/klines'
    
    params = {'symbol': symbol, 'interval': interval, 'limit': limit}
    try:
        r = requests.get(url, params=params, proxies=PROXY, timeout=15)
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data, 'fapi' if use_fapi else 'spot'
        elif isinstance(data, dict) and data.get('code') == -1121:
            return None, None
        return None, None
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None, None

def download_symbol(symbol):
    print(f"\n{'='*50}")
    print(f"[下载] {symbol} ...")
    
    # 1) 尝试永续合约
    klines, source = fetch_klines(symbol, use_fapi=True)
    if not klines:
        print(f"  永续合约无数据，尝试现货...")
        klines, source = fetch_klines(symbol, use_fapi=False)
    
    if not klines:
        print(f"  [FAIL] {symbol} 无法获取数据（两个通道均失败）")
        return None, None
    
    cols = ['open_time','open','high','low','close','volume','close_time',
            'quote_volume','num_trades','taker_buy_base','taker_buy_quote','ignore']
    df = pd.DataFrame(klines, columns=cols)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    for col in ['open','high','low','close','volume']:
        df[col] = df[col].astype(float)
    
    path = f'{DATA_DIR}/{symbol}_1d.csv'
    df.to_csv(path, index=False)
    
    print(f"  [OK] {symbol} | 来源: {source} | {len(df)}条 | 价格: {df['close'].iloc[-1]:.6f}")
    print(f"  时间范围: {df['open_time'].iloc[0].date()} ~ {df['open_time'].iloc[-1].date()}")
    return df, source

if __name__ == '__main__':
    print("=== 大道量化系统 - 批量日线数据下载 ===")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"品种: {', '.join(SYMBOLS)}")
    
    results = {}
    for sym in SYMBOLS:
        df, source = download_symbol(sym)
        results[sym] = {'df': df, 'source': source, 'ok': df is not None}
        time.sleep(0.5)
    
    print(f"\n{'='*50}")
    print("下载汇总:")
    for sym, r in results.items():
        status = "[OK]" if r['ok'] else "[FAIL]"
        src = r['source'] or 'N/A'
        rows = len(r['df']) if r['ok'] else 0
        print(f"  {status} {sym} ({src}) - {rows}条")
    
    ok_count = sum(1 for r in results.values() if r['ok'])
    print(f"\n完成: {ok_count}/{len(SYMBOLS)} 个币种成功下载")
