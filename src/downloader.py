"""下载管理模块"""

import os
import re
import time

import requests
from tqdm import tqdm

from src.api_client import APIRateLimiter

_rate_limiter = APIRateLimiter()


def download_pdf(paper: dict, pdf_path: str) -> bool:
    """下载单篇论文 PDF"""
    try:
        if os.path.exists(pdf_path):
            return True

        resp = requests.get(paper["pdf_url"], stream=True, timeout=60)
        if resp.status_code == 200:
            with open(pdf_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        else:
            print(f"下载失败 [{resp.status_code}]: {paper['title']}")
            return False
    except Exception as e:
        print(f"下载PDF出错 '{paper['title']}': {e}")
        return False


def download_papers(papers, output_dir, *, db=None) -> int:
    """下载论文 PDF（主入口函数）

    Args:
        papers: 论文列表 (每个含 arxiv_id, title, pdf_url, category, year)
        output_dir: 输出目录
        db: MongoDB 数据库实例

    Returns:
        成功下载的数量
    """
    os.makedirs(output_dir, exist_ok=True)

    from src.db import mark_completed, mark_failed

    success = 0
    for paper in tqdm(papers, desc="下载论文"):
        try:
            category = paper["category"]
            year = str(paper["year"])
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', paper["title"])

            subdir = os.path.join(output_dir, category, year)
            os.makedirs(subdir, exist_ok=True)
            pdf_path = os.path.join(subdir, f"{safe_title}.pdf")

            _rate_limiter.wait()

            if not download_pdf(paper, pdf_path):
                if db is not None:
                    mark_failed(db, paper["pdf_url"], "PDF下载失败")
                time.sleep(0.5)
                continue

            if db is not None:
                rel_pdf = os.path.join(category, year, f"{safe_title}.pdf")
                mark_completed(db, paper["pdf_url"], rel_pdf)

            success += 1
            time.sleep(0.5)

        except Exception as e:
            print(f"处理出错 '{paper['title']}': {e}")
            if db is not None:
                mark_failed(db, paper["pdf_url"], str(e))

    return success
