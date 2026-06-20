# Huginn - AI 驱动的多领域探索型数据分析智能体

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/DeepSeek-API-orange.svg" alt="DeepSeek API">
  <img src="https://img.shields.io/badge/Tests-38%20passed-success.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Domains-3%20types-informational.svg" alt="Domains">
  <img src="https://img.shields.io/badge/Status-Stable-brightgreen.svg" alt="Status">
</p>

> **全自动数据分析智能体**：上传 Excel/CSV 表格，自动完成**领域检测** → 智能数据清洗 → **字段角色推断** → 统计推断 → 可视化 → **4 轮 LLM 洞察提炼** → **域自适应报告生成** → 合规性验证。覆盖**零售销售**、**教育问卷**、**通用数据**三大领域，零售场景自动激活亏损驱动分析、折扣响应分析、集中度分析、交叉维度分析四大业务模块。严格遵循"**模型只做决策和解释，所有统计量由 Python 真实计算**"的核心原则，内置**结构化证据表**彻底杜绝 LLM 幻觉。合规性验证最高可达 **100/100**。

---

## 核心功能

### 🌐 多领域自动检测
- **三大预定义领域**：零售销售 / 教育问卷 / 通用数据
- **自动领域检测**：根据列名模式自动识别数据领域，驱动 LLM 提示词、报告模板、业务分析模块的域感知行为
- **手动覆盖**：支持 `--domain retail_sales` 显式指定领域
- **字段角色注册表**：自动推断每列的商务角色（ID / 收入 / 利润 / 折扣 / 维度 / 地理位置等），输出 `field_registry.json`

### 📊 全自动探索型分析（11 步完整管线）
无需指定分析问题，智能体自动理解数据结构、检测领域类型、推断字段角色、发现值得研究的业务问题，用统计方法验证，并**一键生成域自适应的完整分析报告**。

### 🏪 零售业务分析模块（零售领域自动激活）
- **亏损驱动分析**：按 8 个维度（品类、子品类、区域、客群、运输方式、折扣分箱等）分组计算亏损率、亏损金额、亏损贡献度
- **折扣响应分析**：折扣分箱、利润拐点识别（21-30% 区间）、品类内分层、异常检测
- **集中度分析（Pareto）**：产品/客户/子品类 Top-N 分析、累计贡献率曲线、高销售低利润识别
- **交叉维度分析**：自动生成有效维度组合（Region × Category、Segment × Category 等）、交叉制表、交互效应检测

### 🧠 4 轮 LLM 深度推理（证据驱动）
- **第 1 轮 — 任务规划**：根据数据画像和领域上下文生成 8-12 个候选分析任务
- **第 2 轮 — 问题发现**：基于统计结果和证据表，发现值得深挖的业务问题
- **第 3 轮 — 发现与建议**：生成基于证据的数据发现（5 要素结构：结论 + 量级 + 基线 + 归因线索 + 业务影响）和改进建议
- **第 4 轮 — 报告写作**：撰写和润色正式分析报告，引用证据表中的统计路径
- **结构化证据表**：所有业务模块写入中央证据表，LLM 只能引用不能编造，杜绝幻觉

### 学术级统计分析
- 点估计（均值、方差、标准差、中位数等 10 个参数）
- 区间估计（均值、方差、标准差、中位数、预测区间）
- 6 类假设检验（t 检验、配对 t 检验、Wilcoxon、Mann-Whitney 等）
- 单因素/双因素方差分析（ANOVA）+ Tukey 事后检验
- 皮尔逊卡方检验（拟合优度 + 独立性检验）
- 正态性检验（Shapiro-Wilk + D'Agostino-Pearson）
- 相关性分析

### 自动报告生成
- **域自适应报告**：零售 8 章 / 教育 7 章 / 通用 7 章，章节标题随领域自动调整
- **执行摘要**：报告头部展示显著结果统计、验证得分、LLM 审计信息
- **附录**：自动集成合规性验证得分、各模块详细结果、LLM 调用审计
- **Word 导出**：支持一键导出 `.docx` 格式报告
- 所有统计量可溯源至 JSON 原始结果，杜绝编造

