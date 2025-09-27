#!/usr/bin/env python3
"""
🐛 调试标题显示问题
检查从提取器到最终消息的完整链路
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "zotlink"))

from zotlink.extractors.extractor_manager import ExtractorManager
import logging

# 设置详细日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def debug_extraction(url: str):
    """调试提取过程"""
    print(f"\n{'='*80}")
    print(f"🐛 调试URL: {url}")
    print(f"{'='*80}")
    
    try:
        manager = ExtractorManager()
        result = await manager.extract_metadata(url)
        
        print(f"\n📊 提取结果详情：")
        print(f"{'='*50}")
        
        if result:
            # 检查关键字段
            print(f"✅ 提取成功！结果字段：")
            for key, value in result.items():
                if key == 'title':
                    print(f"  🎯 {key}: '{value}' (长度: {len(str(value)) if value else 0})")
                elif key == 'extractor':
                    print(f"  🔧 {key}: {value}")
                elif key == 'error':
                    print(f"  ❌ {key}: {value}")
                else:
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:50] + "..."
                    print(f"     {key}: {value_str}")
            
            # 模拟zotero_mcp_server的标题获取逻辑
            print(f"\n🔍 模拟标题获取逻辑：")
            print(f"{'='*50}")
            
            paper_title = ""  # 模拟空的paper_title
            database = result.get('extractor', '')
            
            print(f"  database: '{database}'")
            print(f"  result.get('title'): '{result.get('title', '')}'")
            print(f"  paper_title: '{paper_title}'")
            
            if database and database != 'arXiv':
                # 这是bioRxiv/medRxiv的情况
                actual_title = result.get('title') or paper_title or '标题提取中...'
                print(f"  🎯 非arXiv分支 - actual_title: '{actual_title}'")
            else:
                actual_title = result.get('title') or paper_title or '标题提取中...'
                print(f"  🎯 其他分支 - actual_title: '{actual_title}'")
            
            print(f"\n✅ 最终显示标题: '{actual_title}'")
            
            if not actual_title or actual_title == '标题提取中...':
                print(f"❌ 标题仍然为空！需要进一步调试。")
            else:
                print(f"✅ 标题提取成功！")
        else:
            print(f"❌ 提取失败或返回空结果")
            
    except Exception as e:
        print(f"❌ 调试异常: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主调试函数"""
    # 使用用户提供的有问题的URL
    test_url = 'https://www.biorxiv.org/content/10.1101/2024.06.26.600822v2'
    await debug_extraction(test_url)

if __name__ == "__main__":
    asyncio.run(main())
