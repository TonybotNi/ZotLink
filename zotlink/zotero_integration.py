"""
🔗 ZotLink Zotero集成模块

扩展版本，支持多种学术数据库：
- arXiv（无需认证）
- Nature（需要cookies）
- 更多数据库（可扩展）
"""

import requests
import json
import time
import re
import sqlite3
import tempfile
import shutil
import os
from pathlib import Path
from typing import Dict, List, Optional
import logging
import asyncio
from datetime import datetime

# 导入提取器管理器
try:
    from .extractors.extractor_manager import ExtractorManager
    EXTRACTORS_AVAILABLE = True
except ImportError:
    try:
        # 备用导入路径
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent))
        from extractors.extractor_manager import ExtractorManager
        EXTRACTORS_AVAILABLE = True
    except ImportError:
        EXTRACTORS_AVAILABLE = False
        logging.warning("⚠️ 提取器管理器不可用，仅支持arXiv")

logger = logging.getLogger(__name__)


class ZoteroConnector:
    """ZotLink的Zotero连接器（扩展版本）"""
    
    def __init__(self):
        """初始化连接器"""
        self.base_url = "http://127.0.0.1:23119"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json'
        })
        
        # 初始化配置与数据库路径
        self._zotero_storage_dir: Optional[Path] = None
        self._zotero_db_override: Optional[Path] = None
        self._load_config_overrides()
        self._zotero_db_path = self._find_zotero_database()
        
        # 初始化提取器管理器
        if EXTRACTORS_AVAILABLE:
            self.extractor_manager = ExtractorManager()
            logger.info("✅ 提取器管理器初始化成功")
        else:
            self.extractor_manager = None
            logger.warning("⚠️ 提取器管理器不可用")

    def _load_config_overrides(self) -> None:
        """从环境变量与配置文件加载Zotero路径覆盖设置。
        优先级：环境变量 > Claude配置 > 本地配置文件 > 默认探测
        支持：
          - 环境变量 ZOTLINK_ZOTERO_ROOT 指定Zotero根目录（推荐，自动推导数据库和存储路径）
          - 环境变量 ZOTLINK_ZOTERO_DB 指定数据库完整路径（向后兼容）
          - 环境变量 ZOTLINK_ZOTERO_DIR 指定storage目录（向后兼容）
          - 通过MCP环境变量传递的配置
          - 配置文件 ~/.zotlink/config.json 中的 zotero.database_path / zotero.storage_dir
        """
        try:
            # 1. 首先检查是否设置了Zotero根目录（推荐方式）
            env_root = os.environ.get('ZOTLINK_ZOTERO_ROOT', '').strip()
            if env_root:
                root_path = Path(os.path.expanduser(env_root))
                if root_path.exists():
                    # 自动推导数据库和存储路径
                    candidate_db = root_path / "zotero.sqlite"
                    candidate_storage = root_path / "storage"
                    
                    if candidate_db.exists():
                        self._zotero_db_override = candidate_db
                        logger.info(f"🔧 从Zotero根目录自动推导数据库路径: {candidate_db}")
                    
                    if candidate_storage.exists():
                        self._zotero_storage_dir = candidate_storage
                        logger.info(f"🔧 从Zotero根目录自动推导存储目录: {candidate_storage}")
                    
                    if not candidate_db.exists() and not candidate_storage.exists():
                        logger.warning(f"⚠️ Zotero根目录 {root_path} 下未找到预期的数据库或存储目录")
                else:
                    logger.warning(f"⚠️ 环境变量ZOTLINK_ZOTERO_ROOT目录不存在: {root_path}")
            
            # 2. 环境变量优先（向后兼容，会覆盖根目录推导的结果）
            env_db = os.environ.get('ZOTLINK_ZOTERO_DB', '').strip()
            if env_db:
                candidate = Path(os.path.expanduser(env_db))
                if candidate.exists():
                    self._zotero_db_override = candidate
                    logger.info(f"🔧 使用环境变量ZOTLINK_ZOTERO_DB覆盖Zotero数据库路径: {candidate}")
                else:
                    logger.warning(f"⚠️ 环境变量ZOTLINK_ZOTERO_DB路径不存在: {candidate}")
            
            env_storage = os.environ.get('ZOTLINK_ZOTERO_DIR', '').strip()
            if env_storage:
                storage_path = Path(os.path.expanduser(env_storage))
                if storage_path.exists():
                    self._zotero_storage_dir = storage_path
                    logger.info(f"🔧 使用环境变量ZOTLINK_ZOTERO_DIR指定storage目录: {storage_path}")
                else:
                    logger.warning(f"⚠️ 环境变量ZOTLINK_ZOTERO_DIR目录不存在: {storage_path}")

            # Claude配置文件（若未通过环境变量设定）
            self._load_claude_config()

            # 本地配置文件（若前面方式都未设定）
            config_file = Path.home() / '.zotlink' / 'config.json'
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                    zotero_cfg = cfg.get('zotero', {}) if isinstance(cfg, dict) else {}

                    if not self._zotero_db_override:
                        cfg_db = zotero_cfg.get('database_path', '').strip()
                        if cfg_db:
                            cfg_db_path = Path(os.path.expanduser(cfg_db))
                            if cfg_db_path.exists():
                                self._zotero_db_override = cfg_db_path
                                logger.info(f"🔧 使用配置文件覆盖Zotero数据库路径: {cfg_db_path}")
                            else:
                                logger.warning(f"⚠️ 配置文件中database_path不存在: {cfg_db_path}")

                    if not self._zotero_storage_dir:
                        cfg_storage = zotero_cfg.get('storage_dir', '').strip()
                        if cfg_storage:
                            cfg_storage_path = Path(os.path.expanduser(cfg_storage))
                            if cfg_storage_path.exists():
                                self._zotero_storage_dir = cfg_storage_path
                                logger.info(f"🔧 使用配置文件指定storage目录: {cfg_storage_path}")
                            else:
                                logger.warning(f"⚠️ 配置文件中storage_dir不存在: {cfg_storage_path}")
                except Exception as e:
                    logger.warning(f"⚠️ 读取配置文件失败: {e}")
        except Exception as e:
            logger.warning(f"⚠️ 加载Zotero路径覆盖设置失败: {e}")

    def _load_claude_config(self) -> None:
        """从Claude配置文件加载Zotero路径设置。
        支持macOS/Linux和Windows的Claude配置路径。
        """
        try:
            # Claude配置文件路径（支持多平台）
            claude_config_paths = [
                Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",  # macOS
                Path.home() / ".config" / "claude" / "claude_desktop_config.json",                          # Linux
                Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"              # Windows
            ]
            
            for config_path in claude_config_paths:
                if config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            claude_config = json.load(f)
                        
                        # 查找zotlink服务器配置
                        mcp_servers = claude_config.get('mcpServers', {})
                        zotlink_config = mcp_servers.get('zotlink', {})
                        
                        # Claude配置文件存在，记录但不再读取非标准MCP字段
                        # 推荐使用env环境变量方式配置Zotero路径
                        logger.debug(f"📖 找到Claude配置文件: {config_path}")
                        logger.info("💡 推荐在MCP配置中使用env环境变量设置Zotero路径")
                        break
                        
                    except Exception as e:
                        logger.warning(f"⚠️ 读取Claude配置文件失败 {config_path}: {e}")
                        
        except Exception as e:
            logger.warning(f"⚠️ 加载Claude配置失败: {e}")
    
    def _extract_arxiv_metadata(self, arxiv_url: str) -> Dict:
        """从arxiv URL提取详细的论文元数据"""
        try:
            # 提取arxiv ID
            arxiv_id_match = re.search(r'arxiv\.org/(abs|pdf)/([^/?]+)', arxiv_url)
            if not arxiv_id_match:
                return {"error": "无法解析arxiv ID"}
            
            arxiv_id = arxiv_id_match.group(2)
            logger.info(f"提取arxiv ID: {arxiv_id}")
            
            # 获取arxiv摘要页面
            abs_url = f"https://arxiv.org/abs/{arxiv_id}"
            response = self.session.get(abs_url, timeout=10)
            
            if response.status_code != 200:
                return {"error": f"无法访问arxiv页面: {response.status_code}"}
            
            html_content = response.text
            
            # 提取论文信息
            metadata = {
                'arxiv_id': arxiv_id,
                'abs_url': abs_url,
                'pdf_url': f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            }
            
            # 提取标题
            title_match = re.search(r'<meta name="citation_title" content="([^"]+)"', html_content)
            if title_match:
                metadata['title'] = title_match.group(1)
            else:
                # 备选方式
                title_match = re.search(r'<h1[^>]*class="title[^"]*"[^>]*>([^<]+)</h1>', html_content)
                if title_match:
                    metadata['title'] = title_match.group(1).replace('Title:', '').strip()
            
            # 提取作者 - 改进版本
            authors = []
            
            # 方法1: 使用citation_author元数据（最准确）
            author_matches = re.findall(r'<meta name="citation_author" content="([^"]+)"', html_content)
            if author_matches:
                authors = author_matches
            else:
                # 方法2: 从作者链接中提取
                author_section = re.search(r'<div[^>]*class="[^"]*authors[^"]*"[^>]*>(.*?)</div>', html_content, re.DOTALL)
                if author_section:
                    # 提取所有作者链接
                    author_links = re.findall(r'<a[^>]*href="/search/\?searchtype=author[^"]*">([^<]+)</a>', author_section.group(1))
                    if author_links:
                        authors = [author.strip() for author in author_links]
            
            # 格式化作者列表 - 确保正确的姓名格式
            if authors:
                formatted_authors = []
                for author in authors:
                    # 如果是 "Last, First" 格式，保持不变
                    if ',' in author:
                        formatted_authors.append(author.strip())
                    else:
                        # 如果是 "First Last" 格式，转换为 "Last, First"
                        parts = author.strip().split()
                        if len(parts) >= 2:
                            last_name = parts[-1]
                            first_names = ' '.join(parts[:-1])
                            formatted_authors.append(f"{last_name}, {first_names}")
                        else:
                            formatted_authors.append(author.strip())
                
                metadata['authors'] = formatted_authors
                metadata['authors_string'] = '; '.join(formatted_authors)  # 使用分号分隔，更标准
            else:
                metadata['authors'] = []
                metadata['authors_string'] = ''
            
            # 提取摘要 - 改进版本
            abstract = None
            
            # 先尝试找到摘要区域
            abstract_section = re.search(r'<blockquote[^>]*class="abstract[^"]*"[^>]*>(.*?)</blockquote>', html_content, re.DOTALL)
            if abstract_section:
                abstract_html = abstract_section.group(1)
                
                # 提取所有文本内容
                abstract_text = re.sub(r'<[^>]+>', ' ', abstract_html)
                abstract_text = re.sub(r'\s+', ' ', abstract_text).strip()
                
                # 移除"Abstract:"标识符
                if abstract_text.startswith('Abstract:'):
                    abstract_text = abstract_text[9:].strip()
                
                # 过滤掉arXivLabs相关内容（通常在摘要最后）
                lines = abstract_text.split('.')
                filtered_lines = []
                
                for line in lines:
                    line = line.strip()
                    if not any(keyword in line.lower() for keyword in 
                             ['arxivlabs', 'framework that allows', 'collaborators to develop', 
                              'new arxiv features', 'directly on our website']):
                        filtered_lines.append(line)
                    else:
                        break  # 遇到arXivLabs内容就停止
                
                if filtered_lines:
                    abstract = '. '.join(filtered_lines).strip()
                    if abstract.endswith('.'):
                        abstract = abstract[:-1]  # 移除最后多余的句号
                    abstract = abstract + '.'  # 添加结束句号
            
            # 如果仍然没有找到摘要，尝试备选方法
            if not abstract:
                # 查找其他可能的摘要标记
                alt_patterns = [
                    r'<div[^>]*class="abstract[^"]*"[^>]*>.*?<p[^>]*>(.*?)</p>',
                    r'<meta[^>]+name="description"[^>]+content="([^"]+)"'
                ]
                
                for pattern in alt_patterns:
                    alt_match = re.search(pattern, html_content, re.DOTALL)
                    if alt_match:
                        abstract_candidate = alt_match.group(1).strip()
                        abstract_candidate = re.sub(r'<[^>]+>', '', abstract_candidate)
                        abstract_candidate = re.sub(r'\s+', ' ', abstract_candidate).strip()
                        
                        if len(abstract_candidate) > 50:
                            abstract = abstract_candidate
                            break
            
            if abstract and len(abstract) > 20:
                metadata['abstract'] = abstract
            
            # 提取日期 - 改进版本
            date_match = re.search(r'<meta name="citation_date" content="([^"]+)"', html_content)
            if date_match:
                metadata['date'] = date_match.group(1)
            else:
                # 备选方法：从提交信息中提取
                date_match = re.search(r'\[Submitted on ([^\]]+)\]', html_content)
                if date_match:
                    date_str = date_match.group(1).strip()
                    # 转换日期格式为标准格式
                    try:
                        import datetime
                        # 尝试解析各种日期格式
                        for fmt in ['%d %b %Y', '%B %d, %Y', '%Y-%m-%d']:
                            try:
                                parsed_date = datetime.strptime(date_str, fmt)
                                metadata['date'] = parsed_date.strftime('%Y/%m/%d')
                                break
                            except ValueError:
                                continue
                        else:
                            metadata['date'] = date_str
                    except:
                        metadata['date'] = date_str
            
            # 提取评论信息（页数、图表等）
            comment = None
            
            # 方式1: 标准表格格式
            comment_match = re.search(r'<td class="comments">([^<]+)</td>', html_content)
            if comment_match:
                comment = comment_match.group(1).strip()
            
            # 方式2: Comments标签后的内容
            if not comment:
                comment_match = re.search(r'Comments:\s*([^\n<]+)', html_content)
                if comment_match:
                    comment = comment_match.group(1).strip()
            
            # 方式3: 直接搜索页数和图表信息
            if not comment:
                pages_figures = re.search(r'(\d+\s*pages?,?\s*\d*\s*figures?)', html_content, re.IGNORECASE)
                if pages_figures:
                    comment = pages_figures.group(1).strip()
            
            # 方式4: 更宽泛的页数搜索
            if not comment:
                pages_match = re.search(r'(\d+\s*pages?[^<\n]{0,30})', html_content, re.IGNORECASE)
                if pages_match:
                    comment = pages_match.group(1).strip()
            
            if comment:
                metadata['comment'] = comment
            
            # 提取学科分类
            subjects_matches = re.findall(r'<span class="primary-subject">([^<]+)</span>', html_content)
            if subjects_matches:
                metadata['subjects'] = subjects_matches
            else:
                # 备选方式
                subjects_matches = re.findall(r'class="[^"]*subject-class[^"]*">([^<]+)</span>', html_content)
                if subjects_matches:
                    metadata['subjects'] = subjects_matches
            
            # 提取DOI（如果有）
            doi_match = re.search(r'<meta name="citation_doi" content="([^"]+)"', html_content)
            if doi_match:
                metadata['doi'] = doi_match.group(1)
            
            # 提取期刊信息（如果已发表）
            journal_match = re.search(r'<meta name="citation_journal_title" content="([^"]+)"', html_content)
            if journal_match:
                metadata['published_journal'] = journal_match.group(1)
            
            # 设置默认值
            metadata.setdefault('title', 'Unknown arXiv Paper')
            metadata.setdefault('authors_string', 'Unknown Authors')
            metadata.setdefault('date', time.strftime('%Y'))
            metadata.setdefault('abstract', '')
            
            logger.info(f"成功提取arxiv元数据: {metadata.get('title', 'Unknown')}")
            return metadata
            
        except Exception as e:
            logger.error(f"提取arxiv元数据失败: {e}")
            return {"error": f"元数据提取失败: {e}"}
    
    def _enhance_paper_info_for_arxiv(self, paper_info: Dict) -> Dict:
        """为arxiv论文增强元数据"""
        url = paper_info.get('url', '')
        
        if 'arxiv.org' in url:
            logger.info("检测到arxiv论文，开始增强元数据...")
            arxiv_metadata = self._extract_arxiv_metadata(url)
            
            if 'error' not in arxiv_metadata:
                # 合并元数据，优先使用arxiv提取的信息
                enhanced_info = paper_info.copy()
                enhanced_info.update({
                    'title': arxiv_metadata.get('title', paper_info.get('title', '')),
                    'authors': arxiv_metadata.get('authors_string', paper_info.get('authors', '')),
                    'abstract': arxiv_metadata.get('abstract', paper_info.get('abstract', '')),
                    'date': arxiv_metadata.get('date', paper_info.get('date', '')),
                    'journal': 'arXiv',
                    'itemType': 'preprint',
                    'url': arxiv_metadata.get('abs_url', url),
                    'arxiv_id': arxiv_metadata.get('arxiv_id', ''),
                    'pdf_url': arxiv_metadata.get('pdf_url', ''),
                    'comment': arxiv_metadata.get('comment', ''),  # 添加comment信息
                    'subjects': arxiv_metadata.get('subjects', []),  # 添加学科信息
                    'doi': arxiv_metadata.get('doi', ''),  # 添加DOI
                    'published_journal': arxiv_metadata.get('published_journal', ''),  # 添加发表期刊
                })
                
                logger.info(f"arxiv元数据增强完成: {enhanced_info.get('title', 'Unknown')}")
                return enhanced_info
            else:
                logger.warning(f"arxiv元数据增强失败: {arxiv_metadata.get('error', 'Unknown')}")
        
        return paper_info

    def _find_zotero_database(self) -> Optional[Path]:
        """查找Zotero数据库文件，优先使用覆盖路径。"""
        # 覆盖优先
        if self._zotero_db_override and Path(self._zotero_db_override).exists():
            logger.info(f"找到Zotero数据库(覆盖): {self._zotero_db_override}")
            return self._zotero_db_override

        # 按系统默认路径探测
        possible_paths: List[Path] = []
        platform = os.name  # 'posix' / 'nt'

        # 通用路径
        possible_paths.append(Path.home() / 'Zotero' / 'zotero.sqlite')

        # macOS
        possible_paths.append(Path.home() / 'Library' / 'Application Support' / 'Zotero' / 'zotero.sqlite')
        profiles_base_mac = Path.home() / 'Library' / 'Application Support' / 'Zotero' / 'Profiles'
        if profiles_base_mac.exists():
            for profile_dir in profiles_base_mac.iterdir():
                if profile_dir.is_dir():
                    possible_paths.append(profile_dir / 'zotero.sqlite')

        # Windows（APPDATA 下的Profiles）
        appdata = os.environ.get('APPDATA')
        if appdata:
            profiles_base_win = Path(appdata) / 'Zotero' / 'Zotero' / 'Profiles'
            if profiles_base_win.exists():
                for profile_dir in profiles_base_win.iterdir():
                    if profile_dir.is_dir():
                        possible_paths.append(profile_dir / 'zotero.sqlite')

        # Linux 常见路径（若用户将Zotero放在家目录）
        possible_paths.append(Path.home() / '.zotero' / 'zotero.sqlite')

        for path in possible_paths:
            try:
                if path.exists():
                    logger.info(f"找到Zotero数据库: {path}")
                    return path
            except Exception:
                continue
        
        logger.warning("未找到Zotero数据库文件")
        return None

    def _read_collections_from_db(self) -> List[Dict]:
        """直接从数据库读取集合信息"""
        if not self._zotero_db_path or not self._zotero_db_path.exists():
            logger.error("Zotero数据库文件不存在")
            return []
        
        try:
            # 创建临时副本以避免锁定问题
            with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as temp_file:
                shutil.copy2(self._zotero_db_path, temp_file.name)
                temp_db_path = temp_file.name
            
            try:
                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()
                
                # 查询集合信息
                query = """
                SELECT 
                    c.collectionID,
                    c.collectionName,
                    c.parentCollectionID,
                    c.key
                FROM collections c
                ORDER BY c.collectionName
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                collections = []
                for row in rows:
                    collection_data = {
                        'id': row[0],
                        'name': row[1],
                        'parentCollection': row[2] if row[2] else None,
                        'key': row[3] if row[3] else f"collection_{row[0]}"
                    }
                    collections.append(collection_data)
                
                conn.close()
                logger.info(f"从数据库成功读取 {len(collections)} 个集合")
                return collections
                
            finally:
                # 清理临时文件
                try:
                    Path(temp_db_path).unlink()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"读取数据库集合失败: {e}")
            return []
    
    def is_running(self) -> bool:
        """检查Zotero是否在运行"""
        try:
            response = self.session.get(f"{self.base_url}/connector/ping", timeout=2)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Zotero未运行或无法连接: {e}")
            return False
    
    def get_version(self) -> Optional[str]:
        """获取Zotero版本信息"""
        try:
            if not self.is_running():
                return None
            
            response = self.session.get(f"{self.base_url}/connector/ping", timeout=5)
            if response.status_code == 200:
                # Zotero ping返回HTML，不是JSON
                if "Zotero is running" in response.text:
                    return "Zotero Desktop (Unknown version)"
                else:
                    return "unknown"
        except Exception as e:
            logger.debug(f"获取Zotero版本失败: {e}")
            return "unknown"
    
    def get_collections(self) -> List[Dict]:
        """获取所有集合
        优先尝试直接读取数据库，备选API方式
        """
        try:
            if not self.is_running():
                return []
            
            # 首先尝试直接从数据库读取（新的解决方案！）
            logger.info("尝试直接从数据库读取集合...")
            db_collections = self._read_collections_from_db()
            
            if db_collections:
                logger.info(f"✅ 成功从数据库获取 {len(db_collections)} 个集合")
                return db_collections
            
            # 如果数据库读取失败，回退到API方式
            logger.info("数据库读取失败，尝试API方式...")
            api_endpoints = [
                "/api/users/local/collections",  # Zotero 7 本地API
                "/connector/collections",        # 可能的Connector API
                "/api/collections"               # 另一种可能的端点
            ]
            
            for endpoint in api_endpoints:
                try:
                    response = self.session.get(f"{self.base_url}{endpoint}", timeout=5)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if isinstance(data, list):
                                logger.info(f"成功从端点获取集合: {endpoint}")
                                return data
                            elif isinstance(data, dict) and 'collections' in data:
                                return data['collections']
                        except json.JSONDecodeError:
                            continue
                except Exception as e:
                    logger.debug(f"测试端点{endpoint}失败: {e}")
                    continue
            
            logger.warning("无法通过API或数据库获取集合列表")
            return []
                
        except Exception as e:
            logger.error(f"获取Zotero集合失败: {e}")
            return []
    
    def save_item_to_zotero(self, paper_info: Dict, pdf_path: Optional[str] = None, 
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
        try:
            if not self.is_running():
                return {
                    "success": False,
                    "message": "Zotero未运行，请启动Zotero桌面应用"
                }
            
            # 🎯 关键扩展：使用提取器管理器增强元数据
            enhanced_paper_info = self._enhance_paper_metadata(paper_info)
            
            # 如果增强失败，回退到原始信息
            if 'error' in enhanced_paper_info:
                logger.warning(f"⚠️ 元数据增强失败: {enhanced_paper_info['error']}")
                enhanced_paper_info = paper_info

            # 构建Zotero项目数据
            zotero_item = self._convert_to_zotero_format(enhanced_paper_info)
            
            # 保存到Zotero
            result = self._save_via_connector(zotero_item, pdf_path, collection_key)
            
            # 添加扩展信息到结果
            if result["success"]:
                result["database"] = enhanced_paper_info.get('extractor', 'arXiv')
                result["enhanced"] = 'extractor' in enhanced_paper_info
            
            # 对于arxiv论文，在元数据保存成功后处理PDF
            if result["success"] and 'arxiv.org' in enhanced_paper_info.get('url', '') and enhanced_paper_info.get('arxiv_id'):
                logger.info("元数据保存成功，现在处理PDF...")
                
                # 在Extra字段中添加PDF信息，用户可以手动下载
                pdf_url = f"https://arxiv.org/pdf/{enhanced_paper_info['arxiv_id']}.pdf"
                result["pdf_url"] = pdf_url
                result["pdf_info"] = f"PDF可从以下链接下载: {pdf_url}"
                result["message"] += f"\n📥 PDF链接: {pdf_url}"
                
                logger.info(f"✅ PDF链接已添加到条目信息中: {pdf_url}")
            
            if result["success"]:
                logger.info(f"成功保存到Zotero: {enhanced_paper_info.get('title', '未知标题')}")
            
            return result
            
        except Exception as e:
            logger.error(f"保存到Zotero失败: {e}")
            return {
                "success": False,
                "message": f"保存到Zotero失败: {e}"
            }
    
    def _convert_to_zotero_format(self, paper_info: Dict) -> Dict:
        """将论文信息转换为Zotero格式"""
        
        # 解析作者 - 修复分号分隔问题
        authors = []
        if paper_info.get('authors'):
            authors_str = paper_info['authors']
            
            # 🚨 关键修复: 正确分割作者列表
            # 优先使用分号分割（我们的标准格式）
            if ';' in authors_str:
                author_names = authors_str.split(';')
            elif ',' in authors_str and ' and ' not in authors_str:
                # 如果没有分号但有逗号，且不是连接词，可能是老格式
                author_names = authors_str.split(',')
            else:
                # 备用：按'and'分割
                author_names = authors_str.replace(' and ', ',').split(',')
            
            for author_name in author_names[:15]:  # 限制作者数量
                author_name = author_name.strip()
                if not author_name or author_name == '未知作者':
                    continue
                
                # 解析"姓, 名"格式
                if ',' in author_name:
                    parts = author_name.split(',', 1)  # 只分割第一个逗号
                    lastName = parts[0].strip()
                    firstName = parts[1].strip()
                else:
                    # 处理"名 姓"格式
                    parts = author_name.split()
                    if len(parts) >= 2:
                        firstName = ' '.join(parts[:-1])
                        lastName = parts[-1]
                    else:
                        firstName = ""
                        lastName = author_name
                
                # 确保不为空
                if firstName or lastName:
                    authors.append({
                        "creatorType": "author",
                        "firstName": firstName,
                        "lastName": lastName
                    })
        
        # 解析日期
        date = paper_info.get('date', '')
        if date and date != '未知日期':
            # 尝试标准化日期格式
            try:
                # 处理arxiv和其他常见的日期格式
                # 格式1: "12 Jun 2017"
                date_match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date)
                if date_match:
                    day, month_name, year = date_match.groups()
                    months = {
                        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                        'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                        'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                    }
                    month = months.get(month_name[:3], '01')
                    date = f"{year}-{month}-{day.zfill(2)}"
                # 格式2: "2017/06/12" 或 "2017-06-12"
                elif re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date):
                    # 已经是标准格式，保持不变
                    pass
                # 格式3: 只有年份 "2017"
                elif re.search(r'^\d{4}$', date):
                    date = f"{date}-01-01"
            except:
                pass
        
        # 确定项目类型 
        item_type = paper_info.get('itemType', 'journalArticle')
        if 'arxiv.org' in paper_info.get('url', ''):
            item_type = 'preprint'  # arxiv论文使用preprint类型
        
        # 构建Zotero项目
        zotero_item = {
            "itemType": item_type,
            "title": paper_info.get('title', ''),
            "creators": authors,
            "abstractNote": paper_info.get('abstract', ''),
            "publicationTitle": self._get_default_publication_title(paper_info),
            "url": paper_info.get('url', ''),
            "date": date
        }
        
        # 🆕 为预印本添加官方Zotero Connector兼容的字段
        if item_type == 'preprint':
            if 'arxiv.org' in paper_info.get('url', '') and paper_info.get('arxiv_id'):
                # arXiv特殊处理
                zotero_item["repository"] = "arXiv"
                zotero_item["archiveID"] = f"arXiv:{paper_info['arxiv_id']}"
                zotero_item["libraryCatalog"] = "arXiv.org"
                
                # 美式日期时间格式
                import datetime
                now = datetime.datetime.now()
                month = now.month
                day = now.day
                year = now.year
                hour = now.hour
                minute = now.minute
                second = now.second
                
                if hour == 0:
                    hour_12 = 12
                    am_pm = "AM"
                elif hour < 12:
                    hour_12 = hour
                    am_pm = "AM"
                elif hour == 12:
                    hour_12 = 12
                    am_pm = "PM"
                else:
                    hour_12 = hour - 12
                    am_pm = "PM"
                
                us_format = f"{month}/{day}/{year}, {hour_12}:{minute:02d}:{second:02d} {am_pm}"
                zotero_item["accessDate"] = us_format
            else:
                # 🆕 其他预印本服务器的通用处理
                if paper_info.get('repository'):
                    zotero_item["repository"] = paper_info['repository']
                
                if paper_info.get('archiveID'):
                    zotero_item["archiveID"] = paper_info['archiveID']
                elif paper_info.get('DOI'):
                    # 如果没有专门的archiveID，使用DOI
                    zotero_item["archiveID"] = paper_info['DOI']
                
                if paper_info.get('libraryCatalog'):
                    zotero_item["libraryCatalog"] = paper_info['libraryCatalog']
                
                # 标准访问日期格式
                if paper_info.get('accessDate'):
                    zotero_item["accessDate"] = paper_info['accessDate']
                else:
                    zotero_item["accessDate"] = time.strftime('%Y-%m-%d')
        else:
            # 非预印本使用标准格式
            zotero_item["accessDate"] = time.strftime('%Y-%m-%d')
        
        # 🚨 修复：为arxiv论文添加PDF URL（供_save_via_connector使用）
        if paper_info.get('arxiv_id') and paper_info.get('pdf_url'):
            zotero_item["pdf_url"] = paper_info['pdf_url']  # 关键：添加pdf_url字段
        
        # 🚀 关键修复：传递浏览器预下载的PDF内容（arXiv路径）
        if paper_info.get('pdf_content'):
            zotero_item["pdf_content"] = paper_info['pdf_content']
            logger.info(f"✅ 传递浏览器预下载的PDF内容: {len(paper_info['pdf_content'])} bytes")
        
        # 添加arxiv特殊字段和增强信息
        if paper_info.get('arxiv_id'):
            # 🆕 使用官方Zotero Connector兼容的Extra格式: "arXiv:ID [学科]"
            arxiv_id = paper_info['arxiv_id']
            extra_parts = [f"arXiv:{arxiv_id}"]
            
            # 添加主要学科分类的缩写 (如 [cs] 表示 Computer Science)
            if paper_info.get('subjects'):
                # 提取第一个学科的缩写
                first_subject = paper_info['subjects'][0]
                # 从"Computation and Language (cs.CL)"中提取"cs"
                subject_match = re.search(r'\(([^.]+)', first_subject)
                if subject_match:
                    subject_abbr = subject_match.group(1)
                    extra_parts.append(f"[{subject_abbr}]")
            
            # 构建简洁的Extra信息 (与官方插件格式一致)
            zotero_item["extra"] = " ".join(extra_parts)
            
            # 添加DOI字段（如果有）
            if paper_info.get('doi'):
                zotero_item["DOI"] = paper_info['doi']
            
            # 如果已发表到期刊，更新期刊名称
            if paper_info.get('published_journal'):
                zotero_item["publicationTitle"] = paper_info['published_journal']
        else:
            # 处理其他数据库的元数据
            extra_info = f"下载来源: ZotLink\n"
            
            if paper_info.get('extractor'):
                extra_info += f"数据库: {paper_info['extractor']}\n"
            
            # 添加DOI字段
            if paper_info.get('DOI'):
                zotero_item["DOI"] = paper_info['DOI']
                extra_info += f"DOI: {paper_info['DOI']}\n"
            elif paper_info.get('doi'):
                zotero_item["DOI"] = paper_info['doi']
                extra_info += f"DOI: {paper_info['doi']}\n"
            
            if paper_info.get('comment'):
                extra_info += f"Comment: {paper_info['comment']}\n"
            
            if paper_info.get('pdf_url'):
                extra_info += f"PDF链接: {paper_info['pdf_url']}\n"
                zotero_item["pdf_url"] = paper_info['pdf_url']

            # 🚀 关键修复：传递浏览器预下载的PDF内容（非arXiv路径）
            if paper_info.get('pdf_content'):
                zotero_item["pdf_content"] = paper_info['pdf_content']
                logger.info(f"✅ 传递浏览器预下载的PDF内容: {len(paper_info['pdf_content'])} bytes")
            
            zotero_item["extra"] = extra_info
        
        # 🔑 添加PDF附件（如果有）
        if paper_info.get('pdf_url'):
            zotero_item["attachments"] = [{
                "title": "Full Text PDF",
                "url": paper_info['pdf_url'],
                "mimeType": "application/pdf",
                "snapshot": False  # 链接附件，不下载内容
            }]
        
        # 移除空值
        zotero_item = {k: v for k, v in zotero_item.items() if v}
        
        return zotero_item
    
    def _download_pdf_content(self, pdf_url: str) -> Optional[bytes]:
        """
        尝试下载PDF内容
        
        Args:
            pdf_url: PDF链接
            
        Returns:
            PDF文件的二进制内容，失败返回None
        """
        try:
            import requests
            
            # 🧬 特殊处理：bioRxiv使用MCP高级浏览器下载
            if 'biorxiv.org' in pdf_url.lower():
                logger.info("🧬 检测到bioRxiv - 启动MCP高级浏览器下载")
                try:
                    # 使用事件循环兼容的异步调用
                    import asyncio
                    # 使用包内相对导入，避免在运行环境中找不到顶级模块
                    from .extractors.browser_extractor import BrowserExtractor
                    
                    async def download_biorxiv_mcp():
                        async with BrowserExtractor() as extractor:
                            return await extractor._download_biorxiv_with_mcp(extractor, pdf_url)
                    
                    # 在新线程中创建新事件循环执行异步任务
                    import concurrent.futures
                    import threading
                    
                    def run_in_thread():
                        # 在新线程中创建新事件循环
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(download_biorxiv_mcp())
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_in_thread)
                        pdf_content = future.result(timeout=120)  # 放宽到120秒
                    
                    if pdf_content:
                        logger.info(f"✅ MCP浏览器下载bioRxiv PDF成功: {len(pdf_content):,} bytes")
                        return pdf_content
                    else:
                        logger.warning("⚠️ MCP浏览器下载bioRxiv PDF失败，尝试备用反爬虫下载器")
                        # 回退：使用通用反爬虫下载器
                        # 在独立线程中调用异步下载器，避免事件循环冲突
                        try:
                            import concurrent.futures
                            import asyncio
                            
                            def run_fallback_thread():
                                new_loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(new_loop)
                                try:
                                    from .tools.anti_crawler_pdf_downloader import download_anti_crawler_pdf_async
                                    return new_loop.run_until_complete(download_anti_crawler_pdf_async(pdf_url))
                                finally:
                                    new_loop.close()
                            
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(run_fallback_thread)
                                fallback_content = future.result(timeout=120)
                        except Exception:
                            fallback_content = None
                        if fallback_content:
                            logger.info(f"✅ 备用下载器成功获取PDF: {len(fallback_content):,} bytes")
                            return fallback_content
                        return None
                        
                except Exception as e:
                    logger.error(f"❌ MCP浏览器下载异常: {e}")
                    # 异常也尝试备用下载器
                    # 异常路径同样在线程中调用异步下载器
                    try:
                        import concurrent.futures
                        import asyncio
                        
                        def run_fallback_thread():
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            try:
                                from .tools.anti_crawler_pdf_downloader import download_anti_crawler_pdf_async
                                return new_loop.run_until_complete(download_anti_crawler_pdf_async(pdf_url))
                            finally:
                                new_loop.close()
                        
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(run_fallback_thread)
                            fallback_content = future.result(timeout=120)
                    except Exception:
                        fallback_content = None
                    if fallback_content:
                        logger.info(f"✅ 备用下载器成功获取PDF: {len(fallback_content):,} bytes")
                        return fallback_content
                    return None
            else:
                # 对于普通网站，使用HTTP请求
                logger.info("📥 使用HTTP请求下载PDF")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'application/pdf,*/*',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive'
                }
                
                response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
                
                if response.status_code == 200:
                    content = response.content
                    
                    # 验证是否为有效PDF
                    if content and content.startswith(b'%PDF'):
                        logger.info(f"✅ HTTP下载成功: {len(content)} bytes")
                        return content
                    else:
                        logger.warning("⚠️ 下载的内容不是有效PDF")
                        return None
                else:
                    logger.warning(f"⚠️ HTTP下载失败: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ PDF下载异常: {e}")
            return None
    
    def _get_default_publication_title(self, paper_info: Dict) -> str:
        """根据论文信息智能确定默认的期刊/会议名称"""
        
        # 优先使用已提取的期刊信息
        if paper_info.get('journal'):
            return paper_info['journal']
        
        if paper_info.get('publicationTitle'):
            return paper_info['publicationTitle']
        
        if paper_info.get('proceedingsTitle'):
            return paper_info['proceedingsTitle']
        
        # 根据URL和提取器类型确定默认值
        url = paper_info.get('url', '')
        extractor = paper_info.get('extractor', '')
        
        # arXiv论文
        if 'arxiv.org' in url:
            return 'arXiv'
        
        # 🆕 其他预印本服务器
        if 'medrxiv.org' in url:
            return 'medRxiv'
        elif 'biorxiv.org' in url:
            return 'bioRxiv'
        elif 'chemrxiv.org' in url:
            return 'ChemRxiv'
        elif 'psyarxiv.com' in url:
            return 'PsyArXiv'
        elif 'socarxiv.org' in url:
            return 'SocArXiv'
        
        # CVF论文
        if 'thecvf.com' in url or extractor.upper() == 'CVF':
            # 从URL推断会议名称
            if '/ICCV' in url:
                return 'IEEE International Conference on Computer Vision (ICCV)'
            elif '/CVPR' in url:
                return 'IEEE Conference on Computer Vision and Pattern Recognition (CVPR)'
            elif '/WACV' in url:
                return 'IEEE Winter Conference on Applications of Computer Vision (WACV)'
            else:
                return 'IEEE Computer Vision Conference'
        
        # Nature论文
        if 'nature.com' in url or extractor.upper() == 'NATURE':
            return 'Nature'
        
        # 根据条目类型确定默认值
        item_type = paper_info.get('itemType', '')
        if item_type == 'conferencePaper':
            return 'Conference Proceedings'
        elif item_type == 'preprint':
            return 'Preprint Server'
        
        # 最终默认值
        return 'Unknown Journal'
    
    def _save_via_connector(self, zotero_item: Dict, pdf_path: Optional[str] = None, 
                           collection_key: Optional[str] = None) -> Dict:
        """通过Connector API保存项目 - 实用解决方案"""
        try:
            import time
            import json
            import requests
            
            session_id = f"success-test-{int(time.time() * 1000)}"
            
            # 🎯 按照官方插件方法：生成随机ID
            import random
            import string
            
            # 生成8位随机字符串ID（模仿官方插件）
            random_item_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            
            clean_item = {
                "itemType": zotero_item.get("itemType", "journalArticle"),
                "title": zotero_item.get("title", ""),
                "url": zotero_item.get("url", ""),
                "id": random_item_id,  # 关键：添加随机ID
                "tags": [],
                "notes": [],
                "seeAlso": [],
                "attachments": []
            }
            
            # 添加完整元数据 - 确保Comment信息在Extra字段中
            if zotero_item.get("creators"):
                clean_item["creators"] = zotero_item["creators"]
            if zotero_item.get("abstractNote"):
                clean_item["abstractNote"] = zotero_item["abstractNote"]
            if zotero_item.get("date"):
                clean_item["date"] = zotero_item["date"]
            if zotero_item.get("publicationTitle"):
                clean_item["publicationTitle"] = zotero_item["publicationTitle"]
            if zotero_item.get("DOI"):
                clean_item["DOI"] = zotero_item["DOI"]
            
            # 🎯 关键：确保Extra字段（包含Comment）被正确保存
            if zotero_item.get("extra"):
                clean_item["extra"] = zotero_item["extra"]
                logger.info(f"✅ Extra字段（包含Comment）: {len(clean_item['extra'])} characters")
                # 显示comment预览
                if 'Comment:' in clean_item['extra']:
                    comment_line = [line for line in clean_item['extra'].split('\n') if 'Comment:' in line][0]
                    logger.info(f"📝 Comment预览: {comment_line}")
            
            # 生成item_id和headers（需要在PDF处理前定义）
            item_id = f"item_{int(time.time() * 1000)}"
            clean_item["id"] = item_id
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Content-Type': 'application/json',
                'X-Zotero-Version': '5.0.97',
                'X-Zotero-Connector-API-Version': '3'
            }
            
            session = requests.Session()
            session.headers.update(headers)
            
            # 🎯 最终策略：不在saveItems中包含附件，稍后手动触发下载
            pdf_url = zotero_item.get('pdf_url')
            
            if pdf_url:
                logger.info(f"🔍 发现PDF链接: {pdf_url}")
                logger.info("📎 将在保存后手动触发PDF下载")
            
            # 为item生成随机ID
            import random
            import string
            item_id = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
            clean_item["id"] = item_id
            
            # 添加链接附件（不会被下载的）
            if pdf_url:
                if not clean_item.get("attachments"):
                    clean_item["attachments"] = []
                clean_item["attachments"].append({
                    "title": f"{clean_item.get('repository', 'Online')} Snapshot",
                    "url": clean_item.get('url', pdf_url),
                    "snapshot": False
                })
            
            # 构建保存payload
            payload = {
                "sessionID": session_id,
                "uri": zotero_item.get("url", ""),
                "items": [clean_item]
            }
            
            # 设置目标集合
            if collection_key:
                tree_view_id = self._get_collection_tree_view_id(collection_key)
                if tree_view_id:
                    payload["target"] = tree_view_id
                    logger.info(f"🎯 使用treeViewID: {tree_view_id}")
            
            # headers和session已经在上面定义了
            
            # 保存项目
            response = session.post(f"{self.base_url}/connector/saveItems", json=payload, timeout=30)
            
            if response.status_code not in [200, 201]:
                return {
                    "success": False,
                    "message": f"保存失败，状态码: {response.status_code}"
                }
            
            logger.info("✅ 项目保存成功")
            
            # 🎯 正确的附件处理：调用saveAttachment API保存PDF
            pdf_attachment_success = False
            
            if pdf_url:
                logger.info(f"🔍 发现PDF链接: {pdf_url}")
                
                # 🚀 关键修复：优先使用浏览器预下载的PDF内容
                try:
                    if zotero_item.get('pdf_content'):
                        logger.info("✅ 使用浏览器预下载的PDF内容，跳过HTTP下载")
                        pdf_content = zotero_item['pdf_content']
                    else:
                        logger.info("📥 开始下载PDF内容...")
                        pdf_content = self._download_pdf_content(pdf_url)
                    
                    if pdf_content:
                        # 准备附件元数据
                        import random
                        import string
                        attachment_id = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
                        
                        attachment_metadata = {
                            "id": attachment_id,
                            "url": pdf_url,
                            "contentType": "application/pdf",
                            "parentItemID": clean_item.get("id", ""),  # 使用item的ID
                            "title": "Full Text PDF"
                        }
                        
                        # 调用saveAttachment API
                        attachment_headers = {
                            "Content-Type": "application/pdf",
                            "X-Metadata": json.dumps(attachment_metadata)
                        }
                        
                        attachment_response = session.post(
                            f"{self.base_url}/connector/saveAttachment?sessionID={session_id}",
                            data=pdf_content,
                            headers=attachment_headers,
                            timeout=30
                        )
                        
                        if attachment_response.status_code in [200, 201]:
                            pdf_attachment_success = True
                            logger.info("✅ PDF附件保存成功！")
                        else:
                            logger.warning(f"⚠️ PDF附件保存失败: {attachment_response.status_code}")
                    else:
                        logger.warning("⚠️ PDF内容下载失败")
                        
                except Exception as e:
                    logger.warning(f"⚠️ PDF处理异常: {e}")
                

            
            # 移动到指定集合
            collection_move_success = False
            if collection_key:
                tree_view_id = self._get_collection_tree_view_id(collection_key)
                if tree_view_id:
                    try:
                        update_data = {"sessionID": session_id, "target": tree_view_id}
                        update_response = session.post(f"{self.base_url}/connector/updateSession", json=update_data, timeout=30)
                        if update_response.status_code in [200, 201]:
                            collection_move_success = True
                            logger.info("✅ 成功移动到指定集合")
                    except Exception as e:
                        logger.warning(f"⚠️ 集合移动失败: {e}")
            
            # 构建结果
            result = {
                "success": True,
                "message": "论文已成功保存" + ("，PDF附件已添加" if pdf_attachment_success else ""),
                "details": {
                    "metadata_saved": True,
                    "collection_moved": collection_move_success,
                    "pdf_downloaded": pdf_attachment_success,
                    "pdf_error": None if pdf_attachment_success else "PDF附件保存失败" if pdf_url else None,
                    "pdf_method": "attachment" if pdf_attachment_success else "failed" if pdf_url else "none"
                }
            }
            
            return result
                        
        except Exception as e:
            logger.error(f"❌ 实用方案保存异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "message": f"保存失败: {e}"
            }
    
    def _download_arxiv_pdf(self, arxiv_id: str, title: str) -> Optional[str]:
        """下载arxiv PDF到临时目录"""
        try:
            import tempfile
            import urllib.request
            from urllib.parse import quote
            
            # 创建临时下载目录
            temp_dir = Path(tempfile.gettempdir()) / "zotero_pdfs"
            temp_dir.mkdir(exist_ok=True)
            
            # 生成安全的文件名
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title[:50] if len(safe_title) > 50 else safe_title
            pdf_filename = f"{arxiv_id}_{safe_title}.pdf"
            pdf_path = temp_dir / pdf_filename
            
            # 下载PDF
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            logger.info(f"下载PDF: {pdf_url}")
            
            urllib.request.urlretrieve(pdf_url, pdf_path)
            
            # 验证文件是否下载成功且是PDF
            if pdf_path.exists() and pdf_path.stat().st_size > 1024:  # 至少1KB
                logger.info(f"PDF下载成功: {pdf_path}")
                return str(pdf_path)
            else:
                logger.warning("PDF下载失败或文件太小")
                return None
                
        except Exception as e:
            logger.error(f"下载PDF失败: {e}")
            return None
    
    def _attach_pdf_to_item(self, item_key: str, pdf_path: str, title: str) -> bool:
        """将PDF附加到Zotero条目"""
        try:
            if not Path(pdf_path).exists():
                logger.error(f"PDF文件不存在: {pdf_path}")
                return False
            
            # 准备附件数据
            attachment_data = {
                "itemType": "attachment",
                "parentItem": item_key,
                "linkMode": "imported_file",
                "title": f"{title} - PDF",
                "filename": Path(pdf_path).name,
                "path": pdf_path,
                "contentType": "application/pdf"
            }
            
            # 尝试不同的附件上传端点
            attachment_endpoints = [
                "/connector/attachments",
                "/connector/saveItems",
                "/attachments"
            ]
            
            for endpoint in attachment_endpoints:
                try:
                    # 使用multipart/form-data上传文件
                    import requests
                    files = {
                        'file': (Path(pdf_path).name, open(pdf_path, 'rb'), 'application/pdf')
                    }
                    data = {
                        'data': json.dumps(attachment_data)
                    }
                    
                    response = self.session.post(
                        f"{self.base_url}{endpoint}",
                        files=files,
                        data=data,
                        timeout=60
                    )
                    
                    files['file'][1].close()  # 关闭文件
                    
                    if response.status_code in [200, 201]:
                        logger.info(f"PDF附件上传成功: {endpoint}")
                        return True
                        
                except Exception as e:
                    logger.debug(f"使用端点{endpoint}上传附件失败: {e}")
                    continue
            
            logger.warning("所有附件上传端点都失败了")
            return False
            
        except Exception as e:
            logger.error(f"附件上传失败: {e}")
            return False
    
    def create_collection(self, name: str, parent_key: Optional[str] = None) -> Dict:
        """创建新集合"""
        try:
            if not self.is_running():
                return {
                    "success": False,
                    "message": "Zotero未运行，请启动Zotero桌面应用"
                }
            
            collection_data = {
                "name": name,
                "parentCollection": parent_key if parent_key else False
            }
            
            # 尝试不同的创建端点
            create_endpoints = [
                "/api/users/local/collections",
                "/connector/createCollection", 
                "/api/collections"
            ]
            
            for endpoint in create_endpoints:
                try:
                    response = self.session.post(
                        f"{self.base_url}{endpoint}",
                        json=collection_data,
                        timeout=15
                    )
                    
                    if response.status_code in [200, 201]:
                        try:
                            result = response.json()
                            collection_key = result.get('key', '')
                            logger.info(f"使用端点{endpoint}成功创建集合: {name}")
                            
                            return {
                                "success": True,
                                "message": f"成功创建集合: {name}",
                                "collection_key": collection_key,
                                "collection_name": name
                            }
                        except json.JSONDecodeError:
                            # 即使没有JSON响应，如果状态码正确也认为成功
                            logger.info(f"使用端点{endpoint}创建集合成功（无JSON响应）")
                            return {
                                "success": True,
                                "message": f"成功创建集合: {name}",
                                "collection_key": "",
                                "collection_name": name
                            }
                    
                    elif response.status_code == 404:
                        logger.debug(f"创建端点不存在: {endpoint}")
                        continue
                    else:
                        logger.debug(f"端点{endpoint}返回状态码: {response.status_code}")
                        continue
                        
                except Exception as e:
                    logger.debug(f"使用端点{endpoint}创建失败: {e}")
                    continue
            
            # 如果所有端点都失败了
            return {
                "success": False,
                "message": "所有创建端点都不可用，可能需要更新的Zotero版本或手动在Zotero中创建集合"
            }
                
        except Exception as e:
            logger.error(f"创建Zotero集合失败: {e}")
            return {
                "success": False,
                "message": f"创建集合失败: {e}"
            }

    def _get_collection_tree_view_id(self, collection_key: str) -> Optional[str]:
        """根据collection key获取treeViewID格式"""
        try:
            # 从数据库中查找collection ID
            if not self._zotero_db_path or not self._zotero_db_path.exists():
                return None
                
            import tempfile
            import shutil
            import sqlite3
            
            with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as temp_file:
                shutil.copy2(self._zotero_db_path, temp_file.name)
                temp_db_path = temp_file.name
                
            try:
                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()
                
                # 根据key查找collectionID
                cursor.execute(
                    'SELECT collectionID FROM collections WHERE key = ?', 
                    (collection_key,)
                )
                
                result = cursor.fetchone()
                if result:
                    collection_id = result[0]
                    tree_view_id = f"C{collection_id}"
                    logger.info(f"🎯 转换: {collection_key} → {tree_view_id}")
                    return tree_view_id
                else:
                    logger.warning(f"⚠️ 找不到collection key: {collection_key}")
                    return None
                    
                conn.close()
                
            finally:
                try:
                    Path(temp_db_path).unlink()
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"❌ 获取treeViewID失败: {e}")
            return None
    
    def set_database_cookies(self, database_name: str, cookies: str) -> bool:
        """
        为特定数据库设置cookies
        
        Args:
            database_name: 数据库名称（如"Nature"）
            cookies: cookie字符串
            
        Returns:
            bool: 设置成功返回True
        """
        if not self.extractor_manager:
            logger.error("❌ 提取器管理器不可用")
            return False
        
        return self.extractor_manager.set_database_cookies(database_name, cookies)
    
    def get_supported_databases(self) -> List[Dict]:
        """获取支持的数据库列表"""
        if not self.extractor_manager:
            return [{'name': 'arXiv', 'requires_auth': False, 'has_cookies': False}]
        
        databases = self.extractor_manager.get_supported_databases()
        
        # 添加内置的arXiv支持
        databases.insert(0, {
            'name': 'arXiv',
            'requires_auth': False,
            'has_cookies': False,
            'supported_types': ['preprint']
        })
        
        return databases
    
    def test_database_access(self, database_name: str) -> Dict:
        """测试数据库访问状态"""
        if database_name.lower() == 'arxiv':
            return {
                'database': 'arXiv',
                'status': 'success',
                'message': 'arXiv无需认证，访问正常'
            }
        
        if not self.extractor_manager:
            return {
                'database': database_name,
                'status': 'not_supported',
                'message': '提取器管理器不可用'
            }
        
        return self.extractor_manager.test_database_access(database_name)
    
    def _quick_validate_pdf_link(self, pdf_url: str) -> bool:
        """快速验证PDF链接是否可用"""
        
        if not pdf_url:
            return False
        
        try:
            import requests
            
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/pdf,*/*;q=0.8',
            })
            
            # 使用HEAD请求快速检查，超时5秒
            response = session.head(pdf_url, timeout=5, allow_redirects=True)
            
            # 检查状态码
            if response.status_code == 200:
                # 检查Content-Type（允许OSF的octet-stream）
                content_type = response.headers.get('Content-Type', '').lower()
                if 'pdf' in content_type or content_type == 'application/octet-stream':
                    logger.info(f"🔍 PDF链接验证通过: {response.status_code}, {content_type}")
                    return True
                else:
                    logger.warning(f"⚠️ PDF链接Content-Type异常: {content_type}")
                    return False
            elif response.status_code == 403:
                logger.warning(f"⚠️ PDF链接被403阻止: {pdf_url[:60]}...")
                return False
            elif response.status_code == 404:
                logger.warning(f"⚠️ PDF链接不存在: {pdf_url[:60]}...")
                return False
            else:
                logger.warning(f"⚠️ PDF链接状态异常: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ PDF链接验证超时")
            return False
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ PDF链接连接失败")
            return False
        except Exception as e:
            logger.warning(f"⚠️ PDF链接验证异常: {e}")
            return False

    def _enhance_paper_metadata(self, paper_info: Dict) -> Dict:
        """
        使用提取器管理器增强论文元数据（支持异步浏览器模式）
        
        Args:
            paper_info: 基本论文信息
            
        Returns:
            Dict: 增强后的论文信息
        """
        url = paper_info.get('url', '')
        
        # 🔧 修复：精确检查arXiv，避免误匹配SocArXiv等
        if re.search(r'(?<!soc)(?<!med)(?<!bio)arxiv\.org', url):
            return self._enhance_paper_info_for_arxiv(paper_info)
        
        # 使用提取器管理器处理其他数据库
        if self.extractor_manager:
            logger.info("🔄 使用提取器管理器增强元数据...")
            
            # 🚀 关键修复：支持异步浏览器模式
            try:
                # 检查是否已在事件循环中运行
                try:
                    loop = asyncio.get_running_loop()
                    logger.info("🔄 在现有事件循环中运行异步提取...")
                    # 如果已经在事件循环中，需要使用不同的方法
                    enhanced_metadata = self._run_async_extraction(url)
                except RuntimeError:
                    # 没有运行的事件循环，创建新的
                    logger.info("🔄 创建新事件循环运行异步提取...")
                    enhanced_metadata = asyncio.run(self.extractor_manager.extract_metadata(url))
            except Exception as e:
                logger.error(f"❌ 异步提取失败: {e}")
                enhanced_metadata = {'error': f'异步提取失败: {e}'}
            
            if 'error' not in enhanced_metadata:
                # 合并原始信息和增强信息
                enhanced_info = paper_info.copy()
                enhanced_info.update(enhanced_metadata)
                
                logger.info(f"✅ 元数据增强成功: {enhanced_info.get('title', 'Unknown')}")
                return enhanced_info
            else:
                logger.warning(f"⚠️ 提取器处理失败: {enhanced_metadata['error']}")
                
                # 🔧 网络失败时的智能回退：尝试基于URL的模式提取
                logger.info("🔄 尝试基于URL的离线模式提取...")
                
                try:
                    # 获取通用提取器进行URL模式提取
                    for extractor in self.extractor_manager.extractors:
                        if extractor.__class__.__name__ == 'GenericOpenAccessExtractor':
                            # 检查是否可以处理这个URL
                            if extractor.can_handle(url):
                                logger.info("📍 找到通用提取器，执行URL模式提取")
                                
                                # 应用URL模式提取
                                url_metadata = extractor._extract_from_url_patterns({}, url)
                                
                                # 🔧 新增：尝试PDF链接构造
                                if not url_metadata.get('pdf_url'):
                                    url_metadata = extractor._search_pdf_links_in_html("", url, url_metadata)
                                
                                if url_metadata.get('pdf_url'):
                                    logger.info(f"✅ 离线模式提取成功，找到PDF链接")
                                    
                                    # 🔧 新增：验证PDF链接的实际可用性
                                    pdf_url = url_metadata.get('pdf_url')
                                    pdf_valid = self._quick_validate_pdf_link(pdf_url)
                                    
                                    if pdf_valid:
                                        logger.info(f"✅ PDF链接验证通过")
                                        
                                        # 识别域名信息
                                        domain_info = extractor._identify_domain(url)
                                        
                                        # 构建基础元数据
                                        fallback_info = paper_info.copy()
                                        fallback_info.update(url_metadata)
                                        fallback_info.update({
                                            'itemType': domain_info['type'],
                                            'source': domain_info['source'],
                                            'extractor': f"Generic-{domain_info['source']}",
                                            'url': url
                                        })
                                        
                                        # 增强预印本字段
                                        fallback_info = extractor._enhance_preprint_fields(fallback_info, url)
                                        
                                        logger.info(f"🎯 离线回退成功: {fallback_info.get('repository', 'Unknown')} - PDF链接已验证")
                                        return fallback_info
                                    else:
                                        logger.warning(f"⚠️ PDF链接验证失败，继续回退流程")
                                        # 移除无效的PDF链接，避免误导用户
                                        url_metadata['pdf_url'] = None
                                else:
                                    logger.warning(f"⚠️ 离线模式提取未找到PDF链接")
                                break
                    
                    # 如果没找到合适的提取器或提取失败，返回原始错误
                    logger.warning(f"❌ 离线回退也失败，返回原始错误")
                    return enhanced_metadata
                    
                except Exception as e:
                    logger.error(f"❌ 离线回退过程出错: {e}")
                    return enhanced_metadata
        
        # 如果没有提取器管理器，返回原始信息
        logger.info("ℹ️ 使用基本论文信息")
        return paper_info

    def _run_async_extraction(self, url: str) -> Dict:
        """
        在现有事件循环中运行异步提取的辅助方法
        """
        import concurrent.futures
        import threading
        import asyncio
        
        try:
            # 创建新的事件循环在独立线程中运行
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(
                        self.extractor_manager.extract_metadata(url)
                    )
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result(timeout=180)  # 增加到180秒超时，给浏览器足够时间
                
        except concurrent.futures.TimeoutError:
            logger.error("❌ 浏览器模式超时（超过3分钟）")
            return {'error': '浏览器模式超时，可能是网络问题或反爬虫机制升级'}
        except Exception as e:
            logger.error(f"❌ 线程池执行异常: {e}")
            return {'error': f'线程执行异常: {e}'}

    def _validate_pdf_content(self, pdf_data: bytes, headers: dict, pdf_url: str) -> dict:
        """
        验证下载的PDF内容是否有效和完整
        
        Args:
            pdf_data: PDF文件二进制数据
            headers: HTTP响应头
            pdf_url: PDF下载URL
            
        Returns:
            dict: 验证结果 {"is_valid": bool, "reason": str, "details": dict}
        """
        try:
            pdf_size = len(pdf_data)
            content_type = headers.get('Content-Type', '').lower()
            
            logger.info(f"🔍 PDF验证开始: {pdf_size} bytes, Content-Type: {content_type}")
            
            # 检查1: 基本大小验证
            if pdf_size < 1024:  # 小于1KB肯定有问题
                return {
                    "is_valid": False,
                    "reason": f"文件太小 ({pdf_size} bytes)，可能是错误页面",
                    "details": {"size": pdf_size, "content_preview": pdf_data[:200].decode('utf-8', errors='ignore')[:100]}
                }
            
            # 检查2: Content-Type验证 (🔧 修复：允许OSF的octet-stream格式)
            if content_type and 'pdf' not in content_type:
                # 🔧 特殊处理：application/octet-stream可能是有效PDF（如OSF）
                if content_type != 'application/octet-stream':
                    return {
                        "is_valid": False,
                        "reason": f"Content-Type不是PDF: {content_type}",
                        "details": {"content_type": content_type, "size": pdf_size}
                    }
                else:
                    logger.info(f"🔧 检测到octet-stream类型，将通过PDF魔术字节验证")
            
            # 检查3: PDF魔术字节
            if not pdf_data.startswith(b'%PDF'):
                return {
                    "is_valid": False,
                    "reason": "文件不以PDF魔术字节开头",
                    "details": {"size": pdf_size, "start_bytes": pdf_data[:20].hex()}
                }
            
            # 检查4: HTML内容检测（有些服务器返回HTML页面但伪造PDF头）
            pdf_text = pdf_data[:2048].decode('utf-8', errors='ignore').lower()
            html_indicators = ['<html', '<body', '<div', '<!doctype', '<title>']
            found_html = [indicator for indicator in html_indicators if indicator in pdf_text]
            
            if found_html:
                return {
                    "is_valid": False,
                    "reason": f"文件包含HTML内容，可能是错误页面: {found_html}",
                    "details": {"size": pdf_size, "html_indicators": found_html}
                }
            
            # 检查5: Nature特定的大小验证
            if 'nature.com' in pdf_url.lower():
                if pdf_size < 500000:  # Nature PDF通常至少500KB
                    logger.warning(f"⚠️ Nature PDF大小异常: {pdf_size} bytes (通常应该>500KB)")
                    return {
                        "is_valid": False,
                        "reason": f"Nature PDF大小异常: {pdf_size/1024:.1f}KB (通常应该>500KB)",
                        "details": {"size": pdf_size, "expected_min_size": 500000, "url": pdf_url}
                    }
            
            # 检查6: PDF结构基本验证
            if b'%%EOF' not in pdf_data[-1024:]:  # PDF文件应该以%%EOF结尾
                logger.warning("⚠️ PDF文件可能不完整（缺少EOF标记）")
                return {
                    "is_valid": False,
                    "reason": "PDF文件不完整（缺少结尾标记）",
                    "details": {"size": pdf_size, "has_eof": False}
                }
            
            # 所有检查通过
            logger.info(f"✅ PDF验证通过: {pdf_size} bytes ({pdf_size/1024:.1f}KB)")
            return {
                "is_valid": True,
                "reason": "PDF验证通过",
                "details": {
                    "size": pdf_size,
                    "size_kb": round(pdf_size/1024, 1),
                    "content_type": content_type,
                    "has_pdf_header": True,
                    "has_eof": True
                }
            }
            
        except Exception as e:
            logger.error(f"❌ PDF验证过程异常: {e}")
            return {
                "is_valid": False,
                "reason": f"PDF验证异常: {e}",
                "details": {"exception": str(e)}
            }

    def _analyze_pdf_status(self, pdf_success: bool, pdf_attempts: int, pdf_errors: list) -> dict:
        """
        分析PDF下载和保存状态
        
        Args:
            pdf_success: PDF是否成功
            pdf_attempts: PDF尝试次数  
            pdf_errors: PDF错误列表
            
        Returns:
            dict: PDF状态分析结果
        """
        if pdf_attempts == 0:
            return {
                "status": "none",
                "message": "未发现PDF下载链接",
                "success": False,
                "details": "论文可能不包含可下载的PDF，或需要特殊权限"
            }
        
        if pdf_success:
            return {
                "status": "success", 
                "message": "PDF附件下载并保存成功",
                "success": True,
                "details": f"成功处理 {pdf_attempts} 个PDF附件"
            }
        else:
            error_summary = "; ".join(pdf_errors) if pdf_errors else "未知错误"
            return {
                "status": "failed",
                "message": "PDF下载失败", 
                "success": False,
                "details": error_summary,
                "suggestion": self._get_pdf_error_suggestion(pdf_errors)
            }
    
    def _get_pdf_error_suggestion(self, pdf_errors: list) -> str:
        """根据PDF错误提供解决建议"""
        if not pdf_errors:
            return "请检查网络连接和PDF链接有效性"
        
        error_text = " ".join(pdf_errors).lower()
        
        if "403" in error_text or "认证" in error_text:
            return "请在Claude Desktop中设置有效的数据库认证cookies"
        elif "404" in error_text:
            return "PDF链接可能已失效，请尝试其他下载源"
        elif "html" in error_text:
            return "下载到登录页面，需要更新认证信息"
        else:
            return "请检查网络连接，稍后重试"
    
    def _generate_save_message(self, pdf_status: dict, collection_moved: bool) -> str:
        """
        生成保存结果的用户友好消息
        
        Args:
            pdf_status: PDF状态信息
            collection_moved: 是否移动到指定集合
            
        Returns:
            str: 用户消息
        """
        base_msg = "✅ 论文基本信息已保存到Zotero"
        
        if pdf_status.get("success", False):
            base_msg += "\n✅ PDF附件下载并保存成功"
        elif pdf_status.get("status") == "none":
            base_msg += "\nℹ️ 未发现可下载的PDF链接"
        else:
            base_msg += f"\n⚠️ PDF下载失败: {pdf_status.get('details', '未知原因')}"
            if pdf_status.get("suggestion"):
                base_msg += f"\n💡 建议: {pdf_status['suggestion']}"
        
        if collection_moved:
            base_msg += "\n✅ 已移动到指定集合"
        
        return base_msg
    
    def load_cookies_from_files(self) -> Dict[str, bool]:
        """
        从文件加载所有可用的cookies
        支持多种格式和位置：
        1. ~/.zotlink/cookies.json (推荐位置，多数据库)
        2. 项目根目录/cookies.json (向后兼容)
        3. shared_cookies_*.json (书签同步)
        4. ~/.zotlink/nature_cookies.txt (向后兼容)
        
        Returns:
            Dict[str, bool]: 每个数据库的加载状态
        """
        import os
        from pathlib import Path
        import time
        from datetime import datetime, timezone
        
        results = {}
        # 优先级：用户配置目录 > 项目根目录
        user_config_dir = Path.home() / '.zotlink'
        project_root = Path(__file__).parent.parent
        
        # 确保用户配置目录存在
        user_config_dir.mkdir(exist_ok=True)
        
        logger.info("🔍 正在扫描cookie文件...")
        
        # 1. 优先加载cookies.json（主配置文件）- 优先从用户配置目录加载
        json_config_paths = [
            user_config_dir / "cookies.json",  # 推荐位置
            project_root / "cookies.json"      # 向后兼容
        ]
        
        json_config_file = None
        for path in json_config_paths:
            if path.exists():
                json_config_file = path
                break
        
        if json_config_file:
            logger.info(f"📁 找到主Cookie配置文件: {json_config_file}")
            try:
                with open(json_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                databases = config.get('databases', {})
                loaded_count = 0
                
                for db_key, db_config in databases.items():
                    if db_config.get('status') == 'active' and db_config.get('cookies'):
                        cookies_str = db_config['cookies']
                        cookie_count = db_config.get('cookie_count', len(cookies_str.split(';')))
                        db_name = db_config.get('name', db_key)
                        
                        # 设置到对应数据库
                        success = self.set_database_cookies(db_key, cookies_str)
                        if success:
                            logger.info(f"✅ 从JSON加载 {db_name} cookies成功：{cookie_count}个cookies")
                            loaded_count += 1
                        else:
                            logger.error(f"❌ 设置 {db_name} cookies失败")
                        results[db_key] = success
                    else:
                        logger.info(f"⏸️ {db_config.get('name', db_key)}: 未激活或无cookies")
                        results[db_key] = False
                
                if loaded_count > 0:
                    logger.info(f"🎯 成功加载 {loaded_count} 个数据库的cookies")
                    return results
                else:
                    logger.warning("⚠️ cookies.json中没有激活的数据库cookies")
                    
            except Exception as e:
                logger.error(f"❌ 读取cookies.json失败：{e}")
                results['json_config'] = False
        
        # 2. 兼容性支持：检查nature_cookies.txt文件 - 优先从用户配置目录加载
        txt_cookie_paths = [
            user_config_dir / "nature_cookies.txt",  # 推荐位置
            project_root / "nature_cookies.txt"      # 向后兼容
        ]
        
        txt_cookie_file = None
        for path in txt_cookie_paths:
            if path.exists():
                txt_cookie_file = path
                break
                
        if txt_cookie_file:
            logger.info(f"📁 找到兼容性TXT文件: {txt_cookie_file}")
            try:
                with open(txt_cookie_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                # 过滤注释和空行
                lines = [line.strip() for line in content.split('\n') 
                        if line.strip() and not line.strip().startswith('#')]
                
                if lines:
                    cookies_str = ' '.join(lines).strip()
                    cookie_count = len(cookies_str.split(';'))
                    
                    # 设置到Nature数据库
                    success = self.set_database_cookies('nature', cookies_str)
                    if success:
                        logger.info(f"✅ 从TXT文件加载Nature cookies成功：{cookie_count}个cookies")
                        logger.warning("💡 建议迁移到cookies.json格式以支持多数据库")
                    else:
                        logger.error("❌ 设置Nature TXT cookies失败")
                    results['nature_txt'] = success
                else:
                    logger.warning("⚠️ nature_cookies.txt文件为空或只包含注释")
                    results['nature_txt'] = False
                    
            except Exception as e:
                logger.error(f"❌ 读取nature_cookies.txt失败：{e}")
                results['nature_txt'] = False
        
        # 3. 查找所有shared_cookies_*.json文件（书签同步格式）
        cookie_files = list(project_root.glob("shared_cookies_*.json"))
        if not cookie_files:
            if not results:
                logger.info("📄 没有找到任何cookie文件")
            return results
        
        logger.info(f"📁 找到 {len(cookie_files)} 个cookie文件")
        
        for file_path in cookie_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)
                
                site_name = cookie_data.get('siteName', 'Unknown')
                cookies = cookie_data.get('cookies', '')
                timestamp = cookie_data.get('timestamp', '')
                cookies_count = cookie_data.get('cookies_count', 0)
                
                # 检查文件是否过期（24小时）
                last_updated = cookie_data.get('last_updated', 0)
                if time.time() - last_updated > 24 * 3600:
                    logger.warning(f"⚠️ {site_name} cookies已过期（{timestamp}）")
                    results[site_name] = False
                    continue
                
                # 根据站点名映射到数据库名
                database_name = self._map_site_to_database(site_name)
                if database_name:
                    success = self.set_database_cookies(database_name, cookies)
                    if success:
                        logger.info(f"✅ 从文件加载 {site_name} cookies成功：{cookies_count}个cookies（{timestamp}）")
                    else:
                        logger.error(f"❌ 设置 {site_name} cookies失败")
                    results[site_name] = success
                else:
                    logger.warning(f"⚠️ 未知站点：{site_name}")
                    results[site_name] = False
                    
            except Exception as e:
                logger.error(f"❌ 读取cookie文件 {file_path} 失败：{e}")
                results[file_path.stem] = False
        
        return results
    
    def _map_site_to_database(self, site_name: str) -> str:
        """将站点名映射到数据库名"""
        mapping = {
            'www.nature.com': 'nature',
            'nature.com': 'nature', 
            'www.science.org': 'science',
            'science.org': 'science',
            'ieeexplore.ieee.org': 'ieee',
            'link.springer.com': 'springer'
        }
        return mapping.get(site_name.lower(), '')
    
    def update_database_cookies(self, database_key: str, cookies_str: str) -> bool:
        """
        更新指定数据库的cookies到cookies.json文件
        
        Args:
            database_key: 数据库标识 (如 'nature', 'science')
            cookies_str: Cookie字符串
            
        Returns:
            bool: 更新是否成功
        """
        import json
        from pathlib import Path
        from datetime import datetime, timezone
        
        # 优先级：用户配置目录 > 项目根目录
        user_config_dir = Path.home() / '.zotlink'
        project_root = Path(__file__).parent.parent
        
        json_config_paths = [
            user_config_dir / "cookies.json",  # 推荐位置
            project_root / "cookies.json"      # 向后兼容
        ]
        
        json_config_file = None
        for path in json_config_paths:
            if path.exists():
                json_config_file = path
                break
        
        # 如果都不存在，使用推荐位置创建新文件
        if not json_config_file:
            user_config_dir.mkdir(exist_ok=True)
            json_config_file = user_config_dir / "cookies.json"
        
        try:
            # 读取现有配置
            if json_config_file.exists():
                with open(json_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                logger.error("❌ cookies.json文件不存在")
                return False
            
            # 检查数据库是否存在
            if database_key not in config.get('databases', {}):
                logger.error(f"❌ 未知数据库: {database_key}")
                return False
            
            # 更新Cookie信息
            current_time = datetime.now(timezone.utc).isoformat()
            cookie_count = len(cookies_str.split(';')) if cookies_str else 0
            
            config['last_updated'] = current_time
            config['databases'][database_key].update({
                'cookies': cookies_str,
                'last_updated': current_time,
                'cookie_count': cookie_count,
                'status': 'active' if cookies_str else 'inactive'
            })
            
            # 保存更新的配置
            with open(json_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # 同时设置到ExtractorManager
            success = self.set_database_cookies(database_key, cookies_str)
            
            db_name = config['databases'][database_key].get('name', database_key)
            if success:
                logger.info(f"✅ 更新 {db_name} cookies成功：{cookie_count}个cookies")
            else:
                logger.error(f"❌ 设置 {db_name} cookies失败")
                
            return success
            
        except Exception as e:
            logger.error(f"❌ 更新数据库cookies失败：{e}")
            return False
    
    def get_databases_status(self) -> Dict[str, Dict]:
        """
        获取所有数据库的状态信息
        
        Returns:
            Dict[str, Dict]: 数据库状态信息
        """
        import json
        from pathlib import Path
        
        # 优先级：用户配置目录 > 项目根目录
        user_config_dir = Path.home() / '.zotlink'
        project_root = Path(__file__).parent.parent
        
        json_config_paths = [
            user_config_dir / "cookies.json",  # 推荐位置
            project_root / "cookies.json"      # 向后兼容
        ]
        
        json_config_file = None
        for path in json_config_paths:
            if path.exists():
                json_config_file = path
                break
        
        # 如果都不存在，使用推荐位置创建新文件
        if not json_config_file:
            user_config_dir.mkdir(exist_ok=True)
            json_config_file = user_config_dir / "cookies.json"
        
        try:
            if not json_config_file.exists():
                return {}
                
            with open(json_config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            databases = config.get('databases', {})
            status_info = {}
            
            for db_key, db_config in databases.items():
                status_info[db_key] = {
                    'name': db_config.get('name', db_key),
                    'status': db_config.get('status', 'inactive'),
                    'cookie_count': db_config.get('cookie_count', 0),
                    'last_updated': db_config.get('last_updated'),
                    'domains': db_config.get('domains', []),
                    'description': db_config.get('description', ''),
                    'login_url': db_config.get('login_url', ''),
                    'test_url': db_config.get('test_url', '')
                }
            
            return status_info
            
        except Exception as e:
            logger.error(f"❌ 读取数据库状态失败：{e}")
            return {}


def test_zotero_connection():
    """测试Zotero连接"""
    print("🧪 测试Zotero连接...")
    
    connector = ZoteroConnector()
    
    if connector.is_running():
        version = connector.get_version()
        if version:
            print(f"✅ Zotero连接成功，版本: {version}")
            
            # 测试集合获取
            collections = connector.get_zotero_collections()
            print(f"📚 找到 {len(collections.get('collections', []))} 个集合")
        else:
            print("⚠️ Zotero连接成功，但无法获取版本信息")
    else:
        print("❌ Zotero未运行或连接失败")


# 在ZoteroConnector类中添加新方法（这里是文件末尾，需要找到类的正确位置）
# 注意：这些方法应该添加到ZoteroConnector类内部

if __name__ == "__main__":
    test_zotero_connection() 