#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cookie同步管理器"""

import logging
import threading
import time
from typing import Dict, Optional, Callable, List
from datetime import datetime

from .cookie_receiver import CookieReceiver, CookieData
from .database_registry import DatabaseRegistry

logger = logging.getLogger(__name__)

class CookieSyncManager:
    """Cookie自动同步管理器"""
    
    def __init__(self, zotero_connector=None, port: int = 23120):
        self.zotero_connector = zotero_connector
        self.cookie_receiver = CookieReceiver(port=port)
        self.database_registry = DatabaseRegistry()
        
        # 同步状态
        self.sync_enabled = True
        self.sync_thread: Optional[threading.Thread] = None
        self.running = False
        
        # 统计信息
        self.stats = {
            "total_received": 0,
            "successfully_applied": 0,
            "failed_applications": 0,
            "last_sync": None,
            "start_time": datetime.now()
        }
        
        logger.info("🔗 Cookie同步管理器已初始化")
    
    def start(self):
        """启动同步服务"""
        if self.running:
            logger.warning("⚠️ Cookie同步服务已在运行")
            return
        
        # 启动HTTP接收服务
        self.cookie_receiver.start()
        
        # 启动同步监控线程
        self.sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name="CookieSync"
        )
        self.sync_thread.start()
        
        self.running = True
        logger.info("🚀 Cookie自动同步服务已启动")
    
    def stop(self):
        """停止同步服务"""
        if not self.running:
            return
        
        self.running = False
        self.sync_enabled = False
        
        # 停止HTTP接收服务
        self.cookie_receiver.stop()
        
        # 等待同步线程结束
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=2)
        
        logger.info("🛑 Cookie同步服务已停止")
    
    def _sync_loop(self):
        """同步主循环"""
        logger.info("🔄 Cookie同步监控开始运行")
        
        while self.running and self.sync_enabled:
            try:
                # 检查是否有新的cookies
                if self.cookie_receiver.has_new_cookies():
                    self._process_pending_cookies()
                
                # 短暂休眠避免过度占用CPU
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ 同步循环异常: {e}")
                time.sleep(1)
        
        logger.info("🔄 Cookie同步监控已停止")
    
    def _process_pending_cookies(self):
        """处理所有待处理的cookies"""
        cookies_batch = self.cookie_receiver.get_all_pending_cookies()
        
        for cookie_data in cookies_batch:
            self._apply_single_cookie(cookie_data)
    
    def _apply_single_cookie(self, cookie_data: CookieData):
        """应用单个cookie数据"""
        try:
            self.stats["total_received"] += 1
            
            # 根据域名查找数据库配置
            db_config = self.database_registry.get_database_by_domain(cookie_data.site)
            
            if not db_config:
                logger.warning(f"⚠️ 未找到 {cookie_data.site} 的数据库配置")
                return
            
            # 提取重要cookies
            important_cookies = self.database_registry.extract_cookies_for_database(
                db_config.identifier, cookie_data.cookies
            )
            
            if not important_cookies:
                logger.warning(f"⚠️ 未从 {cookie_data.site_name} 中提取到有效cookies")
                self.stats["failed_applications"] += 1
                return
            
            # 应用到ZoteroConnector
            if self.zotero_connector:
                success = self.zotero_connector.set_database_cookies(
                    db_config.identifier, important_cookies
                )
                
                if success:
                    # 更新数据库状态
                    self.database_registry.update_cookie_status(
                        db_config.identifier, important_cookies
                    )
                    
                    self.stats["successfully_applied"] += 1
                    self.stats["last_sync"] = datetime.now()
                    
                    logger.info(f"✅ 自动应用{db_config.name}认证信息成功")
                else:
                    logger.error(f"❌ 应用{db_config.name}认证信息失败")
                    self.stats["failed_applications"] += 1
            else:
                logger.warning("⚠️ ZoteroConnector未设置，无法应用cookies")
                self.stats["failed_applications"] += 1
                
        except Exception as e:
            logger.error(f"❌ 应用cookie时出现异常: {e}")
            self.stats["failed_applications"] += 1
    
    def set_zotero_connector(self, connector):
        """设置ZoteroConnector实例"""
        self.zotero_connector = connector
        logger.info("🔗 ZoteroConnector已设置到同步管理器")
    
    def get_receiver_status(self) -> Dict:
        """获取接收服务状态"""
        return self.cookie_receiver.get_status()
    
    def get_database_status(self) -> Dict:
        """获取所有数据库状态"""
        return self.database_registry.get_all_status()
    
    def get_sync_stats(self) -> Dict:
        """获取同步统计信息"""
        uptime = datetime.now() - self.stats["start_time"]
        
        return {
            **self.stats,
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_formatted": str(uptime).split('.')[0],
            "success_rate": (
                self.stats["successfully_applied"] / max(self.stats["total_received"], 1) * 100
            ),
            "receiver_running": self.cookie_receiver.is_running(),
            "sync_enabled": self.sync_enabled,
            "service_running": self.running
        }
    
    def get_comprehensive_status(self) -> Dict:
        """获取完整的服务状态"""
        return {
            "sync_manager": {
                "running": self.running,
                "sync_enabled": self.sync_enabled
            },
            "receiver": self.get_receiver_status(),
            "databases": self.get_database_status(),
            "statistics": self.get_sync_stats()
        }
    
    def get_expired_databases(self) -> List[str]:
        """获取cookies已过期的数据库"""
        return self.database_registry.get_expired_databases()
    
    def is_database_authenticated(self, identifier: str) -> bool:
        """检查指定数据库是否已认证"""
        return self.database_registry.is_cookies_valid(identifier)
    
    def get_authentication_guide(self, identifier: str) -> Dict:
        """获取数据库的认证指南"""
        db_config = self.database_registry.get_database_by_identifier(identifier)
        status = self.database_registry.get_database_status(identifier)
        
        if not db_config:
            return {"error": f"数据库 {identifier} 未找到"}
        
        guide = {
            "database": db_config.name,
            "status": status.get("status", "未知"),
            "login_url": db_config.login_url,
            "steps": [
                f"1. 访问 {db_config.name} 登录页面",
                "2. 使用您的机构或个人账户登录",
                "3. 登录成功后点击 ZotLink 书签",
                "4. 等待认证信息自动同步完成"
            ],
            "bookmark_info": {
                "service_url": f"http://localhost:{self.cookie_receiver.port}",
                "status": "运行中" if self.cookie_receiver.is_running() else "未运行"
            }
        }
        
        if status.get("has_cookies"):
            expires_at = status.get("expires_at")
            if expires_at:
                guide["current_status"] = f"已认证，有效期至 {expires_at.strftime('%Y-%m-%d %H:%M')}"
            else:
                guide["current_status"] = "已认证"
        
        return guide
