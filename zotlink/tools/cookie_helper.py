#!/usr/bin/env python3
"""
Cookie获取辅助工具
帮助用户从浏览器获取Nature网站的cookies
"""
import sys
import os
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.downloader import LightweightNatureDownloader

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def show_manual_guide():
    """显示手动获取cookies的指南"""
    downloader = LightweightNatureDownloader()
    guide = downloader.get_cookies_from_browser_manual()
    print(guide)


def test_cookies_from_input():
    """测试用户输入的cookies"""
    print("🧪 测试Cookies功能")
    print("-" * 50)
    
    print("请先登录Nature网站，然后按照以下步骤获取cookies：")
    print()
    print("方法1: Chrome开发者工具")
    print("1. 在Nature网站按F12打开开发者工具")
    print("2. 进入Network标签，刷新页面")
    print("3. 选择任意请求，在Request Headers中找到Cookie字段")
    print("4. 复制整个Cookie字符串")
    print()
    print("方法2: Application标签")
    print("1. 在Nature网站按F12打开开发者工具")
    print("2. 进入Application标签 > Storage > Cookies > https://www.nature.com")
    print("3. 选择所有cookies并复制为JSON格式")
    print()
    
    cookies_input = input("请粘贴你的cookies（JSON格式或cookie字符串）:\n")
    
    if not cookies_input.strip():
        print("❌ 未输入cookies")
        return
    
    print(f"\n📝 已接收cookies，长度: {len(cookies_input)} 字符")
    print("🔄 正在处理...")
    
    try:
        # 尝试创建下载器
        downloader = LightweightNatureDownloader(cookies_input.strip())
        
        print("\n🧪 测试登录状态...")
        status = downloader.test_login_status()
        
        print(f"📊 测试结果:")
        print(f"  登录状态: {'✅ 已登录' if status.get('logged_in') else '❌ 未登录'}")
        print(f"  状态码: {status.get('status_code', 'N/A')}")
        print(f"  Cookies数量: {status.get('cookies_count', 0)}")
        
        if status.get("logged_in"):
            print("\n🎉 Cookies有效！你可以使用以下命令启动服务器：")
            print("python3 run_server.py")
            
            # 保存cookies到文件
            save_cookies = input("\n是否保存cookies到文件以便下次使用？(y/n): ").strip().lower()
            if save_cookies == 'y':
                cookies_json = downloader.export_cookies()
                with open('saved_cookies.json', 'w') as f:
                    f.write(cookies_json)
                print("✅ Cookies已保存到 saved_cookies.json")
                
        else:
            print("\n❌ Cookies无效或已过期，请检查：")
            print("1. 是否已在浏览器中登录Nature网站")
            print("2. 复制的cookies是否完整")
            print("3. cookies是否已过期")
            
            if status.get("error"):
                print(f"错误详情: {status['error']}")
    
    except Exception as e:
        print(f"❌ 测试cookies时出错: {e}")
        print("请检查cookies格式是否正确")


def load_saved_cookies():
    """加载保存的cookies"""
    cookie_files = ['saved_cookies.json', '.cookies.json', 'cookies.json']
    
    for cookie_file in cookie_files:
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, 'r') as f:
                    cookies = f.read()
                
                print(f"📁 从 {cookie_file} 加载cookies...")
                downloader = LightweightNatureDownloader(cookies)
                status = downloader.test_login_status()
                
                print(f"登录状态: {'✅ 已登录' if status.get('logged_in') else '❌ 未登录'}")
                
                if status.get("logged_in"):
                    print("🎉 可以使用保存的cookies！")
                    return True
                else:
                    print("⚠️ 保存的cookies已过期")
                    
            except Exception as e:
                print(f"❌ 加载 {cookie_file} 失败: {e}")
    
    return False


def auto_load_from_browser():
    """尝试从浏览器自动加载cookies"""
    print("🔄 尝试从浏览器自动读取cookies...")
    
    try:
        downloader = LightweightNatureDownloader()
        
        # 尝试Chrome
        print("尝试从Chrome读取...")
        success = downloader.load_cookies_from_browser("chrome")
        
        if success:
            status = downloader.test_login_status()
            if status.get("logged_in"):
                print("✅ 成功从Chrome读取cookies！")
                return True
            else:
                print("⚠️ 从Chrome读取的cookies无效")
        else:
            print("❌ 从Chrome读取cookies失败")
            print("原因可能是：")
            print("1. Chrome浏览器正在运行（请关闭后重试）")
            print("2. 未安装pycryptodome库（pip install pycryptodome）")
            print("3. 未在Chrome中登录Nature网站")
            
    except Exception as e:
        print(f"❌ 自动读取失败: {e}")
    
    return False


def quick_demo():
    """快速演示"""
    print("🚀 Nature Scholar Tool - Cookie辅助工具")
    print("=" * 60)
    
    print("选择获取cookies的方式：")
    print("1. 📋 手动获取cookies（查看详细指南）")
    print("2. 🧪 测试你的cookies")
    print("3. 📁 使用保存的cookies")
    print("4. 🔄 从浏览器自动读取")
    print("5. ❓ 查看完整指南")
    
    choice = input("\n请选择 (1-5): ").strip()
    
    if choice == "1":
        show_manual_guide()
    elif choice == "2":
        test_cookies_from_input()
    elif choice == "3":
        if not load_saved_cookies():
            print("未找到有效的保存cookies，请选择其他方式")
    elif choice == "4":
        if not auto_load_from_browser():
            print("自动读取失败，建议使用手动方式")
    elif choice == "5":
        show_manual_guide()
        print("\n" + "="*50)
        print("💡 提示：获取cookies后，可以：")
        print("1. 运行 python3 cookie_helper.py 测试cookies")
        print("2. 运行 python3 run_server.py 启动服务器")
        print("3. 在MCP中使用 set_cookies 工具")
    else:
        print("无效选择")


if __name__ == "__main__":
    try:
        quick_demo()
    except KeyboardInterrupt:
        print("\n\n👋 再见！")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")
        print("请检查环境配置或联系开发者") 