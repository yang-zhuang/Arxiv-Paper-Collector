#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
from datetime import datetime
from typing import List, Dict

# 导入自定义模块
from src.core.api_client import ArXivClient
from src.core.data_processor import DataProcessor
from src.core.storage_manager import StorageManager
from src.core.state_manager import StateManager
from src.utils.logger import setup_logger, log_section, log_table, log_progress
from config import settings
from src.core.pdf_downloader import PDFDownloader

# 配置默认值
DEFAULT_CATEGORIES = settings.CATEGORIES
DEFAULT_LIMIT = settings.PAPERS_PER_CATEGORY
DEFAULT_BATCH_MODE = settings.BATCH_MODE
DEFAULT_LOG_LEVEL = "INFO"


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="arXiv论文收集工具")

    parser.add_argument(
        "--categories",
        type=str,
        default=",".join(DEFAULT_CATEGORIES),
        help=f"逗号分隔的类别列表 (默认: {','.join(DEFAULT_CATEGORIES)})"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"每个类别获取的论文数量 (默认: {DEFAULT_LIMIT})"
    )

    parser.add_argument(
        "--batch",
        type=lambda x: (str(x).lower() == 'true'),
        default=DEFAULT_BATCH_MODE,
        help="是否按批次保存文件 (True/False) (默认: True)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=DEFAULT_LOG_LEVEL,
        help=f"日志级别 (默认: {DEFAULT_LOG_LEVEL})"
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default="logs/arxiv_collector.log",
        help="日志文件路径 (默认: logs/arxiv_collector.log)"
    )

    # 🔨 新增搜索参数
    parser.add_argument("--days", type=int, help="获取最近N天的论文")
    parser.add_argument("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--keywords", type=str, help="关键词，用逗号分隔")
    parser.add_argument("--search-fields", type=str, default="title,abstract", help="搜索字段: title,abstract,all")
    parser.add_argument("--authors", type=str, help="作者名称，用逗号分隔")
    parser.add_argument("--match-all-authors", action="store_true", help="必须匹配所有作者")
    parser.add_argument("--sort-by", type=str, choices=["submittedDate", "lastUpdatedDate", "relevance"],
                        default="submittedDate")
    parser.add_argument("--sort-order", type=str, choices=["ascending", "descending"], default="descending")

    return parser.parse_args()


def parse_categories(logger, categories_str: str) -> List[str]:
    """解析类别列表"""
    categories = [cat.strip() for cat in categories_str.split(",") if cat.strip()]
    if not categories:
        logger.error("未指定有效类别，使用默认类别")
        return DEFAULT_CATEGORIES
    return categories


def log_startup_info(logger, timestamp, categories, limit):
    """记录启动信息"""
    log_section(logger, "arXiv Paper Collector 启动", level="info")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"运行标识: {timestamp}")
    logger.info(f"目标类别: {', '.join(categories)}")
    logger.info(f"每类论文数: {limit}")


def log_search_config(logger, search_config):
    """记录搜索配置"""
    logger.info("搜索配置:")
    if search_config["time_range"]["type"] != "all":
        logger.info(f"  时间范围: {search_config['time_range']}")
    if search_config["keywords"].get("enabled"):
        logger.info(f"  关键词: {search_config['keywords']['terms']}")
        logger.info(f"  搜索字段: {search_config['keywords']['search_fields']}")
    if search_config["authors"].get("enabled"):
        logger.info(f"  作者: {search_config['authors']['names']}")
    logger.info(f"  排序: {search_config['sort_by']} {search_config['sort_order']}")


