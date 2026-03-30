"""
大道量化系统 - RIVER策略平衡版 v2.1
=====================================
目标：在保持高收益的同时，优化盈亏比和回撤控制

【策略核心】
- 基于v1.0的14倍收益基础
- 优化止损止盈逻辑
- 改进入场时机
- 严格风控

【优化目标】
- 保持高盈亏比（≥1:3）
- 控制最大回撤
- 提高胜率
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import os


class DaodaoStrategyV2_1:
    """平衡版策略"""

    def __init__(self, symbol="BTCUSDT", timeframe="1h", config=None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.version = "v2.1"
        self.created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 平衡版配置
        self.default_config = {
            'RIVER_WINDOW': 20,
            'PROB_THRESHOLD': 0.60,      # 降低至60%
            'VOL_THRESHOLD': 1.3,
            'STOP_LOSS_PCT': 0.025,      # 止损2.5%
            'TAKE_PROFIT_PCT': 0.08,     # 止盈8%（1:3.2盈亏比）
            'MAX_POSITION': 1.0,
            'USE_TRAILING_STOP': False,
            'TRAILING_TRIGGER': 0.06,
            'MAX_CONSECUTIVE_LOSSES': 5,
            'MIN_TRADES_PER_MONTH': 5,
            'CONFIRM_CANDLES': 2,         # 确认K线数量
            'TREND_FILTER': True,        # 趋势过滤
        }

        self.config = config if config else self.default_config
        self.strategy_name = f"Daodao_RiverBalanced_{self.version}"

    def load_data(self, file_path):
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df

    def create_features(self, df):
        df = df.copy()

        # 基础特征
        df['return'] = df['close'] / df['close'].shift(1) - 1
        df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.0001)
        df['upper_wick'] = (df['high'] - df['close']) / (df['high'] - df['low'] + 0.0001)
        df['lower_wick'] = (df['open'] - df['low']) / (df['high'] - df['low'] + 0.0001)

        # 成交量
        df['volume_ma20'] = df['volume'].rolling(self.config['RIVER_WINDOW']).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma20']

        # 均线
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(self.config['RIVER_WINDOW']).mean()
        df['ma60'] = df['close'].rolling(60).mean()
        df['ma5_ma20_ratio'] = df['ma5'] / df['ma20']

        # RIVER
        df['river_high'] = df['high'].rolling(self.config['RIVER_WINDOW']).max()
        df['river_low'] = df['low'].rolling(self.config['RIVER_WINDOW']).min()
        df['high_break'] = df['close'] > df['river_high'].shift(1)
        df['low_break'] = df['close'] < df['river_low'].shift(1)

        # 目标变量
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)

        df = df.dropna()
        return df

    def train_model(self, df):
        df = df.copy()

        # 评分系统
        df['score'] = (
            (df['return'] > 0) * 1 +
            (df['volume_ratio'] > self.config['VOL_THRESHOLD']) * 1 +
            (df['ma5'] > df['ma20']) * 1 +
            (df['body_ratio'] > 0.5) * 1 +
            (df['high_break']) * 1
        )

        df['pred_prob_up'] = df['score'] / 5
        return df

    def generate_signals(self, df):
        df = df.copy()
        df['signal'] = 0

        window = self.config['RIVER_WINDOW']
        prob_threshold = self.config['PROB_THRESHOLD']
        vol_threshold = self.config['VOL_THRESHOLD']
        confirm_candles = self.config['CONFIRM_CANDLES']

        for i in range(window, len(df) - confirm_candles):
            # 基础条件
            cond_model = df['pred_prob_up'].iloc[i] > prob_threshold
            cond_river_up = df['high_break'].iloc[i]
            cond_volume = df['volume_ratio'].iloc[i] > vol_threshold
            cond_trend = (df['ma5'].iloc[i] > df['ma20'].iloc[i]) if self.config['TREND_FILTER'] else True

            # 确认逻辑：后续K线也保持上涨
            future_confirmation = all(
                df['close'].iloc[i + j] > df['close'].iloc[i + j - 1]
                for j in range(1, confirm_candles + 1)
            )

            if cond_model and cond_river_up and cond_volume and cond_trend and future_confirmation:
                df.iloc[i, df.columns.get_loc('signal')] = 1

        return df

    def backtest(self, df, initial_capital=10000):
        cash = float(initial_capital)
        holdings = 0.0
        position_size = 0.0
        in_position = False
        entry_price = 0.0
        entry_time = None
        trade_log = []

        stop_loss_pct = self.config['STOP_LOSS_PCT']
        take_profit_pct = self.config['TAKE_PROFIT_PCT']
        max_position = self.config['MAX_POSITION']
        max_losses = self.config['MAX_CONSECUTIVE_LOSSES']
        use_trailing = self.config['USE_TRAILING_STOP']
        trailing_trigger = self.config['TRAILING_TRIGGER']

        consecutive_losses = 0

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

            if not in_position:
                if consecutive_losses >= max_losses:
                    cash_list.append(cash)
                    holdings_list.append(0.0)
                    total_list.append(cash)
                    entry_price_list.append(0.0)
                    exit_price_list.append(0.0)
                    pnl_list.append(0.0)
                    signal_list.append(0)
                    trade_type_list.append(None)
                    continue

                if signal == 1:
                    entry_price = current_price
                    entry_time = current_time
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
                stop_loss_price = entry_price * (1 - stop_loss_pct)
                take_profit_price = entry_price * (1 + take_profit_pct)

                if use_trailing:
                    unrealized_pnl_pct = (current_price - entry_price) / entry_price
                    if unrealized_pnl_pct >= trailing_trigger:
                        stop_loss_price = entry_price

                # 止盈
                if current_price >= take_profit_price:
                    pnl = (take_profit_price - entry_price) * position_size
                    cash = cash + pnl
                    holdings = 0.0
                    in_position = False
                    consecutive_losses = 0

                    trade_log.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'entry_price': entry_price,
                        'exit_price': take_profit_price,
                        'pnl': pnl,
                        'pnl_pct': (take_profit_price - entry_price) / entry_price,
                        'holding_hours': (current_time - entry_time).total_seconds() / 3600,
                        'type': 'long',
                        'result': 'win'
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
                    consecutive_losses += 1

                    trade_log.append({
                        'entry_time': entry_time,
                        'exit_time': current_time,
                        'entry_price': entry_price,
                        'exit_price': stop_loss_price,
                        'pnl': pnl,
                        'pnl_pct': (stop_loss_price - entry_price) / entry_price,
                        'holding_hours': (current_time - entry_time).total_seconds() / 3600,
                        'type': 'long',
                        'result': 'loss'
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

        # 统计
        final_balance = total_list[-1]
        total_return = (final_balance - initial_capital) / initial_capital

        total_series = pd.Series(total_list)
        max_drawdown = (total_series.cummax() - total_series).max() / total_series.cummax().max()

        trade_pnls = [p for p in pnl_list if p != 0]
        win_count = len([p for p in trade_pnls if p > 0])
        loss_count = len([p for p in trade_pnls if p < 0])
        win_rate = win_count / len(trade_pnls) * 100 if trade_pnls else 0

        avg_win = np.mean([p for p in trade_pnls if p > 0]) if win_count > 0 else 0
        avg_loss = abs(np.mean([p for p in trade_pnls if p < 0])) if loss_count > 0 else 0
        actual_rr = avg_win / avg_loss if avg_loss != 0 else 0

        returns = pd.Series(total_list).pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0

        target_rr = take_profit_pct / stop_loss_pct

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
            'target_rr': target_rr,
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
        print(f"""
