# -*- coding: utf-8 -*-
"""
@File    : field_registry.py
@Author  : Robusr
@Date    : 2026/6/20
@Description: 字段角色注册表 — 推断每个字段的业务角色并输出 field_registry.json
"""

"""
字段角色注册表模块
功能：基于列名和推断类型，为每个字段分配业务角色（Revenue/Profit/Discount/Category等），
      输出 field_registry.json 供所有下游模块引用。
      角色分类用于：分析模块选择、LLM 提示词构建、验证规则。

与 data_profiler 的区别：
- data_profiler 关注数据类型（numeric/categorical/text）
- field_registry 关注业务含义（这是收入、这是成本、这是维度）
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from domain_registry import DomainConfig, FieldRole, GENERAL_BUSINESS


# ============================================================================
# 默认角色推断（不依赖领域）
# ============================================================================

# 通用 ID 字段模式（不应该作为连续指标）
_ID_PATTERNS = [
    r"(?i)^(?:.*_)?id$",
    r"(?i)^(?:order|customer|product|user|row|transaction)[_ ]?id$",
    r"(?i)^(?:订单|客户|产品|用户|行|交易).*(?:id|编号)$",
    r"(?i)^.*(?:序号|流水号|编码|邮编|zip|postal)$",
]

# 通用数值业务指标模式
_METRIC_PATTERNS = {
    FieldRole.REVENUE: [
        r"(?i)^sales$",
        r"(?i)^.*(?:revenue|销售额|收入|金额|总价|价格)$",
    ],
    FieldRole.PROFIT: [
        r"(?i)^profit$",
        r"(?i)^.*(?:利润|毛利|净利|收益)$",
    ],
    FieldRole.QUANTITY: [
        r"(?i)^quantity$",
        r"(?i)^.*(?:数量|销量|件数|qty|count)$",
    ],
    FieldRole.DISCOUNT: [
        r"(?i)^discount$",
        r"(?i)^.*(?:折扣|优惠|折让|折扣率)$",
    ],
}

# 无业务意义的字段（不参与分析）
_MEANINGLESS_PATTERNS = [
    r"(?i)^.*(?:邮编|zip|postal).*$",
    r"(?i)^.*(?:流水号|序列号).*$",
]


def infer_field_role(column_name: str, inferred_type: str,
                     domain_config: DomainConfig = GENERAL_BUSINESS) -> str:
    """推断单个字段的业务角色。

    :param column_name: 列名
    :param inferred_type: data_profiler 推断的类型 (numeric_continuous/numeric_discrete/categorical/datetime/text)
    :param domain_config: 当前领域配置
    :return: FieldRole 常量字符串
    """
    col_lower = column_name.lower().strip()

    # 1. 检查无意义字段
    for pattern in _MEANINGLESS_PATTERNS:
        if re.match(pattern, col_lower):
            return FieldRole.UNKNOWN

    # 2. 使用领域专用模式
    if domain_config.key != "general_business":
        for role, patterns in domain_config.field_role_patterns.items():
            for pattern in patterns:
                if re.match(pattern, col_lower):
                    return role

    # 3. ID 字段检测（在所有领域中通用）
    for pattern in _ID_PATTERNS:
        if re.match(pattern, col_lower):
            return FieldRole.ID

    # 4. 通用数值指标
    for role, patterns in _METRIC_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, col_lower):
                return role

    # 5. 日期字段
    if inferred_type == "datetime":
        return FieldRole.DATE

    # 6. 按数据类型兜底
    if inferred_type in ("numeric_continuous", "numeric_discrete"):
        return FieldRole.METRIC
    if inferred_type == "categorical":
        return FieldRole.CATEGORY_DIM
    if inferred_type == "text":
        return FieldRole.TEXT

    return FieldRole.UNKNOWN


def build_field_registry(data_profile: Dict[str, Any],
                         domain_config: Optional[DomainConfig] = None) -> Dict[str, Any]:
    """根据数据画像构建字段角色注册表。

    :param data_profile: data_profiler.generate() 的输出
    :param domain_config: 可选，领域配置
    :return: 包含字段角色映射的注册表
    """
    if domain_config is None:
        domain_config = GENERAL_BUSINESS

    fields = data_profile.get("fields", [])
    registry: Dict[str, Dict[str, Any]] = {}

    # 统计各角色字段
    role_counts: Dict[str, int] = {}

    for field_info in fields:
        col = field_info.get("column", "")
        inferred_type = field_info.get("inferred_type", "unknown")
        role = infer_field_role(col, inferred_type, domain_config)

        registry[col] = {
            "column": col,
            "inferred_type": inferred_type,
            "role": role,
            "unique_count": field_info.get("unique", 0),
            "missing_pct": field_info.get("missing_pct", 0),
            # 标记是否为无意义字段
            "is_meaningless": role == FieldRole.UNKNOWN,
            # 标记是否应作为连续业务指标
            "is_business_metric": role in (
                FieldRole.REVENUE, FieldRole.PROFIT, FieldRole.QUANTITY,
                FieldRole.DISCOUNT, FieldRole.METRIC,
            ),
            # 标记是否应作为维度
            "is_dimension": role in (
                FieldRole.CATEGORY_DIM, FieldRole.SEGMENT_DIM,
                FieldRole.GEOGRAPHY, FieldRole.DATE,
            ),
            # 标记是否为 ID 类字段
            "is_id_field": role == FieldRole.ID,
        }

        role_counts[role] = role_counts.get(role, 0) + 1

    # 构建摘要
    id_fields = [c for c, r in registry.items() if r["role"] == FieldRole.ID]
    revenue_fields = [c for c, r in registry.items() if r["role"] == FieldRole.REVENUE]
    profit_fields = [c for c, r in registry.items() if r["role"] == FieldRole.PROFIT]
    discount_fields = [c for c, r in registry.items() if r["role"] == FieldRole.DISCOUNT]
    dimension_fields = [c for c, r in registry.items() if r["is_dimension"]]
    metric_fields = [c for c, r in registry.items() if r["is_business_metric"]]
    meaningless_fields = [c for c, r in registry.items() if r["is_meaningless"]]

    return {
        "domain_key": domain_config.key,
        "domain_name": domain_config.name,
        "fields": registry,
        "summary": {
            "total_fields": len(registry),
            "role_counts": role_counts,
            "id_fields": id_fields,
            "revenue_fields": revenue_fields,
            "profit_fields": profit_fields,
            "discount_fields": discount_fields,
            "dimension_fields": dimension_fields,
            "metric_fields": metric_fields,
            "meaningless_fields": meaningless_fields,
            "has_profit_data": len(profit_fields) > 0,
            "has_discount_data": len(discount_fields) > 0,
            "has_revenue_data": len(revenue_fields) > 0,
            "has_dimensions": len(dimension_fields) > 0,
        },
        "field_lists": {
            "ids": id_fields,
            "revenue": revenue_fields,
            "profit": profit_fields,
            "discount": discount_fields,
            "dimensions": dimension_fields,
            "metrics": metric_fields,
            "meaningless": meaningless_fields,
        },
    }


def save_field_registry(registry: Dict[str, Any], output_dir: Union[str, Path]) -> Path:
    """保存字段注册表到 JSON 文件。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "field_registry.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    return path