def create_search_config(args):
    """根据命令行参数创建搜索配置"""
    search_config = settings.SEARCH_CONFIG.copy()

    # 时间范围配置
    if args.days:
        search_config["time_range"] = {
            "type": "last_n_days",
            "value": args.days
        }
    elif args.start_date and args.end_date:
        search_config["time_range"] = {
            "type": "specific_range",
            "start_date": args.start_date,
            "end_date": args.end_date
        }

    # 关键词配置
    if args.keywords:
        search_config["keywords"] = {
            "enabled": True,
            "terms": [k.strip() for k in args.keywords.split(",")],
            "search_fields": [f.strip() for f in args.search_fields.split(",")]
        }

    # 作者配置
    if args.authors:
        search_config["authors"] = {
            "enabled": True,
            "names": [a.strip() for a in args.authors.split(",")],
            "match_all": args.match_all_authors
        }

    # 排序配置
    search_config["sort_by"] = args.sort_by
    search_config["sort_order"] = args.sort_order

    return search_config


def initialize_components(args, logger):
    """初始化所有核心组件"""
    try:
        client = ArXivClient(
            base_url=settings.API_ENDPOINT,
            delay=settings.REQUEST_DELAY,
            max_retries=settings.MAX_RETRIES,
            logger=logger,
            search_config=create_search_config(args)
        )

        storage = StorageManager(output_root=settings.OUTPUT_ROOT)
        processor = DataProcessor(logger=logger)
        state_manager = StateManager(state_dir=settings.STATE_DIR, logger=logger)

        # 初始化PDF下载器
        pdf_downloader = None
        if settings.DOWNLOAD_PDFS:
            try:
                pdf_downloader = PDFDownloader(
                    base_url="https://arxiv.org/",
                    pdf_dir=settings.PDF_ROOT,
                    delay=settings.PDF_DOWNLOAD_DELAY,
                    max_retries=settings.MAX_RETRIES,
                    logger=logger
                )
            except Exception as e:
                logger.error(f"PDF下载器初始化失败: {str(e)}")

        return client, storage, processor, state_manager, pdf_downloader
    except Exception as e:
        logger.critical(f"初始化失败: {str(e)}")
        sys.exit(1)


def initialize_stats(timestamp):
    """初始化统计数据"""
    return {
        "total_papers": 0,
        "categories": {},
        "output_files": {},
        "start_time": datetime.now(),
        "timestamp": timestamp
    }


def process_all_categories(categories, args, logger, timestamp, client, storage, processor, state_manager,
                           pdf_downloader, stats):
    """处理所有类别"""
    if len(categories) == 0:
        # 处理单个类别
        category_stats = process_single_category(
            None,
            args,
            logger,
            timestamp,
            client,
            storage,
            processor,
            state_manager,
            pdf_downloader,
            stats
        )

        # 更新统计数据
        stats["total_papers"] += category_stats["paper_count"]
        stats["categories"][None] = category_stats["paper_count"]
        stats["output_files"][None] = category_stats["output_file"]

    for i, category in enumerate(categories):
        logger.info(f"\n处理类别 ({i + 1}/{len(categories)}): {category}")

        # 处理单个类别
        category_stats = process_single_category(
            category,
            args,
            logger,
            timestamp,
            client,
            storage,
            processor,
            state_manager,
            pdf_downloader,
            stats
        )

        # 更新统计数据
        stats["total_papers"] += category_stats["paper_count"]
        stats["categories"][category] = category_stats["paper_count"]
        stats["output_files"][category] = category_stats["output_file"]


