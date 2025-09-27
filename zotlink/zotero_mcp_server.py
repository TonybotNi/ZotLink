#!/usr/bin/env python3
"""
🔗 ZotLink - 智能学术文献管理MCP工具

基于Zotero Connector官方源代码实现的智能文献管理系统
提供完整的学术文献管理功能，支持：
- 📄 arXiv论文自动处理（元数据 + PDF）
- 🎯 智能集合管理（updateSession机制）
- 📚 开放获取期刊支持
- 🤖 完全自动化的PDF下载
- 📝 完整的元数据提取（Comment、DOI、学科分类等）

技术特点：
- 无需cookies或登录认证
- 基于Zotero Connector官方API
- 支持treeViewID和updateSession机制
- 100%开源，易于维护
"""

import asyncio
import logging
import json
import sys
from typing import Any, Optional
from pathlib import Path

# MCP imports
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp import ClientSession
from mcp.server.stdio import stdio_server

# 本地导入
from .zotero_integration import ZoteroConnector
from .cookie_sync import CookieSyncManager

# 配置日志 - 写入到用户目录，避免只读安装路径
log_dir = Path.home() / '.zotlink'
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / 'zotlink.log'

# Windows 控制台常见 GBK 编码问题：仅向文件写日志，避免控制台 emoji 编码错误
handlers = [logging.FileHandler(log_file, encoding='utf-8')]
if sys.platform != 'win32':
    handlers.append(logging.StreamHandler(sys.stderr))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=handlers
)

logger = logging.getLogger(__name__)

# 全局Zotero连接器
zotero_connector = ZoteroConnector()

# 自动从文件加载可用的cookies
logger.info("🔄 正在加载共享的cookies...")
cookie_results = zotero_connector.load_cookies_from_files()
if cookie_results:
    success_count = sum(1 for v in cookie_results.values() if v)
    total_count = len(cookie_results)
    logger.info(f"📊 Cookie加载完成：{success_count}/{total_count} 个数据库")
else:
    logger.info("📄 暂无可用的共享cookies")

# 初始化Cookie同步管理器
cookie_sync_manager = CookieSyncManager(zotero_connector=zotero_connector)

# 🔄 同步已加载的cookies到CookieSyncManager
logger.info("🔄 同步已加载的cookies状态...")
if zotero_connector.extractor_manager and zotero_connector.extractor_manager.cookies_store:
    for db_name, cookies in zotero_connector.extractor_manager.cookies_store.items():
        if cookies and cookies.strip():
            # 将cookies同步到CookieSyncManager的数据库注册表
            cookie_sync_manager.database_registry.update_cookie_status(db_name, cookies)
            logger.info(f"✅ 同步{db_name}的cookies状态到认证管理器")

cookie_sync_manager.start()

