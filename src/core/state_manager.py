import os
import json
import logging
from datetime import datetime
from src.utils.helpers import safe_filename


class StateManager:
    """管理每个类别的处理状态"""

    def __init__(self, state_dir="data/state", logger=None):
        """
        初始化状态管理器

        参数:
            state_dir: 状态文件存储目录
            logger: 日志记录器实例
        """
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.logger = logger or logging.getLogger(__name__)

        # 确保logger可用
        if not self.logger:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def get_state_path(self, category):
        """获取类别状态文件路径"""
        safe_name = safe_filename(category)
        return os.path.join(self.state_dir, f"{safe_name}.state")

    def load_state(self, category):
        """
        加载类别状态

        参数:
            category: 类别名称

        返回:
            状态字典
        """
        try:
            state_path = self.get_state_path(category)
            if os.path.exists(state_path):
                try:
                    with open(state_path, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    self.logger.error(f"加载状态失败: {str(e)}")
        except Exception as e:
            pass

        # 默认状态
        return {
            "last_run": None,
            "last_paper_date": None,
            "last_start_index": 0,
            "total_retrieved": 0
        }

    def save_state(self, category, state):
        """
        保存类别状态

        参数:
            category: 类别名称
            state: 状态字典
        """
        state_path = self.get_state_path(category)
        state["last_run"] = datetime.utcnow().isoformat()

        try:
            with open(state_path, 'w') as f:
                json.dump(state, f, indent=2)
            self.logger.debug(f"状态已保存: {state_path}")
        except Exception as e:
            self.logger.error(f"保存状态失败: {str(e)}")