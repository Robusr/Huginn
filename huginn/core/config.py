# -*- coding: utf-8 -*-
"""
@File    : config.py
@Author  : Robusr
@Date    : 2026/6/16
@Description: 集中化配置模块 — 所有硬编码常量统一管理，支持环境变量覆盖
@Software: PyCharm
"""

"""
集中化配置模块
所有硬编码常量在此统一定义，支持环境变量覆盖。
用法：
    from huginn.core.config import Config
    model = Config.LLM_MODEL
    threshold = Config.SIGNIFICANCE_THRESHOLD
"""
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv()


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


def clean_field_name(col: str) -> str:
    """清洗字段名，去掉问卷平台的技术前缀，提取可读的中文名称。

    示例：
        'col_1_你的性别是' → '你的性别是'
        'col_122._竞技运动如跑鞋传感器智能教练等' → '竞技运动如跑鞋传感器智能教练等'
        'col_17你将来有可能...' → '你将来有可能...'
        '提交答卷时间' → '提交答卷时间'
    """
    import re
    # 去掉 col_数字 前缀（后可选跟 _ 或 .）
    cleaned = re.sub(r'^col_\d+(?:[\._])?\s*', '', col)
    if not cleaned:
        return col
    # 去掉残留的前导下划线或点号
    cleaned = cleaned.lstrip('._')
    return cleaned if cleaned else col


