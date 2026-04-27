"""命令行入口"""

import argparse
import os
import re
import sys


def parse_date_range(s):
    """解析日期范围字符串，返回 (start_date, end_date) 元组。

    支持格式:
      '2025'           → ('20250101', '{当前年}1231')
      '2025-2026'      → ('20250101', '20261231')
      '2025-03'        → ('20250301', '{当前年}{当前月}最后一天')
      '2025-03-2025-06'→ ('20250301', '20250630')
    仅提供开始时间时，结束时间默认为当前年月。
    """
    s = s.strip()
    pattern = r'^(\d{4})(?:-(\d{2}))?\s*(?:-\s*(\d{4})(?:-(\d{2}))?)?$'
    match = re.match(pattern, s)
    if not match:
        raise argparse.ArgumentTypeError(
            f"日期格式错误，支持: 2025 / 2024-2025 / 2025-03 / 2025-03-2025-06，得到: {s}"
        )

    from calendar import monthrange
    from datetime import date

    now = date.today()
    g1, g2, g3, g4 = match.group(1), match.group(2), match.group(3), match.group(4)

    if g3 is None:
        # 单个年份或年月: '2025' 或 '2025-03'，结束时间默认为当前年月
        year = int(g1)
        if g2:
            start = f"{year}{int(g2):02d}01"
        else:
            start = f"{year}0101"
        _, last_day = monthrange(now.year, now.month)
        end = f"{now.year}{now.month:02d}{last_day}"
    else:
        # 范围: '2024-2025' 或 '2025-03-2025-06'
        start_year = int(g1)
        end_year = int(g3)
        if g2:
            start_month = int(g2)
        else:
            start_month = 1
        if g4:
            end_month = int(g4)
        else:
            end_month = 12

        start = f"{start_year}{start_month:02d}01"
        _, last_day = monthrange(end_year, end_month)
        end = f"{end_year}{end_month:02d}{last_day}"

    return start, end


def _format_range(start, end):
    """将 '20250301' 格式化为可读的 '2025-03' 格式"""
    def fmt(d):
        return f"{d[:4]}-{d[4:6]}" if len(d) >= 6 else d[:4]
    return f"{fmt(start)} ~ {fmt(end)}"


def _load_config_group(file_path: str, group: str = None, subgroup: str = None) -> list[dict]:
    """从 YAML 配置文件加载特定分组的任务列表。

    Args:
        file_path: YAML 文件路径
        group: 大类名称（可选，不指定则加载所有任务）
        subgroup: 子类名称（可选）

    Returns:
        任务列表，每个任务保持独立配置
    """
    from config.tasks_schema import load_tasks

    # 加载所有任务
    all_tasks = load_tasks(file_path)

    # 筛选匹配的任务
    matched_tasks = []
    for task in all_tasks:
        task_group = task.get("group", "")
        task_subgroup = task.get("subgroup", "")

        # 如果指定了 group，必须匹配
        if group and task_group != group:
            continue

        # 如果指定了 subgroup，必须匹配（空字符串也算）
        if subgroup is not None and task_subgroup != subgroup:
            continue

        matched_tasks.append(task)

    if not matched_tasks:
        group_info = f"group='{group}'" if group else "any group"
        subgroup_info = f", subgroup='{subgroup}'" if subgroup is not None else ""
        raise ValueError(f"No tasks found in {file_path} with {group_info}{subgroup_info}")

    # 更新每个任务的 group/subgroup 标识（用于显示）
    for task in matched_tasks:
        if group:
            task["group"] = group
        if subgroup is not None:
            task["subgroup"] = subgroup

    # 打印加载信息
    print(f"从配置文件加载了 {len(matched_tasks)} 个匹配的任务")
    if group:
        print(f"  大类: {group}")
        if subgroup is not None:
            print(f"  子类: {subgroup}")

    return matched_tasks


def _build_task_id(task_params: dict, index: int, total: int) -> str:
    """构建可读的任务标识符。"""
    parts = []
    if task_params.get("group"):
        parts.append(f"[{task_params['group']}]")
    if task_params.get("subgroup"):
        parts.append(task_params['subgroup'])

    keywords = task_params.get("keywords", "")
    short_id = keywords[:50] + "..." if len(keywords) > 50 else keywords
    parts.append(short_id)

    return " > ".join(parts) if parts else f"Task {index}/{total}"


