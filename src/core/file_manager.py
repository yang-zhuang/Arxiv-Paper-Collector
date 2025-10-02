import os

class StorageManager:
    def __init__(self, output_root):
        self.output_root = output_root

    def get_category_path(self, category, date=None):
        """获取类别存储路径"""
        safe_name = category.replace(".", "-")
        return f"{self.output_root}/{safe_name}"

    def save_batch(self, category, papers):
        """增量写入JSONL文件"""
        path = self.get_category_path(category)
        os.makedirs(path, exist_ok=True)
        # 写入逻辑...