class Config:
    # =========================================================================
    # LLM / API 配置
    # =========================================================================
    LLM_MODEL: str = _env("LLM_MODEL", "deepseek-v4-pro")
    LLM_BASE_URL: str = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MAX_RETRIES: int = _env_int("LLM_MAX_RETRIES", 3)
    LLM_RETRY_DELAY: int = _env_int("LLM_RETRY_DELAY", 3)
    LLM_TEMPERATURE: float = _env_float("LLM_TEMPERATURE", 0.05)
    LLM_TOP_P: float = _env_float("LLM_TOP_P", 0.95)
    LLM_MAX_TOKENS: int = _env_int("LLM_MAX_TOKENS", 8192)

    # =========================================================================
    # 统计分析配置
    # =========================================================================
    DEFAULT_ALPHA: float = _env_float("DEFAULT_ALPHA", 0.05)            # 默认显著性水平
    SIGNIFICANCE_THRESHOLD: float = _env_float("SIGNIFICANCE_THRESHOLD", 0.05)
    STATS_RESULT_FILENAME: str = "stats_results.json"
    DATA_PROFILE_FILENAME: str = "data_profile.json"

    # =========================================================================
    # 数据画像 — 类型推断阈值
    # =========================================================================
    UNIQUE_RATIO_THRESHOLD: float = 0.05    # 唯一值占比 < 5% 且唯一数 <= 50 → 分类
    MAX_CATEGORY_CARDINALITY: int = 50       # 分类变量最大基数
    ANALYSIS_MAX_GROUPS: int = _env_int("ANALYSIS_MAX_GROUPS", 20)
    TUKEY_MAX_GROUPS: int = _env_int("TUKEY_MAX_GROUPS", 12)
    MIN_NUMERIC_UNIQUE: int = 10             # 至少 10 个唯一值才视为连续

    # =========================================================================
    # 任务筛选器配置
    # =========================================================================
    TASK_MIN_COUNT: int = _env_int("TASK_MIN_COUNT", 5)    # 最少有效任务数
    TASK_MAX_COUNT: int = _env_int("TASK_MAX_COUNT", 18)    # 最多执行任务数

    # 统计方法优先级（值越大越优先）
    TASK_PRIORITY: dict = {
        "ANOVA": 3,
        "卡方检验": 2,
        "t检验": 2,
        "配对t检验": 1,
        "相关性分析": 1,
        "分布检验": 1,
    }

    # 默认统计覆盖要求（可通过环境变量和领域配置继续调整）
    TASK_MIN_REQUIREMENTS: dict = {
        "ANOVA": 2,
        "chi_square": 2,
        "t_test": 3,
    }

    # =========================================================================
    # 默认分析完整性验收标准
    # =========================================================================
    REQUIREMENTS: dict = {
        "point_estimation_min": 5,
        "interval_estimation_min": 5,
        "hypothesis_test_min": 5,
        "anova_min": 2,
        "chi_square_min": 2,
        "significant_p_threshold": 0.05,
    }

    # =========================================================================
    # 领域检测与业务模块开关
    # =========================================================================
    # LLM 调用轮次配置
    LLM_MAX_ROUNDS: int = _env_int("LLM_MAX_ROUNDS", 4)      # 默认4轮，可减为2轮
    LLM_EXPECTED_ROUNDS: int = 4                             # 验证时预期的完整轮次数

    # 业务分析模块开关（按 domain key 配置启用哪些模块）
    DOMAIN_MODULES: dict = {
        "retail_sales": [],
        "education_survey": [],
        "general_business": [],
    }

    # 单个模块开关（可通过环境变量禁用）
    BUSINESS_MODULES_ENABLED: dict = {}

    # =========================================================================
    # 输出文件命名
    # =========================================================================
    FIELD_REGISTRY_FILENAME: str = "field_registry.json"
    EVIDENCE_TABLE_FILENAME: str = "evidence_table.json"
    LLM_AUDIT_FILENAME: str = "llm_call_audit.json"
    GRANULARITY_FILENAME: str = "granularity.json"

    # =========================================================================
    # 报告验证 — 禁止词汇
    # =========================================================================
    CAUSAL_WORDS: list = [
        "导致", "造成", "使得", "影响", "决定", "引起", "促成",
        "因为", "所以", "因此", "故而", "由此可见", "综上所述",
        "侵蚀", "促进销量", "源自",
    ]

    VAGUE_WORDS: list = [
        "大概", "也许", "或许", "差不多", "基本上",
        "感觉", "想必", "看样子",
    ]

    # =========================================================================
    # 输出路径
    # =========================================================================
    OUTPUT_DIR: str = _env("OUTPUT_DIR", "./outputs")

    # =========================================================================
    # UI 标签映射（供 app.py / report_generator.py / report_validator.py 共用）
    # =========================================================================
    TYPE_LABELS: dict = {
        "numeric_continuous": "连续数值",
        "numeric_discrete": "离散数值",
        "categorical": "分类",
        "datetime": "日期时间",
        "text": "文本",
    }

    CHART_LABELS: dict = {
        "bar_chart": "柱状图：分类频数与分组均值对比",
        "box_plot": "箱线图：数值分布特征与离群值检测",
        "scatter_plot": "散点图：两变量关系形态与回归趋势",
        "correlation_heatmap": "相关性热力图：多变量相关结构概览",
    }

    MODULE_NAMES: dict = {
        "statistical_quantity": "统计数量硬指标 (30分)",
        "statistical_validity": "统计结果有效性 (20分)",
        "findings_compliance": "数据发现合规性 (20分)",
        "suggestions_quality": "行动建议合理性 (10分)",
        "business_analysis_completeness": "业务分析完整度 (10分)",
        "report_completeness": "报告完整性 (10分)",
    }

    MODULE_MAX_SCORES: dict = {
        "statistical_quantity": 30,
        "statistical_validity": 20,
        "findings_compliance": 20,
        "business_analysis_completeness": 10,
        "suggestions_quality": 10,
        "report_completeness": 10,
    }

    # =========================================================================
    # 应用默认值
    # =========================================================================
    DEFAULT_REQUIREMENT: str = "根据数据生成包含主要发现、图表分析和行动建议的正式报告"
    APP_VERSION: str = "v1.2"
    APP_PAGE_TITLE: str = "Huginn - 通用数据分析报告智能体"
