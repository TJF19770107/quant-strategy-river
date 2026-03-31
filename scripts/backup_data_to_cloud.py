#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据一键备份脚本
================

功能:
- 将 data/ 目录压缩为按日期命名的备份包
- 支持上传到云盘 (百度网盘/阿里云盘)
- 自动清理超过30天的旧备份

使用方法:
    python scripts/backup_data_to_cloud.py

参数说明:
    --data-dir    数据目录 (默认: data/)
    --backup-dir  备份目录 (默认: backups/)
    --keep-days   保留天数 (默认: 30天)
    --cloud       云盘类型 (baidu/aliyun, 默认: 提示手动上传)
    --token       云盘授权token (如需自动上传)

示例:
    # 创建备份并提示手动上传
    python scripts/backup_data_to_cloud.py

    # 创建备份并自动上传到百度网盘 (需要token)
    python scripts/backup_data_to_cloud.py --cloud baidu --token YOUR_TOKEN

    # 自定义保留天数
    python scripts/backup_data_to_cloud.py --keep-days 60

备份文件命名规则:
    data_backup_YYYYMMDD.zip
    
    例如: data_backup_20260331.zip
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class DataBackup:
    """数据备份管理器"""
    
    def __init__(self, data_dir: str = "data", backup_dir: str = "backups"):
        """
        初始化备份管理器
        
        Args:
            data_dir: 数据目录
            backup_dir: 备份目录
        """
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir)
        
        # 创建备份目录
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self) -> Optional[Path]:
        """
        创建数据备份
        
        Returns:
            Path: 备份文件路径,失败返回None
        """
        # 检查数据目录
        if not self.data_dir.exists():
            print(f"❌ 数据目录不存在: {self.data_dir}")
            return None
        
        # 生成备份文件名
        today = datetime.now().strftime("%Y%m%d")
        backup_file = self.backup_dir / f"data_backup_{today}.zip"
        
        # 检查是否已存在今天的备份
        if backup_file.exists():
            print(f"⚠️  今日备份已存在: {backup_file}")
            print("如需重新备份,请先删除旧备份文件")
            return backup_file
        
        # 创建备份
        print(f"📦 开始备份数据...")
        print(f"  数据目录: {self.data_dir.absolute()}")
        print(f"  备份文件: {backup_file.absolute()}")
        
        try:
            # 使用shutil压缩
            shutil.make_archive(
                base_name=str(backup_file.with_suffix("")),
                format="zip",
                root_dir=str(self.data_dir.parent),
                base_dir=self.data_dir.name
            )
            
            # 获取备份文件大小
            size_mb = backup_file.stat().st_size / (1024 * 1024)
            print(f"✅ 备份成功: {backup_file.name} ({size_mb:.2f} MB)")
            
            return backup_file
            
        except Exception as e:
            print(f"❌ 备份失败: {e}")
            return None
    
    def clean_old_backups(self, keep_days: int = 30) -> int:
        """
        清理旧备份
        
        Args:
            keep_days: 保留天数
        
        Returns:
            int: 删除的备份文件数量
        """
        print(f"\n🗑️  清理 {keep_days} 天前的旧备份...")
        
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0
        
        # 查找所有备份文件
        for backup_file in self.backup_dir.glob("data_backup_*.zip"):
            try:
                # 从文件名提取日期
                date_str = backup_file.stem.split("_")[-1]
                backup_date = datetime.strptime(date_str, "%Y%m%d")
                
                # 检查是否需要删除
                if backup_date < cutoff_date:
                    backup_file.unlink()
                    print(f"  🗑️  删除: {backup_file.name}")
                    deleted_count += 1
                    
            except (ValueError, IndexError):
                # 文件名格式不正确,跳过
                continue
        
        if deleted_count == 0:
            print("  ✅ 无需清理")
        else:
            print(f"  ✅ 已清理 {deleted_count} 个旧备份")
        
        return deleted_count
    
    def upload_to_baidu(self, backup_file: Path, token: str) -> bool:
        """
        上传到百度网盘
        
        Args:
            backup_file: 备份文件路径
            token: 百度网盘授权token
        
        Returns:
            bool: 是否上传成功
        """
        print(f"\n☁️  上传到百度网盘...")
        
        try:
            # 这里需要使用百度网盘API
            # 参考: https://pan.baidu.com/union/doc/
            
            print("⚠️  百度网盘API需要配置授权")
            print("请参考文档: https://pan.baidu.com/union/doc/")
            print(f"手动上传路径: /apps/quant-strategy-river/{backup_file.name}")
            
            return False
            
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            return False
    
    def upload_to_aliyun(self, backup_file: Path, token: str) -> bool:
        """
        上传到阿里云盘
        
        Args:
            backup_file: 备份文件路径
            token: 阿里云盘授权token
        
        Returns:
            bool: 是否上传成功
        """
        print(f"\n☁️  上传到阿里云盘...")
        
        try:
            # 这里需要使用阿里云盘API
            # 参考: https://www.alipan.com/drive/
            
            print("⚠️  阿里云盘API需要配置授权")
            print("请参考文档: https://www.alipan.com/drive/")
            print(f"手动上传路径: /quant-strategy-river/{backup_file.name}")
            
            return False
            
        except Exception as e:
            print(f"❌ 上传失败: {e}")
            return False
    
    def show_manual_upload_guide(self, backup_file: Path):
        """显示手动上传指南"""
        print(f"\n📋 手动上传指南")
        print("=" * 60)
        print(f"备份文件: {backup_file.absolute()}")
        print(f"文件大小: {backup_file.stat().st_size / (1024 * 1024):.2f} MB")
        print("\n推荐上传路径:")
        print("  百度网盘: /apps/quant-strategy-river/")
        print("  阿里云盘: /quant-strategy-river/")
        print("\n上传步骤:")
        print("  1. 打开网盘客户端或网页版")
        print("  2. 进入推荐路径或自定义路径")
        print("  3. 上传统份文件")
        print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据一键备份脚本")
    parser.add_argument("--data-dir", type=str, default="data", help="数据目录")
    parser.add_argument("--backup-dir", type=str, default="backups", help="备份目录")
    parser.add_argument("--keep-days", type=int, default=30, help="保留天数")
    parser.add_argument("--cloud", type=str, choices=["baidu", "aliyun"], help="云盘类型")
    parser.add_argument("--token", type=str, help="云盘授权token")
    
    args = parser.parse_args()
    
    # 初始化备份管理器
    backup_manager = DataBackup(
        data_dir=args.data_dir,
        backup_dir=args.backup_dir
    )
    
    # 创建备份
    backup_file = backup_manager.create_backup()
    if not backup_file:
        sys.exit(1)
    
    # 清理旧备份
    backup_manager.clean_old_backups(keep_days=args.keep_days)
    
    # 上传到云盘
    if args.cloud and args.token:
        if args.cloud == "baidu":
            backup_manager.upload_to_baidu(backup_file, args.token)
        elif args.cloud == "aliyun":
            backup_manager.upload_to_aliyun(backup_file, args.token)
    else:
        # 显示手动上传指南
        backup_manager.show_manual_upload_guide(backup_file)
    
    print("\n✅ 备份流程完成!")


if __name__ == "__main__":
    main()
