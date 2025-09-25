# ZotLink Extractors
# 不同学术数据库的元数据提取器

from .base_extractor import BaseExtractor
from .nature_extractor import NatureExtractor  
from .extractor_manager import ExtractorManager

__all__ = ["BaseExtractor", "NatureExtractor", "ExtractorManager"]
