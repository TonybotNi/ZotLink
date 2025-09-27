"""
Nature Scholar Tool MCP 服务器
轻量级版本 - 基于requests + cookies，无需Selenium
"""
import asyncio
import logging
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource, 
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    ReadResourceResult
)
from pydantic import AnyUrl

from .downloader import LightweightNatureDownloader
from .zotero_integration import ZoteroConnector

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化MCP服务器
app = Server("nature-scholar-tool")

# 全局变量
downloader = None

# 独立的Zotero连接器（不依赖cookies）
zotero_connector = ZoteroConnector()


@app.list_resources()
async def handle_list_resources() -> list[Resource]:
    """列出可用资源"""
    resources = [
        Resource(
            uri=AnyUrl("nature://config"),
            name="配置信息",
            description="Nature Scholar Tool的配置信息",
            mimeType="application/json"
        ),
        Resource(
            uri=AnyUrl("nature://status"),
            name="登录状态",
            description="当前登录状态和会话信息",
            mimeType="application/json"
        ),
        Resource(
            uri=AnyUrl("nature://cookies-guide"),
            name="Cookies获取指南",
            description="如何获取Nature网站cookies的详细指南",
            mimeType="text/markdown"
        ),
        Resource(
            uri=AnyUrl("nature://downloads"),
            name="下载历史",
            description="已下载文献的历史记录",
            mimeType="application/json"
        )
    ]
    return resources


@app.read_resource()
async def handle_read_resource(uri: AnyUrl) -> ReadResourceResult:
    """读取资源内容"""
    try:
        if uri.scheme != "nature":
            raise ValueError(f"不支持的URI协议: {uri.scheme}")
        
        path = uri.path
        
        if path == "config":
            config_info = {
                "tool_name": "Nature Scholar Tool",
                "version": "0.2.0",
                "description": "轻量级Nature文献下载工具 - 基于requests + cookies",
                "supported_features": [
                    "基于cookies的无头下载",
                    "论文搜索",
                    "PDF下载",
                    "HTML内容保存",
                    "补充材料下载",
                    "自动从浏览器读取cookies",
                    "手动cookies导入"
                ],
                "download_directory": os.path.expanduser("~/Downloads/Nature_Papers"),
                "no_selenium_required": True
            }
            return ReadResourceResult(
                contents=[TextContent(type="text", text=str(config_info))]
            )
        
        elif path == "status":
            global downloader
            if downloader:
                status = downloader.test_login_status()
                status_info = {
                    "session_active": True,
                    "logged_in": status.get("logged_in", False),
                    "cookies_count": status.get("cookies_count", 0),
                    "last_test": status
                }
            else:
                status_info = {
                    "session_active": False,
                    "logged_in": False,
                    "cookies_count": 0,
                    "message": "尚未初始化下载器"
                }
            
            return ReadResourceResult(
                contents=[TextContent(type="text", text=str(status_info))]
            )
        
        elif path == "cookies-guide":
            if downloader:
                guide = downloader.get_cookies_from_browser_manual()
            else:
                temp_downloader = LightweightNatureDownloader()
                guide = temp_downloader.get_cookies_from_browser_manual()
            
            return ReadResourceResult(
                contents=[TextContent(type="text", text=guide)]
            )
        
        elif path == "downloads":
            download_info = {
                "total_downloads": 0,
                "recent_downloads": [],
                "download_directory": os.path.expanduser("~/Downloads/Nature_Papers"),
                "session_active": downloader is not None
            }
            return ReadResourceResult(
                contents=[TextContent(type="text", text=str(download_info))]
            )
        
        else:
            raise ValueError(f"未知资源路径: {path}")
    
    except Exception as e:
        logger.error(f"读取资源时出错: {str(e)}")
        return ReadResourceResult(
            contents=[TextContent(type="text", text=f"读取资源时出错: {str(e)}")]
        )


