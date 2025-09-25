## 开发指南 | Development Guide

本指南说明如何在本地开发、调试与扩展 ZotLink。

This guide explains local development, debugging and extension for ZotLink.

### 环境搭建 | Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[browser]
python -m playwright install chromium
```

### 运行服务器 | Run Server

```bash
zotlink
# 或/OR
python run_server.py
```

日志位于 `~/.zotlink/zotlink.log`。

Logs: `~/.zotlink/zotlink.log`.

### 代码结构 | Code Structure

- `zotlink/zotero_mcp_server.py`: MCP 入口 / MCP entrypoint
- `zotlink/zotero_integration.py`: 与 Zotero Connector 交互逻辑 / Zotero integration
- `zotlink/extractors/`: 各站点提取器 / site extractors (arXiv, CVF, rxiv family)
- `zotlink/cookie_sync/`: Cookie 同步与状态 / cookie sync and status

### 新增站点支持 | Add New Site

1. 在 `zotlink/extractors/` 下创建提取器，继承 `BaseExtractor`
2. 在 `ExtractorManager._register_extractors` 中注册
3. 实现 `can_handle`, `extract_metadata`, `test_access`

1. Create a new extractor extending `BaseExtractor`
2. Register it in `ExtractorManager._register_extractors`
3. Implement `can_handle`, `extract_metadata`, `test_access`

### 浏览器模式 | Browser Mode

ZotLink 可在需要时启用 Playwright 浏览器以绕过反爬策略（如 OSF、rxiv 系列）。安装 `[browser]` extra 并执行 `playwright install`。

ZotLink can optionally use Playwright to bypass anti-bot (OSF, rxiv family). Install `[browser]` extra and run `playwright install`.

### 发行构建 | Release Build

```bash
python -m build
```

确保 `setup.py` 中包含 `package_data`，书签脚本会被打包。

Ensure `package_data` includes bookmark scripts.

### 测试 | Tests

建议为新提取器添加最小化的端到端测试（可使用公开 URL）。

Add minimal e2e tests for new extractors with public URLs.




