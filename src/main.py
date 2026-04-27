"""命令行入口"""

import argparse
import re
import sys


def parse_date_range(s):
    """解析日期范围字符串。支持: 2025 / 2024-2025 / 2025-03 / 2025-03-2025-06"""
    s = s.strip()
    match = re.match(r'^(\d{4})(?:-(\d{2}))?\s*(?:-\s*(\d{4})(?:-(\d{2}))?)?$', s)
    if not match:
        raise argparse.ArgumentTypeError(
            f"日期格式错误，支持: 2025 / 2024-2025 / 2025-03 / 2025-03-2025-06，得到: {s}"
        )

    from calendar import monthrange
    from datetime import date

    now = date.today()
    g1, g2, g3, g4 = match.group(1), match.group(2), match.group(3), match.group(4)

    if g3 is None:
        year = int(g1)
        start = f"{year}{int(g2):02d}01" if g2 else f"{year}0101"
        _, last_day = monthrange(now.year, now.month)
        end = f"{now.year}{now.month:02d}{last_day}"
    else:
        start_year, end_year = int(g1), int(g3)
        start_month = int(g2) if g2 else 1
        end_month = int(g4) if g4 else 12
        start = f"{start_year}{start_month:02d}01"
        _, last_day = monthrange(end_year, end_month)
        end = f"{end_year}{end_month:02d}{last_day}"

    return start, end


def _format_date_range_display(start, end):
    def fmt(d):
        return f"{d[:4]}-{d[4:6]}" if len(d) >= 6 else d[:4]
    return f"{fmt(start)} ~ {fmt(end)}"


def _build_task_display_name(task):
    """构建任务显示名，如 [Group] Subgroup > keywords"""
    parts = []
    if task.get("group"):
        parts.append(f"[{task['group']}]")
    if task.get("subgroup"):
        parts.append(task['subgroup'])
    kw = task.get("keywords", "")
    parts.append(kw[:50] + "..." if len(kw) > 50 else kw)
    return " > ".join(parts) if parts else "Task"


def _override_yaml_with_cli(task, cli_args):
    """用 CLI 参数覆盖 YAML 任务配置"""
    for key in ("categories", "output", "max", "keywords", "authors", "days", "uri"):
        val = getattr(cli_args, key, None)
        if val:
            task[key] = val
    return task


def load_yaml_tasks(file_path, group=None, subgroup=None):
    """从 YAML 加载任务，按 group/subgroup 过滤"""
    from config.tasks_schema import load_tasks

    all_tasks = load_tasks(file_path)
    matched = [t for t in all_tasks
               if (not group or t.get("group") == group)
               and (subgroup is None or t.get("subgroup") == subgroup)]

    if not matched:
        info = f"group='{group}'" if group else "any group"
        info += f", subgroup='{subgroup}'" if subgroup is not None else ""
        raise ValueError(f"No tasks found in {file_path} with {info}")

    print(f"从配置文件加载了 {len(matched)} 个匹配的任务")
    return matched