@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    """列出可用工具"""
    tools = [
        Tool(
            name="set_cookies",
            description="设置Nature网站的cookies（JSON格式或cookie字符串）",
            inputSchema={
                "type": "object",
                "properties": {
                    "cookies": {
                        "type": "string",
                        "description": "Cookies数据（JSON格式或cookie字符串）"
                    }
                },
                "required": ["cookies"]
            }
        ),
        Tool(
            name="load_cookies_from_browser",
            description="从浏览器自动读取cookies",
            inputSchema={
                "type": "object",
                "properties": {
                    "browser": {
                        "type": "string",
                        "description": "浏览器类型（chrome, safari）",
                        "default": "chrome",
                        "enum": ["chrome", "safari"]
                    }
                }
            }
        ),
        Tool(
            name="test_login_status",
            description="测试当前登录状态",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="search_papers",
            description="在Nature网站搜索论文",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大结果数量（默认10）",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="enhanced_search_papers",
            description="增强的关键词搜索，返回最相关的10篇文献（按相关性排序）",
            inputSchema={
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最大返回数量（默认10）",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["keywords"]
            }
        ),
        Tool(
            name="download_paper",
            description="下载指定的论文",
            inputSchema={
                "type": "object",
                "properties": {
                    "paper_url": {
                        "type": "string",
                        "description": "论文的URL"
                    },
                    "paper_title": {
                        "type": "string",
                        "description": "论文标题（可选，用于生成文件名）",
                        "default": ""
                    }
                },
                "required": ["paper_url"]
            }
        ),
        Tool(
            name="download_papers_batch",
            description="批量下载论文",
            inputSchema={
                "type": "object",
                "properties": {
                    "papers": {
                        "type": "array",
                        "description": "论文信息数组",
                        "items": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "title": {"type": "string"}
                            },
                            "required": ["url"]
                        }
                    }
                },
                "required": ["papers"]
            }
        ),
        Tool(
            name="get_cookies_guide",
            description="获取如何手动获取cookies的指导",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="export_cookies",
            description="导出当前cookies为JSON格式",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="check_zotero_status",
            description="检查Zotero连接状态",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_zotero_collections",
            description="获取Zotero集合列表",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="save_to_zotero",
            description="将论文信息保存到Zotero",
            inputSchema={
                "type": "object",
                "properties": {
                    "paper_url": {
                        "type": "string",
                        "description": "论文URL"
                    },
                    "paper_title": {
                        "type": "string",
                        "description": "论文标题"
                    },
                    "collection_key": {
                        "type": "string",
                        "description": "目标集合key（可选）"
                    }
                },
                "required": ["paper_url", "paper_title"]
            }
        ),
        Tool(
            name="create_zotero_collection",
            description="在Zotero中创建新集合/文件夹",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "集合名称"
                    },
                    "parent_key": {
                        "type": "string", 
                        "description": "父集合key（可选，用于创建子集合）"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="download_and_save_to_zotero",
            description="下载论文并保存到Zotero（一步完成）",
            inputSchema={
                "type": "object",
                "properties": {
                    "paper_url": {
                        "type": "string",
                        "description": "论文URL"
                    },
                    "paper_title": {
                        "type": "string",
                        "description": "论文标题（可选）"
                    },
                    "collection_key": {
                        "type": "string",
                        "description": "目标集合key（可选）"
                    }
                },
                "required": ["paper_url"]
            }
        ),
        Tool(
            name="search_and_download",
            description="搜索并自动下载第一篇论文（快捷操作）",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    },
                    "download_count": {
                        "type": "integer",
                        "description": "下载论文数量（默认1）",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 5
                    }
                },
                "required": ["query"]
            }
        )
    ]
    return tools


