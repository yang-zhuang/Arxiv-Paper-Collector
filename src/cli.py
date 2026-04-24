"""命令行入口"""

import argparse
import sys
import re


def parse_date_range(s):
    """解析日期范围字符串，返回 (start_date, end_date) 元组。

    支持格式:
      '2025'           → ('20250101', '20251231')
      '2025-2026'      → ('20250101', '20261231')
      '2025-03'        → ('20250301', '20250331')
      '2025-03-2025-06'→ ('20250301', '20250630')
    """
    s = s.strip()
    pattern = r'^(\d{4})(?:-(\d{2}))?\s*(?:-\s*(\d{4})(?:-(\d{2}))?)?$'
    match = re.match(pattern, s)
    if not match:
        raise argparse.ArgumentTypeError(
            f"日期格式错误，支持: 2025 / 2024-2025 / 2025-03 / 2025-03-2025-06，得到: {s}"
        )

    from calendar import monthrange

    g1, g2, g3, g4 = match.group(1), match.group(2), match.group(3), match.group(4)

    if g3 is None:
        # 单个年份或年月: '2025' 或 '2025-03'
        year = int(g1)
        if g2:
            month = int(g2)
            _, last_day = monthrange(year, month)
            start = f"{year}{month:02d}01"
            end = f"{year}{month:02d}{last_day}"
        else:
            start = f"{year}0101"
            end = f"{year}1231"
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

    return (start, end)


def _format_range(start, end):
    """将 '20250301' 格式化为可读的 '2025-03' 格式"""
    def fmt(d):
        return f"{d[:4]}-{d[4:6]}" if len(d) >= 6 else d[:4]
    return f"{fmt(start)} ~ {fmt(end)}"


def main():
    parser = argparse.ArgumentParser(
        description="arXiv 论文下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python -m src download --categories cs.AI --date 2025 --max 5\n"
               "  python -m src download --categories cs.CV --date 2025-03-2025-06 --output papers\n"
               "  python -m src list --categories cs.CL --date 2025-03\n",
    )
    sub = parser.add_subparsers(dest="command")

    # download 子命令
    p_dl = sub.add_parser("download", help="下载论文 PDF 和元数据")
    p_dl.add_argument("--categories", type=str, default="cs.AI",
                      help="arXiv类别，逗号分隔 (如 cs.AI,cs.CV，默认: cs.AI)")
    p_dl.add_argument("--date", type=parse_date_range, default=parse_date_range('2026-02'),
                      help="日期范围: 2025 / 2024-2025 / 2025-03 / 2025-03-2025-06。默认: 2025")
    p_dl.add_argument("--output", default="D:/papers/arxiv", help="输出目录 (默认: papers)")
    p_dl.add_argument("--max", type=int, default=100, help="最大下载数量 (默认: 2000)")
    p_dl.add_argument("--keywords", type=str, default="skill", help="关键词，逗号分隔")
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    from src.api_client import fetch_papers
    from src.downloader import download_papers
    from src.db import get_db, upsert_papers_batch, get_pending_papers, get_stats, close

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    start_date, end_date = args.date
    print(f"类别: {', '.join(categories)}  |  日期: {_format_range(start_date, end_date)}")

    if args.command == "list":
        _handle_list(categories, start_date, end_date, args)
        return

    # === download 子命令 ===
    db = get_db(args.uri)

    # 1. 从数据库获取未完成的论文
    all_pending = []
    for cat in categories:
        pending = get_pending_papers(db, category=cat,
                                     start_year=int(start_date[:4]),
                                     end_year=int(end_date[:4]))
        all_pending.extend(pending)
    print(f"数据库中有 {len(all_pending)} 篇未完成论文（pending/failed）")

    # 2. 从 arXiv API 获取新论文
    need_count = max(0, args.max - len(all_pending))
    all_new_papers = []
    if need_count > 0:
        print(f"需要再获取 {need_count} 篇新论文")
        keywords = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
        authors = [a.strip() for a in args.authors.split(",")] if args.authors else None

        per_category = max(1, need_count // len(categories))
        for cat in categories:
            papers = fetch_papers(
                cat, start_date, end_date,
                max_papers=per_category,
                keywords=keywords, authors=authors,
                days=args.days, db=db,
            )
            all_new_papers.extend(papers)

        print(f"从 arXiv API 获取到 {len(all_new_papers)} 篇新论文")
    else:
        print("数据库中的论文已足够，无需获取新论文")

    # 3. 保存新论文到数据库
    if all_new_papers:
        count = upsert_papers_batch(db, all_new_papers, source="arxiv")
        print(f"已保存 {count} 篇新论文到数据库")

    # 4. 合并 pending + 新论文，去重
    all_papers = {p["pdf_url"]: p for p in all_pending}
    for p in all_new_papers:
        all_papers[p["pdf_url"]] = p
    papers = list(all_papers.values())[:args.max]

    print(f"合并后共 {len(papers)} 篇论文待下载（限制: max={args.max}）")

    if not papers:
        print("未找到任何论文")
        close()
        return

    # 5. 下载 PDF
    print(f"\n找到 {len(papers)} 篇论文，开始下载...")
    count = download_papers(papers, args.output, db=db)
    print(f"\n下载完成！成功 {count} 篇")

    # 6. 显示统计
    for cat in categories:
        stats = get_stats(db, category=cat)
        print(f"  {cat}: {stats}")

    close()


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
