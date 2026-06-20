# Huginn - AI-Powered Multi-Domain Exploratory Data Analysis Agent

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/DeepSeek-API-orange.svg" alt="DeepSeek API">
  <img src="https://img.shields.io/badge/Tests-38%20passed-success.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Domains-3%20types-informational.svg" alt="Domains">
  <img src="https://img.shields.io/badge/Status-Stable-brightgreen.svg" alt="Status">
</p>

> **Fully automated data analysis agent**: upload an Excel/CSV file and automatically complete domain detection, intelligent data cleaning, field role inference, statistical inference, visualization, 4-round LLM insight extraction, domain-adaptive report generation, and compliance verification. Covers three domains: retail sales, education survey, and general business. Retail scenarios auto-activate four business analysis modules: loss driver analysis, discount response analysis, Pareto concentration analysis, and cross-dimension analysis. Strictly follows the core principle of "model makes decisions and interpretations only; all statistics are computed by Python." Built-in structured evidence table eliminates LLM hallucinations. Statistical auto-fill ensures compliance even for datasets lacking multi-category variables. Compliance verification can reach up to **100/100**.

---

## Core Features

### Multi-Domain Auto-Detection
- **Three predefined domains**: Retail Sales / Education Survey / General Business
- **Auto domain detection**: automatically identifies data domain based on column name patterns, driving domain-aware behavior for LLM prompts, report templates, and business analysis modules
- **Manual override**: `--domain retail_sales` to explicitly specify the domain
- **Field role registry**: automatically infers the business role of each column (ID / Revenue / Profit / Discount / Dimension / Geography, etc.), outputting `field_registry.json`

### Fully Automated Exploratory Analysis (11-Step Pipeline)
No need to specify analysis questions. The agent automatically understands data structure, detects domain type, infers field roles, discovers business problems worth investigating, validates them with statistical methods, and generates a complete domain-adaptive analysis report with one click.

### Retail Business Analysis Modules (Auto-Activated for Retail Domain)
- **Loss Driver Analysis**: groups by 8 dimensions (category, sub-category, region, segment, ship mode, discount bins, etc.) to calculate loss rate, loss amount, and loss contribution
- **Discount Response Analysis**: discount binning, profit inflection point identification (21-30% range), intra-category stratification, anomaly detection
- **Concentration Analysis (Pareto)**: product/customer/sub-category Top-N analysis, cumulative contribution rate curves, high-sales-low-profit identification
- **Cross-Dimension Analysis**: auto-generates valid dimension combinations (Region x Category, Segment x Category, etc.), cross-tabulation, interaction effect detection

### 4-Round LLM Deep Reasoning (Evidence-Driven)
- **Round 1 -- Task Planning**: generates 8-12 candidate analysis tasks based on data profile and domain context
- **Round 2 -- Problem Discovery**: discovers business problems worth investigating based on statistical results and evidence table
- **Round 3 -- Findings and Suggestions**: generates evidence-based data findings (5-element structure: conclusion + magnitude + baseline + attribution clues + business impact) and improvement suggestions
- **Round 4 -- Report Writing**: writes and polishes the formal analysis report, citing statistical paths from the evidence table
- **Structured Evidence Table**: all business modules write to a central evidence table; LLM can only reference, not fabricate, eliminating hallucinations