def _merge_tasks(tasks: list[dict]) -> dict:
    """合并多个任务为一个（旧行为）。"""
    if not tasks:
        return {}

    merged = tasks[0].copy()

    if len(tasks) > 1:
        all_keywords = [t.get("keywords", "") for t in tasks if t.get("keywords")]
        merged["keywords"] = " OR ".join(all_keywords)
        total_max = sum(t.get("max", 0) for t in tasks)
        merged["max"] = max(merged.get("max", 0), total_max)

    return merged


def _prepare_date(task_params: dict, args) -> tuple:
    """准备 date 参数，支持 CLI override。"""
    cli_date = getattr(args, "date", None)
    yaml_date = task_params.get("date")

    if cli_date is not None:
        return cli_date
    elif isinstance(yaml_date, tuple):
        return yaml_date
    else:
        return parse_date_range(yaml_date)


def _build_params(task_params: dict, args) -> dict:
    """构建最终参数字典。"""
    return {
        "categories": getattr(args, "categories", None) or task_params.get("categories", "cs.AI"),
        "date": task_params["date"],
        "output": getattr(args, "output", None) or task_params.get("output", "D:/papers/arxiv"),
        "max": getattr(args, "max", None) or task_params.get("max", 10),
        "keywords": getattr(args, "keywords", None) or task_params.get("keywords", ""),
        "authors": getattr(args, "authors", None) or task_params.get("authors"),
        "days": getattr(args, "days", None) or task_params.get("days"),
        "uri": getattr(args, "uri", None) or task_params.get("uri", "mongodb://localhost:27017"),
        "on_no_results": task_params.get("on_no_results", "warn"),
        "show_results": task_params.get("show_results", True),
        "group": task_params.get("group", ""),
        "subgroup": task_params.get("subgroup", ""),
    }


def _apply_cli_overrides(task_params: dict, args) -> dict:
    """应用 CLI 参数覆盖到任务。"""
    result = task_params.copy()

    # 只覆盖显式提供的 CLI 参数
    if getattr(args, "categories", None):
        result["categories"] = args.categories
    if getattr(args, "output", None):
        result["output"] = args.output
    if getattr(args, "max", None):
        result["max"] = args.max
    if getattr(args, "keywords", None):
        result["keywords"] = args.keywords
    if getattr(args, "authors", None):
        result["authors"] = args.authors
    if getattr(args, "days", None):
        result["days"] = args.days
    if getattr(args, "uri", None):
        result["uri"] = args.uri

    return result


def _run_download_loop(tasks: list[dict], db=None, stop_on_error=False):
    """循环执行多个下载任务。

    Args:
        tasks: 任务参数列表
        db: 共享数据库连接
        stop_on_error: 遇错是否停止

    Returns:
        (success_count, fail_count, errors) 元组
    """
    from src.db import get_db, close

    own_db = db is None
    if own_db:
        db = get_db(tasks[0].get("uri", "mongodb://localhost:27017"))

    success_count = 0
    fail_count = 0
    errors = []

    for i, task_params in enumerate(tasks, 1):
        task_id = _build_task_id(task_params, i, len(tasks))
        print(f"\n[{i}/{len(tasks)}] 执行: {task_id}")

        try:
            run_download(task_params, db=db)
            success_count += 1
            print(f"  [OK] 完成")
        except Exception as e:
            fail_count += 1
            errors.append((task_id, str(e)))
            print(f"  [FAIL] 失败: {e}")
            if stop_on_error:
                print("因错误终止执行")
                break

    if own_db:
        close()

    return success_count, fail_count, errors


def _show_execution_summary(success: int, fail: int, errors: list) -> None:
    """显示执行汇总。"""
    print(f"\n{'=' * 60}")
    print(f"执行完成: {success} 成功, {fail} 失败, 共 {success + fail} 个任务")

    if errors:
        print("\n失败任务:")
        for name, err in errors:
            print(f"  - {name}: {err}")


