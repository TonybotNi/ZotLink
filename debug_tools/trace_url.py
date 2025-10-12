#!/usr/bin/env python3
"""
URL处理流程追踪工具
监视paper_info在处理过程中的变化

使用方法:
    python trace_url.py <URL>
    或者运行后输入URL
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from zotlink.extractors.extractor_manager import ExtractorManager
from zotlink.zotero_integration import ZoteroConnector


def print_step(step_num: int, title: str, data: dict):
    """打印处理步骤"""
    print("\n" + "=" * 80)
    print(f"步骤 {step_num}: {title}")
    print("=" * 80)
    
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 200:
                print(f"{key}: {value[:200]}...")
            else:
                print(f"{key}: {value}")
    else:
        print(data)


async def trace_url_processing(url: str):
    """追踪URL的完整处理流程"""
    print("\n" + "🔍" * 40)
    print(f"开始追踪 URL: {url}")
    print("🔍" * 40)
    
    extractor_manager = ExtractorManager()
    zotero_connector = ZoteroConnector()
    
    # 🔧 临时修复：保存原始方法并创建修复版本
    original_convert = zotero_connector._convert_to_zotero_format
    
    def patched_convert_to_zotero_format(paper_info):
        """修复版本：支持 creators 字段"""
        import re
        import time
        
        # 解析作者 - 支持两种格式
        authors = []
        
        # 🆕 优先使用已经格式化的 creators（Zotero格式数组）
        if paper_info.get('creators') and isinstance(paper_info['creators'], list):
            print("  ✅ 检测到 creators 字段（Zotero格式），直接使用")
            authors = paper_info['creators'][:15]  # 限制作者数量
        
        # 否则解析 authors 字符串格式
        elif paper_info.get('authors'):
            print("  ✅ 检测到 authors 字段（字符串格式），开始解析")
            # 调用原始方法来解析字符串格式的作者
            return original_convert(paper_info)
        
        else:
            print("  ⚠️ 未找到 authors 或 creators 字段")
        
        # 如果使用了 creators，需要手动构建其他部分
        # 解析日期
        date = paper_info.get('date', '')
        if date and date != '未知日期':
            try:
                date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date)
                if date_match:
                    day, month_name, year = date_match.groups()
                    months = {
                        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                    }
                    month = months.get(month_name[:3], '01')
                    date = f"{year}-{month}-{day.zfill(2)}"
                elif re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date):
                    pass
                elif re.search(r'^\d{4}$', date):
                    date = f"{date}-01-01"
            except:
                pass
        
        # 确定项目类型
        item_type = paper_info.get('itemType', 'journalArticle')
        if 'arxiv.org' in paper_info.get('url', ''):
            item_type = 'preprint'
        
        # 构建Zotero项目
        zotero_item = {
            "itemType": item_type,
            "title": paper_info.get('title', ''),
            "creators": authors,
            "abstractNote": paper_info.get('abstractNote') or paper_info.get('abstract', ''),
            "url": paper_info.get('url', ''),
            "date": date
        }
        
        # 添加其他字段
        if paper_info.get('DOI'):
            zotero_item["DOI"] = paper_info['DOI']
        if paper_info.get('repository'):
            zotero_item["repository"] = paper_info['repository']
        if paper_info.get('libraryCatalog'):
            zotero_item["libraryCatalog"] = paper_info['libraryCatalog']
        
        zotero_item["accessDate"] = time.strftime('%Y-%m-%d')
        
        # 移除空值
        zotero_item = {k: v for k, v in zotero_item.items() if v}
        
        return zotero_item
    
    # 应用修复
    zotero_connector._convert_to_zotero_format = patched_convert_to_zotero_format
    print("✅ 已应用临时修复（支持 creators 字段）\n")
    
    # 步骤1: 提取元数据
    print("\n⏳ 正在提取元数据...")
    
    if 'arxiv.org' in url:
        print("   检测到 arXiv URL，使用专用提取器...")
        try:
            metadata = zotero_connector._extract_arxiv_metadata(url)
            if 'error' not in metadata:
                metadata = {
                    'title': metadata.get('title', 'Unknown'),
                    'authors': metadata.get('authors_string', ''),
                    'date': metadata.get('date', ''),
                    'abstract': metadata.get('abstract', ''),
                    'url': metadata.get('abs_url', url),
                    'pdf_url': metadata.get('pdf_url', ''),
                    'arxiv_id': metadata.get('arxiv_id', ''),
                    'extractor': 'arXiv专用提取器',
                    'DOI': metadata.get('doi', ''),
                }
        except Exception as e:
            print(f"❌ 提取失败: {e}")
            return
    else:
        try:
            metadata = await extractor_manager.extract_metadata(url)
        except Exception as e:
            print(f"❌ 提取失败: {e}")
            return
    
    print_step(1, "提取的原始元数据", metadata)
    
    if not metadata or 'error' in metadata:
        print("\n❌ 提取失败")
        return
    
    # 步骤2: 构建初始 paper_info
    paper_info = {
        'title': metadata.get('title', 'Unknown'),
        'url': url
    }
    
    # 🔧 修复：同时处理 authors 和 creators 字段
    if 'authors' in metadata:
        paper_info['authors'] = metadata['authors']
    
    if 'creators' in metadata:
        paper_info['creators'] = metadata['creators']
    
    # 显示 paper_info（包含作者信息）
    display_info = paper_info.copy()
    if 'creators' in display_info:
        # 简化显示：只显示作者数量
        display_info['creators_count'] = len(display_info['creators'])
        display_info['creators_preview'] = display_info['creators'][:3]  # 显示前3个
        del display_info['creators']
    
    print_step(2, "初始 paper_info", display_info)
    
    # 步骤3: arXiv增强（如果适用）
    if 'arxiv.org' in url:
        print("\n⏳ arXiv元数据增强...")
        enhanced_info = zotero_connector._enhance_paper_info_for_arxiv(paper_info)
        print_step(3, "arXiv增强后的 paper_info", enhanced_info)
        paper_info = enhanced_info
    
    # 步骤3.5: 显示传递给转换方法的 paper_info
    print("\n" + "🔍" * 40)
    print("步骤 3.5: 传递给 _convert_to_zotero_format 的 paper_info")
    print("🔍" * 40)
    print(f"包含 'authors' 字段: {'authors' in paper_info}")
    print(f"包含 'creators' 字段: {'creators' in paper_info}")
    if 'authors' in paper_info:
        print(f"  authors (字符串): {paper_info['authors'][:100]}...")
    if 'creators' in paper_info:
        print(f"  creators (数组): {len(paper_info['creators'])} 位作者")
        for i, creator in enumerate(paper_info['creators'][:3], 1):
            print(f"    作者 {i}: {creator}")
    
    # 步骤4: 转换为Zotero格式
    print("\n⏳ 转换为Zotero格式...")
    zotero_item = zotero_connector._convert_to_zotero_format(paper_info)
    
    print_step(4, "最终的Zotero格式", {
        'title': zotero_item.get('title'),
        'creators': zotero_item.get('creators', []),
        'date': zotero_item.get('date'),
        'url': zotero_item.get('url'),
    })
    
    # 总结作者信息
    print("\n" + "📊" * 40)
    print("作者信息总结")
    print("📊" * 40)
    creators = zotero_item.get('creators', [])
    print(f"最终作者数量: {len(creators)}")
    for i, creator in enumerate(creators, 1):
        print(f"  作者 {i}: {creator['firstName']} {creator['lastName']}")
    
    print("\n✅ 追踪完成！")


async def main():
    """主函数"""
    # 获取URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        print("\n请输入要测试的论文URL:")
        print("示例:")
        print("  - arXiv: https://arxiv.org/abs/2301.00001")
        print("  - bioRxiv: https://www.biorxiv.org/content/...")
        print("  - Nature: https://www.nature.com/articles/...")
        print()
        url = input("URL: ").strip()
    
    if not url:
        print("❌ 未提供URL")
        return
    
    try:
        await trace_url_processing(url)
    except Exception as e:
        print(f"\n❌ 追踪过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

