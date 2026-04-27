# arXiv 论文下载工具 - 使用示例

## ⚠️ 重要说明

**`download` 子命令强制使用 `tasks.yaml` 配置文件！**

所有下载任务都必须从 `config/tasks.yaml` 读取配置。

## 下载模式

### 1. download 子命令（从 tasks.yaml 下载）

#### 🎯 指定分组下载（推荐）

**默认行为（逐个执行任务）：**
```bash
# 下载 GRPO 分组下的所有任务（每个任务独立执行）
python -m src.main download --group "Policy Optimization" --subgroup "GRPO (Group Relative)"

# 输出示例：
# [1/13] 执行: [Policy Optimization] > GRPO (Group Relative) > DeepSeekMath
# [2/13] 执行: [Policy Optimization] > GRPO (Group Relative) > DeepSeek-R1
# ...
# 执行完成: 13 成功, 0 失败, 共 13 个任务
```

**合并模式（旧行为）：**
```bash
# 使用 --merge 将所有任务合并为一个搜索
python -m src.main download \
  --group "Policy Optimization" \
  --subgroup "GRPO (Group Relative)" \
  --merge
```

**其他示例：**
```bash
# 下载特定大类（使用默认配置文件 config/tasks.yaml）
python -m src.main download --group "Policy Optimization"

# 下载特定子类
python -m src.main download --group "Policy Optimization" --subgroup "DPO (Direct Preference)"

# 指定配置文件路径
python -m src.main download --file config/tasks.yaml --group "Self-Distillation"

# 遇到错误时停止执行
python -m src.main download --group "Policy Optimization" --subgroup "DPO" --stop-on-error
```

#### CLI 参数覆盖 YAML 配置

```bash
# 使用 YAML 配置，但用 CLI 参数覆盖部分设置
python -m src.main download \
  --file config/tasks.yaml \
  --group "Policy Optimization" \
  --subgroup "DPO (Direct Preference)" \
  --max 10  # 覆盖所有任务的 max 值为 10
```

### 3. 批量模式（执行所有任务）

```bash
# 执行 tasks.yaml 中的所有 36 个任务
python -m src.main batch --file config/tasks.yaml

# 执行过程中遇到错误时停止
python -m src.main batch --file config/tasks.yaml --stop-on-error

# 覆盖 MongoDB 连接
python -m src.main batch --file config/tasks.yaml --uri mongodb://localhost:27017
```

## tasks.yaml 分组结构

```
groups:
  Policy Optimization:           # ← 大类（第一层）
    GRPO (Group Relative):        # ← 方法变体（第二层）
      - date: 2024-01-2024-03     # ← 具体任务（第三层）
        keywords: "DeepSeekMath: ..."
        max: 2
    DPO (Direct Preference):
      - ...
    Triple PO:
      - ...
```

## 可用的分组

### Policy Optimization (24 个任务)
- `GRPO (Group Relative)` - 13 个任务
- `DPO (Direct Preference)` - 3 个任务
- `Triple PO` - 1 个任务
- `Other PO Variants` - 7 个任务

### Self-Distillation (3 个任务)
- `On-Policy Distillation` - 2 个任务
- `Self-Distillation Code Gen` - 1 个任务

### Multi-Agent Frameworks (4 个任务)
- `Multi-Agent Research` - 2 个任务
- `OpenResearcher` - 2 个任务

### Reasoning Models (3 个任务)
- `Latent Reasoning` - 1 个任务
- `Multimodal Reasoning` - 1 个任务
- `Agentic Engineering` - 1 个任务

### Others (2 个任务)
- 未分组任务

## 常用命令示例

```bash
# 1. 下载 DPO 相关论文
python -m src.main download \
  --group "Policy Optimization" \
  --subgroup "DPO (Direct Preference)"

# 2. 下载所有 Self-Distillation 论文
python -m src.main download \
  --group "Self-Distillation"

# 3. 下载 Multi-Agent 论文（限制数量）
python -m src.main download \
  --group "Multi-Agent Frameworks" \
  --max 5

# 4. 指定配置文件路径
python -m src.main download \
  --file config/custom_tasks.yaml \
  --group "Policy Optimization" \
  --subgroup "GRPO (Group Relative)"

# 5. 列出论文（不下载）
python -m src.main list \
  --categories cs.AI \
  --date 2024
```

## 参数优先级

CLI 参数会覆盖 YAML 配置（当提供 CLI 参数时）：

```bash
python -m src.main download \
  --group "Policy Optimization" \
  --categories cs.LG  # ← 覆盖 YAML 中的 cs.AI
```

## 配置字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `categories` | string | cs.AI | arXiv 类别，逗号分隔 |
| `date` | string | 2025 | 日期范围 |
| `max` | int | 10 | 最大下载数量 |
| `keywords` | string | - | 搜索关键词 |
| `output` | string | D:/papers/arxiv | 输出目录 |
| `on_no_results` | string | warn | 无结果时的处理: warn/raise/silent |
| `show_results` | bool | true | 是否显示搜索到的论文列表 |
