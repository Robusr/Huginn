# -*- coding: utf-8 -*-
"""
@File    : granularity_detector.py
@Author  : Robusr
@Date    : 2026/6/20
@Description: 数据粒度检测器 — 自动识别每行代表什么实体（明细行/订单/客户/产品）
"""

"""
数据粒度检测器
功能：通过分析列特征和唯一值计数，自动推断数据集的行级实体类型。
输出包括：实体类型、各级唯一ID计数、时间跨度、可用的分母基数。
这对于正确解读比率至关重要（例如亏损明细率 vs 亏损订单率 vs 亏损客户率）。
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from field_registry import FieldRole


def detect_granularity(df: pd.DataFrame,
                       field_registry: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """检测数据集的行级粒度。

    核心逻辑：
    - 如果 Order_ID 唯一数 < 总行数 → 明细行（一个订单多行）
    - 如果 Customer_ID 唯一数 ≈ 总行数 → 客户级
    - 如果有 Order_ID 且唯一数 ≈ 总行数 → 订单级
    - 如果有 Product_ID 唯一数 ≈ 总行数 → 产品级

    :param df: 原始 DataFrame
    :param field_registry: 字段角色注册表（可选，用于查找 ID 列）
    :return: 粒度信息字典
    """
    total_rows = len(df)

    # 从 field_registry 获取 ID 列
    id_columns = []
    if field_registry:
        registry_fields = field_registry.get("fields", {})
        for col_name, info in registry_fields.items():
            if info.get("role") == FieldRole.ID:
                id_columns.append(col_name)
    else:
        # 回退：搜索常见 ID 列名
        for col in df.columns:
            col_lower = col.lower().strip()
            if any(pat in col_lower for pat in ["_id", "id", "编号", "序号"]):
                id_columns.append(col)

    # 提取关键 ID 计数
    def _get_unique(col_patterns: List[str]) -> Optional[int]:
        for col in df.columns:
            col_lower = col.lower().strip()
            for pat in col_patterns:
                if pat in col_lower:
                    return int(df[col].nunique(dropna=True))
        return None

    unique_order_id = _get_unique(["order_id", "orderid", "订单id", "订单编号"])
    unique_customer_id = _get_unique(["customer_id", "customerid", "客户id", "客户编号"])
    unique_product_id = _get_unique(["product_id", "productid", "产品id", "产品编号", "商品id"])

    # 检测实体类型
    row_entity_type = "detail_row"  # 默认：明细行
    entity_description = "每行代表一条明细记录"

    if unique_order_id is not None and unique_order_id < total_rows * 0.95:
        # 订单唯一数明显少于行数 → 明细行
        row_entity_type = "order_line_detail"
        entity_description = f"每行代表一条订单明细（{total_rows} 行 ≈ {unique_order_id} 个订单的明细）"
    elif unique_order_id is not None and unique_order_id >= total_rows * 0.95:
        row_entity_type = "order_level"
        entity_description = f"每行代表一个独立订单（{total_rows} 个订单）"
    elif unique_customer_id is not None and unique_customer_id >= total_rows * 0.8:
        row_entity_type = "customer_level"
        entity_description = f"每行代表一个独立客户（{total_rows} 个客户）"
    elif unique_product_id is not None and unique_product_id >= total_rows * 0.8:
        row_entity_type = "product_level"
        entity_description = f"每行代表一个独立产品（{total_rows} 个产品）"

    # 检测时间跨度
    time_span_days = None
    has_timestamps = False
    date_columns = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_columns.append(col)
            has_timestamps = True
            try:
                span = (df[col].max() - df[col].min()).days
                if time_span_days is None or span > time_span_days:
                    time_span_days = span
            except Exception:
                pass

    # 可用的分母基数
    denominator_options = {
        "total_rows": total_rows,
        "unique_orders": unique_order_id,
        "unique_customers": unique_customer_id,
        "unique_products": unique_product_id,
    }

    # 常用比率的分母建议
    rate_denominators = {
        "亏损明细率": {
            "description": "亏损明细行数 / 总明细行数",
            "denominator": total_rows,
        },
        "亏损订单率": {
            "description": "含亏损明细的订单数 / 总订单数",
            "denominator": unique_order_id,
            "available": unique_order_id is not None,
        },
        "亏损客户率": {
            "description": "含亏损明细的客户数 / 总客户数",
            "denominator": unique_customer_id,
            "available": unique_customer_id is not None,
        },
        "亏损产品率": {
            "description": "含亏损明细的产品数 / 总产品数",
            "denominator": unique_product_id,
            "available": unique_product_id is not None,
        },
    }

    return {
        "row_entity_type": row_entity_type,
        "entity_description": entity_description,
        "row_count": total_rows,
        "unique_order_ids": unique_order_id,
        "unique_customer_ids": unique_customer_id,
        "unique_product_ids": unique_product_id,
        "has_timestamps": has_timestamps,
        "date_columns": date_columns,
        "time_span_days": time_span_days,
        "denominator_options": {k: v for k, v in denominator_options.items() if v is not None},
        "rate_denominators": rate_denominators,
        "id_columns_found": id_columns,
        "important_note": (
            "⚠️ 所有比率分析必须明确分母。'亏损明细率'≠'亏损订单率'≠'亏损客户率'。"
            f"当前数据为 {row_entity_type}，比率计算应以此为基础，"
            f"并在报告中明确说明分母含义。"
        ),
    }
