#!/usr/bin/env python3
"""
🧪 预印本网站标题提取测试脚本
测试bioRxiv、medRxiv、chemRxiv的标题提取能力
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "zotlink"))

from zotlink.extractors.extractor_manager import ExtractorManager
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_url_extraction(url: str, expected_title_keywords: list = None):
    """测试单个URL的提取效果"""
    print(f"\n{'='*80}")
    print(f"🧪 测试URL: {url}")
    print(f"{'='*80}")
    
    try:
        manager = ExtractorManager()
        result = await manager.extract_metadata(url)
        
        if result:
            print(f"✅ 提取成功！")
            print(f"📄 标题: {result.get('title', '未提取到')}")
            print(f"🔧 提取器: {result.get('extractor', '未知')}")
            print(f"📊 字段数量: {len(result)} 个")
            
            # 检查是否包含预期关键词
            title = result.get('title', '')
            if expected_title_keywords and title:
                found_keywords = [kw for kw in expected_title_keywords if kw.lower() in title.lower()]
                if found_keywords:
                    print(f"✅ 标题包含预期关键词: {found_keywords}")
                else:
                    print(f"⚠️ 标题可能不准确，未找到预期关键词: {expected_title_keywords}")
            
            # 显示其他重要字段
            for field in ['authors', 'DOI', 'pdf_url', 'abstractNote']:
                if result.get(field):
                    value = result[field]
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"  {field}: {value}")
        else:
            print(f"❌ 提取失败或返回空结果")
            
    except Exception as e:
        print(f"❌ 提取异常: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主测试函数"""
    print("🚀 开始预印本网站标题提取测试")
    
    # 测试URL列表
    test_cases = [
        {
            'url': 'https://www.biorxiv.org/content/10.1101/2025.09.24.677899v1',
            'expected_keywords': ['bioRxiv', 'preprint']  # 用户提供的测试URL
        },
        {
            'url': 'https://www.medrxiv.org/content/10.1101/2025.09.22.25336422v1',
            'expected_keywords': ['medRxiv']
        },
        # 如果有chemRxiv的URL，可以添加测试
    ]
    
    for test_case in test_cases:
        await test_url_extraction(test_case['url'], test_case.get('expected_keywords'))
        await asyncio.sleep(2)  # 避免请求过快
    
    print(f"\n{'='*80}")
    print("🎉 测试完成！请查看上述结果，确认标题提取是否成功。")
    print("如果标题仍为空，请检查网站的HTML结构是否发生变化。")
    print(f"{'='*80}")

if __name__ == "__main__":
    asyncio.run(main())
