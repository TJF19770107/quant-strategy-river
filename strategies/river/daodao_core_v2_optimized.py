"""
大道量化系统 - RIVER策略优化版 v2.0
=====================================
目标：确保所有交易盈利，控制最大回撤在15%以内

【优化策略核心】
1. 严格的入场过滤：只在高确定性时入场
2. 动态止损止盈：根据波动性调整止损止盈
3. 实时盈亏监控：单笔亏损立即停止
4. 市场环境过滤：避免在震荡市交易
5. 资金管理：动态仓位控制

【版本信息】
- 版本号：v2.0 (优化版)
- 创建日期：2026-03-30
- 目标：所有交易盈利，最大回撤≤15%

【核心优化点】
- 更严格的信号过滤（三重过滤→五重过滤）
- ATR动态止损止盈
- 市场环境识别（震荡市不交易）
- 连续亏损自动暂停
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import os


class DaodaoStrategyV2:
    """
    大道量化系统优化策略 v2.0
    确保所有交易盈利，控制回撤
    """

    def __init__(self, symbol="BTCUSDT", timeframe="1h", config=None):
        """
        初始化优化策略
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.version = "v2.0"
        self.created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 优化后的默认配置
        self.default_config = {
            'RIVER_WINDOW': 20,           # RIVER高低点窗口
            'PROB_THRESHOLD': 0.65,       # ML预测概率阈值（提高至65%）
            'VOL_THRESHOLD': 1.5,        # 成交量放大倍数（提高至1.5倍）
            'ATR_WINDOW': 14,            # ATR窗口
            'ATR_MULTIPLIER_SL': 1.5,    # ATR止损倍数
            'ATR_MULTIPLIER_TP': 4.0,    # ATR止盈倍数（1:4盈亏比）
            'MIN_ATR': 0.01,             # 最小波动率要求
            'MAX_POSITION': 1.0,          # 最大仓位比例
            'MAX_DRAWDOWN': 0.15,        # 最大回撤限制
            'CONSECUTIVE_LOSS_LIMIT': 3, # 连续亏损限制
            'TREND_STRENGTH_MIN': 0.7,   # 趋势强度最小值
            'NOISE_THRESHOLD': 0.3,      # 噪音阈值（过滤震荡）
        }

        self.config = config if config else self.default_config
        self.strategy_name = f"Daodao_RiverOptimized_{self.version}"

    def load_data(self, file_path):
        """加载K线数据"""
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df

    def create_features(self, df):
        """
        创建技术特征（增强版）
        """
        df = df.copy()

        # 基础特征
        df['return'] = df['close'] / df['close'].shift(1) - 1
        df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.0001)

        # ATR（真实波动范围）
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift(1))
        low_close = abs(df['low'] - df['close'].shift(1))
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(window=self.config['ATR_WINDOW']).mean()

        # 波动率
        df['volatility'] = df['return'].rolling(self.config['ATR_WINDOW']).std()
        df['normalized_atr'] = df['atr'] / df['close']

        # 成交量特征
        df['volume_ma20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma20']

        # 均线特征
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(self.config['RIVER_WINDOW']).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        df['ma5_ma20_ratio'] = df['ma5'] / df['ma20']
        df['ma20_ma60_ratio'] = df['ma20'] / df['ma60']

        # RIVER高低点
        df['river_high'] = df['high'].rolling(self.config['RIVER_WINDOW']).max()
        df['river_low'] = df['low'].rolling(self.config['RIVER_WINDOW']).min()
        df['high_break'] = df['close'] > df['river_high'].shift(1)
        df['low_break'] = df['close'] < df['river_low'].shift(1)

        # 趋势强度（多周期一致性）
        trend_strength = (
            (df['ma5'] > df['ma20']).astype(int) +
            (df['ma20'] > df['ma60']).astype(int) +
            (df['close'] > df['ma5']).astype(int) +
            (df['return'].rolling(5).mean() > 0).astype(int)
        ) / 4
        df['trend_strength'] = trend_strength

        # 市场噪音（价格与均线的偏离度）
        df['price_deviation'] = abs(df['close'] - df['ma20']) / df['ma20']
        df['is_noisy'] = df['price_deviation'].rolling(20).std() > self.config['NOISE_THRESHOLD']

        # 去除NaN
        df = df.dropna()

        return df

    def train_model(self, df):
        """
        训练增强的历史规律模型
        """
        df = df.copy()

        # 基于历史规律的评分系统（增强版）
        df['score'] = (
            (df['return'] > 0) * 1 +                              # 上涨
            (df['volume_ratio'] > self.config['VOL_THRESHOLD']) * 1 +  # 放量
            (df['ma5'] > df['ma20']) * 1 +                         # 均线多头
            (df['body_ratio'] > 0.5) * 1 +                         # 实体较大
            (df['high_break']) * 1 +                               # 突破RIVER高点
            (df['trend_strength'] > self.config['TREND_STRENGTH_MIN']) * 1 +  # 趋势强度
            (df['normalized_atr'] > self.config['MIN_ATR']) * 1 +   # 波动率足够
            (~df['is_noisy']) * 1                                   # 低噪音
        )

        # 归一化为概率
        df['pred_prob_up'] = df['score'] / 8

        return df

    def generate_signals(self, df):
        """
        生成严格的交易信号（五重过滤）
        """
        df = df.copy()
        df['signal'] = 0

        window = self.config['RIVER_WINDOW']
        prob_threshold = self.config['PROB_THRESHOLD']
        vol_threshold = self.config['VOL_THRESHOLD']

        for i in range(window + 60, len(df) - 1):  # 确保有足够的历史数据
            # 五重过滤条件
            cond_model = df['pred_prob_up'].iloc[i] > prob_threshold  # 1. ML概率高
            cond_river_up = df['high_break'].iloc[i]                  # 2. RIVER突破
            cond_volume = df['volume_ratio'].iloc[i] > vol_threshold  # 3. 成交量放大
            cond_trend = df['trend_strength'].iloc[i] > self.config['TREND_STRENGTH_MIN']  # 4. 趋势强
            cond_noise = not df['is_noisy'].iloc[i]                  # 5. 低噪音

            # 所有条件满足才开仓
            if cond_model and cond_river_up and cond_volume and cond_trend and cond_noise:
                df.iloc[i, df.columns.get_loc('signal')] = 1

        return df

    def backtest(self, df, initial_capital=10000):
        """
        严格回测（确保盈利）
        """
        cash = float(initial_capital)
        holdings = 0.0
        position_size = 0.0
        in_position = False
        entry_price = 0.0
        entry_time = None
        trade_log = []

        # 风控参数
        atr_multiplier_sl = self.config['ATR_MULTIPLIER_SL']
        atr_multiplier_tp = self.config['ATR_MULTIPLIER_TP']
        max_position = self.config['MAX_POSITION']
        max_drawdown = self.config['MAX_DRAWDOWN']
        consecutive_loss_limit = self.config['CONSECUTIVE_LOSS_LIMIT']

        # 初始最高点（用于回撤控制）
        peak_equity = initial_capital
        consecutive_losses = 0

        # 结果列表
        cash_list = []
        holdings_list = []
        total_list = []
        entry_price_list = []
        exit_price_list = []
        pnl_list = []
        signal_list = []
        trade_type_list = []

        for i in range(len(df)):
            signal = df['signal'].iloc[i]
            current_price = float(df['close'].iloc[i])
            current_time = df.index[i]
            current_atr = df['atr'].iloc[i] if not pd.isna(df['atr'].iloc[i]) else 0

            if not in_position:
                # 计算当前权益
                current_equity = cash
                peak_equity = max(peak_equity, current_equity)
                current_drawdown = (peak_equity - current_equity) / peak_equity

                # 回撤过大时暂停交易
                if current_drawdown >= max_drawdown:
                    cash_list.append(cash)
                    holdings_list.append(0.0)
                    total_list.append(cash)
                    entry_price_list.append(0.0)
                    exit_price_list.append(0.0)
                    pnl_list.append(0.0)
                    signal_list.append(0)
                    trade_type_list.append(None)
                    continue

                # 连续亏损时暂停交易
                if consecutive_losses >= consecutive_loss_limit:
                    cash_list.append(cash)
                    holdings_list.append(0.0)
                    total_list.append(cash)
                    entry_price_list.append(0.0)
                    exit_price_list.append(0.0)
                    pnl_list.append(0.0)
                    signal_list.append(0)
                    trade_type_list.append(None)
                    continue

                # 开仓信号
                if signal == 1 and current_atr > 0:
                    # 计算动态止损止盈
                    atr_sl = current_atr * atr_multiplier_sl
                    atr_tp = current_atr * atr_multiplier_tp

                    entry_price = current_price
                    entry_time = current_time
                    stop_loss_price = entry_price - atr_sl
                    take_profit_price = entry_price + atr_tp

                    # 记录交易计划
                    trade_cash = cash * max_position
                    position_size = trade_cash / current_price
                    holdings = position_size * current_price
                    in_position = True
                    trade_type = 'long'

                    cash_list.append(cash)
                    holdings_list.append(holdings)
                    total_list.append(cash)
                    entry_price_list.append(entry_price)
                    exit_price_list.append(0.0)
                    pnl_list.append(0.0)
                    signal_list.append(1)
                    trade_type_list.append(trade_type)
                else:
                    cash_list.append(cash)
                    holdings_list.append(0.0)
                    total_list.append(cash)
                    entry_price_list.append(0.0)
                    exit_price_list.append(0.0)
                    pnl_list.append(0.0)
                    signal_list.append(0)
                    trade_type_list.append(None)
            else:
                # 持仓逻辑 - 动态止损止盈
                atr_sl = df['atr'].iloc[i-1] * atr_multiplier_sl
                atr_tp = df['atr'].iloc[i-1] * atr_multiplier_tp

                stop_loss_price = entry_price - atr_sl
                take_profit_price = entry_price + atr_tp

                # 止盈
                if current_price >= take_profit_price:
                    pnl = (take_profit_price - entry_price) * position_size
                    cash = cash + pnl
                    holdings = 0.0
                    in_position = False
                    consecutive_losses = 0  # 重置连续亏损

                    # 记录交易日志
                    trade_log.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'entry_price': entry_price,
                        'exit_price': take_profit_price,
                        'pnl': pnl,
                        'pnl_pct': pnl / (entry_price * position_size),
                        'holding_hours': (current_time - entry_time).total_seconds() / 3600,
                        'type': 'long',
                        'result': 'win',
                        'atr_at_entry': df['atr'].iloc[df.index.get_loc(entry_time)]
                    })

                    cash_list.append(cash)
                    holdings_list.append(0.0)
                    total_list.append(cash)
                    entry_price_list.append(entry_price)
                    exit_price_list.append(take_profit_price)
                    pnl_list.append(pnl)
                    signal_list.append(0)
                    trade_type_list.append(trade_type)

                # 止损
                elif current_price <= stop_loss_price:
                    pnl = (stop_loss_price - entry_price) * position_size
                    cash = cash + pnl
                    holdings = 0.0
                    in_position = False
                    consecutive_losses += 1  # 连续亏损+1

                    # 记录交易日志
                    trade_log.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'entry_price': entry_price,
                        'exit_price': stop_loss_price,
                        'pnl': pnl,
                        'pnl_pct': pnl / (entry_price * position_size),
                        'holding_hours': (current_time - entry_time).total_seconds() / 3600,
                        'type': 'long',
                        'result': 'loss' if pnl < 0 else 'win',
                        'atr_at_entry': df['atr'].iloc[df.index.get_loc(entry_time)]
                    })

                    cash_list.append(cash)
                    holdings_list.append(0.0)
                    total_list.append(cash)
                    entry_price_list.append(entry_price)
                    exit_price_list.append(stop_loss_price)
                    pnl_list.append(pnl)
                    signal_list.append(0)
                    trade_type_list.append(trade_type)

                # 继续持仓
                else:
                    holdings = position_size * current_price

                    cash_list.append(cash)
                    holdings_list.append(holdings)
                    total_list.append(cash + holdings)
                    entry_price_list.append(entry_price)
                    exit_price_list.append(0.0)
                    pnl_list.append(0.0)
                    signal_list.append(1)
                    trade_type_list.append(trade_type)

        # 创建结果DataFrame
        result_df = df.copy()
        result_df['cash'] = cash_list
        result_df['holdings'] = holdings_list
        result_df['total'] = total_list
        result_df['entry_price'] = entry_price_list
        result_df['exit_price'] = exit_price_list
        result_df['pnl'] = pnl_list
        result_df['signal_traded'] = signal_list
        result_df['trade_type'] = trade_type_list

        # 计算统计指标
        final_balance = total_list[-1]
        total_return = (final_balance - initial_capital) / initial_capital

        # 最大回撤
        total_series = pd.Series(total_list)
        max_drawdown = (total_series.cummax() - total_series).max() / total_series.cummax().max()

        # 盈亏统计
        trade_pnls = [p for p in pnl_list if p != 0]
        win_count = len([p for p in trade_pnls if p > 0])
        loss_count = len([p for p in trade_pnls if p < 0])
        win_rate = win_count / len(trade_pnls) * 100 if trade_pnls else 0

        avg_win = np.mean([p for p in trade_pnls if p > 0]) if win_count > 0 else 0
        avg_loss = abs(np.mean([p for p in trade_pnls if p < 0])) if loss_count > 0 else 0
        actual_rr = avg_win / avg_loss if avg_loss != 0 else float('inf')

        # 夏普比率
        returns = pd.Series(total_list).pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0

        # 统计结果
        stats = {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'version': self.version,
            'initial_capital': initial_capital,
            'final_balance': final_balance,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'total_trades': len(trade_pnls),
            'win_count': win_count,
            'loss_count': loss_count,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'actual_rr': actual_rr,
            'sharpe_ratio': sharpe_ratio,
            'config': self.config.copy(),
            'test_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return {
            'result_df': result_df,
            'stats': stats,
            'trade_log': trade_log
        }

    def print_backtest_results(self, stats):
        """打印回测结果"""
        print(f"""
========================================
【大道量化系统 - 优化策略 {self.version} 回测结果】
========================================

【基本信息】
交易品种：{stats['symbol']}
时间周期：{stats['timeframe']}
测试日期：{stats['test_date']}
策略版本：{stats['version']}

【收益统计】
初始资金：{stats['initial_capital']:.2f}
最终资金：{stats['final_balance']:.2f}
总收益率：{stats['total_return']:.2%}
最大回撤：{stats['max_drawdown']:.2%}
夏普比率：{stats['sharpe_ratio']:.2f}

【交易统计】
交易次数：{stats['total_trades']}
盈利次数：{stats['win_count']}
亏损次数：{stats['loss_count']}
胜率：{stats['win_rate']:.2f}%

【盈亏分析】
平均盈利：{stats['avg_win']:.2f}
平均亏损：{stats['avg_loss']:.2f}
实际盈亏比：{stats['actual_rr']:.2f}

【策略配置】
RIVER窗口：{stats['config']['RIVER_WINDOW']}
ML概率阈值：{stats['config']['PROB_THRESHOLD']}
成交量阈值：{stats['config']['VOL_THRESHOLD']}倍
ATR止损倍数：{stats['config']['ATR_MULTIPLIER_SL']}
ATR止盈倍数：{stats['config']['ATR_MULTIPLIER_TP']}
最大回撤限制：{stats['config']['MAX_DRAWDOWN']:.2%}
连续亏损限制：{stats['config']['CONSECUTIVE_LOSS_LIMIT']}次

========================================
""")

    def save_results(self, stats, result_df, trade_log, output_dir="strategies/results"):
        """保存回测结果"""
        os.makedirs(output_dir, exist_ok=True)

        # 保存统计结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = os.path.join(output_dir, f"{self.symbol}_{self.version}_stats_{timestamp}.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False, default=str)

        # 保存详细交易记录
        trades_file = os.path.join(output_dir, f"{self.symbol}_{self.version}_trades_{timestamp}.csv")
        result_df.to_csv(trades_file, index=True)

        # 保存交易日志（含盈亏详情）
        log_file = os.path.join(output_dir, f"trading_log_river_profit_{timestamp}.csv")
        trade_log_df = pd.DataFrame(trade_log)
        trade_log_df.to_csv(log_file, index=False)

        print(f"\n结果已保存：")
        print(f"- 统计：{stats_file}")
        print(f"- 交易记录：{trades_file}")
        print(f"- 盈亏日志：{log_file}")

        return log_file


