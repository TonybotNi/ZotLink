#!/usr/bin/env python3
"""
🔗 ZotLink 启动脚本

智能学术文献管理MCP工具
专注开放学术资源，无需cookies
"""

import sys
import os
from pathlib import Path

# 优先使用已安装的包；开发模式下回退本地包路径
pkg_path = Path(__file__).parent / "zotlink"
if pkg_path.exists():
    sys.path.insert(0, str(pkg_path))

# 设置日志路径到用户可访问的位置
log_path = Path(__file__).parent / "zotlink.log"

def setup_logging():
    """设置日志配置"""
    import logging
    
    # 重定向到文件
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stderr)  # 输出到stderr避免干扰MCP协议
        ]
    )

def main():
    """主函数"""
    setup_logging()
    
    # 输出启动信息到stderr
    print("🔗 启动ZotLink服务器...", file=sys.stderr)
    print(f"📝 日志位置: {log_path}", file=sys.stderr)
    
    try:
        # 导入并运行服务器（已打包入口）
        from zotlink.zotero_mcp_server import main as server_main
        import asyncio
        
        asyncio.run(server_main())
        
    except ImportError as e:
        print(f"❌ 导入错误: {e}", file=sys.stderr)
        print("💡 请确保安装了所有依赖: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 启动失败: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 