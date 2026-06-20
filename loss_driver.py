# -*- coding: utf-8 -*-
"""
@File    : loss_driver.py
@Author  : Robusr
@Date    : 2026/6/20
@Description: 亏损驱动分析模块 — 找出哪些品类/区域/客群/折扣区间贡献了主要亏损
"""

"""
亏损驱动分析器
功能：按多种维度分组（Category/SubCategory/Region/Segment/ShipMode/DiscountBins），
      计算每组的关键亏损指标，自动识别主要亏损来源。

核心指标：
- total_sales: 总销售额
- total_profit: 总利润
- profit_margin: 利润率 (%)
- loss_count: 亏损明细行数
- loss_rate: 亏损率（该组内亏损行占比）
- loss_amount: 亏损总额（负利润的绝对值之和）
- loss_contribution_pct: 亏损贡献率（该组亏损占总体亏损的百分比）
"""

import json
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from field_registry import FieldRole


class LossDriverAnalyzer:
    """亏损驱动分析器。"""

    def __init__(self, df: pd.DataFrame, field_registry: Optional[Dict[str, Any]] = None):
        self.df = df.copy()
        self.field_registry = field_registry

        # 识别关键列
        self.profit_col = self._find_column_by_role(
            [FieldRole.PROFIT], ["profit", "利润", "Profit"]
        )
        self.sales_col = self._find_column_by_role(
            [FieldRole.REVENUE], ["sales", "销售额", "Sales"]
        )
        self.discount_col = self._find_column_by_role(
            [FieldRole.DISCOUNT], ["discount", "折扣", "Discount"]
        )

        # 维度列
        self.dimension_cols = self._find_dimension_columns()

        # 验证
        self.is_viable = self.profit_col is not None

    def _find_column_by_role(self, roles: List[str], fallback_names: List[str]) -> Optional[str]:
        """通过角色或名称查找列。"""
        # 先查 field_registry
        if self.field_registry:
            for col, info in self.field_registry.get("fields", {}).items():
                if info.get("role") in roles:
                    return col
        # 回退按名称
        for name in fallback_names:
            for col in self.df.columns:
                if col.lower().strip() == name.lower():
                    return col
        # 模糊匹配
        for name in fallback_names:
            for col in self.df.columns:
                if name.lower() in col.lower():
                    return col
        return None

    def _find_dimension_columns(self) -> List[str]:
        """查找可用作分析维度的列。"""
        dims = []
        # 从 field_registry 获取
        if self.field_registry:
            for col, info in self.field_registry.get("fields", {}).items():
                if info.get("is_dimension") and not info.get("is_id_field"):
                    dims.append(col)

        # 回退：找分类列
        if not dims:
            for col in self.df.columns:
                if (
                    col != self.profit_col
                    and col != self.sales_col
                    and col != self.discount_col
                    and self.df[col].dtype == "object"
                    and self.df[col].nunique() <= 20
                    and self.df[col].nunique() >= 2
                ):
                    dims.append(col)

        return dims[:8]  # 最多8个维度

    def analyze_all(self) -> Dict[str, Any]:
        """对全部可用维度执行亏损驱动分析。"""
        if not self.is_viable:
            return {"error": "未找到利润列，无法执行亏损驱动分析", "is_viable": False}

        results = {
            "is_viable": True,
            "profit_column": self.profit_col,
            "sales_column": self.sales_col,
            "dimensions_analyzed": [],
            "dimension_results": {},
            "top_loss_contributors": [],
            "overall_summary": {},
        }

        # 总体指标
        total_sales = self.df[self.sales_col].sum() if self.sales_col else 0
        total_profit = self.df[self.profit_col].sum()
        total_loss_amount = abs(self.df[self.profit_col][self.df[self.profit_col] < 0].sum())
        overall_loss_rate = (self.df[self.profit_col] < 0).mean()
        overall_profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0

        results["overall_summary"] = {
            "total_sales": round(float(total_sales), 2),
            "total_profit": round(float(total_profit), 2),
            "total_loss_amount": round(float(total_loss_amount), 2),
            "overall_loss_rate": round(float(overall_loss_rate), 4),
            "overall_profit_margin": round(float(overall_profit_margin), 2),
            "total_rows": len(self.df),
        }

        # 按每个维度分析
        all_contributors = []
        for dim in self.dimension_cols:
            try:
                dim_result = self.analyze_by_dimension(dim)
                results["dimension_results"][dim] = dim_result
                results["dimensions_analyzed"].append(dim)

                # 收集亏损贡献者
                for item in dim_result.get("top_loss_items", []):
                    item["dimension"] = dim
                    item["dimension_display"] = dim_result.get("dimension_display", dim)
                    all_contributors.append(item)
            except Exception as e:
                results["dimension_results"][dim] = {"error": str(e)}

        # 合并所有维度的亏损贡献者，按亏损贡献率排序
        all_contributors.sort(key=lambda x: x.get("loss_contribution_pct", 0), reverse=True)
        results["top_loss_contributors"] = all_contributors[:15]

        return results

    def analyze_by_dimension(self, dimension_col: str) -> Dict[str, Any]:
        """按单个维度分组分析亏损驱动因素。"""
        from config import clean_field_name

        dimension_display = clean_field_name(dimension_col)

        # 分组聚合
        group_cols = [dimension_col]
        agg_dict = {}
        if self.profit_col:
            agg_dict[self.profit_col] = ["sum", "mean", "count"]
            agg_dict["_is_loss"] = "sum"
        if self.sales_col:
            agg_dict[self.sales_col] = ["sum", "mean"]
        if self.discount_col:
            agg_dict[self.discount_col] = "mean"

        # 创建亏损标记
        df_temp = self.df.copy()
        df_temp["_is_loss"] = (df_temp[self.profit_col] < 0).astype(int)
        df_temp["_loss_amount"] = df_temp[self.profit_col].apply(
            lambda x: abs(x) if x < 0 else 0
        )

        # 聚合
        grouped = df_temp.groupby(dimension_col, dropna=False).agg(**{
            "total_sales": (self.sales_col, "sum") if self.sales_col else ("_is_loss", "count"),
            "total_profit": (self.profit_col, "sum"),
            "avg_profit": (self.profit_col, "mean"),
            "transaction_count": ("_is_loss", "count"),
            "loss_count": ("_is_loss", "sum"),
            "loss_amount": ("_loss_amount", "sum"),
            "avg_discount": (self.discount_col, "mean") if self.discount_col else ("_is_loss", "count"),
        })

        # 计算衍生指标
        total_loss = grouped["loss_amount"].sum()
        grouped["profit_margin"] = np.where(
            grouped["total_sales"] > 0,
            (grouped["total_profit"] / grouped["total_sales"] * 100).round(2),
            0,
        )
        grouped["loss_rate"] = np.where(
            grouped["transaction_count"] > 0,
            (grouped["loss_count"] / grouped["transaction_count"]).round(4),
            0,
        )
        grouped["loss_contribution_pct"] = np.where(
            total_loss > 0,
            (grouped["loss_amount"] / total_loss * 100).round(2),
            0,
        )
        if self.discount_col:
            grouped["avg_discount"] = grouped["avg_discount"].round(4)

        # 按亏损贡献率排序
        grouped = grouped.sort_values("loss_contribution_pct", ascending=False)

        # 转换为列表
        top_loss_items = []
        for idx, row in grouped.head(15).iterrows():
            if row["loss_amount"] <= 0:
                continue
            top_loss_items.append({
                "name": str(idx),
                "total_sales": round(float(row["total_sales"]), 2),
                "total_profit": round(float(row["total_profit"]), 2),
                "profit_margin": round(float(row["profit_margin"]), 2),
                "transaction_count": int(row["transaction_count"]),
                "loss_count": int(row["loss_count"]),
                "loss_rate": round(float(row["loss_rate"]), 4),
                "loss_amount": round(float(row["loss_amount"]), 2),
                "loss_contribution_pct": round(float(row["loss_contribution_pct"]), 2),
                "avg_discount": round(float(row["avg_discount"]), 4) if self.discount_col else None,
            })

        # 亏损集中度
        top3_loss_pct = sum(
            item["loss_contribution_pct"] for item in top_loss_items[:3]
        )

        return {
            "dimension": dimension_col,
            "dimension_display": dimension_display,
            "n_groups": len(grouped),
            "groups_with_losses": int((grouped["loss_count"] > 0).sum()),
            "top3_loss_concentration_pct": round(top3_loss_pct, 2),
            "top_loss_items": top_loss_items,
            "summary": {
                "largest_loss_contributor": top_loss_items[0] if top_loss_items else None,
                "loss_concentration": (
                    f"前3的{dimension_display}贡献了 {top3_loss_pct:.1f}% 的亏损"
                    if top_loss_items else "无亏损数据"
                ),
            },
        }
