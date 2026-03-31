# -*- coding: utf-8 -*-
"""
大道量化系统 - 1小时K线历史数据批量下载
严格串行执行，断点续传，自动清洗
时间范围: 2020-03-01 至今
"""

import os
import sys
import time
import requests
import pandas as pd
from datetime import datetime, timezone

# ── 配置 ──────────────────────────────────────────────────────────────────────
PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
START_DATE = "2020-03-01"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "1h")
INTERVAL = "1h"
LIMIT = 1500          # 每次最多1500根
MAX_RETRY = 5
RETRY_DELAY = 3       # 秒

SYMBOLS = [
    "XRPUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "TURBOUSDT",
    "SIRENUSDT",
    "BEATUSDT",
    "RIVERUSDT",
]

COLS = ["timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"]

os.makedirs(DATA_DIR, exist_ok=True)

# ── 工具函数 ─────────────────────────────────────────────────────────────────

def ts_to_ms(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def fetch_klines(symbol, start_ms, end_ms, source="fapi"):
    """从 fapi(合约) 或 api(现货) 拉取一批K线"""
    if source == "fapi":
        url = "https://fapi.binance.com/fapi/v1/klines"
    else:
        url = "https://api.binance.com/api/v3/klines"

    params = {
        "symbol": symbol,
        "interval": INTERVAL,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT,
    }
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.get(url, params=params, proxies=PROXIES, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 400:
                # 可能是 invalid symbol，返回空列表让调用方切换
                return None
            else:
                print(f"  [WARN] HTTP {resp.status_code} attempt {attempt}/{MAX_RETRY}")
        except Exception as e:
            print(f"  [WARN] 请求异常 attempt {attempt}/{MAX_RETRY}: {e}")
        time.sleep(RETRY_DELAY * attempt)
    return None

def load_existing(csv_path):
    """读取已有CSV，返回DataFrame"""
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, parse_dates=["datetime"])
        df["timestamp"] = pd.to_numeric(df["timestamp"])
        return df
    return pd.DataFrame()

def clean_df(df):
    """清洗：去重、排序、剔除异常值、时间轴对齐"""
    df = df.drop_duplicates(subset=["timestamp"]).copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 剔除价格为0或NaN
    df = df[(df["close"] > 0) & df["close"].notna()]
    df = df[(df["high"] >= df["low"])]

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return df[["timestamp", "datetime", "open", "high", "low", "close", "volume"]]

def download_symbol(symbol):
    """完整下载单个币种，断点续传"""
    csv_path = os.path.join(DATA_DIR, f"{symbol}_{INTERVAL}.csv")
    existing = load_existing(csv_path)

    start_ms = ts_to_ms(START_DATE)
    end_ms = now_ms()

    # 断点续传：从已有数据的最后时间戳续传
    if not existing.empty:
        last_ts = int(existing["timestamp"].max())
        resume_ms = last_ts + 1  # 下一毫秒开始
        if resume_ms >= end_ms - 3600000:
            print(f"  [SKIP] {symbol} 数据已是最新（最后: {existing['datetime'].iloc[-1]}）")
            return existing, "already_latest"
        print(f"  [RESUME] {symbol} 从 {existing['datetime'].iloc[-1]} 续传")
        start_ms = resume_ms
    else:
        print(f"  [NEW] {symbol} 从 {START_DATE} 全量下载")

    # 判断数据源
    source = "fapi"
    test = fetch_klines(symbol, start_ms, start_ms + 3600000 * 2, source="fapi")
    if test is None or len(test) == 0:
        source = "api"
        print(f"  [INFO] fapi无数据，切换现货API")

    all_rows = []
    cursor = start_ms
    batch_count = 0

    while cursor < end_ms:
        batch = fetch_klines(symbol, cursor, end_ms, source=source)
        if batch is None or len(batch) == 0:
            break

        all_rows.extend(batch)
        last_open_time = batch[-1][0]
        cursor = last_open_time + 1
        batch_count += 1

        if batch_count % 10 == 0:
            print(f"    已拉取 {len(all_rows)} 根K线...")

        # 防止频率限制
        time.sleep(0.15)

        if len(batch) < LIMIT:
            break  # 最后一批

    if not all_rows:
        print(f"  [WARN] {symbol} 无新数据")
        return existing, "no_new_data"

    # 构建新数据
    new_df = pd.DataFrame(all_rows, columns=COLS)
    new_df = new_df[["timestamp", "open", "high", "low", "close", "volume"]]

    # 合并旧数据
    if not existing.empty:
        combined = pd.concat([existing[["timestamp", "open", "high", "low", "close", "volume"]], new_df], ignore_index=True)
    else:
        combined = new_df

    # 清洗
    cleaned = clean_df(combined)

    # 保存
    cleaned.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"  [SAVE] {csv_path} ({len(cleaned)} 根K线)")
    return cleaned, "success"

# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("大道量化系统 - 1H K线批量下载")
    print(f"时间范围: {START_DATE} ~ 当前")
    print(f"数据目录: {DATA_DIR}")
    print("=" * 60)

    results = {}

    for i, symbol in enumerate(SYMBOLS, 1):
        print(f"\n[{i}/{len(SYMBOLS)}] 处理 {symbol} ...")
        t0 = time.time()
        try:
            df, status = download_symbol(symbol)
            elapsed = time.time() - t0
            if not df.empty:
                start_dt = df["datetime"].iloc[0] if "datetime" in df.columns else "N/A"
                end_dt = df["datetime"].iloc[-1] if "datetime" in df.columns else "N/A"
                total = len(df)
            else:
                start_dt = end_dt = "N/A"
                total = 0
            results[symbol] = {
                "status": status,
                "total": total,
                "start": start_dt,
                "end": end_dt,
                "elapsed": f"{elapsed:.1f}s"
            }
            print(f"  完成: {total} 根 | {start_dt} ~ {end_dt} | 耗时 {elapsed:.1f}s")
        except Exception as e:
            results[symbol] = {"status": "error", "error": str(e)}
            print(f"  [ERROR] {symbol}: {e}")

        # 串行间隔
        if i < len(SYMBOLS):
            time.sleep(1)

    # ── 汇总报告 ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("执行汇总")
    print("=" * 60)
    success_count = 0
    for sym, r in results.items():
        status_str = r.get("status", "unknown")
        if status_str in ("success", "already_latest"):
            success_count += 1
            print(f"  [OK] {sym:15s} {r.get('total',0):6d}根 | {r.get('start','?')} ~ {r.get('end','?')}")
        else:
            print(f"  [!!] {sym:15s} {status_str} {r.get('error','')}")

    print(f"\n完成: {success_count}/{len(SYMBOLS)} 个币种")
    print("=" * 60)
    return results

if __name__ == "__main__":
    main()