def execute_download(task_config, db=None):
    """执行一次下载任务。date 应为 (start_date, end_date) 元组。"""
    from src.api_client import fetch_papers
    from src.downloader import download_papers
    from src.db import get_db, upsert_papers_batch, get_pending_papers, get_stats, close

    categories = [c.strip() for c in task_config["categories"].split(",") if c.strip()]
    start_date, end_date = task_config["date"]
    max_papers = task_config["max"]

    own_db = db is None
    if own_db:
        db = get_db(task_config["uri"])

    try:
        display_name = _build_task_display_name(task_config)
        print(f"\n{'=' * 60}\n  {display_name}\n{'=' * 60}")
        print(f"  类别: {', '.join(categories)}  |  日期: {_format_date_range_display(start_date, end_date)}")

        # 获取未完成论文
        pending_papers = []
        for cat in categories:
            pending_papers.extend(get_pending_papers(db, category=cat,
                                                      start_year=int(start_date[:4]),
                                                      end_year=int(end_date[:4])))
        print(f"  数据库中有 {len(pending_papers)} 篇未完成论文（pending/failed）")

        # 从 API 获取新论文
        need_count = max(0, max_papers - len(pending_papers))
        new_papers = []
        if need_count > 0:
            print(f"  需要再获取 {need_count} 篇新论文")
            kw_list = [k.strip() for k in task_config["keywords"].split(",")] if task_config.get("keywords") else None
            au_list = [a.strip() for a in task_config["authors"].split(",")] if task_config.get("authors") else None
            per_cat = max(1, need_count // len(categories))
            for cat in categories:
                new_papers.extend(fetch_papers(cat, start_date, end_date, max_papers=per_cat,
                                               keywords=kw_list, authors=au_list,
                                               days=task_config.get("days"), db=db))
            print(f"  从 arXiv API 获取到 {len(new_papers)} 篇新论文")
            if task_config.get("show_results", True) and new_papers:
                print(f"\n  搜索到的论文:")
                for i, p in enumerate(new_papers, 1):
                    print(f"    {i}. [{p.get('year', 'N/A')}] {p.get('title', 'N/A')}")
                print()
        else:
            print("  数据库中的论文已足够，无需获取新论文")

        # 保存到数据库
        if new_papers:
            count = upsert_papers_batch(db, new_papers, source="arxiv")
            print(f"  已保存 {count} 篇新论文到数据库")

        # 合并去重
        papers_by_url = {p["pdf_url"]: p for p in pending_papers}
        for p in new_papers:
            papers_by_url[p["pdf_url"]] = p
        papers = list(papers_by_url.values())[:max_papers]
        print(f"  合并后共 {len(papers)} 篇论文待下载（限制: max={max_papers}）")

        if not papers:
            if task_config.get("on_no_results", "warn") == "raise":
                raise ValueError("未找到任何论文")
            elif task_config.get("on_no_results", "warn") == "warn":
                print("  [WARNING] 未找到任何论文")
            return

        # 下载 PDF
        print(f"\n  找到 {len(papers)} 篇论文，开始下载...")
        count = download_papers(papers, task_config["output"], db=db)
        print(f"  下载完成！成功 {count} 篇")

        # 统计
        for cat in categories:
            print(f"    {cat}: {get_stats(db, category=cat)}")
    finally:
        if own_db:
            close()


def execute_download_tasks(tasks, stop_on_error=False):
    """顺序执行多个下载任务，共享数据库连接。"""
    from src.db import get_db, close

    db = get_db(tasks[0].get("uri", "mongodb://localhost:27017"))
    ok, fail, errors = 0, 0, []

    for i, task in enumerate(tasks, 1):
        display_name = _build_task_display_name(task)
        print(f"\n[{i}/{len(tasks)}] 执行: {display_name}")
        try:
            execute_download(task, db=db)
            ok += 1
            print("  [OK] 完成")
        except Exception as e:
            fail += 1
            errors.append((display_name, str(e)))
            print(f"  [FAIL] 失败: {e}")
            if stop_on_error:
                print("因错误终止执行")
                break

    close()
    print(f"\n{'=' * 60}")
    print(f"执行完成: {ok} 成功, {fail} 失败, 共 {len(tasks)} 个任务")
    if errors:
        print("\n失败任务:")
        for name, err in errors:
            print(f"  - {name}: {err}")


def main():
    parser = argparse.ArgumentParser(
        description="arXiv 论文下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python -m src.main --group \"Policy Optimization\" --subgroup \"GRPO\"\n"
               "  python -m src.main --group \"Policy Optimization\"\n"
               "  python -m src.main --file config/tasks.yaml\n",
    )
    parser.add_argument("--file", "--config", type=str, dest="file", default="../config/tasks.yaml")
    parser.add_argument("--group", type=str)
    parser.add_argument("--subgroup", type=str)
    for key, help_text in [
        ("categories", "arXiv 类别（覆盖 YAML）"), ("date", "日期范围（覆盖 YAML）"),
        ("output", "输出目录（覆盖 YAML）"), ("max", "最大下载数（覆盖 YAML）"),
        ("keywords", "关键词（覆盖 YAML）"), ("authors", "作者（覆盖 YAML）"),
        ("days", "最近 N 天（覆盖 YAML）"), ("uri", "MongoDB 地址（覆盖 YAML）"),
    ]:
        parser.add_argument(f"--{key}", type=int if key in ("max", "days") else str, help=help_text)
    parser.add_argument("--stop-on-error", action="store_true")

    cli_args = parser.parse_args()

    try:
        tasks = load_yaml_tasks(cli_args.file,
                                group=getattr(cli_args, "group", None),
                                subgroup=getattr(cli_args, "subgroup", None))
        cli_date = getattr(cli_args, "date", None)
        for task in tasks:
            if cli_date:
                task["date"] = cli_date
            elif isinstance(task.get("date"), str):
                task["date"] = parse_date_range(task["date"])
            _override_yaml_with_cli(task, cli_args)
        execute_download_tasks(tasks, stop_on_error=getattr(cli_args, "stop_on_error", False))
    except Exception as e:
        print(f"错误: 无法加载配置文件 '{cli_args.file}': {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
