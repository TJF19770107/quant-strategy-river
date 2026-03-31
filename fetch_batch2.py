#!/usr/bin/env python3
"""
第二批6币种1小时K线串行拉取
严格按顺序逐个处理，禁止并行
"""
import requests, time, datetime, os, pandas as pd, json

PROXIES = {'http':'http://127.0.0.1:7897','https':'http://127.0.0.1:7897'}
DATA_DIR = 'data/1h'
os.makedirs(DATA_DIR, exist_ok=True)

COLS = ['timestamp','open','high','low','close','volume','close_time','quote_vol','trades','tbbase','tbquote','ignore']

# 第二批币种列表
SYMBOLS = ['BANANAS31USDT', 'POWERUSDT', 'PIPPINUSDT', 'AIAUSDT', 'MYXUSDT', 'COAIUSDT']

def clean_save(rows, sym):
    """清洗并保存数据"""
    df = pd.DataFrame(rows, columns=COLS)[['timestamp','open','high','low','close','volume']]
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    # 剔除异常值
    df = df[(df['close']>0) & df['close'].notna() & (df['high']>=df['low'])]
    df = df.drop_duplicates('timestamp').sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'],unit='ms',utc=True).dt.strftime('%Y-%m-%d %H:%M:%S')
    df = df[['timestamp','datetime','open','high','low','close','volume']]
    path = f'{DATA_DIR}/{sym}_1h.csv'
    df.to_csv(path, index=False, encoding='utf-8')
    return df, path

def fetch_symbol(sym):
    """从fapi拉取单个币种全量数据"""
    print(f"\n{'='*50}")
    print(f"开始拉取: {sym}")
    print('='*50)
    
    url = 'https://fapi.binance.com/fapi/v1/klines'
    
    # 1. 先查最早可用时间
    start_ms = 1577836800000  # 2020-03-01
    r = requests.get(url, params={'symbol':sym,'interval':'1h','limit':1,'startTime':start_ms}, proxies=PROXIES, timeout=15)
    
    if r.status_code != 200 or not r.json():
        print(f"  [失败] fapi无数据 HTTP={r.status_code}")
        return False
    
    earliest = r.json()[0][0]
    print(f"  最早数据时间戳: {earliest}")
    
    # 2. 全量拉取
    all_rows = []
    cursor = earliest
    end_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp()*1000)
    batch = 0
    
    while cursor < end_ms:
        resp = requests.get(url, params={
            'symbol':sym,
            'interval':'1h',
            'startTime':cursor,
            'endTime':end_ms,
            'limit':1500
        }, proxies=PROXIES, timeout=20)
        
        if resp.status_code != 200 or not resp.json():
            print(f"  [中断] HTTP={resp.status_code}, 停止拉取")
            break
            
        data = resp.json()
        all_rows.extend(data)
        cursor = data[-1][0] + 1
        batch += 1
        
        if len(data) < 1500:
            break
        time.sleep(0.15)  # 避免触发限流
    
    if not all_rows:
        print(f"  [失败] 无有效数据")
        return False
    
    # 3. 清洗保存
    df, path = clean_save(all_rows, sym)
    print(f"  [成功] 保存 {len(df)} 根 K线")
    print(f"  时间范围: {df['datetime'].iloc[0]} ~ {df['datetime'].iloc[-1]}")
    print(f"  文件路径: {path}")
    
    return True

# 串行执行
results = []
for i, sym in enumerate(SYMBOLS):
    print(f"\n>>> 进度: {i+1}/{len(SYMBOLS)} <<<")
    success = fetch_symbol(sym)
    results.append({'symbol': sym, 'success': success})
    time.sleep(1)  # 币种间间隔

print("\n" + "="*60)
print("全部执行完成 - 结果汇总")
print("="*60)
for r in results:
    status = "✅" if r['success'] else "❌"
    print(f"{status} {r['symbol']}")
