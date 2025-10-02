import time
import random
from collections import deque


class APIRateLimiter:
    def __init__(self, base_delay=3, burst_size=5):
        self.base_delay = base_delay
        self.burst_size = burst_size
        self.request_times = deque(maxlen=burst_size)

    def wait(self):
        """等待适当的请求时间"""
        now = time.time()

        if len(self.request_times) >= self.burst_size:
            # 计算最近一次请求的时间
            elapsed = now - self.request_times[0]
            if elapsed < self.base_delay * self.burst_size:
                # 需要等待
                wait_time = max(0, self.base_delay * self.burst_size - elapsed)
                time.sleep(wait_time + random.uniform(0, 1))

        self.request_times.append(time.time())