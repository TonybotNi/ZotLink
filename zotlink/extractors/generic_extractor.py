#!/usr/bin/env python3
"""
🔗 通用开源学术论文提取器

基于标准元数据标签的通用提取策略，支持大部分开源学术网站
"""

import re
import json
import requests
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin
from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class GenericOpenAccessExtractor(BaseExtractor):
    """通用开源学术论文提取器"""
    
    # 开源网站域名模式识别
    OPEN_ACCESS_PATTERNS = {
        # 🔧 修复域名匹配：使用更精确的模式，避免误匹配
        r'(?<!soc)(?<!med)(?<!bio)arxiv\.org': {'type': 'preprint', 'source': 'arXiv', 'priority': 0},  # 已有专用，排除其他rxiv
        r'medrxiv\.org': {'type': 'preprint', 'source': 'medRxiv', 'priority': 1},
        r'biorxiv\.org': {'type': 'preprint', 'source': 'bioRxiv', 'priority': 1},
        r'chemrxiv\.org': {'type': 'preprint', 'source': 'ChemRxiv', 'priority': 1},
        r'psyarxiv\.com': {'type': 'preprint', 'source': 'PsyArXiv', 'priority': 1},
        r'socarxiv\.org': {'type': 'preprint', 'source': 'SocArXiv', 'priority': 1},
        r'osf\.io/preprints/psyarxiv': {'type': 'preprint', 'source': 'PsyArXiv', 'priority': 1},  # 🔧 修复：OSF格式的PsyArXiv
        r'osf\.io/preprints/socarxiv': {'type': 'preprint', 'source': 'SocArXiv', 'priority': 1},  # 🔧 修复：OSF格式的SocArXiv
        r'openaccess\.thecvf\.com': {'type': 'conferencePaper', 'source': 'CVF', 'priority': 0},  # 已有专用
        r'proceedings\.mlr\.press': {'type': 'conferencePaper', 'source': 'MLR Press', 'priority': 1},
        r'openreview\.net': {'type': 'conferencePaper', 'source': 'OpenReview', 'priority': 1},
        r'plos\.org|plosone\.org': {'type': 'journalArticle', 'source': 'PLOS', 'priority': 1},
        r'ncbi\.nlm\.nih\.gov/pmc': {'type': 'journalArticle', 'source': 'PMC', 'priority': 1},
        r'frontiersin\.org': {'type': 'journalArticle', 'source': 'Frontiers', 'priority': 1},
        r'mdpi\.com': {'type': 'journalArticle', 'source': 'MDPI', 'priority': 1},
        r'hindawi\.com': {'type': 'journalArticle', 'source': 'Hindawi', 'priority': 1},
        r'nature\.com': {'type': 'journalArticle', 'source': 'Nature', 'priority': 0},  # 已有专用
        # 机构库模式
        r'dspace\.|eprints\.|repository\.|digital\.': {'type': 'journalArticle', 'source': 'Repository', 'priority': 2},
    }
    
    # Citation标签映射
    CITATION_FIELDS = {
        'citation_title': 'title',
        'citation_author': 'authors',
        'citation_journal_title': 'publicationTitle',
        'citation_conference_title': 'publicationTitle',
        'citation_publisher': 'publicationTitle',  # 有些网站用这个字段
        'citation_publication_date': 'date',
        'citation_date': 'date',
        'citation_online_date': 'date',  # 在线发布日期
        'citation_doi': 'DOI',
        'citation_pmid': 'pmid',
        'citation_pmcid': 'pmcid',
        'citation_pdf_url': 'pdf_url',
        'citation_fulltext_pdf_url': 'pdf_url',  # 🔧 新增：另一种PDF标签
        'citation_fulltext_html_url': 'html_url',
        'citation_abstract': 'abstract',
        'citation_keywords': 'tags',
        'citation_volume': 'volume',
        'citation_issue': 'issue',
        'citation_firstpage': 'pages_start',
        'citation_lastpage': 'pages_end',
        # 预印本特有字段
        'citation_preprint_server': 'repository',
        'citation_archive_id': 'archiveID',
        'citation_preprint_doi': 'DOI',
    }
    
    # Dublin Core标签映射
    DUBLIN_CORE_FIELDS = {
        'DC.title': 'title',
        'DC.creator': 'authors',
        'DC.date': 'date',
        'DC.publisher': 'publisher',
        'DC.description': 'abstract',
        'DC.subject': 'tags',
        'DC.identifier': 'identifier',
    }
    
    def __init__(self, session: requests.Session = None):
        """初始化通用提取器"""
        super().__init__(session)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def can_handle(self, url: str) -> bool:
        """检查是否可以处理此URL"""
        domain_info = self._identify_domain(url)
        # priority > 0 表示可以用通用提取器处理
        return domain_info['priority'] > 0
    
    def requires_authentication(self) -> bool:
        """大多数开源网站不需要认证"""
        return False
    
    def get_database_name(self) -> str:
        """获取数据库名称"""
        return "Generic"
    
    def extract_metadata(self, url: str) -> Dict:
        """通用元数据提取"""
        try:
            # 获取网页内容
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return {'error': f'无法访问页面: {response.status_code}', 'url': url}
            
            html_content = response.text
            
            # 第一层：标准元数据标签提取
            metadata = self._extract_citation_tags(html_content)
            
            # 第二层：结构化数据提取 (JSON-LD, RDFa)
            if not self._is_metadata_sufficient(metadata):
                structured_data = self._extract_structured_data(html_content)
                metadata.update(structured_data)
            
            # 第三层：启发式HTML解析
            if not self._is_metadata_sufficient(metadata):
                heuristic_data = self._extract_heuristic(html_content)
                metadata.update(heuristic_data)
            
            # 第四层：URL模式识别和补充
            domain_info = self._identify_domain(url)
            metadata.update({
                'extractor': f"Generic-{domain_info['source']}",
                'itemType': domain_info['type'],
                'source': domain_info['source'],
                'url': url
            })
            
            # 🆕 增强：从URL提取额外信息
            metadata = self._extract_from_url_patterns(metadata, url)
            
            # 🔧 改进：如果还没有PDF链接，尝试启发式搜索
            if not metadata.get('pdf_url'):
                metadata = self._search_pdf_links_in_html(html_content, url, metadata)
            
            # 数据清理和标准化
            metadata = self._clean_and_standardize(metadata)
            
            # 🆕 增强：补充预印本特有字段
            metadata = self._enhance_preprint_fields(metadata, url)
            
            logger.info(f"✅ 通用提取器成功处理: {metadata.get('title', 'Unknown')[:50]}...")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ 通用元数据提取失败: {e}")
            return {
                'error': f'通用元数据提取失败: {str(e)}',
                'url': url
            }
    
    def _identify_domain(self, url: str) -> Dict:
        """识别域名类型"""
        for pattern, info in self.OPEN_ACCESS_PATTERNS.items():
            if re.search(pattern, url, re.IGNORECASE):
                return info
        
        # 默认处理
        return {'type': 'journalArticle', 'source': 'Unknown', 'priority': 1}
    
    def _extract_citation_tags(self, html_content: str) -> Dict:
        """提取Citation元数据标签"""
        metadata = {}
        authors = []
        
        for meta_name, field_name in self.CITATION_FIELDS.items():
            if meta_name in ['citation_author']:
                # 处理多作者
                matches = re.findall(f'<meta name="{meta_name}" content="([^"]+)"', html_content, re.IGNORECASE)
                if matches:
                    authors.extend(matches)
            else:
                # 处理单值字段
                match = re.search(f'<meta name="{meta_name}" content="([^"]+)"', html_content, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if field_name == 'date':
                        value = self._normalize_date(value)
                    metadata[field_name] = value
        
        # 处理作者列表
        if authors:
            formatted_authors = []
            for author in authors:
                author = author.strip()
                if ',' in author:
                    formatted_authors.append(author)  # "Last, First"格式
                else:
                    # "First Last" → "Last, First"
                    parts = author.split()
                    if len(parts) >= 2:
                        last_name = parts[-1]
                        first_names = ' '.join(parts[:-1])
                        formatted_authors.append(f"{last_name}, {first_names}")
                    else:
                        formatted_authors.append(author)
            
            metadata['authors'] = '; '.join(formatted_authors)
        
        return metadata
    
    def _extract_dublin_core(self, html_content: str) -> Dict:
        """提取Dublin Core元数据"""
        metadata = {}
        
        for meta_name, field_name in self.DUBLIN_CORE_FIELDS.items():
            pattern = f'<meta name="{meta_name}" content="([^"]+)"'
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                metadata[field_name] = match.group(1).strip()
        
        return metadata
    
    def _extract_structured_data(self, html_content: str) -> Dict:
        """提取结构化数据 (JSON-LD, Schema.org)"""
        metadata = {}
        
        # 提取JSON-LD
        jsonld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
        jsonld_matches = re.findall(jsonld_pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for jsonld_content in jsonld_matches:
            try:
                data = json.loads(jsonld_content.strip())
                
                # 处理单个对象或数组
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                # 映射Schema.org字段
                if data.get('@type') in ['ScholarlyArticle', 'Article', 'CreativeWork']:
                    if data.get('headline'):
                        metadata['title'] = data['headline']
                    elif data.get('name'):
                        metadata['title'] = data['name']
                    
                    if data.get('author'):
                        authors = data['author']
                        if isinstance(authors, list):
                            author_names = [auth.get('name', '') for auth in authors if auth.get('name')]
                        else:
                            author_names = [authors.get('name', '')] if authors.get('name') else []
                        
                        if author_names:
                            metadata['authors'] = '; '.join(author_names)
                    
                    if data.get('datePublished'):
                        metadata['date'] = self._normalize_date(data['datePublished'])
                    
                    if data.get('description'):
                        metadata['abstract'] = data['description']
                    
                    if data.get('publisher', {}).get('name'):
                        metadata['publisher'] = data['publisher']['name']
                
            except json.JSONDecodeError:
                continue
        
        return metadata
    
    def _extract_heuristic(self, html_content: str) -> Dict:
        """启发式HTML解析"""
        metadata = {}
        
        # 标题启发式匹配
        if not metadata.get('title'):
            title_patterns = [
                r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>',
                r'<div[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</div>',
                r'<span[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</span>',
                r'<title>([^<]+)</title>',
                r'<h1[^>]*>([^<]+)</h1>',  # 简单h1标签
            ]
            
            for pattern in title_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if match:
                    title = match.group(1).strip()
                    title = re.sub(r'<[^>]+>', '', title)  # 清理HTML标签
                    title = re.sub(r'\s+', ' ', title).strip()
                    if len(title) > 10 and len(title) < 300:  # 合理的标题长度
                        metadata['title'] = title
                        break
        
        # 作者启发式匹配
        if not metadata.get('authors'):
            author_patterns = [
                r'<div[^>]*class="[^"]*author[^"]*"[^>]*>([^<]+)</div>',
                r'<span[^>]*class="[^"]*author[^"]*"[^>]*>([^<]+)</span>',
                r'<p[^>]*class="[^"]*author[^"]*"[^>]*>([^<]+)</p>',
            ]
            
            for pattern in author_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    authors = [match.strip() for match in matches if match.strip()]
                    if authors:
                        metadata['authors'] = '; '.join(authors[:10])  # 限制作者数量
                        break
        
        # 摘要启发式匹配
        if not metadata.get('abstract'):
            abstract_patterns = [
                r'<div[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</div>',
                r'<p[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</p>',
                r'<section[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</section>',
            ]
            
            for pattern in abstract_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                if match:
                    abstract = match.group(1).strip()
                    abstract = re.sub(r'<[^>]+>', '', abstract)  # 清理HTML标签
                    abstract = re.sub(r'\s+', ' ', abstract).strip()
                    if len(abstract) > 50:  # 最小摘要长度
                        metadata['abstract'] = abstract
                        break
        
        return metadata
    
    def _is_metadata_sufficient(self, metadata: Dict) -> bool:
        """判断元数据是否足够完整"""
        required_fields = ['title']
        optional_fields = ['authors', 'abstract', 'date']
        
        # 必须有标题
        if not metadata.get('title'):
            return False
        
        # 至少有一个可选字段
        has_optional = any(metadata.get(field) for field in optional_fields)
        return has_optional
    
    def _normalize_date(self, date_str: str) -> str:
        """标准化日期格式"""
        if not date_str:
            return ""
        
        # 常见日期格式模式
        patterns = [
            (r'(\d{4})-(\d{2})-(\d{2})', r'\1-\2-\3'),  # YYYY-MM-DD
            (r'(\d{4})/(\d{2})/(\d{2})', r'\1-\2-\3'),  # YYYY/MM/DD
            (r'(\d{2})/(\d{2})/(\d{4})', r'\3-\1-\2'),  # MM/DD/YYYY
            (r'(\d{1,2})\s+(\w+)\s+(\d{4})', self._convert_month_name),  # DD Month YYYY
        ]
        
        for pattern, replacement in patterns:
            if callable(replacement):
                match = re.search(pattern, date_str)
                if match:
                    return replacement(match)
            else:
                if re.search(pattern, date_str):
                    return re.sub(pattern, replacement, date_str)
        
        return date_str  # 返回原格式
    
    def _convert_month_name(self, match) -> str:
        """转换月份名称为数字"""
        day, month_name, year = match.groups()
        
        months = {
            'january': '01', 'jan': '01',
            'february': '02', 'feb': '02',
            'march': '03', 'mar': '03',
            'april': '04', 'apr': '04',
            'may': '05',
            'june': '06', 'jun': '06',
            'july': '07', 'jul': '07',
            'august': '08', 'aug': '08',
            'september': '09', 'sep': '09',
            'october': '10', 'oct': '10',
            'november': '11', 'nov': '11',
            'december': '12', 'dec': '12'
        }
        
        month_num = months.get(month_name.lower(), '01')
        return f"{year}-{month_num}-{day.zfill(2)}"
    
    def _extract_from_url_patterns(self, metadata: Dict, url: str) -> Dict:
        """从URL模式中提取额外信息 - 🔧 修复：仅提取DOI，不构造可能无效的PDF链接"""
        
        # medRxiv URL模式: https://www.medrxiv.org/content/10.1101/2025.09.01.25334224v1
        if 'medrxiv.org' in url.lower():
            # DOI提取
            if not metadata.get('DOI'):
                doi_match = re.search(r'10\.1101/([0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:\.[0-9]+)?)', url)
                if doi_match:
                    full_doi = f"10.1101/{doi_match.group(1)}"
                    metadata['DOI'] = full_doi
                    
            # 从DOI提取日期
            if metadata.get('DOI'):
                date_match = re.search(r'10\.1101/([0-9]{4})\.([0-9]{2})\.([0-9]{2})', metadata['DOI'])
                if date_match:
                    year, month, day = date_match.groups()
                    metadata['date'] = f"{year}-{month}-{day}"
                    
        # bioRxiv URL模式: https://www.biorxiv.org/content/10.1101/2024.09.16.613241v1
        elif 'biorxiv.org' in url.lower():
            # DOI提取
            if not metadata.get('DOI'):
                doi_match = re.search(r'10\.1101/([0-9]{4}\.[0-9]{2}\.[0-9]{2}(?:\.[0-9]+)?)', url)
                if doi_match:
                    metadata['DOI'] = f"10.1101/{doi_match.group(1)}"
                    
            # 从DOI提取日期
            if metadata.get('DOI'):
                date_match = re.search(r'10\.1101/([0-9]{4})\.([0-9]{2})\.([0-9]{2})', metadata['DOI'])
                if date_match:
                    year, month, day = date_match.groups()
                    metadata['date'] = f"{year}-{month}-{day}"
                    
        # PLOS DOI提取
        elif 'plos.org' in url.lower():
            if not metadata.get('DOI'):
                doi_match = re.search(r'10\.1371/journal\.[^&\s]+', url)
                if doi_match:
                    metadata['DOI'] = doi_match.group(0)
                    
        # PMC ID提取
        elif 'ncbi.nlm.nih.gov/pmc' in url.lower():
            pmc_match = re.search(r'PMC(\d+)', url)
            if pmc_match:
                metadata['pmcid'] = f"PMC{pmc_match.group(1)}"
                
        # 🔧 注意：不再构造可能无效的PDF链接
        # PDF链接应该优先从HTML的citation标签中提取
        # 只有在HTML解析成功时才会有可靠的PDF链接
                
        return metadata
    
    def _enhance_preprint_fields(self, metadata: Dict, url: str) -> Dict:
        """增强预印本特有字段"""
        
        # 只处理预印本类型
        if metadata.get('itemType') != 'preprint':
            return metadata
            
        source = metadata.get('source', '').lower()
        
        # 为预印本设置Repository字段
        if not metadata.get('repository'):
            if 'medrxiv' in source:
                metadata['repository'] = 'medRxiv'
            elif 'biorxiv' in source:
                metadata['repository'] = 'bioRxiv'
            elif 'chemrxiv' in source:
                metadata['repository'] = 'ChemRxiv'
            elif 'psyarxiv' in source:
                metadata['repository'] = 'PsyArXiv'
            elif 'socarxiv' in source:
                metadata['repository'] = 'SocArXiv'
            else:
                metadata['repository'] = metadata.get('source', 'Preprint Server')
        
        # 设置Archive ID（基于DOI）
        if metadata.get('DOI') and not metadata.get('archiveID'):
            # 对于bioRxiv/medRxiv的DOI格式
            if metadata['DOI'].startswith('10.1101/'):
                metadata['archiveID'] = metadata['DOI']
            else:
                metadata['archiveID'] = metadata['DOI']
                
        # 🆕 对于预印本，强制使用服务器名称作为Publication Title
        # 这样用户在Zotero中看到的是"medRxiv"而不是"Cold Spring Harbor Laboratory Press"
        metadata['publicationTitle'] = metadata.get('repository', metadata.get('source', 'Preprint'))
            
        # 设置Library Catalog
        if not metadata.get('libraryCatalog'):
            if 'medrxiv' in source:
                metadata['libraryCatalog'] = 'medRxiv.org'
            elif 'biorxiv' in source:
                metadata['libraryCatalog'] = 'bioRxiv.org'
            else:
                domain_match = re.search(r'https?://([^/]+)', url)
                if domain_match:
                    metadata['libraryCatalog'] = domain_match.group(1)
        
        # 设置访问日期
        if not metadata.get('accessDate'):
            import time
            metadata['accessDate'] = time.strftime('%Y-%m-%d')
            
        return metadata
    
    def _search_pdf_links_in_html(self, html_content: str, url: str, metadata: Dict) -> Dict:
        """在HTML中启发式搜索PDF链接"""
        
        try:
            # 🔧 特定网站的PDF链接构造逻辑
            if 'chemrxiv.org' in url.lower():
                # ChemRxiv特殊处理：基于文章ID构造PDF链接
                article_match = re.search(r'article-details/([a-f0-9]{24,})', url)
                if article_match:
                    article_id = article_match.group(1)
                    # 使用发现的有效PDF URL格式
                    chemrxiv_pdf_url = f"https://chemrxiv.org/engage/api-gateway/chemrxiv/assets/orp/resource/item/{article_id}/original/manuscript.pdf"
                    metadata['pdf_url'] = chemrxiv_pdf_url
                    logger.info(f"🧪 ChemRxiv构造PDF链接: {chemrxiv_pdf_url}")
                    return metadata
            
            elif 'osf.io/preprints' in url.lower():
                # OSF preprints (PsyArXiv, SocArXiv等)
                # URL格式: https://osf.io/preprints/socarxiv/rhqmu_v1
                preprint_match = re.search(r'osf\.io/preprints/[^/]+/([a-z0-9]+)', url)
                if preprint_match:
                    preprint_id = preprint_match.group(1)
                    osf_pdf_url = f"https://osf.io/{preprint_id}/download"
                    metadata['pdf_url'] = osf_pdf_url
                    logger.info(f"🔗 OSF构造PDF链接: {osf_pdf_url}")
                    return metadata
            
            elif 'biorxiv.org' in url.lower() or 'medrxiv.org' in url.lower():
                # bioRxiv/medRxiv离线PDF构造 (当403/404时使用)
                # URL格式: https://www.biorxiv.org/content/10.1101/2025.02.19.639094v1
                doi_match = re.search(r'10\.1101/([0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+)', url)
                if doi_match:
                    doi_id = doi_match.group(1)
                    year, month, day = doi_id.split('.')[:3]
                    
                    # 尝试多种可能的PDF URL格式
                    if 'biorxiv.org' in url.lower():
                        possible_pdf_urls = [
                            f"https://www.biorxiv.org/content/10.1101/{doi_id}.full.pdf",
                            f"https://www.biorxiv.org/content/biorxiv/early/{year}/{month.zfill(2)}/{day.zfill(2)}/{doi_id}/{doi_id}.full.pdf",
                            f"https://www.biorxiv.org/content/early/{year}/{month.zfill(2)}/{day.zfill(2)}/{doi_id}.full.pdf"
                        ]
                        service = "bioRxiv"
                    else:
                        possible_pdf_urls = [
                            f"https://www.medrxiv.org/content/10.1101/{doi_id}.full.pdf",
                            f"https://www.medrxiv.org/content/medrxiv/early/{year}/{month.zfill(2)}/{day.zfill(2)}/{doi_id}/{doi_id}.full.pdf",
                            f"https://www.medrxiv.org/content/early/{year}/{month.zfill(2)}/{day.zfill(2)}/{doi_id}.full.pdf"
                        ]
                        service = "medRxiv"
                    
                    # 使用最可能的格式 (根据经验，第一个格式最常见)
                    metadata['pdf_url'] = possible_pdf_urls[0]
                    logger.info(f"🔧 {service}离线构造PDF链接: {possible_pdf_urls[0]}")
                    return metadata
            
            # 通用HTML PDF链接搜索模式
            pdf_patterns = [
                # 直接链接到PDF文件
                r'href="([^"]*\.pdf[^"]*)"[^>]*>(?:[^<]*(?:download|pdf|full\s*text)[^<]*)</a>',
                r'href="([^"]*\.pdf[^"]*)"[^>]*>[^<]*(?:PDF|pdf)[^<]*</a>',
                r'href="([^"]*\.pdf[^"]*)"',
                
                # medRxiv/bioRxiv特有的PDF链接
                r'href="([^"]*content[^"]*\.full\.pdf[^"]*)"',
                r'href="([^"]*early[^"]*\.full\.pdf[^"]*)"',
                
                # 下载链接
                r'href="([^"]*download[^"]*)"[^>]*>(?:[^<]*(?:PDF|pdf)[^<]*)</a>',
                r'href="([^"]*ndownloader[^"]*)"',  # ChemRxiv等
                
                # OSF类型的下载链接
                r'href="(https://osf\.io/[a-z0-9]+/download)"',
                
                # 其他可能的PDF链接格式
                r'href="([^"]*fulltext[^"]*\.pdf[^"]*)"',
                r'href="([^"]*manuscript[^"]*\.pdf[^"]*)"',
                
                # 🔧 新增：更多常见的PDF链接模式
                r'href="([^"]*)"[^>]*>(?:[^<]*(?:Full Text|全文|PDF版本)[^<]*)</a>',
                r'data-download-url="([^"]+)"',  # 数据属性中的下载链接
                r'downloadUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',  # JavaScript变量
            ]
            
            found_pdfs = []
            
            for pattern in pdf_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    if match not in found_pdfs:
                        found_pdfs.append(match)
            
            if found_pdfs:
                # 选择最可能是主文档PDF的链接
                main_pdf = self._select_main_pdf_link(found_pdfs, url)
                if main_pdf:
                    # 确保是绝对URL
                    if not main_pdf.startswith('http'):
                        from urllib.parse import urljoin
                        main_pdf = urljoin(url, main_pdf)
                    
                    metadata['pdf_url'] = main_pdf
                    logger.info(f"🔍 启发式搜索找到PDF链接: {main_pdf[:60]}...")
            
        except Exception as e:
            logger.warning(f"⚠️ PDF链接启发式搜索失败: {e}")
        
        return metadata
    
    def _select_main_pdf_link(self, pdf_links: list, base_url: str) -> str:
        """从多个PDF链接中选择最可能是主文档的链接"""
        
        if not pdf_links:
            return None
        
        if len(pdf_links) == 1:
            return pdf_links[0]
        
        # 排序优先级规则
        def pdf_priority(pdf_url):
            score = 0
            pdf_lower = pdf_url.lower()
            
            # 优先选择包含这些关键词的链接
            if 'full.pdf' in pdf_lower:
                score += 10
            if 'manuscript' in pdf_lower:
                score += 8  
            if 'main' in pdf_lower:
                score += 7
            if 'download' in pdf_lower and 'osf.io' in pdf_lower:
                score += 6  # OSF下载链接
            if 'ndownloader' in pdf_lower:
                score += 5  # ChemRxiv下载
            
            # 降低优先级的内容
            if 'supplement' in pdf_lower:
                score -= 5
            if 'supporting' in pdf_lower:
                score -= 5  
            if 'appendix' in pdf_lower:
                score -= 3
            
            # 绝对URL优先
            if pdf_url.startswith('http'):
                score += 2
                
            return score
        
        # 按优先级排序并返回最高分的
        sorted_pdfs = sorted(pdf_links, key=pdf_priority, reverse=True)
        return sorted_pdfs[0]
    
    def _clean_and_standardize(self, metadata: Dict) -> Dict:
        """清理和标准化元数据"""
        # 清理标题
        if metadata.get('title'):
            title = metadata['title']
            # 移除多余空白
            title = re.sub(r'\s+', ' ', title).strip()
            # 移除常见的无用后缀
            title = re.sub(r'\s*[\|\-]\s*(PLoS|PLOS|medRxiv|bioRxiv|Nature|Science).*$', '', title, re.IGNORECASE)
            metadata['title'] = title
        
        # 清理作者
        if metadata.get('authors'):
            authors = metadata['authors']
            # 移除email地址
            authors = re.sub(r'\s*\([^@]+@[^)]+\)', '', authors)
            # 移除多余空白
            authors = re.sub(r'\s+', ' ', authors).strip()
            metadata['authors'] = authors
        
        # 清理摘要
        if metadata.get('abstract'):
            abstract = metadata['abstract']
            # 限制长度
            if len(abstract) > 2000:
                abstract = abstract[:2000] + '...'
            metadata['abstract'] = abstract
        
        # 确保有PDF链接
        if metadata.get('pdf_url'):
            pdf_url = metadata['pdf_url']
            if not pdf_url.startswith('http'):
                # 相对链接转绝对链接
                if metadata.get('url'):
                    base_url = metadata['url']
                    metadata['pdf_url'] = urljoin(base_url, pdf_url)
        
        # 🆕 确保期刊类和会议论文也有合适的publication title
        if not metadata.get('publicationTitle') and metadata.get('source'):
            source = metadata.get('source')
            item_type = metadata.get('itemType', '')
            
            if item_type == 'journalArticle':
                if 'PLOS' in source:
                    metadata['publicationTitle'] = 'PLOS ONE'
                elif 'Frontiers' in source:
                    metadata['publicationTitle'] = 'Frontiers'
                elif 'MDPI' in source:
                    metadata['publicationTitle'] = 'MDPI Journal'
                elif 'PMC' in source:
                    metadata['publicationTitle'] = 'PubMed Central'
                else:
                    metadata['publicationTitle'] = source
            elif item_type == 'conferencePaper':
                metadata['publicationTitle'] = source
        
        return metadata
    
    def test_access(self, test_url: str = None) -> bool:
        """测试网站访问"""
        if not test_url:
            test_url = "https://www.medrxiv.org/"  # 使用medRxiv作为测试
        
        try:
            response = self.session.get(test_url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def get_supported_item_types(self) -> List[str]:
        """获取支持的条目类型"""
        return ['journalArticle', 'conferencePaper', 'preprint'] 