========================================
【大道量化系统 - 平衡策略 {self.version} 回测结果】
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
目标盈亏比：{stats['target_rr']:.2f}

【策略配置】
RIVER窗口：{stats['config']['RIVER_WINDOW']}
ML概率阈值：{stats['config']['PROB_THRESHOLD']}
成交量阈值：{stats['config']['VOL_THRESHOLD']}倍
止损比例：{stats['config']['STOP_LOSS_PCT']:.2%}
止盈比例：{stats['config']['TAKE_PROFIT_PCT']:.2%}
确认K线：{stats['config']['CONFIRM_CANDLES']}根
趋势过滤：{'启用' if stats['config']['TREND_FILTER'] else '未启用'}

========================================
""")

    def save_results(self, stats, result_df, trade_log, output_dir="strategies/results"):
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = os.path.join(output_dir, f"{self.symbol}_{self.version}_stats_{timestamp}.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False, default=str)

        trades_file = os.path.join(output_dir, f"{self.symbol}_{self.version}_trades_{timestamp}.csv")
        result_df.to_csv(trades_file, index=True)

        log_file = os.path.join(output_dir, f"trading_log_river_profit_{timestamp}.csv")
        trade_log_df = pd.DataFrame(trade_log)
        trade_log_df.to_csv(log_file, index=False)

        print(f"\n结果已保存：")
        print(f"- 统计：{stats_file}")
        print(f"- 交易记录：{trades_file}")
        print(f"- 盈亏日志：{log_file}")

        return log_file


def run_balanced_backtest(data_file, symbol="BTCUSDT", timeframe="1h", initial_capital=10000):
    print(f"\n{'='*60}")
    print(f"大道量化系统 - 平衡策略 v2.1")
    print(f"交易品种：{symbol} | 时间周期：{timeframe}")
    print(f"目标：高收益 + 合理回撤")
    print(f"{'='*60}\n")

    strategy = DaodaoStrategyV2_1(symbol=symbol, timeframe=timeframe)

    print("1. 加载数据...")
    df = strategy.load_data(data_file)
    print(f"   数据行数：{len(df)}")
    print(f"   时间范围：{df.index[0]} 至 {df.index[-1]}")

    print("\n2. 创建技术特征...")
    df = strategy.create_features(df)
    print(f"   特征数量：{len(df.columns)}")

    print("\n3. 训练历史规律模型...")
    df = strategy.train_model(df)
    print(f"   平均预测概率：{df['pred_prob_up'].mean():.2%}")

    print("\n4. 生成交易信号...")
    df = strategy.generate_signals(df)
    signal_count = len(df[df['signal'] != 0])
    print(f"   信号数量：{signal_count}")

    print("\n5. 执行回测...")
    result = strategy.backtest(df, initial_capital)
    stats = result['stats']
    result_df = result['result_df']
    trade_log = result['trade_log']

    strategy.print_backtest_results(stats)

    print("\n6. 保存结果...")
    log_file = strategy.save_results(stats, result_df, trade_log)

    return strategy, result, log_file


if __name__ == "__main__":
    strategy, result, log_file = run_balanced_backtest(
        data_file='../my_database/1h/BTCUSDT_1h.csv',
        symbol='BTCUSDT',
        timeframe='1h',
        initial_capital=10000
    )

    print(f"\n交易日志文件：{log_file}")
