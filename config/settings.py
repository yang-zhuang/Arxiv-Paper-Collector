# config/settings.py

# arXiv API配置
API_ENDPOINT = "http://export.arxiv.org/api/query"
REQUEST_DELAY = 3  # 基础延迟秒数
MAX_RETRIES = 3  # 失败重试次数

# 输出配置
OUTPUT_ROOT = "data/metadata"
STATE_DIR = "data/state"
BATCH_MODE = True

# 获取限制
PAPERS_PER_CATEGORY = 1000  # 每个类别每次获取数量，默认200
MAX_RESULTS_PER_REQUEST = 500  # 每次API请求最大数量，默认100

# 添加PDF相关配置
PDF_ROOT = "data/pdfs"  # PDF存储根目录
DOWNLOAD_PDFS = True    # 是否下载PDF
PDF_DOWNLOAD_DELAY = 5  # PDF下载之间的延迟（秒）

# 论文获取配置
CATEGORIES = [
    "cs.AI", # Artificial Intelligence (人工智能，除视觉、机器人、机器学习等子领域)
    "cs.AR", # Hardware Architecture (硬件架构)
    "cs.CC", # Computational Complexity (计算复杂性)
    "cs.CE", # Computational Engineering, Finance, and Science (计算工程、金融与科学)
    "cs.CG", # Computational Geometry (计算几何)
    "cs.CL", # Computation and Language (计算与语言/自然语言处理)
    "cs.CR", # Cryptography and Security (密码学与安全)
    "cs.CV", # Computer Vision and Pattern Recognition (计算机视觉与模式识别)
    "cs.CY", # Computers and Society (计算机与社会)
    "cs.DB", # Databases (数据库)
    "cs.DC", # Distributed, Parallel, and Cluster Computing (分布式、并行与集群计算)
    "cs.DL", # Digital Libraries (数字图书馆)
    "cs.DM", # Discrete Mathematics (离散数学)
    "cs.DS", # Data Structures and Algorithms (数据结构与算法)
    "cs.ET", # Emerging Technologies (新兴技术)
    "cs.FL", # Formal Languages and Automata Theory (形式语言与自动机理论)
    "cs.GL", # General Literature (通用文献)
    "cs.GR", # Graphics (计算机图形学)
    "cs.GT", # Computer Science and Game Theory (计算机科学与博弈论)
    "cs.HC", # Human-Computer Interaction (人机交互)
    "cs.IR", # Information Retrieval (信息检索)
    "cs.IT", # Information Theory (信息论)
    "cs.LG", # Machine Learning (机器学习)
    "cs.LO", # Logic in Computer Science (计算机科学中的逻辑)
    "cs.MA", # Multiagent Systems (多智能体系统)
    "cs.MM", # Multimedia (多媒体)
    "cs.MS", # Mathematical Software (数学软件)
    "cs.NA", # Numerical Analysis (数值分析，与math.NA相同)

    "cs.NE", # Neural and Evolutionary Computing (神经与进化计算)
    "cs.NI", # Networking and Internet Architecture (网络与互联网架构)
    "cs.OH", # Other Computer Science (其他计算机科学)
    "cs.OS", # Operating Systems (操作系统)
    "cs.PF", # Performance (性能)
    "cs.PL", # Programming Languages (编程语言)
    "cs.RO", # Robotics (机器人学)
    "cs.SC", # Symbolic Computation (符号计算)
    "cs.SD", # Sound (声音处理)
    "cs.SE", # Software Engineering (软件工程)
    "cs.SI", # Social and Information Networks (社会与信息网络)
    "cs.SY", # Systems and Control (系统与控制，与eess.SY相同)
]

# 🔨 新增搜索参数配置
SEARCH_CONFIG = {
    # 时间范围配置 (支持 'last_n_days', 'specific_range', 'all')
    "time_range": {
        "type": "specific_range",  # 'last_n_days', 'specific_range', 'all'
        "value": 7,  # 当 type='last_n_days' 时，表示最近几天
        "start_date": "2025-01-01",  # 当 type='specific_range' 时使用
        "end_date": "2025-10-02"  # 当 type='specific_range' 时使用
    },

    # 关键词搜索配置
    "keywords": {
        "enabled": False,
        "terms": ["transformer", "attention mechanism"],
        "search_fields": ["title", "abstract"]  # 'title', 'abstract', 'all'
    },

    # 作者搜索配置
    "authors": {
        "enabled": False,
        "names": ["Smith, John", "Lee, Jane"],
        "match_all": False  # True: 必须匹配所有作者, False: 匹配任一作者
    },

    # 排序配置
    "sort_by": "submittedDate",  # 'submittedDate', 'lastUpdatedDate', 'relevance'
    "sort_order": "descending"  # 'ascending', 'descending'
}