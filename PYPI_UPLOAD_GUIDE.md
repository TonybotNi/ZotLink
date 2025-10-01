# 📦 ZotLink PyPI 上传指南

## 🎯 快速上传流程

### 1. 准备 PyPI API Token

1. 访问 [PyPI官网](https://pypi.org/)
2. 注册或登录账户
3. 进入 **Account settings** → **API tokens**
4. 点击 **Add API token**
5. Token名称: `zotlink-upload`
6. Scope: **Entire account** 
7. 创建并复制token（格式：`pypi-xxx...`）

### 2. 设置认证信息

**方式A: 环境变量（推荐）**
```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-你的完整token
```

**方式B: 配置文件 `~/.pypirc`**
```ini
[pypi]
username = __token__
password = pypi-你的完整token
```

### 3. 上传包

```bash
# 确保在正确环境
conda activate mcp_dev
cd ZotLink

# 验证包
python -m twine check dist/*

# 上传到PyPI
python -m twine upload dist/zotlink-1.3.0*
```

### 4. 验证上传

- 访问: https://pypi.org/project/zotlink/
- 测试安装: `pip install zotlink==1.3.0`

## 🧪 测试流程（可选）

如果你想先测试，可以上传到TestPyPI：

```bash
# 上传到TestPyPI
python -m twine upload --repository testpypi dist/*

# 从TestPyPI安装测试
pip install --index-url https://test.pypi.org/simple/ zotlink==1.3.0
```

## ⚠️ 重要提醒

- **API Token安全**: 只显示一次，请妥善保存
- **不要提交token**: 确保token不会被git提交
- **版本不可删除**: 上传成功后无法删除，只能发新版本
- **版本号唯一**: 每个版本号只能上传一次

## 🎉 上传成功后

用户就可以通过以下命令安装：

```bash
pip install zotlink
python -m playwright install chromium
zotlink
```

享受完整的学术文献管理功能！
