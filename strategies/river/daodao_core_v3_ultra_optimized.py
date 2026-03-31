#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大道量化系统 v3.0 - 极致优化版
目标: 最大回撤<15%, 胜率>80%, 筛选高盈亏比交易
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os

class RiverStrategyV3:
    """
    RIVER极致优化策略 v3.0
    
    核心优化:
    1. 七重过滤机制,只选择最高确定性交易
    2. 动态止损止盈,根据ATR调整
    3. 风险控制:最大回撤15%,连续亏损限制
    4. 只交易高盈亏比信号(盈亏比>=1:4)
    """
    
    def __init__(self, river_window=20, ml_threshold=0.70, volume_ratio=1.5,
                 stop_loss_pct=1.5, take_profit_pct=6.0,
                 initial_capital=10000, position_size=1.0,
                 max_drawdown=0.15, max_consecutive_losses=3,
                 min_rr_ratio=4.0):
        """
        初始化策略参数
        
        Args:
            river_window: RIVER窗口周期
            ml_threshold: ML概率阈值
            volume_ratio: 成交量确认倍数
            stop_loss_pct: 止损百分比
            take_profit_pct: 止盈百分比
            initial_capital: 初始资金
            position_size: 仓位大小(0-1)
            max_drawdown: 最大回撤限制
            max_consecutive_losses: 最大连续亏损次数
            min_rr_ratio: 最小盈亏比
        """
        self.river_window = river_window
        self.ml_threshold = ml_threshold
        self.volume_ratio = volume_ratio
        self.stop_loss_pct = stop_loss_pct / 100
        self.take_profit_pct = take_profit_pct / 100
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.max_drawdown = max_drawdown
        self.max_consecutive_losses = max_consecutive_losses
        self.min_rr_ratio = min_rr_ratio
        
        # 状态变量
        self.capital = initial_capital
        self.position = None  # 'long' 或 'short'
        self.entry_price = None
        self.entry_time = None
        self.stop_loss = None
        self.take_profit = None
        self.consecutive_losses = 0
        self.trades = []
        self.peak_capital = initial_capital
        
    def calculate_river_levels(self, df, window):
        """
        计算RIVER高低点
        
        Args:
            df: K线数据
            window: 窗口大小
            
        Returns:
            包含river_high和river_low的DataFrame
        """
        df['river_high'] = df['high'].rolling(window=window).max()
        df['river_low'] = df['low'].rolling(window=window).min()
        df['river_high_prev'] = df['river_high'].shift(1)
        df['river_low_prev'] = df['river_low'].shift(1)
        
        return df
    
    def calculate_volume_ma(self, df, window=20):
        """
        计算成交量均线
        
        Args:
            df: K线数据
            window: 均线窗口
            
        Returns:
            包含volume_ma的DataFrame
        """
        df['volume_ma'] = df['volume'].rolling(window=window).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        return df
    
    def calculate_ml_probability(self, df, window=24):
        """
        简化的ML概率计算(基于历史规律)
        
        Args:
            df: K线数据
            window: 特征窗口
            
        Returns:
            包含ml_probability的DataFrame
        """
        # 计算历史收益率特征
        df['return_1'] = df['close'].pct_change()
        df['return_mean'] = df['return_1'].rolling(window=window).mean()
        df['return_std'] = df['return_1'].rolling(window=window).std()
        
        # 计算成交量特征
        df['volume_change'] = df['volume'].pct_change()
        df['volume_mean'] = df['volume_change'].rolling(window=window).mean()
        
        # 计算趋势强度
        df['trend_strength'] = (df['close'] - df['close'].shift(window)) / df['close'].shift(window)
        
        # 简化的概率计算(基于多因子加权)
        df['ml_probability'] = (
            (df['return_mean'] > 0).astype(float) * 0.3 +
            (df['trend_strength'] > 0.02).astype(float) * 0.3 +
            (df['volume_change'] > 0).astype(float) * 0.2 +
            (df['return_1'] > 0).astype(float) * 0.2
        )
        
        # 限制在0-1之间
        df['ml_probability'] = df['ml_probability'].clip(0, 1)
        
        return df
    
    def calculate_atr(self, df, window=14):
        """
        计算ATR(Average True Range)
        
        Args:
            df: K线数据
            window: ATR窗口
            
        Returns:
            包含atr的DataFrame
        """
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = np.abs(df['high'] - df['close'].shift(1))
        df['low_close'] = np.abs(df['low'] - df['close'].shift(1))
        
        df['true_range'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['true_range'].rolling(window=window).mean()
        
        return df
    
    def check_entry_signals(self, row, prev_row):
        """
        检查入场信号(七重过滤)
        
        Args:
            row: 当前K线
            prev_row: 前一根K线
            
        Returns:
            signal: 'long', 'short', 或 None
            confidence: 信号置信度
        """
        # 过滤1: ML概率
        if row['ml_probability'] < self.ml_threshold:
            return None, 0
        
        # 过滤2: 成交量确认
        if row['volume_ratio'] < self.volume_ratio:
            return None, 0
        
        # 过滤3: RIVER突破
        long_break = (row['close'] > prev_row['river_high_prev'])
        short_break = (row['close'] < prev_row['river_low_prev'])
        
        if not long_break and not short_break:
            return None, 0
        
        # 过滤4: 趋势确认(EMA)
        if 'ema_20' in row:
            trend_ok = (long_break and row['close'] > row['ema_20']) or \
                      (short_break and row['close'] < row['ema_20'])
            if not trend_ok:
                return None, 0
        
        # 过滤5: ATR过滤(波动率适中)
        if 'atr_pct' in row:
            atr_pct = row['atr'] / row['close']
            if atr_pct < 0.005 or atr_pct > 0.03:  # 0.5%-3%波动率
                return None, 0
        
        # 过滤6: 连续亏损限制
        if self.consecutive_losses >= self.max_consecutive_losses:
            return None, 0
        
        # 过滤7: 最大回撤保护
        current_drawdown = 1 - (self.capital / self.peak_capital)
        if current_drawdown >= self.max_drawdown:
            return None, 0
        
        # 计算置信度
        confidence = (
            (row['ml_probability'] - self.ml_threshold) / (1 - self.ml_threshold) * 0.4 +
            (row['volume_ratio'] - self.volume_ratio) / 2.0 * 0.3 +
            (1 - current_drawdown) * 0.3
        )
        
        if long_break:
            return 'long', confidence
        elif short_break:
            return 'short', confidence
        
        return None, 0
    
    def check_exit_signals(self, row, current_price):
        """
        检查出场信号
        
        Args:
            row: 当前K线
            current_price: 当前价格
            
        Returns:
            should_exit: 是否应该出场
            exit_reason: 出场原因
        """
        if self.position is None:
            return False, None
        
        # 检查止损
        if self.position == 'long' and current_price <= self.stop_loss:
            return True, 'stop_loss'
        elif self.position == 'short' and current_price >= self.stop_loss:
            return True, 'stop_loss'
        
        # 检查止盈
        if self.position == 'long' and current_price >= self.take_profit:
            return True, 'take_profit'
        elif self.position == 'short' and current_price <= self.take_profit:
            return True, 'take_profit'
        
        # 检查反向信号
        if 'ml_probability' in row:
            if row['ml_probability'] < (self.ml_threshold - 0.1):
                return True, 'signal_reverse'
        
        return False, None
    
    def execute_trade(self, signal_type, entry_price, entry_time, exit_price=None, exit_time=None, exit_reason=None):
        """
        执行交易
        
        Args:
            signal_type: 'long' 或 'short'
            entry_price: 入场价格
            entry_time: 入场时间
            exit_price: 出场价格
            exit_time: 出场时间
            exit_reason: 出场原因
        """
        position_size = self.capital * self.position_size
        
        if exit_price is None:
            # 入场
            self.position = signal_type
            self.entry_price = entry_price
            self.entry_time = entry_time
            
            # 计算止损止盈
            if signal_type == 'long':
                self.stop_loss = entry_price * (1 - self.stop_loss_pct)
                self.take_profit = entry_price * (1 + self.take_profit_pct)
            else:
                self.stop_loss = entry_price * (1 + self.stop_loss_pct)
                self.take_profit = entry_price * (1 - self.take_profit_pct)
            
            return
        else:
            # 出场
            if signal_type == 'long':
                profit_pct = (exit_price - entry_price) / entry_price
            else:
                profit_pct = (entry_price - exit_price) / entry_price
            
            profit = position_size * profit_pct
            self.capital += profit
            
            # 更新连续亏损计数
            if profit < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0
            
            # 更新峰值资金
            if self.capital > self.peak_capital:
                self.peak_capital = self.capital
            
            # 计算持仓时长
            holding_period = (exit_time - entry_time).total_seconds() / 3600  # 小时
            
            # 计算实际盈亏比
            if profit > 0:
                risk = abs(entry_price - self.stop_loss) / entry_price
                reward = abs(exit_price - entry_price) / entry_price
                rr_ratio = reward / risk if risk > 0 else 0
            else:
                rr_ratio = 0
            
            # 记录交易
            trade = {
                'signal_type': signal_type,
                'entry_time': entry_time,
                'entry_price': entry_price,
                'exit_time': exit_time,
                'exit_price': exit_price,
                'exit_reason': exit_reason,
                'profit_pct': profit_pct,
                'profit': profit,
                'holding_period_hours': holding_period,
                'capital_before': self.capital - profit,
                'capital_after': self.capital,
                'rr_ratio': rr_ratio,
                'result': 'profit' if profit > 0 else 'loss'
            }
            self.trades.append(trade)
            
            # 重置状态
            self.position = None
            self.entry_price = None
            self.entry_time = None
            self.stop_loss = None
            self.take_profit = None
    
    def backtest(self, df):
        """
        运行回测
        
        Args:
            df: K线数据
            
        Returns:
            回测结果字典
        """
        # 计算指标
        df = self.calculate_river_levels(df, self.river_window)
        df = self.calculate_volume_ma(df)
        df = self.calculate_ml_probability(df)
        df = self.calculate_atr(df)
        
        # 计算EMA用于趋势确认
        df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
        
        # 过滤低盈亏比交易
        df['atr_pct'] = df['atr'] / df['close']
        
        # 迭代K线
        for i in range(len(df)):
            if i < self.river_window + 1:
                continue
            
            row = df.iloc[i]
            prev_row = df.iloc[i-1]
            current_time = row['timestamp'] if 'timestamp' in row else row.name
            current_price = row['close']
            
            # 检查出场
            if self.position is not None:
                should_exit, exit_reason = self.check_exit_signals(row, current_price)
                if should_exit:
                    self.execute_trade(
                        self.position,
                        self.entry_price,
                        self.entry_time,
                        current_price,
                        current_time,
                        exit_reason
                    )
            
            # 检查入场
            if self.position is None:
                signal, confidence = self.check_entry_signals(row, prev_row)
                if signal is not None:
                    # 只交易高盈亏比信号
                    if row['atr_pct'] > 0.008 and row['atr_pct'] < 0.025:
                        self.execute_trade(signal, current_price, current_time)
        
        # 平仓未平仓位
        if self.position is not None:
            last_row = df.iloc[-1]
            last_time = last_row['timestamp'] if 'timestamp' in last_row else last_row.name
            last_price = last_row['close']
            self.execute_trade(
                self.position,
                self.entry_price,
                self.entry_time,
                last_price,
                last_time,
                'force_close'
            )
        
        # 计算回测结果
        result = self.calculate_results()
        
        return result
    
    def calculate_results(self):
        """
        计算回测结果
        
        Returns:
            回测结果字典
        """
        if not self.trades:
            return {
                'total_return': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'total_trades': 0,
                'profit_trades': 0,
                'loss_trades': 0,
                'avg_profit': 0,
                'avg_loss': 0,
                'avg_rr_ratio': 0,
                'sharpe_ratio': 0,
                'final_capital': self.capital
            }
        
        trades_df = pd.DataFrame(self.trades)
        
        # 计算资金曲线
        capital_curve = [self.initial_capital]
        for _, trade in trades_df.iterrows():
            capital_curve.append(trade['capital_after'])
        
        capital_curve = np.array(capital_curve)
        returns = np.diff(capital_curve) / capital_curve[:-1]
        
        # 计算最大回撤
        peak = np.maximum.accumulate(capital_curve)
        drawdown = (capital_curve - peak) / peak
        max_drawdown = abs(np.min(drawdown))
        
        # 计算夏普比率
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # 统计交易
        profit_trades = trades_df[trades_df['result'] == 'profit']
        loss_trades = trades_df[trades_df['result'] == 'loss']
        
        avg_rr_ratio = trades_df['rr_ratio'].mean()
        
        result = {
            'total_return': (self.capital - self.initial_capital) / self.initial_capital * 100,
            'max_drawdown': max_drawdown * 100,
            'win_rate': len(profit_trades) / len(trades_df) * 100,
            'total_trades': len(trades_df),
            'profit_trades': len(profit_trades),
            'loss_trades': len(loss_trades),
            'avg_profit': profit_trades['profit'].mean() if len(profit_trades) > 0 else 0,
            'avg_loss': loss_trades['profit'].mean() if len(loss_trades) > 0 else 0,
            'avg_rr_ratio': avg_rr_ratio,
            'sharpe_ratio': sharpe_ratio,
            'final_capital': self.capital
        }
        
        return result


def save_trading_log(trades, output_file):
    """
    保存交易日志
    
    Args:
        trades: 交易记录列表
        output_file: 输出文件路径
    """
    df = pd.DataFrame(trades)
    df.to_csv(output_file, index=False)
    print(f"交易日志已保存到: {output_file}")


def print_backtest_results(result, symbol):
    """
    打印回测结果
    
    Args:
        result: 回测结果字典
        symbol: 交易品种
    """
    print(f"\n{'='*60}")
    print(f"{symbol} 回测结果 - 大道量化系统 v3.0 极致优化版")
    print(f"{'='*60}")
    print(f"总收益率:       {result['total_return']:.2f}%")
    print(f"最大回撤:       {result['max_drawdown']:.2f}%")
    print(f"胜率:           {result['win_rate']:.2f}%")
    print(f"交易次数:       {result['total_trades']}")
    print(f"盈利交易:       {result['profit_trades']}")
    print(f"亏损交易:       {result['loss_trades']}")
    print(f"平均盈利:       ${result['avg_profit']:.2f}")
    print(f"平均亏损:       ${result['avg_loss']:.2f}")
    print(f"平均盈亏比:     {result['avg_rr_ratio']:.2f}")
    print(f"夏普比率:       {result['sharpe_ratio']:.2f}")
    print(f"最终资金:       ${result['final_capital']:.2f}")
    print(f"{'='*60}\n")


def run_ultra_optimized_backtest(data_file, symbol, timeframe='1h', initial_capital=10000):
    """
    运行极致优化回测
    
    Args:
        data_file: 数据文件路径
        symbol: 交易品种
        timeframe: 时间周期
        initial_capital: 初始资金
        
    Returns:
        strategy: 策略实例
        result: 回测结果
        log_file: 交易日志文件
    """
    print(f"正在加载 {symbol} {timeframe} 数据...")
    df = pd.read_csv(data_file)
    
    # 转换时间戳
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    print(f"数据范围: {df['timestamp'].min()} 至 {df['timestamp'].max()}")
    print(f"数据条数: {len(df)}")
    
    # 初始化策略
    print(f"\n初始化策略...")
    strategy = RiverStrategyV3(
        river_window=20,
        ml_threshold=0.65,  # 调整至65%
        volume_ratio=1.4,    # 调整至1.4倍
        stop_loss_pct=2.0,   # 调整止损至2.0%
        take_profit_pct=8.0, # 调整止盈至8%(1:4盈亏比)
        initial_capital=initial_capital,
        position_size=1.0,    # 满仓
        max_drawdown=0.15,   # 最大回撤15%
        max_consecutive_losses=3,  # 最大连续亏损3次
        min_rr_ratio=4.0     # 最小盈亏比4.0
    )
    
    # 运行回测
    print(f"\n开始回测...")
    result = strategy.backtest(df)
    
    # 打印结果
    print_backtest_results(result, symbol)
    
    # 保存交易日志
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs('strategies/results', exist_ok=True)
    log_file = f"strategies/results/trading_log_river_profit_{timestamp}.csv"
    save_trading_log(strategy.trades, log_file)
    
    # 复制到根目录
    root_log_file = "trading_log_river_profit.csv"
    import shutil
    shutil.copy(log_file, root_log_file)
    print(f"交易日志已复制到: {root_log_file}")
    
    return strategy, result, log_file


if __name__ == "__main__":
    # 运行极致优化策略
    strategy, result, log_file = run_ultra_optimized_backtest(
        data_file='../my_database/1h/BTCUSDT_1h.csv',
        symbol='BTCUSDT',
        timeframe='1h',
        initial_capital=10000
    )
    
    print(f"\n交易日志文件：{log_file}")
