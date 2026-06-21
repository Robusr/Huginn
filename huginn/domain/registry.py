# -*- coding: utf-8 -*-
"""
@File    : domain_registry.py
@Author  : Robusr
@Date    : 2026/6/20
@Description: 领域注册表 — 声明式领域定义 + 自动检测，驱动所有域感知行为
"""

"""
领域注册表模块
功能：定义数据领域（零售/教育/通用），通过字段名模式自动检测，
      为 LLM 提示词、报告模板、验证规则提供域感知能力。
每个领域是纯数据（dataclass），不可变，不包含逻辑。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
import re


# ============================================================================
# 字段角色（供 field_registry.py 引用，此处定义以打破循环导入）
# ============================================================================

class FieldRole:
    """字段业务角色常量。"""
    ID: str = "id"
    DATE: str = "date"
    REVENUE: str = "revenue"
    COST: str = "cost"
    PROFIT: str = "profit"
    QUANTITY: str = "quantity"
    DISCOUNT: str = "discount"
    CATEGORY_DIM: str = "category_dimension"
    SEGMENT_DIM: str = "segment_dimension"
    GEOGRAPHY: str = "geography"
    CUSTOMER_ID: str = "customer_id"
    PRODUCT_ID: str = "product_id"
    METRIC: str = "metric"
    TEXT: str = "text"
    ORDINAL: str = "ordinal"
    UNKNOWN: str = "unknown"


# ============================================================================
# 领域配置数据类
# ============================================================================

@dataclass(frozen=True)
class DomainConfig:
    """单个领域的完整配置。"""

    # 标识
    name: str                              # 领域名称，如 "零售销售"
    key: str                               # 唯一键，如 "retail_sales"

    # LLM 提示词 persona（第一句）
    persona: str                           # 如 "你是一位专业的零售业务数据分析专家"

    # 报告模板
    report_title: str                      # 报告标题模板，如 "{filename}数据分析报告"
    report_subtitle: str                   # 副标题/页眉

    # 建议词库（用于验证和建议生成）
    suggestion_taxonomy: List[str]         # 建议分类维度
    recommendation_prefix: str             # 建议前缀

    # 字段角色检测模式（按优先级排序）
    field_role_patterns: Dict[str, List[str]] = field(default_factory=dict)
    # role -> [regex patterns]

    # 领域专用模块（哪些分析模块应启用）
    active_modules: Set[str] = field(default_factory=set)

    # 提示词中的禁用/谨慎词语
    cautious_terms: List[str] = field(default_factory=list)
    # 该领域特有的需谨慎使用的术语


# ============================================================================
# 预定义领域
# ============================================================================

RETAIL_SALES = DomainConfig(
    name="零售销售",
    key="retail_sales",
    persona="你是一位专业的零售业务数据分析专家，擅长从销售数据中诊断经营问题并提出可落地的改进建议。",
    report_title="零售销售数据分析报告",
    report_subtitle="基于销售明细的经营诊断与改进建议",
    suggestion_taxonomy=[
        "产品组合优化",
        "定价与折扣策略",
        "区域与渠道管理",
        "客户分层经营",
        "供应链与运输优化",
    ],
    recommendation_prefix="建议",
    field_role_patterns={
        FieldRole.ID: [
            r"(?i)^.*(?:order_?)?id$",
            r"(?i)^.*row[_ ]?id$",
            r"(?i)^.*序号$",
        ],
        FieldRole.DATE: [
            r"(?i)^.*(?:order_?|ship_?)?date$",
            r"(?i)^.*(?:order_?|ship_?)?time$",
            r"(?i)^.*日期$",
            r"(?i)^.*时间$",
        ],
        FieldRole.REVENUE: [
            r"(?i)^sales$",
            r"(?i)^.*(?:revenue|销售额|收入|金额)$",
        ],
        FieldRole.PROFIT: [
            r"(?i)^profit$",
            r"(?i)^.*(?:利润|毛利|净利)$",
        ],
        FieldRole.QUANTITY: [
            r"(?i)^quantity$",
            r"(?i)^.*(?:数量|销量|件数)$",
        ],
        FieldRole.DISCOUNT: [
            r"(?i)^discount$",
            r"(?i)^.*(?:折扣|优惠|折让)$",
        ],
        FieldRole.CATEGORY_DIM: [
            r"(?i)^category$",
            r"(?i)^sub[_ ]?category$",
            r"(?i)^.*(?:品类|类别|分类|大类|中类)$",
        ],
        FieldRole.SEGMENT_DIM: [
            r"(?i)^segment$",
            r"(?i)^.*(?:客群|客户类型|细分)$",
        ],
        FieldRole.GEOGRAPHY: [
            r"(?i)^(?:country|nation|state|city|region|province|area)$",
            r"(?i)^.*(?:国家|省|市|区|区域|地区)$",
        ],
        FieldRole.CUSTOMER_ID: [
            r"(?i)^.*(?:customer|cust)[_ ]?(?:id|name|编号|名称)$",
            r"(?i)^.*客户.*(?:id|编号|名称)$",
        ],
        FieldRole.PRODUCT_ID: [
            r"(?i)^.*product[_ ]?(?:id|name)$",
            r"(?i)^.*(?:产品.*(?:id|编号|名称)|商品.*(?:id|编号|名称))$",
        ],
        FieldRole.TEXT: [
            r"(?i)^.*(?:name|姓名|备注|note|desc|说明)$",
        ],
    },
    active_modules={
        "loss_driver_analysis",
        "discount_response_analysis",
        "pareto_analysis",
        "cross_dimension_analysis",
    },
    cautious_terms=[
        # 零售中需谨慎使用的词语（容易误用的因果词）
    ],
)

EDUCATION_SURVEY = DomainConfig(
    name="教育问卷",
    key="education_survey",
    persona="你是一位专业的教育数据分析专家，擅长从课程问卷中发现教学改进方向。",
    report_title="课程问卷数据统计分析报告",
    report_subtitle="基于学生反馈的教学改进建议",
    suggestion_taxonomy=[
        "教学方法改进",
        "课程内容优化",
        "学习支持服务",
        "评估方式调整",
        "学生参与促进",
    ],
    recommendation_prefix="课程建议",
    field_role_patterns={
        FieldRole.ID: [
            r"(?i)^.*序号$",
            r"(?i)^.*id$",
        ],
        FieldRole.DATE: [
            r"(?i)^.*(?:提交答卷时间|所用时间|填写时间)$",
        ],
        FieldRole.METRIC: [
            # Likert 量表题
            r"(?i)^col_\d+.*$",
        ],
        FieldRole.CATEGORY_DIM: [
            r"(?i)^.*(?:性别|年级|专业|学院|班级|部门|院系)$",
            r"(?i)^.*department$",
            r"(?i)^.*(?:passed|通过|合格)$",
        ],
        FieldRole.TEXT: [
            r"(?i)^.*(?:姓名|name|来源详情)$",
        ],
    },
    active_modules=set(),  # 教育域不启用业务分析模块
    cautious_terms=[
        "学生",  # 教育域允许
        "教师",
        "课堂",
        "教学",
    ],
)

GENERAL_BUSINESS = DomainConfig(
    name="通用数据",
    key="general_business",
    persona="你是一位专业的数据分析专家，擅长从数据中发现模式并给出可操作的改进建议。",
    report_title="数据分析报告",
    report_subtitle="基于数据探索的分析与建议",
    suggestion_taxonomy=[
        "效率改进",
        "质量提升",
        "成本优化",
        "流程改善",
    ],
    recommendation_prefix="建议",
    field_role_patterns={
        FieldRole.ID: [
            r"(?i)^.*(?:id|编号|序号)$",
        ],
        FieldRole.DATE: [
            r"(?i)^.*(?:date|time|日期|时间)$",
        ],
        FieldRole.REVENUE: [
            r"(?i)^.*(?:sales|revenue|收入|销售额|金额|总价)$",
        ],
        FieldRole.PROFIT: [
            r"(?i)^.*(?:profit|利润)$",
        ],
        FieldRole.QUANTITY: [
            r"(?i)^.*(?:quantity|数量|件数|次数)$",
        ],
        FieldRole.DISCOUNT: [
            r"(?i)^.*(?:discount|折扣|优惠)$",
        ],
        FieldRole.CATEGORY_DIM: [
            r"(?i)^.*(?:category|type|group|分类|类型|类别)$",
        ],
        FieldRole.GEOGRAPHY: [
            r"(?i)^.*(?:country|state|city|region|地区|城市|省份)$",
        ],
    },
    active_modules=set(),  # 默认不启用，由字段检测决定
    cautious_terms=[],
)


# ============================================================================
# 领域注册表
# ============================================================================

ALL_DOMAINS: List[DomainConfig] = [RETAIL_SALES, EDUCATION_SURVEY, GENERAL_BUSINESS]
DOMAIN_MAP: Dict[str, DomainConfig] = {d.key: d for d in ALL_DOMAINS}


# ============================================================================
# 领域检测
# ============================================================================

def detect_domain(column_names: List[str]) -> DomainConfig:
    """根据列名自动检测数据所属领域。

    检测策略：对每个领域计分（匹配列数），返回得分最高的领域。
    约束：至少需匹配 3 个不同角色才算有效匹配。

    :param column_names: DataFrame 列名列表
    :return: 匹配的 DomainConfig
    """
    if not column_names:
        return GENERAL_BUSINESS

    scores: Dict[str, int] = {}
    roles_matched: Dict[str, set] = {}

    for col in column_names:
        col_lower = col.lower().strip()
        for domain in ALL_DOMAINS:
            if domain.key not in scores:
                scores[domain.key] = 0
                roles_matched[domain.key] = set()
            for role, patterns in domain.field_role_patterns.items():
                for pattern in patterns:
                    if re.match(pattern, col_lower):
                        scores[domain.key] += 1
                        roles_matched[domain.key].add(role)
                        break

    # 过滤：至少匹配 3 个不同角色（排除噪声匹配）
    candidates = []
    for domain in ALL_DOMAINS:
        if domain.key == "general_business":
            continue  # 作为兜底
        if len(roles_matched.get(domain.key, set())) >= 3:
            candidates.append((domain, scores[domain.key]))

    if candidates:
        # 返回得分最高的
        candidates.sort(key=lambda x: -x[1])
        best_domain, best_score = candidates[0]
        # 如果最高得分远超第二名，直接返回
        if best_score >= 5:
            return best_domain
        # 否则检查是否是零售数据（有 sales/discount/profit 三件套）
        retail_roles = roles_matched.get("retail_sales", set())
        if {FieldRole.REVENUE, FieldRole.PROFIT}.issubset(retail_roles):
            return RETAIL_SALES
        # 检查教育问卷特征
        edu_roles = roles_matched.get("education_survey", set())
        if len(edu_roles) >= 3:
            return EDUCATION_SURVEY

    # 兜底：按列名特征判断
    col_set = {c.lower().strip() for c in column_names}
    # 零售特征：同时有 sales/profit/discount
    if {"sales", "profit"}.issubset(col_set) or {"销售额", "利润"}.issubset(col_set):
        return RETAIL_SALES
    # 教育特征：有 col_N_xxx 格式的列
    col_pattern_count = sum(1 for c in column_names if re.match(r'^col_\d+', c.lower()))
    if col_pattern_count >= 5:
        return EDUCATION_SURVEY

    return GENERAL_BUSINESS


def get_domain_config(domain_key: Optional[str] = None,
                      column_names: Optional[List[str]] = None) -> DomainConfig:
    """获取领域配置。

    优先级：
    1. 显式 domain_key
    2. 通过列名自动检测
    3. 兜底 GENERAL_BUSINESS
    """
    if domain_key and domain_key in DOMAIN_MAP:
        return DOMAIN_MAP[domain_key]
    if column_names:
        return detect_domain(column_names)
    return GENERAL_BUSINESS
