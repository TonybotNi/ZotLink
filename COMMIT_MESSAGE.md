# 🚀 ZotLink v1.1.0 - PyPI发布准备

## 📦 主要改进

### ✨ 新功能
- **配置文件重构**: 支持多级配置优先级（环境变量 > Claude配置 > 本地配置 > 自动检测）
- **Claude配置支持**: 可直接在Claude配置文件中指定Zotero路径，无需额外配置文件
- **用户配置目录**: 配置文件迁移到 `~/.zotlink/` 目录，适合PyPI发布
- **迁移工具**: 提供 `migrate_configs.py` 自动迁移现有配置
- **清理工具**: 提供 `cleanup_nature.py` 清理未使用的功能

### 🔧 代码优化
- **Nature功能**: 禁用未启用的Nature相关功能，但保留代码结构便于将来启用
- **配置路径**: 所有cookies和配置文件支持用户目录，解决PyPI发布后的路径问题
- **向后兼容**: 保持对现有配置方式的兼容性

### 📝 文档更新
- **README**: 更新安装指南，改为从PyPI安装的推荐方式
- **配置说明**: 添加Claude配置文件的详细说明
- **多语言支持**: 中英文文档同步更新

### 🧹 项目清理
- **文件结构**: 清理临时文件、日志文件、用户配置等
- **开发报告**: 移除大量开发报告，保留核心文档
- **gitignore**: 更新忽略规则，适合开源项目

### 🚀 PyPI准备
- **构建配置**: 完善 `setup.py` 和 `pyproject.toml`
- **发布脚本**: 提供 `publish_to_pypi.sh` 发布工具
- **包验证**: 通过 `twine check` 质量检查

## 🎯 发布说明

此版本为PyPI发布准备版本，用户安装后可通过以下方式使用：

```bash
pip install zotlink
```

然后在Claude配置中添加：
```json
{
  "mcpServers": {
    "zotlink": {
      "command": "zotlink", 
      "args": [],
      "zotero_database_path": "/path/to/zotero.sqlite",
      "zotero_storage_dir": "/path/to/zotero/storage"
    }
  }
}
```

支持arXiv、bioRxiv、CVF等多个学术网站的论文提取和Zotero集成。
