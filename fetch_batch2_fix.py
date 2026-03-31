"""
第二批6币种完整数据拉取脚本
严格串行执行，确保每个币种完整拉取后再执行下一个
"""
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import json

# 代理配置
PROXIES = {
    'http': 'http://127.0.0.1:7897',
    'https': 'http://127.0.0.1:7897'
}

# 币种上线日期（UTC+8）
SYMBOLS_CONFIG = {
    'BANANAS31USDT': {'start_date': '2025-03-22', 'source': 'fapi'},
    'POWERUSDT': {'start_date': '2025-12-06', 'source': 'fapi'},
    'PIPPINUSDT': {'start_date': '2025-01-24', 'source': 'fapi'},
    'AIAUSDT': {'start_date': '2026-01-20', 'source': 'fapi'},
    'MYXUSDT': {'start_date': '2025-06-18', 'source': 'fapi'},
    'COAIUSDT': {'start_date': '2025-09-25', 'source': 'fapi'},
}

END_DATE = '2026-03-31'

def get_klines_fapi(symbol, start_time_ms, end_time_ms, limit=1500):
    """从币安合约API获取K线"""
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        'symbol': symbol,
        'interval': '1h',
        'startTime': start_time_ms,
        'endTime': end_time_ms,
        'limit': limit
    }
    
    for retry in range(3):
        try:
            resp = requests.get(url, params=params, proxies=PROXIES, timeout=30)
            data = resp.json()
            
            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                df = df.iloc[:, :6]  # 只取前6列
                df.columns = ['open_time', 'open', 'high', 'low', 'close', 'volume']
                return df
            elif isinstance(data, dict) and 'code' in data:
                print(f"  API错误: {data.get('msg', '')}")
                return None
            else:
                return None
        except Exception as e:
            print(f"  重试 {retry+1}/3: {e}")
            time.sleep(2)
    return None

def save_klines(symbol, df):
    """保存K线数据"""
    if df is None or len(df) == 0:
        print(f"  ❌ 无数据保存")
        return False
    
    # 转换时间戳
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
    df['datetime'] = df['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 只保留需要的列
    df_output = df[['datetime', 'open', 'high', 'low', 'close', 'volume']].copy()
    
    # 去重排序
    df_output = df_output.drop_duplicates()
    df_output = df_output.sort_values('datetime')
    
    # 保存
    os.makedirs('data', exist_ok=True)
    filepath = f'data/{symbol}_1h.csv'
    df_output.to_csv(filepath, index=False)
    print(f"  ✅ 已保存: {filepath} ({len(df_output)} 条)")
    return True

def fetch_symbol(symbol, config):
    """拉取单个币种数据"""
    print(f"\n{'='*60}")
    print(f"【{symbol}】")
    print(f"  上线日期: {config['start_date']}")
    print(f"  数据源: {config['source']}")
    print(f"{'='*60}")
    
    # 计算时间范围
    start_dt = datetime.strptime(config['start_date'], '%Y-%m-%d')
    end_dt = datetime.strptime(END_DATE, '%Y-%m-%d')
    
    start_time_ms = int(start_dt.timestamp() * 1000)
    end_time_ms = int(end_dt.timestamp() * 1000)
    
    print(f"  开始拉取: {config['start_date']} ~ {END_DATE}")
    
    # 分批拉取（每次1500根）
    all_data = []
    current_start = start_time_ms
    
    while current_start < end_time_ms:
        batch_end = min(current_start + 1500 * 3600 * 1000, end_time_ms)
        
        print(f"  拉取批次: {datetime.fromtimestamp(current_start/1000).strftime('%Y-%m-%d')} ~ {datetime.fromtimestamp(batch_end/1000).strftime('%Y-%m-%d')}")
        
        df = get_klines_fapi(symbol, current_start, batch_end)
        
        if df is not None and len(df) > 0:
            all_data.append(df)
            print(f"    本批: {len(df)} 根")
            current_start = int(df['open_time'].max()) + 3600 * 1000
        else:
            print(f"    无数据或出错，跳过")
            break
        
        time.sleep(0.5)  # 避免请求过快
    
    # 合并并保存
    if all_data:
        df_full = pd.concat(all_data, ignore_index=True)
        save_klines(symbol, df_full)
    else:
        print(f"  ❌ 未能获取任何数据")

def main():
    print("=" * 60)
    print("第二批6币种完整数据拉取")
    print(f"目标日期: ~ {END_DATE}")
    print("=" * 60)
    
    # 串行执行每个币种
    for i, (symbol, config) in enumerate(SYMBOLS_CONFIG.items()):
        print(f"\n[{i+1}/6] 处理 {symbol}")
        fetch_symbol(symbol, config)
        print(f"\n✅ {symbol} 完成，休息2秒后继续...")
        time.sleep(2)
    
    print("\n" + "=" * 60)
    print("全部6币种数据拉取完成！")
    print("=" * 60)

if __name__ == '__main__':
    main()
