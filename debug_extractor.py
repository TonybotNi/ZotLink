#!/usr/bin/env python3
"""
🔍 ZotLink 提取器调试工具

用于诊断预印本网站标题提取问题
"""

import asyncio
import logging
from zotlink.extractors.extractor_manager import ExtractorManager

# 配置日志显示详细信息
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

async def test_extraction(url: str):
    """测试URL的元数据提取"""
    print(f"\n🔍 测试URL: {url}")
    print("=" * 80)
    
    try:
        # 创建提取器管理器
        manager = ExtractorManager()
        
        # 执行提取
        result = await manager.extract_metadata(url)
        
        print(f"\n📊 提取结果:")
        print(f"  成功: {result.get('success', 'Unknown')}")
        print(f"  提取器: {result.get('extractor', 'Unknown')}")
        print(f"  标题: '{result.get('title', 'None')}'")
        print(f"  作者: '{result.get('authors', 'None')}'")
        print(f"  DOI: '{result.get('DOI', 'None')}'")
        print(f"  PDF URL: '{result.get('pdf_url', 'None')}'")
        
        if result.get('error'):
            print(f"  错误: {result.get('error')}")
        
        print("\n" + "="*80)
        
        return result
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """主测试函数"""
    print("🚀 ZotLink 提取器调试工具")
    print("用于诊断预印本网站标题提取问题")
    
    # 测试URL列表
    test_urls = [
        "https://www.medrxiv.org/content/10.1101/2025.09.22.25336422v1",
        "https://www.biorxiv.org/content/10.1101/2024.01.01.000001v1",
        "https://openaccess.thecvf.com/content/ICCV2023/papers/Fang_Visible-Infrared_Person_Re-Identification_via_Semantic_Alignment_and_Affinity_Inference_ICCV_2023_paper.pdf"
    ]
    
    for url in test_urls:
        try:
            result = await test_extraction(url)
            
            # 检查结果
            if result and result.get('title') and result.get('title').strip():
                print(f"✅ {url[:50]}... - 标题提取成功")
            else:
                print(f"❌ {url[:50]}... - 标题提取失败")
                
        except Exception as e:
            print(f"💥 {url[:50]}... - 测试异常: {e}")
        
        print()  # 空行分隔
    
    print("🎯 调试建议:")
    print("1. 查看上面的详细日志输出")
    print("2. 如果浏览器提取失败，检查是否安装了 playwright: pip install playwright && playwright install")
    print("3. 如果HTTP提取器有标题但浏览器提取器没有，说明是浏览器模式的问题")
    print("4. 注意智能回退机制是否被触发")

if __name__ == "__main__":
    asyncio.run(main())
