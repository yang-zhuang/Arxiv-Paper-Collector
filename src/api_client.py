"""arXiv 论文抓取模块 — 对标 ACL 的 scraper.py，同时负责抓取和处理"""

import re
import html
import time
import random
from collections import deque
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
import feedparser
from tqdm import tqdm
from dateutil import parser as date_parser

BASE_URL = "http://export.arxiv.org/api/query"


# ── 工具函数 ──────────────────────────────────────────────

def clean_filename(name: str) -> str:
    """清理文件名中的非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def safe_filename(text: str) -> str:
    """文件名安全处理（用于类别名等）"""
    return re.sub(r"[^\w-]", "_", text)


# ── Rate Limiter ─────────────────────────────────────────

class APIRateLimiter:
    def __init__(self, base_delay=3, burst_size=5):
        self.base_delay = base_delay
        self.burst_size = burst_size
        self.request_times = deque(maxlen=burst_size)

    def wait(self):
        now = time.time()
        if len(self.request_times) >= self.burst_size:
            elapsed = now - self.request_times[0]
            if elapsed < self.base_delay * self.burst_size:
                wait_time = max(0, self.base_delay * self.burst_size - elapsed)
                time.sleep(wait_time + random.uniform(0, 1))
        self.request_times.append(time.time())


# ── 查询构建 ─────────────────────────────────────────────

def _build_query(category=None, start_date=None, end_date=None,
                 days=None, keywords=None, authors=None, match_all_authors=False):
    """构建 arXiv API 搜索查询字符串

    start_date/end_date 格式: 'YYYYMMDD' (如 '20250301')
    """
    parts = []

    if category:
        parts.append(f"cat:{category}")

    # 时间范围
    if days is not None:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        parts.append(f"submittedDate:[{start} TO *]")
    elif start_date and end_date:
        parts.append(f"submittedDate:[{start_date} TO {end_date}]")
    elif start_date:
        parts.append(f"submittedDate:[{start_date} TO *]")

    # 关键词
    if keywords:
        if isinstance(keywords, str):
            keywords = [keywords]
        kw_parts = [f"(ti:{quote(k)} OR abs:{quote(k)})" for k in keywords]
        parts.append(f"({' AND '.join(kw_parts)})" if len(kw_parts) > 1 else kw_parts[0])

    # 作者
    if authors:
        if isinstance(authors, str):
            authors = [authors]
        au_parts = [f"au:{quote(a)}" for a in authors]
        join = " AND " if match_all_authors else " OR "
        parts.append(f"({join.join(au_parts)})")

    return " AND ".join(f"({p})" for p in parts)


# ── 数据提取 ─────────────────────────────────────────────

def _parse_entry(entry, category):
    """从 feedparser 条目中提取论文信息，返回标准字典"""
    # 提取 arxiv_id
    id_str = entry.get('id', '')
    arxiv_id = id_str.split('/')[-1] if id_str else ""

    # 提取 pdf_url
    pdf_url = ""
    for link in entry.get('links', []):
        if link.get('type') == 'application/pdf':
            pdf_url = link.get('href', '')
            break
    if not pdf_url and arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # 提取年份
    published_str = ""
    year = 0
    raw_published = entry.get('published', '')
    if raw_published:
        try:
            dt = date_parser.parse(raw_published)
            published_str = dt.isoformat()
            year = dt.year
        except Exception:
            pass

    # 提取摘要
    abstract = entry.get('summary', '')
    if abstract:
        abstract = html.unescape(abstract)
        abstract = re.sub(r'\s+', ' ', abstract).strip()

    # 提取标题
    title = entry.get('title', '')
    if title:
        title = html.unescape(title)
        title = re.sub(r'\s+', ' ', title).strip()

    # 提取作者
    authors = []
    for a in entry.get('authors', []):
        name = a.get('name', '').strip()
        if name:
            authors.append(name)

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "category": category,
        "year": year,
        "published": published_str,
        "pdf_url": pdf_url,
    }


# ── 主入口 ───────────────────────────────────────────────

_rate_limiter = APIRateLimiter(base_delay=3)


def fetch_papers(
    category: str,
    start_date: str,
    end_date: str,
    max_papers: int | None = None,
    keywords=None,
    authors=None,
    days=None,
    match_all_authors=False,
    db=None,
) -> list[dict]:
    """获取论文信息（主入口函数，对标 ACL 的 collect_paper_info）

    Args:
        category: arXiv 类别 (如 "cs.AI")
        start_date: 起始日期 'YYYYMMDD'
        end_date: 结束日期 'YYYYMMDD'
        max_papers: 最大获取数量
        keywords: 关键词列表
        authors: 作者列表
        days: 最近N天（优先于日期范围）
        match_all_authors: 是否匹配所有作者
        db: 可选数据库连接（用于增量抓取）

    Returns:
        论文信息列表
    """
    query = _build_query(category, start_date, end_date, days,
                         keywords, authors, match_all_authors)
    print(f"  搜索: {query}")

    # 增量抓取：跳过已完成的论文
    completed_urls = set()
    if db is not None:
        from src.db import get_existing_papers
        completed_urls = get_existing_papers(db, category,
                                             start_year=int(start_date[:4]),
                                             end_year=int(end_date[:4]))
        if completed_urls:
            print(f"  跳过 {len(completed_urls)} 篇已完成论文")

    all_papers = []
    start_index = 0
    remaining = max_papers or 999999

    while remaining > 0:
        batch_size = min(100, remaining)

        params = {
            "search_query": query,
            "start": start_index,
            "max_results": batch_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        # 带重试的请求
        feed = None
        for attempt in range(3):
            try:
                _rate_limiter.wait()
                resp = requests.get(BASE_URL, params=params, timeout=60)
                resp.raise_for_status()
                feed = feedparser.parse(resp.content)
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    print(f"  请求失败: {e}")
                    return all_papers

        if not feed or not feed.entries:
            break

        for entry in feed.entries:
            if max_papers is not None and len(all_papers) >= max_papers:
                return all_papers

            paper = _parse_entry(entry, category)

            # 跳过无 pdf_url 或已完成的
            if not paper["pdf_url"]:
                continue
            if paper["pdf_url"] in completed_urls:
                continue

            all_papers.append(paper)

        start_index += len(feed.entries)

        if len(feed.entries) < batch_size:
            break

    return all_papers
