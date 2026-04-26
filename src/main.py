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


def run_download(params: dict, db=None):
    """执行一次下载任务。

    Args:
        params: 参数字典，包含 categories, date, output, max,
                keywords, authors, days, uri, name 等键。
                其中 date 应为 (start_date, end_date) 元组。
        db: 已有的数据库连接。为 None 时自动创建并在完成后关闭。
    """
    from src.api_client import fetch_papers
    from src.downloader import download_papers
    from src.db import get_db, upsert_papers_batch, get_pending_papers, get_stats, close

    name = params.get("name", "")
    categories = [c.strip() for c in params["categories"].split(",") if c.strip()]
    start_date, end_date = params["date"]
    max_papers = params["max"]

    own_db = db is None
    if own_db:
        db = get_db(params["uri"])

    try:
        if name:
            print(f"\n{'=' * 60}")
            print(f"  {name}")
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
            keywords = [k.strip() for k in params["keywords"].split(",")] if params.get("keywords") else None
            authors = [a.strip() for a in params["authors"].split(",")] if params.get("authors") else None

            per_category = max(1, need_count // len(categories))
            for cat in categories:
                papers = fetch_papers(
                    cat, start_date, end_date,
                    max_papers=per_category,
                    keywords=keywords, authors=authors,
                    days=params.get("days"), db=db,
                )
                all_new_papers.extend(papers)
            print(f"  从 arXiv API 获取到 {len(all_new_papers)} 篇新论文")
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
            print("  未找到任何论文")
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

    print(f"从 {file_path} 加载了 {len(tasks)} 个任务\n")

    db = get_db(tasks[0]["uri"] if tasks else args.uri)

    success_count = 0
    fail_count = 0
    errors = []

    for i, task_params in enumerate(tasks, 1):
        task_name = task_params.get("name", f"Task {i}")
        print(f"\n[{i}/{len(tasks)}] 执行: {task_name}")
        try:
            task_params["date"] = parse_date_range(task_params["date"])
            run_download(task_params, db=db)
            success_count += 1
            print(f"  [{task_name}] 完成")
        except Exception as e:
            fail_count += 1
            errors.append((task_name, str(e)))
            print(f"  [{task_name}] 失败: {e}")
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
               "  python -m src download --categories cs.AI --date 2025 --max 5\n"
               "  python -m src batch --file config/tasks.yaml\n"
               "  python -m src list --categories cs.CL --date 2025-03\n",
    )
    sub = parser.add_subparsers(dest="command")

    # download 子命令
    p_dl = sub.add_parser("download", help="下载论文 PDF 和元数据")
    p_dl.add_argument("--categories", type=str, default="cs.AI",
                      help="arXiv类别，逗号分隔 (如 cs.AI,cs.CV，默认: cs.AI)")
    p_dl.add_argument("--date", type=parse_date_range, default=parse_date_range('2025-11-2026-04'),
                      help="日期范围: 2025 / 2024-2025 / 2025-03 / 2025-03-2025-06。默认: 2025")
    p_dl.add_argument("--output", default="D:/papers/arxiv", help="输出目录 (默认: papers)")
    p_dl.add_argument("--max", type=int, default=3, help="最大下载数量 (默认: 2000)")
    p_dl.add_argument("--keywords", type=str, default="Nested Learning (NL)", help="关键词，逗号分隔")
    p_dl.add_argument("--authors", type=str, help="作者，逗号分隔")
    p_dl.add_argument("--days", type=int, help="最近N天的论文")
    p_dl.add_argument("--uri", default="mongodb://localhost:27017",
                      help="MongoDB 连接地址 (默认: mongodb://localhost:27017)")

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
        params = {
            "categories": args.categories,
            "date": args.date,
            "output": args.output,
            "max": args.max,
            "keywords": args.keywords,
            "authors": args.authors,
            "days": args.days,
            "uri": args.uri,
        }
        run_download(params)
        return

    if args.command == "batch":
        _handle_batch(args)
        return


if __name__ == '__main__':
    main()
