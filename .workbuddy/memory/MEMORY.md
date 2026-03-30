# RIVER 量化策略系统 - 长期记忆

## 用户信息

- **GitHub 账号**: TJF19770107
- **默认仓库**: quant-strategy-river
- **远程地址**: https://github.com/TJF19770107/quant-strategy-river

## 项目配置

### 项目结构
```
quant-strategy-river/
├── strategies/           # 策略核心代码
│   └── main.py          # RIVER 主策略
├── data/                # 数据文件
│   └── trading_log_river_profit.csv
├── reports/             # 分析报告
│   └── backtest_report.md
├── visualizations/      # 可视化文件
│   └── BTC_1h_profit_kline.html
├── .gitignore
└── README.md
```

### Git 配置
- **用户名**: TJF19770107
- **邮箱**: tjf19770107@users.noreply.github.com
- **分支**: main
- **远程仓库**: origin → https://github.com/TJF19770107/quant-strategy-river.git

## 自动化流程模板

### 策略迭代标准流程 (v3.0+)

**每次策略版本迭代自动执行以下流程:**

1. **本地生成** - 创建/更新策略文件
   - `strategies/main.py` - 策略核心代码
   - `data/trading_log_river_profit.csv` - 盈利交易日志
   - `visualizations/BTC_1h_profit_kline.html` - 交互式盈利 K 线
   - `reports/backtest_report.md` - 回测报告

2. **Git 提交** - 版本控制
   ```bash
   git add .
   git commit -m "feat: optimize RIVER v{VERSION} + {DESCRIPTION}"
   ```

3. **GitHub 推送** - 远程备份
   ```bash
   git push origin main
   ```

4. **云端同步** - 多端访问 (待配置)
   - 需要配置云存储服务 (如腾讯云 COS / 阿里云 OSS)
   - 同步核心策略文件和报告

### 提交信息规范

- `feat:` - 新功能
- `fix:` - Bug 修复
- `optimize:` - 性能优化
- `refactor:` - 代码重构
- `docs:` - 文档更新
- `test:` - 测试相关

## 大道心法 (核心原则)

```
无动无静,无生无灭,无去无来,无是非,无住无往。
直观,屏息注念,一念不生,湛于末时。
了了分明,一尘不染。
```

**交易原则:**
- 应无所住而生其心
- 不预测,只识别;不预判,只跟随
- 心不住于涨跌,不住于多空,不住于盈亏,不住于境相
- 以K线为相,以量价为证,以结构为凭,以历史为镜

## 待办事项

- [x] 初始化本地 Git 仓库
- [x] 创建项目结构
- [x] 保存自动化流程到 MEMORY.md
- [x] 安装 GitHub CLI (v2.89.0)
- [x] GitHub 认证登录 (账号: TJF19770107)
- [x] 关联远程仓库 `quant-strategy-river`
- [x] 推送代码到 GitHub main 分支
- [ ] 配置云端同步服务 (腾讯云 COS / 阿里云 OSS)
- [ ] 导入历史策略文件

## 更新记录

- **2026-03-31 00:18**: ✅ 更新项目名称为「大道量化策略系统」并推送到 GitHub
- **2026-03-31 00:13**: ✅ GitHub 推送成功 - 仓库地址: https://github.com/TJF19770107/quant-strategy-river
- **2026-03-31 00:08**: ✅ GitHub 认证成功 (浏览器方式) - 账号: TJF19770107
- **2026-03-30**: 初始化项目结构,配置 Git 仓库,建立自动化流程模板