### 自动合规性验证
内置多领域验证器，分析完成后自动运行并写入报告附录：
- **统计数量硬指标（30分）**：≥5 点估计 / ≥5 区间估计 / ≥5 假设检验 / ≥2 ANOVA / ≥2 卡方
- **统计结果有效性（20分）**：p 值范围、样本量、无编造数据
- **数据发现合规性（20分）**：无因果错误、无模糊表述、引用正确
- **业务分析覆盖度（10分）**：业务分析模块是否完整覆盖
- **建议质量（10分）**：有数据依据、可落地
- **报告完整性（10分）**：章节完整、附录齐全
- 100 分制，60 分及格

### 交互式 Web 界面
- **Streamlit 应用**：`streamlit run app.py` 一键启动
- 支持文件上传、需求输入、离线模式切换
- 标签页展示：概况 / 图表 / 统计 / 发现 / 建议 / 验证 / 完整报告
- 一键下载 Markdown 报告、Word 报告、统计结果 JSON、**ZIP 打包**

### 工程化基础设施
- **集中化配置**：`config.py` 管理 60+ 配置项，涵盖 LLM 参数、统计阈值、领域模块开关、UI 标签、评分权重等，支持环境变量覆盖
- **统一日志**：`logger.py` 幂等初始化，消除模块 import 时日志静默丢失的问题
- **单元测试**：38 个测试覆盖完整分析链、领域检测、字段角色推断，`pytest tests/ -v` 一键运行

### 多 AI 平台原生支持
- **DeepSeek API**（默认，中文效果最佳，性价比最高）
- 适配 Claude Code、Cursor、GitHub Copilot、Windsurf、Aider 等主流 AI 助手
- 离线演示模式，无需 API 也能运行

### 专业可视化
自动生成柱状图、箱线图、散点图、相关性热力图，已修复中文乱码问题。

---

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
# 教育问卷
python agent_runner.py "你的课程问卷.csv" "为下一次上课的老师生成课程建议报告"

# 零售销售
python agent_runner.py "销售数据.csv" "分析经营问题，提出改进建议"

# 手动指定领域
python agent_runner.py "数据.csv" "分析数据" --domain retail_sales

# 离线模式（不调用 API，用于演示和测试）
python agent_runner.py "你的课程问卷.csv" "生成课程建议报告" --offline
```

### 5. 启动 Web 界面（可选）
```bash
streamlit run app.py
```

### 6. 查看结果
运行完成后，所有结果保存在 `outputs/YYYYMMDD_HHMMSS_文件名/` 目录下：
```
outputs/20260620_143022_课程问卷/
├── data_profile.json              # 数据画像
├── field_registry.json            # 字段角色注册表
├── stats_results.json             # 完整统计结果
├── valid_tasks.json               # 已执行的分析任务
├── evidence_table.json            # 结构化证据表（零售领域）
├── granularity.json               # 数据粒度检测（零售领域）
├── loss_driver_results.json       # 亏损驱动分析（零售领域）
├── discount_analysis_results.json # 折扣响应分析（零售领域）
├── pareto_results.json            # 集中度分析（零售领域）
├── cross_dimension_results.json   # 交叉维度分析（零售领域）
├── findings.json                  # 核心数据发现（LLM 生成）
├── suggestions.json               # 改进建议（LLM 生成）
├── llm_generated_report.md        # LLM 生成的报告草稿
├── llm_report.md                  # LLM 润色后的报告
├── llm_call_audit.json            # LLM 调用审计
├── charts/                        # 可视化图表
│   ├── bar_chart.png
│   ├── box_plot.png
│   ├── scatter_plot.png
│   └── correlation_heatmap.png
├── final_report.md                # 完整分析报告（域自适应章节）
├── final_report.docx              # Word 格式报告（可选导出）
├── validation_result.json         # 合规性验证结果（JSON）
└── validation_report.md           # 合规性验证报告（Markdown）
```

### 7. 运行测试（可选）
```bash
# 验证所有模块正常工作
pytest tests/ -v

