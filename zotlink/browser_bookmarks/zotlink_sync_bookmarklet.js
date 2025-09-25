javascript:(function(){
    // ZotLink Cookie同步书签 v1.0
    
    // 配置
    const ZOTLINK_SERVICE_URL = 'http://localhost:23120';
    const NOTIFICATION_DURATION = 4000;
    
    // 支持的数据库配置
    const DATABASE_CONFIGS = {
        'nature.com': {
            name: 'Nature',
            identifier: 'nature',
            patterns: ['session', 'auth', 'token', 'login', 'user', 'account', 'JSESSIONID', 'remember', 'csrf']
        },
        'science.org': {
            name: 'Science', 
            identifier: 'science',
            patterns: ['session', 'auth', 'token', 'user', 'login', 'remember', 'csrf']
        },
        'sciencemag.org': {
            name: 'Science',
            identifier: 'science', 
            patterns: ['session', 'auth', 'token', 'user', 'login', 'remember', 'csrf']
        },
        'ieee.org': {
            name: 'IEEE',
            identifier: 'ieee',
            patterns: ['JSESSIONID', 'session', 'auth', 'token', 'user', 'remember', 'csrf']
        },
        'ieeexplore.ieee.org': {
            name: 'IEEE',
            identifier: 'ieee',
            patterns: ['JSESSIONID', 'session', 'auth', 'token', 'user', 'remember', 'csrf']
        },
        'springer.com': {
            name: 'Springer',
            identifier: 'springer',
            patterns: ['session', 'auth', 'token', 'user', 'login', 'remember', 'csrf']
        },
        'link.springer.com': {
            name: 'Springer',
            identifier: 'springer', 
            patterns: ['session', 'auth', 'token', 'user', 'login', 'remember', 'csrf']
        }
    };
    
    // 获取当前网站信息
    function getCurrentSiteInfo() {
        const hostname = window.location.hostname.toLowerCase();
        const cleanHostname = hostname.replace('www.', '');
        
        // 查找匹配的数据库配置
        for (const [domain, config] of Object.entries(DATABASE_CONFIGS)) {
            if (cleanHostname === domain || cleanHostname.endsWith('.' + domain)) {
                return {
                    ...config,
                    site: hostname,
                    url: window.location.href
                };
            }
        }
        
        return null;
    }
    
    // 提取重要cookies
    function extractImportantCookies(patterns) {
        const allCookies = document.cookie;
        if (!allCookies) return '';
        
        const cookieList = allCookies.split(';').map(c => c.trim());
        const importantCookies = [];
        
        for (const cookie of cookieList) {
            const cookieName = cookie.split('=')[0].toLowerCase();
            
            for (const pattern of patterns) {
                if (cookieName.includes(pattern.toLowerCase())) {
                    importantCookies.push(cookie);
                    break;
                }
            }
        }
        
        return importantCookies.join('; ');
    }
    
    // 发送cookies到ZotLink
    async function sendCookiesToZotLink(data) {
        try {
            const response = await fetch(ZOTLINK_SERVICE_URL + '/cookies', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            return { success: true, data: result };
            
        } catch (error) {
            return { success: false, error: error.message };
        }
    }
    
    // 显示通知
    function showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 999999;
            max-width: 350px;
            padding: 15px 20px;
            border-radius: 8px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 14px;
            line-height: 1.4;
            color: white;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            cursor: pointer;
            transition: opacity 0.3s ease;
            background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#2196F3'};
        `;
        
        notification.innerHTML = message;
        notification.onclick = () => notification.remove();
        
        document.body.appendChild(notification);
        
        // 自动移除
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 300);
            }
        }, NOTIFICATION_DURATION);
    }
    
    // 检查ZotLink服务状态
    async function checkZotLinkService() {
        try {
            const response = await fetch(ZOTLINK_SERVICE_URL + '/health', {
                method: 'GET',
                timeout: 2000
            });
            return response.ok;
        } catch (error) {
            return false;
        }
    }
    
    // 主执行函数
    async function main() {
        // 检查当前网站是否支持
        const siteInfo = getCurrentSiteInfo();
        if (!siteInfo) {
            showNotification(`
                ⚠️ 当前网站不受支持<br>
                <small>ZotLink目前支持：Nature、Science、IEEE、Springer</small>
            `, 'warning');
            return;
        }
        
        // 检查ZotLink服务状态
        showNotification(`🔄 正在连接ZotLink服务...`, 'info');
        
        const serviceOnline = await checkZotLinkService();
        if (!serviceOnline) {
            showNotification(`
                ❌ 无法连接到ZotLink服务<br>
                <small>请确保ZotLink正在运行并重试</small>
            `, 'error');
            return;
        }
        
        // 提取cookies
        const cookies = extractImportantCookies(siteInfo.patterns);
        if (!cookies) {
            showNotification(`
                ⚠️ 未找到${siteInfo.name}认证信息<br>
                <small>请先登录您的${siteInfo.name}账户</small>
            `, 'warning');
            return;
        }
        
        // 准备数据
        const cookieData = {
            site: siteInfo.site,
            siteName: siteInfo.name,
            cookies: cookies,
            url: siteInfo.url,
            timestamp: new Date().toISOString(),
            userAgent: navigator.userAgent,
            cookieCount: cookies.split(';').length
        };
        
        // 发送到ZotLink
        showNotification(`�� 正在同步${siteInfo.name}认证信息...`, 'info');
        
        const result = await sendCookiesToZotLink(cookieData);
        
        if (result.success) {
            showNotification(`
                ✅ ${siteInfo.name}认证信息同步成功！<br>
                <small>已提取 ${cookieData.cookieCount} 个认证cookie</small><br>
                <small>现在可以在Claude Desktop中下载${siteInfo.name}论文了</small>
            `, 'success');
        } else {
            showNotification(`
                ❌ 同步失败：${result.error}<br>
                <small>请检查ZotLink服务状态后重试</small>
            `, 'error');
        }
    }
    
    // 执行主函数
    main().catch(error => {
        console.error('ZotLink书签执行错误:', error);
        showNotification(`
            ❌ 执行出错：${error.message}<br>
            <small>请查看控制台获取详细信息</small>
        `, 'error');
    });
    
})();
