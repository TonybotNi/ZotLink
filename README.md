<div align="center">

<img src="logo.png" alt="ZotLink Logo" width="150" height="150">

# ZotLink

MCP Server for Zotero Connector

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platforms](https://img.shields.io/badge/platforms-macOS%20|%20Windows%20|%20Linux-lightgrey)]()

**🌍 Language / 语言选择:**
[🇺🇸 English](README.md) | [🇨🇳 中文](README_zh.md)

</div>

## 🔗 ZotLink

A lightweight, production-ready MCP server that brings open scholarly sources into Zotero with one command.

❤️ Like ZotLink? Give it a star 🌟 to support the development!

## ✨ Core Features

- 🌐 **Open Preprint Coverage**: arXiv, CVF (OpenAccess), bioRxiv, medRxiv, chemRxiv
- 🧠 **Rich Metadata Extraction**: title, authors, abstract, DOI, subjects, comments
- 📄 **Smart PDF Attachment**: auto-attach when available; validated link fallback
- 📚 **One-Click Collection Save**: list + save (updateSession, treeViewID: C{id})
- 🧭 **Adaptive Browser Strategy**: Playwright for tough sites; HTTP for the rest
- 💻 **Client Compatibility**: Works with Claude Desktop and Cherry Studio
- 🧩 **Deep MCP Interoperability**: Integrates with literature-related MCPs such as [arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server) and [Zotero MCP](https://github.com/54yyyu/zotero-mcp)
- 📝 **Unified Logging**: `~/.zotlink/zotlink.log`

## 🚀 Quick Start

### Install

**Install from PyPI (recommended)**
```bash
pip install zotlink
```
*Now includes full browser support for all preprint servers by default!*

**Development installation**

***macOS (zsh)***
```bash
pip install -e .
```

***Windows (CMD/PowerShell)***
```powershell
pip install -e .
```

***Linux (bash)***
```bash
pip install -e .
```

Requires Python 3.10+. Includes browser-driven extraction for all preprint servers. After installation, run:

```bash
python -m playwright install chromium
```

### Run

CLI (recommended):

```bash
zotlink
```

Development mode:

```bash
python run_server.py
```

### MCP Integration (Claude Desktop)

**Recommended configuration** (simple - just specify Zotero directory):

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

**Advanced configuration** (specify paths separately):

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

**Minimal config** (auto-detect Zotero paths):

```json
{
  "mcpServers": {
    "zotlink": { "command": "zotlink", "args": [] }
  }
}
```

**Fallback** (explicit Python path):

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

**Claude config file locations:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`  
- **Windows**: `~/AppData/Roaming/Claude/claude_desktop_config.json`

**Note**: Using `env` variables follows MCP standard and works with all MCP clients (Claude Desktop, Cherry Studio, etc.).

## 🧰 Available Tools

- `check_zotero_status`: Check if Zotero is running and reachable
- `get_zotero_collections`: List collections (tree view) from the local DB
- `save_paper_to_zotero`: Save a paper by URL (arXiv/CVF/rxiv), attach PDF/metadata
- `extract_arxiv_metadata`: Extract full arXiv metadata (title/authors/subjects/DOI/comment)
- Cookie helpers (stubs prepared) for auth-required sources

## 📁 Logging

Logs are written to `~/.zotlink/zotlink.log`.

## 🌐 Browser Mode (Included)

Browser-driven extraction is now included by default! All preprint servers (bioRxiv, medRxiv, chemRxiv) work automatically. After installation, initialize the browser runtime:

***macOS (zsh)*** — development install
```bash
pip install -e .
```

***Windows (CMD/PowerShell)*** — development install
```powershell
pip install -e .
```

***Linux (bash)*** — development install
```bash
pip install -e .
```

**Install browser runtime**
```bash
python -m playwright install chromium
```

**Linux may require system dependencies**
```bash
sudo apt-get install -y libnss3 libatk1.0-0 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libgbm1 libasound2
```

The server will switch to a browser strategy automatically when needed.

### Optional: Custom Zotero Paths (DB/Storage)

You can override the local Zotero database path and storage dir. Precedence: ENV vars > Claude config > local config file > defaults.

1) Environment variables (highest priority)

**Recommended - Single directory**:
- macOS/Linux (bash/zsh)
```bash
export ZOTLINK_ZOTERO_ROOT=/Users/yourname/Zotero
```

- Windows (PowerShell)
```powershell
$env:ZOTLINK_ZOTERO_ROOT='C:\\Users\\YourName\\Zotero'
```

**Advanced - Separate paths** (backward compatibility):
- macOS/Linux (bash/zsh)
```bash
export ZOTLINK_ZOTERO_DB=/Users/yourname/Zotero/zotero.sqlite
export ZOTLINK_ZOTERO_DIR=/Users/yourname/Zotero/storage
```

- Windows (PowerShell)
```powershell
$env:ZOTLINK_ZOTERO_DB='C:\\Users\\YourName\\Zotero\\zotero.sqlite'
$env:ZOTLINK_ZOTERO_DIR='C:\\Users\\YourName\\Zotero\\storage'
```

2) Claude configuration (recommended for MCP users)

Add Zotero paths directly to your Claude configuration file:

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

Claude config file locations:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux**: `~/.config/claude/claude_desktop_config.json`
- **Windows**: `~/AppData/Roaming/Claude/claude_desktop_config.json`

3) Local config file (traditional method)

Create `~/.zotlink/config.json`:
```json
{
  "zotero": {
    "database_path": "/Users/yourname/Zotero/zotero.sqlite",
    "storage_dir": "/Users/yourname/Zotero/storage"
  }
}
```

Default search locations when not configured:
- macOS: `~/Zotero/zotero.sqlite` or `~/Library/Application Support/Zotero/Profiles/<profile>/zotero.sqlite`
- Windows: `C:\\Users\\<User>\\Zotero\\zotero.sqlite` or `%APPDATA%\\Zotero\\Zotero\\Profiles\\<profile>\\zotero.sqlite`
- Linux: `~/Zotero/zotero.sqlite` or `~/.zotero/zotero.sqlite`

Restart ZotLink after changing configuration.

## 🧩 Supported Sources (Open)

- **arXiv** (preprint)
- **CVF (OpenAccess)** (CVPR/ICCV/WACV)
- **bioRxiv** / **medRxiv** / **chemRxiv** (preprint servers)

Auth-required sources (e.g., Nature) are planned via bookmark-based cookie sync.

## 🧰 Troubleshooting

- Zotero not detected: ensure Zotero Desktop is running (port 23119)
- No PDF attached: some pages only expose links; the server falls back to link attachments
- Browser mode errors: verify Playwright is installed and Chromium is available
  - Install error: ensure Python 3.10+ is installed

## 🧪 Development

```bash
pip install -e .
python -m playwright install chromium
zotlink  # or: python run_server.py
```

See `docs/DEVELOPMENT.md` for code structure, adding new extractors, and release tips.

## 🗺️ Roadmap (To‑Do)

- Sources
  - [x] arXiv
  - [x] CVF (OpenAccess)
  - [x] bioRxiv
  - [x] medRxiv
  - [x] chemRxiv
  - [ ] Nature (cookies)
  - [ ] Science (cookies)
  - [ ] IEEE Xplore (cookies)
  - [ ] Springer (cookies)
  - [ ] ACM Digital Library (cookies)
  - [ ] OpenReview
  - [ ] PLOS / PMC / Frontiers / MDPI

- Stability & Quality
  - [x] Configurable Zotero DB path (ENV + ~/.zotlink/config.json)
  - [x] HTTP fallback when browser fails (Windows compatibility)
  - [ ] Windows playwright optimization (current limitation: Python asyncio ProactorEventLoop + MCP event loop nesting)
  - [ ] Post-save title correction when placeholder detected
  - [ ] Enhanced PDF heuristics and alternative URL strategies
  - [ ] Crossref DOI enrichment as fallback
  - [ ] Unified error taxonomy with auto-retry/backoff

- Integration & DX
  - [ ] Cookie sync bookmark flow for Nature-family and other publishers
  - [ ] Example templates for Claude Desktop / Cherry Studio
  - [ ] Extended MCP interoperability docs and samples
  - [ ] CI and tests (unit/integration) for extractors
  - [ ] Packaged releases (optional)

## 📄 License

MIT (see SPDX identifier in packaging metadata)