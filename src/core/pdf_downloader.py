# src/core/pdf_downloader.py
import os
import requests
import time
import logging
import random
from urllib.parse import urljoin
from tqdm import tqdm
from src.utils.api_throttle import APIRateLimiter
import re


def safe_arxiv_id(arxiv_id):
    """确保arXiv ID安全用于文件名"""
    # 替换特殊字符
    return re.sub(r'[\\/*?:"<>|]', '_', arxiv_id).replace('/', '_')


class PDFDownloader:
    """处理arXiv论文PDF的下载"""

    def __init__(self, base_url="https://arxiv.org/",
                 pdf_dir="data/pdfs",
                 delay=3, max_retries=3, logger=None):
        """
        初始化PDF下载器

        参数:
            base_url: arXiv基础URL
            pdf_dir: PDF存储目录
            delay: 下载之间的基础延迟（秒）
            max_retries: 失败下载的最大重试次数
            logger: 日志记录器实例
        """
        self.base_url = base_url
        self.pdf_dir = pdf_dir
        self.rate_limiter = APIRateLimiter(delay)
        self.max_retries = max_retries
        self.logger = logger or logging.getLogger(__name__)

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})  # 避免被屏蔽

        # 确保日志可用
        if not self.logger:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 确保目录存在
        os.makedirs(pdf_dir, exist_ok=True)

    def _validate_pdf_url(self, possible_urls):
        """验证并返回第一个有效的PDF URL"""
        for url in possible_urls:
            response = requests.head(url, allow_redirects=True, timeout=10)
            if response.status_code == 200:
                return url
            else:
                return None
        return None

    def _generate_possible_urls(self, arxiv_id, category=None):
        """生成可能的PDF URL列表"""
        urls = []
        if '/' in arxiv_id:  # 处理旧格式
            parts = arxiv_id.split('/')
            urls.append(urljoin(self.base_url, f"pdf/{parts[0]}/{parts[1]}.pdf"))
        else:  # 新格式
            urls.append(urljoin(self.base_url, f"pdf/{arxiv_id}.pdf"))
            if category:
                primary_part = category.split('.')[0] if '.' in category else category
                urls.append(urljoin(self.base_url, f"pdf/{primary_part}/{arxiv_id}.pdf"))
        return urls

    # def get_pdf_url(self, arxiv_id, category=None):
    #     """
    #     获取正确的PDF URL（处理新旧格式）
    #
    #     参数:
    #         arxiv_id: arXiv论文ID (如: "0704.0001", "0704.0001v2", "cs/0010001", "cs.CV/0010001")
    #         category: 论文类别（可选，如 "cs.CV"）
    #
    #     返回:
    #         正确的PDF URL
    #
    #     可能格式:
    #         - 旧格式: [category]/YYMMnumber[vX]
    #         - 新格式: YYYY.MMnumber[vX]
    #     """
    #     # 标准化arxiv_id（去除可能存在的URL编码或空格）
    #     arxiv_id = arxiv_id.split('arxiv.org/abs/')[-1].split('arxiv.org/pdf/')[-1]
    #
    #     # 处理旧格式（包含斜杠）
    #     if '/' in arxiv_id:
    #         # 旧格式: archive/YYMMnumber 或 YYMMnumber
    #         parts = arxiv_id.split('/')
    #         # if len(parts) == 2:
    #         #     # 提取基础ID（去除版本号）
    #         #     base_id = parts[1].split('v')[0]
    #         #     return urljoin(self.base_url, f"pdf/{parts[0]}/{base_id}.pdf")
    #
    #         # 提取基础ID（移除版本号）
    #         base_id = parts[-1].split('v')[0]
    #         if len(parts) == 2:
    #             return f"https://arxiv.org/pdf/{parts[0]}/{base_id}.pdf"
    #         return f"https://arxiv.org/pdf/{base_id}.pdf"
    #
    #
    #     # 处理新格式
    #     if '.' in arxiv_id:
    #         # 提取基础ID（去除版本号）
    #         base_id = arxiv_id.split('v')[0]
    #         # 如果提供了类别，尝试使用类别路径
    #         if category:
    #             primary_part = category.split('.')[0]
    #             return urljoin(self.base_url, f"pdf/{primary_part}/{base_id}.pdf")
    #         return urljoin(self.base_url, f"pdf/{base_id}.pdf")
    #
    #     # 默认处理（可能是数字ID格式）
    #     base_id = arxiv_id.split('v')[0]
    #     return urljoin(self.base_url, f"pdf/{base_id}.pdf")

    def get_pdf_url(self, paper):
        possible_urls = []

        # 从links字段中收集所有可能的PDF URL
        for link in paper.get('links', []):
            if "pdf" == link['title'] and "url" in link:
                url = link['url']
                if self._validate_pdf_url([url]):
                    return url

            if "url" in link:
                possible_urls.append(link['url'])

        # 如果links中有PDF链接，则验证并返回第一个有效的链接
        for url in possible_urls:
            if self._validate_pdf_url([url]):
                return url

        # 如果links中没有可用的PDF链接，则尝试生成可能的PDF URL
        arxiv_id = paper.get('arxiv_id')
        category = paper.get('primary_category')

        generated_urls = self._generate_possible_urls(arxiv_id, category)
        possible_urls.extend(generated_urls)

        valid_url = self._validate_pdf_url(possible_urls)
        return valid_url

    def download_pdf(self, paper, arxiv_id, category, output_dir=None, timestamp=None):
        """
        下载论文PDF

        参数:
            arxiv_id: arXiv论文ID
            category: 论文类别
            output_dir: 自定义输出目录 (可选)
            timestamp: 时间戳 (可选，用于文件名)

        返回:
            下载的PDF文件路径
        """
        # 获取正确的PDF URL
        # pdf_url = self.get_pdf_url(arxiv_id)
        pdf_url = self.get_pdf_url(paper)

        # 确定输出目录
        target_dir = output_dir or self.pdf_dir

        # 创建类别目录
        safe_category = safe_arxiv_id(category)
        category_dir = os.path.join(target_dir, safe_category)
        os.makedirs(category_dir, exist_ok=True)

        # 创建时间戳目录
        if timestamp:
            timestamp_dir = os.path.join(category_dir, timestamp)
            os.makedirs(timestamp_dir, exist_ok=True)
            save_dir = timestamp_dir
        else:
            save_dir = category_dir

        # 安全文件名
        safe_id = safe_arxiv_id(arxiv_id)

        # 确定文件名
        if timestamp:
            filename = f"{safe_id}_{timestamp}.pdf"
        else:
            filename = f"{safe_id}.pdf"

        pdf_path = os.path.join(save_dir, filename)

        # 检查文件是否已存在
        if os.path.exists(pdf_path):
            self.logger.info(f"PDF已存在: {pdf_path}")
            return pdf_path

        # 带重试机制的下载
        for attempt in range(self.max_retries):
            try:
                self.rate_limiter.wait()

                # 使用流式下载
                response = requests.get(pdf_url, stream=True)
                response.raise_for_status()

                # 检查内容类型
                content_type = response.headers.get('Content-Type', '')
                if 'pdf' not in content_type.lower():
                    self.logger.warning(f"URL可能不是PDF: {pdf_url} (Content-Type: {content_type})")
                    return None

                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))

                # 下载文件
                with open(pdf_path, 'wb') as f:
                    with tqdm(total=total_size,
                              unit='B',
                              unit_scale=True,
                              desc=f"下载 {arxiv_id}",
                              disable=not self.logger) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:  # 过滤keep-alive新块
                                f.write(chunk)
                                pbar.update(len(chunk))

                # 验证文件大小
                downloaded_size = os.path.getsize(pdf_path)
                if total_size > 0 and downloaded_size != total_size:
                    raise IOError(f"文件大小不匹配: 预期 {total_size} 字节, 实际 {downloaded_size} 字节")

                self.logger.info(f"PDF下载成功: {pdf_path} (大小: {downloaded_size} 字节)")
                return pdf_path

            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) + random.random()
                    self.logger.warning(f"下载失败: {str(e)}，等待{wait_time:.1f}秒后重试...")
                    time.sleep(wait_time)

                    # 清理可能损坏的文件
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                else:
                    self.logger.error(f"PDF下载失败，已达最大重试次数: {str(e)}")
                    return None

    def download_pdfs(self, papers, category, timestamp=None):
        """
        批量下载论文PDF

        参数:
            papers: 论文数据列表
            category: 论文类别
            timestamp: 时间戳 (可选)

        返回:
            下载统计信息
        """
        stats = {
            "total": len(papers),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "downloaded": []
        }

        for paper in papers:
            arxiv_id = paper.get("arxiv_id")
            if not arxiv_id:
                self.logger.warning("论文缺少arxiv_id，跳过下载")
                stats["skipped"] += 1
                continue

            pdf_path = self.download_pdf(paper, arxiv_id, category, timestamp=timestamp)

            if pdf_path:
                stats["success"] += 1
                stats["downloaded"].append({
                    "arxiv_id": arxiv_id,
                    "category": category,
                    "path": pdf_path
                })
            else:
                stats["failed"] += 1

        return stats