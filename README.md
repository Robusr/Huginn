# Huginn - AI驱动的探索型课程问卷数据分析智能体

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/DeepSeek-API-orange.svg" alt="DeepSeek API">
  <img src="https://img.shields.io/badge/Status-Stable-brightgreen.svg" alt="Status">
</p>

>  **全自动数据分析智能体**：上传Excel/CSV表格，自动完成数据清洗、统计推断、可视化、洞察提炼和报告生成。严格遵循"**模型只做决策和解释，所有统计量由Python真实计算**"的核心原则，彻底杜绝大模型幻觉。

##  核心功能

###  全自动探索型分析
无需指定分析问题，智能体自动理解数据结构，主动发现值得研究的业务问题，并用统计方法验证。

###  学术级统计分析
-  点估计（均值、方差、标准差、中位数等10个参数）
-  区间估计（均值、方差、标准差、中位数、预测区间）
-  6类假设检验（t检验、配对t检验、Wilcoxon、Mann-Whitney等）
-  单因素/双因素方差分析（ANOVA）+ Tukey事后检验
-  皮尔逊卡方检验（拟合优度+独立性检验）
-  正态性检验（Shapiro-Wilk + D'Agostino-Pearson）

###  多AI平台原生支持
-  **DeepSeek API**（默认，中文效果最佳，性价比最高）
-  适配Claude Code、Cursor、GitHub Copilot、Windsurf、Aider等主流AI助手
-  离线演示模式，无需API也能运行

###  自动合规性验证
内置课程作业专用验证器，自动检查是否满足所有验收标准：
- 统计数量硬指标（≥5点估计/≥5区间估计/≥5假设检验/≥2ANOVA/≥2卡方）
- 结果有效性（p值范围、样本量、无编造数据）
- 发现合规性（无因果错误、无模糊表述、引用正确）
- 建议合理性（有数据依据、可落地）

###  专业可视化
自动生成柱状图、箱线图、散点图、相关性热力图，已修复中文乱码问题。

##  快速开始

