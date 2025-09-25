#!/usr/bin/env python3
"""
🔗 ZotLink 提取器管理器

统一管理不同学术数据库的提取器，现在支持浏览器驱动模式
"""

import requests
import logging
import asyncio
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

from .base_extractor import BaseExtractor
from .nature_extractor import NatureExtractor
from .cvf_extractor import CVFExtractor
from .generic_extractor import GenericOpenAccessExtractor
from .browser_extractor import BrowserExtractor, PLAYWRIGHT_AVAILABLE
from .biorxiv_direct_extractor import BioRxivDirectExtractor

logger = logging.getLogger(__name__)

class ExtractorManager:
    """提取器管理器，支持HTTP和浏览器双模式"""
    
    def __init__(self):
        """初始化管理器"""
        self.session = requests.Session()
        self.extractors: List[BaseExtractor] = []
        self.cookies_store: Dict[str, str] = {}
        
        # 注册所有可用的提取器
        self._register_extractors()
        
        # 浏览器模式设置
        self.browser_available = PLAYWRIGHT_AVAILABLE
        if self.browser_available:
            logger.info("✅ 浏览器模式可用")
        else:
            logger.warning("⚠️ 浏览器模式不可用，需要安装Playwright")
    
    def _register_extractors(self):
        """注册所有提取器"""
        try:
            # 注册专用提取器 (优先级高)
            # bioRxiv专用提取器 - 最高优先级
            biorxiv_extractor = BioRxivDirectExtractor(self.session)
            self.extractors.append(biorxiv_extractor)
            logger.info("✅ 注册BioRxiv专用提取器")
            
            nature_extractor = NatureExtractor(self.session)
            self.extractors.append(nature_extractor)
            logger.info("✅ 注册Nature提取器")
            
            cvf_extractor = CVFExtractor(self.session)
            self.extractors.append(cvf_extractor)
            logger.info("✅ 注册CVF提取器")
            
            # 注册通用提取器 (作为后备)
            generic_extractor = GenericOpenAccessExtractor(self.session)
            self.extractors.append(generic_extractor)
            logger.info("✅ 注册通用开源提取器")
            
            logger.info(f"📊 总共注册了 {len(self.extractors)} 个HTTP提取器")
            if PLAYWRIGHT_AVAILABLE:
                logger.info("🌐 浏览器提取器动态可用")
            
        except Exception as e:
            logger.error(f"❌ 注册提取器失败: {e}")
    
    def _should_use_browser(self, url: str) -> bool:
        """判断是否应该使用浏览器模式"""
        if not self.browser_available:
            return False
            
        domain = urlparse(url).netloc.lower()
        browser_domains = [
            'biorxiv.org',
            'medrxiv.org', 
            'chemrxiv.org',
            'psyarxiv.com',
            'osf.io',
            'socarxiv.org'
        ]
        
        for browser_domain in browser_domains:
            if browser_domain in domain:
                logger.info(f"🌐 检测到需要浏览器模式的域名: {domain}")
                return True
        return False
    
    async def extract_metadata(self, url: str) -> Dict[str, Any]:
        """
        提取论文元数据，优先使用浏览器模式处理反爬虫网站
        """
        # 检查是否需要使用浏览器模式
        if self._should_use_browser(url):
            return await self._extract_with_browser(url)
        
        # 使用HTTP提取器
        return self._extract_with_http(url)
    
    async def _extract_with_browser(self, url: str) -> Dict[str, Any]:
        """使用浏览器提取器"""
        try:
            async with BrowserExtractor() as browser_extractor:
                metadata = await browser_extractor._async_extract_metadata(url)
                if metadata:
                    logger.info(f"🌐 浏览器模式成功提取元数据: {url}")
                    metadata['extractor'] = 'Browser-Driven'
                    return metadata
                else:
                    logger.warning(f"⚠️ 浏览器模式提取失败，回退到HTTP模式: {url}")
                    return self._extract_with_http(url)
        except Exception as e:
            logger.error(f"❌ 浏览器模式异常，回退到HTTP模式: {url} - {e}")
            return self._extract_with_http(url)
    
    def _extract_with_http(self, url: str) -> Dict[str, Any]:
        """使用HTTP提取器"""
        extractor = self.get_extractor_for_url(url)
        
        if not extractor:
            return {
                'error': '不支持的URL或数据库',
                'url': url,
                'supported_databases': [e.get_database_name() for e in self.extractors]
            }
        
        try:
            # 检查是否需要认证
            if extractor.requires_authentication():
                database_name = extractor.get_database_name()
                database_key = database_name.lower()
                if database_key not in self.cookies_store:
                    return {
                        'error': f'{database_name}需要认证，请先设置cookies',
                        'database': database_name,
                        'requires_auth': True,
                        'url': url
                    }
                
                # 设置cookies
                cookies = self.cookies_store[database_key]
                if not extractor.set_cookies(cookies):
                    return {
                        'error': f'设置{database_name} cookies失败',
                        'database': database_name,
                        'url': url
                    }
            
            # 执行元数据提取
            metadata = extractor.extract_metadata(url)
            
            # 添加提取器信息
            if 'error' not in metadata:
                metadata['extractor'] = extractor.get_database_name()
                metadata['authenticated'] = extractor.requires_authentication()
            
            logger.info(f"📊 HTTP模式成功提取元数据: {extractor.get_database_name()}")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ HTTP模式元数据提取异常: {e}")
            return {
                'error': f'提取过程异常: {e}',
                'database': extractor.get_database_name(),
                'url': url
            }
    
    def get_extractor_for_url(self, url: str) -> Optional[BaseExtractor]:
        """根据URL获取合适的HTTP提取器"""
        for extractor in self.extractors:
            try:
                if extractor.can_handle(url):
                    logger.info(f"🎯 选择HTTP提取器: {extractor.get_database_name()}")
                    return extractor
            except Exception as e:
                logger.warning(f"⚠️ 检查提取器失败: {e}")
                continue
        
        return None
    
    def set_database_cookies(self, database_name: str, cookies: str) -> bool:
        """为特定数据库设置cookies"""
        try:
            database_key = database_name.lower()
            self.cookies_store[database_key] = cookies
            logger.info(f"✅ 为{database_name}存储cookies")
            
            # 为相应的提取器设置cookies
            for extractor in self.extractors:
                if extractor.get_database_name().lower() == database_name.lower():
                    return extractor.set_cookies(cookies)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 设置{database_name} cookies失败: {e}")
            return False
    
    def get_supported_databases(self) -> List[Dict]:
        """获取所有支持的数据库信息"""
        databases = []
        
        # HTTP提取器支持的数据库
        for extractor in self.extractors:
            try:
                extractor_name = extractor.get_database_name()
                database_info = {
                    'name': extractor_name,
                    'requires_auth': extractor.requires_authentication(),
                    'has_cookies': extractor_name.lower() in self.cookies_store,
                    'supported_types': extractor.get_supported_item_types(),
                    'mode': 'HTTP'
                }
                databases.append(database_info)
            except Exception as e:
                logger.warning(f"⚠️ 获取提取器信息失败: {e}")
        
        # 浏览器模式支持的数据库
        if self.browser_available:
            for domain, info in BrowserExtractor.BROWSER_REQUIRED_DOMAINS.items():
                database_info = {
                    'name': info['source'],
                    'requires_auth': False,
                    'has_cookies': False,
                    'supported_types': [info['itemType']],
                    'mode': 'Browser',
                    'domain': domain
                }
                databases.append(database_info)
        
        return databases
    
    def get_supported_domains(self) -> Dict[str, str]:
        """获取支持的域名列表"""
        domains = {}
        
        # HTTP提取器支持的域名
        for extractor in self.extractors:
            if hasattr(extractor, 'OPEN_ACCESS_PATTERNS'):
                for pattern, info in extractor.OPEN_ACCESS_PATTERNS.items():
                    domains[pattern] = f"{extractor.__class__.__name__} (HTTP)"
            elif hasattr(extractor, 'SUPPORTED_DOMAINS'):
                for domain in extractor.SUPPORTED_DOMAINS:
                    domains[domain] = f"{extractor.__class__.__name__} (HTTP)"
        
        # 浏览器提取器支持的域名
        if self.browser_available:
            for domain, info in BrowserExtractor.BROWSER_REQUIRED_DOMAINS.items():
                domains[domain] = f"BrowserExtractor (浏览器模式)"
        
        return domains
    
    def test_database_access(self, database_name: str) -> Dict:
        """测试特定数据库的访问状态"""
        for extractor in self.extractors:
            if extractor.get_database_name().lower() == database_name.lower():
                try:
                    # 如果需要认证，先设置cookies
                    if extractor.requires_authentication():
                        database_key = database_name.lower()
                        if database_key not in self.cookies_store:
                            return {
                                'database': database_name,
                                'status': 'no_cookies',
                                'message': '需要先设置cookies'
                            }
                        
                        extractor.set_cookies(self.cookies_store[database_key])
                    
                    # 测试访问
                    has_access = extractor.test_access()
                    
                    return {
                        'database': database_name,
                        'status': 'success' if has_access else 'access_denied',
                        'message': '访问正常' if has_access else '访问被拒绝，可能需要更新cookies'
                    }
                    
                except Exception as e:
                    return {
                        'database': database_name,
                        'status': 'error',
                        'message': f'测试失败: {e}'
                    }
        
        return {
            'database': database_name,
            'status': 'not_supported',
            'message': '不支持的数据库'
        }
