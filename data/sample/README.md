# 数据目录说明

## 目录结构

```
data/
├── BTCUSDT_1h.csv          # BTC 1小时K线数据 (已忽略,需手动拉取)
├── fetch_btc_1h.py         # 数据拉取脚本
└── sample/                 # 示例数据 (会提交到Git)
    └── README.md           # 本文件
```

## 数据拉取

### 首次拉取

```bash
# 全量拉取 (默认从2020-03-01开始)
python data/fetch_btc_1h.py

# 使用代理
python data/fetch_btc_1h.py --proxy http://127.0.0.1:7897

# 指定时间范围
python data/fetch_btc_1h.py --start 2024-01-01 --end 2024-12-31
```

### 增量更新

```bash
# 自动识别已有数据,只拉取新数据
python data/fetch_btc_1h.py
```

### 强制重新拉取

```bash
# 忽略已有数据,重新拉取
python data/fetch_btc_1h.py --force
```

## 数据备份

### 创建备份

```bash
# 创建备份并提示手动上传
python scripts/backup_data_to_cloud.py

# 自定义保留天数
python scripts/backup_data_to_cloud.py --keep-days 60
```

### 备份位置

备份文件保存在 `backups/` 目录,命名格式:

```
data_backup_YYYYMMDD.zip
```

例如: `data_backup_20260331.zip`

## .gitignore 配置

以下数据文件已被忽略,不会提交到Git:

- `data/*.csv` - CSV格式数据
- `data/*.parquet` - Parquet格式数据
- `data/*.feather` - Feather格式数据
- `data/*.h5` - HDF5格式数据
- `data/*.zip` - ZIP压缩数据
- `data/*.tar.gz` - TAR.GZ压缩数据

保留的内容:

- `data/sample/` - 示例数据目录
- `data/fetch_*.py` - 数据拉取脚本

## 数据安全建议

1. **定期备份**: 建议每周运行一次备份脚本
2. **云端同步**: 将备份文件上传到云盘 (百度网盘/阿里云盘)
3. **多地备份**: 建议保留至少2个不同位置的备份
4. **定期清理**: 备份脚本会自动清理30天前的旧备份