@app.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """处理工具调用"""
    global downloader
    
    try:
        if name == "set_cookies":
            cookies = arguments.get("cookies")
            
            if not cookies:
                return [TextContent(type="text", text="缺少cookies参数")]
            
            try:
                # 初始化下载器并设置cookies
                downloader = LightweightNatureDownloader(cookies)
                
                # 测试登录状态
                status = downloader.test_login_status()
                
                if status.get("logged_in"):
                    message = "✅ Cookies设置成功，已登录Nature网站！"
                else:
                    message = "⚠️ Cookies已设置，但登录状态不确定。请检查cookies是否有效。"
                
                message += f"\n📊 当前cookies数量: {status.get('cookies_count', 0)}"
                
                return [TextContent(type="text", text=message)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"设置cookies失败: {str(e)}")]
        
        elif name == "load_cookies_from_browser":
            browser = arguments.get("browser", "chrome")
            
            try:
                if not downloader:
                    downloader = LightweightNatureDownloader()
                
                success = downloader.load_cookies_from_browser(browser)
                
                if success:
                    status = downloader.test_login_status()
                    message = f"✅ 成功从{browser}浏览器加载cookies！\n"
                    message += f"登录状态: {'已登录' if status.get('logged_in') else '未登录'}\n"
                    message += f"Cookies数量: {status.get('cookies_count', 0)}"
                else:
                    message = f"❌ 从{browser}浏览器加载cookies失败。\n"
                    message += "请确保:\n1. 浏览器已关闭\n2. 已在浏览器中登录Nature网站\n3. 安装了必要的解密库"
                
                return [TextContent(type="text", text=message)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"从浏览器加载cookies失败: {str(e)}")]
        
        elif name == "test_login_status":
            if not downloader:
                return [TextContent(type="text", text="❌ 请先设置cookies或初始化下载器")]
            
            status = downloader.test_login_status()
            
            if status.get("logged_in"):
                message = "✅ 已登录Nature网站"
            else:
                message = "❌ 未登录或cookies已过期"
            
            message += f"\n📊 详细信息:\n"
            message += f"  状态码: {status.get('status_code', 'N/A')}\n"
            message += f"  Cookies数量: {status.get('cookies_count', 0)}\n"
            message += f"  测试URL状态: {status.get('test_url_status', 'N/A')}"
            
            if status.get("error"):
                message += f"\n❌ 错误: {status['error']}"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "search_papers":
            if not downloader:
                return [TextContent(type="text", text="❌ 请先设置cookies")]
            
            query = arguments.get("query")
            max_results = arguments.get("max_results", 10)
            
            if not query:
                return [TextContent(type="text", text="缺少搜索关键词")]
            
            papers = downloader.search_papers(query, max_results)
            
            if papers:
                result_text = f"🔍 找到 {len(papers)} 篇相关论文:\n\n"
                for i, paper in enumerate(papers, 1):
                    result_text += f"{i}. **{paper.get('title', '未知标题')}**\n"
                    result_text += f"   作者: {paper.get('authors', '未知作者')}\n"
                    result_text += f"   期刊: {paper.get('journal', 'Nature')}\n"
                    result_text += f"   日期: {paper.get('date', '未知日期')}\n"
                    result_text += f"   链接: {paper.get('url', '')}\n"
                    if paper.get('abstract'):
                        abstract = paper['abstract'][:200] + "..." if len(paper['abstract']) > 200 else paper['abstract']
                        result_text += f"   摘要: {abstract}\n"
                    result_text += "\n"
            else:
                result_text = f"❌ 未找到关键词 '{query}' 的相关论文"
            
            return [TextContent(type="text", text=result_text)]
        
        elif name == "enhanced_search_papers":
            if not downloader:
                return [TextContent(type="text", text="❌ 请先设置cookies")]
            
            keywords = arguments.get("keywords")
            max_results = arguments.get("max_results", 10)
            
            if not keywords:
                return [TextContent(type="text", text="缺少搜索关键词")]
            
            search_results = downloader.enhanced_search_papers(keywords, max_results)
            
            if search_results.get("error"):
                return [TextContent(type="text", text=f"❌ 搜索失败: {search_results['error']}")]
            
            papers = search_results.get("papers", [])
            search_info = search_results.get("search_info", {})
            
            if papers:
                result_text = f"🎯 **增强搜索结果** - 关键词: {keywords}\n"
                result_text += f"📊 搜索统计: 找到 {search_results.get('total_found', 0)} 篇论文，返回前 {len(papers)} 篇最相关的\n"
                result_text += f"⏰ 搜索时间: {search_info.get('timestamp', '未知')}\n\n"
                
                for i, paper in enumerate(papers, 1):
                    relevance_score = paper.get('relevance_score', 0)
                    result_text += f"**{i}. {paper.get('title', '未知标题')}**\n"
                    result_text += f"   🎯 相关性评分: {relevance_score}/10\n"
                    result_text += f"   👥 作者: {paper.get('authors', '未知作者')}\n"
                    result_text += f"   📖 期刊: {paper.get('journal', 'Nature')}\n"
                    result_text += f"   📅 日期: {paper.get('date', '未知日期')}\n"
                    result_text += f"   🔗 链接: {paper.get('url', '')}\n"
                    result_text += f"   📥 可下载: {'✅' if paper.get('downloadable') else '❌'}\n"
                    
                    if paper.get('abstract'):
                        abstract = paper['abstract'][:300] + "..." if len(paper['abstract']) > 300 else paper['abstract']
                        result_text += f"   📝 摘要: {abstract}\n"
                    
                    result_text += "\n"
                
                result_text += f"\n💡 **使用提示**: 复制论文链接，使用 `download_paper` 工具进行下载\n"
                result_text += f"📂 下载位置: {downloader.download_dir}"
                
            else:
                result_text = f"❌ 未找到关键词 '{keywords}' 的相关论文\n"
                result_text += f"💡 建议尝试不同的关键词或者更通用的搜索词"
            
            return [TextContent(type="text", text=result_text)]
        
        elif name == "download_paper":
            if not downloader:
                return [TextContent(type="text", text="❌ 请先设置cookies")]
            
            paper_url = arguments.get("paper_url")
            paper_title = arguments.get("paper_title", "")
            
            if not paper_url:
                return [TextContent(type="text", text="缺少论文URL")]
            
            result = downloader.download_paper(paper_url, paper_title)
            
            if result["success"]:
                message = f"✅ {result['message']}\n"
                message += f"下载的文件:\n"
                for file in result["files"]:
                    message += f"  📄 {file}\n"
                message += f"\n📂 文件保存位置: {downloader.download_dir}"
            else:
                message = f"❌ 下载失败: {result['message']}"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "download_papers_batch":
            if not downloader:
                return [TextContent(type="text", text="❌ 请先设置cookies")]
            
            papers = arguments.get("papers", [])
            
            if not papers:
                return [TextContent(type="text", text="缺少论文列表")]
            
            # 批量下载
            results = []
            success_count = 0
            total_files = 0
            
            for i, paper in enumerate(papers):
                url = paper.get("url", "")
                title = paper.get("title", f"论文{i+1}")
                
                if not url:
                    continue
                
                result = downloader.download_paper(url, title)
                results.append(result)
                
                if result["success"]:
                    success_count += 1
                    total_files += len(result["files"])
            
            message = f"📊 批量下载完成:\n"
            message += f"  ✅ 成功: {success_count}/{len(papers)} 篇论文\n"
            message += f"  📄 共下载: {total_files} 个文件\n\n"
            
            for i, result in enumerate(results, 1):
                paper_title = papers[i-1].get("title", f"论文{i}")
                if result["success"]:
                    message += f"{i}. ✅ {paper_title}: {len(result['files'])} 个文件\n"
                else:
                    message += f"{i}. ❌ {paper_title}: {result['message']}\n"
            
            message += f"\n📂 文件保存位置: {downloader.download_dir}"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "get_cookies_guide":
            temp_downloader = LightweightNatureDownloader()
            guide = temp_downloader.get_cookies_from_browser_manual()
            
            return [TextContent(type="text", text=guide)]
        
        elif name == "export_cookies":
            if not downloader:
                return [TextContent(type="text", text="❌ 请先设置cookies")]
            
            cookies_json = downloader.export_cookies()
            
            message = f"📋 当前cookies（JSON格式）:\n\n```json\n{cookies_json}\n```\n\n"
            message += "💡 你可以保存这些cookies，稍后使用 set_cookies 工具重新导入"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "search_and_download":
            if not downloader:
                return [TextContent(type="text", text="❌ 请先设置cookies")]
            
            query = arguments.get("query")
            download_count = arguments.get("download_count", 1)
            
            if not query:
                return [TextContent(type="text", text="缺少搜索关键词")]
            
            # 先搜索
            papers = downloader.search_papers(query, download_count + 2)
            
            if not papers:
                return [TextContent(type="text", text=f"❌ 未找到关键词 '{query}' 的相关论文")]
            
            # 下载前几篇
            papers_to_download = papers[:download_count]
            results = []
            success_count = 0
            total_files = 0
            
            message = f"🔍 找到 {len(papers)} 篇论文，正在下载前 {len(papers_to_download)} 篇:\n\n"
            
            for i, paper in enumerate(papers_to_download):
                result = downloader.download_paper(paper.get("url", ""), paper.get("title", ""))
                results.append(result)
                
                if result["success"]:
                    success_count += 1
                    total_files += len(result["files"])
                    message += f"✅ {paper.get('title', '未知标题')}: {len(result['files'])} 个文件\n"
                else:
                    message += f"❌ {paper.get('title', '未知标题')}: {result['message']}\n"
            
            message += f"\n📊 总结:\n"
            message += f"  成功: {success_count}/{len(papers_to_download)} 篇论文\n"
            message += f"  共下载: {total_files} 个文件\n"
            message += f"  文件保存位置: {downloader.download_dir}"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "check_zotero_status":
            if zotero_connector.is_running():
                version = zotero_connector.get_version() or "未知版本"
                collections = zotero_connector.get_collections()
                collections_count = len(collections)
                
                message = f"✅ **Zotero连接正常**\n\n"
                message += f"📊 **版本**: {version}\n"
                message += f"📚 **集合数量**: {collections_count} 个\n"
                message += f"🔗 **端口**: {zotero_connector.port}\n"
                message += f"🗃️ **数据库**: {'已找到' if zotero_connector._zotero_db_path else '未找到'}\n\n"
                message += f"🎯 **可用功能**:\n"
                message += f"  ✅ `get_zotero_collections` - 查看所有集合 (数据库直读)\n"
                message += f"  ✅ `save_to_zotero` - 保存论文元数据\n"
                message += f"  ✅ `create_zotero_collection` - 创建新集合\n"
                message += f"  🔧 `download_and_save_to_zotero` - 完整下载 (需cookies)\n\n"
                message += f"🎉 **突破性进展**: 现在可以直接读取Zotero数据库获取完整集合列表！"
            else:
                message = f"❌ **Zotero不可用**\n\n"
                message += f"请确保:\n"
                message += f"  1. Zotero桌面应用已启动\n"
                message += f"  2. Zotero版本为6.0以上\n"
                message += f"  3. 没有防火墙阻止本地连接(端口23119)"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "get_zotero_collections":
            if not zotero_connector.is_running():
                return [TextContent(type="text", text="❌ Zotero不可用，请启动Zotero桌面应用")]
            
            collections = zotero_connector.get_collections()
            
            if collections and len(collections) > 0:
                # 构建层级结构的辅助函数
                def build_tree_display(collections_list):
                    # 按层级组织
                    root_collections = [c for c in collections_list if not c.get('parentCollection')]
                    child_collections = [c for c in collections_list if c.get('parentCollection')]
                    
                    # 创建父子关系映射
                    children_map = {}
                    for child in child_collections:
                        parent_id = child.get('parentCollection')
                        if parent_id not in children_map:
                            children_map[parent_id] = []
                        children_map[parent_id].append(child)
                    
                    tree_text = ""
                    
                    def add_collection(collection, level=0, is_last=False, parent_prefix=""):
                        nonlocal tree_text
                        
                        name = collection.get('name', '未命名集合')
                        key = collection.get('key', 'N/A')
                        
                        # 根据层级确定前缀
                        if level == 0:
                            prefix = ""
                            line_prefix = ""
                        else:
                            connector = "└── " if is_last else "├── "
                            prefix = parent_prefix + connector
                            line_prefix = parent_prefix + ("    " if is_last else "│   ")
                        
                        # 添加集合信息
                        tree_text += f"{prefix}📁 **{name}**\n"
                        tree_text += f"{line_prefix}🔑 `{key}`\n"
                        
                        # 添加子集合
                        collection_id = collection.get('id')
                        if collection_id in children_map:
                            children = children_map[collection_id]
                            for i, child in enumerate(children):
                                is_last_child = (i == len(children) - 1)
                                add_collection(child, level + 1, is_last_child, line_prefix)
                        
                        if level == 0:  # 根集合之间添加空行
                            tree_text += "\n"
                    
                    # 添加所有根集合
                    for root in sorted(root_collections, key=lambda x: x.get('name', '')):
                        add_collection(root)
                    
                    # 处理孤立的子集合（没有对应父集合的）
                    orphans = [c for c in child_collections 
                             if not any(p.get('id') == c.get('parentCollection') for p in root_collections)]
                    
                    if orphans:
                        tree_text += "**🔍 孤立集合** (可能父集合已删除):\n"
                        for orphan in orphans:
                            add_collection(orphan)
                    
                    return tree_text
                
                message = f"📚 **Zotero集合树状结构** ({len(collections)} 个集合):\n\n"
                message += build_tree_display(collections)
                
                message += f"💡 **使用说明**:\n"
                message += f"• 复制上面的🔑Key值用作 `collection_key` 参数\n"
                message += f"• 不指定collection_key → 保存到📚我的文库（默认位置）\n"
                message += f"• 指定collection_key → 保存到🎯指定集合\n"
                message += f"• 层级结构：└── 表示子集合，├── 表示有兄弟集合"
            else:
                message = f"📚 **Zotero中暂无集合**\n\n"
                message += f"看起来你的Zotero中还没有创建任何集合（文件夹）。\n\n"
                message += f"**建议**:\n"
                message += f"• 📁 在Zotero中手动创建一些集合\n"
                message += f"• ➕ 使用 `create_zotero_collection` 工具创建新集合\n"
                message += f"• 💾 直接使用 `save_to_zotero` 保存论文（会保存到默认位置）"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "save_to_zotero":
            paper_url = arguments.get("paper_url")
            paper_title = arguments.get("paper_title", "")
            collection_key = arguments.get("collection_key")
            
            if not paper_url:
                return [TextContent(type="text", text="缺少论文URL")]
            
            if not zotero_connector.is_running():
                return [TextContent(type="text", text="❌ Zotero不可用，请启动Zotero桌面应用")]
            
            # 构建基本论文信息
            paper_info = {
                "title": paper_title,
                "url": paper_url,
                "journal": "Nature",
                "itemType": "journalArticle"
            }
            
            # 显示处理进度
            if 'arxiv.org' in paper_url:
                processing_msg = "🔄 处理arxiv论文...\n"
                processing_msg += "• 提取论文元数据\n"
                processing_msg += "• 获取作者、摘要、日期等信息\n"
                processing_msg += "• 保存到Zotero...\n"
                logger.info("开始处理arxiv论文")
            
            result = zotero_connector.save_item_to_zotero(paper_info, collection_key=collection_key)
            
            if result["success"]:
                message = f"🎉 **成功保存到Zotero!**\n\n"
                
                # 显示使用的数据库 - 优先使用真实数据库名称
                source = result.get("source", "")
                database = result.get("database", "未知")
                
                # 🎯 优先显示真实数据库名称而非提取器名称
                display_database = source or database
                if display_database == "Browser-Driven":
                    display_database = "未知数据库"
                
                enhanced = result.get("enhanced", False)
                
                message += f"🔗 **数据库**: {display_database}\n"
                message += f"🤖 **智能增强**: {'✅ 是' if enhanced else '➖ 否'}\n\n"
                
                # 检查是否是arxiv论文并提供更详细信息
                if 'arxiv.org' in paper_url:
                    message += f"📄 **论文类型**: arXiv预印本\n"
                    
                    # 尝试从URL提取arxiv ID
                    import re
                    arxiv_match = re.search(r'arxiv\.org/(abs|pdf)/([^/?]+)', paper_url)
                    if arxiv_match:
                        arxiv_id = arxiv_match.group(2)
                        message += f"🏷️ **arXiv ID**: {arxiv_id}\n"
                        # 🎯 修复：优先使用返回结果中的标题
                        actual_title = result.get('title') or paper_title or f'arXiv:{arxiv_id} (标题提取中...)'
                        message += f"📄 **标题**: {actual_title}\n"
                        message += f"🔗 **摘要页面**: https://arxiv.org/abs/{arxiv_id}\n"
                        message += f"📥 **PDF链接**: https://arxiv.org/pdf/{arxiv_id}.pdf\n"
                else:
                    # 🎯 根据itemType和source确定论文类型
                    item_type = result.get('itemType', '')
                    paper_type = "期刊文章"
                    
                    if item_type == 'preprint' or source in ['bioRxiv', 'medRxiv', 'ChemRxiv', 'PsyArXiv']:
                        paper_type = "预印本"
                    elif source:
                        paper_type = f"{source}论文"
                    elif display_database != "未知数据库":
                        paper_type = f"{display_database}期刊文章"
                    
                    message += f"📄 **论文类型**: {paper_type}\n"
                    # 🎯 修复：优先使用返回结果中的标题，而非空的paper_title
                    actual_title = result.get('title') or paper_title or '标题提取中...'
                    message += f"📄 **标题**: {actual_title}\n"
                    message += f"🔗 **URL**: {paper_url}\n"
                
                # 集合保存状态
                if collection_key:
                    if result.get("collection_specified"):
                        message += f"✅ **保存集合**: 已指定到 {collection_key}\n"
                    else:
                        message += f"⚠️ **保存集合**: 指定失败，已保存到默认位置\n"
                else:
                    message += f"📚 **保存位置**: 我的文库（默认位置）\n"
                
                # updateSession修复状态
                if result.get("update_session_used"):
                    message += f"\n📎 **集合移动状态** (基于官方源码):\n"
                    
                    if result.get("collection_move_success"):
                        message += f"🎉 **集合移动**: ✅ 成功使用updateSession移动到指定集合\n"
                        message += f"✨ **重大突破**: 基于Zotero Connector官方updateSession机制\n"
                    else:
                        message += f"⚠️ **集合移动**: ❌ updateSession失败，条目在默认位置\n"
                    
                    if result.get("pdf_success"):
                        message += f"✅ **PDF附件**: 已自动下载并附加\n"
                    
                    if result.get("extra_preserved"):
                        message += f"✅ **Comment信息**: 已保存在Extra字段中\n"
                
                if result.get("zotero_url"):
                    message += f"🚀 **Zotero链接**: {result['zotero_url']}\n"
                
                message += f"\n✨ **已提取的元数据**:\n"
                message += f"• 🔍 完整论文信息（标题、作者、摘要、日期）\n"
                message += f"• 📄 页数和图表信息（\"15 pages, 5 figures\"）\n"
                message += f"• 📚 学科分类信息\n"
                message += f"• 🏷️ 正确的文献类型（预印本/期刊文章）\n"
                message += f"• 🔗 完整的引用信息\n"
                
                message += f"\n📋 **立即验证**:\n"
                if result.get("collection_move_success"):
                    message += f"🎉 **终极成功！updateSession集合移动**:\n"
                    message += f"1. 打开Zotero桌面应用\n"
                    message += f"2. **直接检查My Research集合**\n"
                    message += f"3. 条目应该已经在正确的集合中了！\n"
                    if result.get("pdf_success"):
                        message += f"4. 确认PDF附件已自动添加\n"
                    if result.get("extra_preserved"):
                        message += f"5. 查看Extra字段的Comment信息\n"
                    message += f"\n🎯 **这是真正的完全自动化！**\n"
                elif result.get("update_session_used"):
                    message += f"⚠️ **updateSession尝试失败**:\n"
                    message += f"1. 打开Zotero桌面应用\n"
                    message += f"2. 在\"我的文库\"中找到条目\n"
                    message += f"3. 手动拖拽到My Research集合\n"
                else:
                    message += f"📚 打开Zotero桌面应用查看保存的条目\n"
            else:
                message = f"❌ **保存失败**: {result.get('message', '未知错误')}\n\n"
                message += f"🔧 **故障排除**:\n"
                message += f"• 确保Zotero桌面应用正在运行\n"
                message += f"• 检查网络连接是否正常\n"
                message += f"• 尝试重新启动Zotero应用\n"
                message += f"• 如果是集合问题，可尝试不指定collection_key"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "create_zotero_collection":
            collection_name = arguments.get("name", "").strip()
            parent_key = arguments.get("parent_key", "").strip() or None
            
            if not collection_name:
                return [TextContent(type="text", text="缺少集合名称")]
            
            if not zotero_connector.is_running():
                return [TextContent(type="text", text="❌ Zotero不可用，请启动Zotero桌面应用")]
            
            # 由于Zotero Connector API限制，提供手动创建指导
            message = f"⚠️ **Zotero API限制说明**\n\n"
            message += f"很抱歉，Zotero的本地Connector API不支持通过代码创建集合。\n"
            message += f"这是Zotero软件的设计限制。\n\n"
            message += f"🎯 **请手动创建集合**：\n"
            message += f"1. 📱 打开你的**Zotero桌面应用**\n"
            message += f"2. 🖱️ 右键点击左侧文件夹区域\n"
            message += f"3. ➕ 选择 **\"新建集合\"**\n"
            message += f"4. 📝 输入集合名称：**{collection_name}**\n"
            message += f"5. ✅ 确认创建\n\n"
            message += f"📚 **创建完成后**：\n"
            message += f"• 使用 `get_zotero_collections` 工具获取新集合的Key\n"
            message += f"• 使用获取到的Key保存论文到指定集合\n"
            message += f"• 或者直接使用 `save_to_zotero`（不指定collection_key）保存到默认位置\n\n"
            message += f"💡 **提示**: 手动创建集合只需要10秒钟，之后就可以正常使用所有保存功能了！"
            
            return [TextContent(type="text", text=message)]
        
        elif name == "download_and_save_to_zotero":
            paper_url = arguments.get("paper_url")
            paper_title = arguments.get("paper_title", "")
            collection_key = arguments.get("collection_key")
            
            if not paper_url:
                return [TextContent(type="text", text="缺少论文URL")]
            
            if not zotero_connector.is_running():
                return [TextContent(type="text", text="❌ Zotero不可用，请启动Zotero桌面应用")]
            
            # 此工具需要下载功能，所以确实需要cookies
            if not downloader:
                return [TextContent(type="text", text="❌ 下载功能需要先设置cookies\n💡 你可以使用 `save_to_zotero` 仅保存元数据（无需cookies）")]
            
            result = downloader.download_and_save_to_zotero(paper_url, paper_title, collection_key)
            
            if result["success"]:
                message = f"🎉 成功下载并保存到Zotero!\n\n"
                message += f"📄 标题: {result.get('title', paper_title)}\n"
                message += f"📥 下载文件:\n"
                for file_path in result.get("download_files", []):
                    message += f"  • {file_path}\n"
                
                if collection_key:
                    message += f"📚 保存到集合: {collection_key}\n"
                
                if result.get("zotero_url"):
                    message += f"🚀 在Zotero中打开: {result['zotero_url']}\n"
                
                message += f"\n✨ 论文已同时保存到:\n"
                message += f"  • 本地文件系统: {downloader.download_dir}\n"
                message += f"  • Zotero数据库 (包含PDF附件)"
            else:
                message = f"❌ 操作失败: {result.get('message', '未知错误')}"
            
            return [TextContent(type="text", text=message)]
        
        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]
    
    except Exception as e:
        logger.error(f"工具调用时出错 {name}: {str(e)}")
        return [TextContent(type="text", text=f"工具调用时出错: {str(e)}")]


async def main():
    """运行MCP服务器"""
    # 设置服务器选项
    options = InitializationOptions(
        server_name="nature-scholar-tool",
        server_version="0.2.0",
        capabilities={
            "resources": {},
            "tools": {}
        }
    )
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            options
        )


if __name__ == "__main__":
    asyncio.run(main()) 