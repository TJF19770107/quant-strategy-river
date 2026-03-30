import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score

# ==============================================================================
# 1. 核心参数配置（可根据需要微调）
# ==============================================================================
# RIVER 策略参数
RIVER_WINDOW = 20  # RIVER高低点计算周期
VOL_THRESHOLD = 1.2  # 突破时成交量需大于20日均量的倍数

# 机器学习预测参数
LOOKBACK = 24  # 用过去24小时数据预测下一根
TEST_SIZE = 0.2  # 训练集比例

# 交易过滤阈值
PROB_THRESHOLD = 0.55  # 模型预测概率必须 > 55% 才考虑入场

# ==============================================================================
# 2. 数据加载与预处理
# ==============================================================================
def load_data(file_path):
    """加载CSV数据并转换时间索引"""
    df = pd.read_csv(file_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    return df

# ==============================================================================
# 3. 特征工程：提取历史规律 + RIVER 高低点
# ==============================================================================
def create_features(df):
    """
    构建特征集：
    1. 基础技术指标（均线、RSI、波动率）
    2. RIVER 高低点（你的核心策略）
    3. 目标变量（下一根K线是否上涨）
    """
    df = df.copy()
    
    # --- 基础特征 ---
    df['return'] = df['close'] / df['close'].shift(1) - 1
    df['volume_ma20'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma20']
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    
    # --- RIVER 核心特征 ---
    df['river_high'] = df['high'].rolling(RIVER_WINDOW).max()
    df['river_low'] = df['low'].rolling(RIVER_WINDOW).min()
    # 计算当前价格相对于RIVER高点的突破程度
    df['high_break_ratio'] = df['close'] / df['river_high'].shift(1) - 1
    df['low_break_ratio'] = df['close'] / df['river_low'].shift(1) - 1
    
    # --- 构建目标变量 (Label) ---
    # 1代表上涨，0代表下跌/平盘
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    
    # 移除缺失值
    df = df.dropna()
    return df

# ==============================================================================
# 4. 模型训练：学习历史规律
# ==============================================================================
def train_prediction_model(df):
    """训练随机森林模型，预测下一根K线方向"""
    # 选择特征列（排除不需要的列和目标列）
    feature_cols = ['return', 'volume_ratio', 'ma5', 'ma20',
                    'high_break_ratio', 'low_break_ratio']
    X = df[feature_cols]
    y = df['target']
    
    # 划分训练集与测试集
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, shuffle=False)
    
    # 标准化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 训练模型
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train_scaled, y_train)
    
    # 评估模型
    y_pred = model.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    print(f"[MODEL] 历史预测准确率: {acc:.4f}")
    
    return model, scaler, feature_cols

# ==============================================================================
# 5. 核心交易逻辑：双重验证（模型预测 + RIVER 突破）
# ==============================================================================
def generate_trading_signals(df, model, scaler, feature_cols):
    """
    生成最终信号：
    信号规则 = 模型预测上涨(概率>阈值) AND 价格突破RIVER高点 AND 放量
    """
    df = df.copy()
    df['signal'] = 0  # 0=无信号, 1=买入, -1=卖出
    
    # 1. 预处理特征
    df = create_features(df) # 重新生成特征确保包含最新数据
    df_scaled = scaler.transform(df[feature_cols])
    
    # 2. 模型预测概率
    df['pred_prob_up'] = model.predict_proba(df_scaled)[:, 1]
    
    # 3. 逻辑判断 (从后往前推，避免越界)
    for i in range(RIVER_WINDOW + 1, len(df) - 1):
        # 条件A：模型强烈看多 (概率 > 55%)
        cond_model = df['pred_prob_up'].iloc[i] > PROB_THRESHOLD
        
        # 条件B：突破RIVER高点 (结合你的RIVER策略)
        cond_river_break = df['close'].iloc[i] > df['river_high'].iloc[i-1]
        
        # 条件C：放量 (确认突破有效性)
        cond_volume = df['volume'].iloc[i] > df['volume_ma20'].iloc[i] * VOL_THRESHOLD
        
        if cond_model and cond_river_break and cond_volume:
            df.iloc[i, df.columns.get_loc('signal')] = 1 # 买入信号
            
        # 做空逻辑：模型看跌 + 跌破RIVER低点
        elif df['pred_prob_up'].iloc[i] < (1 - PROB_THRESHOLD):
            if df['close'].iloc[i] < df['river_low'].iloc[i-1] and cond_volume:
                df.iloc[i, df.columns.get_loc('signal')] = -1 # 卖出信号
                
    return df

