# -*- coding: utf-8 -*-
"""
@File    : cross_dimension.py
@Author  : Robusr
@Date    : 2026/6/20
@Description: 交叉维度分析模块 — 代码生成合法维度组合，计算交互统计，供 LLM 排名解读
"""

"""
交叉维度分析器
设计原则：代码生成有效组合，模型只排序和解释。

支持的分析类型：
1. Region × Category（区域×品类）
2. Category × DiscountBin（品类×折扣区间）
3. Segment × Category（客群×品类）
4. ShipMode × ProfitMargin（运输方式×利润率）
5. Region × Segment（区域×客群）

对每个有效组合：
- 计算销售额、利润、利润率的双向分组表
- 检测交互效应（哪些组合偏离了整体均值）
- 准备好结构化数据供 LLM 轮次3 排名解读
"""

import json
from itertools import product as cartesian_product
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from field_registry import FieldRole


class CrossDimensionAnalyzer:
    """交叉维度分析器。"""

    def __init__(self, df: pd.DataFrame, field_registry: Optional[Dict[str, Any]] = None):
        self.df = df.copy()
        self.field_registry = field_registry

        # 查找关键列
        self.sales_col = self._find_col(["sales", "销售额", "Sales"])
        self.profit_col = self._find_col(["profit", "利润", "Profit"])
        self.discount_col = self._find_col(["discount", "折扣", "Discount"])
        self.quantity_col = self._find_col(["quantity", "数量", "销量", "Quantity"])

        # 查找维度列
        self.region_col = self._find_col(["region", "区域", "地区", "Region"])
        self.category_col = self._find_col(["category", "品类", "Category"])
        self.subcategory_col = self._find_col(["sub_category", "subcategory", "子品类", "SubCategory"])
        self.segment_col = self._find_col(["segment", "客群", "客户类型", "Segment"])
        self.ship_mode_col = self._find_col(["ship_mode", "shipmode", "运输方式", "Ship Mode"])

        self.is_viable = self.sales_col is not None

    def _find_col(self, names: List[str]) -> Optional[str]:
        for name in names:
            for col in self.df.columns:
                if name.lower() in col.lower().strip():
                    return col
        return None

    def _get_binned_discount_col(self) -> Optional[str]:
        """创建折扣分箱列（如果需要）。"""
        if not self.discount_col:
            return None

        temp_col = "_discount_bin_cross"
        if temp_col not in self.df.columns:
            bins = [0, 0.01, 0.10, 0.20, 0.30, float("inf")]
            labels = ["0%", "1-10%", "11-20%", "21-30%", ">30%"]
            self.df[temp_col] = pd.cut(
                self.df[self.discount_col], bins=bins, labels=labels, right=True
            )
        return temp_col

    def _get_binned_profit_margin_col(self) -> Optional[str]:
        """创建利润率分箱列。"""
        if not self.profit_col or not self.sales_col:
            return None

        temp_col = "_profit_margin_bin_cross"
        if temp_col not in self.df.columns:
            margin = np.where(
                self.df[self.sales_col] > 0,
                self.df[self.profit_col] / self.df[self.sales_col] * 100,
                0,
            )
            self.df[temp_col] = pd.cut(
                margin,
                bins=[-float("inf"), 0, 5, 10, 20, float("inf")],
                labels=["亏损", "0-5%", "5-10%", "10-20%", ">20%"],
            )
        return temp_col

    def analyze_all(self) -> Dict[str, Any]:
        """执行所有有效的交叉维度分析。"""
        if not self.is_viable:
            return {"error": "缺少销售额列", "is_viable": False}

        results = {
            "is_viable": True,
            "combinations": [],
            "summary": {},
        }

        # 定义可能的维度组合（按优先级）
        combos = []

        if self.region_col and self.category_col:
            combos.append(("region_x_category", self.region_col, self.category_col, "区域×品类"))
        if self.category_col and self.discount_col:
            disc_bin = self._get_binned_discount_col()
            if disc_bin:
                combos.append(("category_x_discount", self.category_col, disc_bin, "品类×折扣区间"))
        if self.segment_col and self.category_col:
            combos.append(("segment_x_category", self.segment_col, self.category_col, "客群×品类"))
        if self.ship_mode_col:
            margin_bin = self._get_binned_profit_margin_col()
            if margin_bin:
                combos.append(("ship_mode_x_margin", self.ship_mode_col, margin_bin, "运输方式×利润率"))
        if self.region_col and self.segment_col:
            combos.append(("region_x_segment", self.region_col, self.segment_col, "区域×客群"))
        if self.region_col and self.subcategory_col:
            combos.append(("region_x_subcategory", self.region_col, self.subcategory_col, "区域×子品类"))

        for combo_id, dim1, dim2, label in combos:
            try:
                combo_result = self.analyze_cross(
                    dim1=dim1,
                    dim2=dim2,
                    label=label,
                    combo_id=combo_id,
                )
                if combo_result and "error" not in combo_result:
                    results["combinations"].append(combo_result)
            except Exception as e:
                results["combinations"].append({
                    "combo_id": combo_id,
                    "label": label,
                    "error": str(e),
                })

        # 生成摘要
        total_combos = len(results["combinations"])
        successful = sum(1 for c in results["combinations"] if "error" not in c)
        results["summary"] = {
            "total_combinations": total_combos,
            "successful": successful,
            "failed": total_combos - successful,
        }

        return results

    def analyze_cross(
        self,
        dim1: str,
        dim2: str,
        label: str = "",
        combo_id: str = "",
    ) -> Dict[str, Any]:
        """分析两个维度的交叉交互。"""
        from config import clean_field_name

        cols_needed = [dim1, dim2]
        if self.sales_col:
            cols_needed.append(self.sales_col)
        if self.profit_col:
            cols_needed.append(self.profit_col)

        df_clean = self.df[cols_needed].dropna()
        if len(df_clean) < 10:
            return {"error": "有效数据量不足（<10行）"}

        # 分组聚合
        grouped = df_clean.groupby([dim1, dim2], observed=True).agg(
            **{
                "total_sales": (self.sales_col, "sum") if self.sales_col else ("_dummy", "count"),
                "transaction_count": (self.sales_col, "count") if self.sales_col else ("_dummy", "count"),
                **(
                    {"total_profit": (self.profit_col, "sum")}
                    if self.profit_col else {}
                ),
            }
        )

        if self.sales_col and self.profit_col:
            grouped["profit_margin"] = np.where(
                grouped["total_sales"] > 0,
                (grouped["total_profit"] / grouped["total_sales"] * 100).round(2),
                0,
            )

        # 计算整体均值用于检测偏离
        overall_sales_avg = grouped["total_sales"].mean()
        if self.profit_col:
            overall_margin_avg = grouped["profit_margin"].mean()

        # 提取显著的交叉组合（偏离整体均值≥2倍标准差）
        sales_std = grouped["total_sales"].std() if len(grouped) > 1 else 0
        top_patterns = []

        for (d1, d2), row in grouped.iterrows():
            sales_deviation = (row["total_sales"] - overall_sales_avg) / max(sales_std, 1)
            entry = {
                "dim1": str(d1),
                "dim2": str(d2),
                "total_sales": round(float(row["total_sales"]), 2),
                "transaction_count": int(row["transaction_count"]),
            }
            if self.profit_col and "profit_margin" in row.index:
                entry["profit_margin"] = round(float(row["profit_margin"]), 2)
                entry["margin_deviation"] = round(
                    float(row["profit_margin"] - overall_margin_avg), 2
                )

            if abs(sales_deviation) >= 1.5:
                entry["is_notable"] = True
                entry["note"] = (
                    f"销售额显著{'高于' if sales_deviation > 0 else '低于'}均值"
                    f"（偏离{sales_deviation:.1f}个标准差）"
                )
                top_patterns.append(entry)

        # 按销售额排序
        top_patterns.sort(key=lambda x: x.get("total_sales", 0), reverse=True)
        top_patterns = top_patterns[:12]

        return {
            "combo_id": combo_id,
            "label": label,
            "dimensions": [dim1, dim2],
            "display_names": [clean_field_name(dim1), clean_field_name(dim2)],
            "n_combinations": len(grouped),
            "n_notable_patterns": len(top_patterns),
            "overall_avg_sales": round(float(overall_sales_avg), 2),
            "top_patterns": top_patterns,
            "interpretation_ready": (
                f"{label}分析完成：共 {len(grouped)} 个组合，"
                f"其中 {len(top_patterns)} 个组合显示出显著偏离整体均值的特征。"
                "这些显著组合值得在报告中重点讨论。"
            ),
        }
