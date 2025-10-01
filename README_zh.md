<div align="center">

<img src="logo.png" alt="ZotLink Logo" width="150" height="150">

# ZotLink

面向 Zotero Connector 的 MCP 服务器

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Playwright 可选](https://img.shields.io/badge/Playwright-可选-informational)]()
[![Platforms](https://img.shields.io/badge/平台-macOS%20|%20Linux-lightgrey)]()

**🌍 Language / 语言选择:**
[🇺🇸 English](README.md) | [🇨🇳 中文](README_zh.md)

</div>

## 🔗 ZotLink

轻量、稳定、可扩展的学术文献 MCP 服务，让开放学术资源一键进入 Zotero。

❤️ 喜欢 ZotLink？给它一个星标 🌟 来支持开发！

## ✨ 核心特性

- 🌐 **开放预印本覆盖**：arXiv、CVF（OpenAccess）、bioRxiv、medRxiv、chemRxiv
- 🧠 **丰富元数据提取**：标题、作者、摘要、DOI、学科、Comment
- 📄 **智能PDF附件**：可用即自动附件；失败降级为已校验的链接
- 📚 **一键集合保存**：列出与保存（updateSession，treeViewID: C{id}）
- 🧭 **自适应浏览器策略**：艰难站点用 Playwright，其余使用 HTTP
- 💻 **客户端适配**：兼容 Claude Desktop、Cherry Studio
- 🧩 **深度 MCP 互操作**：与文献相关 MCP 深度适配，例如 [arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server) 与 [Zotero MCP](https://github.com/54yyyu/zotero-mcp)
- 📝 **统一日志**：`~/.zotlink/zotlink.log`

## 🚀 快速开始

### 安装

**从PyPI安装（推荐）**
```bash
pip install zotlink
```
*现已默认包含所有预印本服务器的完整浏览器支持！*

**开发安装**

***macOS（zsh）***
```bash
pip install -e .
```

***Windows（CMD/PowerShell）***
```powershell
pip install -e .
```

***Linux（bash）***
```bash
pip install -e .
```

需要 Python 3.10+。现已默认包含浏览器驱动提取功能。安装后执行：

```bash
python -m playwright install chromium
```

### 运行

命令行（推荐）：

```bash
zotlink
```

开发模式：

```bash
python run_server.py
```

### MCP 集成（Claude Desktop）

**推荐配置**（简单 - 只需指定Zotero目录）：

```json
{
  "mcpServers": {
    "zotlink": {
      "command": "/path/to/zotlink",
      "args": [],
      "env": {
        "ZOTLINK_ZOTERO_ROOT": "/Users/yourname/Zotero"
      }
    }
  }
}
```

**高级配置**（分别指定路径）：

```json
{
  "mcpServers": {
    "zotlink": {
      "command": "/path/to/zotlink",
      "args": [],
      "env": {
        "ZOTLINK_ZOTERO_DB": "/Users/yourname/Zotero/zotero.sqlite",
        "ZOTLINK_ZOTERO_DIR": "/Users/yourname/Zotero/storage"
      }
    }
  }
}
```

**最简配置**（自动检测Zotero路径）：

```json
{
  "mcpServers": {
    "zotlink": { "command": "zotlink", "args": [] }
  }
}
```

**备用方式**（显式Python路径）：

```json
{
  "mcpServers": {
    "zotlink": {
      "command": "/full/path/to/python",
      "args": ["-m", "zotlink.zotero_mcp_server"],
      "env": {
        "ZOTLINK_ZOTERO_ROOT": "/Users/yourname/Zotero"
      }
    }
  }
}
```

**Claude配置文件位置**：
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`  
- **Windows**: `~/AppData/Roaming/Claude/claude_desktop_config.json`

**注意**: 使用 `env` 环境变量符合MCP标准，兼容所有MCP客户端（Claude Desktop、Cherry Studio等）。

## 🧰 可用工具

- `check_zotero_status`：检查 Zotero 是否运行且可达
- `get_zotero_collections`：从本地数据库读取集合（树形）
- `save_paper_to_zotero`：通过 URL（arXiv/CVF/rxiv）保存论文，自动处理 PDF/元数据
- `extract_arxiv_metadata`：提取完整 arXiv 元数据（标题/作者/学科/DOI/Comment）
- Cookies 辅助（预留）支持需要认证的站点

## 📁 日志

日志写入 `~/.zotlink/zotlink.log`。

## 🌐 浏览器模式（已内置）

浏览器驱动提取现已默认包含！所有预印本服务器（bioRxiv、medRxiv、chemRxiv）自动工作。安装后初始化浏览器运行时：

***macOS（zsh）*** — 开发安装
```bash
pip install -e .
```

***Windows（CMD/PowerShell）*** — 开发安装
```powershell
pip install -e .
```

***Linux（bash）*** — 开发安装
```bash
pip install -e .
```

**安装浏览器运行时**
```bash
python -m playwright install chromium
```

**Linux 可能需要系统依赖**
```bash
sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2
```

服务器会在需要时自动切换到浏览器策略。

### 可选：自定义 Zotero 路径（数据库/存储目录）

支持多种配置方式，优先级：环境变量 > Claude配置 > 本地配置文件 > 默认探测。

1) 环境变量（最高优先级）

**推荐方式 - 单目录**：
- macOS/Linux（bash/zsh）
```bash
export ZOTLINK_ZOTERO_ROOT=/Users/yourname/Zotero
```

- Windows（PowerShell）
```powershell
$env:ZOTLINK_ZOTERO_ROOT='C:\\Users\\YourName\\Zotero'
```

**高级方式 - 分别指定**（向后兼容）：
- macOS/Linux（bash/zsh）
```bash
export ZOTLINK_ZOTERO_DB=/Users/yourname/Zotero/zotero.sqlite
export ZOTLINK_ZOTERO_DIR=/Users/yourname/Zotero/storage
```

- Windows（PowerShell）
```powershell
$env:ZOTLINK_ZOTERO_DB='C:\\Users\\YourName\\Zotero\\zotero.sqlite'
$env:ZOTLINK_ZOTERO_DIR='C:\\Users\\YourName\\Zotero\\storage'
```

2) Claude 配置文件（推荐，适合MCP用户）

直接在 Claude 配置文件中添加 Zotero 路径，无需额外配置文件：

```json
{
  "mcpServers": {
    "zotlink": {
      "command": "path/to/zotlink",
      "args": [],
      "zotero_database_path": "/Users/yourname/Zotero/zotero.sqlite",
      "zotero_storage_dir": "/Users/yourname/Zotero/storage"
    }
  }
}
```

Claude 配置文件位置：
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`
- **Windows**: `~/AppData/Roaming/Claude/claude_desktop_config.json`

3) 本地配置文件（传统方式）

在用户目录创建 `~/.zotlink/config.json`：
```json
{
  "zotero": {
    "database_path": "/Users/yourname/Zotero/zotero.sqlite",
    "storage_dir": "/Users/yourname/Zotero/storage"
  }
}
```

未配置时的常见默认路径：
- macOS: `~/Zotero/zotero.sqlite` 或 `~/Library/Application Support/Zotero/Profiles/<profile>/zotero.sqlite`
- Windows: `C:\\Users\\<User>\\Zotero\\zotero.sqlite` 或 `%APPDATA%\\Zotero\\Zotero\\Profiles\\<profile>\\zotero.sqlite`
- Linux: `~/Zotero/zotero.sqlite` 或 `~/.zotero/zotero.sqlite`

修改后请重启 ZotLink 使配置生效。

## 🧩 支持的开放站点

- **arXiv**（预印本）
- **CVF（OpenAccess）**（CVPR/ICCV/WACV）
- **bioRxiv** / **medRxiv** / **chemRxiv**（预印本服务器）

需要认证的站点（如 Nature 家族）计划通过书签同步 cookies 支持。

## 🧰 故障排除

- 未检测到 Zotero：请确认 Zotero Desktop 已运行（端口 23119）
- 未附加 PDF：部分页面仅提供链接，服务器将退回为“链接附件”
~- 浏览器模式报错：确认已安装 Playwright 且 Chromium 可用~

## 🧪 开发

```bash
pip install -e .
python -m playwright install chromium
zotlink  # 或：python run_server.py
```

参见 `docs/DEVELOPMENT.md` 获取代码结构、扩展新提取器、发布建议等。

## 🗺️ 路线图（To‑Do）

- 站点支持
  - [x] arXiv
  - [x] CVF（OpenAccess）
  - [x] bioRxiv
  - [x] medRxiv
  - [x] chemRxiv
  - [ ] Nature（需要 cookies）
  - [ ] Science（需要 cookies）
  - [ ] IEEE Xplore（需要 cookies）
  - [ ] Springer（需要 cookies）
  - [ ] ACM Digital Library（需要 cookies）
  - [ ] OpenReview
  - [ ] PLOS / PMC / Frontiers / MDPI

- 稳定性与质量
  - [x] 可配置的 Zotero 数据库路径（ENV + ~/.zotlink/config.json）
  - [x] 浏览器失败时的HTTP回退机制（Windows兼容性）
  - [x] PDF下载重试机制（3次重试+指数退避）
  - [ ] Windows playwright优化（当前限制：Python asyncio ProactorEventLoop与MCP事件循环嵌套问题）
  - [ ] 占位标题的保存后纠正（自动二次提取标题）
  - [ ] 增强 PDF 启发式与备用 URL 策略
  - [ ] Crossref DOI 富化作为回退
  - [ ] 统一错误分类与自动重试/退避

- 集成与开发体验
  - [ ] Nature 等商业站点书签同步 Cookie 流程
  - [ ] 为 Claude Desktop / Cherry Studio 提供示例配置与模板
  - [ ] 扩展 MCP 互操作文档与示例
  - [ ] 提取器的单元/集成测试与 CI
  - [ ] 可选发布包（打包发布）

## 📄 许可证

MIT（打包元数据中含 SPDX 标识）