# ==============================================================================
# 6. 回测执行
# ==============================================================================
def backtest_strategy(df, initial_capital=10000):
    """简单回测：根据信号执行买卖"""
    df = df.copy()
    df['position'] = 0
    df['cash'] = initial_capital
    df['holdings'] = 0.0
    df['total'] = initial_capital
    
    position_size = 0.0
    
    # 使用列表存储结果,避免iloc的类型错误
    positions = []
    cash_list = []
    holdings_list = []
    totals = []
    
    positions.append(0)
    cash_list.append(initial_capital)
    holdings_list.append(0.0)
    totals.append(initial_capital)
    
    for i in range(1, len(df)):
        # 简单逻辑：全仓进出，可根据情况调整仓位
        if df['signal'].iloc[i] == 1 and positions[-1] == 0:
            # 买入
            price = df['close'].iloc[i]
            position_size = cash_list[-1] / price
            positions.append(1)
            holdings_list.append(position_size * price)
            cash_list.append(0.0)
            
        elif df['signal'].iloc[i] == -1 and positions[-1] == 1:
            # 卖出
            price = df['close'].iloc[i]
            cash_list.append(position_size * price)
            positions.append(0)
            holdings_list.append(0.0)
            
        else:
            # 持仓不变
            positions.append(positions[-1])
            holdings_list.append(position_size * df['close'].iloc[i])
            cash_list.append(cash_list[-1])
            
        totals.append(cash_list[-1] + holdings_list[-1])
    
    # 将列表赋值回DataFrame
    df['position'] = positions
    df['cash'] = cash_list
    df['holdings'] = holdings_list
    df['total'] = totals
    
    # 计算收益指标
    final_balance = df['total'].iloc[-1]
    total_return = (final_balance - initial_capital) / initial_capital
    max_drawdown = (df['total'].cummax() - df['total']).max() / df['total'].cummax().max()
    
    # 统计交易次数
    buy_signals = (df['signal'] == 1).sum()
    sell_signals = (df['signal'] == -1).sum()
    
    print("\n" + "="*60)
    print("【回测结果】")
    print("="*60)
    print(f"初始资金: {initial_capital:.2f}")
    print(f"最终资金: {final_balance:.2f}")
    print(f"总收益率: {total_return:.2%}")
    print(f"最大回撤: {max_drawdown:.2%}")
    print(f"买入信号数: {buy_signals}")
    print(f"卖出信号数: {sell_signals}")
    print("="*60)
    
    return df

# ==============================================================================
# 7. 主程序入口
# ==============================================================================
if __name__ == "__main__":
    # 请确保路径与你的文件路径一致
    DATA_PATH = "my_database/1h/BTCUSDT_1h.csv"
    
    print("开始执行 RIVER + 机器学习 融合策略回测...\n")
    
    # 步骤1：加载数据
    raw_data = load_data(DATA_PATH)
    print(f"[DATA] 加载数据完成，共 {len(raw_data)} 根K线\n")
    
    # 步骤2：生成特征集（包含RIVER指标）
    feat_data = create_features(raw_data)
    print(f"[FEATURE] 特征工程完成，特征列: {feat_data.columns.tolist()}\n")
    
    # 步骤3：训练模型
    model, scaler, features = train_prediction_model(feat_data)
    
    # 步骤4：生成融合后的交易信号
    backtest_data = generate_trading_signals(feat_data, model, scaler, features)
    
    # 步骤5：执行回测
    final_result = backtest_strategy(backtest_data)
    
    # 导出交易记录查看详细盈亏
    output_file = "my_database/1h/trading_log_river_ml.csv"
    final_result[['open', 'close', 'signal', 'pred_prob_up', 'river_high', 'river_low']].to_csv(output_file)
    print(f"[OUTPUT] 交易记录已保存到: {output_file}")
    print("\n回测完成！")
