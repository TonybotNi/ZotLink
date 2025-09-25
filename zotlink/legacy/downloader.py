"""
轻量级Nature文献下载器
基于requests和用户提供的cookies，无需Selenium
"""
import os
import json
import time
import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union
from urllib.parse import urljoin, urlparse
from pathlib import Path
import re

from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# 尝试导入Zotero集成模块
try:
    from .zotero_integration import ZoteroConnector
    ZOTERO_AVAILABLE = True
except ImportError:
    ZOTERO_AVAILABLE = False
    ZoteroConnector = None

logger = logging.getLogger(__name__)


class LightweightNatureDownloader:
    """轻量级Nature文献下载器"""
    
    def __init__(self, cookies: Union[Dict, str, None] = None):
        self.session = requests.Session()
        self.user_agent = UserAgent()
        self.download_dir = os.path.expanduser("~/Downloads/Nature_Papers")
        self.ensure_download_dir()
        
        # 设置请求头
        self.session.headers.update({
            'User-Agent': self.user_agent.chrome,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        if cookies:
            self.set_cookies(cookies)
        
        # 初始化Zotero连接器
        self.zotero = ZoteroConnector() if ZOTERO_AVAILABLE else None
            
    def ensure_download_dir(self):
        """确保下载目录存在"""
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"下载目录: {self.download_dir}")
    
    def set_cookies(self, cookies: Union[Dict, str]):
        """设置cookies"""
        if isinstance(cookies, str):
            # 如果是字符串，尝试解析为JSON
            try:
                cookies = json.loads(cookies)
            except json.JSONDecodeError:
                # 如果不是JSON，尝试解析cookie字符串格式
                cookies = self._parse_cookie_string(cookies)
        
        if isinstance(cookies, dict):
            self.session.cookies.update(cookies)
            logger.info("Cookies已设置")
        else:
            raise ValueError("不支持的cookies格式")
    
    def _parse_cookie_string(self, cookie_string: str) -> Dict:
        """解析cookie字符串格式（从浏览器复制的格式）"""
        cookies = {}
        
        # 处理从浏览器开发者工具复制的cookie格式
        for item in cookie_string.split(';'):
            if '=' in item:
                key, value = item.strip().split('=', 1)
                cookies[key] = value
        
        return cookies
    
    def load_cookies_from_browser(self, browser: str = "chrome") -> bool:
        """
        从浏览器数据库中读取cookies（macOS）
        
        Args:
            browser: 浏览器类型 ("chrome", "safari", "edge")
        """
        try:
            if browser.lower() == "chrome":
                return self._load_chrome_cookies()
            elif browser.lower() == "safari":
                return self._load_safari_cookies()
            else:
                logger.warning(f"不支持的浏览器: {browser}")
                return False
        except Exception as e:
            logger.error(f"从浏览器加载cookies失败: {e}")
            return False
    
    def _load_chrome_cookies(self) -> bool:
        """从Chrome浏览器加载Nature相关cookies"""
        try:
            import sqlite3
            import keyring
            from Crypto.Cipher import AES
            from Crypto.Protocol.KDF import PBKDF2
            
            # Chrome cookies数据库路径（macOS）
            chrome_cookies_path = os.path.expanduser(
                "~/Library/Application Support/Google/Chrome/Default/Cookies"
            )
            
            if not os.path.exists(chrome_cookies_path):
                logger.warning("Chrome cookies数据库不存在")
                return False
            
            # 连接数据库
            conn = sqlite3.connect(chrome_cookies_path)
            cursor = conn.cursor()
            
            # 查询Nature相关cookies
            cursor.execute(
                "SELECT name, value, host_key FROM cookies WHERE host_key LIKE '%nature%'"
            )
            
            cookies = {}
            for name, value, host in cursor.fetchall():
                cookies[name] = value
            
            conn.close()
            
            if cookies:
                self.session.cookies.update(cookies)
                logger.info(f"从Chrome加载了 {len(cookies)} 个cookies")
                return True
            else:
                logger.warning("未找到Nature相关cookies")
                return False
                
        except ImportError:
            logger.error("需要安装 pycryptodome 来解密Chrome cookies")
            return False
        except Exception as e:
            logger.error(f"加载Chrome cookies失败: {e}")
            return False
    
    def test_login_status(self) -> Dict:
        """测试当前登录状态"""
        try:
            # 访问Nature主页检查登录状态
            response = self.session.get("https://www.nature.com", timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 检查登录指标
            login_indicators = [
                soup.find('a', href=re.compile(r'logout|signout', re.I)),
                soup.find('div', class_=re.compile(r'user-menu|account', re.I)),
                soup.find('button', string=re.compile(r'logout|sign out', re.I))
            ]
            
            is_logged_in = any(indicator for indicator in login_indicators)
            
            # 尝试访问需要登录的页面
            test_response = self.session.get(
                "https://www.nature.com/my-account", 
                timeout=10, 
                allow_redirects=False
            )
            
            # 如果返回200而不是重定向到登录页面，说明已登录
            if test_response.status_code == 200:
                is_logged_in = True
            
            result = {
                "logged_in": is_logged_in,
                "status_code": response.status_code,
                "cookies_count": len(self.session.cookies),
                "test_url_status": test_response.status_code
            }
            
            logger.info(f"登录状态检查: {result}")
            return result
            
        except Exception as e:
            logger.error(f"检查登录状态失败: {e}")
            return {
                "logged_in": False,
                "error": str(e),
                "cookies_count": len(self.session.cookies)
            }
    
    def search_papers(self, query: str, max_results: int = 10) -> List[Dict]:
        """搜索论文"""
        try:
            search_url = f"https://www.nature.com/search"
            params = {
                'q': query,
                'page': 1
            }
            
            response = self.session.get(search_url, params=params, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            papers = []
            
            # 查找搜索结果
            result_selectors = [
                'article[data-test="search-result"]',
                '.c-card',
                '.c-list-item',
                'article'
            ]
            
            results = []
            for selector in result_selectors:
                results = soup.select(selector)
                if results:
                    break
            
            for result in results[:max_results]:
                try:
                    paper_info = self._extract_paper_info_from_soup(result)
                    if paper_info:
                        papers.append(paper_info)
                except Exception as e:
                    logger.warning(f"提取论文信息失败: {e}")
                    continue
            
            logger.info(f"找到 {len(papers)} 篇论文")
            return papers
            
        except Exception as e:
            logger.error(f"搜索论文失败: {e}")
            return []
    
    def _extract_paper_info_from_soup(self, element) -> Optional[Dict]:
        """从BeautifulSoup元素提取论文信息"""
        try:
            paper_info = {}
            
            # 提取标题和链接
            title_selectors = [
                'h3 a', 'h2 a', '.c-card__title a', 
                '[data-test="article-title"] a', 'a[data-track-action="view article"]'
            ]
            
            title_element = None
            for selector in title_selectors:
                title_element = element.select_one(selector)
                if title_element:
                    break
            
            if not title_element:
                return None
            
            paper_info['title'] = title_element.get_text(strip=True)
            href = title_element.get('href', '')
            
            # 构建完整URL
            if href.startswith('/'):
                paper_info['url'] = f"https://www.nature.com{href}"
            elif href.startswith('http'):
                paper_info['url'] = href
            else:
                paper_info['url'] = f"https://www.nature.com/{href}"
            
            # 提取作者
            author_selectors = [
                '.c-author-list', '.c-meta__authors', 
                '[data-test="author-list"]', '.authors'
            ]
            
            authors_element = None
            for selector in author_selectors:
                authors_element = element.select_one(selector)
                if authors_element:
                    break
            
            paper_info['authors'] = authors_element.get_text(strip=True) if authors_element else "未知作者"
            
            # 提取摘要
            abstract_selectors = [
                '.c-card__summary', '.c-card-teaser__summary',
                '[data-test="article-description"]', '.abstract'
            ]
            
            abstract_element = None
            for selector in abstract_selectors:
                abstract_element = element.select_one(selector)
                if abstract_element:
                    break
            
            paper_info['abstract'] = abstract_element.get_text(strip=True) if abstract_element else ""
            
            # 提取日期
            date_selectors = [
                'time', '.c-meta__date', '[data-test="publication-date"]'
            ]
            
            date_element = None
            for selector in date_selectors:
                date_element = element.select_one(selector)
                if date_element:
                    break
            
            paper_info['date'] = date_element.get_text(strip=True) if date_element else ""
            
            # 提取期刊
            journal_selectors = [
                '.c-meta__journal', '.journal-title'
            ]
            
            journal_element = None
            for selector in journal_selectors:
                journal_element = element.select_one(selector)
                if journal_element:
                    break
            
            paper_info['journal'] = journal_element.get_text(strip=True) if journal_element else "Nature"
            
            return paper_info
            
        except Exception as e:
            logger.warning(f"提取论文信息失败: {e}")
            return None
    
    def download_paper(self, paper_url: str, paper_title: str = "") -> Dict:
        """下载论文"""
        try:
            logger.info(f"开始下载论文: {paper_url}")
            
            # 访问论文页面
            response = self.session.get(paper_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            download_info = {
                "success": False,
                "files": [],
                "message": ""
            }
            
            # 查找PDF下载链接
            pdf_selectors = [
                'a[href$=".pdf"]',
                'a[data-track-action*="pdf"]',
                'a[href*="pdf"]',
                '.c-pdf-download a',
                '.pdf-download-link'
            ]
            
            pdf_downloaded = False
            for selector in pdf_selectors:
                pdf_links = soup.select(selector)
                for link in pdf_links:
                    pdf_url = link.get('href', '')
                    
                    if not pdf_url:
                        continue
                    
                    # 构建完整URL
                    if pdf_url.startswith('/'):
                        pdf_url = f"https://www.nature.com{pdf_url}"
                    elif not pdf_url.startswith('http'):
                        pdf_url = f"https://www.nature.com/{pdf_url}"
                    
                    # 下载PDF
                    filename = self._generate_filename(paper_title, "pdf")
                    if self._download_file(pdf_url, filename):
                        download_info["files"].append(filename)
                        pdf_downloaded = True
                        break
                
                if pdf_downloaded:
                    break
            
            # 如果没有PDF，保存HTML版本
            if not pdf_downloaded:
                logger.info("未找到PDF，保存HTML版本")
                html_filename = self._generate_filename(paper_title, "html")
                if self._save_html_content(response.content, html_filename, paper_url):
                    download_info["files"].append(html_filename)
            
            # 下载补充材料
            self._download_supplementary_materials(soup, download_info)
            
            if download_info["files"]:
                download_info["success"] = True
                download_info["message"] = f"成功下载 {len(download_info['files'])} 个文件"
            else:
                download_info["message"] = "无法下载任何文件"
            
            logger.info(f"下载完成: {download_info['message']}")
            return download_info
            
        except Exception as e:
            logger.error(f"下载论文失败: {e}")
            return {
                "success": False,
                "files": [],
                "message": f"下载失败: {str(e)}"
            }
    
    def _download_file(self, url: str, filename: str) -> bool:
        """下载文件"""
        try:
            logger.info(f"下载文件: {url}")
            
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            filepath = os.path.join(self.download_dir, filename)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            logger.info(f"文件下载成功: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"下载文件失败 {filename}: {e}")
            return False
    
    def _save_html_content(self, content: bytes, filename: str, url: str) -> bool:
        """保存HTML内容"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # 查找文章主体内容
            article_selectors = [
                'article', '.c-article-body', '.article-item-body',
                'main', '#content', '.main-content'
            ]
            
            article_content = None
            for selector in article_selectors:
                article_content = soup.select_one(selector)
                if article_content:
                    break
            
            if not article_content:
                article_content = soup
            
            # 创建完整的HTML文档
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{filename.replace('.html', '')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1, h2, h3 {{ color: #333; }}
        .source-url {{ background: #f0f0f0; padding: 10px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="source-url">
        <strong>原文链接:</strong> <a href="{url}">{url}</a>
    </div>
    {article_content}
</body>
</html>
"""
            
            filepath = os.path.join(self.download_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML内容保存成功: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"保存HTML内容失败: {e}")
            return False
    
    def _download_supplementary_materials(self, soup: BeautifulSoup, download_info: Dict):
        """下载补充材料"""
        try:
            supp_selectors = [
                'a[href*="supplementary"]',
                'a[href*="supplement"]',
                '.supplementary-material a',
                '.additional-information a'
            ]
            
            for selector in supp_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    
                    if not href:
                        continue
                    
                    # 构建完整URL
                    if href.startswith('/'):
                        href = f"https://www.nature.com{href}"
                    elif not href.startswith('http'):
                        continue
                    
                    # 检查是否是可下载的文件格式
                    downloadable_exts = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.csv']
                    if any(ext in href.lower() for ext in downloadable_exts):
                        ext = next((ext for ext in downloadable_exts if ext in href.lower()), '.pdf')
                        filename = self._generate_filename(f"supplementary_{text}", ext.lstrip('.'))
                        
                        if self._download_file(href, filename):
                            download_info["files"].append(filename)
            
        except Exception as e:
            logger.warning(f"下载补充材料失败: {e}")
    
    def _generate_filename(self, title: str, extension: str) -> str:
        """生成安全的文件名"""
        if not title:
            title = f"nature_paper_{int(time.time())}"
        
        # 清理标题
        safe_title = re.sub(r'[^\w\s-]', '', title).strip()
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        
        # 限制长度
        if len(safe_title) > 100:
            safe_title = safe_title[:100]
        
        return f"{safe_title}.{extension}"
    
    def export_cookies(self) -> str:
        """导出当前cookies为JSON字符串"""
        cookies_dict = dict(self.session.cookies)
        return json.dumps(cookies_dict, indent=2)
    
    def get_cookies_from_browser_manual(self) -> str:
        """返回手动获取cookies的指导说明"""
        return """
## 如何手动获取Nature网站的Cookies：

### 方法1：Chrome开发者工具
1. 打开Chrome浏览器，登录Nature网站
2. 按F12打开开发者工具
3. 进入"Application"标签页
4. 在左侧选择"Storage" > "Cookies" > "https://www.nature.com"
5. 复制所有cookies的内容

### 方法2：使用浏览器扩展
1. 安装"Cookie Editor"等浏览器扩展
2. 登录Nature网站后，点击扩展图标
3. 导出cookies为JSON格式

### 方法3：直接复制Cookie字符串
1. 登录Nature网站
2. 按F12，进入Network标签
3. 刷新页面，选择任意请求
4. 在Request Headers中找到Cookie字段
5. 复制整个Cookie字符串

使用示例：
```python
# JSON格式
cookies_json = '{"session_id": "abc123", "auth_token": "xyz789"}'

# Cookie字符串格式  
cookies_string = "session_id=abc123; auth_token=xyz789; path=/; domain=.nature.com"

downloader = LightweightNatureDownloader(cookies_json)
```
"""

    def enhanced_search_papers(self, keywords: str, max_results: int = 10) -> Dict:
        """
        增强的关键词搜索功能，返回最相关的论文
        
        Args:
            keywords: 搜索关键词
            max_results: 最大返回数量（默认10篇）
            
        Returns:
            Dict: 包含搜索结果的详细信息
        """
        try:
            logger.info(f"开始增强搜索: {keywords}")
            
            # 搜索结果
            results = {
                'query': keywords,
                'total_found': 0,
                'papers': [],
                'search_info': {
                    'timestamp': datetime.now().isoformat(),
                    'source': 'Nature.com',
                    'max_results': max_results
                }
            }
            
            # 多页搜索以获得更多结果
            all_papers = []
            pages_to_search = min(3, (max_results + 9) // 10)  # 最多搜索3页
            
            for page in range(1, pages_to_search + 1):
                try:
                    search_url = f"https://www.nature.com/search"
                    params = {
                        'q': keywords,
                        'page': page,
                        'order': 'relevance'  # 按相关性排序
                    }
                    
                    logger.info(f"搜索第 {page} 页...")
                    response = self.session.get(search_url, params=params, timeout=20)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 查找搜索结果
                    result_selectors = [
                        'article[data-test="search-result"]',
                        '.c-card',
                        '.c-list-item',
                        'article'
                    ]
                    
                    page_results = []
                    for selector in result_selectors:
                        page_results = soup.select(selector)
                        if page_results:
                            break
                    
                    logger.info(f"第 {page} 页找到 {len(page_results)} 个结果")
                    
                    for result in page_results:
                        try:
                            paper_info = self._extract_enhanced_paper_info(result, keywords)
                            if paper_info and paper_info['title']:
                                all_papers.append(paper_info)
                        except Exception as e:
                            logger.warning(f"提取论文信息失败: {e}")
                            continue
                    
                    # 如果已经获得足够的结果，可以提前停止
                    if len(all_papers) >= max_results * 1.5:
                        break
                        
                except Exception as e:
                    logger.warning(f"搜索第 {page} 页失败: {e}")
                    continue
            
            # 去重和排序
            unique_papers = []
            seen_urls = set()
            
            for paper in all_papers:
                if paper['url'] and paper['url'] not in seen_urls:
                    seen_urls.add(paper['url'])
                    unique_papers.append(paper)
            
            # 按相关性评分排序
            sorted_papers = self._rank_papers_by_relevance(unique_papers, keywords)
            
            # 取前max_results个结果
            final_papers = sorted_papers[:max_results]
            
            results['total_found'] = len(unique_papers)
            results['papers'] = final_papers
            results['search_info']['pages_searched'] = min(page, pages_to_search)
            results['search_info']['unique_results'] = len(unique_papers)
            
            logger.info(f"搜索完成: 找到 {len(unique_papers)} 篇唯一论文，返回前 {len(final_papers)} 篇")
            
            return results
            
        except Exception as e:
            logger.error(f"增强搜索失败: {e}")
            return {
                'query': keywords,
                'total_found': 0,
                'papers': [],
                'error': str(e),
                'search_info': {
                    'timestamp': datetime.now().isoformat(),
                    'source': 'Nature.com',
                    'max_results': max_results
                }
            }
    
    def _extract_enhanced_paper_info(self, element, keywords: str) -> Optional[Dict]:
        """提取增强的论文信息"""
        try:
            # 先使用现有的提取函数
            paper_info = self._extract_paper_info_from_soup(element)
            
            if not paper_info:
                return None
            
            # 添加相关性评分
            paper_info['relevance_score'] = self._calculate_relevance_score(paper_info, keywords)
            
            # 添加更多元数据
            paper_info['search_keywords'] = keywords
            paper_info['extracted_at'] = datetime.now().isoformat()
            
            # 确保URL是完整的
            if paper_info.get('url') and not paper_info['url'].startswith('http'):
                paper_info['url'] = f"https://www.nature.com{paper_info['url']}"
            
            # 添加下载准备标记
            paper_info['downloadable'] = bool(paper_info.get('url'))
            
            return paper_info
            
        except Exception as e:
            logger.warning(f"提取增强论文信息失败: {e}")
            return None
    
    def _calculate_relevance_score(self, paper_info: Dict, keywords: str) -> float:
        """计算论文相关性评分"""
        try:
            score = 0.0
            keywords_lower = keywords.lower()
            keyword_list = keywords_lower.split()
            
            # 标题匹配 (权重最高)
            title = paper_info.get('title', '').lower()
            for keyword in keyword_list:
                if keyword in title:
                    score += 3.0
            
            # 摘要匹配 (权重中等)
            abstract = paper_info.get('abstract', '').lower()
            for keyword in keyword_list:
                if keyword in abstract:
                    score += 2.0
            
            # 作者匹配 (权重较低)
            authors = paper_info.get('authors', '').lower()
            for keyword in keyword_list:
                if keyword in authors:
                    score += 1.0
            
            # 期刊匹配 (小权重)
            journal = paper_info.get('journal', '').lower()
            for keyword in keyword_list:
                if keyword in journal:
                    score += 0.5
            
            # 完整关键词匹配奖励
            full_text = f"{title} {abstract} {authors}".lower()
            if keywords_lower in full_text:
                score += 5.0
            
            return round(score, 2)
            
        except Exception as e:
            logger.warning(f"计算相关性评分失败: {e}")
            return 0.0
    
    def _rank_papers_by_relevance(self, papers: List[Dict], keywords: str) -> List[Dict]:
        """按相关性对论文进行排序"""
        try:
            # 按相关性评分降序排序，相同评分按日期排序
            return sorted(
                papers,
                key=lambda p: (
                    p.get('relevance_score', 0),
                    p.get('date', ''),
                    p.get('title', '')
                ),
                reverse=True
            )
        except Exception as e:
            logger.warning(f"排序失败: {e}")
            return papers

    def is_zotero_available(self) -> bool:
        """检查Zotero是否可用"""
        return ZOTERO_AVAILABLE and self.zotero and self.zotero.is_running()
    
    def get_zotero_collections(self) -> List[Dict]:
        """获取Zotero集合列表"""
        if not self.is_zotero_available():
            return []
        
        try:
            return self.zotero.get_collections()
        except Exception as e:
            logger.error(f"获取Zotero集合失败: {e}")
            return []
    
    def save_to_zotero(self, paper_info: Dict, pdf_path: Optional[str] = None, 
                      collection_key: Optional[str] = None) -> Dict:
        """
        保存论文到Zotero
        
        Args:
            paper_info: 论文信息字典
            pdf_path: PDF文件路径（可选）
            collection_key: 目标集合key（可选）
            
        Returns:
            Dict: 保存结果
        """
        if not ZOTERO_AVAILABLE:
            return {
                "success": False,
                "message": "Zotero集成模块不可用"
            }
        
        if not self.zotero:
            return {
                "success": False,
                "message": "Zotero连接器未初始化"
            }
        
        return self.zotero.save_item_to_zotero(paper_info, pdf_path, collection_key)
    
    def create_zotero_collection(self, name: str, parent_key: Optional[str] = None) -> Dict:
        """
        创建新的Zotero集合
        
        Args:
            name: 集合名称
            parent_key: 父集合key（可选，用于创建子集合）
            
        Returns:
            Dict: 创建结果
        """
        if not ZOTERO_AVAILABLE:
            return {
                "success": False,
                "message": "Zotero集成模块不可用"
            }
        
        if not self.zotero:
            return {
                "success": False,
                "message": "Zotero连接器未初始化"
            }
        
        return self.zotero.create_collection(name, parent_key)
    
    def download_and_save_to_zotero(self, paper_url: str, paper_title: str = "",
                                   collection_key: Optional[str] = None) -> Dict:
        """
        下载论文并保存到Zotero
        
        Args:
            paper_url: 论文URL
            paper_title: 论文标题
            collection_key: Zotero集合key
            
        Returns:
            Dict: 操作结果
        """
        try:
            # 首先下载论文
            download_result = self.download_paper(paper_url, paper_title)
            
            if not download_result["success"]:
                return {
                    "success": False,
                    "message": f"下载失败: {download_result.get('message', '未知错误')}"
                }
            
            # 获取下载的PDF路径
            pdf_path = None
            for file_path in download_result.get("files", []):
                if file_path.endswith(".pdf"):
                    pdf_path = file_path
                    break
            
            # 构建论文信息
            paper_info = {
                "title": paper_title or download_result.get("title", "未知标题"),
                "url": paper_url,
                "authors": download_result.get("authors", ""),
                "abstract": download_result.get("abstract", ""),
                "journal": "Nature",
                "date": download_result.get("date", ""),
            }
            
            # 保存到Zotero
            zotero_result = self.save_to_zotero(paper_info, pdf_path, collection_key)
            
            if zotero_result["success"]:
                return {
                    "success": True,
                    "message": "成功下载并保存到Zotero",
                    "download_files": download_result.get("files", []),
                    "zotero_key": zotero_result.get("zotero_key"),
                    "zotero_url": zotero_result.get("zotero_url")
                }
            else:
                return {
                    "success": False,
                    "message": f"下载成功但保存到Zotero失败: {zotero_result.get('message', '未知错误')}",
                    "download_files": download_result.get("files", [])
                }
                
        except Exception as e:
            logger.error(f"下载并保存到Zotero失败: {e}")
            return {
                "success": False,
                "message": f"操作失败: {e}"
            } 