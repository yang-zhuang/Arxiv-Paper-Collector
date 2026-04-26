#!/usr/bin/env python3
"""arXiv 论文下载工具"""

from setuptools import setup, find_packages

setup(
    name="arxiv-paper-collector",
    version="2.0.0",
    description="Download papers from arXiv",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.28.0",
        "feedparser>=6.0.0",
        "tqdm>=4.64.0",
        "python-dateutil>=2.8.0",
        "pymongo>=4.6.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "arxiv-collector=src.main:main",
        ],
    },
)