### Academic-Grade Statistical Analysis
- Point estimation (mean, variance, standard deviation, median, etc. -- 10 parameters)
- Interval estimation (mean, variance, standard deviation, median, prediction intervals)
- 6 types of hypothesis tests (t-test, paired t-test, Wilcoxon, Mann-Whitney, etc.)
- One-way/Two-way ANOVA + Tukey post-hoc tests **(auto-fill ensures ≥2 ANOVA even without multi-category columns)**
- Pearson chi-square tests (goodness-of-fit + independence)
- Normality tests (Shapiro-Wilk + D'Agostino-Pearson)
- Correlation analysis
- **Intelligent auto-fill**: automatically supplements ANOVA, chi-square, and distribution tests to meet verification thresholds when task planning falls short

### Automatic Report Generation
- **Domain-adaptive reports**: Retail 8 chapters / Education 7 chapters / General 7 chapters; chapter titles adjust automatically by domain
- **Executive summary**: displays significant result statistics, verification score, and LLM audit info at the report header
- **Appendix**: automatically integrates compliance verification score, detailed module results, and LLM call audit
- **Word export**: one-click export to `.docx` format
- **PDF export**: one-click export to `.pdf` format
- All statistics are traceable to raw JSON results, eliminating fabrication

### Automatic Compliance Verification
Built-in multi-domain validator that runs automatically after analysis and is written to the report appendix:
- **Statistical Quantity (30 pts)**: >=5 point estimates / >=5 interval estimates / >=5 hypothesis tests / >=2 ANOVA / >=2 chi-square
- **Statistical Validity (20 pts)**: p-value range (supports scientific notation: `3.7e-118`), sample size, no fabricated data
- **Findings Compliance (20 pts)**: no causal errors, no vague expressions, correct citations
- **Business Analysis Coverage (10 pts)**: whether business analysis modules are fully covered
- **Suggestion Quality (10 pts)**: data-backed, actionable
- **Report Completeness (10 pts)**: complete chapters, comprehensive appendix
- 100-point scale, 60 points to pass

### Interactive Web Interface
- **Streamlit app**: `streamlit run app.py` to launch
- Supports file upload, requirement input, offline mode toggle
- Tabbed display: Overview / Charts / Statistics / Findings / Suggestions / Verification / Full Report
- One-click download of Markdown report, Word report, statistics JSON, and ZIP package

### Engineering Infrastructure
- **Centralized configuration**: `config.py` manages 60+ configuration items covering LLM parameters, statistical thresholds, domain module switches, UI labels, scoring weights, etc., with environment variable support
- **Unified logging**: `logger.py` with idempotent initialization, eliminating silent log loss during module imports
- **Unit tests**: 38 tests covering full analysis chain, domain detection, and field role inference; run with `pytest tests/ -v`

### Multi AI Platform Native Support
- **DeepSeek API** (default, best Chinese results, highest cost-effectiveness)
- Compatible with Claude Code, Cursor, GitHub Copilot, Windsurf, Aider, and other mainstream AI assistants
- Offline demo mode, operational without API

### Professional Visualization
Automatically generates bar charts, box plots, scatter plots, and correlation heatmaps with Chinese font support.

---

## Quick Start

### Requirements
- Python 3.9+
- (Optional) DeepSeek API Key (obtain from [DeepSeek Platform](https://platform.deepseek.com/))

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/huginn.git
cd huginn
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure API Key
```bash
# Copy environment variable template
cp .env.example .env

# Edit .env and fill in your DeepSeek API Key
# DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. Run the Agent
```bash
# Online mode (calls DeepSeek API, recommended)
# Education survey
python -m huginn.cli.runner "your_course_survey.csv" "Generate course improvement suggestions for the next instructor"

# Retail sales
python -m huginn.cli.runner "sales_data.csv" "Analyze business problems and propose improvements"

# Manually specify domain
python -m huginn.cli.runner "data.csv" "Analyze data" --domain retail_sales

# Offline mode (no API calls, for demo and testing)
python -m huginn.cli.runner "your_course_survey.csv" "Generate course suggestion report" --offline
```

### 5. Launch Web Interface (Optional)
```bash
streamlit run app.py
```

### 6. View Results
After completion, all results are saved under `outputs/YYYYMMDD_HHMMSS_filename/`:
```
outputs/20260620_143022_course_survey/
├── data_profile.json              # Data profile
├── field_registry.json            # Field role registry
├── domain_context.json            # Domain context
├── stats_results.json             # Full statistical results
├── valid_tasks.json               # Executed analysis tasks
├── evidence_table.json            # Structured evidence table (retail domain)
├── granularity.json               # Data granularity detection (retail domain)
├── loss_driver_results.json       # Loss driver analysis (retail domain)
├── discount_analysis_results.json # Discount response analysis (retail domain)
├── pareto_results.json            # Concentration analysis (retail domain)
├── cross_dimension_results.json   # Cross-dimension analysis (retail domain)
├── findings.json                  # Core data findings (LLM-generated)
├── suggestions.json               # Improvement suggestions (LLM-generated)
├── report_narrative.json          # 4th-round polished report narrative
├── llm_call_audit.json            # LLM call audit
├── charts/                        # Visualizations
│   ├── bar_chart.png
│   ├── box_plot.png
│   ├── scatter_plot.png
│   └── correlation_heatmap.png
├── final_report.md                # Complete analysis report (domain-adaptive chapters)
├── final_report.docx              # Word format report (optional export)
├── final_report.pdf               # PDF format report (optional export)
├── validation_result.json         # Compliance verification result (JSON)
└── validation_report.md           # Compliance verification report (Markdown)
```

### 7. Run Tests (Optional)
```bash
# Verify all modules are working correctly
pytest tests/ -v

# Expected output: 38 passed in ~1.3s
```

---

## Three Data Domains

### Retail Sales (`retail_sales`)
Suitable for sales transaction data containing fields such as sales, profit, discount, category, and region.
- **Auto-detection features**: simultaneously has sales/profit/discount-related fields, or matches >=3 retail field roles
- **Activated modules**: loss driver analysis, discount response analysis, concentration analysis, cross-dimension analysis
- **Report title**: `Retail Sales Data Analysis Report -- Business Diagnosis and Improvement Suggestions Based on Sales Transactions`
- **Suggestion dimensions**: product mix optimization, pricing and discount strategy, regional and channel management, customer segmentation, supply chain and shipping optimization

### Education Survey (`education_survey`)
Suitable for survey data with Likert scales, course evaluations, student feedback, and similar fields.
- **Auto-detection features**: >=5 `col_N_xxx` format columns (survey platform export characteristic)
- **Activated modules**: none (primarily relies on LLM deep reasoning)
- **Report title**: `Course Survey Statistical Analysis Report -- Teaching Improvement Suggestions Based on Student Feedback`
- **Suggestion dimensions**: teaching method improvement, course content optimization, learning support services, assessment adjustment, student engagement promotion

### General Business (`general_business`)
Fallback domain for structured data that does not match retail or education characteristics.
- **Auto-detection conditions**: used as fallback when retail/education conditions are not met
- **Report title**: `Data Analysis Report -- Analysis and Suggestions Based on Data Exploration`
- **Suggestion dimensions**: efficiency improvement, quality enhancement, cost optimization, process improvement

---

## Usage

### Command Line Arguments
```bash
python -m huginn.cli.runner <data_file_path> <analysis_requirement> [options]

Options:
  --offline    Offline mode, no API calls, use rule-based generation for findings and suggestions
  --domain     Manually specify domain (retail_sales / education_survey / general_business)
  --help       Show help message
```

### One-Click Full Pipeline (No LLM, Pure Statistics)
```bash
python main.py "your_file.csv"
```

### AI Assistant Integration
This project natively supports all mainstream AI programming assistants. Simply copy the corresponding platform configuration file:
- **Claude Code**: Install skill: `cp skill/SKILL.md ~/.claude/skills/stat-analysis/`
- **Cursor**: Copy `platforms/cursor/.cursorrules` to project root
- **GitHub Copilot**: Copy `platforms/copilot/.github-copilot-instructions.md` to `.github/`
- **Windsurf**: Copy `platforms/windsurf/.windsurfrules` to project root
- **Aider**: `aider --conventions platforms/aider/CONVENTIONS.md`
- **Continue.dev**: Merge `platforms/continue_dev/config.json` into `~/.continue/config.json`
- **ChatGPT / DeepSeek / Kimi**: Open `platforms/general/COPY_PASTE_PROMPT.txt`, copy all content and paste into the dialog

---

## Project Structure
```
Huginn/
├── app.py                       # Streamlit launch entry (thin wrapper)
├── main.py                      # Legacy CLI entry (deprecated, delegates to new entry)
├── pyproject.toml               # Python package configuration
│
├── huginn/                      # Core Python package
│   ├── __init__.py              # Version info
│   ├── core/                    # Infrastructure
│   │   ├── config.py            # Centralized configuration (60+ items)
│   │   ├── logger.py            # Unified logging
│   │   └── label_utils.py       # Chinese label utilities
│   ├── data/                    # Data layer
│   │   ├── loader.py            # CSV/Excel loading
│   │   └── profiler.py          # Data profiling
│   ├── domain/                  # Domain detection
│   │   ├── registry.py          # Domain registry
│   │   ├── context.py           # Domain context
│   │   └── fields.py            # Field role inference
│   ├── planning/                # Task planning
│   │   ├── task_planner.py      # Task filter
│   │   ├── analysis_planning.py # Analysis planning
│   │   └── feature_miner.py     # Distinctive signal mining
│   ├── analysis/                # Statistical analysis
│   │   ├── engine.py            # Statistical inference engine
│   │   └── charts.py            # Chart generation
│   ├── llm/                     # LLM client
│   │   └── client.py            # DeepSeek API (4-round orchestration)
│   ├── reporting/               # Report generation
│   │   ├── generator.py         # Report generator (MD + Word + PDF)
│   │   └── validator.py         # Compliance validator
│   ├── web/                     # Web interface
│   │   └── app.py               # Streamlit application
│   └── cli/                     # CLI entry
│       └── runner.py            # Main pipeline controller (11-step pipeline)
│
├── .env.example                 # Environment variable template
├── .gitignore                   # Git ignore rules
├── requirements.txt             # Dependency list
├── README.md                    # This file
│
├── tests/                       # Unit tests (38 tests)
│   ├── test_analysis_chain.py   # Full pipeline integration tests (~30 tests)
│   └── test_domain_registry.py  # Domain detection and field role tests (~8 tests)
│
├── platforms/                   # AI platform adapter files
│   ├── cursor/
│   ├── copilot/
│   ├── windsurf/
│   ├── aider/
│   ├── continue_dev/
│   └── general/
│
├── skill/                       # Claude Code skill definition
└── outputs/                     # Run result output directory
```

---

## Core Module Descriptions

### 1. Data Loading and Cleaning (`data/loader.py`)
- Auto-detects CSV encoding (utf-8 / gbk / gb18030) and delimiter
- Auto-cleans headers, handles empty rows and missing values
- **Intelligent numeric extraction**: automatically converts Likert scale strings (e.g., `"5 (Very Interested)"`, `"B.1-2 hours"`, `"10 hours"`) to numeric values, greatly increasing usable numeric columns
- Auto-infers data types (numeric / date / categorical), compatible with pandas 2 and pandas 3
- Supports Excel (.xlsx / .xls) and CSV formats

### 2. Statistical Analysis Engine (`analysis/engine.py`)
- **Dual mode**: `run_all()` full analysis + `run_tasks(tasks)` on-demand execution, unified entry
- All statistical methods implemented based on scipy and statsmodels
- **Auto-completion**: point/interval estimation covers all numeric columns, automatically fills in distribution tests, chi-square goodness-of-fit tests, and **ANOVA** (with smart fallback: uses `numeric_discrete` columns as grouping factors, or quartile-bins continuous variables when the dataset lacks multi-category categorical columns)
- Built-in count self-check mechanism to ensure minimum statistical requirements are met
- All results traceable, complete calculation process automatically saved

### 3. Domain Registry (`domain/registry.py`)
- Defines complete configurations for three domains (retail sales / education survey / general business)
- Each domain includes: LLM persona, report template, suggestion taxonomy, field role detection patterns, active module set
- **Auto-detection**: `detect_domain()` scores via column name regex matching; at least 3 distinct roles must be matched to be valid
- **Field role constants**: ID, Date, Revenue, Cost, Profit, Quantity, Discount, Category Dimension, Geography, Customer ID, Product ID, etc. -- 15 role types
- Drives domain-adaptive behavior for LLM prompts, report titles/chapters, and validation rules

### 4. Field Role Registry (`domain/fields.py`)
- `infer_field_role()` assigns a business role to each column based on column name patterns and domain config
- `build_field_registry()` generates a complete registry, marking ID fields, meaningless fields, revenue/profit/discount fields
- Outputs `field_registry.json` for reference by business analysis modules and LLM rounds

### 5. LLM Client (`llm/client.py`)
- Wraps DeepSeek API using `json_object` mode + Pydantic manual parsing
- **4-round LLM orchestration**: task planning -> problem discovery -> findings and suggestions -> report writing
- Each round receives different context (data profile / statistical results / evidence table / field registry / granularity info)
- Auto-handles rate limits and timeout retries (retry count, delay, etc. centrally managed by `config.py`)
- Built-in offline mode: **dynamically generates findings and suggestions based on statistical results**, no hardcoded demo data
- Strict prompt constraints with built-in significant result pre-scanning and p>=0.05 handling rules
- All parameters (model, temperature, max tokens, etc.) read via `Config` class with environment variable override support
- Outputs `llm_call_audit.json` recording each round's call status

### 6. Task Planner (`planning/task_planner.py`)
- Strictly validates LLM-proposed questions, filters out non-executable tasks
- Auto-supplements default tasks to ensure statistical count requirements; **auto-excludes sequence numbers, constant columns, and other fields unsuitable for analysis**
- Sorts by priority (ANOVA > chi-square > t-test > others)
- **Relaxed ANOVA validation**: accepts `numeric_discrete` columns (e.g., RAD 1-8) with ≥3 unique values as valid grouping factors, not just pure categorical columns
- Built-in max iteration limit to prevent infinite loops when data types are insufficient
- Detailed logging of why each question was filtered, for debugging

### 7. Retail Business Analysis Modules

#### 7a. Data Granularity Detection
- Auto-identifies row-level entity type via ID column unique value ratio
- Supports: order line detail / order-level / customer-level / product-level
- Outputs unique order count, unique customer count, unique product count, row count, etc.

#### 7b. Loss Driver Analysis
- Groups by 8 dimensions (category, sub-category, region, segment, ship mode, discount bins, etc.)
- Calculates loss rate, loss amount, and loss contribution percentage for each group
- Identifies primary loss sources and writes to evidence table

#### 7c. Discount Response Analysis
- Discount binning (e.g., 0-10%, 10-20%, ..., 80%+)
- Profit inflection point identification (discount range where profit rate turns from positive to negative)
- Intra-category stratification analysis, anomalous profit point detection

#### 7d. Concentration Analysis (Pareto)
- Product/customer/sub-category Top-N analysis
- Cumulative contribution rate curves (top 20% products contribute X% of sales)
- High-sales-low-profit product identification

#### 7e. Cross-Dimension Analysis
- Auto-generates valid dimension combinations (Region x Category, Segment x Category, etc.)
- Cross-tabulation calculation
- Interaction effect detection

### 8. Report Generator (`reporting/generator.py`)
- Reads all intermediate JSON results, auto-assembles domain-adaptive complete report (retail 8 chapters / education 7 chapters / general 7 chapters)
- **Domain-adaptive chapters**: retail reports include a dedicated "Business Analysis" chapter; education reports include a "Teaching Improvement Suggestions" chapter
- **Executive summary**: displays significant result statistics, verification score, LLM audit, etc. at the report header
- **Intelligent field name cleaning**: auto-removes survey platform technical prefixes (e.g., `col_122._`), preserving readable Chinese names
- Only displays statistically significant results with p < 0.05
- Auto-inserts chart references, integrates compliance verification appendix
- Supports Markdown (native), Word (python-docx), and PDF (reportlab) export formats
- Can run standalone or integrated within the agent runner pipeline

### 9. Report Validator (`reporting/validator.py`)
- 6 modules, 20+ check items covering multi-domain acceptance criteria
- **Scoring weights**: statistical quantity (30 pts) + statistical validity (20 pts) + findings compliance (20 pts) + business coverage (10 pts) + suggestion quality (10 pts) + report completeness (10 pts)
- 100-point scoring system, 60 points to pass
- **Intelligent evidence checking**: accepts both hypothesis test (t/F/chi-squared + p-value) and descriptive statistics (mean/std/CV) evidence formats
- **Scientific notation p-value parsing**: correctly interprets `p=3.7e-118` (as 3.7×10⁻¹¹⁸) rather than misreading it as p=3.7; also handles `p≈` and whitespace variants
- **Intelligent vague word detection**: excludes words naturally contained in survey field names
- **Business analysis coverage check**: verifies complete coverage of 4 retail business modules
- Auto-checks limitations chapter in `final_report.md`
- Outputs both JSON and Markdown formats

### 10. Web Interface (`web/app.py`)
- Streamlit-based interactive analysis interface
- Supports file upload, requirement input, offline mode toggle
- **Execution statistics panel**: overview page shows key metrics such as task count, finding count, verification score
- **Accordion-style report preview**: full report folded by chapter to avoid loading overly long content at once
- Tabbed display of all analysis results (Overview / Charts / Statistics / Findings / Suggestions / Verification / Full Report)
- **Auto field name cleaning**: all field names in the UI are displayed in readable format
- One-click download of Markdown report, Word report, statistics JSON, ZIP package

### 11. Centralized Configuration (`core/config.py`)
- All hardcoded constants centrally managed with environment variable override support
- Covers LLM parameters, task thresholds, significance levels, domain module switches, scoring weights, prohibited vocabulary, UI labels, etc. -- 60+ items
- **Shared utility functions**: `clean_field_name()` imported by all project modules for unified survey platform technical prefix cleaning
- **Domain module switches**: `DOMAIN_MODULES` configured per domain, `BUSINESS_MODULES_ENABLED` individually controlled via environment variables
- Modify `config.py` for global effect without finding and modifying individual files
- Key environment variables: `LLM_MODEL`, `LLM_MAX_RETRIES`, `LLM_TEMPERATURE`, `TASK_MIN_COUNT`, `ENABLE_LOSS_DRIVER`, etc.

### 12. Unified Logging (`core/logger.py`)
- Idempotent `get_logger(name)` function ensures `basicConfig` executes only once
- All modules share unified log format: `time [level] module_name: message`
- Solves the problem of silent log loss when modules are imported
- Outputs to stderr, not interfering with user-facing `print()` output

### 13. Data Profiler (`data/profiler.py`)
- Auto-calculates type, missing rate, frequency distribution, numeric statistics, etc. for each field
- **Numeric discrete fields** (e.g., Likert scale 1-5 ratings) also get full numeric statistics (mean, std, skewness, kurtosis, etc.)
- Outputs standardized `data_profile.json` for use by all subsequent modules

### 14. Chart Generator (`analysis/charts.py`)
- Auto-generates bar charts, box plots, scatter plots, and correlation heatmaps
- **Chart titles and labels auto-cleaned**: field names stripped of technical prefixes for readability
- Chinese font auto-detection and configuration

### 15. One-Click Entry (`main.py`)
- Pure statistical pipeline without LLM dependency: load -> profile -> analyze -> chart -> insights
- For use in CI/CD or environments without API access
- Outputs standardized JSON results compatible with the full pipeline

---

## Analysis Pipeline Detail

```
+-----------------------------------------------------------------------------+
|  Step 1:  Data loading and cleaning           (data/loader.py)              |
|  Step 2:  Data profile generation             (data/profiler.py)            |
|  Step 2a: Domain detection                    (domain/registry.py)          |
|  Step 2b: Field role registry                 (domain/fields.py)            |
|  Step 3:  LLM Round 1 -- Candidate tasks      (llm/client.py)               |
|  Step 4:  Task filtering and validation       (planning/task_planner.py)    |
|  Step 5:  Statistical analysis execution      (analysis/engine.py)          |
|  Step 5b: Business analysis modules (retail)  (loss/discount/pareto/cross)  |
|  Step 6:  Distinctive signal mining           (planning/feature_miner.py)   |
|  Step 7:  LLM Round 2 -- Problem discovery    (llm/client.py)               |
|  Step 8:  Visualization charts                (analysis/charts.py)          |
|  Step 9:  LLM Round 3 -- Findings/suggestions (llm/client.py)               |
|  Step 10: LLM Round 4 -- Report writing       (llm/client.py)               |
|  Step 11: Report generation + validation      (reporting/*)                 |
+-----------------------------------------------------------------------------+
```

**Core Design Principles**:
- Data profile -> Domain detection -> Field role inference -> Task planning -> Statistical analysis -> Business modules -> Evidence table -> LLM reasoning -> Report generation
- LLM only makes decisions and interpretations; all statistics are computed by Python
- The evidence table is the central fact store for hallucination prevention; LLM can only reference, not fabricate
- Domain configuration drives domain-adaptive behavior throughout the entire pipeline (prompts, report templates, validation rules)

---

## Compliance Acceptance Criteria

This project is designed strictly according to acceptance criteria to ensure generated reports meet requirements:

| Check Item | Minimum Requirement | Config Key |
|------------|-------------------|-------------|
| Point estimation | >=5 | `REQUIREMENTS["point_estimation_min"]` |
| Interval estimation | >=5 | `REQUIREMENTS["interval_estimation_min"]` |
| Hypothesis tests | >=5 types | `REQUIREMENTS["hypothesis_test_min"]` |
| ANOVA | >=2 items | `REQUIREMENTS["anova_min"]` |
| Chi-square tests | >=2 items | `REQUIREMENTS["chi_square_min"]` |
| Data findings | >=5 items | -- |
| Improvement suggestions | >=3 items | -- |
| Visualization charts | >=3 | -- |
| Limitations statement | Required | -- |
| Causality | Prohibited from stating correlation as causation | `CAUSAL_WORDS` (prohibited word list) |
| Business analysis coverage (retail) | 4 modules complete | `BUSINESS_MODULES_ENABLED` |

---

## FAQ

### Q: ModuleNotFoundError on run?
A: Ensure all dependencies are installed: `pip install -r requirements.txt`

### Q: DeepSeek API call fails?
A: Check that your API Key is correct and network is working, or use `--offline` flag to run in offline mode.

### Q: How to choose the correct data domain?
A: Auto-detection is the default; you can also manually specify:
```bash
python -m huginn.cli.runner "data.csv" "analysis requirement" --domain retail_sales     # Retail
python -m huginn.cli.runner "data.csv" "analysis requirement" --domain education_survey # Education
python -m huginn.cli.runner "data.csv" "analysis requirement" --domain general_business # General
```

### Q: How to toggle retail business analysis modules?
A: Control individual modules via environment variables:
```bash
export ENABLE_LOSS_DRIVER=false       # Disable loss driver analysis
export ENABLE_DISCOUNT_ANALYZER=false # Disable discount response analysis
export ENABLE_PARETO=false            # Disable concentration analysis
export ENABLE_CROSS_DIM=false         # Disable cross-dimension analysis
```

### Q: Can LLM call rounds be adjusted?
A: Adjustable via environment variable (default 4 rounds):
```bash
export LLM_MAX_ROUNDS=2   # Reduce to 2 rounds (task planning + report writing)
```

### Q: Chinese characters show as boxes in charts?
A: `chart_generator.py` auto-searches and configures system Chinese fonts (macOS PingFang / Windows SimHei / Linux Noto CJK). If still ineffective, manually install Chinese fonts and retry.

### Q: Statistical counts don't meet requirements?
A: The analysis engine auto-executes point and interval estimation on all numeric columns, and auto-fills distribution tests, chi-square goodness-of-fit, and **ANOVA** (with smart fallback: uses `numeric_discrete` columns with ≥3 unique values as ANOVA grouping factors, or quartile-bins continuous variables when the dataset lacks multi-category categorical columns — e.g., Boston Housing with only binary CHAS). If still insufficient, check whether your data has enough numeric and categorical columns. Note: data with string-format Likert scales (e.g., `"5 (Very Interested)"`) is now intelligently recognized and converted to numeric.

### Q: Generated findings and suggestions are low quality?
A: Optimize your requirement description with clearer business context; or adjust prompts in `llm/client.py`. Offline mode now dynamically generates findings and suggestions based on statistical results without relying on hardcoded demo data.

### Q: How to export a Word report?
A:
```bash
# Reports are auto-generated as part of the pipeline; they appear in the output directory.
# To re-export from an existing run directory, use the report generator programmatically:
python -c "
from huginn.reporting.generator import ReportGenerator
gen = ReportGenerator('outputs/<run_dir>', 'analysis requirement')
gen.export_word('final_report.docx')
"
```

### Q: How to launch the Web interface?
A:
```bash
streamlit run app.py
```
Then open `http://localhost:8501` in your browser, upload a file, and start analysis.

### Q: How to customize LLM parameters (model, temperature, etc.)?
A: No code modification needed; override defaults via environment variables:
```bash
# Use a different model
export LLM_MODEL=deepseek-reasoner

# Adjust retry count and delay
export LLM_MAX_RETRIES=5
export LLM_RETRY_DELAY=5

# Adjust output temperature (0-1, lower is more stable)
export LLM_TEMPERATURE=0.1

# Then run normally
python -m huginn.cli.runner "data.csv" "analysis requirement"
```
See `config.py` for more configurable items; all support `KEY=VALUE` environment variable override.

### Q: How to switch to another LLM provider (e.g., OpenAI)?
A: The project uses an OpenAI-compatible SDK; switching only requires changing environment variables:
```bash
export DEEPSEEK_BASE_URL=https://api.openai.com/v1   # OpenAI or other compatible endpoint
export LLM_MODEL=gpt-4o                               # Model name
export DEEPSEEK_API_KEY=sk-your-openai-key            # API Key
```
Any service compatible with the OpenAI API format (e.g., Groq, Together, vLLM, etc.) can be used directly.

### Q: How to contribute?
A: Issues and Pull Requests are welcome! Before contributing:
1. Read the [Development Guide](#development-guide) below
2. Ensure `pytest tests/ -v` all pass (expected 38 passed)
3. Follow PEP 8 coding standards with type annotations
4. Add corresponding test cases for new features

### Q: How to run tests?
A: Test dependencies are included in `requirements.txt` (`pytest>=7.0`):
```bash
pytest tests/ -v              # All tests (expected 38 passed)
pytest tests/ -v --tb=short   # Compact output mode
```
See [Development Guide -> Running Tests](#running-tests) below.

---

## Development Guide

### Project Architecture

```
+----------------------------------------------------------------------+
|                          Entry Layer                                   |
|  cli/runner.py (11-step pipeline)   main.py (5-step no-LLM pipeline)  |
|  web/app.py (Streamlit Web)                                           |
+------+----------+----------+----------+--------------+----------------+
       |          |          |          |              |
+------+----+ +---+------+ +-+-------+ ++----------+ +--------------+
| Data Layer | | Domain  | | Intelligence | | Report    | | Infrastructure |
| loader     | | domain  | | llm          | | generator | | config.py      |
| profiler   | | field   | | planner      | | validator | | logger.py      |
| engine     | | evidence| |              | |           | | tests/         |
| charts     | | granular| |              | |           | |                |
| (pure Py)  | | (domain-| | (LLM)        | | (template+| | (config+log)   |
|            | | aware)  | |              | | validate) | |                |
+------------+ +--------+ +--------------+ +-----------+ +----------------+

Business Analysis Modules (auto-activated for retail domain):
  loss_driver / discount_analyzer / pareto_analyzer / cross_dimension
```

- **Data Layer**: data loading -> profiling -> statistical computation -> chart generation (pure Python, no LLM dependency)
- **Domain Layer**: domain detection -> field role inference -> granularity detection -> evidence table writes (domain-aware, drives full pipeline adaptation)
- **Intelligence Layer**: 4-round LLM orchestration -- candidate tasks -> problem discovery -> findings & suggestions -> report writing (evidence-driven, hallucination prevention)
- **Report Layer**: reads intermediate JSON -> assembles domain-adaptive report -> compliance verification -> exports Markdown/Word/PDF
- **Infrastructure Layer**: configuration management, logging system, unit tests

### Environment Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# macOS/Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Coding Standards
- Follow PEP 8
- Use type annotations
- Write detailed docstrings
- Run code formatting before committing: `black .`
- Run tests before committing: `pytest tests/ -v`

### Running Tests
```bash
# All tests
pytest tests/ -v

# Specific modules
pytest tests/test_analysis_chain.py -v
pytest tests/test_domain_registry.py -v
```
Test coverage:
- `test_analysis_chain.py` -- full pipeline integration tests: domain context, task planning, data loading, statistical inference, report generation, compliance verification
- `test_domain_registry.py` -- domain detection + field role inference + registry construction

### Configuration Management
All hardcoded values are centrally managed by the `Config` class in `config.py`. Modify defaults or override via environment variables:
```bash
# View all configurable items
grep "env(" huginn/core/config.py

# Override via environment variables (examples)
export LLM_MODEL=deepseek-chat               # LLM model name
export LLM_MAX_RETRIES=3                     # Max API retries
export LLM_MAX_ROUNDS=4                      # Max LLM call rounds
export TASK_MIN_COUNT=5                      # Minimum analysis tasks
export TASK_MAX_COUNT=18                     # Maximum analysis tasks
export OUTPUT_DIR=./outputs                  # Result output directory
export SIGNIFICANCE_THRESHOLD=0.05           # Significance threshold
export ENABLE_LOSS_DRIVER=true               # Enable loss driver analysis
export ENABLE_DISCOUNT_ANALYZER=true         # Enable discount response analysis
export ENABLE_PARETO=true                    # Enable concentration analysis
export ENABLE_CROSS_DIM=true                 # Enable cross-dimension analysis
```

### Extending the Project
- **Add a new data domain**: define a new `DomainConfig` in `domain/registry.py`, add to `ALL_DOMAINS` list
- **Add a new business analysis module**: create module file -> register in `Config.DOMAIN_MODULES` -> orchestrate call in `cli/runner.py` step 5b
- **Modify default parameters**: edit `Config` class attributes in `config.py`
- **Add new statistical methods**: modify `analysis/engine.py`, add corresponding methods in `AnalysisEngine` class, register in `_METHOD_DISPATCH` dict
- **Adapt other LLM APIs**: modify `llm/client.py`, implement corresponding API call logic
- **Add new chart types**: modify `analysis/charts.py`, add corresponding plotting methods
- **Extend report templates**: modify chapter rendering methods in `reporting/generator.py`, implement domain-adaptation via `domain_config`
- **Customize Streamlit interface**: modify `web/app.py`, add new tabs or components
- **Add tests**: create new `test_*.py` in `tests/`, reference fixture and helper patterns in existing tests

---

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built by Robusr</sub>
</p>
