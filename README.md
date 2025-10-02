# arXiv Paper Collector

一个强大的arXiv论文收集工具，支持按类别、时间范围、关键词、作者等多种条件筛选论文，并自动下载元数据和PDF文件。

## 项目结构

```
arxiv_paper_collector/
├── config/                 # 配置文件
│   └── settings.py        # 主配置文件
├── src/                   # 源代码目录
│   ├── core/              # 核心功能模块
│   │   ├── api_client.py      # arXiv API客户端
│   │   ├── data_processor.py  # 数据处理器
│   │   ├── pdf_downloader.py  # PDF下载器
│   │   ├── state_manager.py   # 状态管理器
│   │   └── storage_manager.py # 存储管理器
│   ├── utils/             # 工具模块
│   │   ├── api_throttle.py    # API限流器
│   │   ├── helpers.py         # 辅助函数
│   │   └── logger.py          # 日志系统
│   └── main.py            # 主程序入口
├── data/                  # 数据目录（自动生成）
│   ├── metadata/          # 论文元数据
│   ├── pdfs/              # PDF文件
│   └── state/             # 状态文件
├── logs/                  # 日志目录（自动生成）
├── requirements.txt       # Python依赖列表
└── README.md             # 项目文档
```

## 功能特性

### 🎯 智能论文收集
- **多条件筛选**: 支持按类别、时间范围、关键词、作者等多种条件组合筛选
- **智能去重**: 内置状态管理，避免重复获取相同论文
- **增量更新**: 支持从上次结束位置继续获取，高效更新数据

### 📚 完整数据获取
- **元数据收集**: 获取论文标题、摘要、作者、类别、发布时间等完整信息
- **PDF下载**: 自动下载论文PDF文件，支持新旧arXiv ID格式
- **结构化存储**: 按类别和时间戳组织文件，便于管理

### ⚡ 高性能设计
- **速率控制**: 智能API限流，遵守arXiv服务条款
- **并发优化**: 高效的请求调度，最大化获取速度
- **错误恢复**: 自动重试机制，确保数据完整性

### 🔧 灵活配置
- **配置文件**: 通过YAML配置文件定制化搜索条件
- **命令行参数**: 支持命令行参数临时覆盖配置
- **模块化设计**: 易于扩展和维护

## 快速开始

### 环境要求

- Python 3.7+
- 依赖包: 参见 `requirements.txt`

### 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd arxiv_paper_collector
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 创建数据目录
```bash
mkdir -p data/metadata data/pdfs data/state logs
```

### 基础使用

1. 使用默认配置运行
```bash
python main.py
```

2. 指定特定类别
```bash
python main.py --categories cs.AI,cs.CV,cs.LG --limit 500
```

3. 获取最近一周的论文
```bash
python main.py --days 7 --categories cs.AI
```

4. 搜索特定关键词
```bash
python main.py --keywords "transformer,attention mechanism" --search-fields title,abstract
```

5. 搜索特定作者
```bash
python main.py --authors "Vaswani,Ashish" --categories cs.CL
```

## 核心模块说明

### 核心模块 (`src/core/`)
- **api_client.py**: 负责与arXiv API交互，构建查询请求和处理响应
- **data_processor.py**: 处理原始数据，清洗、验证和标准化论文信息
- **pdf_downloader.py**: 下载论文PDF文件，处理各种arXiv ID格式
- **state_manager.py**: 管理每个类别的获取状态，避免重复下载
- **storage_manager.py**: 处理元数据和PDF文件的存储组织

### 工具模块 (`src/utils/`)
- **api_throttle.py**: API请求速率限制器，确保遵守服务条款
- **helpers.py**: 通用辅助函数，如文件名安全处理等
- **logger.py**: 彩色日志系统，支持进度条和表格输出

## 配置说明

### 配置文件结构

项目配置位于 `config/settings.py`，主要包含以下部分：

```python
# API配置
API_ENDPOINT = "http://export.arxiv.org/api/query"
REQUEST_DELAY = 3  # 请求延迟(秒)
MAX_RETRIES = 3    # 最大重试次数

# 输出配置
OUTPUT_ROOT = "data/metadata"  # 元数据输出目录
PDF_ROOT = "data/pdfs"         # PDF存储目录
STATE_DIR = "data/state"       # 状态文件目录
BATCH_MODE = True              # 批次模式

# 获取限制
PAPERS_PER_CATEGORY = 1000     # 每类论文数量
MAX_RESULTS_PER_REQUEST = 500  # 每次请求最大数量

# 类别列表
CATEGORIES = [
    "cs.AI",   # 人工智能
    "cs.CV",   # 计算机视觉
    "cs.CL",   # 计算语言学
    # ... 更多类别
]

# 搜索配置
SEARCH_CONFIG = {
    "time_range": {
        "type": "specific_range",  # 时间范围类型
        "start_date": "2025-01-01",
        "end_date": "2025-10-02"
    },
    "keywords": {
        "enabled": False,          # 是否启用关键词搜索
        "terms": ["transformer"],
        "search_fields": ["title", "abstract"]
    },
    # ... 更多搜索配置
}
```

