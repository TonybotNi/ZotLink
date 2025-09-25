#!/usr/bin/env python3
"""
🔗 CVF (Computer Vision Foundation) 论文提取器

处理 openaccess.thecvf.com 网站的论文元数据提取
"""

import re
import requests
import logging
from typing import Dict, List
from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class CVFExtractor(BaseExtractor):
    """CVF论文提取器"""
    
    def __init__(self, session: requests.Session = None):
        """初始化CVF提取器"""
        super().__init__(session)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def can_handle(self, url: str) -> bool:
        """检查是否可以处理此URL"""
        cvf_domains = [
            'openaccess.thecvf.com',
            'thecvf.com'
        ]
        return any(domain in url.lower() for domain in cvf_domains)
    
    def requires_authentication(self) -> bool:
        """CVF是开放获取，不需要认证"""
        return False
    
    def get_database_name(self) -> str:
        """获取数据库名称"""
        return "CVF"
    
    def extract_metadata(self, url: str) -> Dict:
        """从CVF URL提取论文元数据"""
        try:
            # 从URL提取基本信息
            metadata = self._extract_from_url(url)
            
            # 尝试获取对应的HTML页面来提取更多信息
            html_url = self._get_html_url_from_pdf(url)
            if html_url:
                html_metadata = self._extract_from_html_page(html_url)
                # 优先使用HTML页面的信息
                for key, value in html_metadata.items():
                    if value:  # 只有当HTML页面的值不为空时才覆盖
                        metadata[key] = value
            
            # 生成TLDR
            if metadata.get('abstract'):
                metadata['tldr'] = self._generate_tldr(metadata['abstract'])
            
            # 设置CVF特有字段
            metadata.update({
                'extractor': self.get_database_name(),
                'itemType': 'conferencePaper',
                'pdf_url': url if url.endswith('.pdf') else None
            })
            
            return metadata
            
        except Exception as e:
            logger.error(f"❌ CVF元数据提取失败: {e}")
            return {
                'error': f'CVF元数据提取失败: {str(e)}',
                'url': url
            }
    
    def _extract_from_url(self, url: str) -> Dict:
        """从URL路径提取基本信息"""
        metadata = {}
        
        # 从URL路径提取会议信息
        # 例如: /content/ICCV2023/papers/...
        path_match = re.search(r'/content/([A-Z]+)(\d{4})/', url)
        if path_match:
            conference_abbr = path_match.group(1)  # ICCV, CVPR, WACV
            year = path_match.group(2)
            
            # 映射会议缩写到全名
            conference_names = {
                'ICCV': 'International Conference on Computer Vision',
                'CVPR': 'Conference on Computer Vision and Pattern Recognition', 
                'WACV': 'Winter Conference on Applications of Computer Vision'
            }
            
            full_conference = conference_names.get(conference_abbr, conference_abbr)
            conference_full_name = f"{year} IEEE/CVF {full_conference} ({conference_abbr})"
            
            metadata.update({
                'conference': conference_abbr,
                'conferenceName': conference_full_name,
                'proceedingsTitle': conference_full_name,
                'publicationTitle': conference_full_name,
                'date': f"{year}-10-01",  # ICCV通常在10月
                'year': year
            })
        
        # 改进的文件名解析
        # 例如: Fang_Visible-Infrared_Person_Re-Identification_via_Semantic_Alignment_and_Affinity_Inference_ICCV_2023_paper.pdf
        filename_match = re.search(r'/([^/_]+)_(.+)_([A-Z]+)_(\d{4})_paper\.pdf$', url)
        if filename_match:
            first_author_lastname = filename_match.group(1)
            title_part = filename_match.group(2)
            conf_abbr = filename_match.group(3)
            
            # 重构标题：将下划线转换为空格，连字符保留
            title = title_part.replace('_', ' ')
            
            metadata.update({
                'title': title,
                'first_author_lastname': first_author_lastname
            })
        
        # 如果无法从文件名完整解析，尝试更简单的模式
        elif not metadata.get('title'):
            simple_match = re.search(r'/([^/]+)_paper\.pdf$', url)
            if simple_match:
                filename = simple_match.group(1)
                # 尝试分割出作者和标题
                parts = filename.split('_')
                if len(parts) >= 3:
                    first_author_lastname = parts[0]
                    title = ' '.join(parts[1:]).replace('-', ' ')
                    
                    metadata.update({
                        'title': title,
                        'first_author_lastname': first_author_lastname
                    })
        
        return metadata
    
    def _get_html_url_from_pdf(self, pdf_url: str) -> str:
        """从PDF URL获取对应的HTML页面URL"""
        if not pdf_url.endswith('.pdf'):
            return pdf_url
        
        # 转换PDF URL为HTML URL
        # 例如: .../paper.pdf -> .../html/...html
        html_url = pdf_url.replace('.pdf', '.html').replace('/papers/', '/html/')
        
        # 也尝试直接去掉.pdf后缀的版本
        simple_url = pdf_url.replace('_paper.pdf', '')
        
        # 优先尝试HTML版本
        for candidate_url in [html_url, simple_url]:
            try:
                response = self.session.head(candidate_url, timeout=5)
                if response.status_code == 200:
                    logger.info(f"✅ 找到HTML页面: {candidate_url}")
                    return candidate_url
            except:
                continue
        
        logger.warning(f"⚠️ 未找到HTML页面，将尝试直接解析PDF")
        return None
    
    def _extract_from_html_page(self, html_url: str) -> Dict:
        """从HTML页面提取详细元数据"""
        try:
            response = self.session.get(html_url, timeout=10)
            if response.status_code != 200:
                return {}
            
            html_content = response.text
            metadata = {}
            
            # 提取标题 - 优先使用citation元数据，然后使用页面内容
            # 首先尝试从citation元数据提取标题
            citation_title_match = re.search(r'<meta name="citation_title" content="([^"]+)"', html_content, re.IGNORECASE)
            if citation_title_match:
                title = citation_title_match.group(1).strip()
                metadata['title'] = title
                logger.info(f"✅ 从citation元数据提取到标题: {title}")
            else:
                # 如果没有citation元数据，尝试从页面内容提取
                title_patterns = [
                    r'<div id="papertitle">\s*([^<]+(?:\n[^<]*)*?)</div>',
                    r'<div class="ptitle">([^<]+)</div>',
                    r'<div class="papertitle">([^<]+)</div>',
                    r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>',
                    r'<h1[^>]*>([^<]+)</h1>'
                ]
                
                for pattern in title_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                    if match:
                        title = match.group(1).strip()
                        # 清理标题
                        title = re.sub(r'\s+', ' ', title)
                        title = re.sub(r'^\s*[-–]\s*', '', title)  # 移除开头的破折号
                        if title and len(title) > 10:  # 确保是有意义的标题
                            metadata['title'] = title
                            logger.info(f"✅ 从页面内容提取到标题: {title}")
                            break
            
            # 提取作者 - 优先使用citation元数据，然后使用页面内容
            authors = []
            
            # 首先尝试从citation元数据提取作者
            citation_authors = re.findall(r'<meta name="citation_author" content="([^"]+)"', html_content, re.IGNORECASE)
            if citation_authors:
                # citation_author已经是"Last, First"格式
                metadata['authors'] = '; '.join(citation_authors)
                logger.info(f"✅ 从citation元数据提取到作者: {metadata['authors']}")
            else:
                # 如果没有citation元数据，尝试从页面内容提取
                author_patterns = [
                    r'<div id="authors">[^<]*<b><i>([^<]+)</i></b>',
                    r'<div class="pauthors">([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</div>',
                    r'<div class="authors?">([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</div>',
                    r'<span class="author[^"]*">([^<]+)</span>',
                    r'<div class="author[^"]*">([^<]+)</div>',
                    r'<p class="author[^"]*">([^<]+)</p>'
                ]
                
                for pattern in author_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
                    if match:
                        author_block = match.group(1).strip()
                        # 清理HTML标签
                        clean_authors = re.sub(r'<[^>]+>', '', author_block)
                        # 分割多个作者（可能用逗号、分号或其他分隔符）
                        author_list = re.split(r'[,;]|\s+and\s+', clean_authors)
                        
                        formatted_authors = []
                        for author in author_list:
                            author = author.strip()
                            if author and len(author) > 2:
                                # 处理"First Middle Last"格式，转换为"Last, First Middle"
                                parts = author.split()
                                if len(parts) >= 2:
                                    first_names = ' '.join(parts[:-1])
                                    last_name = parts[-1]
                                    formatted_authors.append(f"{last_name}, {first_names}")
                                else:
                                    formatted_authors.append(author)
                        
                        if formatted_authors:
                            metadata['authors'] = '; '.join(formatted_authors)
                            logger.info(f"✅ 从页面内容提取到作者: {metadata['authors']}")
                            break
            
            # 提取摘要 - 使用正确的CVF页面结构
            abstract_patterns = [
                r'<div id="abstract">\s*(.*?)\s*</div>',
                r'<div class="pabstract">([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</div>',
                r'<div class="abstract">([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</div>',
                r'<p class="abstract[^"]*">([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</p>',
                r'<div[^>]*class="[^"]*abstract[^"]*"[^>]*>([^<]+(?:<[^>]*>[^<]*</[^>]*>[^<]*)*)</div>'
            ]
            
            for pattern in abstract_patterns:
                match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
                if match:
                    abstract = match.group(1).strip()
                    # 清理HTML标签和多余空白
                    abstract = re.sub(r'<[^>]+>', '', abstract)
                    abstract = re.sub(r'\s+', ' ', abstract).strip()
                    if len(abstract) > 100:  # 确保是真正的摘要
                        metadata['abstract'] = abstract
                        logger.info(f"✅ 提取到摘要: {abstract[:100]}...")
                        break
            
            # 提取页码范围 - 从citation元数据
            first_page = re.search(r'<meta name="citation_firstpage" content="([^"]+)"', html_content, re.IGNORECASE)
            last_page = re.search(r'<meta name="citation_lastpage" content="([^"]+)"', html_content, re.IGNORECASE)
            if first_page and last_page:
                pages = f"{first_page.group(1)}-{last_page.group(1)}"
                metadata['pages'] = pages
                logger.info(f"✅ 提取到页码: {pages}")
            elif first_page:
                metadata['pages'] = first_page.group(1)
                logger.info(f"✅ 提取到起始页: {first_page.group(1)}")
            
            # 提取发布日期 - 更精确的日期
            pub_date_match = re.search(r'<meta name="citation_publication_date" content="([^"]+)"', html_content, re.IGNORECASE)
            if pub_date_match:
                year = pub_date_match.group(1).strip()
                # 根据会议类型设定更精确的日期，覆盖URL解析的日期
                if metadata.get('conference') == 'ICCV':
                    metadata['date'] = f"{year}-10-01"  # ICCV通常在10月
                elif metadata.get('conference') == 'CVPR':
                    metadata['date'] = f"{year}-06-01"  # CVPR通常在6月
                elif metadata.get('conference') == 'WACV':
                    metadata['date'] = f"{year}-01-01"  # WACV通常在1月
                else:
                    metadata['date'] = f"{year}-01-01"
                logger.info(f"✅ 更新日期: {metadata['date']}")
            
            # 设置出版商信息
            metadata['publisher'] = 'IEEE'
            
            # 设置语言
            metadata['language'] = 'en'
            
            # 提取或设置会议地点（如果HTML中有的话）
            place_patterns = [
                r'<meta name="citation_conference_place" content="([^"]+)"',
                r'<div class="conference-location">([^<]+)</div>',
                r'(\w+,\s*\w+)\s*\d{4}'  # 匹配"City, Country 2023"格式
            ]
            
            for pattern in place_patterns:
                place_match = re.search(pattern, html_content, re.IGNORECASE)
                if place_match:
                    place = place_match.group(1).strip()
                    if place and len(place) > 2:
                        metadata['place'] = place
                        logger.info(f"✅ 提取到会议地点: {place}")
                        break
            
            # 如果没有找到地点，根据会议和年份设置默认地点
            if not metadata.get('place') and metadata.get('conference') and metadata.get('year'):
                conf = metadata['conference']
                year = metadata['year']
                # 一些常见的CVF会议地点（这些是历史数据，实际使用时可以更新）
                default_places = {
                    'ICCV': {
                        '2023': 'Paris, France',
                        '2021': 'Virtual',
                        '2019': 'Seoul, Korea'
                    },
                    'CVPR': {
                        '2023': 'Vancouver, Canada', 
                        '2022': 'New Orleans, USA',
                        '2021': 'Virtual'
                    },
                    'WACV': {
                        '2023': 'Waikoloa, Hawaii',
                        '2022': 'Waikoloa, Hawaii'
                    }
                }
                if conf in default_places and year in default_places[conf]:
                    metadata['place'] = default_places[conf][year]
                    logger.info(f"✅ 设置默认会议地点: {metadata['place']}")
            
            # 查找DOI（虽然CVF的开放获取论文通常没有单独的DOI）
            doi_patterns = [
                r'<meta name="citation_doi" content="([^"]+)"',
                r'<meta name="DC\.identifier" content="doi:([^"]+)"',
                r'doi:\s*([0-9]{2}\.[0-9]{4}/[^\s<>]+)',
                r'DOI:\s*([0-9]{2}\.[0-9]{4}/[^\s<>]+)'
            ]
            
            for pattern in doi_patterns:
                doi_match = re.search(pattern, html_content, re.IGNORECASE)
                if doi_match:
                    doi = doi_match.group(1).strip()
                    if doi.startswith('10.'):
                        metadata['DOI'] = doi
                        metadata['url'] = f'https://doi.org/{doi}'  # DOI URL优先于PDF URL
                        logger.info(f"✅ 提取到DOI: {doi}")
                        break
            
            # 查找ISBN（会议论文集通常有ISBN）
            isbn_patterns = [
                r'<meta name="citation_isbn" content="([^"]+)"',
                r'ISBN[:\s]*([0-9-]{10,17})',
                r'ISBN[:\s]*([0-9]{10,13})'
            ]
            
            for pattern in isbn_patterns:
                isbn_match = re.search(pattern, html_content, re.IGNORECASE)
                if isbn_match:
                    isbn = isbn_match.group(1).strip()
                    # 简单验证ISBN格式
                    isbn_clean = re.sub(r'[^0-9X]', '', isbn.upper())
                    if len(isbn_clean) in [10, 13]:
                        metadata['ISBN'] = isbn
                        logger.info(f"✅ 提取到ISBN: {isbn}")
                        break
            
            # 提取更精确的会议信息 - 优先使用citation元数据
            citation_conference_match = re.search(r'<meta name="citation_conference_title" content="([^"]+)"', html_content, re.IGNORECASE)
            if citation_conference_match:
                conference_title = citation_conference_match.group(1).strip()
                metadata['proceedingsTitle'] = conference_title
                metadata['publicationTitle'] = conference_title
                logger.info(f"✅ 从citation元数据提取到会议标题: {conference_title}")
            else:
                # 备选方案：从页面内容提取
                conference_patterns = [
                    r'<div class="pconf">([^<]+)</div>',
                    r'Proceedings of the ([^<\n]+)',
                    r'(\d{4} IEEE/CVF [^<\n]+Conference[^<\n]*)'
                ]
                
                for pattern in conference_patterns:
                    match = re.search(pattern, html_content, re.IGNORECASE)
                    if match:
                        conference_info = match.group(1).strip()
                        metadata['proceedingsTitle'] = conference_info
                        metadata['publicationTitle'] = conference_info
                        logger.info(f"✅ 从页面内容提取到会议标题: {conference_info}")
                        break
            
            # 设置完整的URL（如果没有DOI的话）
            if not metadata.get('DOI'):
                metadata['url'] = html_url
            
            return metadata
            
        except Exception as e:
            logger.warning(f"⚠️ HTML页面元数据提取失败: {e}")
            return {}
    
    def _generate_tldr(self, abstract: str) -> str:
        """从摘要生成TLDR"""
        if not abstract or len(abstract) < 50:
            return ""
        
        # 提取第一句话或前100个字符作为TLDR
        sentences = re.split(r'[.!?]\s+', abstract)
        if sentences:
            first_sentence = sentences[0].strip()
            if len(first_sentence) > 20:
                # 如果第一句话合理长度，使用第一句话
                tldr = first_sentence
                if not tldr.endswith('.'):
                    tldr += '.'
                return tldr
        
        # 否则使用前150个字符
        tldr = abstract[:150].strip()
        if len(tldr) == 150:
            # 确保不在单词中间截断
            last_space = tldr.rfind(' ')
            if last_space > 100:
                tldr = tldr[:last_space]
            tldr += '...'
        
        return tldr
    
    def test_access(self, test_url: str = None) -> bool:
        """测试CVF网站访问"""
        if not test_url:
            test_url = "https://openaccess.thecvf.com/"
        
        try:
            response = self.session.get(test_url, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def get_supported_item_types(self) -> List[str]:
        """获取支持的条目类型"""
        return ['conferencePaper'] 