# 创建MCP服务器
server = Server("zotlink")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """列出所有可用的Zotero工具"""
    return [
        types.Tool(
            name="check_zotero_status",
            description="检查Zotero桌面应用的连接状态和版本信息",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="get_zotero_collections",
            description="获取Zotero文献库中的所有集合/文件夹列表（树形结构显示）",
            inputSchema={
                "type": "object", 
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="save_paper_to_zotero",
            description="保存学术论文到Zotero（支持arXiv、DOI等，自动下载PDF和提取元数据）",
            inputSchema={
                "type": "object",
                "properties": {
                    "paper_url": {
                        "type": "string",
                        "description": "论文URL（支持arXiv、DOI链接等）"
                    },
                    "paper_title": {
                        "type": "string", 
                        "description": "论文标题（可选，会自动提取）"
                    },
                    "collection_key": {
                        "type": "string",
                        "description": "目标集合key（可选，不指定则保存到默认位置）"
                    }
                },
                "required": ["paper_url"]
            }
        ),
        types.Tool(
            name="create_zotero_collection",
            description="在Zotero中创建新的集合/文件夹（提供手动创建指导）",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "集合名称"
                    },
                    "parent_key": {
                        "type": "string",
                        "description": "父集合key（可选）"
                    }
                },
                "required": ["name"]
            }
        ),
        types.Tool(
            name="extract_arxiv_metadata",
            description="从arXiv URL提取完整的论文元数据（标题、作者、摘要、Comment、学科分类等）",
            inputSchema={
                "type": "object",
                "properties": {
                    "arxiv_url": {
                        "type": "string",
                        "description": "arXiv论文URL（abs或pdf页面）"
                    }
                },
                "required": ["arxiv_url"]
            }
        ),
        types.Tool(
            name="set_database_cookies",
            description="为特定学术数据库设置认证cookies（如Nature、Science等）",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_name": {
                        "type": "string",
                        "description": "数据库名称（如Nature、Science等）"
                    },
                    "cookies": {
                        "type": "string",
                        "description": "从浏览器复制的cookie字符串"
                    }
                },
                "required": ["database_name", "cookies"]
            }
        ),
        types.Tool(
            name="get_supported_databases",
            description="获取所有支持的学术数据库列表及其认证状态",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="get_databases_status",
            description="获取所有数据库的详细状态信息（包括登录URL、测试URL等）",
            inputSchema={
                "type": "object", 
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="update_database_cookies", 
            description="更新指定数据库的Cookie配置（支持nature、science、ieee、springer等）",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "数据库标识 (nature, science, ieee, springer)"
                    },
                    "cookies": {
                        "type": "string",
                        "description": "Cookie字符串，格式: name1=value1; name2=value2; name3=value3"
                    }
                },
                "required": ["database", "cookies"]
            }
        ),
        types.Tool(
            name="test_database_access",
            description="测试特定数据库的访问权限和认证状态",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_name": {
                        "type": "string",
                        "description": "要测试的数据库名称（如Nature、Science等）"
                    }
                },
                "required": ["database_name"]
            }
        ),
        types.Tool(
            name="get_cookie_guide",
            description="获取详细的cookie获取指南（用于访问商业数据库）",
            inputSchema={
                "type": "object",
                "properties": {
                    "database_name": {
                        "type": "string",
                        "description": "数据库名称（可选，如Nature、Science等）"
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_cookie_sync_status",
            description="获取Cookie自动同步服务的状态信息",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="get_database_auth_status",
            description="获取所有支持数据库的认证状态",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="get_authentication_guide",
            description="获取指定数据库的详细认证指南",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {
                        "type": "string",
                        "description": "数据库标识符（如nature、science、ieee等）"
                    }
                },
                "required": ["database"]
            }
        ),
        types.Tool(
            name="generate_bookmark_code",
            description="生成ZotLink书签代码，用于浏览器自动同步cookies",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """列出可用资源"""
    return [
        types.Resource(
            uri="zotero://status",
            name="Zotero连接状态",
            description="当前Zotero桌面应用的连接状态",
            mimeType="application/json"
        ),
        types.Resource(
            uri="zotero://collections",
            name="Zotero集合列表", 
            description="用户Zotero文献库中的所有集合",
            mimeType="application/json"
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """处理工具调用"""
    
    if name == "check_zotero_status":
        try:
            is_running = zotero_connector.is_running()
            version = zotero_connector.get_version()
            
            if is_running:
                collections_count = len(zotero_connector.get_collections())
                
                message = "🎉 **Zotero连接成功！**\n\n"
                message += f"📱 **应用状态**: ✅ Zotero桌面应用正在运行\n"
                message += f"📝 **版本信息**: {version}\n"
                message += f"📚 **集合数量**: {collections_count} 个\n"
                message += f"🔗 **API端点**: http://127.0.0.1:23119\n\n"
                # 获取支持的数据库
                databases = zotero_connector.get_supported_databases()
                
                message += f"✨ **支持的数据库** ({len(databases)}个):\n"
                for db in databases:
                    db_name = db.get('name', '未知')
                    auth_icon = "🔐" if db.get('requires_auth', False) else "🌐"
                    cookie_icon = "✅" if db.get('has_cookies', False) else "❌" if db.get('requires_auth', False) else "➖"
                    message += f"  {auth_icon} **{db_name}** {cookie_icon}\n"
                
                message += f"\n🛠️ **可用功能**:\n"
                message += f"  🎯 `save_paper_to_zotero` - 保存学术论文\n"
                message += f"  📚 `get_zotero_collections` - 查看集合列表\n"
                message += f"  🔬 `extract_arxiv_metadata` - arXiv元数据提取\n"
                message += f"  🌐 `get_supported_databases` - 查看支持的数据库\n"
                message += f"  🔐 `set_database_cookies` - 设置数据库认证\n"
                message += f"  🧪 `test_database_access` - 测试数据库访问\n"
                message += f"  ➕ `create_zotero_collection` - 创建新集合\n\n"
                message += f"🚀 **开始使用**: 查看支持的数据库并保存学术文献！"
            else:
                message = "❌ **Zotero未运行**\n\n"
                message += f"🔧 **解决方案**:\n"
                message += f"1. 启动Zotero桌面应用\n"
                message += f"2. 确保Zotero完全加载完成\n"
                message += f"3. 重新运行此检查\n\n"
                message += f"💡 **要求**: 需要Zotero 6.0以上版本"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            logger.error(f"检查Zotero状态失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 检查Zotero状态时出错: {e}")]
    
    elif name == "get_zotero_collections":
        try:
            if not zotero_connector.is_running():
                return [types.TextContent(type="text", text="❌ Zotero不可用，请启动Zotero桌面应用")]
            
            collections = zotero_connector.get_collections()
            
            if not collections:
                message = "📚 **集合管理**\n\n"
                message += "⚠️ 当前没有发现任何集合\n\n"
                message += "💡 **建议**:\n"
                message += "• 使用 `create_zotero_collection` 创建新集合\n"
                message += "• 或在Zotero桌面应用中手动创建集合"
                return [types.TextContent(type="text", text=message)]
            
            # 构建集合树形结构显示
            message = f"📚 **Zotero集合列表** (共{len(collections)}个)\n\n"
            
            # 构建层级结构
            root_collections = [c for c in collections if not c.get('parentCollection')]
            child_collections = [c for c in collections if c.get('parentCollection')]
            
            def format_collection(coll, level=0):
                indent = "  " * level
                name = coll.get('name', '未知集合')
                key = coll.get('key', '无key')
                
                # 显示带emoji和层级的集合名称
                formatted = f"{indent}📁 **{name}**\n"
                formatted += f"{indent}   🔑 Key: `{key}`\n"
                
                # 查找子集合
                children = [c for c in child_collections if c.get('parentCollection') == coll.get('id')]
                for child in children:
                    formatted += format_collection(child, level + 1)
                
                return formatted
            
            for root_coll in root_collections:
                message += format_collection(root_coll)
            
            message += f"\n💡 **使用方法**:\n"
            message += f"• 复制集合的Key值\n"
            message += f"• 在 `save_paper_to_zotero` 中指定 `collection_key`\n"
            message += f"• 论文将自动保存到指定集合中"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            logger.error(f"获取集合列表失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 获取集合列表失败: {e}")]
    
    elif name == "save_paper_to_zotero":
        paper_url = arguments.get("paper_url")
        paper_title = arguments.get("paper_title", "")
        collection_key = arguments.get("collection_key")
        
        if not paper_url:
            return [types.TextContent(type="text", text="❌ 缺少论文URL")]
        
        if not zotero_connector.is_running():
            return [types.TextContent(type="text", text="❌ Zotero不可用，请启动Zotero桌面应用")]
        
        try:
            # 构建论文信息
            paper_info = {
                "title": paper_title,
                "url": paper_url
            }
            
            # 处理进度提示
            if 'arxiv.org' in paper_url:
                logger.info("开始处理arXiv论文")
            
            result = zotero_connector.save_item_to_zotero(paper_info, collection_key=collection_key)
            
            if result["success"]:
                message = f"🎉 **论文保存成功！**\n\n"
                
                # 显示使用的数据库
                database = result.get("database", "未知")
                enhanced = result.get("enhanced", False)
                
                message += f"🔗 **数据库**: {database}\n"
                message += f"🤖 **智能增强**: {'✅ 是' if enhanced else '➖ 否'}\n"
                
                # 检查是否是arXiv论文
                if 'arxiv.org' in paper_url:
                    import re
                    arxiv_match = re.search(r'arxiv\.org/(abs|pdf)/([^/?]+)', paper_url)
                    if arxiv_match:
                        arxiv_id = arxiv_match.group(2)
                        message += f"📄 **论文类型**: arXiv预印本\n"
                        message += f"🏷️ **arXiv ID**: {arxiv_id}\n"
                        # 🎯 优先使用返回结果中的标题，如果没有则使用原始标题
                        actual_title = result.get('title') or paper_title or f'arXiv:{arxiv_id} (标题提取中...)'
                        message += f"📄 **标题**: {actual_title}\n"
                        message += f"🔗 **原始链接**: {paper_url}\n"
                        message += f"📥 **PDF链接**: https://arxiv.org/pdf/{arxiv_id}.pdf\n"
                elif database and database != 'arXiv':
                    message += f"📄 **论文类型**: {database}期刊文章\n"
                    # 🎯 修复：优先使用返回结果中的标题，而非空的paper_title
                    actual_title = result.get('title') or paper_title or '标题提取中...'
                    message += f"📄 **标题**: {actual_title}\n"
                    message += f"🔗 **原始链接**: {paper_url}\n"
                else:
                    # 🎯 修复：统一使用result.get('title')逻辑
                    actual_title = result.get('title') or paper_title or '标题提取中...'
                    message += f"📄 **标题**: {actual_title}\n"
                    message += f"🔗 **URL**: {paper_url}\n"
                
                # 集合保存状态
                if collection_key:
                    # 🔧 修复字段名不一致问题: 使用正确的collection_moved字段
                    collection_moved = result.get("details", {}).get("collection_moved", False)
                    if collection_moved:
                        message += f"✅ **集合保存**: 已自动移动到指定集合\n"
                        message += f"🎯 **技术突破**: 使用updateSession官方机制\n"
                    else:
                        message += f"⚠️ **集合保存**: 移动失败，条目在默认位置\n"
                        message += f"📋 **手动操作**: 请在Zotero中拖拽条目到目标集合\n"
                else:
                    message += f"📚 **保存位置**: 我的文库（默认位置）\n"
                
                # 📊 PDF状态详细分析（新格式）
                details = result.get("details", {})
                pdf_downloaded = details.get("pdf_downloaded", False)
                pdf_error = details.get("pdf_error")
                pdf_method = details.get("pdf_method", "link_attachment")
                
                if pdf_downloaded and pdf_method == "attachment":
                    message += f"📄 **PDF文件**: ✅ 已成功下载并保存为附件\n"
                    message += f"   🎉 **完美**: PDF文件已作为独立附件保存到Zotero中\n"
                elif pdf_method == "failed":
                    if "biorxiv.org" in paper_url.lower():
                        message += f"📄 **PDF附件**: 🧬 bioRxiv高级下载尝试失败\n"
                        message += f"   💡 **技术说明**: 已尝试MCP高级浏览器技术，但本次下载未成功\n"
                        message += f"   🔄 **可能原因**: 网络延迟、服务器负载或反爬虫检测加强\n"
                        message += f"   🔗 **建议解决方案**: \n"
                        message += f"   1. 稍后重试（网络状况可能影响成功率）\n"
                        message += f"   2. 使用浏览器官方Zotero插件作为备选方案\n"
                    else:
                        message += f"📄 **PDF附件**: ⚠️ 保存失败（可能是网络或服务器临时问题）\n"
                        message += f"   💡 **说明**: 元数据已保存，您可以稍后手动添加PDF附件\n"
                elif pdf_method == "none":
                    message += f"📄 **PDF附件**: ℹ️ 未发现PDF链接\n"
                else:
                    message += f"📄 **PDF附件**: ⚠️ 处理异常\n"
                
                if result.get("extra_preserved"):
                    message += f"📝 **元数据**: ✅ 完整提取（Comment、学科分类、DOI等）\n"
                
                message += f"\n📋 **立即验证**:\n"
                details = result.get("details", {})
                if details.get("collection_moved"):
                    message += f"🎯 **成功！论文已在指定集合中**\n"
                    message += f"1. 打开Zotero桌面应用\n"
                    message += f"2. 查看指定集合中的新条目\n"
                    message += f"3. 确认PDF附件和元数据完整性\n"
                elif collection_key:
                    message += f"⚠️ **论文已保存，但集合移动可能需要确认**\n"
                    message += f"1. 打开Zotero桌面应用\n"
                    message += f"2. 首先在指定集合中查找\n"
                    message += f"3. 如未找到，在'我的文库'中查找并手动移动\n"
                else:
                    message += f"✅ **论文已保存到默认位置**\n"
                    message += f"1. 打开Zotero桌面应用\n"
                    message += f"2. 在'我的文库'中找到新条目\n"
                    message += f"3. 如需要，可移动到指定集合\n"
                
                message += f"\n🎉 **完成！享受完整的学术文献管理体验！**"
                
            else:
                message = f"❌ **保存失败**: {result.get('message', '未知错误')}\n\n"
                message += f"🔧 **故障排除**:\n"
                message += f"• 确保Zotero桌面应用正在运行\n"
                message += f"• 检查网络连接\n"
                message += f"• 验证论文URL是否有效\n"
                message += f"• 尝试重新启动Zotero应用"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            logger.error(f"保存论文失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 保存论文时出错: {e}")]
    
    elif name == "create_zotero_collection":
        collection_name = arguments.get("name", "").strip()
        parent_key = arguments.get("parent_key", "").strip() or None
        
        if not collection_name:
            return [types.TextContent(type="text", text="❌ 缺少集合名称")]
        
        if not zotero_connector.is_running():
            return [types.TextContent(type="text", text="❌ Zotero不可用，请启动Zotero桌面应用")]
        
        # 由于Zotero Connector API限制，提供手动创建指导
        message = f"📁 **创建Zotero集合指导**\n\n"
        message += f"💡 **注意**: 由于Zotero API限制，需要手动创建集合\n\n"
        message += f"🎯 **手动创建步骤**：\n"
        message += f"1. 📱 打开**Zotero桌面应用**\n"
        message += f"2. 🖱️ 右键点击左侧集合区域\n"
        message += f"3. ➕ 选择 **\"新建集合\"**\n"
        message += f"4. 📝 输入集合名称：**{collection_name}**\n"
        
        if parent_key:
            message += f"5. 📁 可选：拖拽到父集合下\n"
        
        message += f"6. ✅ 确认创建\n\n"
        message += f"📚 **创建完成后**：\n"
        message += f"• 使用 `get_zotero_collections` 获取新集合的Key\n"
        message += f"• 使用Key在 `save_paper_to_zotero` 中指定目标集合\n\n"
        message += f"⏱️ **只需30秒，一次创建，长期使用！**"
        
        return [types.TextContent(type="text", text=message)]
    
    elif name == "extract_arxiv_metadata":
        arxiv_url = arguments.get("arxiv_url")
        
        if not arxiv_url:
            return [types.TextContent(type="text", text="❌ 缺少arXiv URL")]
        
        if 'arxiv.org' not in arxiv_url:
            return [types.TextContent(type="text", text="❌ 无效的arXiv URL")]
        
        try:
            metadata = zotero_connector._extract_arxiv_metadata(arxiv_url)
            
            if 'error' in metadata:
                return [types.TextContent(type="text", text=f"❌ 提取失败: {metadata['error']}")]
            
            message = f"📄 **arXiv论文元数据**\n\n"
            message += f"🏷️ **arXiv ID**: {metadata.get('arxiv_id', '未知')}\n"
            message += f"📝 **标题**: {metadata.get('title', '未知')}\n"
            message += f"👥 **作者**: {metadata.get('authors_string', '未知')}\n"
            message += f"📅 **日期**: {metadata.get('date', '未知')}\n"
            
            if metadata.get('comment'):
                message += f"📋 **Comment**: {metadata['comment']}\n"
            
            if metadata.get('subjects'):
                subjects_str = ', '.join(metadata['subjects'][:3])
                message += f"🔬 **学科分类**: {subjects_str}\n"
            
            if metadata.get('doi'):
                message += f"🔗 **DOI**: {metadata['doi']}\n"
            
            message += f"🔗 **PDF链接**: {metadata.get('pdf_url', '未知')}\n"
            
            if metadata.get('abstract'):
                abstract_preview = metadata['abstract'][:200] + "..." if len(metadata['abstract']) > 200 else metadata['abstract']
                message += f"\n📖 **摘要预览**:\n{abstract_preview}\n"
            
            message += f"\n💡 **下一步**: 使用 `save_paper_to_zotero` 保存到文献库"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            logger.error(f"提取arXiv元数据失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 提取元数据时出错: {e}")]
    
    elif name == "set_database_cookies":
        database_name = arguments.get("database_name", "").strip()
        cookies = arguments.get("cookies", "").strip()
        
        if not database_name or not cookies:
            return [types.TextContent(type="text", text="❌ 缺少数据库名称或cookies")]
        
        try:
            success = zotero_connector.set_database_cookies(database_name, cookies)
            
            if success:
                message = f"✅ **{database_name} Cookies设置成功！**\n\n"
                message += f"🔐 **数据库**: {database_name}\n"
                message += f"📝 **状态**: 认证信息已保存\n\n"
                message += f"🚀 **下一步**: 使用 `test_database_access` 验证访问权限\n"
                message += f"💡 **然后**: 可以保存{database_name}的论文到Zotero了！"
            else:
                message = f"❌ **{database_name} Cookies设置失败**\n\n"
                message += f"🔧 **可能原因**:\n"
                message += f"• Cookie格式不正确\n"
                message += f"• 不支持的数据库名称\n"
                message += f"• 网络连接问题\n\n"
                message += f"💡 **建议**: 检查cookie格式并重试"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            logger.error(f"设置{database_name} cookies失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 设置cookies时出错: {e}")]
    
    elif name == "get_supported_databases":
        try:
            databases = zotero_connector.get_supported_databases()
            
            message = f"🌐 **ZotLink支持的学术数据库**\n\n"
            
            for db in databases:
                db_name = db.get('name', '未知')
                requires_auth = db.get('requires_auth', False)
                has_cookies = db.get('has_cookies', False)
                
                auth_status = "🔐 需要认证" if requires_auth else "🌐 开放访问"
                cookie_status = "✅ 已配置" if has_cookies else "❌ 未配置" if requires_auth else "➖ 无需配置"
                
                message += f"### {db_name}\n"
                message += f"📊 **访问类型**: {auth_status}\n"
                message += f"🍪 **Cookie状态**: {cookie_status}\n"
                
                if db.get('supported_types'):
                    types_str = ', '.join(db['supported_types'][:3])
                    message += f"📝 **支持类型**: {types_str}\n"
                
                message += f"\n"
            
            message += f"💡 **使用说明**:\n"
            message += f"• 🌐 **开放访问**数据库可直接使用\n"
            message += f"• 🔐 **需要认证**的数据库需先设置cookies\n"
            message += f"• 🍪 使用 `set_database_cookies` 设置认证信息\n"
            message += f"• 🧪 使用 `test_database_access` 验证访问权限"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            logger.error(f"获取支持的数据库失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 获取数据库信息时出错: {e}")]
    
    elif name == "test_database_access":
        database_name = arguments.get("database_name", "").strip()
        
        if not database_name:
            return [types.TextContent(type="text", text="❌ 缺少数据库名称")]
        
        try:
            result = zotero_connector.test_database_access(database_name)
            
            db_name = result.get('database', database_name)
            status = result.get('status', 'unknown')
            message_text = result.get('message', '未知状态')
            
            if status == 'success':
                message = f"🎉 **{db_name} 访问测试成功！**\n\n"
                message += f"✅ **状态**: 访问正常\n"
                message += f"🔗 **数据库**: {db_name}\n"
                message += f"💡 **说明**: {message_text}\n\n"
                message += f"🚀 **现在可以**:\n"
                message += f"• 使用 `save_paper_to_zotero` 保存{db_name}的论文\n"
                message += f"• 自动下载PDF和提取元数据\n"
                message += f"• 保存到指定的Zotero集合"
            elif status == 'no_cookies':
                message = f"🔐 **{db_name} 需要认证**\n\n"
                message += f"⚠️ **状态**: 未设置认证信息\n"
                message += f"💡 **说明**: {message_text}\n\n"
                message += f"📋 **下一步**:\n"
                message += f"1. 在浏览器中登录{db_name}网站\n"
                message += f"2. 复制cookie信息\n"
                message += f"3. 使用 `set_database_cookies` 设置认证\n"
                message += f"4. 重新测试访问权限"
            elif status == 'access_denied':
                message = f"❌ **{db_name} 访问被拒绝**\n\n"
                message += f"🚫 **状态**: {message_text}\n"
                message += f"🔧 **可能原因**:\n"
                message += f"• Cookies已过期\n"
                message += f"• 需要重新登录\n"
                message += f"• 机构访问权限问题\n\n"
                message += f"💡 **建议**: 重新获取cookies并更新"
            else:
                message = f"⚠️ **{db_name} 状态未知**\n\n"
                message += f"❓ **状态**: {status}\n"
                message += f"💬 **说明**: {message_text}"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            logger.error(f"测试{database_name}访问失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 测试访问时出错: {e}")]
    
    elif name == "get_cookie_guide":
        database_name = arguments.get("database_name", "").strip()
        
        message = f"🍪 **学术数据库Cookie获取指南**\n\n"
        
        if database_name and database_name.lower() == "nature":
            message += f"🔬 **Nature网站Cookie获取指南**\n\n"
            message += f"### 📋 详细步骤（Chrome推荐）：\n\n"
            message += f"1. **🌐 登录Nature网站**\n"
            message += f"   • 访问 https://www.nature.com\n"
            message += f"   • 使用机构账号或个人订阅登录\n"
            message += f"   • 确保能正常访问付费内容\n\n"
            message += f"2. **🛠️ 打开开发者工具**\n"
            message += f"   • 按 `F12` 或右键 → 检查\n"
            message += f"   • 进入 `Network` 标签页\n\n"
            message += f"3. **🔄 刷新页面**\n"
            message += f"   • 按 `F5` 刷新Nature首页\n"
            message += f"   • 等待网络请求加载完成\n\n"
            message += f"4. **📋 复制Cookie**\n"
            message += f"   • 选择任意一个请求\n"
            message += f"   • 在右侧找到 `Request Headers`\n"
            message += f"   • 找到 `Cookie:` 行\n"
            message += f"   • **复制冒号后的全部内容**\n\n"
            message += f"5. **✅ 设置到ZotLink**\n"
            message += f"   • 使用 `set_database_cookies` 工具\n"
            message += f"   • database_name: \"Nature\"\n"
            message += f"   • cookies: [粘贴复制的内容]\n\n"
        else:
            message += f"### 🌐 **通用Cookie获取方法**：\n\n"
            message += f"#### 方法1: Chrome开发者工具 (推荐)\n"
            message += f"1. 在Chrome中访问并登录目标数据库网站\n"
            message += f"2. 按 `F12` 打开开发者工具\n"
            message += f"3. 进入 `Network` 标签页\n"
            message += f"4. 刷新页面（`F5`）\n"
            message += f"5. 选择任意请求\n"
            message += f"6. 在右侧找到 `Request Headers`\n"
            message += f"7. 复制 `Cookie:` 后面的全部内容\n\n"
            message += f"#### 方法2: Application标签\n"
            message += f"1. 按 `F12` 打开开发者工具\n"
            message += f"2. 进入 `Application` 标签页\n"
            message += f"3. 左侧选择 `Storage` > `Cookies` > 目标网站\n"
            message += f"4. 手动复制所有cookies\n\n"
            message += f"#### 方法3: 浏览器扩展\n"
            message += f"安装 \"Cookie Editor\" 等扩展，一键导出cookies\n\n"
        
        message += f"### 🎯 **支持的数据库**：\n"
        try:
            databases = zotero_connector.get_supported_databases()
            for db in databases:
                if db.get('requires_auth'):
                    auth_status = "✅ 已配置" if db.get('has_cookies') else "❌ 需要配置"
                    message += f"• **{db['name']}**: 🔐 需要cookies {auth_status}\n"
                else:
                    message += f"• **{db['name']}**: 🌐 开放访问，无需cookies\n"
        except:
            message += f"• **Nature**: 🔐 需要cookies\n"
            message += f"• **arXiv**: 🌐 开放访问，无需cookies\n"
        
        message += f"\n💡 **提示**：cookies通常7-30天过期，需要定期更新\n"
        message += f"🔧 **下一步**：设置cookies后使用 `test_database_access` 验证"
        
        return [types.TextContent(type="text", text=message)]
    
    elif name == "get_cookie_sync_status":
        try:
            status = cookie_sync_manager.get_comprehensive_status()
            
            message = f"🔄 **Cookie自动同步服务状态**\n\n"
            
            # 同步管理器状态
            sync_status = status['sync_manager']
            message += f"### 📊 同步服务状态\n"
            message += f"• **运行状态**: {'🟢 运行中' if sync_status['running'] else '🔴 已停止'}\n"
            message += f"• **同步功能**: {'🟢 启用' if sync_status['sync_enabled'] else '🔴 禁用'}\n\n"
            
            # HTTP接收服务状态
            receiver_status = status['receiver']
            message += f"### 🌐 HTTP接收服务\n"
            message += f"• **服务状态**: {'🟢 运行中' if receiver_status['running'] else '🔴 已停止'}\n"
            message += f"• **监听端口**: {receiver_status['port']}\n"
            message += f"• **服务地址**: {receiver_status['url']}\n"
            message += f"• **待处理队列**: {receiver_status['pending_cookies']} 个\n\n"
            
            # 统计信息
            stats = status['statistics']
            message += f"### 📈 同步统计\n"
            message += f"• **总接收**: {stats['total_received']} 次\n"
            message += f"• **成功应用**: {stats['successfully_applied']} 次\n"
            message += f"• **失败次数**: {stats['failed_applications']} 次\n"
            message += f"• **成功率**: {stats['success_rate']:.1f}%\n"
            message += f"• **运行时长**: {stats['uptime_formatted']}\n"
            if stats.get('last_sync'):
                message += f"• **最后同步**: {stats['last_sync'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ 获取同步状态失败: {e}")]
    
    elif name == "get_database_auth_status":
        try:
            db_status = cookie_sync_manager.get_database_status()
            
            message = f"🔐 **数据库认证状态**\n\n"
            
            authenticated_count = 0
            total_count = len(db_status)
            
            for identifier, status in db_status.items():
                status_icon = "🟢" if status.get('has_cookies') else "🔴"
                auth_status = status.get('status', '未知')
                
                message += f"### {status_icon} {status['name']}\n"
                message += f"• **状态**: {auth_status}\n"
                message += f"• **域名**: {', '.join(status.get('domains', []))}\n"
                
                if status.get('has_cookies'):
                    authenticated_count += 1
                    if status.get('expires_at'):
                        message += f"• **有效期**: {status['expires_at'].strftime('%Y-%m-%d %H:%M')}\n"
                    if status.get('cookie_count'):
                        message += f"• **Cookie数量**: {status['cookie_count']} 个\n"
                else:
                    message += f"• **登录页面**: {status.get('login_url', 'N/A')}\n"
                
                message += f"\n"
            
            message += f"📊 **总览**: {authenticated_count}/{total_count} 个数据库已认证\n\n"
            
            if authenticated_count < total_count:
                expired_dbs = cookie_sync_manager.get_expired_databases()
                if expired_dbs:
                    message += f"⚠️ **需要更新认证的数据库**: {', '.join(expired_dbs)}\n"
                    message += f"💡 **建议**: 使用 `generate_bookmark_code` 获取书签，然后登录相应网站点击书签自动同步\n"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ 获取认证状态失败: {e}")]
    
    elif name == "get_authentication_guide":
        database = arguments.get("database", "").lower()
        
        if not database:
            return [types.TextContent(type="text", text="❌ 请指定数据库标识符")]
        
        try:
            guide = cookie_sync_manager.get_authentication_guide(database)
            
            if "error" in guide:
                return [types.TextContent(type="text", text=f"❌ {guide['error']}")]
            
            message = f"🔐 **{guide['database']} 认证指南**\n\n"
            
            if guide.get('current_status'):
                message += f"### 📊 当前状态\n{guide['current_status']}\n\n"
            else:
                message += f"### 📊 当前状态\n❌ 未认证\n\n"
            
            message += f"### 📋 认证步骤\n"
            for step in guide.get('steps', []):
                message += f"{step}\n"
            
            message += f"\n### 🔗 相关链接\n"
            message += f"• **登录页面**: {guide.get('login_url')}\n"
            
            bookmark_info = guide.get('bookmark_info', {})
            if bookmark_info.get('status') == '运行中':
                message += f"• **同步服务**: ✅ {bookmark_info['status']} ({bookmark_info['service_url']})\n"
            else:
                message += f"• **同步服务**: ❌ 未运行，请确保ZotLink正在运行\n"
            
            message += f"\n💡 **提示**: 使用 `generate_bookmark_code` 获取书签代码，添加到浏览器收藏夹后即可一键同步认证信息"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ 获取认证指南失败: {e}")]
    
    elif name == "get_databases_status":
        try:
            databases_status = zotero_connector.get_databases_status()
            
            if not databases_status:
                return [types.TextContent(type="text", text="❌ 没有找到数据库配置信息")]
            
            message = f"📊 **数据库详细状态信息**\n\n"
            
            for db_key, status in databases_status.items():
                db_name = status.get('name', db_key)
                status_flag = status.get('status', 'inactive')
                cookie_count = status.get('cookie_count', 0)
                last_updated = status.get('last_updated', '未知')
                domains = status.get('domains', [])
                description = status.get('description', '')
                login_url = status.get('login_url', '')
                test_url = status.get('test_url', '')
                
                status_icon = "✅" if status_flag == "active" else "❌"
                
                message += f"### {status_icon} {db_name} (`{db_key}`)\n"
                message += f"📊 **状态**: {status_flag}\n"
                message += f"🍪 **Cookie数量**: {cookie_count}\n"
                message += f"⏰ **更新时间**: {last_updated}\n"
                message += f"🌐 **域名**: {', '.join(domains) if domains else '无'}\n"
                
                if description:
                    message += f"📝 **描述**: {description}\n"
                
                if login_url:
                    message += f"🔗 **登录页面**: {login_url}\n"
                    
                if test_url:
                    message += f"🧪 **测试链接**: {test_url}\n"
                
                message += f"\n"
            
            message += f"💡 **管理说明**:\n"
            message += f"• 使用 `update_database_cookies` 更新Cookie\n"
            message += f"• Cookie格式: `name1=value1; name2=value2`\n"
            message += f"• 从浏览器开发者工具获取Cookie字符串\n\n"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            logger.error(f"获取数据库状态失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 获取数据库状态时出错: {e}")]
    
    elif name == "update_database_cookies":
        try:
            database = arguments.get("database")
            cookies = arguments.get("cookies")
            
            if not database:
                return [types.TextContent(type="text", text="❌ 请指定数据库名称")]
                
            if not cookies:
                return [types.TextContent(type="text", text="❌ 请提供Cookie字符串")]
            
            # 更新数据库Cookie
            success = zotero_connector.update_database_cookies(database, cookies)
            
            if success:
                cookie_count = len(cookies.split(';'))
                message = f"✅ **{database.upper()}数据库Cookie更新成功！**\n\n"
                message += f"📊 **更新信息**:\n"
                message += f"• 🍪 Cookie数量: {cookie_count}\n" 
                message += f"• ⏰ 更新时间: 刚刚\n"
                message += f"• 📊 状态: 已激活\n\n"
                message += f"💡 **下一步**:\n"
                message += f"• 使用 `test_database_access` 测试访问权限\n"
                message += f"• 尝试保存论文测试功能\n"
                
                return [types.TextContent(type="text", text=message)]
            else:
                return [types.TextContent(type="text", text=f"❌ 更新{database}数据库Cookie失败")]
                
        except Exception as e:
            logger.error(f"更新数据库cookies失败: {e}")
            return [types.TextContent(type="text", text=f"❌ 更新Cookie时出错: {e}")]
    
    elif name == "generate_bookmark_code":
        try:
            # 读取书签JavaScript代码
            bookmark_file = Path(__file__).parent / "browser_bookmarks" / "zotlink_sync_bookmarklet.js"
            
            if not bookmark_file.exists():
                # 如果文件不存在，生成简化版本
                bookmark_code = """javascript:(function(){
    const ZOTLINK_URL='http://localhost:23120';
    const site=location.hostname;
    const cookies=document.cookie;
    if(!cookies){alert('请先登录网站');return;}
    fetch(ZOTLINK_URL+'/cookies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({site:site,siteName:site,cookies:cookies,url:location.href,timestamp:new Date().toISOString()})}).then(r=>r.json()).then(d=>alert('✅ 认证信息已同步到ZotLink')).catch(e=>alert('❌ 同步失败: '+e.message));
})();"""
            else:
                with open(bookmark_file, 'r', encoding='utf-8') as f:
                    bookmark_code = f.read().strip()
            
            receiver_status = cookie_sync_manager.get_receiver_status()
            
            message = f"🔖 **ZotLink自动同步书签**\n\n"
            
            if receiver_status.get('running'):
                message += f"### ✅ 服务状态正常\n"
                message += f"Cookie接收服务正在运行: {receiver_status['url']}\n\n"
            else:
                message += f"### ❌ 服务未运行\n"
                message += f"请确保ZotLink正在运行，然后重新生成书签\n\n"
                
            message += f"### 📋 使用步骤\n"
            message += f"1. **复制书签代码**（见下方）\n"
            message += f"2. **添加到浏览器**：\n"
            message += f"   - 右键收藏夹栏 → 添加书签\n"
            message += f"   - 名称：`ZotLink同步助手`\n"
            message += f"   - URL：粘贴下方代码\n"
            message += f"3. **使用方法**：\n"
            message += f"   - 登录Nature/Science/IEEE等学术网站\n"
            message += f"   - 点击书签即可自动同步认证信息\n\n"
            
            message += f"### 🎯 支持的网站\n"
            message += f"• Nature (nature.com)\n"
            message += f"• Science (science.org)\n"
            message += f"• IEEE (ieeexplore.ieee.org)\n"
            message += f"• Springer (link.springer.com)\n\n"
            
            message += f"### 📝 书签代码\n"
            message += f"```javascript\n{bookmark_code}\n```\n\n"
            
            message += f"💡 **使用技巧**：\n"
            message += f"- 书签会在页面右上角显示同步状态\n"
            message += f"- 同步成功后可立即在Claude Desktop中下载论文\n"
            message += f"- 如果同步失败，请检查ZotLink是否正在运行"
            
            return [types.TextContent(type="text", text=message)]
            
        except Exception as e:
            return [types.TextContent(type="text", text=f"❌ 生成书签代码失败: {e}")]
    
    else:
        return [types.TextContent(type="text", text=f"❌ 未知工具: {name}")]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """读取资源"""
    if uri == "zotero://status":
        status = {
            "running": zotero_connector.is_running(),
            "version": zotero_connector.get_version(),
            "collections_count": len(zotero_connector.get_collections()) if zotero_connector.is_running() else 0
        }
        return json.dumps(status, indent=2)
    
    elif uri == "zotero://collections":
        collections = zotero_connector.get_collections() if zotero_connector.is_running() else []
        return json.dumps(collections, indent=2, ensure_ascii=False)
    
    else:
        raise ValueError(f"未知资源: {uri}")

async def main():
    """启动服务器"""
    logger.info("🔗 启动ZotLink服务器...")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="zotlink",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

def run():
    """同步入口（供 console_scripts 调用）"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    run()