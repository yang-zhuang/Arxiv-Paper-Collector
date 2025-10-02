import os
import json
from datetime import datetime
from src.utils.helpers import safe_filename


class StorageManager:
    """管理论文数据的存储"""

    def __init__(self, output_root="data/outputs", pdf_root="data/pdfs"):
        self.output_root = output_root
        self.pdf_root = pdf_root
        os.makedirs(pdf_root, exist_ok=True)

    def get_category_dir(self, category):
        """获取类别存储目录"""
        safe_name = safe_filename(category)
        return os.path.join(self.output_root, safe_name)

    def get_output_file(self, category, batch=False, timestamp=None):
        """
        获取输出文件路径

        参数:
            category: 论文类别
            batch: 是否批量模式
            timestamp: 自定义时间戳 (可选)
        """
        dir_path = self.get_category_dir(category)
        os.makedirs(dir_path, exist_ok=True)

        if batch:
            # 使用精确到秒的时间戳
            ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
            return os.path.join(dir_path, f"papers_{ts}.jsonl")
        else:
            # 追加模式：使用统一文件
            return os.path.join(dir_path, "papers.jsonl")

    def save_papers(self, category, papers, batch=False, timestamp=None):
        """
        保存论文到文件

        参数:
            category: 论文类别
            papers: 论文数据列表
            batch: 是否批量模式
            timestamp: 自定义时间戳 (可选)
        """
        output_file = self.get_output_file(category, batch, timestamp)

        with open(output_file, "w", encoding="utf-8") as f:  # 使用'w'模式覆盖旧文件
            for paper in papers:
                f.write(json.dumps(paper, ensure_ascii=False) + "\n")

        return output_file

    def append_papers(self, category, papers):
        """
        追加论文到统一文件
        """
        output_file = self.get_output_file(category, batch=False)

        with open(output_file, "a", encoding="utf-8") as f:
            for paper in papers:
                f.write(json.dumps(paper, ensure_ascii=False) + "\n")

        return output_file

    # 添加获取PDF目录的方法
    def get_pdf_dir(self, category=None, timestamp=None):
        """获取PDF存储目录"""
        if category:
            safe_name = safe_filename(category)
            dir_path = os.path.join(self.pdf_root, safe_name)
        else:
            dir_path = self.pdf_root

        if timestamp:
            dir_path = os.path.join(dir_path, timestamp)

        os.makedirs(dir_path, exist_ok=True)
        return dir_path