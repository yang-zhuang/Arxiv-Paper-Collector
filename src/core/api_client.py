# src/core/api_client.py
import requests
import feedparser
import time
import random
import logging
from datetime import datetime
from .state_manager import StateManager
from src.utils.api_throttle import APIRateLimiter
import arxiv
from datetime import datetime, timedelta
from urllib.parse import quote
import logging


class ArXivClient:
    """arXiv API 客户端，封装论文获取逻辑"""

    SORT_ASC = "ascending"
    SORT_DESC = "descending"

    def __init__(self, base_url="http://export.arxiv.org/api/query",
                 delay=3, max_retries=3, logger=None,
                 search_config=None):
        """
        初始化API客户端

        参数:
            base_url: arXiv API基础URL
            delay: 请求之间的基础延迟（秒）
            max_retries: 失败请求的最大重试次数
            logger: 日志记录器实例
        """
        self.base_url = base_url
        self.rate_limiter = APIRateLimiter(delay)
        self.state_manager = StateManager()
        self.max_retries = max_retries
        self.logger = logger or logging.getLogger(__name__)
        self.current_state = {}  # 存储当前处理状态

        self.search_config = search_config or {}

        # 确保logger可用
        if not self.logger:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _build_time_query(self):
        """构建时间范围查询"""
        time_config = self.search_config.get("time_range", {})
        time_type = time_config.get("type", "all")

        if time_type == "all":
            return ""

        elif time_type == "last_n_days":
            days = time_config.get("value", 7)
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            return f"submittedDate:[{start_date} TO *]"

        elif time_type == "specific_range":
            start_date = time_config.get("start_date", "").replace("-", "")
            end_date = time_config.get("end_date", "").replace("-", "")
            if start_date and end_date:
                return f"submittedDate:[{start_date} TO {end_date}]"

        return ""

    def _build_keyword_query(self):
        """构建关键词查询"""
        keyword_config = self.search_config.get("keywords", {})
        if not keyword_config.get("enabled", False):
            return ""

        terms = keyword_config.get("terms", [])
        if not terms:
            return ""

        search_fields = keyword_config.get("search_fields", ["title", "abstract"])

        # 构建字段查询
        field_queries = []
        for term in terms:
            if "all" in search_fields:
                field_queries.append(f"all:{quote(term)}")
            else:
                field_parts = []
                if "title" in search_fields:
                    field_parts.append(f"ti:{quote(term)}")
                if "abstract" in search_fields:
                    field_parts.append(f"abs:{quote(term)}")
                if field_parts:
                    field_queries.append(f"({' OR '.join(field_parts)})")

        # 组合所有关键词 (使用 AND 关系)
        if len(field_queries) == 1:
            return field_queries[0]
        else:
            return f"({' AND '.join(field_queries)})"

    def _build_author_query(self):
        """构建作者查询"""
        author_config = self.search_config.get("authors", {})
        if not author_config.get("enabled", False):
            return ""

        authors = author_config.get("names", [])
        if not authors:
            return ""

        # 构建作者查询
        author_queries = [f"au:{quote(author)}" for author in authors]

        # 根据配置使用 AND 或 OR 关系
        if author_config.get("match_all", False):
            return f"({' AND '.join(author_queries)})"
        else:
            return f"({' OR '.join(author_queries)})"

    def build_search_query(self, category):
        """
        构建搜索查询字符串
        参考: arXiv API 查询语法 :cite[1]
        """
        query_parts = []

        # 基础类别查询
        if category is not None:
            query_parts.append(f"cat:{category}")

        # 时间范围查询
        time_query = self._build_time_query()
        if time_query:
            query_parts.append(time_query)

        # 关键词查询
        keyword_query = self._build_keyword_query()
        if keyword_query:
            query_parts.append(keyword_query)

        # 作者查询
        author_query = self._build_author_query()
        if author_query:
            query_parts.append(author_query)

        # 组合所有查询条件
        final_query = " AND ".join(f"({part})" for part in query_parts)
        self.logger.info(f"构建的搜索查询: {final_query}")

        return final_query

    def fetch_papers_old(self, category=None, keywords=None, limit=200,
                      sort_by="submittedDate", sort_order=SORT_DESC):
        """
        获取论文，支持类别、关键词搜索，支持灵活排序

        参数:
            category: arXiv类别 (如 "cs.CV")
            keywords: 搜索关键词，可以是字符串或字符串列表
            limit: 获取的论文数量
            sort_by: 排序字段 ("submittedDate", "updatedDate")
            sort_order: 排序方向 ("ascending" 或 "descending")

        返回:
            论文条目列表
        """
        self.logger.info(f"开始获取论文，类别: {category}, 关键词: {keywords}")

        # 加载类别状态
        state = self.state_manager.load_state(category or (keywords or "default"))
        self.current_state = state

        papers = []
        start_index = state.get("last_start_index", 0)
        total_needed = limit

        # 构建查询条件
        date_filter = ""
        if state.get("last_paper_date"):
            date_filter = f" AND submittedDate:[{state['last_paper_date']} TO *]"

        # 构建搜索查询
        query_parts = []
        if category:
            query_parts.append(f"cat:{category}")
        if keywords:
            if isinstance(keywords, str):
                query_parts.append(f"all:{keywords}")
            elif isinstance(keywords, (list, tuple)):
                query_parts.append(f"all:{' AND '.join(keywords)}")
        if date_filter:
            query_parts.append(date_filter)

        search_query = " AND ".join(query_parts)

        self.logger.debug(f"构建的搜索查询: {search_query}")
        self.logger.debug(f"起始索引: {start_index}, 排序方式: {sort_by}, 排序方向: {sort_order}")

        while total_needed > 0:
            batch_size = min(100, total_needed)  # arXiv API限制

            # 构建请求参数
            params = {
                "search_query": search_query,
                "start": start_index,
                "max_results": batch_size,
                "sortBy": sort_by,
                # "sortBy": arxiv.SortCriterion.SubmittedDate,  # 按提交日期排序
                "sortOrder": sort_order,
                # "sortOrder": sort_order=arxiv.SortOrder.Descending      # 降序（最新优先）
            }

            # 带重试机制的请求
            feed = None
            for attempt in range(self.max_retries):
                try:
                    self.rate_limiter.wait()
                    response = requests.get(self.base_url, params=params)
                    response.raise_for_status()
                    feed = feedparser.parse(response.content)
                    break  # 成功则退出重试循环
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        wait_time = (2 ** attempt) + random.random()
                        self.logger.warning(f"请求失败: {str(e)}，等待{wait_time:.1f}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"请求失败，已达最大重试次数: {str(e)}")
                        raise

            if feed is None or not feed.entries:
                self.logger.info(f"没有更多论文，已获取 {len(papers)} 篇")
                break

            # 处理获取到的论文
            for entry in feed.entries:
                papers.append(entry)
                total_needed -= 1
                if total_needed <= 0:
                    break

            # 更新状态
            if feed.entries:
                last_entry = feed.entries[-1]
                state["last_paper_date"] = last_entry.published
                state["last_start_index"] = start_index + len(feed.entries)
                state["total_retrieved"] = state.get("total_retrieved", 0) + len(feed.entries)
                self.current_state = state

            # 更新起始索引
            start_index += len(feed.entries)

            if len(feed.entries) < batch_size:
                self.logger.info(f"没有更多论文，已获取 {len(papers)} 篇")
                break

        # 保存状态到文件
        self.state_manager.save_state(category, state)

        self.logger.info(f"成功获取 {len(papers)} 篇 {category} 论文")
        return papers

    def fetch_papers(self, category=None, limit=200):
        """
        获取论文，支持类别、关键词搜索，支持灵活排序

        参数:
            category: arXiv类别 (如 "cs.CV")
            limit: 获取的论文数量

        返回:
            论文条目列表
        """
        self.logger.info(f"开始获取论文，类别: {category}")

        # 加载类别状态
        state = self.state_manager.load_state(category)
        self.current_state = state

        papers = []
        start_index = state.get("last_start_index", 0)
        total_needed = limit

        # 构建搜索查询
        search_query = self.build_search_query(category)
        self.logger.info(f"搜索条件: {search_query}")

        date_filter = ""
        if state.get("last_paper_date") and not self.search_config.get("time_range"):
            date_filter = f" AND submittedDate:[{state['last_paper_date']} TO *]"
            search_query += date_filter

        while total_needed > 0:
            batch_size = min(100, total_needed)  # arXiv API限制

            # 构建请求参数
            params = {
                "search_query": search_query,
                "start": start_index,
                "max_results": batch_size,
                "sortBy": self.search_config.get("sort_by", "submittedDate"),
                "sortOrder": self.search_config.get("sort_order", "descending")
            }

            # 移除空值参数
            params = {k: v for k, v in params.items() if v is not None}

            # 带重试机制的请求
            feed = None
            for attempt in range(self.max_retries):
                try:
                    self.rate_limiter.wait()
                    response = requests.get(self.base_url, params=params)
                    response.raise_for_status()
                    feed = feedparser.parse(response.content)
                    break  # 成功则退出重试循环
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        wait_time = (2 ** attempt) + random.random()
                        self.logger.warning(f"请求失败: {str(e)}，等待{wait_time:.1f}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"请求失败，已达最大重试次数: {str(e)}")
                        raise

            if feed is None or not feed.entries:
                self.logger.info(f"没有更多论文，已获取 {len(papers)} 篇")
                break

            # 处理获取到的论文
            for entry in feed.entries:
                papers.append(entry)
                total_needed -= 1
                if total_needed <= 0:
                    break

            # 更新状态
            if feed.entries:
                last_entry = feed.entries[-1]
                state["last_paper_date"] = last_entry.published
                state["last_start_index"] = start_index + len(feed.entries)
                state["total_retrieved"] = state.get("total_retrieved", 0) + len(feed.entries)
                self.current_state = state

            # 更新起始索引
            start_index += len(feed.entries)

            if len(feed.entries) < batch_size:
                self.logger.info(f"没有更多论文，已获取 {len(papers)} 篇")
                break

        # 保存状态到文件
        self.state_manager.save_state(category, state)

        self.logger.info(f"成功获取 {len(papers)} 篇 {category} 论文")
        return papers

    def get_current_state(self, category):
        """
        获取当前处理状态

        参数:
            category: 类别名称

        返回:
            当前状态字典
        """
        # 确保返回的状态包含类别信息
        state = self.current_state.copy()
        state["category"] = category
        state["retrieved_at"] = datetime.utcnow().isoformat()
        state["search_config"] = self.search_config
        return state