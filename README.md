# arXiv Paper Collector

从 arXiv 批量下载学术论文 PDF，支持按类别、日期范围、关键词、作者筛选。与 ACL Anthology Downloader 共用 MongoDB 数据库。

## 项目结构

```
Arxiv-Paper-Collector/
├── setup.py              # 包安装 + console script
├── requirements.txt      # Python 依赖
├── src/
│   ├── __main__.py       # 入口
│   ├── cli.py            # 命令行 (download / list 子命令)
│   ├── api_client.py     # arXiv API 抓取 + 数据处理
│   ├── db.py             # MongoDB 状态跟踪
│   ├── downloader.py     # PDF 下载
│   └── __init__.py
├── config/
│   └── settings.py       # API 配置 + 类别列表
├── README.md
└── CLAUDE.md
```

## 快速开始

### 安装

```bash
pip install -r requirements.txt
# 或
pip install -e .
```

### 使用

```bash
# 下载论文
python -m src download --categories cs.AI --date 2025 --max 10

# 下载指定月份范围
python -m src download --categories cs.AI,cs.CV --date 2025-03-2025-06 --output papers

# 按关键词搜索
python -m src download --categories cs.CL --date 2025 --keywords "transformer,attention"

# 列出论文（不下载）
python -m src list --categories cs.AI --date 2025-03 --max 20
```

### PyCharm

直接运行 `src/__main__.py` 即可，支持断点调试。

## 命令行参数

### download 子命令

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--categories` | arXiv 类别，逗号分隔 | `cs.AI` |
| `--date` | 日期范围（见下方格式） | `2025` |
| `--output` | PDF 输出目录 | `papers` |
| `--max` | 最大下载数量 | `2000` |
| `--keywords` | 关键词，逗号分隔 | - |
| `--authors` | 作者，逗号分隔 | - |
| `--days` | 最近 N 天 | - |
| `--uri` | MongoDB 连接地址 | `mongodb://localhost:27017` |

### list 子命令

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--categories` | arXiv 类别（必填） | - |
| `--date` | 日期范围（必填） | - |
| `--keywords` | 关键词过滤 | - |
| `--max` | 最大显示数量 | `100` |

### --date 格式

| 格式 | 示例 | 含义 |
|------|------|------|
| 年份 | `2025` | 整个 2025 年 |
| 年份范围 | `2024-2025` | 2024 到 2025 年 |
| 年-月 | `2025-03` | 2025 年 3 月 |
| 月-月 | `2025-03-2025-06` | 2025 年 3 月到 6 月 |

## 输出结构

```
papers/                          # --output 目录
├── cs.AI/
│   ├── 2025/
│   │   ├── Attention_Is_All_You_Need.pdf
│   │   └── ...
│   └── 2024/
│       └── ...
├── cs.CV/
│   └── ...
```

## 数据库

与 ACL Anthology Downloader 共用同一个 MongoDB：

- 数据库: `acl_anthology`
- 集合: `papers`
- 通过 `source` 字段区分来源：`"arxiv"` vs `"acl_anthology"`
- `pdf_url` 作为唯一键
- 状态: `pending` → `completed` / `failed`
- 支持断点续传：重新运行自动跳过已下载的论文

## 常见问题

**Q: 如何恢复中断的下载？**
A: 直接重新运行相同命令，MongoDB 会自动跳过已完成的论文。

**Q: 下载速度慢？**
A: arXiv API 有频率限制，项目内置了 3 秒间隔的速率控制，避免被封 IP。

**Q: 如何添加新类别？**
A: 在 `config/settings.py` 的 `CATEGORIES` 列表中添加，或在命令行用 `--categories` 指定任意类别。
