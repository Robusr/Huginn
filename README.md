<div align="center">

# Huginn - AI-Powered Multi-Domain Exploratory Data Analysis Agent

</div>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/DeepSeek-API-orange.svg" alt="DeepSeek API">
  <img src="https://img.shields.io/badge/Tests-38%20passed-success.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Education%20Score-100%2F100-brightgreen.svg" alt="Education Score">
  <img src="https://img.shields.io/badge/General%20Score-96%2F100-brightgreen.svg" alt="General Score">
</p>

> **Fully automated data analysis agent**: upload an Excel/CSV file and automatically receive a complete statistical analysis report with **7+ tables**, **4+ charts**, and **100/100 compliance score**. Automatically handles Chinese ordinal text encoding (Likert scales), domain detection, field role inference, statistical inference, 4-round LLM insight extraction, and compliance verification. **All statistics computed by Python — LLM only interprets, never fabricates.**

---

## Core Features

### 1. Multi-Domain Auto-Detection
Automatically identifies your data domain and adapts the entire pipeline:
- **Education Survey** (`education_survey`) — course evaluations, Likert scales, student feedback
- **Retail Sales** (`retail_sales`) — transactions, profit/loss, discounts, categories
- **General Business** (`general_business`) — fallback for any structured data

### 2. Chinese Ordinal Text Auto-Encoding [NEW]
Survey platforms export Chinese Likert responses as raw text ("非常困难", "比较容易", "一般" etc.). Huginn automatically:
- Detects Chinese ordinal response columns (evaluative words + ≤15 unique values)
- Encodes them to numeric values (1–5) using a 5-layer fallback pipeline
- Handles letter-prefixed values (A./B./C.), time ranges ("3-6小时"), and raw numbers
- Covers 5 semantic domains: difficulty, importance/satisfaction, time investment, frequency, and mastery

### 3. 11-Step Fully Automated Pipeline
```
Step 1  → Data loading & cleaning (CSV/Excel, auto-encoding detection)
Step 2  → Data profiling & domain detection
Step 3  → LLM Round 1 — Task planning (8-12 candidate analysis tasks)
Step 4  → Task filtering & validation
Step 5  → Statistical analysis execution (scipy + statsmodels)
Step 6  → Distinctive feature mining
Step 7  → LLM Round 2 — Problem discovery
Step 8  → Chart generation (bar, box, scatter, heatmap)
Step 9  → LLM Round 3 — Evidence-based findings & suggestions
Step 10 → LLM Round 4 — Report writing & language polishing
Step 11 → Report generation + compliance verification
```

### 4. Academic-Grade Statistical Analysis
- **Point estimation** (≥5 parameters): mean, variance, std, median, skewness, kurtosis
- **Interval estimation** (≥5 parameters): t-distribution CI, proportion CI, variance CI, mean-difference CI, bootstrap CI
- **Hypothesis tests** (≥5 types): one-sample t, independent t, paired t, Wilcoxon, Mann-Whitney, chi-square independence
- **ANOVA** (≥2): one-way + two-way with effect size η²
- **Pearson chi-square tests** (≥2): goodness-of-fit + independence
- **Normality tests**: Shapiro-Wilk + D'Agostino-Pearson
- **Auto-fill**: automatically supplements missing test types to meet minimum requirements

### 5. Anti-Hallucination Architecture
- **Structured Evidence Table**: all statistics written to a central evidence store; LLM can only reference, never fabricate
- **3 Hard Gates**: code execution success → stdout validity check → chart count validation — failure at any gate produces an honest error report, never fake data
- **Causal Language Sanitizer**: automatically replaces causal words ("影响"→"存在关联", "导致"→"伴随") in LLM output
- **p-value Validation**: rejects non-significant results (p≥0.05) presented as "significant"

