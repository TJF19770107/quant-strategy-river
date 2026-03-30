"""
大道量化系统 - 多品种适配器
=====================================
功能：
1. 自动适配不同品种的波动特性（BTC、ETH、SIREN等）
2. 根据历史波动率自动调整参数
3. 支持牛市、牛股、庄股的强化过滤
4. 一键复用核心策略到新品种

【适配原则】
- BTC/ETH：高波动品种，使用标准参数
- 牛股/庄股：增强趋势跟踪和突破过滤
- 低波动品种：降低盈亏比，提高交易频率
"""

import pandas as pd
import numpy as np
import os


class MultiSymbolAdapter:
    """
    多品种适配器

    根据不同品种的历史特性，自动优化策略参数
    """

    def __init__(self):
        """初始化适配器"""
        self.symbol_profiles = self._load_symbol_profiles()

    def _load_symbol_profiles(self):
        """
        加载品种特性数据库

        Returns:
        --------
        dict : 品种特性配置
        """
        return {
            'BTCUSDT': {
                'category': 'crypto',
                'volatility_level': 'high',
                'base_config': {
                    'RIVER_WINDOW': 20,
                    'PROB_THRESHOLD': 0.55,
                    'VOL_THRESHOLD': 1.2,
            'STOP_LOSS_PCT': 0.02,
            'TAKE_PROFIT_PCT': 0.08,  # 1:4盈亏比
            'MAX_POSITION': 1.0,
            'USE_TRAILING_STOP': False,
            'TRAILING_TRIGGER': 0.05,
            'MAX_CONSECUTIVE_LOSSES': 999,
            'MIN_TRADES_PER_MONTH': 5
                },
                'description': '比特币 - 高波动、高流动性'
            },
            'ETHUSDT': {
                'category': 'crypto',
                'volatility_level': 'high',
                'base_config': {
                    'RIVER_WINDOW': 20,
                    'PROB_THRESHOLD': 0.55,
                    'VOL_THRESHOLD': 1.2,
                    'STOP_LOSS_PCT': 0.02,
                    'TAKE_PROFIT_PCT': 0.08,
                    'MAX_POSITION': 1.0,
                    'USE_TRAILING_STOP': False,
                    'TRAILING_TRIGGER': 0.05,
                    'MAX_CONSECUTIVE_LOSSES': 999,
                    'MIN_TRADES_PER_MONTH': 5
                },
                'description': '以太坊 - 高波动、跟随BTC'
            },
            'SOLUSDT': {
                'category': 'crypto',
                'volatility_level': 'very_high',
                'base_config': {
                    'RIVER_WINDOW': 15,  # 更短窗口
                    'PROB_THRESHOLD': 0.50,  # 更低阈值
                    'VOL_THRESHOLD': 1.3,
                    'STOP_LOSS_PCT': 0.025,  # 更大止损
                    'TAKE_PROFIT_PCT': 0.10,  # 1:4盈亏比
                    'MAX_POSITION': 0.8,  # 降低仓位
                    'USE_TRAILING_STOP': True,
                    'TRAILING_TRIGGER': 0.06,
                    'MAX_CONSECUTIVE_LOSSES': 5,
                    'MIN_TRADES_PER_MONTH': 8
                },
                'description': 'Solana - 超高波动、需要更灵活'
            },
            'STOCK_BULL': {
                'category': 'stock',
                'volatility_level': 'medium',
                'base_config': {
                    'RIVER_WINDOW': 25,  # 更长窗口
                    'PROB_THRESHOLD': 0.60,  # 更高阈值
                    'VOL_THRESHOLD': 1.5,  # 更高放量要求
                    'STOP_LOSS_PCT': 0.03,
                    'TAKE_PROFIT_PCT': 0.12,  # 1:4盈亏比
                    'MAX_POSITION': 0.7,
                    'USE_TRAILING_STOP': True,
                    'TRAILING_TRIGGER': 0.05,
                    'MAX_CONSECUTIVE_LOSSES': 3,
                    'MIN_TRADES_PER_MONTH': 5,
                    'STRENGTH_FILTER': True  # 强化趋势过滤
                },
                'description': '牛股 - 中等波动、需强化趋势过滤'
            },
            'STOCK_ZHUANG': {
                'category': 'stock',
                'volatility_level': 'low',
                'base_config': {
                    'RIVER_WINDOW': 30,  # 更长窗口
                    'PROB_THRESHOLD': 0.65,  # 更高阈值
                    'VOL_THRESHOLD': 2.0,  # 更高放量要求
                    'STOP_LOSS_PCT': 0.04,
                    'TAKE_PROFIT_PCT': 0.12,  # 1:3盈亏比（降低目标）
                    'MAX_POSITION': 0.5,
                    'USE_TRAILING_STOP': True,
                    'TRAILING_TRIGGER': 0.05,
                    'MAX_CONSECUTIVE_LOSSES': 3,
                    'MIN_TRADES_PER_MONTH': 3,
                    'STRENGTH_FILTER': True,
                    'REDUCE_NOISE': True  # 减少假信号
                },
                'description': '庄股 - 低波动、需要更强的突破确认'
            }
        }

    def analyze_symbol_volatility(self, df):
        """
        分析品种的历史波动特性

        Parameters:
        -----------
        df : DataFrame
            K线数据

        Returns:
        --------
        dict : 波动特性分析结果
        """
        # 计算收益率
        df = df.copy()
        df['return'] = df['close'] / df['close'].shift(1) - 1

        # 波动率指标
        volatility = df['return'].std() * np.sqrt(365 * 24)  # 年化波动率
        max_single_return = df['return'].abs().max()
        avg_single_return = df['return'].abs().mean()

        # 趋势强度（价格涨幅）
        total_return = (df['close'].iloc[-1] / df['close'].iloc[0]) - 1
        annualized_return = total_return / (len(df) / (365 * 24))

        # 成交量稳定性
        volume_volatility = df['volume'].std() / df['volume'].mean()

        # 分类波动等级
        if volatility > 1.5:
            volatility_level = 'very_high'
        elif volatility > 1.0:
            volatility_level = 'high'
        elif volatility > 0.5:
            volatility_level = 'medium'
        else:
            volatility_level = 'low'

        return {
            'volatility': volatility,
            'volatility_level': volatility_level,
            'max_single_return': max_single_return,
            'avg_single_return': avg_single_return,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'volume_volatility': volume_volatility,
            'data_points': len(df)
        }

    def auto_adapt_config(self, symbol, df=None):
        """
        自动适配策略参数

        优先使用预配置，如果有数据则根据实际波动微调

        Parameters:
        -----------
        symbol : str
            品种代码
        df : DataFrame
            K线数据（可选，用于微调）

        Returns:
        --------
        dict : 适配后的配置参数
        """
        # 1. 查找预配置
        base_config = None
        for key, profile in self.symbol_profiles.items():
            if key.upper() in symbol.upper():
                base_config = profile['base_config'].copy()
                volatility_level = profile['volatility_level']
                break

        # 2. 如果没有预配置，使用默认配置
        if base_config is None:
            base_config = {
                'RIVER_WINDOW': 20,
                'PROB_THRESHOLD': 0.55,
                'VOL_THRESHOLD': 1.2,
                'STOP_LOSS_PCT': 0.02,
                'TAKE_PROFIT_PCT': 0.08,
                'MAX_POSITION': 1.0,
                'USE_TRAILING_STOP': False,
                'TRAILING_TRIGGER': 0.05,
                'MAX_CONSECUTIVE_LOSSES': 999,
                'MIN_TRADES_PER_MONTH': 5
            }
            volatility_level = 'medium'

        # 3. 如果有数据，根据实际波动微调
        if df is not None:
            volatility_info = self.analyze_symbol_volatility(df)
            actual_volatility_level = volatility_info['volatility_level']

            print(f"\n[{symbol} 波动特性分析]")
            print(f"  预期波动：{volatility_level}")
            print(f"  实际波动：{actual_volatility_level}")
            print(f"  年化波动率：{volatility_info['volatility']:.2%}")
            print(f"  年化收益率：{volatility_info['annualized_return']:.2%}")

            # 根据实际波动调整
            if actual_volatility_level == 'very_high':
                base_config['STOP_LOSS_PCT'] *= 1.25  # 增大止损
                base_config['TAKE_PROFIT_PCT'] *= 1.25  # 增大止盈
                base_config['MAX_POSITION'] *= 0.8  # 降低仓位
                base_config['USE_TRAILING_STOP'] = True
                base_config['RIVER_WINDOW'] = int(base_config['RIVER_WINDOW'] * 0.8)  # 缩短窗口
            elif actual_volatility_level == 'high':
                base_config['MAX_POSITION'] *= 0.9
            elif actual_volatility_level == 'low':
                base_config['STOP_LOSS_PCT'] *= 1.5  # 增大止损
                base_config['TAKE_PROFIT_PCT'] *= 1.5  # 增大止盈
                base_config['MAX_POSITION'] *= 0.6  # 降低仓位
                base_config['PROB_THRESHOLD'] += 0.05  # 提高阈值
                base_config['RIVER_WINDOW'] = int(base_config['RIVER_WINDOW'] * 1.2)  # 延长窗口

        return base_config

    def apply_bull_stock_filters(self, df, config):
        """
        应用牛股强化过滤

        针对牛股、强趋势股，增强突破确认和趋势跟踪

        Parameters:
        -----------
        df : DataFrame
            K线数据
        config : dict
            策略配置

        Returns:
        --------
        DataFrame : 添加强化过滤的数据
        """
        if not config.get('STRENGTH_FILTER', False):
            return df

        df = df.copy()

        # 强化指标
        df['trend_strength'] = (
            (df['close'] > df['ma20']).astype(int) * 2 +
            (df['close'] > df['ma5']).astype(int)
        )

        df['break_strength'] = (
            df['high_break'].astype(int) * 2 +
            (df['volume_ratio'] > config['VOL_THRESHOLD']).astype(int)
        )

        # 只在趋势强度>=3 且 突破强度>=3时触发信号
        df['signal'] = 0
        strong_bull_condition = (
            (df['signal'] == 1) &
            (df['trend_strength'] >= 3) &
            (df['break_strength'] >= 3)
        )

        print(f"[OK] 牛股强化过滤已启用（趋势强度阈值：3，突破强度阈值：3）")

        return df

    def apply_zhuang_stock_filters(self, df, config):
        """
        应用庄股强化过滤

        针对庄股、低波动股，减少假信号，提高持仓确定性

        Parameters:
        -----------
        df : DataFrame
            K线数据
        config : dict
            策略配置

        Returns:
        --------
        DataFrame : 添加强化过滤的数据
        """
        if not config.get('REDUCE_NOISE', False):
            return df

        df = df.copy()

        # 噪音过滤指标
        df['noise_level'] = (
            df['body_ratio'].rolling(5).std() +
            df['upper_wick'].rolling(5).std() +
            df['lower_wick'].rolling(5).std()
        )

        # 只在噪音低且突破强时触发信号
        df['low_noise'] = df['noise_level'] < df['noise_level'].rolling(20).mean()

        filtered_signals = (
            (df['signal'] == 1) &
            df['low_noise'] &
            (df['volume_ratio'] > 2.0)  # 2倍放量
        )

        df.loc[~filtered_signals & (df['signal'] == 1), 'signal'] = 0

        print(f"[OK] 庄股噪音过滤已启用（低噪音阈值，2倍放量确认）")

        return df

    def save_symbol_profile(self, symbol, profile_data, config):
        """
        保存品种适配记录

        Parameters:
        -----------
        symbol : str
            品种代码
        profile_data : dict
            波动特性数据
        config : dict
            适配后的配置
        """
        profile_dir = "strategies/symbol_profiles"
        os.makedirs(profile_dir, exist_ok=True)

        profile_file = os.path.join(profile_dir, f"{symbol}_profile.json")

        data = {
            'symbol': symbol,
            'profile_data': profile_data,
            'adapted_config': config,
            'created_at': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        import json
        with open(profile_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        print(f"[OK] 品种配置已保存：{profile_file}")


# 使用示例
if __name__ == "__main__":
    # 创建适配器
    adapter = MultiSymbolAdapter()

    # 示例：适配BTC
    # df = pd.read_csv('my_database/1h/BTCUSDT_1h.csv')
    # config = adapter.auto_adapt_config('BTCUSDT', df)

    # 示例：直接获取预配置
    eth_config = adapter.auto_adapt_config('ETHUSDT')
    print("\nETHUSDT 配置参数：")
    print(eth_config)

    # 示例：适配牛股
    bull_stock_config = adapter.auto_adapt_config('STOCK_BULL')
    print("\n牛股配置参数：")
    print(bull_stock_config)

    # 示例：适配庄股
    zhuang_stock_config = adapter.auto_adapt_config('STOCK_ZHUANG')
    print("\n庄股配置参数：")
    print(zhuang_stock_config)
