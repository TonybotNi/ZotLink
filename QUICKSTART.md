# 🔗 ZotLink 快速开始

## 📋 5分钟配置指南

### Step 1: 确保Zotero已启动
```bash
# 启动Zotero桌面应用，确保完全加载
```

### Step 2: 测试功能
```bash
python test_zotlink.py
```

预期结果：
```
🎉 所有测试通过！ZotLink已准备就绪！
```

### Step 3: 配置Claude Desktop

1. **找到配置文件**：
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. **添加服务器配置**：
```json
{
  "mcpServers": {
    "zotlink": {
      "command": "python3",
      "args": ["/Users/mudrobot/Documents/CodeField/ScholarTool/ZotLink/run_server.py"],
      "env": {
        "PYTHONPATH": "/Users/mudrobot/Documents/CodeField/ScholarTool/ZotLink/src"
      }
    }
  }
}
```

**注意**：请将路径修改为你的实际路径！

### Step 4: 重启Claude Desktop

完全关闭并重新启动Claude Desktop应用。

### Step 5: 验证安装

在Claude Desktop中输入：
```
请检查我的Zotero连接状态
```

预期回复：
```
🎉 Zotero连接成功！

📱 应用状态: ✅ Zotero桌面应用正在运行
📚 集合数量: X 个
🚀 开始使用: 直接调用工具保存和管理学术文献！
```

## 🎯 立即体验

### 保存arXiv论文
```
请帮我保存这篇arXiv论文：https://arxiv.org/abs/1706.03762
```

### 查看集合
```
请显示我的Zotero集合列表
```

### 保存到指定集合
```
请帮我保存这篇论文到My Research集合：https://arxiv.org/abs/1706.03762
```

## 🎉 享受功能

- **🤖 完全自动化**：PDF自动下载
- **📝 完整元数据**：Comment、DOI、学科分类
- **🎯 智能集合**：自动保存到指定位置
- **⚡ 极速处理**：30-60秒完成

**开始享受最先进的学术文献管理体验！** 🚀 