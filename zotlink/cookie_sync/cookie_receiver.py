#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cookie接收服务器"""

import json
import logging
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from queue import Queue, Empty
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class CookieData:
    """Cookie数据结构"""
    
    def __init__(self, data: Dict):
        self.site = data.get('site', '')
        self.site_name = data.get('siteName', '')
        self.cookies = data.get('cookies', '')
        self.url = data.get('url', '')
        self.timestamp = data.get('timestamp', datetime.now().isoformat())
        self.user_agent = data.get('userAgent', '')
        self.raw_data = data
    
    def is_valid(self) -> bool:
        """验证cookie数据的有效性"""
        return bool(self.site and self.cookies and self.site_name)
    
    def __repr__(self):
        return f"CookieData(site={self.site}, cookies_count={len(self.cookies.split(';')) if self.cookies else 0})"

class CookieRequestHandler(BaseHTTPRequestHandler):
    """处理Cookie推送请求"""
    
    def __init__(self, *args, cookie_queue: Queue = None, **kwargs):
        self.cookie_queue = cookie_queue
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """覆盖默认日志以使用我们的logger"""
        logger.debug(f"HTTP: {format % args}")
    
    def do_GET(self):
        """处理GET请求 - 用于健康检查"""
        if self.path == '/health':
            self._send_json_response(200, {"status": "ok", "service": "ZotLink Cookie Receiver"})
        elif self.path == '/':
            self._send_html_response()
        else:
            self._send_json_response(404, {"error": "Not found"})
    
    def do_POST(self):
        """处理POST请求 - 接收cookies"""
        if self.path == '/cookies':
            self._handle_cookie_push()
        else:
            self._send_json_response(404, {"error": "Endpoint not found"})
    
    def do_OPTIONS(self):
        """处理OPTIONS请求 - 支持CORS"""
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()
    
    def _handle_cookie_push(self):
        """处理cookie推送"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_response(400, {"error": "Empty request body"})
                return
            
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            cookie_data = CookieData(data)
            
            if not cookie_data.is_valid():
                self._send_json_response(400, {"error": "Invalid cookie data"})
                return
            
            if self.cookie_queue:
                self.cookie_queue.put(cookie_data)
                logger.info(f"📥 接收到cookies: {cookie_data.site_name}")
            
            self._send_json_response(200, {
                "status": "success",
                "message": f"{cookie_data.site_name}认证信息已接收",
                "timestamp": datetime.now().isoformat()
            })
            
        except json.JSONDecodeError:
            self._send_json_response(400, {"error": "Invalid JSON format"})
        except Exception as e:
            logger.error(f"❌ 处理cookie推送时出错: {e}")
            self._send_json_response(500, {"error": "Internal server error"})
    
    def _send_json_response(self, status_code: int, data: Dict):
        """发送JSON响应"""
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        
        response_json = json.dumps(data, ensure_ascii=False, indent=2)
        self.wfile.write(response_json.encode('utf-8'))
    
    def _send_html_response(self):
        """发送HTML状态页面"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ZotLink Cookie接收服务</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; margin: 50px; }}
                .status {{ color: #4CAF50; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>🔗 ZotLink Cookie接收服务</h1>
            <p class="status">✅ 服务正在运行</p>
            <p>启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </body>
        </html>
        """
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def _send_cors_headers(self):
        """发送CORS头"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Access-Control-Max-Age', '3600')

class CookieReceiver:
    """Cookie接收服务器管理器"""
    
    def __init__(self, port: int = 23120):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.cookie_queue = Queue()
        self.running = False
    
    def start(self):
        """启动接收服务器"""
        if self.running:
            logger.warning("⚠️ Cookie接收服务器已在运行")
            return
        
        try:
            def handler_factory(*args, **kwargs):
                return CookieRequestHandler(*args, cookie_queue=self.cookie_queue, **kwargs)
            
            self.server = HTTPServer(('localhost', self.port), handler_factory)
            
            self.server_thread = threading.Thread(
                target=self._run_server, 
                daemon=True,
                name="CookieReceiver"
            )
            self.server_thread.start()
            
            self.running = True
            logger.info(f"🌐 Cookie接收服务启动成功: http://localhost:{self.port}")
            
        except OSError as e:
            if e.errno == 48:
                logger.error(f"❌ 端口 {self.port} 已被占用")
            else:
                logger.error(f"❌ 启动Cookie接收服务失败: {e}")
        except Exception as e:
            logger.error(f"❌ 启动Cookie接收服务时出现异常: {e}")
    
    def _run_server(self):
        """运行服务器主循环"""
        try:
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"❌ Cookie接收服务器运行异常: {e}")
        finally:
            self.running = False
    
    def stop(self):
        """停止接收服务器"""
        if not self.running:
            return
        
        self.running = False
        
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("🛑 Cookie接收服务器已停止")
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2)
    
    def has_new_cookies(self) -> bool:
        """检查是否有新的cookies"""
        return not self.cookie_queue.empty()
    
    def get_latest_cookies(self, timeout: float = 0.1) -> Optional[CookieData]:
        """获取最新的cookies数据"""
        try:
            return self.cookie_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def get_all_pending_cookies(self):
        """获取所有待处理的cookies"""
        cookies = []
        while not self.cookie_queue.empty():
            try:
                cookies.append(self.cookie_queue.get_nowait())
            except Empty:
                break
        return cookies
    
    def is_running(self) -> bool:
        """检查服务器是否在运行"""
        return self.running and self.server is not None
    
    def get_status(self) -> Dict:
        """获取服务器状态信息"""
        return {
            "running": self.is_running(),
            "port": self.port,
            "url": f"http://localhost:{self.port}",
            "pending_cookies": self.cookie_queue.qsize(),
            "thread_alive": self.server_thread.is_alive() if self.server_thread else False
        }
