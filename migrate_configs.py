#!/usr/bin/env python3
"""
🔧 ZotLink 配置文件迁移工具

将cookies等配置文件从项目根目录迁移到 ~/.zotlink/ 目录
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse

def migrate_config_files(dry_run: bool = False):
    """迁移配置文件到用户配置目录"""
    
    # 源目录和目标目录
    project_root = Path(__file__).parent
    user_config_dir = Path.home() / '.zotlink'
    
    print(f"🔧 ZotLink 配置文件迁移工具")
    print(f"源目录: {project_root}")
    print(f"目标目录: {user_config_dir}")
    print()
    
    # 创建用户配置目录
    if not dry_run:
        user_config_dir.mkdir(exist_ok=True)
        print(f"✅ 创建用户配置目录: {user_config_dir}")
    else:
        print(f"[DRY RUN] 将创建用户配置目录: {user_config_dir}")
    
    # 需要迁移的文件列表
    files_to_migrate = [
        'cookies.json',
        'nature_cookies.txt',
    ]
    
    # 可选的配置文件（如果存在）
    optional_files = [
        'config/working_cookies.json',
        'saved_cookies.json',
        '.cookies.json'
    ]
    
    migrated_files = []
    skipped_files = []
    
    # 迁移主要配置文件
    for filename in files_to_migrate:
        source_path = project_root / filename
        target_path = user_config_dir / filename
        
        if source_path.exists():
            if target_path.exists():
                print(f"⚠️  目标文件已存在，跳过: {filename}")
                skipped_files.append(filename)
            else:
                if not dry_run:
                    # 复制文件
                    if filename == 'cookies.json':
                        # 对于cookies.json，我们需要确保格式正确
                        try:
                            with open(source_path, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                            
                            # 添加迁移信息
                            if 'metadata' not in config:
                                config['metadata'] = {}
                            config['metadata']['migrated_at'] = datetime.now().isoformat()
                            config['metadata']['migrated_from'] = str(source_path)
                            
                            with open(target_path, 'w', encoding='utf-8') as f:
                                json.dump(config, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            print(f"❌ 迁移 {filename} 时出错: {e}")
                            continue
                    else:
                        shutil.copy2(source_path, target_path)
                    
                    print(f"✅ 迁移完成: {filename}")
                    migrated_files.append(filename)
                else:
                    print(f"[DRY RUN] 将迁移: {filename}")
                    migrated_files.append(filename)
        else:
            print(f"⚪ 源文件不存在，跳过: {filename}")
    
    # 迁移可选配置文件
    for filepath in optional_files:
        source_path = project_root / filepath
        filename = Path(filepath).name
        target_path = user_config_dir / filename
        
        if source_path.exists():
            if target_path.exists():
                print(f"⚠️  目标文件已存在，跳过: {filepath}")
                skipped_files.append(filepath)
            else:
                if not dry_run:
                    # 确保目标目录存在
                    target_path.parent.mkdir(exist_ok=True)
                    shutil.copy2(source_path, target_path)
                    print(f"✅ 迁移完成: {filepath}")
                    migrated_files.append(filepath)
                else:
                    print(f"[DRY RUN] 将迁移: {filepath}")
                    migrated_files.append(filepath)
    
    # 总结
    print()
    print("📊 迁移总结:")
    print(f"✅ 成功迁移: {len(migrated_files)} 个文件")
    if migrated_files:
        for f in migrated_files:
            print(f"   • {f}")
    
    if skipped_files:
        print(f"⚠️  跳过文件: {len(skipped_files)} 个")
        for f in skipped_files:
            print(f"   • {f}")
    
    # 后续步骤提示
    if migrated_files and not dry_run:
        print()
        print("🎯 后续步骤:")
        print("1. 重新启动 ZotLink 服务器以使用新的配置文件位置")
        print("2. 验证功能正常工作后，可以删除项目根目录中的原始配置文件")
        print("3. 如果遇到问题，可以将文件复制回项目根目录")
        
        # 创建备份脚本
        backup_script_path = user_config_dir / 'restore_configs.sh'
        with open(backup_script_path, 'w') as f:
            f.write('#!/bin/bash\n')
            f.write('# ZotLink 配置文件恢复脚本\n')
            f.write('# 如果迁移后出现问题，运行此脚本恢复到项目根目录\n\n')
            
            for filename in migrated_files:
                if filename in files_to_migrate:
                    source = user_config_dir / filename
                    target = project_root / filename
                    f.write(f'cp "{source}" "{target}"\n')
        
        backup_script_path.chmod(0o755)
        print(f"📝 备份恢复脚本已创建: {backup_script_path}")

def cleanup_old_files(dry_run: bool = False):
    """清理项目根目录中的旧配置文件"""
    
    project_root = Path(__file__).parent
    user_config_dir = Path.home() / '.zotlink'
    
    print(f"🧹 清理项目根目录中的旧配置文件")
    print()
    
    files_to_clean = [
        'nature_cookies.txt',  # 这个文件是空的，可以安全删除
        'config/working_cookies.json'  # 工作配置文件
    ]
    
    # 检查用户配置目录中是否有对应文件
    for filename in files_to_clean:
        source_path = project_root / filename
        target_path = user_config_dir / Path(filename).name
        
        if source_path.exists():
            if target_path.exists() or filename == 'nature_cookies.txt':  # nature_cookies.txt是空的
                if not dry_run:
                    try:
                        source_path.unlink()
                        print(f"✅ 删除旧文件: {filename}")
                    except Exception as e:
                        print(f"❌ 删除失败 {filename}: {e}")
                else:
                    print(f"[DRY RUN] 将删除: {filename}")
            else:
                print(f"⚠️  跳过删除 {filename}: 用户配置目录中没有对应文件")

def main():
    parser = argparse.ArgumentParser(description='ZotLink 配置文件迁移工具')
    parser.add_argument('--dry-run', action='store_true', 
                       help='预览模式，不实际执行操作')
    parser.add_argument('--cleanup', action='store_true',
                       help='清理项目根目录中的旧配置文件')
    
    args = parser.parse_args()
    
    if args.cleanup:
        cleanup_old_files(args.dry_run)
    else:
        migrate_config_files(args.dry_run)

if __name__ == '__main__':
    main()