### 6. Compliance Verification (100-Point Scale)
| Module | Points | Checks |
|--------|--------|--------|
| Statistical Quantity | 30 | ≥5 point est. / ≥5 interval est. / ≥5 hypothesis / ≥2 ANOVA / ≥2 chi-square |
| Statistical Validity | 20 | p-value range, significance filtering, sample size, module completeness |
| Findings Compliance | 20 | Evidence integrity, no causal errors, no vague language |
| Business Coverage | 10 | Domain-specific module coverage |
| Suggestion Quality | 10 | Data-backed, actionable |
| Report Completeness | 10 | All chapters present, appendix comprehensive |

### 7. Multi-Format Report Export
- **Markdown** (.md) — native, with embedded chart references
- **Word** (.docx) — python-docx, A4 with TOC
- **PDF** (.pdf) — reportlab
- **JSON artifacts**: stats_results.json, findings.json, suggestions.json, evidence_table.json

---

## Quick Start

### Prerequisites
- Python 3.9+
- DeepSeek API Key ([get one here](https://platform.deepseek.com/))

### 1. Clone & Install
```bash
git clone https://github.com/Robusr/huginn.git
cd huginn
pip install -r requirements.txt
```

### 2. Configure API Key
```bash
cp .env.example .env
# Edit .env and fill in your DeepSeek API Key:
# DEEPSEEK_API_KEY=sk-your-key-here
```

Or set environment variables directly:
```bash
export DEEPSEEK_API_KEY=sk-your-key-here
export DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
export LLM_MODEL=deepseek-v4-pro
```

### 3. Run Analysis
```bash
# Education survey (most common use case)
python -m huginn.cli.runner "course_survey.xlsx" "请进行全面统计分析，给出教学改进建议" --domain education_survey

# General business data
python -m huginn.cli.runner "survey.csv" "请进行全面统计分析" --domain general_business

# Retail sales data (activates 4 business modules)
python -m huginn.cli.runner "sales.csv" "分析业务问题并提出改进建议" --domain retail_sales

# Offline mode (no API key required — uses rule-based generation)
python -m huginn.cli.runner "data.csv" "分析需求" --offline
```

### 4. Web Interface (Optional)
```bash
streamlit run app.py
# Open http://localhost:8501
```

### 5. View Results
```
outputs/20260622_143022_course_survey/
├── data_profile.json            # Column types, stats, missing values
├── field_registry.json          # Business role per column
├── domain_context.json          # Detected domain + config
├── stats_results.json           # All statistical computation results
├── valid_tasks.json             # Executed analysis tasks
├── distinctive_features.json    # Mined data signals
├── findings.json                # Evidence-based findings(LLM)
├── suggestions.json             # Actionable suggestions(LLM)
├── discovered_problems.json     # Problems flagged by LLM
├── report_narrative.json        # Polished report narrative
├── llm_call_audit.json          # 4-round LLM call audit trail
├── charts/                      # Visualization images
│   ├── bar_chart.png
│   ├── box_plot.png
│   ├── scatter_plot.png
│   └── correlation_heatmap.png
├── final_report.md              # Markdown report
├── final_report.docx            # Word report
├── final_report.pdf             # PDF report
├── validation_result.json       # 100-point compliance check
└── validation_report.md         # Human-readable validation
```

## Recent Fixes (v1.2)

| Fix | File | Description |
|-----|------|-------------|
| Chinese ordinal encoding | `core/label_utils.py` | Added `encode_chinese_ordinal()` — auto-converts 66+ Chinese Likert text columns to numeric, boosting education score from 89→100 |
| Windows Unicode output | `cli/runner.py` | Fixed GBK codec crash on `✓`/`✗` characters by forcing UTF-8 stdout |
| Offline findings bug | `llm/client.py` | Fixed `_load_offline_findings_suggestions()` argument mismatch |
| Causal language sanitizer | `llm/client.py` + `cli/runner.py` | Added "影响"→"存在关联", "导致"→"伴随" replacement in findings & suggestions |
| Data loader integration | `data/loader.py` | Hooked `encode_chinese_ordinal` into `_infer_and_convert_types()` pipeline |
| Hypothesis test auto-fill | `analysis/engine.py` | Added `_auto_fill_hypothesis_tests()` for datasets without categorical grouping columns (cafeteria 96→100) |

---

## Project Structure
```
huginn/
├── app.py                       # Streamlit launch entry
├── main.py                      # Legacy no-LLM pipeline (5-step)
├── pyproject.toml               # Package config
├── requirements.txt             # Dependencies
│
├── huginn/                      # Core package
│   ├── cli/runner.py            # 11-step main pipeline controller
│   ├── core/
│   │   ├── config.py            # 60+ centralized config items
│   │   ├── logger.py            # Unified logging
│   │   └── label_utils.py       # Chinese labels + ordinal encoding
│   ├── data/
│   │   ├── loader.py            # CSV/Excel loading + type inference
│   │   └── profiler.py          # Data profiling
│   ├── domain/
│   │   ├── registry.py          # Domain detection (3 domains)
│   │   ├── context.py           # Domain context builder
│   │   └── fields.py            # Field role inference (15 role types)
│   ├── planning/
│   │   ├── task_planner.py      # Task validation & filtering
│   │   ├── analysis_planning.py # Candidate task pool
│   │   └── feature_miner.py     # Distinctive signal mining
│   ├── analysis/
│   │   ├── engine.py            # Statistical inference engine
│   │   └── charts.py            # Chart generation (4 types)
│   ├── llm/
│   │   └── client.py            # DeepSeek API (4-round orchestration)
│   ├── reporting/
│   │   ├── generator.py         # Report generator (MD+Word+PDF)
│   │   └── validator.py         # 100-point compliance validator
│   └── web/
│       └── app.py               # Streamlit web interface
│
├── tests/                       # 38 unit tests
├── platforms/                   # AI assistant adapter files
├── skill/                       # Claude Code skill definition
└── outputs/                     # Analysis results (auto-created)
```

---

## Configuration

All parameters are centrally managed in `huginn/core/config.py` and can be overridden via environment variables:

```bash
# LLM
export LLM_MODEL=deepseek-v4-pro        # Model name
export LLM_MAX_RETRIES=3                # API retry count
export LLM_TEMPERATURE=0.1              # 0-1, lower = more stable

# Statistical thresholds
export TASK_MIN_COUNT=5                 # Minimum analysis tasks
export SIGNIFICANCE_THRESHOLD=0.05      # p-value threshold

# Retail business modules
export ENABLE_LOSS_DRIVER=true          # Loss driver analysis
export ENABLE_DISCOUNT_ANALYZER=true    # Discount response analysis
export ENABLE_PARETO=true               # Pareto concentration analysis
export ENABLE_CROSS_DIM=true            # Cross-dimension analysis

# Output
export OUTPUT_DIR=./outputs             # Results directory
```

---

## FAQ

**Q: Chinese characters show as boxes in charts?**
A: The chart generator auto-detects system Chinese fonts (SimHei on Windows, PingFang on macOS). If issues persist, install a Chinese font.

**Q: Statistical counts don't meet requirements?**
A: The engine auto-fills missing test types. The Chinese ordinal encoder now converts Likert text columns to numeric. If counts are still low, check if your data has enough numeric/categorical columns.

**Q: How to switch to OpenAI or another provider?**
```bash
export DEEPSEEK_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=gpt-4o
export DEEPSEEK_API_KEY=sk-your-openai-key
```

**Q: How to run tests?**
```bash
pytest tests/ -v          # All 38 tests
pytest tests/ -v -q       # Compact output
```

---

## License
MIT License. See [LICENSE](LICENSE).

<p align="center">
  <sub>Built by Robusr👨🏻‍💻 with ☕️ & 🍵</sub>
</p>
