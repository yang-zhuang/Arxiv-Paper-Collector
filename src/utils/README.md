# 完整日志模块实现 (logger.py)

以下是一个功能完善的日志模块实现，支持彩色输出、文件记录、进度条集成和模块化配置：

```python
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
        'DEBUG': '\033[94m',     # 蓝色
        'INFO': '\033[92m',      # 绿色
        'WARNING': '\033[93m',   # 黄色
        'ERROR': '\033[91m',     # 红色
        'CRITICAL': '\033[95m',  # 紫色
        'RESET': '\033[0m'       # 重置颜色
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
```

## 功能特点

### 1. 核心日志功能
- **多级别日志**：支持DEBUG, INFO, WARNING, ERROR, CRITICAL
- **彩色输出**：不同级别使用不同颜色
- **文件轮转**：自动管理日志文件大小和备份
- **tqdm兼容**：与进度条无缝集成

### 2. 高级日志功能
- **分割线日志**：`log_section()` 用于标记重要阶段
- **进度日志**：`log_progress()` 显示处理进度
- **表格日志**：`log_table()` 以表格格式展示数据摘要

### 3. 日志处理器
- **TqdmLoggingHandler**：确保日志与进度条兼容
- **ProgressBarHandler**：直接在进度条区域显示日志
- **ColoredFormatter**：终端彩色输出格式化器

### 4. 配置选项
```python
setup_logger(
    name="arxiv-collector",         # 日志记录器名称
    log_level="INFO",               # 控制台日志级别
    log_file="logs/app.log",        # 日志文件路径
    file_log_level="DEBUG",         # 文件日志级别
    max_bytes=10*1024*1024,         # 10MB文件大小限制
    backup_count=5                  # 保留5个备份文件
)
```

## 使用示例

### 在主程序中使用
```python
from utils.logger import setup_logger, log_section, log_progress

# 初始化日志记录器
logger = setup_logger(
    name="arxiv-collector",
    log_level="INFO",
    log_file="logs/arxiv_collector.log"
)

def main():
    log_section(logger, "arXiv 论文收集开始", level="info")
    
    # 模拟处理
    total = 100
    for i in range(total):
        # 每10条记录一次进度
        if i % 10 == 0:
            log_progress(logger, i, total, "处理论文")
        
        # 处理逻辑...
    
    log_section(logger, "处理完成", level="info")
```

### 与进度条集成
```python
from tqdm import tqdm
from utils.logger import ProgressBarHandler

def process_items(items):
    # 创建进度条
    pbar = tqdm(items, desc="处理项目")
    
    # 创建进度条日志处理器
    progress_handler = ProgressBarHandler(pbar)
    progress_handler.setLevel(logging.INFO)
    
    # 添加到日志记录器
    logger = logging.getLogger("arxiv-collector")
    logger.addHandler(progress_handler)
    
    for item in pbar:
        try:
            # 处理逻辑...
            logger.info(f"处理项目: {item}")
        except Exception as e:
            logger.error(f"处理失败: {item}, 错误: {str(e)}")
    
    # 处理完成后移除处理器
    logger.removeHandler(progress_handler)
```

## 日志格式说明

### 控制台输出（彩色）
```
2023-08-15 14:30:45 - arxiv-collector - INFO - 开始处理类别: cs.CV
2023-08-15 14:31:02 - arxiv-collector - DEBUG - 获取到100篇论文
2023-08-15 14:31:05 - arxiv-collector - WARNING - API响应延迟较高
```

### 文件输出（纯文本）
```
2023-08-15 14:30:45 - arxiv-collector - INFO - 开始处理类别: cs.CV
2023-08-15 14:31:02 - arxiv-collector - DEBUG - 获取到100篇论文
2023-08-15 14:31:05 - arxiv-collector - WARNING - API响应延迟较高
```

### 特殊格式
```
============================================================================
                             arXiv 论文收集开始                              
============================================================================

处理项目: 50/100 (50.0%)

╔══════════════════════╗
║     处理摘要         ║
╠══════════════════════╣
║ 成功项目 :  85       ║
║ 失败项目 :   5       ║
║ 跳过项目 :  10       ║
║ 总处理时间 : 2分15秒 ║
╚══════════════════════╝
```

## 优势总结

1. **专业美观**：
   - 彩色输出提高可读性
   - 表格和分割线增强信息组织
   - 进度显示直观清晰

2. **高度集成**：
   - 与tqdm进度条无缝协作
   - 支持在进度条区域显示日志
   - 兼容各种运行环境

3. **生产就绪**：
   - 日志轮转防止磁盘空间耗尽
   - 文件和控制台独立日志级别
   - 详细的错误追踪能力

4. **灵活配置**：
   - 可自定义日志格式和级别
   - 支持文件路径自动创建
   - 模块化设计易于扩展

这个日志模块提供了科研级项目所需的所有日志功能，既美观又实用，特别适合需要长时间运行的数据收集任务。