def process_single_category(category, args, logger, timestamp, client, storage, processor, state_manager, pdf_downloader, stats):
    """处理单个类别"""
    # 加载类别状态
    state = state_manager.load_state(category)
    logger.debug(f"类别状态: 最后运行={state.get('last_run')}, 最后获取位置={state.get('last_start_index')}")

    try:
        # 获取论文
        papers = client.fetch_papers(category=category, limit=args.limit)
        logger.info(f"成功获取 {len(papers)} 篇论文")

        if not papers:
            logger.warning(f"类别 {category} 未获取到新论文")
            return {"category": category, "paper_count": 0, "output_file": None}

        # 处理论文数据
        processed = []
        for j, paper in enumerate(papers):
            try:
                processed.append(processor.process_entry(paper, category))
                if (j + 1) % 50 == 0:
                    log_progress(logger, j + 1, len(papers), f"处理 {category} 论文")
            except Exception as e:
                logger.error(f"处理论文时出错: {str(e)}")

        # 保存论文
        if args.batch:
            output_file = storage.save_papers(
                category,
                processed,
                batch=True,
                timestamp=timestamp
            )
        else:
            output_file = storage.append_papers(category, processed)

        logger.info(f"已保存到: {output_file}")

        # 更新状态
        state_manager.save_state(category, client.get_current_state(category))
        logger.debug(f"类别状态已保存")

        # 下载PDF文件
        if pdf_downloader and settings.DOWNLOAD_PDFS:
            pdf_stats = pdf_downloader.download_pdfs(processed, category, timestamp=timestamp)
            logger.info(
                f"PDF下载完成: 成功 {pdf_stats['success']}/"
                f"{pdf_stats['total']}, 失败 {pdf_stats['failed']}, "
                f"跳过 {pdf_stats['skipped']}"
            )
            # 记录PDF文件路径
            for item in pdf_stats["downloaded"]:
                if item["category"] == category:
                    stats["output_files"].setdefault(category, []).append(item["path"])

        return {"category": category, "paper_count": len(processed), "output_file": output_file}

    except Exception as e:
        logger.error(f"处理类别 {category} 时出错: {str(e)}")
        return {"category": category, "paper_count": f"错误: {str(e)}", "output_file": None}


def calculate_duration(stats):
    """计算运行时间"""
    stats["end_time"] = datetime.now()
    stats["duration"] = stats["end_time"] - stats["start_time"]


def generate_summary_report(stats, logger):
    """生成摘要报告"""
    # 打印摘要报告
    log_section(logger, "收集完成", level="info")

    # 准备表格数据
    table_data = {}
    for category, count in stats["categories"].items():
        table_data[category] = count

    table_data["总计"] = stats["total_papers"]
    table_data["运行时间"] = str(stats["duration"])

    # 记录摘要表格
    log_table(logger, table_data, "收集摘要", level="info")

    # 记录输出文件
    logger.info("\n输出文件:")
    for category, file_path in stats["output_files"].items():
        logger.info(f"  {category}: {file_path}")

    logger.info(f"完成时间: {stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"总运行时间: {stats['duration']}")
    logger.info(f"运行标识: {stats['timestamp']}")
    logger.info("程序正常结束")

    # 在摘要中添加PDF统计
    if "pdf_stats" in stats:
        log_section(logger, "PDF下载统计", level="info")
        for category, pdf_stat in stats["pdf_stats"].items():
            logger.info(
                f"{category}: 成功 {pdf_stat['success']}/{pdf_stat['total']}, "
                f"失败 {pdf_stat['failed']}, 跳过 {pdf_stat['skipped']}"
            )


def main():
    """主程序入口"""
    # 解析命令行参数
    args = parse_arguments()

    # 设置日志记录器
    logger = setup_logger(
        name="arxiv-collector",
        log_level=args.log_level,
        log_file=args.log_file
    )

    # 解析类别列表
    categories = parse_categories(logger, args.categories)

    # 生成唯一时间戳 (精确到秒)
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    # 记录启动信息
    log_startup_info(logger, timestamp, categories, args.limit)

    # 记录搜索配置
    search_config = create_search_config(args)
    log_search_config(logger, search_config)

    # 初始化核心组件
    client, storage, processor, state_manager, pdf_downloader = initialize_components(args, logger)

    # 收集统计数据
    stats = initialize_stats(timestamp)

    # 处理每个类别
    process_all_categories(
        categories,
        args,
        logger,
        timestamp,
        client,
        storage,
        processor,
        state_manager,
        pdf_downloader,
        stats
    )

    # 计算运行时间
    calculate_duration(stats)

    # 生成摘要报告
    generate_summary_report(stats, logger)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"未处理的错误: {str(e)}")
        sys.exit(2)