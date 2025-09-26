#!/usr/bin/env python3
"""
🧹 ZotLink Nature功能清理工具

根据用户需求清理或禁用Nature相关功能
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse

def option_a_disable_nature(dry_run: bool = False):
    """选项A: 禁用Nature功能但保留代码"""
    
    print("🎯 选项A: 禁用Nature功能，保留代码结构")
    print()
    
    # 处理cookies.json
    user_config_dir = Path.home() / '.zotlink'
    project_root = Path(__file__).parent
    
    # 寻找cookies.json文件
    cookies_paths = [
        user_config_dir / "cookies.json",
        project_root / "cookies.json"
    ]
    
    cookies_file = None
    for path in cookies_paths:
        if path.exists():
            cookies_file = path
            break
    
    if cookies_file:
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 禁用Nature数据库
            if 'databases' in config and 'nature' in config['databases']:
                if not dry_run:
                    # 清空cookies但保留配置结构
                    config['databases']['nature']['cookies'] = ""
                    config['databases']['nature']['status'] = "inactive"
                    config['databases']['nature']['cookie_count'] = 0
                    config['databases']['nature']['last_updated'] = datetime.now().isoformat()
                    
                    # 备份原文件
                    backup_path = cookies_file.with_suffix('.bak')
                    shutil.copy2(cookies_file, backup_path)
                    
                    # 写入修改后的配置
                    with open(cookies_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=2, ensure_ascii=False)
                    
                    print(f"✅ 已禁用Nature数据库配置")
                    print(f"✅ 原文件备份至: {backup_path}")
                else:
                    print(f"[DRY RUN] 将禁用Nature数据库配置在: {cookies_file}")
            else:
                print("⚪ cookies.json中未找到Nature配置")
                
        except Exception as e:
            print(f"❌ 处理cookies.json失败: {e}")
    else:
        print("⚪ 未找到cookies.json文件")
    
    # 清空nature_cookies.txt
    nature_cookies_paths = [
        user_config_dir / "nature_cookies.txt",
        project_root / "nature_cookies.txt"
    ]
    
    for path in nature_cookies_paths:
        if path.exists():
            if not dry_run:
                path.write_text("# Nature cookies已禁用\n")
                print(f"✅ 已清空: {path}")
            else:
                print(f"[DRY RUN] 将清空: {path}")
    
    print()
    print("🎯 选项A完成 - Nature功能已禁用，代码结构保留")
    print("• NatureExtractor类仍存在，但不会处理请求")
    print("• cookies已清空，数据库状态设为inactive")
    print("• 将来需要时可以重新启用")

def option_b_remove_nature(dry_run: bool = False):
    """选项B: 完全删除Nature相关代码和配置"""
    
    print("🗑️  选项B: 完全移除Nature相关代码")
    print()
    
    files_to_remove = [
        'zotlink/extractors/nature_extractor.py',
        'nature_cookies.txt',
        'config/working_cookies.json'  # 这个文件包含Nature cookies
    ]
    
    files_to_modify = [
        'zotlink/extractors/extractor_manager.py',
        'zotlink/extractors/__init__.py',
        'zotlink/zotero_integration.py'
    ]
    
    project_root = Path(__file__).parent
    user_config_dir = Path.home() / '.zotlink'
    
    # 删除文件
    removed_files = []
    for file_path in files_to_remove:
        full_path = project_root / file_path
        user_path = user_config_dir / Path(file_path).name
        
        for path in [full_path, user_path]:
            if path.exists():
                if not dry_run:
                    try:
                        path.unlink()
                        print(f"✅ 删除文件: {path}")
                        removed_files.append(str(path))
                    except Exception as e:
                        print(f"❌ 删除失败 {path}: {e}")
                else:
                    print(f"[DRY RUN] 将删除: {path}")
                    removed_files.append(str(path))
    
    # 修改extractor_manager.py
    extractor_manager_path = project_root / 'zotlink/extractors/extractor_manager.py'
    if extractor_manager_path.exists():
        if not dry_run:
            try:
                content = extractor_manager_path.read_text(encoding='utf-8')
                
                # 删除Nature相关导入和注册
                lines = content.split('\n')
                new_lines = []
                skip_next = False
                
                for line in lines:
                    if 'from .nature_extractor import NatureExtractor' in line:
                        continue
                    elif 'nature_extractor = NatureExtractor' in line:
                        skip_next = True
                        continue
                    elif skip_next and ('self.extractors.append(nature_extractor)' in line or
                                      '注册Nature提取器' in line):
                        continue
                    else:
                        skip_next = False
                        new_lines.append(line)
                
                extractor_manager_path.write_text('\n'.join(new_lines), encoding='utf-8')
                print(f"✅ 修改: {extractor_manager_path}")
            except Exception as e:
                print(f"❌ 修改extractor_manager.py失败: {e}")
        else:
            print(f"[DRY RUN] 将修改: {extractor_manager_path}")
    
    # 修改__init__.py
    init_path = project_root / 'zotlink/extractors/__init__.py'
    if init_path.exists():
        if not dry_run:
            try:
                content = init_path.read_text(encoding='utf-8')
                content = content.replace('from .nature_extractor import NatureExtractor', '')
                content = content.replace(', "NatureExtractor"', '')
                content = content.replace('"NatureExtractor", ', '')
                content = content.replace('"NatureExtractor"', '')
                init_path.write_text(content, encoding='utf-8')
                print(f"✅ 修改: {init_path}")
            except Exception as e:
                print(f"❌ 修改__init__.py失败: {e}")
        else:
            print(f"[DRY RUN] 将修改: {init_path}")
    
    # 处理cookies.json - 删除nature条目
    cookies_paths = [
        user_config_dir / "cookies.json",
        project_root / "cookies.json"
    ]
    
    for cookies_file in cookies_paths:
        if cookies_file.exists():
            if not dry_run:
                try:
                    with open(cookies_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    
                    if 'databases' in config and 'nature' in config['databases']:
                        # 备份
                        backup_path = cookies_file.with_suffix('.bak')
                        shutil.copy2(cookies_file, backup_path)
                        
                        # 删除nature条目
                        del config['databases']['nature']
                        
                        with open(cookies_file, 'w', encoding='utf-8') as f:
                            json.dump(config, f, indent=2, ensure_ascii=False)
                        
                        print(f"✅ 从cookies.json中删除Nature配置: {cookies_file}")
                        print(f"✅ 备份至: {backup_path}")
                        
                except Exception as e:
                    print(f"❌ 修改cookies.json失败 {cookies_file}: {e}")
            else:
                print(f"[DRY RUN] 将从cookies.json中删除Nature配置: {cookies_file}")
    
    print()
    print("🗑️  选项B完成 - Nature相关代码和配置已完全删除")
    print("• NatureExtractor类和相关文件已删除")
    print("• 所有Nature配置已清除")
    print("• 代码库已清理干净")

def main():
    parser = argparse.ArgumentParser(description='ZotLink Nature功能清理工具')
    parser.add_argument('--dry-run', action='store_true', 
                       help='预览模式，不实际执行操作')
    parser.add_argument('--option', choices=['A', 'B'], required=True,
                       help='A: 禁用Nature但保留代码, B: 完全删除Nature相关代码')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧹 ZotLink Nature功能清理工具")
    print("=" * 60)
    print()
    
    if args.option == 'A':
        option_a_disable_nature(args.dry_run)
    elif args.option == 'B':
        option_b_remove_nature(args.dry_run)
    
    if args.dry_run:
        print()
        print("💡 这是预览模式。要实际执行，请移除 --dry-run 参数")

if __name__ == '__main__':
    main()