### 环境要求
- Python 3.9+
- （可选）DeepSeek API Key（从[DeepSeek开放平台](https://platform.deepseek.com/)获取）

### 1. 克隆仓库
```bash
git clone https://github.com/your-username/huginn.git
cd huginn
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置API密钥
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑.env文件，填入你的DeepSeek API Key
# DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. 运行智能体
```bash
# 在线模式（调用DeepSeek API）
python agent_runner.py "你的课程问卷.csv" "为下一次上课的老师生成课程建议报告"

# 离线模式（不调用API，用于演示）
python agent_runner.py "你的课程问卷.csv" "为下一次上课的老师生成课程建议报告" --offline
```

### 5. 查看结果
运行完成后，所有结果会保存在`outputs/YYYYMMDD_HHMMSS_文件名/`目录下：
```
outputs/20260610_143022_课程问卷/
├── data_profile.json      # 数据画像
├── stats_results.json     # 完整统计结果
├── valid_tasks.json       # 已执行的分析任务
├── findings.json          # 核心数据发现
├── suggestions.json       # 课程改进建议
├── charts/                # 可视化图表
│   ├── bar_chart.png
│   ├── box_plot.png
│   ├── scatter_plot.png
│   └── correlation_heatmap.png
├── validation_result.json # 合规性验证结果
└── validation_report.md   # 验证报告（Markdown）
```

##  使用方法

### 命令行参数
```bash
python agent_runner.py <数据文件路径> <分析需求> [选项]

选项：
  --offline    离线模式，不调用API，使用预生成结果演示
  --help       显示帮助信息
```

### 单独运行模块
```bash
# 仅加载清洗数据
python data_loader.py "你的文件.csv"

# 仅生成数据画像
python data_profiler.py "你的文件.csv"

# 仅执行统计分析
python analysis_engine.py "你的文件.csv"

# 仅生成图表
python chart_generator.py "你的文件.csv"

# 仅验证报告合规性
python report_validator.py "outputs/20260610_143022_课程问卷"
```

### 与AI助手集成
本项目原生支持所有主流AI编程助手，只需复制对应平台的配置文件即可：
- **Cursor**: 复制 `platforms/cursor/.cursorrules` 到项目根目录
- **GitHub Copilot**: 复制 `platforms/copilot/.github-copilot-instructions.md` 到 `.github/`
- **Claude Code**: 安装Skill：`cp skill/SKILL.md ~/.claude/skills/stat-analysis/`
- **Windsurf**: 复制 `platforms/windsurf/.windsurfrules` 到项目根目录

##  项目结构
```
huginn/
├── 📄 agent_runner.py          # 智能体主流程控制器（成员B）
├── 📄 llm_client.py            # DeepSeek API封装（成员B）
├── 📄 task_planner.py          # 任务筛选与校验器（成员B）
├── 📄 analysis_engine_patch.py # 统计引擎扩展（成员B）
├── 📄 report_validator.py      # 报告合规性验证器（成员B）
├── 📄 data_loader.py           # 数据加载与清洗（成员A）
├── 📄 data_profiler.py         # 数据画像生成（成员A）
├── 📄 analysis_engine.py       # 核心统计分析引擎（成员A）
├── 📄 chart_generator.py       # 可视化图表生成（成员A）
├── 📄 insight_generator.py     # 基础洞察提炼（成员A）
├── 📄 main.py                  # 一键全流程入口（兼容旧版）
├── 📄 .env.example             # 环境变量模板
├── 📄 .gitignore               # Git忽略文件
├── 📄 requirements.txt         # 依赖清单
├── 📄 README.md                # 本文件
├── 📂 platforms/               # 各AI平台适配文件
│   ├── cursor/
│   ├── copilot/
│   ├── windsurf/
│   ├── aider/
│   ├── continue_dev/
│   └── general/
├── 📂 skill/                   # Claude Code Skill定义
└── 📂 outputs/                 # 运行结果输出目录
```

##  核心模块说明

### 1. 数据加载与清洗 (`data_loader.py`)
- 自动识别CSV编码（utf-8/gbk/gb18030）和分隔符
- 自动清洗表头、处理空行和缺失值
- 自动推断数据类型（数值/日期/分类）
- 支持Excel（.xlsx/.xls）和CSV格式

### 2. 统计分析引擎 (`analysis_engine.py`)
- 基于scipy和statsmodels实现所有统计方法
- 内置数量自查机制，确保满足最低统计要求
- 所有结果可溯源，自动保存完整计算过程
- 支持按需执行指定任务和全量分析两种模式

### 3. LLM客户端 (`llm_client.py`)
- 封装DeepSeek API，支持结构化输出
- 自动处理速率限制和超时重试
- 内置离线模式，用于无网络环境演示
- 严格的提示词约束，杜绝幻觉和编造数据

### 4. 任务筛选器 (`task_planner.py`)
- 严格校验LLM提出的问题，过滤不可执行的任务
- 自动补充默认任务，确保满足统计数量要求
- 按优先级排序任务，优先执行高价值分析
- 详细记录每个问题被过滤的原因，便于调试

### 5. 报告验证器 (`report_validator.py`)
- 5大模块20+检查项，覆盖课程作业所有验收标准
- 100分制评分体系，60分及格
- 生成详细的改进建议，指导优化报告
- 输出JSON和Markdown两种格式的验证报告

##  课程作业验收标准
本项目严格按照以下标准设计，确保生成的报告100%符合要求：

| 检查项 | 最低要求 |
|--------|----------|
| 点估计 | ≥5个 |
| 区间估计 | ≥5个 |
| 假设检验 | ≥5类 |
| 方差分析(ANOVA) | ≥2项 |
| 卡方检验 | ≥2个 |
| 数据发现 | ≥5条 |
| 课程建议 | ≥3条 |
| 可视化图表 | ≥3张 |
| 局限性说明 | 必须包含 |
| 因果关系 | 禁止将相关性表述为因果关系 |

##  常见问题

### Q: 运行提示ModuleNotFoundError怎么办？
A: 确保已安装所有依赖：`pip install -r requirements.txt`

### Q: DeepSeek API调用失败怎么办？
A: 检查API Key是否正确，网络是否正常，或使用`--offline`参数运行离线模式。

### Q: 图表中文显示方块怎么办？
A: `chart_generator.py`已自动配置中文字体。如仍无效，将`C:\Windows\Fonts\simhei.ttf`复制到目标设备同路径。

### Q: 统计数量不达标怎么办？
A: 任务筛选器会自动补充默认任务。如果仍不达标，检查数据中是否有足够的数值列和分类列（至少3个数值列、2个多分类列、1个二分类列）。

### Q: 生成的发现和建议质量不高怎么办？
A: 优化用户需求描述，提供更明确的业务背景；或调整`llm_client.py`中的提示词。

## 🛠️ 开发指南

### 环境搭建
```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# 安装开发依赖
pip install -r requirements-dev.txt
```

### 代码规范
- 遵循PEP 8代码规范
- 使用类型注解
- 编写详细的文档字符串
- 提交前运行代码格式化：`black .`

### 扩展功能
- **添加新的统计方法**：修改`analysis_engine.py`，在`AnalysisEngine`类中添加对应的方法
- **适配其他LLM API**：修改`llm_client.py`，实现对应的API调用逻辑
- **添加新的图表类型**：修改`chart_generator.py`，添加对应的绘图方法

##  贡献
欢迎提交Issue和Pull Request！

1. Fork本仓库
2. 创建你的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开Pull Request

##  许可证
本项目采用MIT许可证，详情请参见[LICENSE](LICENSE)文件。

---

<p align="center">
  <sub>Built with ☕️️ by Robusr👨🏻‍💻 </sub>
</p>