def run_download(params: dict, db=None):
    """执行一次下载任务。

    Args:
        params: 参数字典，包含 categories, date, output, max,
                keywords, authors, days, uri, group, subgroup,
                on_no_results, show_results 等键。
                其中 date 应为 (start_date, end_date) 元组。
        db: 已有的数据库连接。为 None 时自动创建并在完成后关闭。
    """
    from src.api_client import fetch_papers
    from src.downloader import download_papers
    from src.db import get_db, upsert_papers_batch, get_pending_papers, get_stats, close

    keywords = params.get("keywords", "")
    group = params.get("group", "")
    subgroup = params.get("subgroup", "")
    categories = [c.strip() for c in params["categories"].split(",") if c.strip()]
    start_date, end_date = params["date"]
    max_papers = params["max"]
    on_no_results = params.get("on_no_results", "warn")
    show_results = params.get("show_results", True)

    own_db = db is None
    if own_db:
        db = get_db(params["uri"])

    try:
        # 构建任务标题（使用 keywords 作为标识）
        title_parts = []
        if group:
            title_parts.append(f"[{group}]")
        if subgroup:
            title_parts.append(subgroup)

        # 截取 keywords 作为任务名称（最多 60 字符）
        display_name = keywords[:60] + "..." if len(keywords) > 60 else keywords
        title_parts.append(display_name)

        display_title = " > ".join(title_parts)

        print(f"\n{'=' * 60}")
        print(f"  {display_title}")
        print(f"{'=' * 60}")
        print(f"  类别: {', '.join(categories)}  |  日期: {_format_range(start_date, end_date)}")

        # 1. 从数据库获取未完成的论文
        all_pending = []
        for cat in categories:
            pending = get_pending_papers(db, category=cat,
                                         start_year=int(start_date[:4]),
                                         end_year=int(end_date[:4]))
            all_pending.extend(pending)
        print(f"  数据库中有 {len(all_pending)} 篇未完成论文（pending/failed）")

        # 2. 从 arXiv API 获取新论文
        need_count = max(0, max_papers - len(all_pending))
        all_new_papers = []
        if need_count > 0:
            print(f"  需要再获取 {need_count} 篇新论文")
            keywords_list = [k.strip() for k in params["keywords"].split(",")] if params.get("keywords") else None
            authors = [a.strip() for a in params["authors"].split(",")] if params.get("authors") else None

            per_category = max(1, need_count // len(categories))
            for cat in categories:
                papers = fetch_papers(
                    cat, start_date, end_date,
                    max_papers=per_category,
                    keywords=keywords_list, authors=authors,
                    days=params.get("days"), db=db,
                )
                all_new_papers.extend(papers)
            print(f"  从 arXiv API 获取到 {len(all_new_papers)} 篇新论文")

            # 显示搜索到的论文列表
            if show_results and all_new_papers:
                print(f"\n  搜索到的论文:")
                for i, p in enumerate(all_new_papers, 1):
                    print(f"    {i}. [{p.get('year', 'N/A')}] {p.get('title', 'N/A')}")
                print()
        else:
            print("  数据库中的论文已足够，无需获取新论文")

        # 3. 保存新论文到数据库
        if all_new_papers:
            count = upsert_papers_batch(db, all_new_papers, source="arxiv")
            print(f"  已保存 {count} 篇新论文到数据库")

        # 4. 合并 pending + 新论文，去重
        all_papers = {p["pdf_url"]: p for p in all_pending}
        for p in all_new_papers:
            all_papers[p["pdf_url"]] = p
        papers = list(all_papers.values())[:max_papers]
        print(f"  合并后共 {len(papers)} 篇论文待下载（限制: max={max_papers}）")

        if not papers:
            # 根据 on_no_results 决定行为
            if on_no_results == "raise":
                raise ValueError("未找到任何论文")
            elif on_no_results == "warn":
                print("  [WARNING] 未找到任何论文")
            # silent 模式不显示任何信息
            return

        # 5. 下载 PDF
        print(f"\n  找到 {len(papers)} 篇论文，开始下载...")
        count = download_papers(papers, params["output"], db=db)
        print(f"  下载完成！成功 {count} 篇")

        # 6. 显示统计
        for cat in categories:
            stats = get_stats(db, category=cat)
            print(f"    {cat}: {stats}")
    finally:
        if own_db:
            close()


def _handle_batch(args):
    """处理 batch 子命令：加载 YAML 任务文件，逐个执行下载。"""
    from config.tasks_schema import load_tasks
    from src.db import get_db, close

    file_path = args.file
    if not os.path.isabs(file_path):
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), file_path)

    tasks = load_tasks(file_path)

    # CLI --uri 覆盖所有任务的 uri
    if hasattr(args, "uri") and args.uri:
        for task in tasks:
            task["uri"] = args.uri

    # 显示分组概览
    _show_groups_summary(tasks)

    db = get_db(tasks[0]["uri"] if tasks else args.uri)

    success_count = 0
    fail_count = 0
    errors = []

    for i, task_params in enumerate(tasks, 1):
        keywords = task_params.get("keywords", "")

        # 构建任务标识（包含分组信息）
        task_id_parts = []
        if task_params.get("group"):
            task_id_parts.append(f"[{task_params['group']}]")
        if task_params.get("subgroup"):
            task_id_parts.append(task_params['subgroup'])

        # 截取 keywords 作为任务标识（最多 50 字符）
        task_short_id = keywords[:50] + "..." if len(keywords) > 50 else keywords
        task_id_parts.append(task_short_id)

        task_id = " > ".join(task_id_parts) if task_id_parts else f"Task {i}"

        print(f"\n[{i}/{len(tasks)}] 执行: {task_id}")

        try:
            task_params["date"] = parse_date_range(task_params["date"])
            run_download(task_params, db=db)
            success_count += 1
            print(f"  [OK] 完成")
        except Exception as e:
            fail_count += 1
            errors.append((task_id, str(e)))
            print(f"  [FAIL] 失败: {e}")
            if args.stop_on_error:
                print("因 --stop-on-error 终止")
                break

    close()

    print(f"\n{'=' * 60}")
    print(f"批量完成: {success_count} 成功, {fail_count} 失败, 共 {len(tasks)} 个任务")
    if errors:
        print("\n失败任务:")
        for name, err in errors:
            print(f"  - {name}: {err}")