# 预期输出：38 passed in ~1.7s
```

---

## 三大数据领域

### 🏪 零售销售 (`retail_sales`)
适用于包含销售额、利润、折扣、品类、地区等字段的销售明细数据。
- **自动检测特征**：同时存在 sales/profit/discount 相关字段，或匹配 ≥3 种零售字段角色
- **激活模块**：亏损驱动分析、折扣响应分析、集中度分析、交叉维度分析
- **报告标题**：`零售销售数据分析报告 — 基于销售明细的经营诊断与改进建议`
- **建议维度**：产品组合优化、定价与折扣策略、区域与渠道管理、客户分层经营、供应链与运输优化

### 🎓 教育问卷 (`education_survey`)
适用于带有 Likert 量表、课程评价、学生反馈等字段的问卷数据。
- **自动检测特征**：≥5 个 `col_N_xxx` 格式列（问卷平台导出特征）
- **激活模块**：无（主要依赖 LLM 深度推理）
- **报告标题**：`课程问卷数据统计分析报告 — 基于学生反馈的教学改进建议`
- **建议维度**：教学方法改进、课程内容优化、学习支持服务、评估方式调整、学生参与促进

### 📊 通用数据 (`general_business`)
兜底领域，适用于无法匹配零售或教育特征的其他结构化数据。
- **自动检测条件**：不满足零售 / 教育条件时兜底使用
- **报告标题**：`数据分析报告 — 基于数据探索的分析与建议`
- **建议维度**：效率改进、质量提升、成本优化、流程改善

---

## 使用方法

### 命令行参数
```bash
python agent_runner.py <数据文件路径> <分析需求> [选项]

选项：
  --offline    离线模式，不调用 API，使用离线规则生成发现和建议
  --domain     手动指定领域 (retail_sales / education_survey / general_business)
  --help       显示帮助信息
```

### 生成报告（独立运行）
```bash
# 从已有的运行结果生成 Markdown 报告
python report_generator.py "outputs/20260620_143022_课程问卷" "为下一次上课的老师生成课程建议报告"

# 导出 Word 格式
python report_generator.py "outputs/20260620_143022_课程问卷" "为下一次上课的老师生成课程建议报告" --format word
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

---

## 项目结构
```
huginn/
├── app.py                       # Streamlit 启动入口（thin wrapper）
├── main.py                      # 遗留 CLI 入口（已弃用，委托至新入口）
├── pyproject.toml               # Python 包配置
│
├── huginn/                      # 核心 Python 包
│   ├── __init__.py              # 版本信息
│   ├── core/                    # 基础设施
│   │   ├── config.py            # 集中化配置（60+ 配置项）
│   │   ├── logger.py            # 统一日志
│   │   └── label_utils.py       # 中文标签工具
│   ├── data/                    # 数据层
│   │   ├── loader.py            # CSV/Excel 加载
│   │   └── profiler.py          # 数据画像
│   ├── domain/                  # 领域检测
│   │   ├── registry.py          # 领域注册表
│   │   ├── context.py           # 领域上下文
│   │   └── fields.py            # 字段角色推断
│   ├── planning/                # 任务规划
│   │   ├── task_planner.py      # 任务筛选器
│   │   ├── analysis_planning.py # 分析规划
│   │   └── feature_miner.py     # 特色信号挖掘
│   ├── analysis/                # 统计分析
│   │   ├── engine.py            # 统计推断引擎
│   │   └── charts.py            # 图表生成
│   ├── llm/                     # LLM 客户端
│   │   └── client.py            # DeepSeek API（4 轮编排）
│   ├── reporting/               # 报告生成
│   │   ├── generator.py         # 报告生成器（MD + Word + PDF）
│   │   └── validator.py         # 合规性验证器
│   ├── web/                     # Web 界面
│   │   └── app.py               # Streamlit 应用
│   └── cli/                     # CLI 入口
│       └── runner.py            # 主流程控制器（11 步管线）
│
├── .env.example                 # 环境变量模板
├── .gitignore                   # Git 忽略规则
├── requirements.txt             # 依赖清单
├── README.md                    # 本文件
│
├── tests/                       # 单元测试（47 个）
│   ├── test_analysis_chain.py   # 全流程集成测试（~30 个）
│   └── test_domain_registry.py  # 领域检测与字段角色测试（~17 个）
│
├── platforms/                   # 各 AI 平台适配文件
│   ├── cursor/
│   ├── copilot/
│   ├── windsurf/
│   ├── aider/
│   ├── continue_dev/
│   └── general/
│
├── skill/                       # Claude Code Skill 定义
└── outputs/                     # 运行结果输出目录
```

---

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

### 3. 领域注册表 (`domain_registry.py`)
- 定义三大领域（零售销售 / 教育问卷 / 通用数据）的完整配置
- 每个领域包含：LLM persona、报告模板、建议词库、字段角色检测模式、激活模块集
- **自动检测**：`detect_domain()` 通过列名正则匹配计分，至少匹配 3 种不同角色才算有效
- **字段角色常量**：ID、日期、收入、利润、成本、数量、折扣、品类维度、地理、客户 ID、产品 ID 等 15 种角色
- 驱动 LLM 提示词、报告标题/章节、验证规则的域自适应行为

