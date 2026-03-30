#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC 1小时K线数据拉取脚本
========================

功能:
- 从币安API获取BTCUSDT 1小时K线数据
- 支持增量更新 (自动识别已有数据,只拉取新数据)
- 自动保存为CSV格式
- 支持代理配置

使用方法:
    python data/fetch_btc_1h.py

参数说明:
    --start      开始日期 (格式: YYYY-MM-DD, 默认: 2020-03-01)
    --end        结束日期 (格式: YYYY-MM-DD, 默认: 今天)
    --output     输出文件路径 (默认: data/BTCUSDT_1h.csv)
    --proxy      代理地址 (格式: http://127.0.0.1:7897)
    --force      强制重新拉取 (忽略已有数据)

示例:
    # 拉取全部历史数据
    python data/fetch_btc_1h.py

    # 拉取指定时间范围
    python data/fetch_btc_1h.py --start 2024-01-01 --end 2024-12-31

    # 使用代理
    python data/fetch_btc_1h.py --proxy http://127.0.0.1:7897

    # 强制重新拉取
    python data/fetch_btc_1h.py --force
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm


class BinanceDataFetcher:
    """币安数据拉取器"""
    
    def __init__(self, proxy=None):
        """
        初始化数据拉取器
        
        Args:
            proxy: 代理地址 (格式: http://127.0.0.1:7897)
        """
        self.base_url = "https://api.binance.com/api/v3/klines"
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        
    def fetch_klines(self, symbol="BTCUSDT", interval="1h", start_time=None, end_time=None, limit=1000):
        """
        获取K线数据
        
        Args:
            symbol: 交易对 (默认: BTCUSDT)
            interval: K线周期 (默认: 1h)
            start_time: 开始时间戳 (毫秒)
            end_time: 结束时间戳 (毫秒)
            limit: 单次请求条数限制 (默认: 1000, 最大: 1000)
        
        Returns:
            list: K线数据列表
        """
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        
        try:
            response = requests.get(self.base_url, params=params, proxies=self.proxies, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求失败: {e}")
            return []
    
    def fetch_historical_data(self, symbol="BTCUSDT", interval="1h", 
                              start_date=None, end_date=None, 
                              progress_bar=True):
        """
        获取历史数据 (支持增量拉取)
        
        Args:
            symbol: 交易对
            interval: K线周期
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
            progress_bar: 是否显示进度条
        
        Returns:
            pd.DataFrame: K线数据
        """
        # 转换日期为时间戳
        if start_date:
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000)
        else:
            start_ts = int(datetime(2020, 3, 1).timestamp() * 1000)  # 默认从2020-03-01开始
        
        if end_date:
            end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp() * 1000)
        else:
            end_ts = int(datetime.now().timestamp() * 1000)
        
        # 计算总批次
        total_ms = end_ts - start_ts
        batch_size = 1000 * 60 * 60  # 1小时K线,1000条 = 约42天
        total_batches = (total_ms // batch_size) + 1
        
        # 拉取数据
        all_data = []
        current_ts = start_ts
        
        if progress_bar:
            pbar = tqdm(total=total_batches, desc="📥 拉取数据", unit="批次")
        
        while current_ts < end_ts:
            data = self.fetch_klines(
                symbol=symbol,
                interval=interval,
                start_time=current_ts,
                end_time=end_ts,
                limit=1000
            )
            
            if not data:
                break
            
            all_data.extend(data)
            current_ts = data[-1][0] + 60000  # 下一个时间点
            
            if progress_bar:
                pbar.update(1)
            
            # 如果返回数据少于1000条,说明已经拉取完毕
            if len(data) < 1000:
                break
        
        if progress_bar:
            pbar.close()
        
        # 转换为DataFrame
        df = pd.DataFrame(all_data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])
        
        # 转换数据类型
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        
        for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[col] = df[col].astype(float)
        
        # 删除重复数据
        df = df.drop_duplicates(subset=["open_time"], keep="last")
        
        return df


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="BTC 1小时K线数据拉取脚本")
    parser.add_argument("--start", type=str, default=None, help="开始日期 (格式: YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="结束日期 (格式: YYYY-MM-DD)")
    parser.add_argument("--output", type=str, default="data/BTCUSDT_1h.csv", help="输出文件路径")
    parser.add_argument("--proxy", type=str, default=None, help="代理地址 (格式: http://127.0.0.1:7897)")
    parser.add_argument("--force", action="store_true", help="强制重新拉取 (忽略已有数据)")
    
    args = parser.parse_args()
    
    # 检查输出目录
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 初始化拉取器
    fetcher = BinanceDataFetcher(proxy=args.proxy)
    
    # 检查已有数据
    existing_df = None
    if output_path.exists() and not args.force:
        print(f"📂 发现已有数据: {output_path}")
        existing_df = pd.read_csv(output_path)
        existing_df["open_time"] = pd.to_datetime(existing_df["open_time"])
        
        # 获取最后一条数据的时间
        last_time = existing_df["open_time"].max()
        start_date = (last_time + timedelta(hours=1)).strftime("%Y-%m-%d")
        
        print(f"📊 已有数据: {len(existing_df)} 条")
        print(f"🕐 最后时间: {last_time}")
        print(f"📅 增量更新: {start_date} ~ 今天")
    else:
        start_date = args.start if args.start else "2020-03-01"
        print(f"📥 全量拉取: {start_date} ~ {args.end if args.end else '今天'}")
    
    # 拉取数据
    try:
        new_df = fetcher.fetch_historical_data(
            symbol="BTCUSDT",
            interval="1h",
            start_date=start_date if not args.force else args.start,
            end_date=args.end
        )
        
        if len(new_df) == 0:
            print("✅ 数据已是最新,无需更新")
            return
        
        print(f"✅ 拉取完成: {len(new_df)} 条新数据")
        
        # 合并数据
        if existing_df is not None:
            df = pd.concat([existing_df, new_df], ignore_index=True)
            df = df.drop_duplicates(subset=["open_time"], keep="last")
            df = df.sort_values("open_time").reset_index(drop=True)
        else:
            df = new_df
        
        # 保存数据
        df.to_csv(output_path, index=False)
        print(f"💾 保存成功: {output_path}")
        print(f"📊 总数据量: {len(df)} 条")
        print(f"📅 时间范围: {df['open_time'].min()} ~ {df['open_time'].max()}")
        
    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
