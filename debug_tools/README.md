# ZotLink 调试工具

本文件夹包含两个核心调试工具，用于测试和调试 ZotLink 的功能。

## 工具清单

### 1. `trace_url.py` - URL处理流程追踪

监视 paper_info 在处理过程中的变化，帮助理解和调试论文元数据提取流程。

**使用方法:**

```bash
# 命令行参数模式
python trace_url.py "https://arxiv.org/abs/2301.00001"

# 交互模式
python trace_url.py
# 然后输入URL
```

**功能:**
- 逐步显示元数据提取过程
- 展示 paper_info 的变化
- 显示最终的 Zotero 格式
- 追踪作者信息的处理流程

**支持的网站:**
- arXiv
- bioRxiv
- Nature
- 其他学术网站

---

### 2. `test_author_parsing.py` - 作者解析功能测试

单独测试作者名字的解析功能，支持多种格式。

**使用方法:**

```bash
# 交互模式
python test_author_parsing.py

# 命令行参数模式
python test_author_parsing.py "John Smith, Jane Doe"

# 运行预定义测试
python test_author_parsing.py --test
```

**支持的作者格式:**
- `John Smith, Jane Doe` - First Last格式，逗号分隔
- `Smith, John` - Last, First格式（单作者）
- `Smith, John, Doe, Jane` - Last, First格式（多作者）
- `John Smith; Jane Doe` - 分号分隔
- `John Smith and Jane Doe` - and连接

**交互模式命令:**
- 输入作者字符串: 测试解析
- 输入 `test`: 运行预定义测试用例
- 输入 `q`: 退出

---

## 示例

### 示例 1: 追踪 arXiv 论文处理

```bash
python trace_url.py https://arxiv.org/abs/2509.21154
```

输出将显示:
1. 提取的原始元数据
2. 初始 paper_info
3. arXiv增强后的信息
4. 最终的Zotero格式
5. 作者信息总结

### 示例 2: 测试作者解析

```bash
python test_author_parsing.py
```

然后输入:
```
请输入作者字符串: Smith, John, Doe, Jane
```

输出:
```
解析结果: 2 个作者
作者 1:
  firstName: 'John'
  lastName:  'Smith'
作者 2:
  firstName: 'Jane'
  lastName:  'Doe'
```

---

## 环境要求

- Python 3.8+
- 已安装 ZotLink 依赖
- 对于某些网站（如 bioRxiv），需要安装 Playwright 浏览器

```bash
# 安装依赖
pip install -r ../requirements.txt

# 安装 Playwright 浏览器（如需要）
python -m playwright install chromium
```

---

## 注意事项

1. 这些工具仅用于调试，不会修改实际的 Zotero 库
2. 某些网站可能需要稳定的网络连接
3. `trace_url.py` 会实际访问网页，请遵守目标网站的使用条款

---

## 技术细节

### 作者解析逻辑

作者解析使用以下优先级:
1. 分号分隔 (`;`) - 标准学术格式
2. `and` 连接词
3. 逗号分隔 (`,`) - 智能判断:
   - 1-2个逗号: 可能是单作者 "Last, First" 格式
   - 3个以上逗号: 可能是多作者 "Last, First, Last, First" 格式

### URL处理流程

1. **元数据提取**: 从网页或API提取原始数据
2. **初始化**: 构建基础 paper_info 结构
3. **增强**: 针对特定来源（如arXiv）进行增强
4. **转换**: 转换为Zotero标准格式

---

*最后更新: 2025-10*