def _show_groups_summary(tasks: list[dict]) -> None:
    """显示任务的分组概览"""
    from collections import defaultdict

    # 统计每个分组的任务数
    groups = defaultdict(lambda: defaultdict(int))
    for task in tasks:
        group = task.get("group", "Ungrouped")
        subgroup = task.get("subgroup", "")
        if subgroup:
            groups[group][subgroup] += 1
        else:
            groups[group][""] += 1

    if not groups:
        print(f"从配置文件加载了 {len(tasks)} 个任务\n")
        return

    print(f"从配置文件加载了 {len(tasks)} 个任务\n")
    print("分组概览:")
    print("-" * 60)

    for group, subgroups in sorted(groups.items()):
        group_total = sum(subgroups.values())
        print(f"\n  [{group}] 共 {group_total} 个任务")

        for subgroup, count in sorted(subgroups.items()):
            if subgroup:
                print(f"    - {subgroup}: {count} 个")
            else:
                print(f"    - (未分组): {count} 个")

    print("\n" + "-" * 60 + "\n")


def _handle_list(categories, start_date, end_date, args):
    """处理 list 子命令"""
    from src.api_client import fetch_papers

    keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    total = 0
    for cat in categories:
        papers = fetch_papers(
            cat, start_date, end_date,
            max_papers=args.max, keywords=keywords,
        )
        print(f"\n[{cat}] 共 {len(papers)} 篇论文:")
        for i, p in enumerate(papers, 1):
            print(f"  {i:3d}. [{p['year']}] {p['title']}")
        total += len(papers)

    print(f"\n总计: {total} 篇论文")


