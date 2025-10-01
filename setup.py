#!/usr/bin/env python3
"""
🔬 Zotero Connector MCP 安装脚本
"""

from setuptools import setup, find_packages

setup(
    name="zotlink",
    version="1.3.1",
    description="ZotLink - 智能学术文献管理 MCP 服务器",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="ScholarTool Team",
    license="MIT",
    packages=find_packages(include=["zotlink", "zotlink.*"]),
    include_package_data=True,
    package_data={
        "zotlink": [
            "browser_bookmarks/*.js"
        ]
    },
    python_requires=">=3.10",
    install_requires=[
        "mcp>=1.0.0",
        "python-mcp-server>=0.1.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "playwright>=1.40.0"
    ],
    extras_require={
        "advanced": [
            "pycryptodome>=3.19.0"
        ],
    },
    entry_points={
        "console_scripts": [
            "zotlink=zotlink.zotero_mcp_server:run",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Text Processing :: Markup :: HTML",
    ],
)