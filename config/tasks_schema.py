"""批量任务加载与校验"""

from pathlib import Path

import yaml

CLI_DEFAULTS = {
    "categories": "cs.AI",
    "date": "2025",
    "output": "D:/papers/arxiv",
    "max": 100,
    "keywords": None,
    "authors": None,
    "days": None,
    "uri": "mongodb://localhost:27017",
}

VALID_TASK_KEYS = set(CLI_DEFAULTS.keys()) | {"name"}


def load_tasks(path: str) -> list[dict]:
    """从 YAML 文件加载任务列表，合并 defaults，返回完整任务字典列表。

    Args:
        path: YAML 文件路径。

    Returns:
        任务字典列表，每个字典包含所有参数键。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: YAML 格式错误或无任务。
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"任务文件不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or not isinstance(data, dict):
        raise ValueError(f"YAML 格式错误: 顶层应为 dict，得到: {type(data).__name__}")

    defaults = data.get("defaults", {})
    tasks_raw = data.get("tasks")

    if not tasks_raw or not isinstance(tasks_raw, list):
        raise ValueError("YAML 中缺少 'tasks' 列表或为空")

    tasks = []
    for i, task in enumerate(tasks_raw):
        merged = _merge_defaults(task, defaults)
        # 补齐 CLI 默认值中仍然缺失的键
        for key, value in CLI_DEFAULTS.items():
            if key not in merged:
                merged[key] = value
        _validate_task(merged, i)
        if "name" not in merged:
            merged["name"] = f"Task {i + 1}"
        tasks.append(merged)

    return tasks


def _merge_defaults(task: dict, defaults: dict) -> dict:
    """将任务与 defaults 合并，任务值优先。"""
    merged = {}
    for key, value in defaults.items():
        if key != "name":
            merged[key] = value
    for key, value in task.items():
        merged[key] = value
    return merged


def _validate_task(task: dict, index: int) -> None:
    """校验单个任务字典，不合法则抛 ValueError。"""
    name = task.get("name", f"Task {index + 1}")

    # 检查未知键
    unknown = set(task.keys()) - VALID_TASK_KEYS
    if unknown:
        raise ValueError(f"{name}: 未知参数 {unknown}")

    if not task.get("categories"):
        raise ValueError(f"{name}: 'categories' 不能为空")

    if not task.get("date") and not task.get("days"):
        raise ValueError(f"{name}: 必须提供 'date' 或 'days' 之一")

    if task.get("max") is not None and task["max"] <= 0:
        raise ValueError(f"{name}: 'max' 必须为正整数")

    if task.get("days") is not None and task["days"] <= 0:
        raise ValueError(f"{name}: 'days' 必须为正整数")
