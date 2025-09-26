"""
浏览器驱动的PDF提取器
用于解决开源数据库的反爬虫限制，如bioRxiv、OSF系列等
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin, urlparse
import re
import os

try:
    from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None

from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class BrowserExtractor(BaseExtractor):
    """浏览器驱动的提取器，用于处理有反爬虫机制的开源数据库"""
    
    # 需要使用浏览器的域名列表
    BROWSER_REQUIRED_DOMAINS = {
        'biorxiv.org': {'priority': 10, 'itemType': 'preprint', 'source': 'bioRxiv'},
        'medrxiv.org': {'priority': 10, 'itemType': 'preprint', 'source': 'medRxiv'},
        'chemrxiv.org': {'priority': 10, 'itemType': 'preprint', 'source': 'ChemRxiv'},
        'psyarxiv.com': {'priority': 10, 'itemType': 'preprint', 'source': 'PsyArXiv'},
        'osf.io': {'priority': 10, 'itemType': 'preprint', 'source': 'OSF'},
        'socarxiv.org': {'priority': 10, 'itemType': 'preprint', 'source': 'SocArXiv'},
    }
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context = None
    
    def get_database_name(self) -> str:
        """返回数据库名称"""
        return "Browser-Driven"
    
    def requires_authentication(self) -> bool:
        """是否需要认证"""
        return False
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright未安装，请运行: pip install playwright && playwright install chromium")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,  # 无头模式
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--no-first-run',
                '--disable-plugins',
                '--disable-default-apps',
                '--disable-background-timer-throttling',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows',
                '--disable-ipc-flooding-protection',
                '--single-process',
                '--no-zygote'
            ],
            ignore_default_args=['--enable-blink-features=IdleDetection'],
            timeout=30000  # 30秒启动超时
        )
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            accept_downloads=True
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def _download_biorxiv_with_mcp(self, browser_instance, pdf_url: str) -> Optional[bytes]:
        """
        使用MCP高级浏览器技术下载bioRxiv PDF
        已验证可绕过bioRxiv反爬虫机制
        """
        try:
            logger.info("🧬 启动MCP高级浏览器下载")
            
            # 创建新的高级配置页面
            page = await browser_instance.context.new_page()
            
            # 注入高级反检测脚本
            await page.add_init_script("""
                // 移除webdriver属性
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // 伪造plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            name: 'Chrome PDF Plugin',
                            filename: 'internal-pdf-viewer',
                            description: 'Portable Document Format'
                        },
                        {
                            name: 'Chrome PDF Viewer', 
                            filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                            description: ''
                        }
                    ],
                });
                
                // 伪造languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                // 移除automation标记
                delete Object.getPrototypeOf(navigator).webdriver;
            """)
            
            # 多步骤访问策略
            logger.info("  1. 先访问bioRxiv主页建立会话...")
            # 使用更宽松的加载策略，避免networkidle在Cloudflare场景下超时
            try:
                await page.goto('https://www.biorxiv.org/', wait_until='domcontentloaded', timeout=15000)
            except Exception as e:
                logger.info(f"  ⏭️ 跳过主页等待（{str(e)[:60]}）")
            
            # 模拟人类行为间隔
            await asyncio.sleep(2)
            
            # 优先尝试经过会话的多策略直接下载
            try:
                from typing import Optional as _Optional
                direct_pdf: _Optional[bytes] = await self._download_pdf_with_browser(page, pdf_url)
                if direct_pdf and direct_pdf.startswith(b'%PDF'):
                    await page.close()
                    logger.info(f"  ✅ MCP直接获取PDF成功: {len(direct_pdf):,} bytes")
                    return direct_pdf
            except Exception as e:
                logger.info(f"  ⚠️ 直接获取PDF失败，回退到下载事件: {e}")
            
            # 设置下载监听（回退方案）
            download_success = False
            pdf_content = None
            
            async def handle_biorxiv_download(download):
                nonlocal download_success, pdf_content
                try:
                    logger.info(f"  🎯 MCP检测到下载: {download.url}")
                    
                    # 创建临时文件
                    import tempfile
                    temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                    temp_path = temp_file.name
                    temp_file.close()
                    
                    # 保存下载
                    await download.save_as(temp_path)
                    
                    # 读取内容
                    with open(temp_path, 'rb') as f:
                        pdf_content = f.read()
                    
                    # 验证PDF并清理
                    if pdf_content and pdf_content.startswith(b'%PDF'):
                        download_success = True
                        logger.info(f"  ✅ MCP下载成功: {len(pdf_content):,} bytes")
                    
                    # 清理临时文件
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                        
                except Exception as e:
                    logger.warning(f"  ⚠️ MCP下载处理异常: {e}")
            
            page.on("download", handle_biorxiv_download)
            
            # 触发下载
            logger.info("  2. JavaScript触发PDF下载...")
            try:
                await page.evaluate(f"window.open('{pdf_url}', '_blank')")
            except:
                pass
            
            # 等待下载
            logger.info("  3. 等待下载完成...")
            for i in range(30):  # 最多等30秒
                if download_success:
                    break
                await asyncio.sleep(1)
            
            await page.close()
            
            if download_success and pdf_content:
                logger.info(f"🎉 MCP bioRxiv PDF下载成功: {len(pdf_content):,} bytes")
                return pdf_content
            else:
                logger.warning("⚠️ MCP bioRxiv PDF下载超时或失败")
                return None
                
        except Exception as e:
            logger.error(f"❌ MCP bioRxiv下载异常: {e}")
            return None
    
    def can_handle(self, url: str) -> bool:
        """检查是否需要使用浏览器处理"""
        if not PLAYWRIGHT_AVAILABLE:
            return False
            
        domain = urlparse(url).netloc.lower()
        for browser_domain in self.BROWSER_REQUIRED_DOMAINS:
            if browser_domain in domain:
                return True
        return False
    
    async def _download_pdf_content(self, pdf_url: str) -> Optional[bytes]:
        """
        使用浏览器环境下载PDF内容
        
        Args:
            pdf_url: PDF链接
            
        Returns:
            PDF文件的二进制内容，如果失败返回None
        """
        if not self.browser:
            logger.error("浏览器未初始化，无法下载PDF内容")
            return None
            
        try:
            # 创建新页面用于下载
            page = await self.browser.new_page()
            
            # 设置下载监听
            download_info = None
            pdf_content = None
            
            async def handle_download(download):
                nonlocal download_info, pdf_content
                logger.info(f"🎯 检测到下载: {download.url}")
                download_info = download
                
                # 获取临时文件路径
                temp_path = await download.path()
                if temp_path:
                    # 读取文件内容
                    with open(temp_path, 'rb') as f:
                        pdf_content = f.read()
                    logger.info(f"✅ 成功读取PDF内容: {len(pdf_content)} bytes")
                else:
                    # 如果没有文件路径，尝试获取buffer
                    try:
                        pdf_content = await download.save_as(bytes)
                        logger.info(f"✅ 通过buffer获取PDF内容: {len(pdf_content)} bytes")
                    except Exception as e:
                        logger.warning(f"⚠️ 无法获取PDF buffer: {e}")
            
            # 监听下载事件
            page.on("download", handle_download)
            
            # 导航到PDF URL
            logger.info(f"🌐 浏览器访问PDF: {pdf_url}")
            
            try:
                # 设置较长的超时时间
                response = await page.goto(pdf_url, timeout=60000, wait_until='networkidle')
                
                if response and response.status == 200:
                    # 检查Content-Type是否为PDF
                    headers = await response.all_headers()
                    content_type = headers.get('content-type', '')
                    
                    if 'application/pdf' in content_type:
                        logger.info("📄 检测到PDF响应，尝试获取内容")
                        
                        # 直接从响应获取PDF内容
                        pdf_content = await response.body()
                        logger.info(f"✅ 直接从响应获取PDF: {len(pdf_content)} bytes")
                        
                        # 验证PDF内容
                        if pdf_content and len(pdf_content) > 1024:  # 至少1KB
                            if pdf_content.startswith(b'%PDF'):
                                await page.close()
                                return pdf_content
                            else:
                                logger.warning("⚠️ 内容不是有效的PDF格式")
                        else:
                            logger.warning("⚠️ PDF内容太小或为空")
                    else:
                        logger.warning(f"⚠️ 响应不是PDF类型: {content_type}")
                        
                        # 如果不是直接的PDF响应，可能需要触发下载
                        # 等待一段时间看是否有下载事件
                        await page.wait_for_timeout(5000)
                        
                        if pdf_content:
                            logger.info("✅ 通过下载事件获取PDF内容")
                            await page.close()
                            return pdf_content
                
                else:
                    logger.error(f"❌ PDF访问失败: {response.status if response else 'No response'}")
                    
            except Exception as e:
                logger.error(f"❌ PDF访问异常: {e}")
                
            await page.close()
            return None
            
        except Exception as e:
            logger.error(f"❌ PDF下载严重异常: {e}")
            return None

    def extract_metadata(self, url: str) -> Dict[str, Any]:
        """
        提取论文元数据，对于反爬虫网站还会下载PDF内容
        
        Returns:
            包含元数据和PDF内容的字典
        """
        try:
            # 使用异步包装器
            return asyncio.run(self._async_extract_metadata_with_pdf(url))
        except Exception as e:
            logger.error(f"❌ 元数据提取异常: {e}")
            return {"error": f"提取异常: {str(e)}"}

    async def _async_extract_metadata_with_pdf(self, url: str) -> Dict[str, Any]:
        """异步提取元数据并下载PDF内容 - 修复版本"""
        if not self.can_handle(url):
            return {}
            
        logger.info(f"BrowserExtractor: 使用浏览器处理 {url}")
        
        try:
            # 🔧 修复：在同一个浏览器会话中完成所有操作
            async with BrowserExtractor() as extractor_instance:
                page = await extractor_instance.context.new_page()
                
                # 设置页面属性，提高成功率
                await page.set_extra_http_headers({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Upgrade-Insecure-Requests': '1'
                })
                
                # 1. 首先提取元数据
                result = await self._extract_metadata_from_page(page, url)
                
                if 'error' in result:
                    return result
                    
                # 2. 在同一会话中下载PDF
                pdf_url = result.get('pdf_url')
                if pdf_url:
                    logger.info(f"🔄 尝试下载PDF内容: {pdf_url}")
                    
                    # 🚀 MCP浏览器PDF下载 - 已验证可行
                    if 'biorxiv.org' in pdf_url.lower():
                        logger.info("🧬 使用MCP高级浏览器下载bioRxiv PDF")
                        pdf_content = await self._download_biorxiv_with_mcp(extractor_instance, pdf_url)
                    else:
                        logger.info("⚠️ 非bioRxiv网站，跳过浏览器PDF下载")
                        pdf_content = None
                    
                    if pdf_content:
                        result['pdf_content'] = pdf_content
                        result['pdf_size'] = len(pdf_content)
                        logger.info(f"✅ PDF内容下载成功: {len(pdf_content)} bytes")
                    else:
                        logger.warning("⚠️ PDF内容下载失败，仅提供链接")
                
                return result
                
        except Exception as e:
            logger.error(f"❌ 浏览器元数据+PDF提取异常: {e}")
            return {"error": f"浏览器提取异常: {str(e)}"}

    async def _async_extract_metadata(self, url: str) -> Dict[str, Any]:
        """使用浏览器提取元数据和PDF链接"""
        if not self.can_handle(url):
            return {}
            
        logger.info(f"BrowserExtractor: 使用浏览器处理 {url}")
        
        try:
            # 创建临时浏览器实例
            async with BrowserExtractor() as extractor_instance:
                page = await extractor_instance.context.new_page()
                
                # 设置页面属性，提高成功率
                await page.set_extra_http_headers({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Upgrade-Insecure-Requests': '1'
                })
                
                # 🚀 智能反爬虫策略
                await page.goto(url, wait_until='domcontentloaded', timeout=20000)
                
                # 检查是否遇到"Just a moment"等待页面
                await asyncio.sleep(2)  # 初始等待
                
                title = await page.title()
                if "just a moment" in title.lower() or "please wait" in title.lower():
                    logger.info("🔄 检测到反爬虫等待页面，智能等待中...")
                    
                    # 最多等待30秒让页面自然加载
                    for i in range(15):  # 15次，每次2秒
                        await asyncio.sleep(2)
                        new_title = await page.title()
                        if "just a moment" not in new_title.lower():
                            logger.info(f"✅ 反爬虫页面已通过，新标题: {new_title[:50]}...")
                            break
                        logger.info(f"⏳ 继续等待反爬虫检查... ({i+1}/15)")
                    
                    # 模拟人类行为
                    try:
                        # 滚动页面
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
                        await asyncio.sleep(1)
                        await page.evaluate("window.scrollTo(0, 0)")
                        await asyncio.sleep(1)
                    except:
                        pass
                
                # 等待最终的网络稳定
                try:
                    await page.wait_for_load_state('networkidle', timeout=8000)
                except:
                    logger.info("网络等待超时，继续处理")
                
                # 最终确认页面标题
                final_title = await page.title()
                logger.info(f"📄 最终页面标题: {final_title[:70]}...")
                
                # 执行JavaScript来提取元数据和PDF链接
                metadata = await page.evaluate(extractor_instance._get_extraction_script())
                
                # 识别域名类型
                domain_info = extractor_instance._identify_domain(url)
                metadata.update(domain_info)
                
                # 查找PDF链接
                pdf_urls = await extractor_instance._find_pdf_links(page, url)
                if pdf_urls:
                    pdf_url = pdf_urls[0]
                    metadata['pdf_url'] = pdf_url
                    logger.info(f"BrowserExtractor: 找到PDF链接 {pdf_url}")
                
                await page.close()
                return metadata
             
        except PlaywrightTimeoutError:
            logger.error(f"BrowserExtractor: 页面加载超时 {url}")
            return {}
        except Exception as e:
            logger.error(f"BrowserExtractor: 提取失败 {url} - {e}")
            return {}
    
    def _identify_domain(self, url: str) -> Dict[str, Any]:
        """识别域名类型"""
        domain = urlparse(url).netloc.lower()
        for browser_domain, info in self.BROWSER_REQUIRED_DOMAINS.items():
            if browser_domain in domain:
                return {
                    'itemType': info['itemType'],
                    'source': info['source'],
                    'priority': info['priority']
                }
        return {}
    
    def _get_extraction_script(self) -> str:
        """返回在页面中执行的JavaScript代码"""
        return """
        () => {
            const metadata = {};
            
            // 🎯 优先提取citation_title（最可靠的标题来源）
            const citationTitleMeta = document.querySelector('meta[name="citation_title"]');
            if (citationTitleMeta && citationTitleMeta.content) {
                metadata.title = citationTitleMeta.content.trim();
            } else {
                metadata.title = document.title || '';
            }
            
            // 提取其他citation标签
            const citationFields = {
                'citation_author': 'authors',
                'citation_date': 'date',
                'citation_publication_date': 'date',
                'citation_online_date': 'date',
                'citation_doi': 'DOI',
                'citation_abstract_html_url': 'url',
                'citation_pdf_url': 'pdf_url',
                'citation_fulltext_pdf_url': 'pdf_url',
                'citation_preprint_server': 'publicationTitle',
                'citation_archive_id': 'archiveID'
            };
            
            for (const [citationField, metaField] of Object.entries(citationFields)) {
                const elements = document.querySelectorAll(`meta[name="${citationField}"]`);
                if (elements.length > 0) {
                    if (citationField === 'citation_author') {
                        metadata.authors = Array.from(elements).map(el => el.content).join('; ');
                    } else if (!metadata[metaField]) {  // 避免覆盖已设置的值
                        metadata[metaField] = elements[0].content;
                    }
                }
            }
            
            // 提取Dublin Core标签
            const dcFields = {
                'DC.title': 'title',
                'DC.creator': 'authors',
                'DC.date': 'date',
                'DC.identifier': 'DOI'
            };
            
            for (const [dcField, metaField] of Object.entries(dcFields)) {
                const element = document.querySelector(`meta[name="${dcField}"]`);
                if (element && !metadata[metaField]) {
                    metadata[metaField] = element.content;
                }
            }
            
            // 提取JSON-LD
            const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
            for (const script of jsonLdScripts) {
                try {
                    const data = JSON.parse(script.textContent);
                    if (data['@type'] === 'ScholarlyArticle' || data['@type'] === 'Article') {
                        if (data.name && !metadata.title) metadata.title = data.name;
                        if (data.headline && !metadata.title) metadata.title = data.headline;
                        if (data.datePublished && !metadata.date) metadata.date = data.datePublished;
                        if (data.identifier && !metadata.DOI) {
                            if (Array.isArray(data.identifier)) {
                                const doiIdentifier = data.identifier.find(id => id.propertyID === 'doi' || id['@type'] === 'PropertyValue');
                                if (doiIdentifier) metadata.DOI = doiIdentifier.value;
                            } else if (typeof data.identifier === 'string' && data.identifier.startsWith('10.')) {
                                metadata.DOI = data.identifier;
                            }
                        }
                        if (data.author && !metadata.authors) {
                            if (Array.isArray(data.author)) {
                                metadata.authors = data.author.map(a => a.name || a).join('; ');
                            }
                        }
                        // 检查encoding字段中的PDF
                        if (data.encoding && Array.isArray(data.encoding)) {
                            for (const encoding of data.encoding) {
                                if (encoding.encodingFormat === 'application/pdf' && encoding.contentUrl) {
                                    metadata.pdf_url = encoding.contentUrl;
                                    break;
                                }
                            }
                        }
                    }
                } catch (e) {
                    // 忽略JSON解析错误
                }
            }
            
            // 🎯 改进的标题提取逻辑 - 特别针对预印本网站
            if (!metadata.title || metadata.title === document.title) {
                const url = window.location.href.toLowerCase();
                let foundTitle = false;
                
                // bioRxiv/medRxiv特殊处理
                if (url.includes('biorxiv.org') || url.includes('medrxiv.org')) {
                    const titleSelectors = [
                        'h1.highwire-cite-title',
                        'h1[id="page-title"]',
                        'h1.article-title', 
                        '.article-title h1',
                        'div[id="papertitle"]',
                        '.hw-article-title',
                        'h1[property="name"]'
                    ];
                    
                    for (const selector of titleSelectors) {
                        const titleEl = document.querySelector(selector);
                        if (titleEl) {
                            const title = titleEl.textContent.trim();
                            if (title && title.length > 15 && !title.toLowerCase().includes('preprint') && !title.toLowerCase().includes('version')) {
                                metadata.title = title;
                                foundTitle = true;
                                break;
                            }
                        }
                    }
                }
                
                // ChemRxiv特殊处理
                else if (url.includes('chemrxiv.org')) {
                    const titleSelectors = [
                        'h1[data-testid="article-title"]',
                        '.article-header h1',
                        '.manuscript-title h1',
                        'h1.manuscript-title',
                        '.article-title',
                        'h1'
                    ];
                    
                    for (const selector of titleSelectors) {
                        const titleEl = document.querySelector(selector);
                        if (titleEl) {
                            const title = titleEl.textContent.trim();
                            if (title && title.length > 15) {
                                metadata.title = title;
                                foundTitle = true;
                                break;
                            }
                        }
                    }
                }
                
                // 通用H1标签处理（如果上面的特殊处理没有找到）
                if (!foundTitle) {
                    const h1Elements = document.querySelectorAll('h1');
                    for (const h1 of h1Elements) {
                        const title = h1.textContent.trim();
                        // 过滤掉明显的导航或无意义标题
                        if (title && title.length > 15 && 
                            !title.toLowerCase().includes('menu') && 
                            !title.toLowerCase().includes('navigation') &&
                            !title.toLowerCase().includes('login') &&
                            !title.toLowerCase().includes('search')) {
                            metadata.title = title;
                            foundTitle = true;
                            break;
                        }
                    }
                }
                
                // 最后的回退：清理document.title
                if (!foundTitle && document.title) {
                    let title = document.title.trim();
                    // 移除网站名称等常见后缀
                    title = title.replace(/ - bioRxiv$/i, '');
                    title = title.replace(/ - medRxiv$/i, '');
                    title = title.replace(/ - ChemRxiv$/i, '');
                    title = title.replace(/ \| .*$/i, '');
                    title = title.replace(/ - .*$/i, '');
                    
                    if (title.length > 15) {
                        metadata.title = title;
                    }
                }
            }
            
            // 清理最终标题
            if (metadata.title) {
                metadata.title = metadata.title.replace(/\s+/g, ' ').trim();
                metadata.title = metadata.title.replace(/^[-–—]\s*/, '');
                metadata.title = metadata.title.replace(/\s*[-–—]\s*$/, '');
            }
            
            return metadata;
        }
        """
    
    async def _find_pdf_links(self, page: Page, base_url: str) -> List[str]:
        """在页面中查找PDF链接"""
        pdf_urls = []
        
        try:
            # 方法1: 查找PDF链接元素
            pdf_links = await page.eval_on_selector_all('a[href*=".pdf"], a[href*="pdf"], link[type="application/pdf"]', """
                elements => elements.map(el => el.href || el.getAttribute('href')).filter(href => href)
            """)
            
            for link in pdf_links:
                if link and not link.startswith('javascript:'):
                    full_url = urljoin(base_url, link)
                    pdf_urls.append(full_url)
            
            # 方法2: 针对特定网站的PDF查找策略
            domain = urlparse(base_url).netloc.lower()
            
            if 'biorxiv.org' in domain or 'medrxiv.org' in domain:
                # bioRxiv/medRxiv: 尝试从URL构造PDF链接
                doi_match = re.search(r'/content/(?:early/)?(?:\d{4}/\d{2}/\d{2}/)?(?:10\.1101/)?([^v/]+)', base_url)
                if doi_match:
                    doi = doi_match.group(1)
                    pdf_url = f"https://{urlparse(base_url).netloc}/content/10.1101/{doi}v1.full.pdf"
                    pdf_urls.append(pdf_url)
                
            elif 'chemrxiv.org' in domain:
                # ChemRxiv: 查找特定的下载按钮或链接
                download_links = await page.eval_on_selector_all('a[href*="download"], button[onclick*="download"]', """
                    elements => elements.map(el => el.href || el.getAttribute('onclick')).filter(href => href)
                """)
                for link in download_links:
                    if 'pdf' in link.lower():
                        pdf_urls.append(link)
                        
            elif 'osf.io' in domain:
                # OSF系列: 查找download链接
                download_links = await page.eval_on_selector_all('a[href*="/download"]', """
                    elements => elements.map(el => el.href).filter(href => href)
                """)
                pdf_urls.extend(download_links)
            
            # 方法3: 查找页面中所有可能的PDF相关按钮
            button_links = await page.eval_on_selector_all('button, a.btn, .download-btn, .pdf-btn', """
                elements => {
                    const results = [];
                    elements.forEach(el => {
                        const text = el.textContent.toLowerCase();
                        const href = el.href;
                        const onclick = el.getAttribute('onclick') || '';
                        
                        if (text.includes('pdf') || text.includes('download') || onclick.includes('pdf')) {
                            if (href) results.push(href);
                            if (onclick && onclick.includes('http')) {
                                const urlMatch = onclick.match(/https?:\/\/[^'"\\s)]+/);
                                if (urlMatch) results.push(urlMatch[0]);
                            }
                        }
                    });
                    return results;
                }
            """)
            pdf_urls.extend(button_links)
            
            # 去重并返回
            unique_urls = []
            seen = set()
            for url in pdf_urls:
                if url and url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            logger.debug(f"BrowserExtractor: 找到 {len(unique_urls)} 个PDF候选链接")
            return unique_urls
            
        except Exception as e:
            logger.error(f"BrowserExtractor: PDF链接查找失败 - {e}")
            return []
    
    async def _download_pdf_with_browser(self, page, pdf_url: str) -> Optional[bytes]:
        """使用浏览器会话下载PDF内容 - 增强版"""
        try:
            logger.info(f"🔄 多策略PDF下载: {pdf_url}")
            
            # 策略1: 使用已验证的浏览器会话，添加完整请求头
            try:
                # 获取当前页面的URL作为Referer
                referer = page.url
                
                # 构建完整的请求头，模拟真实浏览器
                headers = {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Referer': referer,
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                
                logger.info(f"🔄 策略1: 使用完整请求头下载PDF")
                response = await page.context.request.get(pdf_url, headers=headers, timeout=45000)
                
                if response.status == 200:
                    content = await response.body()
                    if content and len(content) > 1024 and content.startswith(b'%PDF'):
                        logger.info(f"✅ 策略1成功: 完整请求头下载 ({len(content)} bytes)")
                        return content
                    else:
                        logger.info(f"策略1: 内容不是有效PDF ({len(content) if content else 0} bytes)")
                else:
                    logger.info(f"策略1失败: HTTP {response.status}")
                    
            except Exception as e:
                logger.info(f"策略1异常: {e}")
            
            # 策略2: 尝试不同的PDF URL格式
            alternative_urls = self._generate_alternative_pdf_urls(pdf_url)
            for alt_url in alternative_urls:
                try:
                    logger.info(f"🔄 测试备用URL: {alt_url}")
                    response = await page.context.request.get(alt_url, timeout=15000)
                    if response.status == 200:
                        content = await response.body()
                        if content and content.startswith(b'%PDF'):
                            logger.info(f"✅ 策略2成功: 备用URL ({len(content)} bytes)")
                            return content
                except Exception as e:
                    logger.debug(f"备用URL失败: {alt_url} - {e}")
            
            # 策略3: 捕获浏览器下载事件（关键突破！）
            try:
                logger.info("🔄 策略3: 捕获浏览器下载事件")
                pdf_page = await page.context.new_page()
                
                # 设置下载监听器
                download_content = None
                download_event = asyncio.Event()
                
                def handle_download(download):
                    logger.info(f"✅ 捕获到下载事件: {download.url}")
                    # 这里我们需要异步处理下载
                    asyncio.create_task(save_download(download))
                
                async def save_download(download):
                    nonlocal download_content
                    try:
                        # 等待下载完成并获取内容
                        await download.save_as('/tmp/temp_pdf.pdf')  # 临时保存
                        
                        # 读取下载的内容
                        with open('/tmp/temp_pdf.pdf', 'rb') as f:
                            download_content = f.read()
                        
                        logger.info(f"✅ 下载内容获取成功: {len(download_content)} bytes")
                        download_event.set()
                        
                        # 清理临时文件
                        import os
                        os.remove('/tmp/temp_pdf.pdf')
                        
                    except Exception as e:
                        logger.warning(f"下载处理失败: {e}")
                        download_event.set()
                
                # 注册下载监听器
                pdf_page.on('download', handle_download)
                
                # 导航到PDF URL，这会触发下载
                try:
                    await pdf_page.goto(pdf_url, timeout=20000)
                except Exception as e:
                    # 如果出现"Download is starting"错误，这实际上是好事
                    if "download is starting" in str(e).lower():
                        logger.info("🎯 检测到下载开始，等待下载完成...")
                
                # 等待下载事件，最多20秒
                try:
                    await asyncio.wait_for(download_event.wait(), timeout=20.0)
                    if download_content and download_content.startswith(b'%PDF'):
                        logger.info(f"🎉 策略3成功: 下载事件捕获 ({len(download_content)} bytes)")
                        await pdf_page.close()
                        return download_content
                except asyncio.TimeoutError:
                    logger.info("策略3: 下载等待超时")
                
                await pdf_page.close()
                
            except Exception as e:
                logger.info(f"策略3失败: {e}")
            
            # 策略4: 延迟后重试第一种方法（有时需要时间）
            try:
                logger.info("🔄 策略4: 延迟重试")
                await asyncio.sleep(2)  # 等待2秒
                response = await page.context.request.get(pdf_url, timeout=20000)
                if response.status == 200:
                    content = await response.body()
                    if content and content.startswith(b'%PDF'):
                        logger.info(f"✅ 策略4成功: 延迟重试 ({len(content)} bytes)")
                        return content
            except Exception as e:
                logger.info(f"策略4失败: {e}")
            
            logger.warning(f"所有PDF下载策略都失败了: {pdf_url}")
            return None
                
        except Exception as e:
            logger.error(f"浏览器PDF下载严重异常: {e}")
            return None
    
    def _generate_alternative_pdf_urls(self, original_url: str) -> List[str]:
        """生成可能的PDF URL变体"""
        alternatives = []
        
        if 'biorxiv.org' in original_url:
            # bioRxiv的多种URL格式
            import re
            
            # 提取DOI
            doi_match = re.search(r'(\d{4}\.\d{2}\.\d{2}\.\d{6})', original_url)
            if doi_match:
                doi = doi_match.group(1)
                alternatives.extend([
                    f"https://www.biorxiv.org/content/biorxiv/early/{doi[:4]}/{doi[5:7]}/{doi[8:10]}/{doi}.full.pdf",
                    f"https://www.biorxiv.org/content/early/{doi[:4]}/{doi[5:7]}/{doi[8:10]}/{doi}v1.full.pdf",
                    f"https://www.biorxiv.org/highwire/filestream/{doi}",
                    original_url.replace('.full.pdf', '.pdf'),
                    original_url.replace('v1.full.pdf', '.full.pdf')
                ])
        
        return alternatives 