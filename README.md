# Huginn - AI驱动的探索型课程问卷数据分析智能体

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/DeepSeek-API-orange.svg" alt="DeepSeek API">
  <img src="https://img.shields.io/badge/Tests-35%20passed-success.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Config-60+%20options-informational.svg" alt="Config">
  <img src="https://img.shields.io/badge/Status-Stable-brightgreen.svg" alt="Status">
</p>

> **全自动数据分析智能体**：上传 Excel/CSV 表格，自动完成智能数据清洗 → 统计推断 → 可视化 → LLM 洞察提炼 → **完整报告生成** → 合规性验证。内置 Likert 量表智能识别、字段名清洗、集中化配置管理、统一日志系统。严格遵循"**模型只做决策和解释，所有统计量由 Python 真实计算**"的核心原则，彻底杜绝大模型幻觉。合规性验证最高可达 **100/100**。

## 核心功能

### 全自动探索型分析（9步完整管线）
无需指定分析问题，智能体自动理解数据结构，主动发现值得研究的业务问题，用统计方法验证，并**一键生成完整的 7 章课程分析报告**。

### 学术级统计分析
- 点估计（均值、方差、标准差、中位数等 10 个参数）
- 区间估计（均值、方差、标准差、中位数、预测区间）
- 6 类假设检验（t 检验、配对 t 检验、Wilcoxon、Mann-Whitney 等）
- 单因素/双因素方差分析（ANOVA）+ Tukey 事后检验
- 皮尔逊卡方检验（拟合优度 + 独立性检验）
- 正态性检验（Shapiro-Wilk + D'Agostino-Pearson）

### 自动报告生成
- **7 章完整Markdown报告**：数据来源 → 数据概况 → 描述性统计 → 统计推断 → 数据发现 → 改进建议 → 局限性说明
- **附录**：自动集成合规性验证得分和各模块详细结果
- **Word 导出**：支持一键导出 `.docx` 格式报告
- 所有统计量可溯源至 JSON 原始结果，杜绝编造

### 自动合规性验证
内置课程作业专用验证器，分析完成后自动运行并写入报告附录：
- 统计数量硬指标（≥5 点估计 / ≥5 区间估计 / ≥5 假设检验 / ≥2 ANOVA / ≥2 卡方）
- 结果有效性（p 值范围、样本量、无编造数据）
- 发现合规性（无因果错误、无模糊表述、引用正确）
- 建议合理性（有数据依据、可落地）
- 100 分制，60 分及格

### 交互式 Web 界面
- **Streamlit 应用**：`streamlit run app.py` 一键启动
- 支持文件上传、需求输入、离线模式切换
- 标签页展示：概况 / 图表 / 统计 / 发现 / 建议 / 验证 / 完整报告
- 一键下载 Markdown 报告、Word 报告、统计结果 JSON、**ZIP 打包**

### 工程化基础设施 🆕
- **集中化配置**：`config.py` 管理 60+ 配置项，所有 LLM 参数、统计阈值、UI 标签统一管理，支持环境变量覆盖
- **统一日志**：`logger.py` 幂等初始化，消除模块 import 时日志静默丢失的问题
- **单元测试**：35 个测试覆盖 config / data_loader / task_planner，`pytest tests/ -v` 一键运行

### 多 AI 平台原生支持
- **DeepSeek API**（默认，中文效果最佳，性价比最高）
- 适配 Claude Code、Cursor、GitHub Copilot、Windsurf、Aider 等主流 AI 助手
- 离线演示模式，无需 API 也能运行

### 专业可视化
自动生成柱状图、箱线图、散点图、相关性热力图，已修复中文乱码问题。

## 快速开始

