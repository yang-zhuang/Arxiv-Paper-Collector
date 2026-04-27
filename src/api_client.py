"""arXiv 论文抓取模块"""

import html
import re
import time
import random
import warnings
from collections import deque
from datetime import datetime, timedelta

import requests
import feedparser
from dateutil import parser as date_parser
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings('ignore', category=InsecureRequestWarning)

BASE_URL = "http://export.arxiv.org/api/query"
_session = requests.Session()
_session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))


class APIRateLimiter:
    def __init__(self, delay=3):
        self.delay = delay
        self._times = deque(maxlen=5)

    def wait(self):
        now = time.time()
        if len(self._times) >= 5 and now - self._times[0] < self.delay * 5:
            time.sleep(self.delay * 5 - (now - self._times[0]) + random.uniform(0, 1))
        self._times.append(time.time())


_rate_limiter = APIRateLimiter()


def _build_query(category, start_date, end_date, days=None, keywords=None, authors=None):
    """构建 arXiv API 查询字符串"""
    parts = []
    if category:
        parts.append(f"cat:{category}")
    if days is not None:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        parts.append(f"submittedDate:[{start} TO *]")
    elif start_date and end_date:
        parts.append(f"submittedDate:[{start_date} TO {end_date}]")
    elif start_date:
        parts.append(f"submittedDate:[{start_date} TO *]")
    if keywords:
        if isinstance(keywords, str):
            keywords = [keywords]
        kw_parts = [f"(ti:{k} OR abs:{k})" for k in keywords]
        parts.append(f"({' AND '.join(kw_parts)})" if len(kw_parts) > 1 else kw_parts[0])
    if authors:
        if isinstance(authors, str):
            authors = [authors]
        parts.append(f"({' AND '.join(f'au:{a}' for a in authors)})")
    return " AND ".join(f"({p})" for p in parts)


def _parse_entry(entry, category):
    """从 feedparser 条目提取论文信息"""
    arxiv_id = entry.get('id', '').split('/')[-1]
    pdf_url = next((l['href'] for l in entry.get('links', [])
                    if l.get('type') == 'application/pdf'), '')
    if not pdf_url and arxiv_id:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    published_str, year = "", 0
    raw = entry.get('published', '')
    if raw:
        try:
            dt = date_parser.parse(raw)
            published_str, year = dt.isoformat(), dt.year
        except Exception:
            pass

    title = re.sub(r'\s+', ' ', html.unescape(entry.get('title', ''))).strip()
    abstract = re.sub(r'\s+', ' ', html.unescape(entry.get('summary', ''))).strip()
    authors = [a.get('name', '').strip() for a in entry.get('authors', []) if a.get('name', '').strip()]

    return {
        "arxiv_id": arxiv_id, "title": title, "abstract": abstract,
        "authors": authors, "category": category, "year": year,
        "published": published_str, "pdf_url": pdf_url,
    }


def fetch_papers(category, start_date, end_date, max_papers=None,
                 keywords=None, authors=None, days=None, db=None) -> list[dict]:
    """获取论文信息（主入口）"""
    query = _build_query(category, start_date, end_date, days, keywords, authors)
    print(f"  搜索: {query}")

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
            "search_query": query, "start": start_index,
            "max_results": batch_size, "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        feed = None
        for attempt in range(3):
            try:
                _rate_limiter.wait()
                resp = _session.get(BASE_URL, params=params, timeout=60, verify=False)
                resp.raise_for_status()
                feed = feedparser.parse(resp.content)
                break
            except requests.exceptions.SSLError as e:
                if attempt < 2:
                    print(f"  SSL 错误 (尝试 {attempt + 1}/3): {e}")
                    time.sleep(3 + attempt * 2)
                else:
                    print(f"  请求失败: {e}")
                    return all_papers
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
            if paper["pdf_url"] and paper["pdf_url"] not in completed_urls:
                all_papers.append(paper)

        start_index += len(feed.entries)
        if len(feed.entries) < batch_size:
            break

    return all_papers
