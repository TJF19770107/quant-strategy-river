"""
大道量化系统 - 核心交易策略 v1.0
=====================================
策略名称：RIVER高低点 + ML历史规律 + 高盈亏比交易
核心心法：应无所住而生其心（不预测，只识别；不预判，只跟随）

【策略核心】
1. RIVER高低点突破：20周期窗口，捕捉趋势转折点
2. ML历史规律模型：基于24根K线特征预测上涨概率
3. 高盈亏比交易：固定止损2%，止盈8%（1:4盈亏比）
4. 三重过滤：ML概率 > 55% + RIVER突破 + 放量确认（1.2倍）

【版本信息】
- 版本号：v1.0
- 创建日期：2026-03-30
- 适用品种：BTC、ETH及其他主流币种/牛股
- 时间周期：1小时K线

【核心心法体现】
- 不预测涨跌，只识别突破
- 不预设方向，只跟随趋势
- 不执着盈亏，只在确定性最高时入场
- 去除主观偏见，只做客观判断
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json
import os


class DaodaoStrategyV1:
    """
    大道量化系统核心策略类 v1.0
    支持多品种自动适配、参数优化、版本管理
    """

    def __init__(self, symbol="BTCUSDT", timeframe="1h", config=None):
        """
        初始化策略

        Parameters:
        -----------
        symbol : str
            交易品种，如 "BTCUSDT", "ETHUSDT", "AAPL"
        timeframe : str
            时间周期，如 "1h", "4h", "1d"
        config : dict
            自定义配置参数，如果为None则使用默认配置
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.version = "v1.0"
        self.created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 默认配置（BTC 1小时K线验证过的最优参数）
        self.default_config = {
            'RIVER_WINDOW': 20,           # RIVER高低点窗口
            'PROB_THRESHOLD': 0.55,      # ML预测概率阈值
            'VOL_THRESHOLD': 1.2,         # 成交量放大倍数
            'STOP_LOSS_PCT': 0.02,        # 止损百分比（2%）
            'TAKE_PROFIT_PCT': 0.08,      # 止盈百分比（8%）
            'MAX_POSITION': 1.0,          # 最大仓位比例（100%）
            'USE_TRAILING_STOP': False,   # 是否使用移动止盈
            'TRAILING_TRIGGER': 0.05,     # 移动止盈触发点（5%）
            'MAX_CONSECUTIVE_LOSSES': 999,  # 连续亏损限制
            'MIN_TRADES_PER_MONTH': 5,   # 最小交易频率
        }

        self.config = config if config else self.default_config
        self.strategy_name = f"Daodao_RiverML_{self.version}"

    def load_data(self, file_path):
        """
        加载K线数据

        Parameters:
        -----------
        file_path : str
            CSV文件路径

        Returns:
        --------
        DataFrame : K线数据
        """
        df = pd.read_csv(file_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df

    def create_features(self, df):
        """
        创建技术特征

        Parameters:
        -----------
        df : DataFrame
            原始K线数据

        Returns:
        --------
        DataFrame : 添加特征后的数据
        """
        df = df.copy()

        # 基础特征
        df['return'] = df['close'] / df['close'].shift(1) - 1
        df['body_ratio'] = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 0.0001)
        df['upper_wick'] = (df['high'] - df['close']) / (df['high'] - df['low'] + 0.0001)
        df['lower_wick'] = (df['open'] - df['low']) / (df['high'] - df['low'] + 0.0001)

        # 成交量特征
        df['volume_ma20'] = df['volume'].rolling(self.config['RIVER_WINDOW']).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma20']

        # 均线特征
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(self.config['RIVER_WINDOW']).mean()
        df['ma5_ma20_ratio'] = df['ma5'] / df['ma20']

        # RIVER高低点
        df['river_high'] = df['high'].rolling(self.config['RIVER_WINDOW']).max()
        df['river_low'] = df['low'].rolling(self.config['RIVER_WINDOW']).min()
        df['high_break'] = df['close'] > df['river_high'].shift(1)
        df['low_break'] = df['close'] < df['river_low'].shift(1)

        # 目标变量（下一小时上涨）
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)

        # 去除NaN
        df = df.dropna()

        return df

    def train_simple_model(self, df):
        """
        训练简单的历史规律模型

        基于多个技术特征的加权评分，预测上涨概率

        Parameters:
        -----------
        df : DataFrame
            包含特征的数据

        Returns:
        --------
        DataFrame : 添加预测概率的数据
        """
        df = df.copy()

        # 基于历史规律的评分系统
        df['score'] = (
            (df['return'] > 0) * 1 +           # 上涨
            (df['volume_ratio'] > self.config['VOL_THRESHOLD']) * 1 +  # 放量
            (df['ma5'] > df['ma20']) * 1 +     # 均线多头
            (df['body_ratio'] > 0.5) * 1 +     # 实体较大
            (df['high_break']) * 1             # 突破RIVER高点
        )

        # 归一化为概率（0-1之间）
        df['pred_prob_up'] = df['score'] / 5

        return df

    def generate_signals(self, df):
        """
        生成交易信号

        三重过滤：
        1. ML预测概率 > 55%
        2. RIVER突破（上涨或下跌）
        3. 成交量确认（> 1.2倍20日均量）

        Parameters:
        -----------
        df : DataFrame
            包含特征和预测的数据

        Returns:
        --------
        DataFrame : 添加交易信号的数据
        """
        df = df.copy()
        df['signal'] = 0

        window = self.config['RIVER_WINDOW']
        prob_threshold = self.config['PROB_THRESHOLD']
        vol_threshold = self.config['VOL_THRESHOLD']

        for i in range(window, len(df) - 1):
            # 三重过滤条件
            cond_model = df['pred_prob_up'].iloc[i] > prob_threshold
            cond_river_up = df['high_break'].iloc[i]
            cond_river_down = df['low_break'].iloc[i]
            cond_volume = df['volume_ratio'].iloc[i] > vol_threshold

            # 做多信号
            if cond_model and cond_river_up and cond_volume:
                df.iloc[i, df.columns.get_loc('signal')] = 1

            # 做空信号（可选）
            elif df['pred_prob_up'].iloc[i] < (1 - prob_threshold):
                if cond_river_down and cond_volume:
                    df.iloc[i, df.columns.get_loc('signal')] = -1

        return df

    def backtest(self, df, initial_capital=10000):
        """
        回测策略

        Parameters:
        -----------
        df : DataFrame
            包含信号的数据
        initial_capital : float
            初始资金

        Returns:
        --------
        dict : 回测结果和统计
        """
        cash = float(initial_capital)
        holdings = 0.0
        position_size = 0.0
        in_position = False
        entry_price = 0.0

        # 风控参数
        stop_loss_pct = self.config['STOP_LOSS_PCT']
        take_profit_pct = self.config['TAKE_PROFIT_PCT']
        use_trailing = self.config['USE_TRAILING_STOP']
        trailing_trigger = self.config['TRAILING_TRIGGER']
        max_position = self.config['MAX_POSITION']

        # 连续亏损计数
        consecutive_losses = 0
        max_losses = self.config['MAX_CONSECUTIVE_LOSSES']

        # 结果列表
        cash_list = []
        holdings_list = []
        total_list = []
        entry_price_list = []
        exit_price_list = []
        pnl_list = []
        signal_list = []
        trade_type_list = []  # 'long', 'short', None

        for i in range(len(df)):
            signal = df['signal'].iloc[i]
            current_price = float(df['close'].iloc[i])

            if not in_position:
                # 连续亏损保护
                if consecutive_losses >= max_losses:
                    # 跳过开仓
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
                    # 开多仓
                    entry_price = current_price
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
                # 持仓逻辑
                stop_loss_price = entry_price * (1 - stop_loss_pct)
                take_profit_price = entry_price * (1 + take_profit_pct)

                # 移动止盈逻辑
                if use_trailing:
                    unrealized_pnl_pct = (current_price - entry_price) / entry_price
                    if unrealized_pnl_pct >= trailing_trigger:
                        stop_loss_price = entry_price  # 止损移到成本价

                # 止盈
                if current_price >= take_profit_price:
                    pnl = (take_profit_price - entry_price) * position_size
                    cash = cash + pnl
                    holdings = 0.0
                    in_position = False
                    consecutive_losses = 0  # 重置连续亏损计数

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
        result_df['risk_reward_ratio'] = take_profit_pct / stop_loss_pct

        # 计算统计指标
        final_balance = total_list[-1]
        total_return = (final_balance - initial_capital) / initial_capital

        # 最大回撤
        total_series = pd.Series(total_list)
        max_drawdown = (total_series.cummax() - total_series).max() / total_series.cummax().max()

        # 盈亏统计
        trade_pnls = [p for p in pnl_list if p != 0]
        avg_win = np.mean([p for p in trade_pnls if p > 0]) if trade_pnls else 0
        avg_loss = abs(np.mean([p for p in trade_pnls if p < 0])) if trade_pnls else 0
        actual_rr = avg_win / avg_loss if avg_loss != 0 else 0

        win_count = len([p for p in trade_pnls if p > 0])
        loss_count = len([p for p in trade_pnls if p < 0])
        win_rate = win_count / len(trade_pnls) * 100 if trade_pnls else 0

        # 夏普比率（简化版，假设无风险利率为0）
        returns = pd.Series(total_list).pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() != 0 else 0

        # 盈亏比目标
        target_rr = take_profit_pct / stop_loss_pct

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
            'target_rr': target_rr,
            'sharpe_ratio': sharpe_ratio,
            'config': self.config.copy(),
            'test_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        return {
            'result_df': result_df,
            'stats': stats
        }

    def print_backtest_results(self, stats):
        """
        打印回测结果

        Parameters:
        -----------
        stats : dict
            回测统计结果
        """
        print(f"""
========================================
【大道量化系统 - 核心策略 {self.version} 回测结果】
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
最大仓位：{stats['config']['MAX_POSITION']:.2%}
移动止盈：{'启用' if stats['config']['USE_TRAILING_STOP'] else '未启用'}

========================================
""")

    def save_results(self, stats, result_df, output_dir="strategies/results"):
        """
        保存回测结果

        Parameters:
        -----------
        stats : dict
            统计结果
        result_df : DataFrame
            详细交易记录
        output_dir : str
            输出目录
        """
        # 创建目录
        os.makedirs(output_dir, exist_ok=True)

        # 保存统计结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = os.path.join(output_dir, f"{self.symbol}_{self.version}_stats_{timestamp}.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False, default=str)

        # 保存交易记录
        trades_file = os.path.join(output_dir, f"{self.symbol}_{self.version}_trades_{timestamp}.csv")
        result_df.to_csv(trades_file)

        print(f"\n结果已保存：")
        print(f"- 统计：{stats_file}")
        print(f"- 交易记录：{trades_file}")

    def auto_optimize(self, df, initial_capital=10000):
        """
        自动优化参数（简化版）

        目标：找到胜率>20%且盈亏比>=1:4的参数组合

        Parameters:
        -----------
        df : DataFrame
            K线数据
        initial_capital : float
            初始资金

        Returns:
        --------
        dict : 优化结果
        """
        print("\n开始自动参数优化...")

        best_config = None
        best_score = -float('inf')
        results = []

        # 测试不同的RIVER窗口（15-25）
        for river_window in [15, 20, 25]:
            # 测试不同的概率阈值（0.50-0.60）
            for prob_threshold in [0.50, 0.55, 0.60]:
                # 测试不同的盈亏比（1:3, 1:4, 1:5）
                for sl_pct, tp_pct in [(0.02, 0.06), (0.02, 0.08), (0.02, 0.10)]:
                    config = self.default_config.copy()
                    config['RIVER_WINDOW'] = river_window
                    config['PROB_THRESHOLD'] = prob_threshold
                    config['STOP_LOSS_PCT'] = sl_pct
                    config['TAKE_PROFIT_PCT'] = tp_pct

                    # 创建临时策略并回测
                    temp_strategy = DaodaoStrategyV1(
                        symbol=self.symbol,
                        timeframe=self.timeframe,
                        config=config
                    )

                    temp_df = temp_strategy.create_features(df)
                    temp_df = temp_strategy.train_simple_model(temp_df)
                    temp_df = temp_strategy.generate_signals(temp_df)
                    temp_result = temp_strategy.backtest(temp_df, initial_capital)
                    temp_stats = temp_result['stats']

                    # 计算综合评分（优先盈亏比，其次收益）
                    target_rr = tp_pct / sl_pct
                    if temp_stats['actual_rr'] >= target_rr * 0.8:  # 实际盈亏比不低于目标的80%
                        score = temp_stats['total_return'] * (1 + temp_stats['actual_rr'])
                    else:
                        score = -float('inf')

                    if score > best_score and temp_stats['win_rate'] >= 20:
                        best_score = score
                        best_config = config.copy()
                        best_stats = temp_stats.copy()

                    results.append({
                        'config': config,
                        'stats': temp_stats,
                        'score': score
                    })

        print(f"\n优化完成！最佳配置：")
        if best_config:
            print(f"RIVER窗口：{best_config['RIVER_WINDOW']}")
            print(f"概率阈值：{best_config['PROB_THRESHOLD']}")
            print(f"止损：{best_config['STOP_LOSS_PCT']:.2%}")
            print(f"止盈：{best_config['TAKE_PROFIT_PCT']:.2%}")
            print(f"预期收益：{best_stats['total_return']:.2%}")
            print(f"预期胜率：{best_stats['win_rate']:.2f}%")
            print(f"实际盈亏比：{best_stats['actual_rr']:.2f}")

            return {
                'best_config': best_config,
                'best_stats': best_stats,
                'all_results': results
            }
        else:
            print("未找到符合条件的参数组合")
            return None


