#!/usr/bin/env python3
"""
浏览器驱动安装脚本
安装Playwright并下载Chromium浏览器
"""

import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def install_playwright():
    """安装Playwright包"""
    try:
        logger.info("正在安装Playwright...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright>=1.40.0"])
        logger.info("Playwright安装成功")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Playwright安装失败: {e}")
        return False

def install_browsers():
    """安装浏览器"""
    try:
        logger.info("正在安装Chromium浏览器...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        logger.info("Chromium安装成功")
        
        logger.info("安装浏览器依赖...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install-deps", "chromium"])
        logger.info("浏览器依赖安装成功")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"浏览器安装失败: {e}")
        return False

def main():
    """主安装流程"""
    print("🚀 开始安装浏览器驱动组件...")
    
    # 安装Playwright
    if not install_playwright():
        print("❌ 安装失败")
        sys.exit(1)
    
    # 安装浏览器
    if not install_browsers():
        print("❌ 安装失败")
        sys.exit(1)
    
    print("✅ 浏览器驱动安装完成!")
    print("现在可以使用浏览器模式处理bioRxiv、OSF等反爬虫网站了")

if __name__ == "__main__":
    main() 