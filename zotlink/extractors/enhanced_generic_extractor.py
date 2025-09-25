#!/usr/bin/env python3
"""
基于Zotero Connector架构的增强版通用提取器
解决重定向问题和改进PDF检测逻辑
"""

import requests
import re
import time
import logging
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup # Added for _process_successful_response

from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class EnhancedGenericExtractor(BaseExtractor):
    """
    基于Zotero Connector重新设计的增强版通用提取器
    """
    
    # 主要附件类型 (类似Zotero的PRIMARY_ATTACHMENT_TYPES)
    PRIMARY_ATTACHMENT_TYPES = {
        'application/pdf',
        'application/epub+zip'
    }
    
    # 支持的域名配置
    DOMAIN_CONFIGS = {
        # arXiv系列
        'arxiv.org': {
            'type': 'preprint',
            'source': 'arXiv',
            'priority': 1,
            'pdf_patterns': [
                r'href="([^"]*\.pdf)"',
                r'href="(/pdf/[^"]+)"',
                r'<meta[^>]*name="citation_pdf_url"[^>]*content="([^"]+)"',
            ]
        },
        # medRxiv系列 
        'medrxiv.org': {
            'type': 'preprint', 
            'source': 'medRxiv',
            'priority': 1,
            'pdf_patterns': [
                r'<meta[^>]*name="citation_pdf_url"[^>]*content="([^"]+)"',
                r'href="([^"]*\.full\.pdf[^"]*)"',
            ]
        },
        'biorxiv.org': {
            'type': 'preprint',
            'source': 'bioRxiv', 
            'priority': 1,
            'pdf_patterns': [
                r'<meta[^>]*name="citation_pdf_url"[^>]*content="([^"]+)"',
                r'href="([^"]*\.full\.pdf[^"]*)"',
            ]
        },
        # ChemRxiv
        'chemrxiv.org': {
            'type': 'preprint',
            'source': 'ChemRxiv',
            'priority': 1,
            'pdf_patterns': [
                r'href="([^"]*ndownloader[^"]*)"',
                r'href="([^"]*download[^"]*)"[^>]*>(?:[^<]*(?:PDF|pdf)[^<]*)</a>',
            ]
        },
        # OSF系列
        'osf.io/preprints/psyarxiv': {
            'type': 'preprint',
            'source': 'PsyArXiv', 
            'priority': 1,
            'pdf_patterns': []  # 将使用OSF的特殊处理
        },
        'osf.io/preprints/socarxiv': {
            'type': 'preprint',
            'source': 'SocArXiv',
            'priority': 1, 
            'pdf_patterns': []  # 将使用OSF的特殊处理
        }
    }
    
    def __init__(self, session=None):
        """
        初始化增强通用提取器
        
        Args:
            session: requests会话对象
        """
        super().__init__(session=session)
        self.session = requests.Session()
        
        # 反爬虫网站列表 - 需要强制使用浏览器模式
        self.anti_crawler_sites = {
            'biorxiv.org', 'medrxiv.org', 'chemrxiv.org', 
            'psyarxiv.com', 'socarxiv.org', 'osf.io',
            'researchsquare.com', 'authorea.com'
        }
        
        # 配置会话headers
        self._setup_session()

    def requires_authentication(self) -> bool:
        """检查此提取器是否需要认证"""
        return False
    
    def get_database_name(self) -> str:
        """获取数据库名称"""
        return "Enhanced Generic Extractor"
    
    def can_handle(self, url: str) -> bool:
        """检查是否可以处理该URL"""
        # 增强提取器可以处理任何URL，但会根据域名优化策略
        return True
        url_lower = url.lower()
        for domain_pattern in self.DOMAIN_CONFIGS.keys():
            if domain_pattern in url_lower:
                return True
        return False
    
    def extract_metadata(self, url: str) -> Dict:
        """
        提取论文元数据的主入口（覆盖基类方法）
        
        Returns:
            包含论文信息的字典，如果遇到403错误会自动使用反爬虫处理策略
        """
        logger.info(f"🔍 开始提取论文信息: {url}")
        
        try:
            # 首先尝试常规HTTP请求
            response = self.session.get(url, timeout=30, allow_redirects=True)
            
            # 如果遇到403错误，使用反爬虫处理策略
            if response.status_code == 403:
                logger.warning(f"🚫 检测到403响应，启用反爬虫处理策略")
                return self._handle_403_response(url)
            
            elif response.status_code != 200:
                logger.warning(f"⚠️ HTTP状态码异常: {response.status_code}")
                # 对于其他错误状态码，也尝试反爬虫处理策略
                if self._is_anti_crawler_site(url):
                    return self._handle_403_response(url)
                    
                return {
                    'error': f'HTTP错误: {response.status_code}',
                    'status_code': response.status_code
                }
            
            # 正常处理HTTP 200响应
            return self._process_successful_response(response, url)
            
        except requests.exceptions.Timeout:
            logger.error(f"⏰ 请求超时: {url}")
            # 超时也可能是反爬虫机制，尝试浏览器模式
            if self._is_anti_crawler_site(url):
                return self._handle_403_response(url)
            return {'error': '请求超时'}
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"🌐 连接错误: {e}")
            if self._is_anti_crawler_site(url):
                return self._handle_403_response(url)
            return {'error': f'连接错误: {str(e)}'}
            
        except Exception as e:
            logger.error(f"❌ 提取异常: {e}")
            return {'error': f'提取异常: {str(e)}'}

    def _process_successful_response(self, response: requests.Response, url: str) -> Dict:
        """处理成功的HTTP响应"""
        html_content = response.text
        final_url = response.url
        
        logger.info(f"✅ 成功获取页面内容 (长度: {len(html_content)})")
        
        # 解析HTML并提取信息
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 从域名配置中获取提取策略
        domain_info = self._identify_domain(final_url)
        
        # 基础元数据提取
        metadata = self._extract_comprehensive_metadata(html_content, final_url)
        
        # URL特定的增强处理
        metadata = self._enhance_url_specific_metadata(metadata, final_url)
        
        # 预印本特有字段增强
        if metadata.get('itemType') == 'preprint':
            metadata = self._enhance_preprint_metadata(metadata)
        
        # PDF附件检测
        page_data = {'content': html_content, 'final_url': final_url}
        attachments = self._detect_pdf_attachments(page_data, domain_info)
        
        # 选择主要PDF
        primary_pdf = self._select_primary_pdf(attachments)
        if primary_pdf:
            metadata['pdf_url'] = primary_pdf['url']
            metadata['pdf_source'] = primary_pdf['type']
        
        # 站点特定的后处理
        metadata = self._post_process_by_site(metadata, domain_info)
        
        # 验证必要字段
        if not metadata.get('title'):
            metadata['title'] = f"Paper from {self._extract_domain(final_url)}"
        
        logger.info(f"📝 提取完成 - 标题: {metadata.get('title', 'N/A')[:50]}...")
        return metadata
    
    def _fetch_with_redirect_tracking(self, url: str) -> Optional[Dict]:
        """
        获取页面内容并跟踪重定向链
        类似于Zotero Connector的重定向处理
        """
        redirect_chain = []
        current_url = url
        
        try:
            for i in range(10):  # 最多跟踪10次重定向
                logger.debug(f"🔗 请求: {current_url}")
                
                response = self.session.get(current_url, timeout=15, allow_redirects=False)
                
                redirect_info = {
                    'url': current_url,
                    'status': response.status_code,
                    'headers': dict(response.headers)
                }
                redirect_chain.append(redirect_info)
                
                if response.status_code in (301, 302, 303, 307, 308):
                    # 处理重定向
                    location = response.headers.get('Location')
                    if not location:
                        break
                    
                    # 处理相对URL
                    if not location.startswith('http'):
                        location = urljoin(current_url, location)
                    
                    logger.info(f"↳ 重定向: {current_url} → {location}")
                    current_url = location
                    time.sleep(0.3)  # 避免过快请求
                    
                elif response.status_code == 200:
                    # 成功获取内容
                    return {
                        'content': response.text,
                        'final_url': current_url,
                        'redirect_chain': redirect_chain,
                        'final_headers': dict(response.headers)
                    }
                else:
                    # 其他错误
                    logger.warning(f"⚠️ HTTP错误: {response.status_code}")
                    break
            
            logger.error(f"❌ 重定向次数过多或其他错误")
            return None
            
        except Exception as e:
            logger.error(f"❌ 请求失败: {e}")
            return None
    
    def _identify_domain(self, url: str) -> Dict:
        """识别域名类型"""
        url_lower = url.lower()
        
        for domain_pattern, config in self.DOMAIN_CONFIGS.items():
            if domain_pattern in url_lower:
                return {
                    'type': config['type'],
                    'source': config['source'],
                    'priority': config['priority'],
                    'patterns': config['pdf_patterns']
                }
        
        # 默认配置
        return {
            'type': 'webpage',
            'source': 'Generic',
            'priority': 9,
            'patterns': []
        }
    
    def _extract_comprehensive_metadata(self, html_content: str, url: str) -> Dict:
        """提取全面的元数据"""
        metadata = {'url': url}
        
        # Citation标签 - 最高优先级
        citation_fields = {
            'citation_title': 'title',
            'citation_author': 'authors',
            'citation_journal_title': 'publicationTitle',
            'citation_conference_title': 'publicationTitle',
            'citation_publisher': 'publisher',
            'citation_publication_date': 'date',
            'citation_online_date': 'date',
            'citation_doi': 'DOI',
            'citation_pmid': 'pmid',
            'citation_pmcid': 'pmcid',
            'citation_pdf_url': 'pdf_url',
            'citation_abstract': 'abstract',
            'citation_keywords': 'tags'
        }
        
        # 收集所有作者
        all_authors = []
        
        for citation_name, field_name in citation_fields.items():
            pattern = rf'<meta[^>]*name="{citation_name}"[^>]*content="([^"]+)"'
            if citation_name == 'citation_author':
                # 收集所有作者
                authors = re.findall(pattern, html_content, re.IGNORECASE)
                all_authors.extend(authors)
            else:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match and field_name not in metadata:
                    metadata[field_name] = match.group(1)
        
        # 设置作者信息
        if all_authors:
            metadata['authors'] = all_authors
        
        # Dublin Core标签 - 中等优先级
        dc_fields = {
            'DC.title': 'title',
            'DC.creator': 'authors', 
            'DC.date': 'date',
            'DC.publisher': 'publisher',
            'DC.description': 'abstract'
        }
        
        for dc_name, field_name in dc_fields.items():
            if field_name not in metadata:
                pattern = rf'<meta[^>]*name="{dc_name}"[^>]*content="([^"]+)"'
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    metadata[field_name] = match.group(1)
        
        # Open Graph标签 - 低优先级
        og_fields = {
            'og:title': 'title',
            'og:description': 'abstract',
            'og:url': 'canonical_url'
        }
        
        for og_name, field_name in og_fields.items():
            if field_name not in metadata:
                pattern = rf'<meta[^>]*property="{og_name}"[^>]*content="([^"]+)"'
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    metadata[field_name] = match.group(1)
        
        # HTML标签回退 - 最低优先级
        if 'title' not in metadata:
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
            if title_match:
                metadata['title'] = title_match.group(1).strip()
        
        # JSON-LD结构化数据
        json_ld_data = self._extract_json_ld(html_content)
        for field_name, value in json_ld_data.items():
            if field_name not in metadata:
                metadata[field_name] = value
        
        return metadata
    
    def _extract_json_ld(self, html_content: str) -> Dict:
        """提取JSON-LD结构化数据"""
        metadata = {}
        
        try:
            json_ld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
            matches = re.findall(json_ld_pattern, html_content, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                try:
                    import json
                    data = json.loads(match.strip())
                    
                    # 处理单个对象或数组
                    items = data if isinstance(data, list) else [data]
                    
                    for item in items:
                        if isinstance(item, dict):
                            # 提取相关字段
                            if '@type' in item:
                                if 'ScholarlyArticle' in str(item['@type']):
                                    if 'name' in item and 'title' not in metadata:
                                        metadata['title'] = item['name']
                                    if 'author' in item and 'authors' not in metadata:
                                        authors = item['author']
                                        if isinstance(authors, list):
                                            author_names = [a.get('name', str(a)) if isinstance(a, dict) else str(a) for a in authors]
                                            metadata['authors'] = author_names
                                        elif isinstance(authors, dict):
                                            metadata['authors'] = [authors.get('name', str(authors))]
                                    
                                    if 'datePublished' in item and 'date' not in metadata:
                                        metadata['date'] = item['datePublished']
                                    
                                    if 'description' in item and 'abstract' not in metadata:
                                        metadata['abstract'] = item['description']
                
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.debug(f"JSON-LD解析失败: {e}")
                    continue
        
        except Exception as e:
            logger.debug(f"JSON-LD提取失败: {e}")
        
        return metadata
    
    def _detect_pdf_attachments(self, page_data: Dict, domain_info: Dict) -> List[Dict]:
        """
        分层PDF检测 - 类似于Zotero的附件检测逻辑
        """
        attachments = []
        html_content = page_data['content']
        final_url = page_data['final_url']
        
        # 1. Citation标签PDF (最高优先级)
        citation_pdf_patterns = [
            r'<meta[^>]*name="citation_pdf_url"[^>]*content="([^"]+)"',
            r'<meta[^>]*name="citation_fulltext_pdf_url"[^>]*content="([^"]+)"'
        ]
        
        for pattern in citation_pdf_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                attachments.append({
                    'url': self._resolve_url(match.group(1), final_url),
                    'type': 'citation_pdf',
                    'source': 'citation_meta',
                    'priority': 1
                })
        
        # 2. 网站特定模式
        for pattern in domain_info.get('patterns', []):
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                url = self._resolve_url(match, final_url)
                if url not in [att['url'] for att in attachments]:  # 避免重复
                    attachments.append({
                        'url': url,
                        'type': 'site_specific', 
                        'source': domain_info['source'],
                        'priority': 2
                    })
        
        # 3. 特殊网站处理
        # OSF特殊处理
        if 'osf.io/preprints' in final_url:
            osf_pdf = self._extract_osf_pdf(final_url)
            if osf_pdf:
                attachments.append({
                    'url': osf_pdf,
                    'type': 'osf_download',
                    'source': 'osf',
                    'priority': 1
                })
        
        # ChemRxiv特殊处理
        elif 'chemrxiv.org' in final_url:
            chemrxiv_pdf = self._extract_chemrxiv_pdf(final_url)
            if chemrxiv_pdf:
                attachments.append({
                    'url': chemrxiv_pdf,
                    'type': 'chemrxiv_api',
                    'source': 'chemrxiv',
                    'priority': 1
                })
        
        # bioRxiv/medRxiv离线构造 (当无法访问页面时)
        elif any(domain in final_url.lower() for domain in ['biorxiv.org', 'medrxiv.org']):
            offline_pdf = self._extract_biorxiv_medrxiv_pdf(final_url)
            if offline_pdf:
                attachments.append({
                    'url': offline_pdf,
                    'type': 'offline_construction',
                    'source': domain_info['source'],
                    'priority': 3  # 较低优先级，因为是离线构造
                })
        
        # 4. 通用PDF链接搜索 (最低优先级)
        generic_patterns = [
            r'href="([^"]*\.pdf[^"]*)"[^>]*>(?:[^<]*(?:PDF|Download|Full Text|下载)[^<]*)</a>',
            r'href="([^"]*download[^"]*)"[^>]*>(?:[^<]*(?:PDF|pdf)[^<]*)</a>',
            r'href="([^"]*fulltext[^"]*\.pdf[^"]*)"',
            r'href="([^"]*manuscript[^"]*\.pdf[^"]*)"',
            r'href="([^"]*\.pdf[^"]*)"'
        ]
        
        for pattern in generic_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                url = self._resolve_url(match, final_url)
                # 避免重复和明显的非主文档PDF
                if (url not in [att['url'] for att in attachments] and 
                    not any(exclude in url.lower() for exclude in ['supplement', 'supporting', 'appendix'])):
                    attachments.append({
                        'url': url,
                        'type': 'generic_pdf',
                        'source': 'html_parsing',
                        'priority': 9
                    })
        
        # 去重和清理
        unique_attachments = []
        seen_urls = set()
        
        for att in attachments:
            if att['url'] not in seen_urls and att['url'].startswith('http'):
                seen_urls.add(att['url'])
                unique_attachments.append(att)
        
        logger.info(f"🔍 找到 {len(unique_attachments)} 个PDF候选")
        return unique_attachments
    
    def _extract_osf_pdf(self, url: str) -> Optional[str]:
        """提取OSF的PDF下载链接"""
        # OSF URL格式: https://osf.io/preprints/psyarxiv/abc12/
        match = re.search(r'osf\.io/preprints/[^/]+/([a-z0-9]+)', url)
        if match:
            preprint_id = match.group(1)
            return f"https://osf.io/{preprint_id}/download"
        return None
    
    def _extract_chemrxiv_pdf(self, url: str) -> Optional[str]:
        """提取ChemRxiv的PDF下载链接"""
        # ChemRxiv URL格式: https://chemrxiv.org/engage/chemrxiv/article-details/abc123
        match = re.search(r'article-details/([a-f0-9]{24,})', url)
        if match:
            article_id = match.group(1)
            return f"https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/{article_id}/original/manuscript.pdf"
        return None
    
    def _extract_biorxiv_medrxiv_pdf(self, url: str) -> Optional[str]:
        """提取bioRxiv/medRxiv的离线PDF链接"""
        doi_match = re.search(r'10\.1101/([0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+)', url)
        if doi_match:
            doi_id = doi_match.group(1)
            if 'biorxiv.org' in url.lower():
                return f"https://www.biorxiv.org/content/10.1101/{doi_id}.full.pdf"
            elif 'medrxiv.org' in url.lower():
                return f"https://www.medrxiv.org/content/10.1101/{doi_id}.full.pdf"
        return None
    
    def _select_primary_pdf(self, attachments: List[Dict]) -> Optional[Dict]:
        """
        选择主要PDF - 类似于Zotero的主要附件逻辑
        """
        if not attachments:
            return None
        
        # 按优先级和类型排序
        def attachment_score(att):
            score = 0
            
            # 基础优先级 (越小优先级越高)
            score += (10 - att['priority']) * 100
            
            # 类型奖励
            type_scores = {
                'citation_pdf': 50,
                'osf_download': 45,  
                'chemrxiv_api': 45,
                'site_specific': 35,
                'offline_construction': 25,
                'generic_pdf': 10
            }
            score += type_scores.get(att['type'], 0)
            
            # URL质量奖励
            url_lower = att['url'].lower()
            if 'full.pdf' in url_lower:
                score += 25
            if 'manuscript' in url_lower:
                score += 20
            if 'download' in url_lower:
                score += 15
            if 'main' in url_lower:
                score += 10
            
            # URL质量惩罚
            if 'supplement' in url_lower:
                score -= 30
            if 'supporting' in url_lower:
                score -= 25
            if 'appendix' in url_lower:
                score -= 20
            if 'si.' in url_lower:  # Supporting Information
                score -= 15
            
            return score
        
        # 选择得分最高的
        best_attachment = max(attachments, key=attachment_score)
        logger.info(f"🎯 选择主PDF: {best_attachment['url'][:60]}... (类型: {best_attachment['type']})")
        
        return best_attachment
    
    def _post_process_by_site(self, metadata: Dict, domain_info: Dict) -> Dict:
        """针对特定网站的后处理"""
        source = domain_info['source']
        
        # arXiv特殊处理
        if source == 'arXiv':
            metadata = self._enhance_arxiv_metadata(metadata)
        
        # 预印本通用处理
        if metadata.get('itemType') == 'preprint':
            metadata = self._enhance_preprint_metadata(metadata)
        
        return metadata
    
    def _enhance_arxiv_metadata(self, metadata: Dict) -> Dict:
        """增强arXiv元数据"""
        url = metadata.get('url', '')
        
        # 提取arXiv ID
        arxiv_match = re.search(r'arxiv\.org/(?:abs/|pdf/)?([0-9]{4}\.[0-9]{4,5})', url)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
            metadata['archiveID'] = arxiv_id
            metadata['repository'] = 'arXiv'
            metadata['libraryCatalog'] = 'arXiv.org'
            
            # 构造规范URL和PDF URL
            metadata['url'] = f"https://arxiv.org/abs/{arxiv_id}"
            if not metadata.get('pdf_url'):
                metadata['pdf_url'] = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        
        return metadata
    
    def _enhance_preprint_metadata(self, metadata: Dict) -> Dict:
        """增强预印本元数据"""
        # 设置访问日期
        if not metadata.get('accessDate'):
            import datetime
            metadata['accessDate'] = datetime.date.today().isoformat()
        
        # 预印本特有的额外字段
        if not metadata.get('extra'):
            extra_parts = []
            if metadata.get('repository'):
                extra_parts.append(f"type: article")
            if extra_parts:
                metadata['extra'] = '\n'.join(extra_parts)
        
        return metadata
    
    def _resolve_url(self, url: str, base_url: str) -> str:
        """解析相对URL为绝对URL"""
        if url.startswith('http'):
            return url
        return urljoin(base_url, url)

    def _is_anti_crawler_site(self, url: str) -> bool:
        """检测是否为反爬虫网站"""
        return any(domain in url.lower() for domain in self.anti_crawler_sites)

    def _handle_403_response(self, url: str) -> Optional[Dict]:
        """处理403响应的通用策略"""
        logger.warning(f"🛡️ 检测到反爬虫机制: {url}")
        
        # 对于已知的反爬虫网站，强制使用浏览器模式
        if self._is_anti_crawler_site(url):
            logger.info(f"🌐 切换到浏览器模式处理反爬虫网站")
            
            # 动态导入浏览器提取器（避免循环导入）
            try:
                from .browser_extractor import BrowserExtractor
                browser_extractor = BrowserExtractor()
                result = browser_extractor.extract_paper_info(url)
                if result and not result.get('error'):
                    logger.info(f"✅ 浏览器模式成功绕过反爬虫限制")
                    return result
                else:
                    logger.warning(f"⚠️ 浏览器模式也无法处理: {result.get('error', '未知错误')}")
            except Exception as e:
                logger.error(f"❌ 浏览器模式异常: {e}")
        
        # 尝试离线PDF构造（作为备选方案）
        fallback_pdf = self._construct_offline_pdf_url(url)
        if fallback_pdf:
            return {
                'title': f'Paper from {self._extract_domain(url)}',
                'pdf_url': fallback_pdf,
                'url': url,
                'itemType': 'preprint',
                'source': self._extract_domain(url),
                'note': 'PDF链接通过离线构造获得，可能需要验证有效性',
                'fallback_mode': True
            }
        
        return {
            'error': f'无法访问页面(403)，且无有效的回退策略: {url}',
            'status_code': 403
        }

    def _construct_offline_pdf_url(self, url: str) -> Optional[str]:
        """为反爬虫网站构造离线PDF URL"""
        
        if 'biorxiv.org' in url.lower() or 'medrxiv.org' in url.lower():
            # bioRxiv/medRxiv DOI提取和PDF构造
            doi_match = re.search(r'10\.1101/([0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+)', url)
            if doi_match:
                doi_id = doi_match.group(1)
                
                if 'biorxiv.org' in url.lower():
                    return f"https://www.biorxiv.org/content/10.1101/{doi_id}.full.pdf"
                else:
                    return f"https://www.medrxiv.org/content/10.1101/{doi_id}.full.pdf"
        
        elif 'chemrxiv.org' in url.lower():
            # ChemRxiv文章ID提取
            article_match = re.search(r'article-details/([a-f0-9]{24,})', url)
            if article_match:
                article_id = article_match.group(1)
                return f"https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/{article_id}/original/manuscript.pdf"
        
        elif 'osf.io/preprints' in url.lower():
            # OSF preprints (PsyArXiv, SocArXiv等)
            preprint_match = re.search(r'osf\.io/preprints/[^/]+/([a-z0-9]+)', url)
            if preprint_match:
                preprint_id = preprint_match.group(1)
                return f"https://osf.io/{preprint_id}/download"
        
        return None

    def _extract_domain(self, url: str) -> str:
        """提取URL的域名"""
        from urllib.parse import urlparse
        return urlparse(url).netloc
