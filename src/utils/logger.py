import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict
from tqdm import tqdm


class TqdmLoggingHandler(logging.Handler):
    """确保日志与tqdm进度条兼容"""

    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            tqdm.write(msg)
            self.flush()
        except Exception:
            self.handleError(record)


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    COLORS = {
        'DEBUG': '\033[94m',  # 蓝色
        'INFO': '\033[92m',  # 绿色
        'WARNING': '\033[93m',  # 黄色
        'ERROR': '\033[91m',  # 红色
        'CRITICAL': '\033[95m',  # 紫色
        'RESET': '\033[0m'  # 重置颜色
    }

    def format(self, record):
        log_message = super().format(record)
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        return f"{color}{log_message}{self.COLORS['RESET']}"


class ProgressBarHandler(logging.Handler):
    """进度条日志处理器"""

    def __init__(self, pbar: tqdm, level=logging.INFO):
        super().__init__(level)
        self.pbar = pbar

    def emit(self, record):
        try:
            msg = self.format(record)
            self.pbar.write(msg)
        except Exception:
            self.handleError(record)


def setup_logger(
        name: str = "arxiv-collector",
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        file_log_level: str = "DEBUG",
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
) -> logging.Logger:
    """
    配置并返回一个日志记录器

    参数:
        name: 日志记录器名称
        log_level: 控制台日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径 (None表示不记录到文件)
        file_log_level: 文件日志级别
        max_bytes: 日志文件最大字节数
        backup_count: 保留的备份文件数量
    """
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # 捕获所有级别，由处理器过滤

    # 清除现有处理器（防止重复）
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 创建控制台处理器 (带颜色)
    console_handler = TqdmLoggingHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 控制台格式化器
    console_formatter = ColoredFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器 (如果需要)
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # 创建轮转文件处理器
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, file_log_level.upper(), logging.DEBUG))

        # 文件格式化器 (无颜色)
        file_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def log_section(logger: logging.Logger, message: str, level: str = "info", char: str = "=", length: int = 80):
    """记录带有装饰的分割线日志"""
    full_message = f"\n{char * length}\n{message.center(length)}\n{char * length}"
    getattr(logger, level.lower())(full_message)


def log_progress(logger: logging.Logger, current: int, total: int, message: str = "Progress", level: str = "info"):
    """记录带有进度百分比的日志"""
    percent = (current / total) * 100
    progress_message = f"{message}: {current}/{total} ({percent:.1f}%)"
    getattr(logger, level.lower())(progress_message)


def log_table(logger: logging.Logger, data: Dict[str, int], title: str = "Summary", level: str = "info"):
    """以表格格式记录数据"""
    if not data:
        return

    max_key_length = max(len(str(key)) for key in data.keys())
    max_value_length = max(len(str(value)) for value in data.values())

    table_width = max_key_length + max_value_length + 7  # 边框和间距

    # 创建表格
    lines = [
        f"\n╔{'═' * table_width}╗",
        f"║ {title.center(table_width - 2)} ║",
        f"╠{'═' * table_width}╣"
    ]

    for key, value in data.items():
        key_str = str(key)
        value_str = str(value)
        line = f"║ {key_str.ljust(max_key_length)} : {value_str.rjust(max_value_length)} ║"
        lines.append(line)

    lines.append(f"╚{'═' * table_width}╝")

    # 记录表格
    getattr(logger, level.lower())("\n".join(lines))


# 示例使用
if __name__ == "__main__":
    # 设置日志记录器
    logger = setup_logger(
        name="example-logger",
        log_level="DEBUG",
        log_file="logs/example.log"
    )

    # 记录不同级别的消息
    logger.debug("这是一条调试信息")
    logger.info("这是一条普通信息")
    logger.warning("这是一条警告信息")
    logger.error("这是一条错误信息")
    logger.critical("这是一条严重错误信息")

    # 使用特殊日志功能
    log_section(logger, "数据处理开始", level="info")

    # 模拟进度
    total_items = 100
    for i in range(total_items):
        if i % 10 == 0:
            log_progress(logger, i, total_items, "处理项目")

    log_section(logger, "数据处理完成", level="info")

    # 记录表格
    summary_data = {
        "成功项目": 85,
        "失败项目": 5,
        "跳过项目": 10,
        "总处理时间": "2分15秒"
    }
    log_table(logger, summary_data, "处理摘要")