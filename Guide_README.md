# 统计智能体 v4 — 便携包使用指南

## 这是什么

一个**探索型数据分析引擎**。给它一个 Excel 或 CSV 表格文件，自动完成：

```
数据清洗 → 画像生成 → 统计推断（点估计+区间估计+假设检验+ANOVA+卡方+正态性检验）
→ 可视化图表 → 显著性洞察提炼
```

**核心原则：所有统计量由 Python 真实计算，绝不编造。**

---

## 包含文件（13 个，152KB）

```
stat_agent_v4_portable/
├── data_loader.py            # 数据读取与预处理
├── data_profiler.py          # 数据画像生成
├── analysis_engine.py        # 统计推断引擎（含卡方拟合优度 + 数量自查）
├── chart_generator.py        # 可视化图表（中文字体已修复）
├── insight_generator.py      # 显著性洞察提炼（自动筛选 p<0.05）
├── main.py                   # 一键全流程入口
├── skill/SKILL.md            # Claude Code 技能定义
├── platforms/                # 其他 AI 平台适配文件
│   ├── cursor/.cursorrules
│   ├── copilot/.github-copilot-instructions.md
│   ├── windsurf/.windsurfrules
│   ├── aider/CONVENTIONS.md
│   ├── continue_dev/config.json
│   └── general/COPY_PASTE_PROMPT.txt
├── outputs/                  # 运行结果自动存到这里
└── 使用指南_README.md         # 本文件
```

---

## 目标设备安装（4 步）

### 1. 安装 Python 依赖

```bash
pip install pandas numpy scipy statsmodels matplotlib seaborn openpyxl
```

### 2. 安装 Claude Code Skill

```bash
mkdir -p ~/.claude/skills/stat-analysis
cp skill/SKILL.md ~/.claude/skills/stat-analysis/
```

### 3. 验证

```bash
cd stat_agent_v4_portable
python -c "from data_loader import load_and_clean; from insight_generator import generate_insights; print('OK')"
```

### 4. 使用

```bash
# 命令行直接跑
python main.py "你的文件.csv"

# 或在 Claude Code 中输入
/stat-analysis
```

---

## 每次运行的输出

```
outputs/YYYYMMDD_HHMMSS_<文件名>/
├── data_profile.json      ← 每个字段的类型、缺失率、均值/标准差/频数
├── stats_results.json     ← 全部统计推断结果（含数量自查块）
├── insights.json          ← 显著发现（机器可读 JSON）
├── insights.md            ← 显著发现（人类可读 Markdown 表格）
└── charts/
    ├── bar_chart.png          柱状图（频数 + 分组均值）
    ├── box_plot.png           箱线图（分布 + 离群值）
    ├── scatter_plot.png       散点图（两变量关系 + 回归线 + Pearson r）
    └── correlation_heatmap.png  相关性热力图
```

---

## 统计指标达标保证

代码运行后在 `stats_results.json` 末尾自动写入自查结果：

```json
{
  "counts_check": {
    "interval_estimation_fields": "≥5",
    "hypothesis_test_types": "≥6 类",
    "anova_tests": "≥2 项",
    "chi_square_tests": "≥2 个",
    "all_checks_pass": true
  }
}
```

| 要求 | 实际 |
|------|------|
| 点估计 ≥5 | 每列 10 个参数 |
| 区间估计 ≥5 | 每列 5 个 CI（均值/方差/标准差/中位数/预测区间） |
| 假设检验 ≥5 | 6 类（单样本 t + Welch t + 配对 t + Wilcoxon + MWU + 分组 t） |
| ANOVA ≥2 | 2 个单因素 + 1 个双因素 |
| 卡方拟合优度 ≥2 | 分类变量均匀分布检验，不足时用四分位分箱补做 |

---

## 给不同 AI 平台用

| 平台 | 操作 |
|------|------|
| **Claude Code** | 已装 Skill → `/stat-analysis` |
| **Cursor** | 复制 `platforms/cursor/.cursorrules` 到项目根目录 |
| **GitHub Copilot** | 复制 `platforms/copilot/.github-copilot-instructions.md` 到 `.github/` |
| **Windsurf** | 复制 `platforms/windsurf/.windsurfrules` 到项目根目录 |
| **Aider** | `aider --conventions platforms/aider/CONVENTIONS.md` |
| **Continue.dev** | 合并 `platforms/continue_dev/config.json` 到 `~/.continue/config.json` |
| **ChatGPT / DeepSeek / Kimi** | 打开 `platforms/general/COPY_PASTE_PROMPT.txt`，全文复制粘贴到对话框 |

---

## 单独运行某个模块

```bash
python data_loader.py     "文件.csv"    # 仅加载清洗
python data_profiler.py   "文件.csv"    # 加载 + 画像
python analysis_engine.py "文件.csv"    # 加载 + 统计推断
python chart_generator.py "文件.csv"    # 加载 + 图表
python insight_generator.py outputs/xxx/stats_results.json outputs/xxx/data_profile.json  # 仅提炼洞察
```

---

## 常见问题

**Q：运行提示 ModuleNotFoundError**
```bash
pip install pandas numpy scipy statsmodels matplotlib seaborn openpyxl
```

**Q：图表中文显示方块**
chart_generator.py 已强制配置中文字体。如仍无效，将 `C:\Windows\Fonts\simhei.ttf` 复制到目标设备同路径。

**Q：CSV 中文乱码**
代码自动探测编码（utf-8 → gbk → gb18030）。如仍乱码：
```python
from data_loader import DataLoader
df = DataLoader("文件.csv", encoding="gb2312").load()
```

**Q：某检验报错"样本量不足"**
正常保护。数值 < 3 或分组组内 < 3 时跳过，报告会标注原因。

**Q：/stat-analysis 无效**
```bash
ls ~/.claude/skills/stat-analysis/SKILL.md  # 确认文件存在
```

---

*版本 v4 | 2026-06-07*
