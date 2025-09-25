#!/usr/bin/env python3
"""
🛡️ 反爬虫PDF下载器 - 增强版
专门用于下载bioRxiv等反爬虫网站的PDF内容
"""

import asyncio
import logging
import tempfile
import os
import time
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

async def download_anti_crawler_pdf_async(pdf_url: str) -> Optional[bytes]:
    """
    使用浏览器模式下载反爬虫网站的PDF - 增强版
    
    Args:
        pdf_url: PDF链接
        
    Returns:
        PDF文件的二进制内容，失败返回None
    """
    try:
        from playwright.async_api import async_playwright
        
        logger.info(f"🌐 启动浏览器下载PDF: {pdf_url}")
        
        playwright = await async_playwright().start()
        
        # 使用更真实的浏览器配置
        browser = await playwright.chromium.launch(
            headless=False,  # 使用有头模式更容易绕过检测
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation', 'notifications'],
            accept_downloads=True,  # 明确接受下载
            ignore_https_errors=True
        )
        
        # 添加额外的浏览器标识来绕过检测
        await context.add_init_script("""
            // 移除webdriver标识
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // 添加Chrome特性
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // 修改navigator.plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // 修改navigator.languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        page = await context.new_page()
        
        # 设置额外的headers
        await page.set_extra_http_headers({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
        try:
            # 方法1：监听下载事件
            download_info = {'completed': False, 'content': None, 'error': None}
            
            async def handle_download(download):
                nonlocal download_info
                try:
                    logger.info(f"🎯 检测到PDF下载: {download.url}")
                    
                    # 创建临时文件保存下载内容
                    temp_dir = tempfile.gettempdir()
                    temp_path = os.path.join(temp_dir, f"temp_pdf_{int(time.time())}.pdf")
                    
                    await download.save_as(temp_path)
                    
                    # 读取下载的文件内容
                    with open(temp_path, 'rb') as f:
                        pdf_bytes = f.read()
                    
                    # 清理临时文件
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    
                    if pdf_bytes and pdf_bytes.startswith(b'%PDF'):
                        download_info['content'] = pdf_bytes
                        download_info['completed'] = True
                        logger.info(f"✅ 浏览器下载成功: {len(pdf_bytes)} bytes")
                    else:
                        download_info['error'] = "下载的内容不是有效PDF"
                        
                except Exception as e:
                    download_info['error'] = str(e)
                    logger.error(f"❌ 下载处理异常: {e}")
            
            # 设置下载监听
            page.on("download", handle_download)
            
            # 方法2：如果是bioRxiv，先访问主页面获取cookie
            if 'biorxiv.org' in pdf_url or 'medrxiv.org' in pdf_url:
                # 从PDF URL构建主页面URL
                import re
                match = re.search(r'(\d+\.\d+/\d+\.\d+\.\d+\.\d+v\d+)', pdf_url)
                if match:
                    doi = match.group(1)
                    main_url = f"https://www.biorxiv.org/content/{doi}"
                    
                    logger.info(f"📄 先访问主页面: {main_url}")
                    
                    # 访问主页面获取cookie和session
                    try:
                        await page.goto(main_url, wait_until='networkidle', timeout=30000)
                        await asyncio.sleep(2)  # 等待页面完全加载
                        
                        # 查找并点击PDF链接
                        pdf_link = await page.query_selector('a[href*=".full.pdf"]')
                        if pdf_link:
                            logger.info("🖱️ 找到PDF链接，点击下载...")
                            
                            # 点击链接触发下载
                            await pdf_link.click()
                            
                            # 等待下载完成
                            for i in range(30):
                                if download_info['completed'] or download_info['error']:
                                    break
                                await asyncio.sleep(1)
                            
                            if download_info['completed']:
                                return download_info['content']
                    except Exception as e:
                        logger.warning(f"⚠️ 主页面方法失败: {e}")
            
            # 方法3：直接导航到PDF URL
            logger.info("📥 尝试直接访问PDF URL...")
            try:
                # 使用response事件来捕获PDF内容
                pdf_content = None
                
                async def handle_response(response):
                    nonlocal pdf_content
                    if response.url == pdf_url and response.status == 200:
                        try:
                            body = await response.body()
                            if body and body.startswith(b'%PDF'):
                                pdf_content = body
                                logger.info(f"✅ 从响应获取PDF: {len(body)} bytes")
                        except:
                            pass
                
                page.on("response", handle_response)
                
                await page.goto(pdf_url, wait_until='networkidle', timeout=30000)
                
                # 等待下载或响应
                for i in range(20):
                    if download_info['completed'] or pdf_content:
                        break
                    await asyncio.sleep(1)
                
                if download_info['completed']:
                    return download_info['content']
                elif pdf_content:
                    return pdf_content
                    
            except Exception as e:
                # 下载被触发时会有异常，这是正常的
                logger.info(f"⚡ 导航异常（可能是下载触发）: {str(e)[:100]}")
                
                # 等待下载完成
                for i in range(20):
                    if download_info['completed'] or download_info['error']:
                        break
                    await asyncio.sleep(1)
                
                if download_info['completed']:
                    return download_info['content']
            
            # 如果都失败了，返回None
            if download_info['error']:
                logger.warning(f"⚠️ 下载失败: {download_info['error']}")
            else:
                logger.warning("⚠️ 下载超时或未触发")
            
            return None
            
        finally:
            await page.close()
            await context.close()
            await browser.close()
            await playwright.stop()
            
    except Exception as e:
        logger.error(f"❌ 浏览器PDF下载异常: {e}")
        import traceback
        traceback.print_exc()
        return None


def download_anti_crawler_pdf(pdf_url: str) -> Optional[bytes]:
    """
    同步包装器：下载反爬虫网站的PDF
    
    Args:
        pdf_url: PDF链接
        
    Returns:
        PDF文件的二进制内容，失败返回None
    """
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(download_anti_crawler_pdf_async(pdf_url))
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ 同步下载异常: {e}")
        return None


def is_anti_crawler_site(url: str) -> bool:
    """检查是否为反爬虫网站"""
    anti_crawler_domains = [
        'biorxiv.org', 'medrxiv.org', 'chemrxiv.org', 
        'psyarxiv.com', 'socarxiv.org', 'osf.io'
    ]
    return any(domain in url.lower() for domain in anti_crawler_domains)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 测试下载
    test_urls = [
        "https://www.biorxiv.org/content/10.1101/2025.09.21.677607v1.full.pdf",
        "https://www.biorxiv.org/content/10.1101/2025.09.22.677711v1.full.pdf"
    ]
    
    for test_url in test_urls:
        print(f"\n🧪 测试下载: {test_url}")
        
        content = download_anti_crawler_pdf(test_url)
        
        if content:
            print(f"✅ 下载成功: {len(content)} bytes")
            
            # 保存测试文件
            filename = f'/tmp/test_biorxiv_{int(time.time())}.pdf'
            with open(filename, 'wb') as f:
                f.write(content)
            print(f"📁 测试文件已保存到 {filename}")
        else:
            print("❌ 下载失败") 