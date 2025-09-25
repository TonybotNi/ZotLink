#!/usr/bin/env python3
"""
🧬 BioRxiv专用直接提取器
使用验证成功的MCP浏览器技术
"""

import asyncio
import tempfile
import os
import re
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class BioRxivDirectExtractor(BaseExtractor):
    """BioRxiv专用提取器 - 已验证可绕过反爬虫"""
    
    def __init__(self, session=None):
        super().__init__(session)
    
    def get_database_name(self) -> str:
        """返回数据库名称"""
        return "bioRxiv"
    
    def requires_authentication(self) -> bool:
        """返回是否需要认证"""
        return False
    
    def can_handle(self, url: str) -> bool:
        """检查是否是bioRxiv URL"""
        return 'biorxiv.org' in url.lower()
    
    def extract_metadata(self, url: str) -> Dict[str, Any]:
        """提取bioRxiv论文元数据和PDF内容"""
        if not self.can_handle(url):
            return {}
        
        logger.info(f"🧬 使用BioRxiv专用提取器: {url}")
        
        # 从URL提取基本信息
        basic_info = self._extract_from_url(url)
        
        # 下载PDF内容
        pdf_content = self._download_pdf_content(basic_info['pdf_url'])
        
        if pdf_content:
            basic_info['pdf_content'] = pdf_content
            basic_info['pdf_size'] = len(pdf_content)
            logger.info(f"✅ BioRxiv PDF下载成功: {len(pdf_content):,} bytes")
        else:
            logger.warning("⚠️ BioRxiv PDF下载失败")
        
        return basic_info
    
    def _extract_from_url(self, url: str) -> Dict[str, Any]:
        """从URL提取基本信息"""
        # 提取DOI和日期
        doi_match = re.search(r'10\.1101/(\d{4})\.(\d{2})\.(\d{2})\.(\d+)', url)
        if not doi_match:
            return {"error": "无法从URL提取DOI"}
        
        year, month, day, version = doi_match.groups()
        doi = f"10.1101/{year}.{month}.{day}.{version}"
        paper_id = f"{year}.{month}.{day}.{version}"
        
        # 构造元数据
        metadata = {
            "itemType": "preprint", 
            "title": f"bioRxiv preprint {paper_id}",
            "creators": [{"creatorType": "author", "firstName": "Unknown", "lastName": "Author"}],
            "abstractNote": "bioRxiv preprint - PDF auto-downloaded",
            "url": url,
            "DOI": doi,
            "repository": "bioRxiv", 
            "archiveID": paper_id,
            "date": f"{year}-{month}-{day}",
            "libraryCatalog": "bioRxiv",
            "pdf_url": f"https://www.biorxiv.org/content/10.1101/{paper_id}.full.pdf",
            "extractor": "BioRxiv-Direct"
        }
        
        return metadata
    
    def _download_pdf_content(self, pdf_url: str) -> Optional[bytes]:
        """下载PDF内容（在新线程中执行异步任务）"""
        try:
            import concurrent.futures
            
            def download_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(self._async_download_pdf(pdf_url))
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(download_in_thread)
                return future.result(timeout=60)
                
        except Exception as e:
            logger.error(f"❌ PDF下载线程异常: {e}")
            return None
    
    async def _async_download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """异步下载PDF - 使用验证成功的MCP方法"""
        from playwright.async_api import async_playwright
        
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-web-security',
                '--allow-running-insecure-content',
                '--disable-features=TranslateUI',
                '--no-first-run',
                '--no-default-browser-check'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'DNT': '1'
            }
        )
        
        page = await context.new_page()
        
        # 反检测脚本
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [{name: 'Chrome PDF Plugin'}]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            delete Object.getPrototypeOf(navigator).webdriver;
        """)
        
        try:
            download_success = False
            pdf_content = None
            
            async def handle_download(download):
                nonlocal download_success, pdf_content
                try:
                    temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                    temp_path = temp_file.name
                    temp_file.close()
                    
                    await download.save_as(temp_path)
                    
                    with open(temp_path, 'rb') as f:
                        pdf_content = f.read()
                    
                    if pdf_content and pdf_content.startswith(b'%PDF'):
                        download_success = True
                        logger.info(f"✅ PDF下载成功: {len(pdf_content):,} bytes")
                    
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                except Exception as e:
                    logger.warning(f"⚠️ PDF下载处理异常: {e}")
            
            page.on("download", handle_download)
            
            # 多步骤访问
            await page.goto('https://www.biorxiv.org/', wait_until='networkidle', timeout=20000)
            await asyncio.sleep(2)
            
            # 触发下载
            try:
                await page.evaluate(f"window.open('{pdf_url}', '_blank')")
            except:
                pass
            
            # 等待下载
            for i in range(30):
                if download_success:
                    break
                await asyncio.sleep(1)
            
            return pdf_content
            
        finally:
            await context.close()
            await browser.close()
            await playwright.stop() 