### 4. 字段角色注册表 (`field_registry.py`)
- `infer_field_role()` 根据列名模式和领域配置为每列分配商务角色
- `build_field_registry()` 生成完整注册表，标记 ID 字段、无意义字段、收入/利润/折扣字段
- 输出 `field_registry.json`，供业务分析模块和 LLM 轮次引用

### 5. 数据结构化证据表 (`evidence_table.py`)
- **防幻觉核心机制**：所有 Python 计算的事实存入证据表，LLM 只允许引用不允许编造
- `EvidenceFinding` 数据类包含 5 要素：结论、量级、对比基线、归因线索、业务影响
- 每个发现附带 `stat_reference_path`（如 `loss_driver.category.Furniture`），指向原始统计结果
- 业务分析模块（亏损驱动/折扣/集中度/交叉维度）自动写入证据表

### 6. LLM 客户端 (`llm_client.py`)
- 封装 DeepSeek API，使用 `json_object` 模式 + Pydantic 手动解析
- **4 轮 LLM 编排**：任务规划 → 问题发现 → 发现与建议 → 报告写作
- 每轮接收不同的上下文（数据画像 / 统计结果 / 证据表 / 字段注册表 / 粒度信息）
- 自动处理速率限制和超时重试（重试次数、延迟等由 `config.py` 统一管理）
- 内置离线模式：**动态基于统计结果自动生成发现和建议**，无需硬编码演示数据
- 严格的提示词约束，内置显著结果预扫描和 p≥0.05 处理规则
- 所有参数（模型、温度、最大 token 等）通过 `Config` 类读取，支持环境变量覆盖
- 输出 `llm_call_audit.json` 记录每轮调用状态

### 7. 任务筛选器 (`task_planner.py`)
- 严格校验 LLM 提出的问题，过滤不可执行的任务
- 自动补充默认任务，确保满足统计数量要求，**自动排除序号、常量列等不适合分析的字段**
- 按优先级排序（ANOVA > 卡方 > t 检验 > 其他）
- 内置最大迭代限制，防止数据类型不足时无限循环
- 详细记录每个问题被过滤的原因，便于调试

### 8. 零售业务分析模块

#### 8a. 数据粒度检测 (`granularity_detector.py`)
- 通过 ID 列唯一值比率自动识别行级实体类型
- 支持：订单行明细 / 订单级 / 客户级 / 产品级
- 输出唯一订单数、唯一客户数、唯一产品数、行数等粒度信息

#### 8b. 亏损驱动分析 (`loss_driver.py`)
- 按 8 个维度分组（品类、子品类、区域、客群、运输方式、折扣分箱等）
- 计算各分组的亏损率、亏损金额、亏损贡献百分比
- 识别主要亏损来源并写入证据表

#### 8c. 折扣响应分析 (`discount_analyzer.py`)
- 折扣分箱（如 0-10%, 10-20%, …, 80%+）
- 利润拐点识别（利润率由正转负的折扣区间）
- 品类内分层分析、异常利润点检测

#### 8d. 集中度分析 (`pareto_analyzer.py`)
- 产品/客户/子品类 Top-N 分析
- 累计贡献率曲线（前 20% 商品贡献 X% 销售额）
- 高销售额低利润产品识别

#### 8e. 交叉维度分析 (`cross_dimension.py`)
- 自动生成有效维度组合（Region × Category、Segment × Category 等）
- 交叉制表计算
- 交互效应检测

### 9. 洞察提炼器 (`insight_generator.py`)
- 自动读取 `stats_results.json`，筛选 p < 0.05 的显著发现
- 提取强相关特征，生成可操作的研究问题
- 支持 JSON 和 Markdown 双格式输出
- 独立于 LLM，基于规则引擎保证结果确定性

### 10. 报告生成器 (`report_generator.py`)
- 读取所有中间 JSON 结果，自动组装域自适应完整报告（零售 8 章 / 教育 7 章 / 通用 7 章）
- **域自适应章节**：零售报告包含"业务分析"专章，教育报告包含"教学改进建议"专章
- **执行摘要**：报告头部展示显著结果统计、验证得分、LLM 审计等核心信息
- **字段名智能清洗**：自动去除问卷平台的技术前缀（如 `col_122._`），保留可读的中文名称
- 仅筛选 p < 0.05 的显著统计结果展示
- 自动插入图表引用，集成合规性验证附录
- 支持 Markdown（原生）和 Word（python-docx）两种导出格式
- 可独立运行，也可集成在 agent_runner 管线中

