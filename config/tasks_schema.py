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
    "on_no_results": "warn",  # 可选值: "warn", "raise", "silent"
    "show_results": True,  # 是否显示搜索到的论文列表
}

VALID_TASK_KEYS = set(CLI_DEFAULTS.keys()) | {"group", "subgroup"}


def load_tasks(path: str) -> list[dict]:
    """从 YAML 文件加载任务列表，支持三层嵌套分组结构，合并 defaults，返回完整任务字典列表。

    支持两种结构：
    1. 扁平结构（旧版）: tasks: [...]
    2. 嵌套结构（新版）: groups: {category: {subgroup: [...]}}

    Args:
        path: YAML 文件路径。

    Returns:
        任务字典列表，每个字典包含所有参数键，以及 group 和 subgroup 字段。

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

    # 优先尝试加载嵌套结构（新版）
    groups = data.get("groups")
    if groups and isinstance(groups, dict):
        return _load_nested_groups(groups, defaults)

    # 兼容旧版扁平结构
    tasks_raw = data.get("tasks")
    if not tasks_raw or not isinstance(tasks_raw, list):
        raise ValueError("YAML 中缺少 'groups' 或 'tasks'，或格式不正确")

    tasks = []
    for i, task in enumerate(tasks_raw):
        merged = _merge_defaults(task, defaults)
        # 补齐 CLI 默认值中仍然缺失的键
        for key, value in CLI_DEFAULTS.items():
            if key not in merged:
                merged[key] = value
        _validate_task(merged, i)
        tasks.append(merged)

    return tasks


def _load_nested_groups(groups: dict, defaults: dict) -> list[dict]:
    """从三层嵌套结构加载任务：groups > category > subgroup > tasks

    Args:
        groups: {category: {subgroup: [tasks]}} 或 {category: [tasks]}（两层结构）
        defaults: 全局默认值

    Returns:
        任务字典列表，每个任务带有 group 和 subgroup 字段
    """
    tasks = []
    task_counter = 0

    for category, subgroups in groups.items():
        # 检查是否为两层结构（直接是任务列表）
        if isinstance(subgroups, list):
            for task in subgroups:
                merged = _merge_defaults(task, defaults)
                merged["group"] = category
                merged["subgroup"] = ""
                _fill_defaults(merged)
                _validate_task(merged, task_counter)
                tasks.append(merged)
                task_counter += 1
            continue

        # 三层结构：category > subgroup > tasks
        if not isinstance(subgroups, dict):
            raise ValueError(f"分组 '{category}' 应为 dict 或 list，得到: {type(subgroups).__name__}")

        for subgroup, task_list in subgroups.items():
            if not isinstance(task_list, list):
                raise ValueError(f"子分组 '{category} > {subgroup}' 应为 list，得到: {type(task_list).__name__}")

            for task in task_list:
                merged = _merge_defaults(task, defaults)
                merged["group"] = category
                merged["subgroup"] = subgroup
                _fill_defaults(merged)
                _validate_task(merged, task_counter)
                tasks.append(merged)
                task_counter += 1

    return tasks


def _fill_defaults(task: dict) -> None:
    """补齐 CLI 默认值中缺失的键（就地修改）"""
    for key, value in CLI_DEFAULTS.items():
        if key not in task:
            task[key] = value


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
    keywords = task.get("keywords", "")
    task_id = keywords[:50] + "..." if len(keywords) > 50 else keywords

    # 检查未知键
    unknown = set(task.keys()) - VALID_TASK_KEYS
    if unknown:
        raise ValueError(f"{task_id}: 未知参数 {unknown}")

    if not task.get("categories"):
        raise ValueError(f"{task_id}: 'categories' 不能为空")

    if not task.get("date") and not task.get("days"):
        raise ValueError(f"{task_id}: 必须提供 'date' 或 'days' 之一")

    if task.get("max") is not None and task["max"] <= 0:
        raise ValueError(f"{task_id}: 'max' 必须为正整数")

    if task.get("days") is not None and task["days"] <= 0:
        raise ValueError(f"{task_id}: 'days' 必须为正整数")

    # 校验 on_no_results
    on_no_results = task.get("on_no_results", "warn")
    if on_no_results not in ("warn", "raise", "silent"):
        raise ValueError(f"{task_id}: 'on_no_results' 必须是 'warn', 'raise' 或 'silent'")

    # 校验 show_results
    show_results = task.get("show_results", True)
    if not isinstance(show_results, bool):
        raise ValueError(f"{task_id}: 'show_results' 必须是布尔值")
