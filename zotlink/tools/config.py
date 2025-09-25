"""
Nature Scholar Tool 配置文件
轻量级版本 - 基于requests + cookies
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 下载设置
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", os.path.expanduser("~/Downloads/Nature_Papers"))

# 日志设置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Nature网站配置
NATURE_BASE_URL = "https://www.nature.com"
SEARCH_URL_TEMPLATE = f"{NATURE_BASE_URL}/search?q={{query}}"

# 用户代理配置
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
]

# 请求配置
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2

# 下载限制
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_DELAY = 2  # 秒

# 搜索配置
MAX_SEARCH_RESULTS = 50
DEFAULT_SEARCH_RESULTS = 10

# Cookie配置
COOKIE_FILE_PATHS = [
    'saved_cookies.json', 
    '.cookies.json', 
    'cookies.json'
]

# Chrome数据库路径（用于自动读取cookies）
CHROME_COOKIES_PATH = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Default/Cookies"
) 