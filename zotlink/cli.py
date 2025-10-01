#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZotLink CLI - 命令行工具入口
提供配置生成、状态检查等实用功能
"""

import argparse
import json
import sys
import os
import shutil
from pathlib import Path
from typing import Optional, Dict


def validate_zotero_path(zotero_root: str) -> bool:
    """
    验证Zotero路径是否有效
    
    Args:
        zotero_root: Zotero根目录路径
        
    Returns:
        True if valid, False otherwise
    """
    if not zotero_root:
        print("❌ 错误：未提供Zotero路径", file=sys.stderr)
        return False
    
    root_path = Path(zotero_root).expanduser().resolve()
    
    # 检查路径是否存在
    if not root_path.exists():
        print(f"❌ 错误：路径不存在: {root_path}", file=sys.stderr)
        return False
    
    if not root_path.is_dir():
        print(f"❌ 错误：不是有效的目录: {root_path}", file=sys.stderr)
        return False
    
    # 检查关键文件/目录
    db_file = root_path / "zotero.sqlite"
    storage_dir = root_path / "storage"
    
    if not db_file.exists():
        print(f"❌ 错误：未找到 zotero.sqlite 文件", file=sys.stderr)
        print(f"💡 提示：请确认 {root_path} 是否为Zotero数据目录", file=sys.stderr)
        return False
    
    if not storage_dir.exists():
        print(f"⚠️  警告：未找到 storage 目录（可能是新安装）", file=sys.stderr)
    
    print(f"✅ Zotero路径验证成功: {root_path}")
    return True


def detect_zotero_path() -> Optional[str]:
    """
    自动检测Zotero路径
    
    Returns:
        检测到的路径，或None
    """
    # 常见的Zotero路径
    candidates = []
    
    if sys.platform == "darwin":  # macOS
        candidates = [
            Path.home() / "Zotero",
            Path.home() / "Documents" / "Zotero",
        ]
    elif sys.platform == "win32":  # Windows
        if "APPDATA" in os.environ:
            candidates.append(Path(os.environ["APPDATA"]) / "Zotero")
        candidates.append(Path.home() / "Zotero")
    else:  # Linux
        candidates = [
            Path.home() / "Zotero",
            Path.home() / ".zotero",
        ]
    
    for candidate in candidates:
        if candidate.exists() and (candidate / "zotero.sqlite").exists():
            return str(candidate)
    
    return None


def detect_zotlink_path() -> str:
    """
    检测zotlink命令的完整路径
    
    Returns:
        zotlink命令路径
    """
    # 首先尝试which/where查找
    zotlink_path = shutil.which("zotlink")
    
    if zotlink_path:
        return zotlink_path
    
    # 如果找不到，使用Python解释器路径
    # 这在虚拟环境中很有用
    python_dir = Path(sys.executable).parent
    zotlink_in_venv = python_dir / "zotlink"
    
    if zotlink_in_venv.exists():
        return str(zotlink_in_venv)
    
    # 默认返回相对命令名
    return "zotlink"


def generate_mcp_config(zotlink_cmd: str, zotero_root: str) -> Dict:
    """
    生成MCP服务器配置
    
    Args:
        zotlink_cmd: zotlink命令路径
        zotero_root: Zotero根目录
        
    Returns:
        配置字典
    """
    return {
        "mcpServers": {
            "zotlink": {
                "command": zotlink_cmd,
                "args": [],
                "env": {
                    "ZOTLINK_ZOTERO_ROOT": zotero_root
                }
            }
        }
    }


def cmd_init(args):
    """处理 zotlink init 命令"""
    zotero_root = args.zotero_root
    
    # 如果未提供路径，尝试自动检测
    if not zotero_root:
        print("🔍 未指定路径，尝试自动检测Zotero目录...")
        zotero_root = detect_zotero_path()
        
        if not zotero_root:
            print("❌ 未能自动检测到Zotero目录", file=sys.stderr)
            print("", file=sys.stderr)
            print("💡 请手动指定Zotero数据目录：", file=sys.stderr)
            print("   zotlink init /path/to/Zotero", file=sys.stderr)
            print("", file=sys.stderr)
            print("📍 常见位置：", file=sys.stderr)
            if sys.platform == "darwin":
                print("   macOS:   ~/Zotero", file=sys.stderr)
            elif sys.platform == "win32":
                print("   Windows: C:\\Users\\YourName\\Zotero", file=sys.stderr)
            else:
                print("   Linux:   ~/Zotero", file=sys.stderr)
            sys.exit(1)
        
        print(f"✅ 自动检测到: {zotero_root}")
    
    # 验证路径
    if not validate_zotero_path(zotero_root):
        sys.exit(1)
    
    # 检测zotlink命令路径
    zotlink_path = detect_zotlink_path()
    print(f"📍 检测到zotlink命令: {zotlink_path}")
    
    # 生成配置
    config = generate_mcp_config(zotlink_path, str(Path(zotero_root).resolve()))
    
    # 输出配置
    print("")
    print("━" * 60)
    print("📋 MCP服务器配置已生成，请复制以下内容到Claude配置文件：")
    print("━" * 60)
    print("")
    print(json.dumps(config, indent=2, ensure_ascii=False))
    print("")
    print("━" * 60)
    print("📂 Claude Desktop 配置文件位置：")
    if sys.platform == "darwin":
        print("   ~/Library/Application Support/Claude/claude_desktop_config.json")
    elif sys.platform == "win32":
        print("   %APPDATA%\\Claude\\claude_desktop_config.json")
    else:
        print("   ~/.config/Claude/claude_desktop_config.json")
    print("")
    print("💡 提示：将上述配置添加到配置文件后，重启Claude Desktop即可使用")
    print("━" * 60)


def main():
    """CLI主入口"""
    parser = argparse.ArgumentParser(
        prog='zotlink',
        description='ZotLink - 智能学术文献管理 MCP 服务器'
    )
    
    # 添加子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # init 子命令
    init_parser = subparsers.add_parser(
        'init',
        help='生成MCP服务器配置'
    )
    init_parser.add_argument(
        'zotero_root',
        nargs='?',
        help='Zotero数据目录路径（可选，未提供时自动检测）'
    )
    
    # 解析参数
    args = parser.parse_args()
    
    # 如果没有子命令，启动MCP服务器
    if not args.command:
        from .zotero_mcp_server import run
        run()
        return
    
    # 处理子命令
    if args.command == 'init':
        cmd_init(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()

