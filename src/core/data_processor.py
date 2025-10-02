import re
import html
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dateutil import parser as date_parser


class DataProcessor:
    """处理从arXiv API获取的原始数据"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化数据处理器

        参数:
            logger: 日志记录器实例 (可选)
        """
        self.logger = logger or logging.getLogger(__name__)

        # 确保logger可用
        if not self.logger:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 编译常用正则表达式
        self.title_clean_regex = re.compile(r'\s+', re.UNICODE)
        self.author_name_regex = re.compile(r'^[a-zA-Z\s\-\'\.]+$')
        self.arxiv_id_regex = re.compile(r'^(\d{4}\.\d{4,5}|[a-z\-]+/\d{7})(v\d+)?$')
        self.whitespace_regex = re.compile(r'\s+')

    def process_entry(self, raw_entry: Dict[str, Any], category: str, validate_entry:bool = False) -> Dict[str, Any]:
        """
        处理单个arXiv条目

        参数:
            raw_entry: 从API获取的原始条目数据
            category: 论文所属类别

        返回:
            处理后的标准化论文数据
        """
        try:
            # 基本字段提取
            processed = {
                "arxiv_id": self._extract_arxiv_id(raw_entry.get('id', '')),
                "title": self._clean_text(raw_entry.get('title', '')),
                "abstract": self._clean_text(raw_entry.get('summary', '')),
                "authors": self._process_authors(raw_entry.get('authors', [])),
                "category": category,
                "published": self._parse_date(raw_entry.get('published', '')),
                "updated": self._parse_date(raw_entry.get('updated', '')),
                "primary_category": self._extract_primary_category(raw_entry),
                "categories": self._extract_categories(raw_entry),
                "doi": self._extract_doi(raw_entry),
                "links": self._extract_links(raw_entry),
                "comment": self._clean_text(raw_entry.get('arxiv_comment', '')),
                "journal_ref": self._clean_text(raw_entry.get('arxiv_journal_ref', '')),
                "affiliation": self._extract_affiliation(raw_entry),
            }

            # 验证数据完整性
            if validate_entry:
                self._validate_entry(processed)

            # 添加处理元数据
            processed["processed_at"] = datetime.utcnow().isoformat()

            return processed

        except Exception as e:
            self.logger.error(f"处理条目时出错: {str(e)}")
            self.logger.debug(f"原始条目: {raw_entry}")
            raise

    def _extract_arxiv_id(self, id_str: str) -> str:
        """
        从arXiv URL中提取论文ID

        示例:
            输入: "http://arxiv.org/abs/1706.03762v5"
            输出: "1706.03762v5"
        """
        if not id_str:
            return ""

        # 提取ID部分
        id_parts = id_str.split('/')
        arxiv_id = id_parts[-1] if id_parts else ""

        # 验证ID格式
        if not self.arxiv_id_regex.match(arxiv_id):
            self.logger.warning(f"无效的arXiv ID格式: {arxiv_id}")

        return arxiv_id

    def _clean_text(self, text: str) -> str:
        """
        清理文本数据:
        1. 解码HTML实体
        2. 移除多余空白
        3. 标准化换行符
        4. 移除前后空白
        """
        if not text:
            return ""

        # 解码HTML实体
        cleaned = html.unescape(text)

        # 替换换行符为空格
        cleaned = cleaned.replace('\n', ' ').replace('\r', ' ')

        # 移除多余空白
        cleaned = self.whitespace_regex.sub(' ', cleaned).strip()

        return cleaned

    def _process_authors(self, authors: List[Dict[str, str]]) -> List[str]:
        """
        处理作者列表:
        1. 提取作者姓名
        2. 清理姓名中的多余空白
        3. 验证姓名格式
        """
        processed_authors = []

        for author in authors:
            name = author.get('name', '').strip()
            if not name:
                continue

            # 清理姓名
            cleaned_name = self._clean_author_name(name)

            # 验证姓名格式
            if cleaned_name and self._validate_author_name(cleaned_name):
                processed_authors.append(cleaned_name)
            else:
                self.logger.warning(f"跳过无效作者名: {name}")

        return processed_authors

    def _clean_author_name(self, name: str) -> str:
        """清理作者姓名"""
        # 移除姓名中的多余空白
        cleaned = self.whitespace_regex.sub(' ', name).strip()

        # 注意：capitalize() 会把 'é' 后的字母变小写，但对首字母有效
        # 更安全的方式是 title()，但需注意 O'Neil 这类名字
        # 这里简单使用 title()，或保留原大小写（很多学术姓名大小写敏感）
        # 但按你原意：首字母大写每个部分
        parts = []
        for part in cleaned.split():
            # 使用 title() 可能有问题（如 "McDonald"），但简单场景可用
            # 更保守：只首字母大写，其余不变？但你原逻辑是 capitalize()
            parts.append(part.capitalize())
        return ' '.join(parts)

    def _validate_author_name(self, name: str) -> bool:
        """验证作者姓名格式"""
        allowed_extra = {".", " ", '-', "'"}

        for char in name:
            if char in allowed_extra:
                continue
            if not char.isalpha():
                return False

        # 确保至少包含一个字母（防止如 " - ' " 这样的无效输入）
        if not any(char.isalpha() for char in name):
            return False

        return True

    def _parse_date(self, date_str: str) -> str:
        """解析日期并转换为ISO格式"""
        if not date_str:
            return ""

        try:
            dt = date_parser.parse(date_str)
            return dt.isoformat()
        except Exception:
            self.logger.warning(f"无法解析日期: {date_str}")
            return ""

    def _extract_primary_category(self, entry: Dict[str, Any]) -> str:
        """提取主要类别"""
        primary = entry.get('arxiv_primary_category', {})
        term = primary.get('term', '')
        return self._clean_category(term)

    def _extract_categories(self, entry: Dict[str, Any]) -> List[str]:
        """提取所有类别"""
        categories = []
        for tag in entry.get('tags', []):
            term = tag.get('term', '')
            if term:
                cleaned = self._clean_category(term)
                if cleaned:
                    categories.append(cleaned)
        return list(set(categories))  # 去重

    def _clean_category(self, category: str) -> str:
        """清理类别字符串"""
        if not category:
            return ""

        # 移除arXiv前缀 (如果存在)
        if category.startswith("arXiv:"):
            category = category[5:]

        # 标准化类别格式
        return category.replace(' ', '.').lower()

    def _extract_doi(self, entry: Dict[str, Any]) -> str:
        """提取DOI标识符"""
        links = entry.get('links', [])
        for link in links:
            if link.get('rel') == 'doi' and link.get('title') == 'doi':
                return link.get('href', '').replace('https://doi.org/', '')
        return ""

    def _extract_links(self, entry: Dict[str, Any]) -> List[Dict[str, str]]:
        """提取相关链接"""
        processed_links = []
        links = entry.get('links', [])

        for link in links:
            try:
                link_type = link.get('rel', 'other')
                if link_type == 'alternate':
                    link_type = 'abstract'

                processed_links.append({
                    "type": link_type,
                    "url": link.get('href', ''),
                    "title": link.get('title', '')
                })
            except Exception:
                self.logger.warning("处理链接时出错")

        return processed_links

    def _extract_affiliation(self, entry: Dict[str, Any]) -> List[Dict[str, str]]:
        """提取作者机构信息"""
        affiliations = []
        authors = entry.get('authors', [])

        for author in authors:
            try:
                name = author.get('name', '')
                affil = author.get('arxiv_affiliation', '')

                if name and affil:
                    affiliations.append({
                        "author": self._clean_author_name(name),
                        "affiliation": self._clean_text(affil)
                    })
            except Exception:
                self.logger.warning(f"提取机构信息时出错: {author}")

        return affiliations

    def _validate_entry(self, entry: Dict[str, Any]):
        """验证处理后的条目数据完整性"""
        # 必需字段检查
        required_fields = ["arxiv_id", "title", "abstract", "authors", "published"]
        for field in required_fields:
            if not entry.get(field):
                raise ValueError(f"缺少必需字段: {field}")

        # 特殊字段验证
        if not self.arxiv_id_regex.match(entry["arxiv_id"]):
            raise ValueError(f"无效的arXiv ID格式: {entry['arxiv_id']}")

        if len(entry["authors"]) == 0:
            self.logger.warning("条目没有作者信息")

        # 标题和摘要长度验证
        if len(entry["title"]) < 5:
            raise ValueError(f"标题过短: {entry['title']}")

        if len(entry["abstract"]) < 50:
            self.logger.warning(f"摘要可能过短: {entry['arxiv_id']}")

    def batch_process(self, raw_entries: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
        """
        批量处理多个条目

        参数:
            raw_entries: 原始条目列表
            category: 论文类别

        返回:
            处理后的条目列表
        """
        processed = []
        total = len(raw_entries)

        for i, entry in enumerate(raw_entries):
            try:
                processed.append(self.process_entry(entry, category))

                # 每处理50条记录一次进度
                if self.logger and (i + 1) % 50 == 0:
                    self.logger.info(f"已处理 {i + 1}/{total} 条条目")

            except Exception as e:
                if self.logger:
                    self.logger.error(f"处理条目失败: {str(e)}")
                    self.logger.debug(f"原始条目: {entry}")

        if self.logger:
            self.logger.info(f"完成处理 {len(processed)}/{total} 条条目")

        return processed

    # 在DataProcessor类中添加以下方法
    def _extract_pdf_url(self, entry: Dict[str, Any]) -> str:
        """提取PDF URL"""
        links = entry.get('links', [])
        for link in links:
            if link.get('rel') == 'alternate' and link.get('type') == 'application/pdf':
                return link.get('href', '')

        # 如果未找到，构建默认URL
        arxiv_id = self._extract_arxiv_id(entry.get('id', ''))
        if arxiv_id:
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        return ""

# 示例使用
if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("data_processor")

    # 创建处理器
    processor = DataProcessor(logger)

    # 模拟数据
    sample_entry = {
        "id": "http://arxiv.org/abs/1706.03762v5",
        "title": "Attention Is All You Need  \n",
        "summary": "We propose a new simple network architecture...\n",
        "authors": [
            {"name": "Vaswani, Ashish", "arxiv_affiliation": "Google Brain"},
            {"name": "Shazeer, Noam", "arxiv_affiliation": "Google Research"},
            {"name": "Jones, 123Invalid", "arxiv_affiliation": ""},
        ],
        "published": "2017-06-12T18:00:00Z",
        "updated": "2023-02-15T14:30:00Z",
        "arxiv_primary_category": {"term": "cs.CL"},
        "tags": [{"term": "cs.CL"}, {"term": "cs.LG"}],
        "links": [
            {"rel": "alternate", "href": "http://arxiv.org/abs/1706.03762v5"},
            {"rel": "doi", "href": "https://doi.org/10.48550/arXiv.1706.03762"}
        ],
        "arxiv_comment": "Published in NeurIPS 2017",
        "arxiv_journal_ref": "Advances in Neural Information Processing Systems 30 (2017)"
    }

    # 处理条目
    processed = processor.process_entry(sample_entry, "cs.CL")

    # 打印结果
    print("\n处理后的条目:")
    for key, value in processed.items():
        if isinstance(value, list):
            print(f"{key}:")
            for item in value:
                print(f"  - {item}")
        else:
            print(f"{key}: {value}")