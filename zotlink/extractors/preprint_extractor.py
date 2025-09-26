#!/usr/bin/env python3
"""
🔗 Preprint服务器提取器
处理 medRxiv 和 chemRxiv 等预印本网站的论文元数据提取
"""

import re
import requests
import logging
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class PreprintExtractor(BaseExtractor):
    """medRxiv和chemRxiv预印本提取器"""
    
    def __init__(self, session: requests.Session = None):
        """初始化预印本提取器"""
        super().__init__(session)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # 支持的域名配置
        self.domain_config = {
            'medrxiv.org': {
                'name': 'medRxiv',
                'type': 'preprint',
                'base_url': 'https://www.medrxiv.org',
                'pdf_pattern': r'10\.1101/(\d{4}\.\d{2}\.\d{2}\.\d+)',
                'pdf_template': 'https://www.medrxiv.org/content/10.1101/{doi}.full.pdf'
            },
            'chemrxiv.org': {
                'name': 'ChemRxiv', 
                'type': 'preprint',
                'base_url': 'https://chemrxiv.org',
                'pdf_pattern': r'/([a-f0-9-]+)/',
                'pdf_template': 'https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/{article_id}/original/manuscript.pdf'
            }
        }
    
    def can_handle(self, url: str) -> bool:
        """检查是否可以处理此URL"""
        return any(domain in url.lower() for domain in self.domain_config.keys())
    
    def requires_authentication(self) -> bool:
        """预印本网站通常不需要认证"""
        return False
    
    def get_database_name(self) -> str:
        """获取数据库名称"""
        return "Preprints"
    
    def extract_metadata(self, url: str) -> Dict[str, Any]:
        """从预印本URL提取论文元数据"""
        try:
            # 确定网站类型
            site_config = None
            for domain, config in self.domain_config.items():
                if domain in url.lower():
                    site_config = config
                    break
            
            if not site_config:
                return {"error": "不支持的预印本网站"}
            
            logger.info(f"🧬 提取{site_config['name']}论文元数据: {url}")
            
            # 获取页面内容
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return {'error': f'无法访问页面: {response.status_code}', 'url': url}
            
            soup = BeautifulSoup(response.content, 'html.parser')
            metadata = {}
            
            # 提取标题
            title = self._extract_title(soup, site_config)
            if title:
                metadata['title'] = title
                logger.info(f"✅ 提取标题: {title}")
            else:
                logger.warning("⚠️ 未找到标题")
            
            # 提取作者
            authors = self._extract_authors(soup, site_config)
            if authors:
                metadata['creators'] = authors
                logger.info(f"✅ 提取作者: {len(authors)}位")
            
            # 提取摘要
            abstract = self._extract_abstract(soup, site_config)
            if abstract:
                metadata['abstractNote'] = abstract
                logger.info(f"✅ 提取摘要: {len(abstract)}字符")
            
            # 提取DOI
            doi = self._extract_doi(soup, url, site_config)
            if doi:
                metadata['DOI'] = doi
                logger.info(f"✅ 提取DOI: {doi}")
            
            # 构造PDF URL
            pdf_url = self._construct_pdf_url(url, doi, site_config)
            if pdf_url:
                metadata['pdf_url'] = pdf_url
                logger.info(f"✅ 构造PDF链接: {pdf_url}")
            
            # 设置基本字段
            metadata.update({
                'extractor': site_config['name'],
                'itemType': site_config['type'],
                'url': url,
                'libraryCatalog': site_config['name'],
                'repository': site_config['name']
            })
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ {site_config['name'] if site_config else '预印本'}元数据提取失败: {e}")
            return {
                'error': f'预印本元数据提取失败: {str(e)}',
                'url': url
            }
    
    def _extract_title(self, soup: BeautifulSoup, site_config: Dict) -> Optional[str]:
        """提取标题"""
        title_selectors = [
            'meta[name="citation_title"]',
            'meta[name="dc.title"]',
            'meta[property="og:title"]',
            'h1.highwire-cite-title',
            'h1#page-title',
            'h1.article-title',
            '.article-title h1',
            'h1.entry-title',
            'h1'
        ]
        
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    title = element.get('content', '').strip()
                else:
                    title = element.get_text().strip()
                
                # 清理标题
                title = re.sub(r'\s+', ' ', title)
                title = re.sub(r'^\s*[-–]\s*', '', title)
                
                if title and len(title) > 10:
                    return title
        
        return None
    
    def _extract_authors(self, soup: BeautifulSoup, site_config: Dict) -> List[Dict]:
        """提取作者"""
        authors = []
        
        # 尝试从meta标签提取
        meta_authors = soup.select('meta[name="citation_author"]')
        if meta_authors:
            for meta in meta_authors[:15]:  # 限制作者数量
                author_name = meta.get('content', '').strip()
                if author_name:
                    authors.append(self._parse_author_name(author_name))
        
        # 如果meta标签没有，尝试从页面内容提取
        if not authors:
            author_selectors = [
                '.contrib-group .contrib',
                '.author-list .author',
                '.authors .author',
                '.highwire-cite-authors .contrib'
            ]
            
            for selector in author_selectors:
                author_elements = soup.select(selector)
                if author_elements:
                    for author_el in author_elements[:15]:
                        author_name = author_el.get_text().strip()
                        if author_name:
                            authors.append(self._parse_author_name(author_name))
                    break
        
        return authors
    
    def _parse_author_name(self, author_name: str) -> Dict:
        """解析作者姓名"""
        # 清理作者姓名
        author_name = re.sub(r'[,\d\*†‡§¶#].*$', '', author_name).strip()
        
        name_parts = author_name.split()
        if len(name_parts) >= 2:
            return {
                "creatorType": "author",
                "firstName": " ".join(name_parts[:-1]),
                "lastName": name_parts[-1]
            }
        else:
            return {
                "creatorType": "author",
                "firstName": "",
                "lastName": author_name
            }
    
    def _extract_abstract(self, soup: BeautifulSoup, site_config: Dict) -> Optional[str]:
        """提取摘要"""
        abstract_selectors = [
            'meta[name="citation_abstract"]',
            'meta[name="dc.description"]',
            '.abstract p',
            '#abstract p',
            '.article-summary p',
            '.summary p'
        ]
        
        for selector in abstract_selectors:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    abstract = element.get('content', '').strip()
                else:
                    abstract = element.get_text().strip()
                
                if abstract and len(abstract) > 50:
                    return abstract
        
        return None
    
    def _extract_doi(self, soup: BeautifulSoup, url: str, site_config: Dict) -> Optional[str]:
        """提取DOI"""
        # 尝试从meta标签提取
        doi_meta = soup.select_one('meta[name="citation_doi"]')
        if doi_meta:
            doi = doi_meta.get('content', '').strip()
            if doi:
                return doi
        
        # 从URL提取DOI
        if 'medrxiv.org' in url.lower():
            doi_match = re.search(r'10\.1101/(\d{4}\.\d{2}\.\d{2}\.\d+)', url)
            if doi_match:
                return f"10.1101/{doi_match.group(1)}"
        
        return None
    
    def _construct_pdf_url(self, url: str, doi: Optional[str], site_config: Dict) -> Optional[str]:
        """构造PDF URL"""
        if 'medrxiv.org' in url.lower() and doi:
            doi_id = doi.replace('10.1101/', '')
            return f"https://www.medrxiv.org/content/10.1101/{doi_id}.full.pdf"
        
        elif 'chemrxiv.org' in url.lower():
            article_match = re.search(r'/([a-f0-9-]{36})/', url)
            if article_match:
                article_id = article_match.group(1)
                return f"https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/{article_id}/original/manuscript.pdf"
        
        return None
    
    def test_access(self, test_url: str = None) -> bool:
        """测试网站访问"""
        if not test_url:
            test_url = "https://www.medrxiv.org/"
        
        try:
            response = self.session.get(test_url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def get_supported_item_types(self) -> List[str]:
        """获取支持的条目类型"""
        return ['preprint']
