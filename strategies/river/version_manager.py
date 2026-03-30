"""
大道量化系统 - 策略版本管理器
=====================================
功能：
1. 策略版本自动归档（v1.0 → v1.1 → v1.2...）
2. 历史策略对比与回溯
3. 新品种一键复用与适配
4. 参数自动优化与迭代记录

【使用说明】
- 每次策略升级自动归档旧版本
- 支持多品种策略并行管理
- 自动记录优化历史与回测结果
"""

import os
import json
import shutil
from datetime import datetime
import pandas as pd


class StrategyVersionManager:
    """
    策略版本管理器

    管理策略的生命周期：创建 → 测试 → 优化 → 归档 → 升级
    """

    def __init__(self, base_dir="strategies"):
        """
        初始化版本管理器

        Parameters:
        -----------
        base_dir : str
            策略基础目录
        """
        self.base_dir = base_dir
        self.strategies_dir = os.path.join(base_dir, "core")
        self.archives_dir = os.path.join(base_dir, "archive")
        self.results_dir = os.path.join(base_dir, "results")
        self.config_file = os.path.join(base_dir, "strategy_registry.json")

        # 创建目录结构
        self._init_directories()

        # 加载策略注册表
        self.registry = self._load_registry()

    def _init_directories(self):
        """初始化目录结构"""
        for dir_path in [self.base_dir, self.strategies_dir, self.archives_dir,
                         self.results_dir]:
            os.makedirs(dir_path, exist_ok=True)

    def _load_registry(self):
        """加载策略注册表"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'strategies': {},
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def _save_registry(self):
        """保存策略注册表"""
        self.registry['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    def register_strategy(self, name, version, description="", config=None,
                         performance=None, tags=[]):
        """
        注册新策略

        Parameters:
        -----------
        name : str
            策略名称
        version : str
            版本号（如 "v1.0"）
        description : str
            策略描述
        config : dict
            配置参数
        performance : dict
            性能指标
        tags : list
            标签（如 ["BTC", "ML", "高盈亏比"]）
        """
        strategy_key = f"{name}_{version}"

        self.registry['strategies'][strategy_key] = {
            'name': name,
            'version': version,
            'description': description,
            'config': config or {},
            'performance': performance or {},
            'tags': tags,
            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'status': 'active',
            'file_path': os.path.join(self.strategies_dir, f"{name}_{version}.py")
        }

        self._save_registry()
        print(f"[OK] 策略已注册：{name} {version}")

        return strategy_key

    def archive_strategy(self, strategy_key, reason="版本升级"):
        """
        归档旧策略

        Parameters:
        -----------
        strategy_key : str
            策略键（如 "Daodao_v1.0"）
        reason : str
            归档原因
        """
        if strategy_key not in self.registry['strategies']:
            print(f"[ERROR] 策略不存在：{strategy_key}")
            return False

        strategy_info = self.registry['strategies'][strategy_key]
        old_file = strategy_info['file_path']

        # 创建归档文件名
        timestamp = datetime.now().strftime("%Y%m%d")
        archive_file = os.path.join(
            self.archives_dir,
            f"{strategy_info['name']}_{strategy_info['version']}_{timestamp}.py"
        )

        # 复制文件到归档目录
        if os.path.exists(old_file):
            shutil.copy2(old_file, archive_file)

        # 更新注册表
        strategy_info['status'] = 'archived'
        strategy_info['archived_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        strategy_info['archive_reason'] = reason
        strategy_info['archive_path'] = archive_file

        self._save_registry()
        print(f"[OK] 策略已归档：{strategy_key}（原因：{reason}）")

        return True

    def upgrade_strategy(self, name, new_version, changes=""):
        """
        策略升级

        自动归档旧版本，创建新版本

        Parameters:
        -----------
        name : str
            策略名称
        new_version : str
            新版本号（如 "v1.1"）
        changes : str
            变更说明
        """
        # 查找当前激活版本
        current_version = None
        current_key = None

        for key, info in self.registry['strategies'].items():
            if info['name'] == name and info['status'] == 'active':
                current_version = info['version']
                current_key = key
                break

        if not current_version:
            print(f"[ERROR] 未找到激活的策略：{name}")
            return False

        # 归档旧版本
        self.archive_strategy(current_key, f"升级到 {new_version}")

        # 记录升级历史
        upgrade_history_file = os.path.join(
            self.base_dir,
            f"{name}_upgrade_history.json"
        )

        history = []
        if os.path.exists(upgrade_history_file):
            with open(upgrade_history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

        history.append({
            'from_version': current_version,
            'to_version': new_version,
            'changes': changes,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        with open(upgrade_history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

        print(f"[OK] 策略升级准备完成：{name} {current_version} → {new_version}")
        print(f"  变更说明：{changes}")

        return True

    def get_strategy_info(self, strategy_key):
        """
        获取策略信息

        Parameters:
        -----------
        strategy_key : str
            策略键

        Returns:
        --------
        dict : 策略信息
        """
        return self.registry['strategies'].get(strategy_key)

    def list_strategies(self, status='all'):
        """
        列出所有策略

        Parameters:
        -----------
        status : str
            状态过滤：'all', 'active', 'archived'

        Returns:
        --------
        list : 策略列表
        """
        strategies = []

        for key, info in self.registry['strategies'].items():
            if status == 'all' or info['status'] == status:
                strategies.append({
                    'key': key,
                    'name': info['name'],
                    'version': info['version'],
                    'description': info['description'],
                    'tags': info['tags'],
                    'status': info['status'],
                    'created_at': info['created_at'],
                    'performance': info.get('performance', {})
                })

        return strategies

    def print_strategy_list(self, status='all'):
        """打印策略列表"""
        strategies = self.list_strategies(status=status)

        if not strategies:
            print("未找到策略")
            return

        print(f"\n{'='*80}")
        print(f"大道量化系统 - 策略列表（状态：{status}）")
        print(f"{'='*80}\n")

        for s in strategies:
            status_emoji = "[ACTIVE]" if s['status'] == 'active' else "[ARCHIVED]"
            perf = s['performance']
            perf_str = ""

            if perf:
                if 'total_return' in perf:
                    perf_str += f" 收益:{perf['total_return']:.2%}"
                if 'win_rate' in perf:
                    perf_str += f" 胜率:{perf['win_rate']:.2f}%"
                if 'max_drawdown' in perf:
                    perf_str += f" 回撤:{perf['max_drawdown']:.2%}"

            print(f"{status_emoji} {s['name']} {s['version']}")
            print(f"   描述：{s['description']}")
            print(f"   标签：{', '.join(s['tags'])}")
            print(f"   创建：{s['created_at']}")
            if perf_str:
                print(f"   性能：{perf_str}")
            print()

        print(f"{'='*80}\n")

    def save_backtest_result(self, strategy_key, stats, result_df):
        """
        保存回测结果

        Parameters:
        -----------
        strategy_key : str
            策略键
        stats : dict
            统计结果
        result_df : DataFrame
            交易记录
        """
        if strategy_key not in self.registry['strategies']:
            print(f"[ERROR] 策略不存在：{strategy_key}")
            return

        strategy_info = self.registry['strategies'][strategy_key]

        # 更新策略性能
        strategy_info['performance'] = {
            'total_return': stats['total_return'],
            'max_drawdown': stats['max_drawdown'],
            'win_rate': stats['win_rate'],
            'total_trades': stats['total_trades'],
            'actual_rr': stats['actual_rr'],
            'target_rr': stats['target_rr'],
            'sharpe_ratio': stats['sharpe_ratio'],
            'test_date': stats['test_date']
        }

        # 保存详细结果
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = os.path.join(
            self.results_dir,
            f"{strategy_info['name']}",
            strategy_info['version']
        )
        os.makedirs(result_dir, exist_ok=True)

        # 保存JSON统计
        json_file = os.path.join(result_dir, f"stats_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False, default=str)

        # 保存CSV交易记录
        csv_file = os.path.join(result_dir, f"trades_{timestamp}.csv")
        result_df.to_csv(csv_file, index=False)

        # 更新注册表
        self._save_registry()

        print(f"[OK] 回测结果已保存：{strategy_key}")
        print(f"   JSON：{json_file}")
        print(f"   CSV：{csv_file}")

    def compare_strategies(self, strategy_keys):
        """
        对比多个策略

        Parameters:
        -----------
        strategy_keys : list
            策略键列表
        """
        print(f"\n{'='*80}")
        print(f"策略对比分析")
        print(f"{'='*80}\n")

        comparison_data = []

        for key in strategy_keys:
            info = self.registry['strategies'].get(key)
            if not info:
                continue

            perf = info.get('performance', {})
            comparison_data.append({
                '策略': f"{info['name']} {info['version']}",
                '收益率': perf.get('total_return', 0),
                '最大回撤': perf.get('max_drawdown', 0),
                '胜率(%)': perf.get('win_rate', 0),
                '盈亏比': perf.get('actual_rr', 0),
                '交易次数': perf.get('total_trades', 0),
                '夏普比率': perf.get('sharpe_ratio', 0)
            })

        if not comparison_data:
            print("无有效数据可对比")
            return

        df = pd.DataFrame(comparison_data)

        # 格式化输出
        print(df.to_string(index=False))

        # 找出最佳策略（综合评分）
        df['综合评分'] = (
            df['收益率'] * 0.4 +
            (1 - df['最大回撤']) * 0.3 +
            df['胜率(%)'] / 100 * 0.2 +
            df['盈亏比'] / 5 * 0.1
        )

        best_strategy = df.loc[df['综合评分'].idxmax()]
        print(f"\n[BEST] 最佳策略：{best_strategy['策略']}")
        print(f"   综合评分：{best_strategy['综合评分']:.4f}")

        print(f"\n{'='*80}\n")


# 使用示例
if __name__ == "__main__":
    # 创建版本管理器
    vm = StrategyVersionManager()

    # 注册核心策略 v1.0
    vm.register_strategy(
        name="Daodao_RiverML",
        version="v1.0",
        description="RIVER高低点突破 + ML历史规律 + 高盈亏比交易（1:4）",
        config={
            'RIVER_WINDOW': 20,
            'PROB_THRESHOLD': 0.55,
            'VOL_THRESHOLD': 1.2,
            'STOP_LOSS_PCT': 0.02,
            'TAKE_PROFIT_PCT': 0.08,
            'MAX_POSITION': 1.0
        },
        performance={
            'total_return': 13.9492,
            'max_drawdown': 0.6644,
            'win_rate': 25.39,
            'total_trades': 449,
            'actual_rr': 3.51
        },
        tags=["BTC", "RIVER", "ML", "高盈亏比"]
    )

    # 列出所有策略
    vm.print_strategy_list()

    # 模拟策略升级
    # vm.upgrade_strategy("Daodao_RiverML", "v1.1", "优化移动止盈逻辑")
