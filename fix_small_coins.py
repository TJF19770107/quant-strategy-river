# -*- coding: utf-8 -*-
"""
修复小币种1h数据 - 强制fapi全量拉取
TURBOUSDT / SIRENUSDT / BEATUSDT / RIVERUSDT
"""
import os, time, datetime, requests, pandas as pd

PROXIES = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "1h")
os.makedirs(DATA_DIR, exist_ok=True)

COLS = ["timestamp","open","high","low","close","volume",
        "close_time","quote_vol","trades","tbbase","tbquote","ignore"]

SYMBOLS = ["TURBOUSDT","SIRENUSDT","BEATUSDT","RIVERUSDT"]

def clean_save(rows, sym):
    df = pd.DataFrame(rows, columns=COLS)[["timestamp","open","high","low","close","volume"]]
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[(df["close"] > 0) & df["close"].notna() & (df["high"] >= df["low"])]
    df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df[["timestamp","datetime","open","high","low","close","volume"]]
    path = os.path.join(DATA_DIR, f"{sym}_1h.csv")
    df.to_csv(path, index=False, encoding="utf-8")
    return df, path

def main():
    for sym in SYMBOLS:
        print(f"\n=== {sym} ===")
        url = "https://fapi.binance.com/fapi/v1/klines"
        # 查最早可用时间（从2020年开始找）
        r = requests.get(url,
            params={"symbol": sym, "interval": "1h", "limit": 1, "startTime": 1577836800000},
            proxies=PROXIES, timeout=15)
        if r.status_code != 200 or not r.json():
            print(f"  fapi无数据 HTTP={r.status_code}")
            continue
        earliest = r.json()[0][0]
        dt_start = datetime.datetime.fromtimestamp(earliest/1000, tz=datetime.timezone.utc)
        print(f"  最早K线: {dt_start.strftime('%Y-%m-%d %H:%M:%S')}")

        all_rows = []
        cursor = earliest
        end_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
        cnt = 0
        while cursor < end_ms:
            resp = requests.get(url,
                params={"symbol": sym, "interval": "1h", "startTime": cursor, "endTime": end_ms, "limit": 1500},
                proxies=PROXIES, timeout=20)
            if resp.status_code != 200 or not resp.json():
                break
            data = resp.json()
            all_rows.extend(data)
            cursor = data[-1][0] + 1
            cnt += 1
            if cnt % 5 == 0:
                print(f"    已拉取 {len(all_rows)} 根...")
            if len(data) < 1500:
                break
            time.sleep(0.15)

        if not all_rows:
            print(f"  无数据")
            continue

        df, path = clean_save(all_rows, sym)
        start_str = df["datetime"].iloc[0]
        end_str = df["datetime"].iloc[-1]
        print(f"  保存 {len(df)} 根 -> {path}")
        print(f"  范围: {start_str} ~ {end_str}")
        time.sleep(1)

    print("\n全部完成")

if __name__ == "__main__":
    main()