### 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--categories` | 指定类别列表 | `--categories cs.AI,cs.CV` |
| `--limit` | 每类论文数量 | `--limit 500` |
| `--days` | 最近N天的论文 | `--days 7` |
| `--start-date` | 开始日期 | `--start-date 2025-01-01` |
| `--end-date` | 结束日期 | `--end-date 2025-10-02` |
| `--keywords` | 搜索关键词 | `--keywords "transformer,attention"` |
| `--search-fields` | 搜索字段 | `--search-fields title,abstract` |
| `--authors` | 作者名称 | `--authors "Vaswani,Ashish"` |
| `--match-all-authors` | 必须匹配所有作者 | `--match-all-authors` |
| `--sort-by` | 排序字段 | `--sort-by submittedDate` |
| `--sort-order` | 排序方向 | `--sort-order descending` |
| `--log-level` | 日志级别 | `--log-level DEBUG` |
| `--batch` | 批次模式 | `--batch False` |

## 高级用法

### 定时任务配置

设置每天自动运行：

```bash
# Linux crontab示例
0 2 * * * cd /path/to/arxiv_paper_collector && python main.py --days 1 --categories cs.AI,cs.CV >> logs/cron.log 2>&1
```

### 自定义搜索配置

修改 `config/settings.py` 中的 `SEARCH_CONFIG`：

```python
SEARCH_CONFIG = {
    "time_range": {
        "type": "last_n_days",
        "value": 30  # 最近30天
    },
    "keywords": {
        "enabled": True,
        "terms": ["large language model", "llm"],
        "search_fields": ["title", "abstract"]
    },
    "sort_by": "submittedDate",
    "sort_order": "descending"
}
```

### 扩展新的论文类别

在 `CATEGORIES` 列表中添加新的arXiv类别：

```python
CATEGORIES = [
    "cs.AI",      # 人工智能
    "cs.CV",      # 计算机视觉
    "cs.LG",      # 机器学习
    "cs.CL",      # 计算语言学
    "quant-ph",   # 量子物理
    "math.AT",    # 代数拓扑
    # 添加更多类别...
]
```

## 输出格式

### 元数据文件 (JSONL格式)

每行包含一篇论文的完整信息：

```json
{
  "arxiv_id": "1706.03762v5",
  "title": "Attention Is All You Need",
  "abstract": "We propose a new simple network architecture...",
  "authors": ["Vaswani, Ashish", "Shazeer, Noam", ...],
  "category": "cs.CL",
  "published": "2017-06-12T18:00:00Z",
  "updated": "2023-02-15T14:30:00Z",
  "primary_category": "cs.CL",
  "categories": ["cs.CL", "cs.LG"],
  "doi": "10.48550/arXiv.1706.03762",
  "pdf_url": "https://arxiv.org/pdf/1706.03762v5.pdf",
  "comment": "Published in NeurIPS 2017",
  "processed_at": "2025-10-02T12:30:45.123456Z"
}
```

### 文件组织结构

```
data/
├── metadata/                    # 元数据目录
│   ├── cs-AI/                  # 按类别组织
│   │   ├── papers_20251002_143045.jsonl
│   │   └── papers_20251003_093015.jsonl
│   └── cs-CV/
│       └── ...
├── pdfs/                       # PDF目录
│   ├── cs-AI/                  # 按类别组织
│   │   ├── 20251002_143045/    # 按时间戳组织
│   │   │   ├── 1706.03762v5_20251002_143045.pdf
│   │   │   └── ...
│   │   └── papers/             # 追加模式
│   │       └── ...
│   └── cs-CV/
│       └── ...
└── state/                      # 状态文件
    ├── cs-AI.state
    ├── cs-CV.state
    └── ...
```

## 常见问题

### Q: 如何避免被arXiv API限制？
A: 项目内置了速率控制机制：
- 默认请求间隔3秒
- PDF下载间隔5秒
- 自动重试和指数退避

### Q: 下载PDF失败怎么办？
A: 检查以下可能原因：
1. arXiv ID格式是否正确
2. 网络连接是否正常
3. 存储空间是否充足
4. 查看详细日志：`--log-level DEBUG`

### Q: 如何恢复中断的下载？
A: 状态文件会自动保存进度，重新运行程序即可从上次中断处继续。

### Q: 可以自定义输出格式吗？
A: 当前支持JSONL格式，可通过修改 `data_processor.py` 扩展其他格式。

## 贡献指南

欢迎提交Issue和Pull Request来改进这个项目！

1. Fork本项目
2. 创建特性分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m 'Add some AmazingFeature'`
4. 推送到分支：`git push origin feature/AmazingFeature`
5. 提交Pull Request

## 许可证

本项目采用MIT许可证 - 详见LICENSE文件。

## 致谢

- 感谢[arXiv](https://arxiv.org/)提供开放访问的科研论文
- 感谢所有贡献者和用户

## 支持

如果您在使用过程中遇到问题，请：
1. 查看本文档和代码注释
2. 检查日志文件中的详细错误信息
3. 提交GitHub Issue描述您的问题