### 11. 报告验证器 (`report_validator.py`)
- 6 大模块 20+ 检查项，覆盖多领域验收标准
- **评分权重**：统计数量(30分) + 统计有效性(20分) + 发现合规性(20分) + 业务覆盖度(10分) + 建议质量(10分) + 报告完整性(10分)
- 100 分制评分体系，60 分及格
- **智能证据检查**：接受假设检验（t/F/χ² + p 值）和描述性统计（均值/标准差/CV）两种证据格式
- **智能模糊词检测**：排除问卷字段名中天然包含的词汇（如"觉得"在"你觉得..."中）
- **业务分析覆盖度检查**（新增）：验证零售领域的 4 个业务模块是否完整覆盖
- 自动检查 `final_report.md` 中的局限性章节
- 输出 JSON 和 Markdown 两种格式

### 12. Web 界面 (`app.py`)
- 基于 Streamlit 的交互式分析界面
- 支持文件上传、需求输入、离线模式切换
- **执行统计面板**：概览页展示任务数、发现数、验证分数等关键指标
- **手风琴式报告预览**：完整报告按章节折叠展开，避免一次性加载过长内容
- 标签页展示所有分析结果（概况 / 图表 / 统计 / 发现 / 建议 / 验证 / 完整报告）
- **字段名自动清洗**：界面中所有字段名均显示为可读格式
- 一键下载 Markdown 报告、Word 报告、统计结果 JSON、ZIP 打包

### 13. 集中配置 (`config.py`)
- 所有硬编码常量集中管理，支持环境变量覆盖
- 涵盖 LLM 参数、任务阈值、显著性水平、领域模块开关、评分权重、禁止词汇、UI 标签等 60+ 配置项
- **共享工具函数**：`clean_field_name()` 供全项目模块导入，统一清洗问卷平台技术前缀
- **领域模块开关**：`DOMAIN_MODULES` 按领域配置，`BUSINESS_MODULES_ENABLED` 通过环境变量单独控制
- 修改 `config.py` 即可全局生效，无需逐个文件查找修改
- 关键环境变量：`LLM_MODEL`、`LLM_MAX_RETRIES`、`LLM_TEMPERATURE`、`TASK_MIN_COUNT`、`ENABLE_LOSS_DRIVER` 等

### 14. 统一日志 (`logger.py`)
- 幂等 `get_logger(name)` 函数，确保 `basicConfig` 仅执行一次
- 所有模块共享统一的日志格式：`时间 [级别] 模块名: 消息`
- 解决模块被 import 时日志静默丢失的问题
- 输出至 stderr，与用户界面 `print()` 输出互不干扰

### 15. 数据画像器 (`data_profiler.py`)
- 自动计算每个字段的类型、缺失率、频数分布、数值统计等
- **数值型离散字段**（如 Likert 量表 1-5 评分）同样计算完整数值统计（均值、标准差、偏度、峰度等）
- 输出标准化 `data_profile.json`，供后续所有模块使用

### 16. 图表生成器 (`chart_generator.py`)
- 自动生成柱状图、箱线图、散点图和相关性热力图
- **图表标题和标签自动清洗**：字段名去技术前缀，可读性强
- 中文字体自动检测和配置

### 17. 一键入口 (`main.py`)
- 无 LLM 依赖的纯统计管线：加载 → 画像 → 分析 → 图表 → 洞察
- 供 CI/CD 或无法访问 API 的环境使用
- 输出与 `agent_runner.py` 兼容的标准化 JSON 结果

---

## 分析管线详解

