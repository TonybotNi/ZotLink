#!/usr/bin/env python3
"""
作者解析功能测试工具
给定文本，测试作者名字的解析功能

使用方法:
    python test_author_parsing.py "John Smith, Jane Doe"
"""

import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from zotlink.zotero_integration import ZoteroConnector


def test_author_parsing(authors_str: str):
    """测试作者解析"""
    print("\n" + "=" * 80)
    print(f"输入: {authors_str}")
    print("=" * 80)
    
    # 创建 ZoteroConnector 实例
    connector = ZoteroConnector()
    
    # 创建测试数据
    paper_info = {
        "title": "Test Paper",
        "authors": authors_str,
    }
    
    # 调用转换方法
    zotero_item = connector._convert_to_zotero_format(paper_info)
    creators = zotero_item.get('creators', [])
    
    # 显示结果
    print(f"\n解析结果: {len(creators)} 个作者")
    print("-" * 80)
    for i, creator in enumerate(creators, 1):
        print(f"作者 {i}: {creator['firstName']} {creator['lastName']}")
    print()


def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 从命令行参数读取作者字符串
        authors_str = ' '.join(sys.argv[1:])
        test_author_parsing(authors_str)
    else:
        # 交互模式
        print("\n作者解析测试工具")
        print("输入作者字符串进行测试，输入 q 退出\n")
        
        while True:
            try:
                user_input = input("作者字符串: ").strip()
                
                if not user_input or user_input.lower() == 'q':
                    break
                
                test_author_parsing(user_input)
                
            except (KeyboardInterrupt, EOFError):
                print("\n退出")
                break


if __name__ == "__main__":
    main()
