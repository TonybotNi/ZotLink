#!/usr/bin/env python3
"""
增强版浏览器提取器 - 基于Zotero Connector策略
借鉴官方插件的下载监控和反爬虫绕过机制
"""

import asyncio
import logging
import os
import tempfile
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from pathlib import Path

logger = logging.getLogger(__name__)

class EnhancedBrowserExtractor:
    """增强版浏览器提取器，实现类似Zotero Connector的功能"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.playwright = await async_playwright().start()
        
        # 🚀 关键改进：使用更接近真实浏览器的配置
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--allow-running-insecure-content',
                '--disable-features=VizDisplayCompositor',
                '--disable-blink-features=AutomationControlled',
                '--disable-automation-controlled',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-popup-blocking',
                '--single-process',  # 避免进程管理问题
                '--enable-features=NetworkService,NetworkServiceLogging'
            ],
            ignore_default_args=['--enable-automation'],
            timeout=60000
        )
        
        # 创建上下文，模拟真实用户环境
        self.context = await self.browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            accept_downloads=True,  # 允许下载
            has_touch=False,
            is_mobile=False,
            bypass_csp=True  # 绕过CSP限制
        )
        
        # 设置全局下载路径
        self.download_path = tempfile.mkdtemp()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"清理资源时出现问题: {e}")
        
        # 清理临时下载目录
        try:
            import shutil
            if hasattr(self, 'download_path') and os.path.exists(self.download_path):
                shutil.rmtree(self.download_path)
        except Exception as e:
            logger.warning(f"清理下载目录失败: {e}")
    
    async def extract_with_zotero_strategy(self, url: str) -> Dict[str, Any]:
        """使用类似Zotero Connector的策略提取内容"""
        logger.info(f"🚀 使用Zotero Connector策略处理: {url}")
        
        try:
            page = await self.context.new_page()
            
            # 🎯 步骤1: 智能页面导航和等待
            await self._smart_page_navigation(page, url)
            
            # 🎯 步骤2: 提取元数据
            metadata = await self._extract_metadata_zotero_style(page, url)
            
            # 🎯 步骤3: 下载PDF（使用下载监控）
            if metadata.get('pdf_url'):
                pdf_content = await self._download_with_monitoring(page, metadata['pdf_url'])
                if pdf_content:
                    metadata['pdf_content'] = pdf_content
            
            await page.close()
            return metadata
            
        except Exception as e:
            logger.error(f"Zotero策略提取失败: {e}")
            return {}
    
    async def _smart_page_navigation(self, page: Page, url: str):
        """智能页面导航，处理反爬虫"""
        logger.info("🌐 开始智能页面导航...")
        
        # 设置页面属性
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 导航到页面
        timeout_ms = 45000 if 'osf.io' in url else 25000
        await page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
        
        # 检测并处理反爬虫页面
        await self._handle_bot_protection(page)
        
        # OSF平台特殊处理
        if 'osf.io' in url:
            await self._handle_osf_loading(page)
    
    async def _handle_bot_protection(self, page: Page):
        """处理反爬虫保护 - 类似Zotero的处理方式"""
        try:
            title = await page.title()
            if any(phrase in title.lower() for phrase in ['just a moment', 'checking', 'please wait', 'cloudflare']):
                logger.info("🛡️ 检测到反爬虫页面，启用绕过策略...")
                
                # 模拟人类行为
                await asyncio.sleep(2)
                await page.mouse.move(100, 100)
                await asyncio.sleep(1)
                
                # 等待反爬虫页面自动跳转（最多30秒）
                for i in range(15):
                    await asyncio.sleep(2)
                    new_title = await page.title()
                    if 'just a moment' not in new_title.lower():
                        logger.info(f"✅ 反爬虫页面已绕过: {new_title[:50]}...")
                        break
                    logger.info(f"⏳ 等待反爬虫检查完成... ({i+1}/15)")
                
                # 额外的人类行为模拟
                await page.mouse.move(200, 200)
                await page.evaluate("window.scrollTo(0, 300)")
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, 0)")
                
        except Exception as e:
            logger.info(f"反爬虫处理异常: {e}")
    
    async def _handle_osf_loading(self, page: Page):
        """处理OSF平台的Ember应用加载 - 增强版等待策略"""
        logger.info("🔧 处理OSF Ember应用加载...")
        
        try:
            # 等待Ember应用容器
            await page.wait_for_selector('.ember-application, .ember-view', timeout=15000)
            logger.info("✅ Ember容器加载完成")
            
            # 🚀 关键改进：循环等待直到标题真正加载
            max_attempts = 20  # 最多等待40秒
            for attempt in range(max_attempts):
                await asyncio.sleep(2)
                
                title = await page.title()
                logger.info(f"第{attempt+1}次检查 - 当前标题: {title}")
                
                # 检查标题是否真正加载（包含论文信息）
                if title and '|' in title and len(title) > 20:
                    logger.info(f"✅ OSF内容加载完成: {title[:50]}...")
                    break
                
                # 检查是否有H1标题出现
                h1_text = await page.evaluate("document.querySelector('h1')?.textContent?.trim() || ''")
                if h1_text and len(h1_text) > 10:
                    logger.info(f"✅ 发现H1标题: {h1_text[:50]}...")
                    break
                
                # 每5次尝试后触发页面交互
                if (attempt + 1) % 5 == 0:
                    logger.info("🔄 触发页面交互以促进加载...")
                    await page.evaluate("window.scrollTo(0, 300)")
                    await asyncio.sleep(1)
                    await page.evaluate("window.scrollTo(0, 0)")
                    
                    # 尝试点击可能的加载按钮或链接
                    try:
                        # 检查是否有"show more"或类似的按钮
                        await page.evaluate("""
                            const buttons = document.querySelectorAll('button, a');
                            for (const btn of buttons) {
                                const text = btn.textContent.toLowerCase();
                                if (text.includes('load') || text.includes('show') || text.includes('expand')) {
                                    btn.click();
                                    break;
                                }
                            }
                        """)
                    except:
                        pass
                
                if attempt == max_attempts - 1:
                    logger.warning("⚠️ OSF内容等待超时，使用当前状态")
            
        except Exception as e:
            logger.info(f"OSF加载处理异常: {e}")
    
    async def _extract_metadata_zotero_style(self, page: Page, url: str) -> Dict[str, Any]:
        """使用类似Zotero的方式提取元数据"""
        logger.info("📊 使用Zotero风格提取元数据...")
        
        metadata = {}
        
        # 执行JavaScript提取
        result = await page.evaluate("""
            () => {
                const data = {
                    title: '',
                    authors: '',
                    abstract: '',
                    DOI: '',
                    pdf_url: '',
                    date: '',
                    publicationTitle: ''
                };
                
                // 优先从页面标题提取
                if (document.title) {
                    data.title = document.title;
                    
                    // OSF格式特殊处理
                    if (document.title.includes('|') && window.location.hostname === 'osf.io') {
                        data.title = document.title.split('|')[1].trim();
                    }
                }
                
                // 从H1提取标题（备用）
                if (!data.title || data.title === 'OSF') {
                    const h1 = document.querySelector('h1');
                    if (h1) data.title = h1.textContent.trim();
                }
                
                // Citation meta标签提取
                const citationMeta = {
                    'citation_title': 'title',
                    'citation_author': 'authors',
                    'citation_publication_date': 'date',
                    'citation_doi': 'DOI',
                    'citation_pdf_url': 'pdf_url',
                    'citation_abstract_html_url': 'url'
                };
                
                for (const [metaName, field] of Object.entries(citationMeta)) {
                    const elements = document.querySelectorAll(`meta[name="${metaName}"]`);
                    if (elements.length > 0) {
                        if (metaName === 'citation_author') {
                            data.authors = Array.from(elements).map(el => el.content).join('; ');
                        } else {
                            data[field] = elements[0].content || data[field];
                        }
                    }
                }
                
                // OSF特殊处理：PDF链接构造
                if (window.location.hostname === 'osf.io' && !data.pdf_url) {
                    const pathMatch = window.location.pathname.match(/\/preprints\/\\w+\/([^\\/]+)/);
                    if (pathMatch) {
                        const preprintId = pathMatch[1].replace(/_v\\d+$/, '');
                        data.pdf_url = `https://osf.io/${preprintId}/download/`;
                    }
                }
                
                // 查找作者链接（OSF）
                if (!data.authors && window.location.hostname === 'osf.io') {
                    const authorLinks = document.querySelectorAll('a[href*="/profile/"]');
                    if (authorLinks.length > 0) {
                        data.authors = Array.from(authorLinks)
                            .map(link => link.textContent.trim())
                            .filter(name => name)
                            .join('; ');
                    }
                }
                
                return data;
            }
        """)
        
        metadata.update(result)
        
        # 确定源和类型
        if 'osf.io' in url:
            if 'psyarxiv' in url:
                metadata['source'] = 'PsyArXiv'
            elif 'socarxiv' in url:
                metadata['source'] = 'SocArXiv' 
            else:
                metadata['source'] = 'OSF'
            metadata['itemType'] = 'preprint'
        
        logger.info(f"📊 元数据提取完成: 标题={metadata.get('title', 'N/A')[:30]}, PDF={bool(metadata.get('pdf_url'))}")
        return metadata
    
    async def _download_with_monitoring(self, page: Page, pdf_url: str) -> Optional[bytes]:
        """使用下载监控获取PDF - 类似Zotero Connector"""
        logger.info(f"📁 启动下载监控: {pdf_url}")
        
        try:
            # 🚀 创建专门的下载页面
            download_page = await self.context.new_page()
            download_content = None
            download_event = asyncio.Event()
            download_path = None
            
            def handle_download(download):
                nonlocal download_content, download_path
                logger.info(f"✅ 捕获下载事件: {download.url}")
                
                async def save_download():
                    try:
                        # 建议的文件名
                        import time
                        suggested_filename = download.suggested_filename or f"download_{int(time.time())}.pdf"
                        download_path = os.path.join(self.download_path, suggested_filename)
                        
                        # 保存下载文件
                        await download.save_as(download_path)
                        
                        # 读取内容
                        if os.path.exists(download_path):
                            with open(download_path, 'rb') as f:
                                content = f.read()
                            
                            if content and len(content) > 5000:
                                download_content = content
                                logger.info(f"✅ 下载成功: {len(content)} bytes")
                            else:
                                logger.warning(f"下载文件太小: {len(content) if content else 0} bytes")
                        
                        download_event.set()
                        
                    except Exception as e:
                        logger.error(f"保存下载文件失败: {e}")
                        download_event.set()
                
                asyncio.create_task(save_download())
            
            # 监听下载事件
            download_page.on('download', handle_download)
            
            try:
                # 设置下载页面属性
                await download_page.set_extra_http_headers({
                    'Accept': 'application/pdf,*/*;q=0.8',
                    'Referer': page.url,
                    'Cache-Control': 'no-cache'
                })
                
                # 导航到PDF链接，处理"Download is starting"情况
                try:
                    await download_page.goto(pdf_url, timeout=30000)
                except Exception as e:
                    # "Download is starting"实际上意味着下载被触发了
                    if "download is starting" in str(e).lower():
                        logger.info("✅ 检测到下载开始信号，等待下载完成...")
                    else:
                        logger.warning(f"页面导航异常: {e}")
                
                # 等待下载事件
                try:
                    await asyncio.wait_for(download_event.wait(), timeout=25.0)
                    
                    if download_content:
                        if download_content.startswith(b'%PDF'):
                            logger.info(f"🎉 PDF下载监控成功: {len(download_content)} bytes")
                            return download_content
                        else:
                            logger.warning("下载内容不是PDF格式")
                    else:
                        logger.warning("未获取到下载内容")
                        
                except asyncio.TimeoutError:
                    logger.warning("下载监控超时")
                
            finally:
                await download_page.close()
                # 清理下载文件
                if download_path and os.path.exists(download_path):
                    try:
                        os.remove(download_path)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"下载监控异常: {e}")
        
        # 备用策略：直接请求下载
        logger.info("📁 尝试备用下载策略...")
        try:
            response = await page.context.request.get(
                pdf_url,
                headers={
                    'Accept': 'application/pdf,*/*;q=0.8',
                    'Referer': page.url
                },
                timeout=25000
            )
            
            if response.status == 200:
                 content = await response.body()
                 if content:
                     # 🚀 改进：检查各种PDF格式的可能性
                     if content.startswith(b'%PDF'):
                         logger.info(f"✅ 备用下载成功 (标准PDF): {len(content)} bytes")
                         return content
                     elif len(content) > 100000:  # 大于100KB的文件
                         # 对于OSF的application/octet-stream，可能仍然是PDF
                         # 尝试查找PDF标识符
                         if b'%PDF' in content[:2048]:  # 在前2KB中查找
                             logger.info(f"✅ 备用下载成功 (嵌入式PDF): {len(content)} bytes")
                             return content
                         # 或者检查是否包含PDF相关内容
                         elif (b'Adobe' in content or b'PDF' in content or 
                               response.headers.get('content-type', '').startswith('application')):
                             logger.info(f"✅ 备用下载成功 (可能是PDF): {len(content)} bytes")
                             return content
                         else:
                             logger.warning(f"备用下载获得大文件但格式未知: {len(content)} bytes")
                     else:
                         logger.warning(f"备用下载文件太小: {len(content)} bytes")
                    
        except Exception as e:
            logger.info(f"备用下载失败: {e}")
        
        logger.warning("所有下载策略都失败了")
        return None

# 使用示例
async def test_enhanced_extractor():
    """测试增强版提取器"""
    test_url = 'https://osf.io/preprints/psyarxiv/prd9y_v1'
    
    async with EnhancedBrowserExtractor() as extractor:
        result = await extractor.extract_with_zotero_strategy(test_url)
        
        print("🎯 增强版提取器测试结果:")
        print(f"📄 标题: {result.get('title', '未获取')}")
        print(f"👥 作者: {result.get('authors', '未获取')}")
        print(f"🔗 PDF链接: {result.get('pdf_url', '未获取')}")
        
        if result.get('pdf_content'):
            size_mb = len(result['pdf_content']) / (1024 * 1024)
            print(f"📁 PDF下载: 成功 ({size_mb:.2f} MB)")
        else:
            print(f"📁 PDF下载: 失败")

if __name__ == "__main__":
    asyncio.run(test_enhanced_extractor()) 
"""
增强版浏览器提取器 - 基于Zotero Connector策略
借鉴官方插件的下载监控和反爬虫绕过机制
"""

import asyncio
import logging
import os
import tempfile
from typing import Optional, Dict, Any, List
from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from pathlib import Path

logger = logging.getLogger(__name__)

class EnhancedBrowserExtractor:
    """增强版浏览器提取器，实现类似Zotero Connector的功能"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.playwright = await async_playwright().start()
        
        # 🚀 关键改进：使用更接近真实浏览器的配置
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--allow-running-insecure-content',
                '--disable-features=VizDisplayCompositor',
                '--disable-blink-features=AutomationControlled',
                '--disable-automation-controlled',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-popup-blocking',
                '--single-process',  # 避免进程管理问题
                '--enable-features=NetworkService,NetworkServiceLogging'
            ],
            ignore_default_args=['--enable-automation'],
            timeout=60000
        )
        
        # 创建上下文，模拟真实用户环境
        self.context = await self.browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            accept_downloads=True,  # 允许下载
            has_touch=False,
            is_mobile=False,
            bypass_csp=True  # 绕过CSP限制
        )
        
        # 设置全局下载路径
        self.download_path = tempfile.mkdtemp()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"清理资源时出现问题: {e}")
        
        # 清理临时下载目录
        try:
            import shutil
            if hasattr(self, 'download_path') and os.path.exists(self.download_path):
                shutil.rmtree(self.download_path)
        except Exception as e:
            logger.warning(f"清理下载目录失败: {e}")
    
    async def extract_with_zotero_strategy(self, url: str) -> Dict[str, Any]:
        """使用类似Zotero Connector的策略提取内容"""
        logger.info(f"🚀 使用Zotero Connector策略处理: {url}")
        
        try:
            page = await self.context.new_page()
            
            # 🎯 步骤1: 智能页面导航和等待
            await self._smart_page_navigation(page, url)
            
            # 🎯 步骤2: 提取元数据
            metadata = await self._extract_metadata_zotero_style(page, url)
            
            # 🎯 步骤3: 下载PDF（使用下载监控）
            if metadata.get('pdf_url'):
                pdf_content = await self._download_with_monitoring(page, metadata['pdf_url'])
                if pdf_content:
                    metadata['pdf_content'] = pdf_content
            
            await page.close()
            return metadata
            
        except Exception as e:
            logger.error(f"Zotero策略提取失败: {e}")
            return {}
    
    async def _smart_page_navigation(self, page: Page, url: str):
        """智能页面导航，处理反爬虫"""
        logger.info("🌐 开始智能页面导航...")
        
        # 设置页面属性
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # 导航到页面
        timeout_ms = 45000 if 'osf.io' in url else 25000
        await page.goto(url, wait_until='domcontentloaded', timeout=timeout_ms)
        
        # 检测并处理反爬虫页面
        await self._handle_bot_protection(page)
        
        # OSF平台特殊处理
        if 'osf.io' in url:
            await self._handle_osf_loading(page)
    
    async def _handle_bot_protection(self, page: Page):
        """处理反爬虫保护 - 类似Zotero的处理方式"""
        try:
            title = await page.title()
            if any(phrase in title.lower() for phrase in ['just a moment', 'checking', 'please wait', 'cloudflare']):
                logger.info("🛡️ 检测到反爬虫页面，启用绕过策略...")
                
                # 模拟人类行为
                await asyncio.sleep(2)
                await page.mouse.move(100, 100)
                await asyncio.sleep(1)
                
                # 等待反爬虫页面自动跳转（最多30秒）
                for i in range(15):
                    await asyncio.sleep(2)
                    new_title = await page.title()
                    if 'just a moment' not in new_title.lower():
                        logger.info(f"✅ 反爬虫页面已绕过: {new_title[:50]}...")
                        break
                    logger.info(f"⏳ 等待反爬虫检查完成... ({i+1}/15)")
                
                # 额外的人类行为模拟
                await page.mouse.move(200, 200)
                await page.evaluate("window.scrollTo(0, 300)")
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, 0)")
                
        except Exception as e:
            logger.info(f"反爬虫处理异常: {e}")
    
    async def _handle_osf_loading(self, page: Page):
        """处理OSF平台的Ember应用加载 - 增强版等待策略"""
        logger.info("🔧 处理OSF Ember应用加载...")
        
        try:
            # 等待Ember应用容器
            await page.wait_for_selector('.ember-application, .ember-view', timeout=15000)
            logger.info("✅ Ember容器加载完成")
            
            # 🚀 关键改进：循环等待直到标题真正加载
            max_attempts = 20  # 最多等待40秒
            for attempt in range(max_attempts):
                await asyncio.sleep(2)
                
                title = await page.title()
                logger.info(f"第{attempt+1}次检查 - 当前标题: {title}")
                
                # 检查标题是否真正加载（包含论文信息）
                if title and '|' in title and len(title) > 20:
                    logger.info(f"✅ OSF内容加载完成: {title[:50]}...")
                    break
                
                # 检查是否有H1标题出现
                h1_text = await page.evaluate("document.querySelector('h1')?.textContent?.trim() || ''")
                if h1_text and len(h1_text) > 10:
                    logger.info(f"✅ 发现H1标题: {h1_text[:50]}...")
                    break
                
                # 每5次尝试后触发页面交互
                if (attempt + 1) % 5 == 0:
                    logger.info("🔄 触发页面交互以促进加载...")
                    await page.evaluate("window.scrollTo(0, 300)")
                    await asyncio.sleep(1)
                    await page.evaluate("window.scrollTo(0, 0)")
                    
                    # 尝试点击可能的加载按钮或链接
                    try:
                        # 检查是否有"show more"或类似的按钮
                        await page.evaluate("""
                            const buttons = document.querySelectorAll('button, a');
                            for (const btn of buttons) {
                                const text = btn.textContent.toLowerCase();
                                if (text.includes('load') || text.includes('show') || text.includes('expand')) {
                                    btn.click();
                                    break;
                                }
                            }
                        """)
                    except:
                        pass
                
                if attempt == max_attempts - 1:
                    logger.warning("⚠️ OSF内容等待超时，使用当前状态")
            
        except Exception as e:
            logger.info(f"OSF加载处理异常: {e}")
    
    async def _extract_metadata_zotero_style(self, page: Page, url: str) -> Dict[str, Any]:
        """使用类似Zotero的方式提取元数据"""
        logger.info("📊 使用Zotero风格提取元数据...")
        
        metadata = {}
        
        # 执行JavaScript提取
        result = await page.evaluate("""
            () => {
                const data = {
                    title: '',
                    authors: '',
                    abstract: '',
                    DOI: '',
                    pdf_url: '',
                    date: '',
                    publicationTitle: ''
                };
                
                // 优先从页面标题提取
                if (document.title) {
                    data.title = document.title;
                    
                    // OSF格式特殊处理
                    if (document.title.includes('|') && window.location.hostname === 'osf.io') {
                        data.title = document.title.split('|')[1].trim();
                    }
                }
                
                // 从H1提取标题（备用）
                if (!data.title || data.title === 'OSF') {
                    const h1 = document.querySelector('h1');
                    if (h1) data.title = h1.textContent.trim();
                }
                
                // Citation meta标签提取
                const citationMeta = {
                    'citation_title': 'title',
                    'citation_author': 'authors',
                    'citation_publication_date': 'date',
                    'citation_doi': 'DOI',
                    'citation_pdf_url': 'pdf_url',
                    'citation_abstract_html_url': 'url'
                };
                
                for (const [metaName, field] of Object.entries(citationMeta)) {
                    const elements = document.querySelectorAll(`meta[name="${metaName}"]`);
                    if (elements.length > 0) {
                        if (metaName === 'citation_author') {
                            data.authors = Array.from(elements).map(el => el.content).join('; ');
                        } else {
                            data[field] = elements[0].content || data[field];
                        }
                    }
                }
                
                // OSF特殊处理：PDF链接构造
                if (window.location.hostname === 'osf.io' && !data.pdf_url) {
                    const pathMatch = window.location.pathname.match(/\/preprints\/\\w+\/([^\\/]+)/);
                    if (pathMatch) {
                        const preprintId = pathMatch[1].replace(/_v\\d+$/, '');
                        data.pdf_url = `https://osf.io/${preprintId}/download/`;
                    }
                }
                
                // 查找作者链接（OSF）
                if (!data.authors && window.location.hostname === 'osf.io') {
                    const authorLinks = document.querySelectorAll('a[href*="/profile/"]');
                    if (authorLinks.length > 0) {
                        data.authors = Array.from(authorLinks)
                            .map(link => link.textContent.trim())
                            .filter(name => name)
                            .join('; ');
                    }
                }
                
                return data;
            }
        """)
        
        metadata.update(result)
        
        # 确定源和类型
        if 'osf.io' in url:
            if 'psyarxiv' in url:
                metadata['source'] = 'PsyArXiv'
            elif 'socarxiv' in url:
                metadata['source'] = 'SocArXiv' 
            else:
                metadata['source'] = 'OSF'
            metadata['itemType'] = 'preprint'
        
        logger.info(f"📊 元数据提取完成: 标题={metadata.get('title', 'N/A')[:30]}, PDF={bool(metadata.get('pdf_url'))}")
        return metadata
    
    async def _download_with_monitoring(self, page: Page, pdf_url: str) -> Optional[bytes]:
        """使用下载监控获取PDF - 类似Zotero Connector"""
        logger.info(f"📁 启动下载监控: {pdf_url}")
        
        try:
            # 🚀 创建专门的下载页面
            download_page = await self.context.new_page()
            download_content = None
            download_event = asyncio.Event()
            download_path = None
            
            def handle_download(download):
                nonlocal download_content, download_path
                logger.info(f"✅ 捕获下载事件: {download.url}")
                
                async def save_download():
                    try:
                        # 建议的文件名
                        import time
                        suggested_filename = download.suggested_filename or f"download_{int(time.time())}.pdf"
                        download_path = os.path.join(self.download_path, suggested_filename)
                        
                        # 保存下载文件
                        await download.save_as(download_path)
                        
                        # 读取内容
                        if os.path.exists(download_path):
                            with open(download_path, 'rb') as f:
                                content = f.read()
                            
                            if content and len(content) > 5000:
                                download_content = content
                                logger.info(f"✅ 下载成功: {len(content)} bytes")
                            else:
                                logger.warning(f"下载文件太小: {len(content) if content else 0} bytes")
                        
                        download_event.set()
                        
                    except Exception as e:
                        logger.error(f"保存下载文件失败: {e}")
                        download_event.set()
                
                asyncio.create_task(save_download())
            
            # 监听下载事件
            download_page.on('download', handle_download)
            
            try:
                # 设置下载页面属性
                await download_page.set_extra_http_headers({
                    'Accept': 'application/pdf,*/*;q=0.8',
                    'Referer': page.url,
                    'Cache-Control': 'no-cache'
                })
                
                # 导航到PDF链接，处理"Download is starting"情况
                try:
                    await download_page.goto(pdf_url, timeout=30000)
                except Exception as e:
                    # "Download is starting"实际上意味着下载被触发了
                    if "download is starting" in str(e).lower():
                        logger.info("✅ 检测到下载开始信号，等待下载完成...")
                    else:
                        logger.warning(f"页面导航异常: {e}")
                
                # 等待下载事件
                try:
                    await asyncio.wait_for(download_event.wait(), timeout=25.0)
                    
                    if download_content:
                        if download_content.startswith(b'%PDF'):
                            logger.info(f"🎉 PDF下载监控成功: {len(download_content)} bytes")
                            return download_content
                        else:
                            logger.warning("下载内容不是PDF格式")
                    else:
                        logger.warning("未获取到下载内容")
                        
                except asyncio.TimeoutError:
                    logger.warning("下载监控超时")
                
            finally:
                await download_page.close()
                # 清理下载文件
                if download_path and os.path.exists(download_path):
                    try:
                        os.remove(download_path)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"下载监控异常: {e}")
        
        # 备用策略：直接请求下载
        logger.info("📁 尝试备用下载策略...")
        try:
            response = await page.context.request.get(
                pdf_url,
                headers={
                    'Accept': 'application/pdf,*/*;q=0.8',
                    'Referer': page.url
                },
                timeout=25000
            )
            
            if response.status == 200:
                 content = await response.body()
                 if content:
                     # 🚀 改进：检查各种PDF格式的可能性
                     if content.startswith(b'%PDF'):
                         logger.info(f"✅ 备用下载成功 (标准PDF): {len(content)} bytes")
                         return content
                     elif len(content) > 100000:  # 大于100KB的文件
                         # 对于OSF的application/octet-stream，可能仍然是PDF
                         # 尝试查找PDF标识符
                         if b'%PDF' in content[:2048]:  # 在前2KB中查找
                             logger.info(f"✅ 备用下载成功 (嵌入式PDF): {len(content)} bytes")
                             return content
                         # 或者检查是否包含PDF相关内容
                         elif (b'Adobe' in content or b'PDF' in content or 
                               response.headers.get('content-type', '').startswith('application')):
                             logger.info(f"✅ 备用下载成功 (可能是PDF): {len(content)} bytes")
                             return content
                         else:
                             logger.warning(f"备用下载获得大文件但格式未知: {len(content)} bytes")
                     else:
                         logger.warning(f"备用下载文件太小: {len(content)} bytes")
                    
        except Exception as e:
            logger.info(f"备用下载失败: {e}")
        
        logger.warning("所有下载策略都失败了")
        return None

# 使用示例
async def test_enhanced_extractor():
    """测试增强版提取器"""
    test_url = 'https://osf.io/preprints/psyarxiv/prd9y_v1'
    
    async with EnhancedBrowserExtractor() as extractor:
        result = await extractor.extract_with_zotero_strategy(test_url)
        
        print("🎯 增强版提取器测试结果:")
        print(f"📄 标题: {result.get('title', '未获取')}")
        print(f"👥 作者: {result.get('authors', '未获取')}")
        print(f"🔗 PDF链接: {result.get('pdf_url', '未获取')}")
        
        if result.get('pdf_content'):
            size_mb = len(result['pdf_content']) / (1024 * 1024)
            print(f"📁 PDF下载: 成功 ({size_mb:.2f} MB)")
        else:
            print(f"📁 PDF下载: 失败")

if __name__ == "__main__":
    asyncio.run(test_enhanced_extractor()) 