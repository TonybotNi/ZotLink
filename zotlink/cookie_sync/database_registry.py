#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可扩展的学术数据库注册中心"""

import re
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """数据库配置信息"""
    name: str
    identifier: str
    domains: List[str]
    cookie_patterns: List[str]
    login_url: str
    test_url: str
    description: str
    cookie_expiry_hours: int = 24

class DatabaseRegistry:
    """学术数据库注册中心"""
    
    def __init__(self):
        self.databases: Dict[str, DatabaseConfig] = {}
        self.cookie_status: Dict[str, Dict] = {}
        self._register_default_databases()
    
    def _register_default_databases(self):
        """注册默认支持的数据库"""
        
        # Nature系列
        self.register_database(DatabaseConfig(
            name="Nature",
            identifier="nature",
            domains=["nature.com", "www.nature.com"],
            cookie_patterns=[
                "session*", "auth*", "token*", "login*",
                "user*", "account*", "JSESSIONID*",
                "remember*", "csrf*"
            ],
            login_url="https://idp.nature.com/login/",
            test_url="https://www.nature.com/articles",
            description="Nature系列期刊和数据库"
        ))
        
        # Science系列  
        self.register_database(DatabaseConfig(
            name="Science",
            identifier="science",
            domains=["science.org", "www.science.org", "sciencemag.org"],
            cookie_patterns=[
                "session*", "auth*", "token*", "user*",
                "login*", "remember*", "csrf*"
            ],
            login_url="https://www.science.org/action/ssostart",
            test_url="https://www.science.org/toc/science/current",
            description="Science期刊和相关出版物"
        ))
        
        logger.info(f"✅ 已注册 {len(self.databases)} 个默认数据库")
    
    def register_database(self, config: DatabaseConfig):
        """注册新的数据库"""
        self.databases[config.identifier] = config
        
        # 初始化cookie状态
        self.cookie_status[config.identifier] = {
            "has_cookies": False,
            "last_updated": None,
            "expires_at": None,
            "cookie_count": 0,
            "status": "未配置"
        }
        
        logger.info(f"📝 已注册数据库: {config.name} ({config.identifier})")
    
    def get_database_by_domain(self, domain: str) -> Optional[DatabaseConfig]:
        """根据域名获取数据库配置"""
        domain = domain.lower().replace('www.', '')
        
        for db_config in self.databases.values():
            for db_domain in db_config.domains:
                clean_domain = db_domain.lower().replace('www.', '')
                if domain == clean_domain or domain.endswith('.' + clean_domain):
                    return db_config
        return None
    
    def get_database_by_identifier(self, identifier: str) -> Optional[DatabaseConfig]:
        """根据标识符获取数据库配置"""
        return self.databases.get(identifier.lower())
    
    def extract_cookies_for_database(self, identifier: str, raw_cookies: str) -> str:
        """为指定数据库提取重要cookies"""
        db_config = self.get_database_by_identifier(identifier)
        if not db_config:
            return raw_cookies
        
        if not raw_cookies:
            return ""
            
        cookies = []
        cookie_list = [c.strip() for c in raw_cookies.split(';') if c.strip()]
        
        for cookie in cookie_list:
            cookie_name = cookie.split('=')[0].strip().lower()
            
            # 检查是否匹配任何模式
            for pattern in db_config.cookie_patterns:
                pattern_lower = pattern.lower().replace('*', '')
                if pattern_lower in cookie_name:
                    cookies.append(cookie.strip())
                    break
        
        return '; '.join(cookies)
    
    def update_cookie_status(self, identifier: str, cookies: str):
        """更新数据库的cookie状态"""
        if identifier not in self.cookie_status:
            return
        
        now = datetime.now()
        db_config = self.databases.get(identifier)
        
        if cookies and cookies.strip():
            expires_at = now + timedelta(hours=db_config.cookie_expiry_hours if db_config else 24)
            cookie_count = len([c for c in cookies.split(';') if c.strip()])
            
            self.cookie_status[identifier].update({
                "has_cookies": True,
                "last_updated": now,
                "expires_at": expires_at,
                "cookie_count": cookie_count,
                "status": "已配置"
            })
        else:
            self.cookie_status[identifier].update({
                "has_cookies": False,
                "last_updated": now,
                "expires_at": None,
                "cookie_count": 0,
                "status": "配置失败"
            })
    
    def get_all_databases(self) -> Dict[str, DatabaseConfig]:
        """获取所有注册的数据库"""
        return self.databases.copy()
    
    def get_database_status(self, identifier: str) -> Dict:
        """获取数据库的详细状态"""
        db_config = self.get_database_by_identifier(identifier)
        status = self.cookie_status.get(identifier, {})
        
        if not db_config:
            return {"error": f"数据库 {identifier} 未找到"}
        
        # 检查cookies是否过期
        if status.get("expires_at") and datetime.now() > status["expires_at"]:
            status["status"] = "已过期"
            status["has_cookies"] = False
        
        return {
            "name": db_config.name,
            "identifier": db_config.identifier,
            "description": db_config.description,
            "domains": db_config.domains,
            "login_url": db_config.login_url,
            **status
        }
    
    def get_all_status(self) -> Dict[str, Dict]:
        """获取所有数据库的状态"""
        return {
            identifier: self.get_database_status(identifier)
            for identifier in self.databases.keys()
        }
    
    def is_cookies_valid(self, identifier: str) -> bool:
        """检查指定数据库的cookies是否有效"""
        status = self.cookie_status.get(identifier, {})
        
        if not status.get("has_cookies"):
            return False
        
        expires_at = status.get("expires_at")
        if expires_at and datetime.now() > expires_at:
            return False
        
        return True
    
    def get_expired_databases(self) -> List[str]:
        """获取cookies已过期的数据库列表"""
        expired = []
        for identifier in self.databases.keys():
            if not self.is_cookies_valid(identifier):
                status = self.cookie_status.get(identifier, {})
                if status.get("last_updated"):
                    expired.append(identifier)
        return expired
