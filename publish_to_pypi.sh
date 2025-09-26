#!/bin/bash
"""
🚀 ZotLink PyPI 发布脚本

使用方法：
1. 获取PyPI API token: https://pypi.org/manage/account/token/
2. 运行: bash publish_to_pypi.sh
3. 输入用户名: __token__
4. 输入密码: pypi-YOUR_API_TOKEN
"""

set -e

echo "🚀 ZotLink PyPI 发布脚本"
echo "========================"

# 激活conda环境
if command -v conda &> /dev/null; then
    echo "📦 激活conda环境..."
    conda activate mcp_dev
else
    echo "⚠️  conda未找到，使用当前Python环境"
fi

# 检查dist目录
if [ ! -d "dist" ] || [ -z "$(ls -A dist/)" ]; then
    echo "❌ dist目录不存在或为空，请先构建包："
    echo "   python -m build"
    exit 1
fi

echo "📋 当前可发布的文件："
ls -la dist/

echo
echo "⚠️  发布前确认："
echo "1. 你已经有PyPI账号"
echo "2. 你已经创建了API token"
echo "3. 用户名输入: __token__"
echo "4. 密码输入: pypi-YOUR_API_TOKEN"
echo

read -p "继续发布? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ 取消发布"
    exit 0
fi

echo "🚀 开始上传到PyPI..."
python -m twine upload dist/*

echo "✅ 发布完成！"
echo "🔗 访问 https://pypi.org/project/zotlink/ 查看你的包"