```
┌─────────────────────────────────────────────────────────────────────┐
│  步骤 1:  数据加载与清洗          (data_loader.py)                   │
│  步骤 2:  数据画像生成            (data_profiler.py)                 │
│  步骤 2a: 领域检测                (domain_registry.py)               │
│  步骤 2b: 字段角色注册表          (field_registry.py)                │
│  步骤 3:  LLM 第 1 轮 — 候选任务  (llm_client.py)                   │
│  步骤 4:  任务筛选与校验          (task_planner.py)                  │
│  步骤 5:  统计分析执行            (analysis_engine.py)               │
│  步骤 5b: 业务分析模块 (零售)      (loss/discount/pareto/cross_dim)  │
│  步骤 6:  可视化图表生成          (chart_generator.py)               │
│  步骤 7:  LLM 第 2 轮 — 问题发现  (llm_client.py)                   │
│  步骤 8:  LLM 第 3 轮 — 发现建议  (llm_client.py)                   │
│  步骤 9:  LLM 第 4 轮 — 报告写作  (llm_client.py)                   │
│  步骤 10: 结构化报告生成          (report_generator.py)              │
│  步骤 11: 合规性验证              (report_validator.py)              │
└─────────────────────────────────────────────────────────────────────┘
```

**核心设计原则**：
- 数据画像 → 领域检测 → 字段角色推断 → 任务规划 → 统计分析 → 业务模块 → 证据表 → LLM 推理 → 报告生成
- LLM 仅做决策和解释，所有统计量由 Python 真实计算
- 证据表（`evidence_table.py`）是防幻觉的中央事实存储，LLM 只能引用不能编造
- 领域配置驱动全流程的域自适应行为（提示词、报告模板、验证规则）

---

## 合规性验收标准

本项目严格按照验收标准设计，确保生成的报告符合要求：

| 检查项 | 最低要求 | 对应 Config 键 |
|--------|----------|---------------|
| 点估计 | ≥5 个 | `REQUIREMENTS["point_estimation_min"]` |
| 区间估计 | ≥5 个 | `REQUIREMENTS["interval_estimation_min"]` |
| 假设检验 | ≥5 类 | `REQUIREMENTS["hypothesis_test_min"]` |
| 方差分析 (ANOVA) | ≥2 项 | `REQUIREMENTS["anova_min"]` |
| 卡方检验 | ≥2 个 | `REQUIREMENTS["chi_square_min"]` |
| 数据发现 | ≥5 条 | — |
| 改进建议 | ≥3 条 | — |
| 可视化图表 | ≥3 张 | — |
| 局限性说明 | 必须包含 | — |
| 因果关系 | 禁止将相关性表述为因果关系 | `CAUSAL_WORDS`（禁止词汇列表） |
| 业务分析覆盖（零售） | 4 个模块完整 | `BUSINESS_MODULES_ENABLED` |

---

## 常见问题

### Q: 运行提示 ModuleNotFoundError 怎么办？
A: 确保已安装所有依赖：`pip install -r requirements.txt`

### Q: DeepSeek API 调用失败怎么办？
A: 检查 API Key 是否正确，网络是否正常，或使用 `--offline` 参数运行离线模式。

### Q: 如何选择正确的数据领域？
A: 默认自动检测，也可以手动指定：
```bash
python agent_runner.py "数据.csv" "分析需求" --domain retail_sales     # 零售
python agent_runner.py "数据.csv" "分析需求" --domain education_survey # 教育
python agent_runner.py "数据.csv" "分析需求" --domain general_business # 通用
```

### Q: 零售领域的业务分析模块如何开启/关闭？
A: 通过环境变量控制单个模块：
```bash
export ENABLE_LOSS_DRIVER=false      # 关闭亏损驱动分析
export ENABLE_DISCOUNT_ANALYZER=false # 关闭折扣响应分析
export ENABLE_PARETO=false           # 关闭集中度分析
export ENABLE_CROSS_DIM=false        # 关闭交叉维度分析
```

### Q: LLM 调用轮次可以调整吗？
A: 可通过环境变量调整（默认 4 轮）：
```bash
export LLM_MAX_ROUNDS=2   # 减少到 2 轮（任务规划 + 报告写作）
```

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
2. 确保 `pytest tests/ -v` 全部通过（预期 38 passed）
3. 遵循 PEP 8 代码规范，使用类型注解
4. 新增功能需补充对应测试用例