### 环境要求
- Python 3.9+
- （可选）DeepSeek API Key（从 [DeepSeek 开放平台](https://platform.deepseek.com/) 获取）

### 1. 克隆仓库
```bash
git clone https://github.com/your-username/huginn.git
cd huginn
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置 API 密钥
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. 运行智能体
```bash
# 在线模式（调用 DeepSeek API，推荐）
python agent_runner.py "你的课程问卷.csv" "为下一次上课的老师生成课程建议报告"

# 离线模式（不调用 API，用于演示和测试）
python agent_runner.py "你的课程问卷.csv" "为下一次上课的老师生成课程建议报告" --offline
```

### 5. 启动 Web 界面（可选）
```bash
streamlit run app.py
```

### 6. 查看结果
运行完成后，所有结果保存在 `outputs/YYYYMMDD_HHMMSS_文件名/` 目录下：
```
outputs/20260610_143022_课程问卷/
├── data_profile.json          # 数据画像
├── stats_results.json         # 完整统计结果
├── valid_tasks.json           # 已执行的分析任务
├── findings.json              # 核心数据发现（LLM 生成）
├── suggestions.json           # 课程改进建议（LLM 生成）
├── charts/                    # 可视化图表
│   ├── bar_chart.png
│   ├── box_plot.png
│   ├── scatter_plot.png
│   └── correlation_heatmap.png
├── final_report.md            # 完整课程分析报告（7章 + 附录）
├── final_report.docx          # Word 格式报告（可选导出）
├── validation_result.json     # 合规性验证结果（JSON）
└── validation_report.md       # 合规性验证报告（Markdown）
```

### 7. 运行测试（可选）
```bash
# 验证所有模块正常工作
pytest tests/ -v

# 预期输出：35 passed in 0.30s
```

## 使用方法

### 命令行参数
```bash
python agent_runner.py <数据文件路径> <分析需求> [选项]

选项：
  --offline    离线模式，不调用 API，使用预生成结果演示
  --help       显示帮助信息
```

### 生成报告（独立运行）
```bash
# 从已有的运行结果生成 Markdown 报告
python report_generator.py "outputs/20260610_143022_课程问卷" "为下一次上课的老师生成课程建议报告"

# 导出 Word 格式
python report_generator.py "outputs/20260610_143022_课程问卷" "为下一次上课的老师生成课程建议报告" --format word
```

### 单独运行模块
```bash
# 仅加载清洗数据
python data_loader.py "你的文件.csv"

# 仅生成数据画像
python data_profiler.py "你的文件.csv"

# 仅执行统计分析（全量模式）
python analysis_engine.py "你的文件.csv"

# 仅生成图表
python chart_generator.py "你的文件.csv"

# 仅提炼显著性洞察（需要已有统计结果）
python insight_generator.py "outputs/<run_dir>/stats_results.json"

# 仅生成报告（需要已有运行结果）
python report_generator.py "outputs/<run_dir>" "分析需求"

# 仅验证报告合规性
python report_validator.py "outputs/<run_dir>"

# 导出 Word 格式报告
python report_generator.py "outputs/<run_dir>" "分析需求" --format word
```

### 一键全流程（v4 兼容入口，无 LLM）
```bash
python main.py "你的文件.csv"
```

### 与 AI 助手集成
本项目原生支持所有主流 AI 编程助手，只需复制对应平台的配置文件即可：
- **Claude Code**: 安装 Skill：`cp skill/SKILL.md ~/.claude/skills/stat-analysis/`
- **Cursor**: 复制 `platforms/cursor/.cursorrules` 到项目根目录
- **GitHub Copilot**: 复制 `platforms/copilot/.github-copilot-instructions.md` 到 `.github/`
- **Windsurf**: 复制 `platforms/windsurf/.windsurfrules` 到项目根目录
- **Aider**: `aider --conventions platforms/aider/CONVENTIONS.md`
- **Continue.dev**: 合并 `platforms/continue_dev/config.json` 到 `~/.continue/config.json`
- **ChatGPT / DeepSeek / Kimi**: 打开 `platforms/general/COPY_PASTE_PROMPT.txt`，全文复制粘贴到对话框

## 项目结构
```
huginn/
├── agent_runner.py              # 智能体主流程控制器（9步完整管线）
├── report_generator.py          # 完整报告生成器（Markdown + Word）
├── app.py                       # Streamlit 交互式 Web 界面
├── config.py                    # 🆕 集中化配置管理（支持环境变量覆盖）
├── logger.py                    # 🆕 统一日志模块（幂等初始化）
├── llm_client.py                # DeepSeek API 封装（结构化输出）
├── task_planner.py              # 任务筛选与校验器
├── analysis_engine.py           # 核心统计分析引擎（全量 + 按需双模式）
├── analysis_engine_patch.py     # 向后兼容 shim（已合并至 analysis_engine.py）
├── report_validator.py          # 报告合规性验证器（100分制）
├── data_loader.py               # 数据加载与清洗（成员A）
├── data_profiler.py             # 数据画像生成（成员A）
├── chart_generator.py           # 可视化图表生成（成员A）
├── insight_generator.py         # 基础洞察提炼（成员A）
├── main.py                      # 一键全流程入口（v4兼容，无LLM）
├── .env.example                 # 环境变量模板
├── .gitignore                   # Git 忽略文件
├── requirements.txt             # 依赖清单
├── README.md                    # 本文件
├── tests/                       # 🆕 单元测试
│   ├── conftest.py              # 共享测试夹具
│   ├── test_config.py           # 配置模块测试
│   ├── test_data_loader.py      # 数据加载测试
│   └── test_task_planner.py     # 任务筛选测试
├── platforms/                   # 各 AI 平台适配文件
│   ├── cursor/
│   ├── copilot/
│   ├── windsurf/
│   ├── aider/
│   ├── continue_dev/
│   └── general/
├── skill/                       # Claude Code Skill 定义
└── outputs/                     # 运行结果输出目录
```

## 核心模块说明

### 1. 数据加载与清洗 (`data_loader.py`)
- 自动识别 CSV 编码（utf-8 / gbk / gb18030）和分隔符
- 自动清洗表头、处理空行和缺失值
- **智能数值提取**：自动将 Likert 量表字符串（如 `"5（非常感兴趣）"`、`"B.1-2小时"`、`"10小时"`）转换为数值，大幅提升可用数值列数量
- 自动推断数据类型（数值 / 日期 / 分类），兼容 pandas 2 和 pandas 3
- 支持 Excel（.xlsx / .xls）和 CSV 格式

### 2. 统计分析引擎 (`analysis_engine.py`)
- **双模式**：`run_all()` 全量分析 + `run_tasks(tasks)` 按需执行，统一入口
- 基于 scipy 和 statsmodels 实现所有统计方法
- **自动补齐**：点估计/区间估计覆盖全部数值列，自动补齐分布检验和卡方拟合优度检验
- 内置数量自查机制，确保满足最低统计要求
- 所有结果可溯源，自动保存完整计算过程
- `analysis_engine_patch.py` 为向后兼容 shim，实际逻辑已合并至主引擎

### 3. LLM 客户端 (`llm_client.py`)
- 封装 DeepSeek API，使用 `json_object` 模式 + Pydantic 手动解析（兼容 DeepSeek 不支持的 `beta.chat.completions.parse`）
- 自动处理速率限制和超时重试（重试次数、延迟等由 `config.py` 统一管理）
- 内置离线模式：**动态基于统计结果自动生成发现和建议**，无需硬编码演示数据
- 严格的提示词约束，内置显著结果预扫描和 p≥0.05 处理规则，杜绝幻觉和编造数据
- 所有参数（模型、温度、最大 token 等）通过 `Config` 类读取，支持环境变量覆盖

### 4. 任务筛选器 (`task_planner.py`)
- 严格校验 LLM 提出的问题，过滤不可执行的任务
- 自动补充默认任务，确保满足统计数量要求，**自动排除序号、常量列等不适合分析的字段**
- 按优先级排序（ANOVA > 卡方 > t 检验 > 其他）
- 内置最大迭代限制，防止数据类型不足时无限循环
- 详细记录每个问题被过滤的原因，便于调试

### 5. 洞察提炼器 (`insight_generator.py`)
- 自动读取 `stats_results.json`，筛选 p < 0.05 的显著发现
- 提取强相关特征，生成可操作的研究问题
- 支持 JSON 和 Markdown 双格式输出
- 独立于 LLM，基于规则引擎保证结果确定性

### 6. 报告生成器 (`report_generator.py`)
- 读取所有中间 JSON 结果，自动组装 7 章完整报告
- **执行摘要**：报告头部展示显著结果统计、验证得分等核心信息
- **字段名智能清洗**：自动去除问卷平台的技术前缀（如 `col_122._`），保留可读的中文名称
- 仅筛选 p < 0.05 的显著统计结果展示
- 自动插入图表引用，集成合规性验证附录
- 支持 Markdown（原生）和 Word（python-docx）两种导出格式
- 可独立运行，也可集成在 agent_runner 管线中

### 7. 报告验证器 (`report_validator.py`)
- 5 大模块 20+ 检查项，覆盖课程作业所有验收标准
- 100 分制评分体系，60 分及格
- **智能证据检查**：接受假设检验（t/F/χ² + p 值）和描述性统计（均值/标准差/CV）两种证据格式
- **智能模糊词检测**：排除问卷字段名中天然包含的词汇（如"觉得"在"你觉得..."中）
- 自动检查 `final_report.md` 中的局限性章节
- 输出 JSON 和 Markdown 两种格式

### 8. Web 界面 (`app.py`)
- 基于 Streamlit 的交互式分析界面
- 支持文件上传、需求输入、离线模式切换
- **执行统计面板**：概览页展示任务数、发现数、验证分数等关键指标
- **手风琴式报告预览**：完整报告按章节折叠展开，避免一次性加载过长内容
- 标签页展示所有分析结果（概况 / 图表 / 统计 / 发现 / 建议 / 验证 / 完整报告）
- **字段名自动清洗**：界面中所有字段名均显示为可读格式
- 一键下载 Markdown 报告、Word 报告、统计结果 JSON、ZIP 打包

### 9. 集中配置 (`config.py`)  — 🆕
- 所有硬编码常量集中管理，支持环境变量覆盖
- 涵盖 LLM 参数、任务阈值、显著性水平、禁止词汇、UI 标签等 60+ 配置项
- **共享工具函数**：`clean_field_name()` 供全项目模块导入，统一清洗问卷平台技术前缀
- 修改 `config.py` 即可全局生效，无需逐个文件查找修改
- 关键环境变量：`LLM_MODEL`、`LLM_MAX_RETRIES`、`LLM_TEMPERATURE`、`TASK_MIN_COUNT` 等

### 10. 统一日志 (`logger.py`)  — 🆕

### 11. 数据画像器 (`data_profiler.py`)
- 自动计算每个字段的类型、缺失率、频数分布、数值统计等
- **数值型离散字段**（如 Likert 量表 1-5 评分）同样计算完整数值统计（均值、标准差、偏度、峰度等）
- 输出标准化 `data_profile.json`，供后续所有模块使用

### 12. 图表生成器 (`chart_generator.py`)
- 自动生成柱状图、箱线图、散点图和相关性热力图
- **图表标题和标签自动清洗**：字段名去技术前缀，可读性强
- 中文字体自动检测和配置

### 13. 一键入口 (`main.py`)
- 无 LLM 依赖的纯统计管线：加载 → 画像 → 分析 → 图表 → 洞察
- 供 CI/CD 或无法访问 API 的环境使用
- 输出与 `agent_runner.py` 兼容的标准化 JSON 结果
- 幂等 `get_logger(name)` 函数，确保 `basicConfig` 仅执行一次
- 所有模块共享统一的日志格式：`时间 [级别] 模块名: 消息`
- 解决模块被 import 时日志静默丢失的问题
- 输出至 stderr，与用户界面 `print()` 输出互不干扰

## 课程作业验收标准
本项目严格按照以下标准设计，确保生成的报告 100% 符合要求：

| 检查项 | 最低要求 | 对应 Config 键 |
|--------|----------|---------------|
| 点估计 | ≥5 个 | `REQUIREMENTS["point_estimation_min"]` |
| 区间估计 | ≥5 个 | `REQUIREMENTS["interval_estimation_min"]` |
| 假设检验 | ≥5 类 | `REQUIREMENTS["hypothesis_test_min"]` |
| 方差分析 (ANOVA) | ≥2 项 | `REQUIREMENTS["anova_min"]` |
| 卡方检验 | ≥2 个 | `REQUIREMENTS["chi_square_min"]` |
| 数据发现 | ≥5 条 | — |
| 课程建议 | ≥3 条 | — |
| 可视化图表 | ≥3 张 | — |
| 局限性说明 | 必须包含 | — |
| 因果关系 | 禁止将相关性表述为因果关系 | `CAUSAL_WORDS`（禁止词汇列表） |

## 常见问题

### Q: 运行提示 ModuleNotFoundError 怎么办？
A: 确保已安装所有依赖：`pip install -r requirements.txt`

### Q: DeepSeek API 调用失败怎么办？
A: 检查 API Key 是否正确，网络是否正常，或使用 `--offline` 参数运行离线模式。

### Q: 图表中文显示方块怎么办？
A: `chart_generator.py` 已自动搜索并配置系统中文字体（macOS PingFang / Windows SimHei / Linux Noto CJK）。如果仍无效，可手动安装中文字体后重试。

### Q: 统计数量不达标怎么办？
A: 分析引擎会自动对全部数值列执行点估计和区间估计，并自动补齐分布检验和卡方拟合优度。如果仍不达标，检查数据中是否有足够的数值列和分类列。提示：包含字符串格式 Likert 量表的数据（如 `"5（非常感兴趣）"`）现已被智能识别并转换为数值。

### Q: 生成的发现和建议质量不高怎么办？
A: 优化用户需求描述，提供更明确的业务背景；或调整 `llm_client.py` 中的提示词。离线模式现已动态基于统计结果自动生成发现和建议，无需依赖硬编码演示数据。

### Q: 如何导出 Word 报告？
A:
```bash
# 方式1：在 agent_runner 运行后单独导出
python report_generator.py "outputs/<运行目录>" "分析需求" --format word

# 方式2：在 Python 代码中调用
from report_generator import ReportGenerator
gen = ReportGenerator("outputs/<运行目录>", "分析需求")
gen.export_word("final_report.docx")
```

### Q: 如何启动 Web 界面？
A:
```bash
streamlit run app.py
```
然后在浏览器打开 `http://localhost:8501`，上传文件即可开始分析。

### Q: 如何自定义 LLM 参数（模型、温度等）？
A: 无需修改代码，通过环境变量即可覆盖默认值：
```bash
# 使用不同的模型
export LLM_MODEL=deepseek-reasoner

# 调整重试次数和延迟
export LLM_MAX_RETRIES=5
export LLM_RETRY_DELAY=5

# 调整输出温度（0-1，越低越稳定）
export LLM_TEMPERATURE=0.1

# 然后正常运行
python agent_runner.py "数据.csv" "分析需求"
```
更多可配置项参见 `config.py`，所有配置均支持 `KEY=VALUE` 环境变量覆盖。

### Q: 如何切换到其他 LLM 提供商（如 OpenAI）？
A: 项目使用 OpenAI 兼容 SDK，切换只需修改环境变量：
```bash
export DEEPSEEK_BASE_URL=https://api.openai.com/v1   # OpenAI 或其他兼容端点
export LLM_MODEL=gpt-4o                               # 模型名
export DEEPSEEK_API_KEY=sk-your-openai-key            # API Key
```
任何兼容 OpenAI API 格式的服务（如 Groq、Together、vLLM 等）均可直接使用。注意：如使用 OpenAI 原生服务，可以恢复 `client.beta.chat.completions.parse()` 调用以使用原生结构化输出功能。

### Q: 如何贡献代码？
A: 欢迎提交 Issue 和 Pull Request！贡献前请：
1. 阅读下方 [开发指南](#开发指南)
2. 确保 `pytest tests/ -v` 全部通过（预期 35 passed）
3. 遵循 PEP 8 代码规范，使用类型注解
4. 新增功能需补充对应测试用例

### Q: 如何运行测试？
A: 测试依赖已包含在 `requirements.txt` 中（`pytest>=7.0`）：
```bash
pytest tests/ -v              # 全部测试（预期 35 passed）
pytest tests/ -v --tb=short   # 简洁输出模式
```
详见下方 [开发指南 → 运行测试](#运行测试)。

## 🛠️ 开发指南

### 项目架构

```
┌──────────────────────────────────────────────────────────┐
│                     入口层                               │
│  agent_runner.py (9步管线)    main.py (5步无LLM管线)     │
│  app.py (Streamlit Web)                                  │
└──────────┬──────────┬──────────┬────────────┬───────────┘
           │          │          │            │
    ┌──────▼──┐ ┌─────▼────┐ ┌──▼──────┐ ┌───▼──────────┐
    │数据层   │ │智能层    │ │报告层   │ │基础设施层     │
    │loader   │ │llm_client│ │report   │ │config.py      │
    │profiler │ │planner   │ │generator│ │logger.py      │
    │engine   │ │insight   │ │validator│ │tests/         │
    │charts   │ │          │ │         │ │               │
    └─────────┘ └──────────┘ └─────────┘ └───────────────┘
```

- **数据层**：数据加载 → 画像 → 统计计算 → 图表生成（纯 Python，无 LLM 依赖）
- **智能层**：LLM 生成候选问题 → 任务筛选 → 执行 → 发现与建议提炼
- **报告层**：读取中间 JSON → 组装 7 章报告 → 合规性验证 → 导出 Markdown/Word
- **基础设施层**：配置管理、日志系统、单元测试

### 环境搭建
```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 代码规范
- 遵循 PEP 8 代码规范
- 使用类型注解
- 编写详细的文档字符串
- 提交前运行代码格式化：`black .`
- 提交前运行测试：`pytest tests/ -v`

### 运行测试
```bash
# 全部测试
pytest tests/ -v

# 指定模块
pytest tests/test_config.py -v
pytest tests/test_data_loader.py -v
pytest tests/test_task_planner.py -v
```
测试覆盖：
- `test_config.py` — Config 默认值 + 环境变量覆盖（11 个测试）
- `test_data_loader.py` — CSV/编码/中文/异常场景（9 个测试）
- `test_task_planner.py` — 验证逻辑 + 筛选流程 + 优先级排序（15 个测试）

### 配置管理
所有硬编码值均由 `config.py` 中的 `Config` 类集中管理。修改默认值或通过环境变量覆盖：
```bash
# 查看所有可配置项
grep "env(" config.py

# 通过环境变量覆盖（示例）
export LLM_MODEL=deepseek-chat        # LLM 模型名
export LLM_MAX_RETRIES=3              # API 最大重试次数
export TASK_MIN_COUNT=5               # 最少分析任务数
export TASK_MAX_COUNT=10              # 最多分析任务数
export OUTPUT_DIR=./outputs           # 结果输出目录
export SIGNIFICANCE_THRESHOLD=0.05    # 显著性阈值
```

### 扩展功能
- **修改默认参数**：编辑 `config.py` 中的 `Config` 类属性
- **添加新的统计方法**：修改 `analysis_engine.py`，在 `AnalysisEngine` 类中添加对应方法，并在 `_METHOD_DISPATCH` 字典中注册
- **适配其他 LLM API**：修改 `llm_client.py`，实现对应的 API 调用逻辑
- **添加新的图表类型**：修改 `chart_generator.py`，添加对应的绘图方法
- **扩展报告模板**：修改 `report_generator.py` 中的章节渲染方法
- **自定义 Streamlit 界面**：修改 `app.py`，添加新的标签页或组件
- **添加测试**：在 `tests/` 目录下新建 `test_*.py`，参考 `conftest.py` 中的 fixture

## 许可证
本项目采用 MIT 许可证，详情请参见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  <sub>Built with ☕️️ by Robusr👨🏻‍💻 </sub>
</p>
