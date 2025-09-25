#!/usr/bin/env python3
"""
🔗 ZotLink Nature 提取器

专门处理Nature系列期刊的学术论文提取
"""

import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
import logging
from urllib.parse import urljoin, urlparse

from .base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class NatureExtractor(BaseExtractor):
    """Nature期刊提取器"""
    
    def can_handle(self, url: str) -> bool:
        """检查是否为Nature系列网站"""
        nature_domains = ['nature.com', 'nature.org', 'springernature.com']
        return any(domain in url.lower() for domain in nature_domains)
    
    def get_database_name(self) -> str:
        return "Nature"
    
    def requires_authentication(self) -> bool:
        return True
    
    def extract_metadata(self, url: str) -> Dict:
        """从Nature URL提取论文元数据"""
        try:
            logger.info(f"🔄 开始提取Nature论文元数据: {url}")
            
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                return {'error': f'无法访问页面，状态码: {response.status_code}', 'url': url}
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            metadata = {
                'url': url,
                'itemType': 'journalArticle',
                'journal': 'Nature'
            }
            
            # 提取标题
            title_selectors = [
                'h1[data-test="article-title"]',
                'h1.c-article-title', 
                'h1.article-title',
                'h1'
            ]
            
            for selector in title_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        title = element.get_text(strip=True)
                        if title and len(title) > 3:
                            metadata['title'] = title
                            logger.info(f"📝 提取标题: {title}")
                            break
                except Exception:
                    continue
            
            # 提取作者
            authors = self._extract_authors(soup)
            if authors:
                metadata['authors'] = authors
                logger.info(f"👥 提取作者: {authors[:50]}...")
            
            # 提取摘要
            abstract_selectors = [
                '[data-test="abstract-content"]',
                '.c-article-section__content',
                '.abstract'
            ]
            
            for selector in abstract_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        abstract = element.get_text(strip=True)
                        if abstract and len(abstract) > 20:
                            metadata['abstract'] = abstract
                            logger.info(f"📄 提取摘要: {len(abstract)} 字符")
                            break
                except Exception:
                    continue
            
            # 提取DOI
            doi = self._extract_doi(soup, url)
            if doi:
                metadata['doi'] = doi
                logger.info(f"🔗 提取DOI: {doi}")
            
            # 提取PDF URL
            pdf_url = self._extract_pdf_url(soup, url)
            if pdf_url:
                metadata['pdf_url'] = pdf_url
                logger.info(f"📥 提取PDF URL: {pdf_url}")
            
            logger.info("✅ Nature元数据提取完成")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Nature元数据提取失败: {e}")
            return {'error': f'提取失败: {e}', 'url': url}
    
    def _extract_authors(self, soup: BeautifulSoup) -> Optional[str]:
        """提取作者"""
        authors_selectors = [
            '[data-test="author-name"]',
            '.c-article-author-list__item',
            '.AuthorName'
        ]
        
        authors = []
        for selector in authors_selectors:
            try:
                author_elements = soup.select(selector)
                if author_elements:
                    for elem in author_elements:
                        author_text = elem.get_text(strip=True)
                        if author_text and author_text not in authors:
                            authors.append(author_text)
                    break
            except Exception:
                continue
        
        return ', '.join(authors[:10]) if authors else None
    
    def _extract_doi(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """提取DOI"""
        # 从URL中提取DOI
        doi_match = re.search(r'nature\.com/articles/([^/?]+)', url)
        if doi_match:
            article_id = doi_match.group(1)
            if article_id.startswith('s'):
                return f"10.1038/{article_id}"
        
        return None
    
    def _extract_pdf_url(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """提取PDF URL - 优先主文章PDF"""
        try:
            # 方法1: 构造标准PDF URL（最可靠的方法）
            doi_match = re.search(r'nature\.com/articles/([^/?]+)', url)
            if doi_match:
                article_id = doi_match.group(1)
                # Nature的标准PDF URL格式
                constructed_pdf_url = f"https://www.nature.com/articles/{article_id}.pdf"
                logger.info(f"🔗 构造标准PDF URL: {constructed_pdf_url}")
                return constructed_pdf_url
            
            # 方法2: 查找主文章PDF下载链接
            main_pdf_selectors = [
                'a[data-track-action="download pdf"]',
                '.c-pdf-download a',
                '.pdf-download-link',
                '[data-test="pdf-link"]',
                'a[title*="Download PDF"]',
                'a[aria-label*="Download PDF"]'
            ]
            
            for selector in main_pdf_selectors:
                try:
                    pdf_links = soup.select(selector)
                    for link in pdf_links:
                        href = link.get('href')
                        if href and self._is_main_article_pdf(href):
                            # 转换为绝对URL
                            if href.startswith('/'):
                                pdf_url = urljoin(url, href)
                            elif href.startswith('http'):
                                pdf_url = href
                            else:
                                continue
                            
                            logger.info(f"🎯 找到主文章PDF链接: {pdf_url}")
                            return pdf_url
                except Exception as e:
                    logger.debug(f"PDF选择器 {selector} 失败: {e}")
                    continue
            
            # 方法3: 通用PDF链接（过滤补充材料）
            general_pdf_selectors = [
                'a[href*=".pdf"]',
                'a[href*="/pdf/"]'
            ]
            
            for selector in general_pdf_selectors:
                try:
                    pdf_links = soup.select(selector)
                    for link in pdf_links:
                        href = link.get('href')
                        if href and self._is_main_article_pdf(href):
                            if href.startswith('/'):
                                pdf_url = urljoin(url, href)
                            elif href.startswith('http'):
                                pdf_url = href
                            else:
                                continue
                            
                            logger.info(f"📄 找到PDF链接: {pdf_url}")
                            return pdf_url
                except Exception:
                    continue
            
            logger.warning("❌ 未找到主文章PDF链接")
            return None
            
        except Exception as e:
            logger.error(f"❌ PDF URL提取失败: {e}")
            return None
    
    def _is_main_article_pdf(self, url: str) -> bool:
        """判断是否是主文章PDF（排除补充材料）"""
        url_lower = url.lower()
        
        # 排除补充材料的关键词
        exclude_patterns = [
            'moesm',  # Supplementary materials
            'supplement', 
            'supporting',
            'additional',
            'si.pdf',  # Supporting Information
            'supp',
            'appendix',
            'mediaobjects'
        ]
        
        # 检查是否包含排除模式
        if any(pattern in url_lower for pattern in exclude_patterns):
            logger.debug(f"排除补充材料PDF: {url}")
            return False
        
        # 必须包含PDF相关模式
        include_patterns = ['.pdf', '/pdf/', 'download']
        if not any(pattern in url_lower for pattern in include_patterns):
            return False
            
        return True
