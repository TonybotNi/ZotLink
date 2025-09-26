#!/usr/bin/env python3
"""
🚀 BioRxiv终极下载器
使用所有可能的反爬虫绕过技术
"""

import asyncio
import logging
import tempfile
import os
import time
import requests
import json
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class BioRxivDownloader:
    """BioRxiv专用下载器类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def method_1_smart_http(self, pdf_url: str) -> Optional[bytes]:
        """方法1: 智能HTTP请求（多步预热）"""
        try:
            logger.info("🎯 方法1: 智能HTTP请求")
            
            # 步骤1: 访问bioRxiv主页
            logger.info("  1.1 访问bioRxiv主页...")
            self.session.get('https://www.biorxiv.org/', timeout=10)
            time.sleep(0.5)
            
            # 步骤2: 访问论文页面
            paper_url = pdf_url.replace('.full.pdf', '').replace('/pdf/', '/content/')
            logger.info(f"  1.2 访问论文页面: {paper_url}")
            
            paper_resp = self.session.get(paper_url, timeout=15)
            if paper_resp.status_code != 200:
                logger.warning(f"    论文页面访问失败: {paper_resp.status_code}")
                return None
            
            time.sleep(1)  # 模拟人类阅读时间
            
            # 步骤3: 访问PDF URL
            logger.info(f"  1.3 访问PDF URL: {pdf_url}")
            pdf_headers = self.session.headers.copy()
            pdf_headers.update({
                'Accept': 'application/pdf,*/*',
                'Referer': paper_url,
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin'
            })
            
            pdf_resp = self.session.get(pdf_url, headers=pdf_headers, timeout=30)
            
            if pdf_resp.status_code == 200:
                content = pdf_resp.content
                if content and content.startswith(b'%PDF'):
                    logger.info(f"  ✅ 智能HTTP成功: {len(content)} bytes")
                    return content
                else:
                    logger.warning("  ❌ 返回内容不是PDF")
            else:
                logger.warning(f"  ❌ PDF请求失败: {pdf_resp.status_code}")
            
            return None
            
        except Exception as e:
            logger.warning(f"  ❌ 智能HTTP异常: {e}")
            return None
    
    async def method_2_playwright_stealth(self, pdf_url: str) -> Optional[bytes]:
        """方法2: 超级隐身浏览器"""
        try:
            from playwright.async_api import async_playwright
            
            logger.info("🥷 方法2: 超级隐身浏览器")
            
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor,TranslateUI',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-images',  # 禁用图片加载，提速
                    '--disable-javascript',  # 禁用JavaScript，避免检测
                    '--user-data-dir=/tmp/chrome_user_data'
                ]
            )
            
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            )
            
            page = await context.new_page()
            
            # 设置下载处理
            download_info = {'completed': False, 'content': None}
            
            async def handle_download(download):
                try:
                    temp_path = tempfile.mktemp(suffix='.pdf')
                    await download.save_as(temp_path)
                    
                    with open(temp_path, 'rb') as f:
                        content = f.read()
                    
                    os.unlink(temp_path)
                    
                    if content and content.startswith(b'%PDF'):
                        download_info['content'] = content
                        download_info['completed'] = True
                        logger.info(f"  ✅ 浏览器下载成功: {len(content)} bytes")
                except Exception as e:
                    logger.error(f"  ❌ 下载处理异常: {e}")
            
            page.on("download", handle_download)
            
            # 多阶段导航
            try:
                logger.info("  2.1 访问bioRxiv主页...")
                await page.goto('https://www.biorxiv.org/', timeout=20000)
                await asyncio.sleep(1)
                
                paper_url = pdf_url.replace('.full.pdf', '').replace('/pdf/', '/content/')
                logger.info("  2.2 访问论文页面...")
                await page.goto(paper_url, timeout=20000)
                await asyncio.sleep(2)
                
                logger.info("  2.3 直接访问PDF...")
                await page.goto(pdf_url, timeout=30000)
            except Exception as e:
                logger.info(f"  2.x 导航异常（可能正常）: {e}")
            
            # 等待下载
            for i in range(100):  # 10秒
                if download_info['completed']:
                    break
                await asyncio.sleep(0.1)
            
            await context.close()
            await browser.close()
            await playwright.stop()
            
            return download_info.get('content')
            
        except Exception as e:
            logger.warning(f"  ❌ 隐身浏览器异常: {e}")
            return None
    
    async def method_3_curl_simulation(self, pdf_url: str) -> Optional[bytes]:
        """方法3: 模拟curl请求"""
        try:
            logger.info("🌐 方法3: 模拟curl请求")
            
            import subprocess
            
            # 使用curl模拟真实浏览器请求
            paper_url = pdf_url.replace('.full.pdf', '').replace('/pdf/', '/content/')
            
            # 第一步：获取论文页面的cookies
            logger.info("  3.1 使用curl获取cookies...")
            curl_cmd1 = [
                'curl', '-s', '-L',
                '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                '-H', 'Accept-Language: en-US,en;q=0.5',
                '-H', 'Accept-Encoding: gzip, deflate',
                '-H', 'Connection: keep-alive',
                '-H', 'Upgrade-Insecure-Requests: 1',
                '-c', '/tmp/biorxiv_cookies.txt',
                paper_url
            ]
            
            subprocess.run(curl_cmd1, capture_output=True, timeout=15)
            
            # 第二步：使用cookies下载PDF
            logger.info("  3.2 使用cookies下载PDF...")
            curl_cmd2 = [
                'curl', '-s', '-L',
                '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '-H', 'Accept: application/pdf,*/*',
                '-H', f'Referer: {paper_url}',
                '-H', 'Connection: keep-alive',
                '-b', '/tmp/biorxiv_cookies.txt',
                '-o', '/tmp/biorxiv_curl.pdf',
                pdf_url
            ]
            
            result = subprocess.run(curl_cmd2, capture_output=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists('/tmp/biorxiv_curl.pdf'):
                with open('/tmp/biorxiv_curl.pdf', 'rb') as f:
                    content = f.read()
                
                # 清理临时文件
                try:
                    os.unlink('/tmp/biorxiv_curl.pdf')
                    os.unlink('/tmp/biorxiv_cookies.txt')
                except:
                    pass
                
                if content and content.startswith(b'%PDF'):
                    logger.info(f"  ✅ curl下载成功: {len(content)} bytes")
                    return content
            
            return None
            
        except Exception as e:
            logger.warning(f"  ❌ curl模拟异常: {e}")
            return None
    
    def method_4_proxy_rotation(self, pdf_url: str) -> Optional[bytes]:
        """方法4: 代理轮换（如果可用）"""
        try:
            logger.info("🔄 方法4: 代理轮换")
            
            # 一些免费代理（实际使用时应该用更好的代理服务）
            proxies_list = [
                None,  # 直连
                # 可以在这里添加代理服务器
            ]
            
            for i, proxy in enumerate(proxies_list):
                try:
                    logger.info(f"  4.{i+1} 尝试代理: {proxy or '直连'}")
                    
                    session = requests.Session()
                    if proxy:
                        session.proxies.update({'http': proxy, 'https': proxy})
                    
                    session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    })
                    
                    # 快速尝试
                    resp = session.get(pdf_url, timeout=10)
                    if resp.status_code == 200 and resp.content.startswith(b'%PDF'):
                        logger.info(f"  ✅ 代理成功: {len(resp.content)} bytes")
                        return resp.content
                        
                except Exception as e:
                    logger.info(f"  ❌ 代理{i+1}失败: {e}")
                    continue
            
            return None
            
        except Exception as e:
            logger.warning(f"  ❌ 代理轮换异常: {e}")
            return None


def download_biorxiv_pdf(pdf_url: str) -> Optional[bytes]:
    """主入口：终极bioRxiv下载器"""
    logger.info(f"🚀 启动终极bioRxiv下载器: {pdf_url}")
    
    downloader = BioRxivDownloader()
    methods = [
        ("智能HTTP", downloader.method_1_smart_http),
        # 🔧 暂时禁用异步方法，避免event loop冲突
        # ("隐身浏览器", lambda url: asyncio.run(downloader.method_2_playwright_stealth(url))),
        # ("curl模拟", lambda url: asyncio.run(downloader.method_3_curl_simulation(url))),
        ("代理轮换", downloader.method_4_proxy_rotation),
    ]
    
    for method_name, method_func in methods:
        try:
            logger.info(f"\n🔄 尝试方法: {method_name}")
            content = method_func(pdf_url)
            
            if content:
                logger.info(f"🎉 {method_name}成功！")
                return content
            else:
                logger.info(f"⚠️ {method_name}失败")
                
        except Exception as e:
            logger.warning(f"❌ {method_name}异常: {e}")
            continue
    
    logger.error("💥 所有方法都失败了！bioRxiv的反爬虫太强了")
    return None


if __name__ == "__main__":
    # 测试
    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
    
    test_url = "https://www.biorxiv.org/content/10.1101/2025.09.21.677607v1.full.pdf"
    
    print(f"🧪 测试终极下载器: {test_url}")
    print("=" * 60)
    
    content = download_biorxiv_pdf(test_url)
    
    if content:
        print(f"\n✅ 成功！下载了 {len(content)} bytes")
        with open('/tmp/test_biorxiv_ultimate.pdf', 'wb') as f:
            f.write(content)
        print("📁 测试文件已保存到 /tmp/test_biorxiv_ultimate.pdf")
    else:
        print("\n❌ 终极下载器也失败了...")
        print("💡 建议：bioRxiv可能需要更高级的反爬虫绕过技术")
        print("💡 比如：真实浏览器扩展、验证码识别、或付费代理服务") 