def main():
    parser = argparse.ArgumentParser(
        description="arXiv 论文下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  # 下载特定分组（默认：逐个执行任务）\n"
               "  python -m src.main download --group \"Policy Optimization\" --subgroup \"GRPO (Group Relative)\"\n\n"
               "  # 合并模式：将所有任务合并为一个搜索\n"
               "  python -m src.main download --group \"Policy Optimization\" --subgroup \"DPO\" --merge\n\n"
               "  # 下载整个大类\n"
               "  python -m src.main download --group \"Policy Optimization\"\n\n"
               "  # 批量下载所有任务\n"
               "  python -m src.main batch --file config/tasks.yaml\n\n"
               "  # 列出论文（不下载）\n"
               "  python -m src.main list --categories cs.CL --date 2025-03\n",
    )
    sub = parser.add_subparsers(dest="command")

    # download 子命令
    p_dl = sub.add_parser("download", help="下载论文 PDF 和元数据（从 tasks.yaml）")
    p_dl.add_argument("--file", "--config", type=str, dest="file", default="../config/tasks.yaml",
                      help="YAML 配置文件路径（默认: config/tasks.yaml）")
    p_dl.add_argument("--group", type=str,
                      help="从配置文件中选择的大类（可选），不指定则使用 defaults 配置")
    p_dl.add_argument("--subgroup", type=str,
                      help="从配置文件中选择的子类（可选）")
    p_dl.add_argument("--categories", type=str,
                      help="arXiv类别（覆盖 YAML 配置）")
    p_dl.add_argument("--date", type=parse_date_range,
                      help="日期范围（覆盖 YAML 配置）")
    p_dl.add_argument("--output",
                      help="输出目录（覆盖 YAML 配置）")
    p_dl.add_argument("--max", type=int,
                      help="最大下载数量（覆盖 YAML 配置）")
    p_dl.add_argument("--keywords", type=str,
                      help="关键词（覆盖 YAML 配置）")
    p_dl.add_argument("--authors", type=str,
                      help="作者（覆盖 YAML 配置）")
    p_dl.add_argument("--days", type=int,
                      help="最近N天的论文（覆盖 YAML 配置）")
    p_dl.add_argument("--uri",
                      help="MongoDB 连接地址（覆盖 YAML 配置）")
    p_dl.add_argument("--merge", action="store_true",
                      help="[已弃用] 合并同一分组下的所有任务为一个搜索（用 OR 连接关键词）")
    p_dl.add_argument("--stop-on-error", action="store_true",
                      help="遇到错误时停止（仅在非合并模式下有效）")

    # list 子命令
    p_ls = sub.add_parser("list", help="列出论文（不下载）")
    p_ls.add_argument("--categories", type=str, required=True,
                      help="arXiv类别，逗号分隔")
    p_ls.add_argument("--date", type=parse_date_range, required=True,
                      help="日期范围: 2025 / 2024-2025 / 2025-03 / 2025-03-2025-06")
    p_ls.add_argument("--keywords", type=str, help="关键词过滤")
    p_ls.add_argument("--max", type=int, default=100, help="最大显示数量 (默认: 100)")

    # batch 子命令
    p_batch = sub.add_parser("batch", help="批量下载（从 YAML 配置文件）")
    p_batch.add_argument("--file", type=str, default="config/tasks.yaml",
                         help="YAML 任务文件路径 (默认: config/tasks.yaml)")
    p_batch.add_argument("--stop-on-error", action="store_true",
                         help="遇到错误时停止 (默认: 跳过继续)")
    p_batch.add_argument("--uri", default="mongodb://localhost:27017",
                         help="MongoDB 连接地址 (覆盖配置文件)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "list":
        categories = [c.strip() for c in args.categories.split(",") if c.strip()]
        start_date, end_date = args.date
        print(f"类别: {', '.join(categories)}  |  日期: {_format_range(start_date, end_date)}")
        _handle_list(categories, start_date, end_date, args)
        return

    if args.command == "download":
        try:
            # 加载任务列表
            tasks = _load_config_group(
                args.file,
                group=getattr(args, "group", None),
                subgroup=getattr(args, "subgroup", None)
            )

            # 检查是否使用合并模式
            merge_mode = getattr(args, "merge", False)

            if merge_mode:
                # 合并模式：将所有任务合并为一个
                task_params = _merge_tasks(tasks)
                task_params["date"] = _prepare_date(task_params, args)
                params = _build_params(task_params, args)
                run_download(params)
            else:
                # 默认模式：逐个执行任务
                # 准备所有任务的 date
                for task in tasks:
                    task["date"] = _prepare_date(task, args)

                # 应用 CLI override 到所有任务
                tasks = [_apply_cli_overrides(task, args) for task in tasks]

                # 执行循环
                success, fail, errors = _run_download_loop(
                    tasks,
                    stop_on_error=getattr(args, "stop_on_error", False)
                )

                # 显示汇总
                _show_execution_summary(success, fail, errors)

        except Exception as e:
            print(f"错误: 无法加载配置文件 '{args.file}': {e}")
            sys.exit(1)

        return

    if args.command == "batch":
        _handle_batch(args)
        return


if __name__ == '__main__':
    main()
