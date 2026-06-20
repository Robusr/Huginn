# -*- coding: utf-8 -*-
"""
@File    : pareto_analyzer.py
@Author  : Robusr
@Date    : 2026/6/20
@Description: 集中度与帕累托分析 — 识别头部贡献者、累计贡献率和异常对象
"""

"""
集中度与帕累托分析器
功能：
1. 产品/客户/子品类的销售额和利润贡献度排名
2. 累计贡献率曲线（识别多少实体贡献了80%的结果）
3. 高销售低利润对象识别
4. 低销售高亏损对象识别
"""

import json
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from field_registry import FieldRole


class ParetoAnalyzer:
    """集中度与帕累托分析器。"""

    def __init__(self, df: pd.DataFrame, field_registry: Optional[Dict[str, Any]] = None):
        self.df = df.copy()
        self.field_registry = field_registry

        self.sales_col = self._find_column(["sales", "销售额", "Sales"])
        self.profit_col = self._find_column(["profit", "利润", "Profit"])
        self.product_col = self._find_column(["product_name", "product_id", "产品", "商品", "Product Name", "Product"])
        self.customer_col = self._find_column(["customer_name", "customer_id", "客户", "Customer Name", "Customer"])
        self.subcategory_col = self._find_column(["sub_category", "subcategory", "子品类", "SubCategory"])

        self.is_viable = (
            self.sales_col is not None
            and (self.product_col is not None or self.customer_col is not None)
        )

    def _find_column(self, names: List[str]) -> Optional[str]:
        for name in names:
            for col in self.df.columns:
                if name.lower() in col.lower().strip():
                    return col
        return None

    def analyze_all(self) -> Dict[str, Any]:
        """执行完整的集中度分析。"""
        if not self.is_viable:
            return {"error": "缺少必要列（sales + product/customer）", "is_viable": False}

        results = {"is_viable": True}

        # 商品集中度
        if self.product_col:
            try:
                results["product_concentration"] = self.analyze_concentration(
                    group_by=self.product_col,
                    value_col=self.sales_col,
                    profit_col=self.profit_col,
                    label="商品",
                )
            except Exception as e:
                results["product_concentration"] = {"error": str(e)}

        # 客户集中度
        if self.customer_col:
            try:
                results["customer_concentration"] = self.analyze_concentration(
                    group_by=self.customer_col,
                    value_col=self.sales_col,
                    profit_col=self.profit_col,
                    label="客户",
                )
            except Exception as e:
                results["customer_concentration"] = {"error": str(e)}

        # 子品类集中度
        if self.subcategory_col:
            try:
                results["subcategory_concentration"] = self.analyze_concentration(
                    group_by=self.subcategory_col,
                    value_col=self.sales_col,
                    profit_col=self.profit_col,
                    label="子品类",
                )
            except Exception as e:
                results["subcategory_concentration"] = {"error": str(e)}

        # 高销售低利润对象
        if self.product_col and self.profit_col:
            results["high_sales_low_profit"] = self._find_high_sales_low_profit()

        # 低销售高亏损对象
        if self.product_col and self.profit_col:
            results["low_sales_high_loss"] = self._find_low_sales_high_loss()

        return results

    def analyze_concentration(
        self,
        group_by: str,
        value_col: str,
        profit_col: Optional[str] = None,
        label: str = "实体",
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """分析单一维度的集中度。"""
        grouped = self.df.groupby(group_by).agg({
            value_col: "sum",
            **( {profit_col: "sum"} if profit_col else {}),
        })
        grouped = grouped.sort_values(value_col, ascending=False)

        total_value = grouped[value_col].sum()
        total_items = len(grouped)
        grouped["pct_of_total"] = (grouped[value_col] / total_value * 100).round(2)
        grouped["cumulative_pct"] = grouped["pct_of_total"].cumsum().round(2)

        # Top-N
        top_items = []
        for i, (idx, row) in enumerate(grouped.head(top_n).iterrows()):
            item = {
                "rank": i + 1,
                "name": str(idx),
                "total_value": round(float(row[value_col]), 2),
                "pct_of_total": round(float(row["pct_of_total"]), 2),
                "cumulative_pct": round(float(row["cumulative_pct"]), 2),
            }
            if profit_col:
                item["total_profit"] = round(float(row[profit_col]), 2)
                item["profit_margin"] = (
                    round(float(row[profit_col] / row[value_col] * 100), 2)
                    if row[value_col] > 0 else 0
                )
            top_items.append(item)

        # 集中度指标
        top5_pct = grouped.head(5)["pct_of_total"].sum()
        top20_pct = grouped.head(max(1, total_items // 5))["pct_of_total"].sum()
        top80_count = (grouped["cumulative_pct"] <= 80).sum() + 1

        return {
            "group_by": group_by,
            "label": label,
            "total_items": total_items,
            "total_value": round(float(total_value), 2),
            "top_n": top_n,
            "top_items": top_items,
            "concentration_metrics": {
                "top5_pct": round(float(top5_pct), 2),
                "top20_pct": round(float(top20_pct), 2),
                "items_needed_for_80pct": int(top80_count),
                "pct_items_for_80pct": round(float(top80_count / total_items * 100), 2),
            },
            "interpretation": (
                f"前5个{label}贡献了 {top5_pct:.1f}% 的销售额；"
                f"前20%的{label}（约{max(1, total_items//5)}个）贡献了 {top20_pct:.1f}%；"
                f"需要 {top80_count} 个{label}（占{top80_count/total_items*100:.1f}%）才能覆盖80%的销售额。"
            ),
        }

    def _find_high_sales_low_profit(self) -> Dict[str, Any]:
        """找出销售额高但利润率低的商品。"""
        if not self.product_col or not self.profit_col or not self.sales_col:
            return {"error": "缺少必要列"}

        grouped = self.df.groupby(self.product_col).agg({
            self.sales_col: "sum",
            self.profit_col: "sum",
        })

        sales_median = grouped[self.sales_col].median()
        profit_median = grouped[self.profit_col].median()

        # 销售额在前25%（高销售），但利润在后25%（低利润）
        sales_q75 = grouped[self.sales_col].quantile(0.75)
        profit_q25 = grouped[self.profit_col].quantile(0.25)

        high_sales_mask = grouped[self.sales_col] >= sales_q75
        low_profit_mask = grouped[self.profit_col] <= profit_q25
        anomaly = grouped[high_sales_mask & low_profit_mask]

        profit_margin = np.where(
            anomaly[self.sales_col] > 0,
            (anomaly[self.profit_col] / anomaly[self.sales_col] * 100),
            0,
        )
        anomaly = anomaly.copy()
        anomaly["profit_margin"] = profit_margin
        anomaly = anomaly.sort_values("profit_margin")

        items = []
        for idx, row in anomaly.head(10).iterrows():
            items.append({
                "product": str(idx),
                "total_sales": round(float(row[self.sales_col]), 2),
                "total_profit": round(float(row[self.profit_col]), 2),
                "profit_margin": round(float(row["profit_margin"]), 2),
            })

        return {
            "count": len(anomaly),
            "top_items": items,
            "summary": (
                f"发现 {len(anomaly)} 个商品属于'高销售低利润'——"
                "它们贡献了大量销售额但利润率极低，建议检查定价和成本结构。"
                if len(anomaly) > 0 else "未发现显著的高销售低利润异常。"
            ),
        }

    def _find_low_sales_high_loss(self) -> Dict[str, Any]:
        """找出销售额低但亏损大的商品。"""
        if not self.product_col or not self.profit_col or not self.sales_col:
            return {"error": "缺少必要列"}

        grouped = self.df.groupby(self.product_col).agg({
            self.sales_col: "sum",
            self.profit_col: "sum",
        })

        sales_q25 = grouped[self.sales_col].quantile(0.25)

        low_sales_mask = grouped[self.sales_col] <= sales_q25
        loss_mask = grouped[self.profit_col] < 0
        anomaly = grouped[low_sales_mask & loss_mask]
        anomaly = anomaly.sort_values(self.profit_col)

        items = []
        for idx, row in anomaly.head(10).iterrows():
            items.append({
                "product": str(idx),
                "total_sales": round(float(row[self.sales_col]), 2),
                "total_profit": round(float(row[self.profit_col]), 2),
                "loss_per_dollar_sales": (
                    round(float(abs(row[self.profit_col]) / row[self.sales_col]), 4)
                    if row[self.sales_col] > 0 else "N/A"
                ),
            })

        return {
            "count": len(anomaly),
            "top_items": items,
            "summary": (
                f"发现 {len(anomaly)} 个商品属于'低销售高亏损'——"
                "它们的销售额已经很低但仍在亏损，建议考虑是否保留这些商品。"
                if len(anomaly) > 0 else "未发现显著的低销售高亏损异常。"
            ),
        }
