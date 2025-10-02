import re
import time
import random


def safe_filename(text):
    """文件名安全处理"""
    return re.sub(r"[^\w-]", "_", text)

def random_delay(base=3, variation=2):
    """随机延迟控制"""
    time.sleep(base + random.random() * variation)