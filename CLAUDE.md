# CLAUDE.md

## Project Overview

arXiv 论文批量下载工具，与 ACL Anthology Downloader 共用 MongoDB 数据库 (`acl_anthology.papers`)，通过 `source` 字段区分来源。

## Development Commands

```bash
# 下载论文
python -m src download --categories cs.AI --date 2025 --max 10

# 按月份范围
python -m src download --categories cs.AI,cs.CV --date 2025-03-2025-06 --output papers

# 按关键词
python -m src download --categories cs.CL --date 2025 --keywords "transformer"

# 列出论文
python -m src list --categories cs.AI --date 2025 --max 20

# 安装依赖
pip install -r requirements.txt
```

## Architecture

对标 ACL Anthology Downloader，5 个模块一一对应：

| ACL | Arxiv | 职责 |
|-----|-------|------|
| `scraper.py` | `api_client.py` | 抓取 + 数据处理 |
| `db.py` | `db.py` | MongoDB 操作 |
| `downloader.py` | `downloader.py` | PDF 下载 |
| `cli.py` | `cli.py` | 命令行入口 |
| - | `__main__.py` | 模块入口 |

### 数据流

1. `cli.py` 解析参数 → 调用 `api_client.fetch_papers()` 抓取并处理数据
2. `db.upsert_papers_batch()` 写入 MongoDB
3. `downloader.download_papers()` 下载 PDF 到 `{output}/{category}/{year}/{title}.pdf`
4. `db.mark_completed()` / `db.mark_failed()` 更新状态

### 关键设计

- `pdf_url` 为唯一键（与 ACL 一致）
- arXiv 特有字段: `arxiv_id`, `category`, `published`
- `--date` 支持年/年范围/月/月范围四种格式
- 内置 `APIRateLimiter`，3 秒请求间隔
- 支持断点续传（MongoDB pending/failed 状态）