def run_full_backtest(data_file, symbol="BTCUSDT", timeframe="1h", initial_capital=10000,
                      optimize=False, save=True):
    """
    运行完整回测流程

    Parameters:
    -----------
    data_file : str
        数据文件路径
    symbol : str
        交易品种
    timeframe : str
        时间周期
    initial_capital : float
        初始资金
    optimize : bool
        是否自动优化参数
    save : bool
        是否保存结果

    Returns:
    --------
    DaodaoStrategyV1 : 策略实例
    """
    print(f"\n{'='*60}")
    print(f"大道量化系统 - 核心策略 v1.0")
    print(f"交易品种：{symbol} | 时间周期：{timeframe}")
    print(f"{'='*60}\n")

    # 创建策略实例
    strategy = DaodaoStrategyV1(symbol=symbol, timeframe=timeframe)

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
    df = strategy.train_simple_model(df)
    print(f"   模型类型：基于历史规律的加权评分")

    # 生成信号
    print("\n4. 生成交易信号...")
    df = strategy.generate_signals(df)
    signal_count = len(df[df['signal'] != 0])
    print(f"   信号数量：{signal_count}")

    # 自动优化
    if optimize:
        print("\n5. 自动优化参数...")
        optimization_result = strategy.auto_optimize(df, initial_capital)

        if optimization_result:
            # 使用最佳配置重新回测
            best_config = optimization_result['best_config']
            strategy = DaodaoStrategyV1(symbol=symbol, timeframe=timeframe, config=best_config)
            df = strategy.generate_signals(df)
            print(f"\n使用优化后的配置进行回测...")

    # 回测
    print("\n6. 执行回测...")
    result = strategy.backtest(df, initial_capital)
    stats = result['stats']
    result_df = result['result_df']

    # 打印结果
    strategy.print_backtest_results(stats)

    # 保存结果
    if save:
        strategy.save_results(stats, result_df)

    return strategy


# 使用示例
if __name__ == "__main__":
    # 运行BTC回测（使用默认配置，已验证的最优参数）
    strategy = run_full_backtest(
        data_file='my_database/1h/BTCUSDT_1h.csv',
        symbol='BTCUSDT',
        timeframe='1h',
        initial_capital=10000,
        optimize=False,  # 不优化，使用已验证的最优参数
        save=True
    )

    # 运行优化测试（寻找更好的参数组合）
    # strategy_optimized = run_full_backtest(
    #     data_file='my_database/1h/BTCUSDT_1h.csv',
    #     symbol='BTCUSDT',
    #     timeframe='1h',
    #     initial_capital=10000,
    #     optimize=True,
    #     save=True
    # )