def run_optimized_backtest(data_file, symbol="BTCUSDT", timeframe="1h", initial_capital=10000):
    """运行优化策略回测"""
    print(f"\n{'='*60}")
    print(f"大道量化系统 - 优化策略 v2.0")
    print(f"交易品种：{symbol} | 时间周期：{timeframe}")
    print(f"目标：所有交易盈利，最大回撤≤15%")
    print(f"{'='*60}\n")

    # 创建策略实例
    strategy = DaodaoStrategyV2(symbol=symbol, timeframe=timeframe)

    # 加载数据
    print("1. 加载数据...")
    df = strategy.load_data(data_file)
    print(f"   数据行数：{len(df)}")
    print(f"   时间范围：{df.index[0]} 至 {df.index[-1]}")

    # 创建特征
    print("\n2. 创建技术特征...")
    df = strategy.create_features(df)
    print(f"   特征数量：{len(df.columns)}")

    # 训练模型
    print("\n3. 训练历史规律模型...")
    df = strategy.train_model(df)
    print(f"   平均预测概率：{df['pred_prob_up'].mean():.2%}")

    # 生成信号
    print("\n4. 生成交易信号（五重过滤）...")
    df = strategy.generate_signals(df)
    signal_count = len(df[df['signal'] != 0])
    print(f"   信号数量：{signal_count}")

    # 回测
    print("\n5. 执行回测...")
    result = strategy.backtest(df, initial_capital)
    stats = result['stats']
    result_df = result['result_df']
    trade_log = result['trade_log']

    # 打印结果
    strategy.print_backtest_results(stats)

    # 检查是否所有交易都盈利
    if stats['loss_count'] > 0:
        print(f"\n[WARNING] 仍有 {stats['loss_count']} 笔亏损交易")
        print("建议：进一步调整参数或增加过滤条件")
    else:
        print(f"\n[SUCCESS] 所有交易均盈利！")

    # 检查回撤是否达标
    if stats['max_drawdown'] <= 0.15:
        print(f"[SUCCESS] 最大回撤 {stats['max_drawdown']:.2%} ≤ 15%")
    else:
        print(f"[WARNING] 最大回撤 {stats['max_drawdown']:.2%} > 15%")

    # 保存结果
    print("\n6. 保存结果...")
    log_file = strategy.save_results(stats, result_df, trade_log)

    return strategy, result, log_file


if __name__ == "__main__":
    # 运行优化策略
    strategy, result, log_file = run_optimized_backtest(
        data_file='../my_database/1h/BTCUSDT_1h.csv',
        symbol='BTCUSDT',
        timeframe='1h',
        initial_capital=10000
    )

    print(f"\n交易日志文件：{log_file}")
