"""
大道量化系统 - 主入口
=====================================
使用说明：
1. 支持回测与实盘适配多品种
2. 自动优化参数，自动保存结果
3. 版本管理，历史对比
4. 一键测试新品种

【使用示例】
# 测试BTC（使用默认配置）
python strategies/main.py --symbol BTCUSDT --data my_database/1h/BTCUSDT_1h.csv

# 测试ETH（自动适配）
python strategies/main.py --symbol ETHUSDT --data my_database/1h/ETHUSDT_1h.csv

# 自动优化参数
python strategies/main.py --symbol BTCUSDT --data my_database/1h/BTCUSDT_1h.csv --optimize

# 查看策略列表
python strategies/main.py --list

# 对比多个策略
python strategies/main.py --compare Daodao_RiverML_v1.0 Daodao_RiverML_v1.1
"""

import argparse
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daodao_core_v1 import DaodaoStrategyV1, run_full_backtest
from version_manager import StrategyVersionManager
from multi_symbol_adapter import MultiSymbolAdapter


def run_strategy(args):
    """运行策略回测"""
    print(f"\n{'='*80}")
    print("大道量化系统 - 核心策略回测")
    print(f"{'='*80}\n")

    # 创建适配器
    adapter = MultiSymbolAdapter()

    # 加载数据（如果提供了数据文件）
    import pandas as pd
    df = None
    if args.data and os.path.exists(args.data):
        df = pd.read_csv(args.data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)

    # 自动适配配置
    config = adapter.auto_adapt_config(args.symbol, df)

    print(f"\n【策略配置】")
    for key, value in config.items():
        print(f"  {key}: {value}")

    # 创建策略
    strategy = DaodaoStrategyV1(
        symbol=args.symbol,
        timeframe=args.timeframe,
        config=config
    )

    # 如果有数据文件，直接回测
    if args.data:
        result = run_full_backtest(
            data_file=args.data,
            symbol=args.symbol,
            timeframe=args.timeframe,
            initial_capital=args.initial_capital,
            optimize=args.optimize,
            save=True
        )

        # 注册策略到版本管理器
        vm = StrategyVersionManager()

        # 直接使用回测结果
        df = pd.read_csv(args.data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df = strategy.create_features(df)
        df = strategy.train_simple_model(df)
        df = strategy.generate_signals(df)
        backtest_result = strategy.backtest(df, args.initial_capital)

        strategy_key = vm.register_strategy(
            name="Daodao_RiverML",
            version="v1.0",
            description=f"RIVER高低点 + ML历史规律 + 高盈亏比交易（{args.symbol}）",
            config=config,
            performance=backtest_result['stats'],
            tags=[args.symbol, "RIVER", "ML", "高盈亏比"]
        )

        # 保存回测结果
        vm.save_backtest_result(strategy_key, backtest_result['stats'], backtest_result['result_df'])

    else:
        print(f"\n错误：数据文件不存在 - {args.data}")


def list_strategies(args):
    """列出所有策略"""
    vm = StrategyVersionManager()
    vm.print_strategy_list(status=args.status)


def compare_strategies(args):
    """对比策略"""
    vm = StrategyVersionManager()
    vm.compare_strategies(args.strategies)


def new_symbol(args):
    """测试新品种"""
    print(f"\n{'='*80}")
    print(f"大道量化系统 - 新品种测试：{args.symbol}")
    print(f"{'='*80}\n")

    if not args.data:
        print("错误：请提供数据文件路径")
        return

    # 创建适配器
    adapter = MultiSymbolAdapter()

    # 分析波动特性
    import pandas as pd
    df = pd.read_csv(args.data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)

    volatility_info = adapter.analyze_symbol_volatility(df)

    print(f"\n【波动特性】")
    for key, value in volatility_info.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")

    # 自动适配配置
    config = adapter.auto_adapt_config(args.symbol, df)

    # 保存品种配置
    adapter.save_symbol_profile(args.symbol, volatility_info, config)

    # 运行回测
    run_full_backtest(
        data_file=args.data,
        symbol=args.symbol,
        timeframe=args.timeframe,
        initial_capital=args.initial_capital,
        optimize=args.optimize,
        save=True
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="大道量化系统 - 核心交易策略",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  # 测试BTC
  python main.py --run --symbol BTCUSDT --data ../my_database/1h/BTCUSDT_1h.csv

  # 自动优化
  python main.py --run --symbol BTCUSDT --data ../my_database/1h/BTCUSDT_1h.csv --optimize

  # 测试新品种
  python main.py --new --symbol ETHUSDT --data ../my_database/1h/ETHUSDT_1h.csv

  # 列出策略
  python main.py --list

  # 对比策略
  python main.py --compare Daodao_RiverML_v1.0 Daodao_RiverML_v1.1
        """
    )

    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # run 命令
    run_parser = subparsers.add_parser('run', help='运行策略回测')
    run_parser.add_argument('--symbol', type=str, required=True, help='交易品种（如 BTCUSDT）')
    run_parser.add_argument('--data', type=str, required=True, help='数据文件路径')
    run_parser.add_argument('--timeframe', type=str, default='1h', help='时间周期（默认：1h）')
    run_parser.add_argument('--initial-capital', type=float, default=10000, help='初始资金（默认：10000）')
    run_parser.add_argument('--optimize', action='store_true', help='自动优化参数')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出所有策略')
    list_parser.add_argument('--status', type=str, default='all', choices=['all', 'active', 'archived'],
                             help='策略状态（默认：all）')

    # compare 命令
    compare_parser = subparsers.add_parser('compare', help='对比策略')
    compare_parser.add_argument('strategies', nargs='+', help='策略键（如 Daodao_RiverML_v1.0）')

    # new 命令
    new_parser = subparsers.add_parser('new', help='测试新品种')
    new_parser.add_argument('--symbol', type=str, required=True, help='新品种代码')
    new_parser.add_argument('--data', type=str, help='数据文件路径')
    new_parser.add_argument('--timeframe', type=str, default='1h', help='时间周期（默认：1h）')
    new_parser.add_argument('--initial-capital', type=float, default=10000, help='初始资金（默认：10000）')
    new_parser.add_argument('--optimize', action='store_true', help='自动优化参数')

    args = parser.parse_args()

    # 执行命令
    if args.command == 'run':
        run_strategy(args)
    elif args.command == 'list':
        list_strategies(args)
    elif args.command == 'compare':
        compare_strategies(args)
    elif args.command == 'new':
        new_symbol(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
