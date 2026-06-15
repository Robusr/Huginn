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
    from config import Config
    model = Config.LLM_MODEL
    threshold = Config.SIGNIFICANCE_THRESHOLD
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.getenv(key, str(default)))


def _env_float(key: str, default: float) -> float:
    return float(os.getenv(key, str(default)))


class Config:
    # =========================================================================
    # LLM / API 配置
    # =========================================================================
    LLM_MODEL: str = _env("LLM_MODEL", "deepseek-chat")
    LLM_BASE_URL: str = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MAX_RETRIES: int = _env_int("LLM_MAX_RETRIES", 3)
    LLM_RETRY_DELAY: int = _env_int("LLM_RETRY_DELAY", 3)
    LLM_TEMPERATURE: float = _env_float("LLM_TEMPERATURE", 0.05)
    LLM_TOP_P: float = _env_float("LLM_TOP_P", 0.95)
    LLM_MAX_TOKENS: int = _env_int("LLM_MAX_TOKENS", 4096)

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
    MIN_NUMERIC_UNIQUE: int = 10             # 至少 10 个唯一值才视为连续

    # =========================================================================
    # 任务筛选器配置
    # =========================================================================
    TASK_MIN_COUNT: int = _env_int("TASK_MIN_COUNT", 5)    # 最少有效任务数
    TASK_MAX_COUNT: int = _env_int("TASK_MAX_COUNT", 10)    # 最多执行任务数

    # 统计方法优先级（值越大越优先）
    TASK_PRIORITY: dict = {
        "ANOVA": 3,
        "卡方检验": 2,
        "t检验": 2,
        "配对t检验": 1,
        "相关性分析": 1,
        "分布检验": 1,
    }

    # 课程作业最低统计要求
    TASK_MIN_REQUIREMENTS: dict = {
        "ANOVA": 2,
        "chi_square": 2,
        "t_test": 3,
    }

    # =========================================================================
    # 课程作业验收标准
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
    # 报告验证 — 禁止词汇
    # =========================================================================
    CAUSAL_WORDS: list = [
        "导致", "造成", "使得", "影响", "决定", "引起", "促成",
        "因为", "所以", "因此", "故而", "由此可见", "综上所述",
    ]

    VAGUE_WORDS: list = [
        "可能", "大概", "也许", "或许", "差不多", "基本上",
        "感觉", "认为", "觉得", "应该", "想必", "看样子",
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
        "statistical_quantity": "统计数量硬指标 (40分)",
        "statistical_validity": "统计结果有效性 (20分)",
        "findings_compliance": "数据发现合规性 (20分)",
        "suggestions_reasonableness": "课程建议合理性 (10分)",
        "report_completeness": "报告完整性 (10分)",
    }

    # =========================================================================
    # 应用默认值
    # =========================================================================
    DEFAULT_REQUIREMENT: str = "为下一次上课的老师生成课程建议报告"
    APP_VERSION: str = "v1.0"
    APP_PAGE_TITLE: str = "Huginn - 课程问卷分析智能体"
