"""
大道龙头币缠论分析模块
深度融合：笔、线段、中枢、背驰、买卖点
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional


class ChanTheoryAnalyzer:
    """缠论分析器"""
    
    def __init__(self, df: pd.DataFrame):
        """
        初始化缠论分析器
        df需要包含: datetime, open, high, low, close, volume
        """
        self.df = df.copy()
        self.df = self.df.sort_values('datetime').reset_index(drop=True)
        self.fenbi = []      # 分笔
        self.xianduan = []   # 线段
        self.zhongshu = []   # 中枢
        self.beichi = []     # 背驰
        self.maimian = {}    # 买卖点
        
    def find_extremes(self, min_bars: int, key: str = 'high') -> List[Dict]:
        """
        寻找极值点（分笔基础）
        min_bars: 前后最少K线数
        key: 'high' 或 'low'
        """
        extremes = []
        n = len(self.df)
        
        for i in range(min_bars, n - min_bars):
            if key == 'high':
                if self.df[key].iloc[i] == self.df[key].iloc[i-min_bars:i+min_bars].max():
                    extremes.append({
                        'index': i,
                        'datetime': self.df['datetime'].iloc[i],
                        'price': self.df[key].iloc[i],
                        'type': 'high'
                    })
            else:
                if self.df[key].iloc[i] == self.df[key].iloc[i-min_bars:i+min_bars].min():
                    extremes.append({
                        'index': i,
                        'datetime': self.df['datetime'].iloc[i],
                        'price': self.df[key].iloc[i],
                        'type': 'low'
                    })
        return extremes
    
    def build_fenbi(self, min_bars: int = 5) -> List[Dict]:
        """
        构建分笔（笔）
        条件：相邻的顶和底，且顶底之间至少有min_bars根K线
        """
        highs = self.find_extremes(min_bars, 'high')
        lows = self.find_extremes(min_bars, 'low')
        
        # 合并极值点并按时间排序
        all_extremes = sorted(highs + lows, key=lambda x: x['index'])
        
        fenbi = []
        i = 0
        while i < len(all_extremes) - 1:
            current = all_extremes[i]
            next_one = all_extremes[i + 1]
            
            # 必须是顶底交替
            if current['type'] != next_one['type']:
                bars_between = next_one['index'] - current['index']
                if bars_between >= min_bars:
                    fenbi.append({
                        'start': current,
                        'end': next_one,
                        'type': 'up' if current['type'] == 'low' else 'down',
                        'bars': bars_between,
                        'range': abs(next_one['price'] - current['price']),
                        'range_pct': abs(next_one['price'] - current['price']) / current['price'] * 100
                    })
            i += 1
        
        self.fenbi = fenbi
        return fenbi
    
    def build_xianduan(self, min_fenbi: int = 3) -> List[Dict]:
        """
        构建线段
        条件：连续3笔同向运动，且后一笔幅度大于等于前一笔
        """
        if not self.fenbi:
            self.build_fenbi(5)
        
        xianduan = []
        i = 0
        
        while i < len(self.fenbi) - 2:
            # 需要至少3笔来确认线段
            b1 = self.fenbi[i]
            b2 = self.fenbi[i+1]
            b3 = self.fenbi[i+2]
            
            # 3笔同向
            if b1['type'] == b2['type'] == b3['type']:
                # 线段破坏：后一笔幅度大于等于前一笔
                if b3['range'] >= b1['range']:
                    # 确认线段
                    xianduan.append({
                        'start': b1['start'],
                        'end': b3['end'],
                        'type': b1['type'],
                        'fenbi_count': 3,
                        'total_range': abs(b3['end']['price'] - b1['start']['price']),
                        'total_range_pct': abs(b3['end']['price'] - b1['start']['price']) / b1['start']['price'] * 100
                    })
                    i += 3
                    continue
            i += 1
        
        self.xianduan = xianduan
        return xianduan
    
    def build_zhongshu(self, min_xianduan: int = 2) -> List[Dict]:
        """
        构建中枢
        条件：至少3段重叠区域构成
        """
        if not self.xianduan:
            self.build_xianduan(3)
        
        zhongshu = []
        i = 0
        
        while i < len(self.xianduan) - 2:
            x1 = self.xianduan[i]
            x2 = self.xianduan[i+1]
            x3 = self.xianduan[i+2]
            
            # 3段重叠
            ranges = []
            for x in [x1, x2, x3]:
                if x['type'] == 'up':
                    ranges.append((x['start']['price'], x['end']['price']))
                else:
                    ranges.append((x['end']['price'], x['start']['price']))
            
            # 计算重叠区域
            overlap_high = min([r[1] for r in ranges])
            overlap_low = max([r[0] for r in ranges])
            
            if overlap_low < overlap_high:  # 有重叠
                zhongshu.append({
                    'start': x1['start'],
                    'end': x3['end'],
                    'type': x1['type'],
                    'range_high': overlap_high,
                    'range_low': overlap_low,
                    'range': overlap_high - overlap_low,
                    'xianduan_count': 3
                })
                i += 3
                continue
            i += 1
        
        self.zhongshu = zhongshu
        return zhongshu
    
    def find_beichi(self) -> List[Dict]:
        """
        识别背驰
        条件：创新高/新低，但力度（MACD/rsi/量能）减弱
        """
        if not self.fenbi:
            self.build_fenbi()
        
        # 计算MACD力度
        self.df['MACD'] = self.df['close'].ewm(span=12).mean() - self.df['close'].ewm(span=26).mean()
        self.df['Signal'] = self.df['MACD'].ewm(span=9).mean()
        
        beichi = []
        
        # 寻找最近的高低点
        for i in range(len(self.fenbi) - 1):
            b1 = self.fenbi[i]
            b2 = self.fenbi[i+1]
            
            # 获取两笔的MACD面积（简化：用收盘价差）
            if b1['type'] == 'up' and b2['type'] == 'down':
                # 检查顶背驰
                if b2['end']['price'] > b1['end']['price']:  # 创新高
                    # 比较力度
                    idx1_start = b1['start']['index']
                    idx1_end = b1['end']['index']
                    idx2_end = b2['end']['index']
                    
                    macd1 = self.df['MACD'].iloc[idx1_start:idx1_end].sum()
                    macd2 = self.df['MACD'].iloc[idx1_end:idx2_end].sum()
                    
                    if macd2 < macd1:  # 力度减弱
                        beichi.append({
                            'type': 'top_beichi',
                            'fenbi': [b1, b2],
                            'strength_decline': (macd1 - macd2) / abs(macd1) * 100 if macd1 != 0 else 0
                        })
        
        self.beichi = beichi
        return beichi
    
    def find_maimian(self) -> Dict:
        """
        识别买卖点
        - 一买：背驰后的最低点
        - 二买：次低点
        - 三买：突破中枢后的回踩不破
        - 一卖：背驰后的最高点
        - 二卖：次高点  
        - 三卖：跌破中枢后的回抽不破
        """
        if not self.fenbi:
            self.build_fenbi()
        if not self.zhongshu:
            self.build_zhongshu()
        
        maimian = {
            '一买': [],
            '二买': [],
            '三买': [],
            '一卖': [],
            '二卖': [],
            '三卖': []
        }
        
        # 简化逻辑：寻找极值点
        # 一买：连续下跌后出现底背驰的最低点
        recent_fenbi = self.fenbi[-5:] if len(self.fenbi) >= 5 else self.fenbi
        
        for i, fb in enumerate(recent_fenbi):
            if fb['type'] == 'down' and i > 0:
                # 检查是否背驰（用笔的幅度比较）
                prev_up = None
                for j in range(i-1, -1, -1):
                    if recent_fenbi[j]['type'] == 'up':
                        prev_up = recent_fenbi[j]
                        break
                
                if prev_up and fb['range'] < prev_up['range'] * 0.8:  # 背驰
                    maimian['一买'].append({
                        'datetime': fb['end']['datetime'],
                        'price': fb['end']['price'],
                        'beichi_ratio': fb['range'] / prev_up['range']
                    })
        
        # 二买：次低点
        if maimian['一买']:
            lowest = maimian['一买'][0]
            for m in maimian['一买'][1:]:
                if m['price'] < lowest['price']:
                    lowest = m
            maimian['二买'].append(lowest)
        
        # 一卖：相反逻辑
        for i, fb in enumerate(recent_fenbi):
            if fb['type'] == 'up' and i > 0:
                prev_down = None
                for j in range(i-1, -1, -1):
                    if recent_fenbi[j]['type'] == 'down':
                        prev_down = recent_fenbi[j]
                        break
                
                if prev_down and fb['range'] < prev_down['range'] * 0.8:
                    maimian['一卖'].append({
                        'datetime': fb['end']['datetime'],
                        'price': fb['end']['price'],
                        'beichi_ratio': fb['range'] / prev_down['range']
                    })
        
        self.maimian = maimian
        return maimian
    
    def full_analysis(self) -> Dict:
        """
        完整缠论分析
        """
        self.build_fenbi()
        self.build_xianduan()
        self.build_zhongshu()
        self.find_beichi()
        self.find_maimian()
        
        return {
            'fenbi': self.fenbi,
            'xianduan': self.xianduan,
            'zhongshu': self.zhongshu,
            'beichi': self.beichi,
            'maimian': self.maimian,
            'summary': self.get_summary()
        }
    
    def get_summary(self) -> Dict:
        """获取分析摘要"""
        if not self.fenbi:
            return {}
        
        # 最新趋势
        latest_fenbi = self.fenbi[-1] if self.fenbi else None
        trend = latest_fenbi['type'] if latest_fenbi else 'unknown'
        
        # 当前价格位置
        current_price = self.df['close'].iloc[-1]
        
        # 最近的支撑阻力
        supports = []
        resistances = []
        
        for fb in self.fenbi[-5:]:
            if fb['type'] == 'down':
                supports.append(fb['end']['price'])
            else:
                resistances.append(fb['end']['price'])
        
        return {
            'current_price': current_price,
            'trend': trend,
            'fenbi_count': len(self.fenbi),
            'xianduan_count': len(self.xianduan),
            'zhongshu_count': len(self.zhongshu),
            'nearest_support': min(supports) if supports else None,
            'nearest_resistance': max(resistances) if resistances else None,
            'last_beichi': self.beichi[-1] if self.beichi else None,
            'active_signals': self.maimian
        }


def analyze_symbol(symbol: str, df: pd.DataFrame) -> Dict:
    """
    快速分析单个币种
    """
    analyzer = ChanTheoryAnalyzer(df)
    return analyzer.full_analysis()


if __name__ == '__main__':
    # 测试
    df = pd.read_csv('data/RIVERUSDT_1h.csv')
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    result = analyze_symbol('RIVERUSDT', df)
    print(result['summary'])
