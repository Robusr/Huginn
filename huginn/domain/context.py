# -*- coding: utf-8 -*-
"""数据领域识别与通用字段安全规则。"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable


DOMAIN_CONFIGS: Dict[str, Dict[str, Any]] = {
    "retail_sales": {
        "domain": "retail_sales",
        "domain_label": "零售经营",
        "report_title": "超市销售数据分析报告",
        "report_subtitle": "销售、利润与经营结构的证据化分析",
        "recommendation_section": "经营改进建议",
        "audience": "经营管理与业务分析人员",
        "metric_keywords": ["Profit", "Sales", "Discount", "Quantity", "利润", "销售", "折扣", "数量"],
        "group_keywords": ["Category", "Sub-Category", "Region", "Segment", "Ship Mode", "品类", "区域", "客群"],
    },
    "education_survey": {
        "domain": "education_survey",
        "domain_label": "教育问卷",
        "report_title": "课程问卷数据分析报告",
        "report_subtitle": "关键差异、特色信号与改进方向",
        "recommendation_section": "教学改进建议",
        "audience": "课程教师与教学管理人员",
        "metric_keywords": ["兴趣", "技术难度", "契合", "社会价值", "竞争", "机会", "创业"],
        "group_keywords": ["数学能力", "编程能力", "作业", "课堂", "性别", "专业"],
    },
    "general": {
        "domain": "general",
        "domain_label": "通用数据",
        "report_title": "数据分析报告",
        "report_subtitle": "主要发现、统计证据与行动建议",
        "recommendation_section": "行动建议",
        "audience": "数据使用与决策人员",
        "metric_keywords": [],
        "group_keywords": [],
    },
}


IDENTIFIER_PATTERNS = [
    r"(^|[ _-])id$",
    r"(^|[ _-])id([ _-]|$)",
    r"编号$",
    r"序号$",
    r"代码$",
    r"编码$",
    r"邮编",
    r"postal[\s_-]*code",
    r"row\s*id",
    r"order\s*id",
    r"customer\s*id",
    r"product\s*id",
]

NOISE_KEYWORDS = ["提交答卷时间", "所用时间", "来源详情", "生成时间"]


def detect_domain_context(data_profile: Dict[str, Any], user_requirement: str = "") -> Dict[str, Any]:
    """根据需求和字段名识别数据领域，并返回报告语义配置。"""
    columns = " ".join(str(field.get("column", "")) for field in data_profile.get("fields", []))
    text = f"{user_requirement} {columns}".lower()

    retail_terms = ["sales", "profit", "discount", "quantity", "category", "销售", "利润", "折扣", "超市", "零售"]
    education_terms = ["课程", "学生", "教师", "老师", "课堂", "作业", "问卷", "教学", "兴趣程度", "专业契合"]
    retail_score = sum(term.lower() in text for term in retail_terms)
    education_score = sum(term.lower() in text for term in education_terms)

    domain = "general"
    if retail_score >= 3 and retail_score > education_score:
        domain = "retail_sales"
    elif education_score >= 2:
        domain = "education_survey"

    context = dict(DOMAIN_CONFIGS[domain])
    context["user_requirement"] = user_requirement
    return context


def is_identifier_or_noise(column: str, field: Dict[str, Any] | None = None, n_rows: int = 0) -> bool:
    """识别 ID、邮编、流水号、时间戳等不应作为分析指标的字段。"""
    text = str(column).strip()
    lower = text.lower()
    if any(keyword.lower() in lower for keyword in NOISE_KEYWORDS):
        return True
    if any(re.search(pattern, lower, flags=re.IGNORECASE) for pattern in IDENTIFIER_PATTERNS):
        return True

    field = field or {}
    unique = int(field.get("unique") or 0)
    inferred_type = field.get("inferred_type", "")
    if n_rows and unique / n_rows >= 0.95 and inferred_type in {"categorical", "text", "numeric_continuous"}:
        return True
    return False


def domain_keywords(context: Dict[str, Any], key: str, fallback: Iterable[str] = ()) -> list[str]:
    values = context.get(key)
    return list(values) if isinstance(values, list) else list(fallback)