### Q: 如何运行测试？
A: 测试依赖已包含在 `requirements.txt` 中（`pytest>=7.0`）：
```bash
pytest tests/ -v              # 全部测试（预期 38 passed）
pytest tests/ -v --tb=short   # 简洁输出模式
```
详见下方 [开发指南 → 运行测试](#运行测试)。

---

## 🛠️ 开发指南

### 项目架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        入口层                                     │
│  agent_runner.py (11步管线)   main.py (5步无LLM管线)              │
│  app.py (Streamlit Web)                                          │
└────┬──────────┬──────────┬──────────┬───────────────┬───────────┘
     │          │          │          │               │
┌────▼───┐ ┌───▼────┐ ┌───▼────┐ ┌───▼───────┐ ┌────▼──────────┐
│数据层  │ │领域层  │ │智能层  │ │报告层     │ │基础设施层     │
│loader  │ │domain  │ │llm     │ │report     │ │config.py      │
│profiler│ │field   │ │planner │ │generator  │ │logger.py      │
│engine  │ │evidence│ │        │ │validator  │ │tests/         │
│charts  │ │granular│ │        │ │           │ │               │
│insight │ │        │ │        │ │           │ │               │
│        │ │        │ │        │ │           │ │               │
│(纯Py)  │ │(域感知)│ │(LLM)   │ │(模板+验证)│ │(配置+日志)    │
└────────┘ └────────┘ └────────┘ └───────────┘ └───────────────┘

业务分析模块 (零售领域自动激活):
  loss_driver / discount_analyzer / pareto_analyzer / cross_dimension
```

- **数据层**：数据加载 → 画像 → 统计计算 → 图表生成（纯 Python，无 LLM 依赖）
- **领域层**：领域检测 → 字段角色推断 → 粒度检测 → 证据表写入（域感知，驱动全流程自适应）
- **智能层**：4 轮 LLM 编排 — 候选任务 → 问题发现 → 发现与建议 → 报告写作（证据驱动，防幻觉）
- **报告层**：读取中间 JSON → 组装域自适应报告 → 合规性验证 → 导出 Markdown/Word
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
pytest tests/test_analysis_chain.py -v
pytest tests/test_domain_registry.py -v
```
测试覆盖：
- `test_analysis_chain.py` — 全流程集成测试：领域上下文、任务规划、数据加载、统计推断、报告生成、合规性验证
- `test_domain_registry.py` — 领域检测 + 字段角色推断 + 注册表构建

### 配置管理
所有硬编码值均由 `config.py` 中的 `Config` 类集中管理。修改默认值或通过环境变量覆盖：
```bash
# 查看所有可配置项
grep "env(" config.py

# 通过环境变量覆盖（示例）
export LLM_MODEL=deepseek-chat              # LLM 模型名
export LLM_MAX_RETRIES=3                    # API 最大重试次数
export LLM_MAX_ROUNDS=4                     # LLM 调用最大轮次
export TASK_MIN_COUNT=5                     # 最少分析任务数
export TASK_MAX_COUNT=10                    # 最多分析任务数
export OUTPUT_DIR=./outputs                 # 结果输出目录
export SIGNIFICANCE_THRESHOLD=0.05          # 显著性阈值
export ENABLE_LOSS_DRIVER=true              # 启用亏损驱动分析
export ENABLE_DISCOUNT_ANALYZER=true        # 启用折扣响应分析
export ENABLE_PARETO=true                   # 启用集中度分析
export ENABLE_CROSS_DIM=true                # 启用交叉维度分析
```

### 扩展功能
- **新增数据领域**：在 `domain_registry.py` 中定义新的 `DomainConfig`，加入 `ALL_DOMAINS` 列表
- **新增业务分析模块**：创建模块文件 → 在 `Config.DOMAIN_MODULES` 中注册 → 在 `agent_runner.py` 步骤 5b 中编排调用
- **修改默认参数**：编辑 `config.py` 中的 `Config` 类属性
- **添加新的统计方法**：修改 `analysis_engine.py`，在 `AnalysisEngine` 类中添加对应方法，并在 `_METHOD_DISPATCH` 字典中注册
- **适配其他 LLM API**：修改 `llm_client.py`，实现对应的 API 调用逻辑
- **添加新的图表类型**：修改 `chart_generator.py`，添加对应的绘图方法
- **扩展报告模板**：修改 `report_generator.py` 中的章节渲染方法，通过 `domain_config` 实现域自适应
- **自定义 Streamlit 界面**：修改 `app.py`，添加新的标签页或组件
- **添加测试**：在 `tests/` 目录下新建 `test_*.py`，参考现有测试中的 fixture 和 helper 模式

---

## 许可证
本项目采用 MIT 许可证，详情请参见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  <sub>Built with ☕️ by Robusr👨🏻‍💻</sub>
</p>
