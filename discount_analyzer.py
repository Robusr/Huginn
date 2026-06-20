# -*- coding: utf-8 -*-
"""
@File    : discount_analyzer.py
@Author  : Robusr
@Date    : 2026/6/20
@Description: 折扣响应分析模块 — 折扣分箱、阈值识别、品类内对照、异常检测
"""

"""
折扣响应分析器
功能：
1. 折扣分箱 (0%, 1-10%, 11-20%, 21-30%, >30%)
2. 品类内的折扣×销量/利润关系分析
3. 折扣阈值识别（利润率转负的临界点）
4. 高折扣但销售未改善的异常组合检测

约束：
- 不能仅凭总体 Pearson 相关给出折扣政策结论
- 必须按品类分层后再分析折扣效应
- 必须区分相关性与因果：高折扣可能是结果（滞销品打折）而非原因
"""

import json
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from field_registry import FieldRole


class DiscountAnalyzer:
    """折扣响应分析器。"""

    DEFAULT_BINS = [0, 0.01, 0.10, 0.20, 0.30, float("inf")]
    DEFAULT_LABELS = ["0%", "1-10%", "11-20%", "21-30%", ">30%"]

    def __init__(self, df: pd.DataFrame, field_registry: Optional[Dict[str, Any]] = None):
        self.df = df.copy()
        self.field_registry = field_registry

        self.discount_col = self._find_column(["discount", "折扣", "Discount"])
        self.sales_col = self._find_column(["sales", "销售额", "Sales"])
        self.profit_col = self._find_column(["profit", "利润", "Profit"])
        self.quantity_col = self._find_column(["quantity", "数量", "销量", "Quantity"])
        self.category_col = self._find_column(["category", "品类", "Category"])

        self.is_viable = self.discount_col is not None

    def _find_column(self, names: List[str]) -> Optional[str]:
        """查找匹配的列。"""
        for name in names:
            for col in self.df.columns:
                if name.lower() in col.lower().strip():
                    return col
        return None

    def analyze_all(self) -> Dict[str, Any]:
        """执行完整的折扣响应分析。"""
        if not self.is_viable:
            return {"error": "未找到折扣列", "is_viable": False}

        results = {
            "is_viable": True,
            "discount_column": self.discount_col,
            "sales_column": self.sales_col,
            "profit_column": self.profit_col,
            "category_column": self.category_col,
            "overall_summary": self._overall_discount_summary(),
            "discount_bins": self._analyze_discount_bins(),
            "category_discount_response": self._category_discount_response(),
            "profit_tipping_point": self._find_discount_threshold(),
            "anomalies": self._detect_high_discount_anomalies(),
        }

        # 添加人类可读摘要
        tp = results["profit_tipping_point"]
        anomalies = results["anomalies"]
        results["tipping_point_detail"] = tp.get("description", "未检测到阈值")
        results["n_discount_bins"] = len(results["discount_bins"].get("bins", []))
        results["anomalies_summary"] = anomalies.get("summary", "未检测到显著异常")

        return results

    def _overall_discount_summary(self) -> Dict[str, Any]:
        """总体折扣统计。"""
        disc = self.df[self.discount_col].dropna()
        if len(disc) == 0:
            return {"error": "折扣列无有效数据"}

        n_with_discount = (disc > 0).sum()
        return {
            "mean_discount": round(float(disc.mean()), 4),
            "median_discount": round(float(disc.median()), 4),
            "max_discount": round(float(disc.max()), 4),
            "discount_rate": round(float(n_with_discount / len(disc)), 4),
            "n_total": len(disc),
            "n_with_discount": int(n_with_discount),
        }

    def _analyze_discount_bins(self) -> Dict[str, Any]:
        """按折扣分箱分析销量和利润。"""
        disc = self.df[self.discount_col].dropna()
        if len(disc) == 0:
            return {"error": "无有效折扣数据"}

        df_temp = self.df.dropna(subset=[self.discount_col]).copy()
        df_temp["_discount_bin"] = pd.cut(
            df_temp[self.discount_col],
            bins=self.DEFAULT_BINS,
            labels=self.DEFAULT_LABELS,
            right=True,
        )

        agg_dict = {"_discount_bin": "count"}
        if self.sales_col:
            agg_dict[self.sales_col] = ["sum", "mean"]
        if self.profit_col:
            agg_dict[self.profit_col] = ["sum", "mean"]
        if self.quantity_col:
            agg_dict[self.quantity_col] = ["sum", "mean"]

        grouped = df_temp.groupby("_discount_bin", observed=False).agg(agg_dict)

        bins = []
        for idx, row in grouped.iterrows():
            bin_info = {
                "bin": str(idx),
                "count": int(row[("_discount_bin", "count")]),
            }
            if self.sales_col:
                bin_info["total_sales"] = round(float(row[(self.sales_col, "sum")]), 2)
                bin_info["avg_sales"] = round(float(row[(self.sales_col, "mean")]), 2)
            if self.profit_col:
                bin_info["total_profit"] = round(float(row[(self.profit_col, "sum")]), 2)
                bin_info["avg_profit"] = round(float(row[(self.profit_col, "mean")]), 2)
            if self.quantity_col:
                bin_info["total_quantity"] = round(float(row[(self.quantity_col, "sum")]), 2)
                bin_info["avg_quantity"] = round(float(row[(self.quantity_col, "mean")]), 2)
            bins.append(bin_info)

        return {
            "bins": bins,
        }

    def _category_discount_response(self) -> Dict[str, Any]:
        """品类内的折扣与利润关系分析（分层分析，避免辛普森悖论）。"""
        if not self.category_col:
            return {"error": "未找到品类列，无法执行分层分析"}

        df_temp = self.df.dropna(subset=[self.discount_col, self.category_col]).copy()
        df_temp["_discount_bin"] = pd.cut(
            df_temp[self.discount_col],
            bins=self.DEFAULT_BINS,
            labels=self.DEFAULT_LABELS,
            right=True,
        )

        category_responses = {}
        for cat in df_temp[self.category_col].unique():
            cat_df = df_temp[df_temp[self.category_col] == cat]
            if len(cat_df) < 5:
                continue

            response = {}
            for bin_label in self.DEFAULT_LABELS:
                bin_df = cat_df[cat_df["_discount_bin"] == bin_label]
                if len(bin_df) < 3:
                    continue
                entry = {"count": len(bin_df)}
                if self.sales_col:
                    entry["avg_sales"] = round(float(bin_df[self.sales_col].mean()), 2)
                if self.profit_col:
                    entry["avg_profit"] = round(float(bin_df[self.profit_col].mean()), 2)
                if self.quantity_col:
                    entry["avg_quantity"] = round(float(bin_df[self.quantity_col].mean()), 2)
                response[str(bin_label)] = entry

            if response:
                category_responses[str(cat)] = response

        return {
            "categories_analyzed": len(category_responses),
            "category_details": category_responses,
        }

    def _find_discount_threshold(self) -> Dict[str, Any]:
        """识别利润率转负的折扣阈值。"""
        if not self.profit_col:
            return {"error": "无利润列", "description": "无利润数据，无法计算阈值"}

        df_temp = self.df.dropna(subset=[self.discount_col, self.profit_col]).copy()

        # 按折扣分箱计算平均利润率
        df_temp["_discount_bin"] = pd.cut(
            df_temp[self.discount_col],
            bins=self.DEFAULT_BINS,
            labels=self.DEFAULT_LABELS,
            right=True,
        )

        if self.sales_col:
            df_temp = df_temp.dropna(subset=[self.sales_col])
            df_temp["_margin"] = np.where(
                df_temp[self.sales_col] > 0,
                df_temp[self.profit_col] / df_temp[self.sales_col] * 100,
                0,
            )
        else:
            df_temp["_margin"] = df_temp[self.profit_col]

        bin_margins = df_temp.groupby("_discount_bin", observed=False)["_margin"].mean()

        # 找第一个利润率为负的分箱
        tipping_point = None
        tipping_bin = None
        for bin_label, margin in bin_margins.items():
            if margin < 0:
                tipping_point = str(bin_label)
                tipping_bin = str(bin_label)
                break

        if tipping_bin is None:
            return {
                "tipping_bin": None,
                "description": "在当前折扣范围内，所有分箱的平均利润均为正",
                "bin_margins": {str(k): round(float(v), 2) for k, v in bin_margins.items()},
            }

        return {
            "tipping_bin": tipping_bin,
            "description": (
                f"当折扣进入 {tipping_bin} 区间时，平均利润率转为负值"
                f"（{tipping_bin}: {bin_margins.get(tipping_bin, 0):.2f}%）。"
                "建议对该区间的折扣进行严格控制。"
            ),
            "bin_margins": {str(k): round(float(v), 2) for k, v in bin_margins.items()},
            "recommendation": (
                f"建议将折扣上限设置在 {tipping_bin} 以下，"
                "或针对高利润率品类允许更高的折扣上限。"
            ),
        }

    def _detect_high_discount_anomalies(self) -> Dict[str, Any]:
        """检测高折扣但销售未改善的异常组合。

        高折扣低回报组合：折扣分箱最高但销售额或利润在品类内低下。
        """
        if not self.category_col or not self.sales_col:
            return {"summary": "需要品类+销售数据才能检测异常", "anomaly_count": 0}

        df_temp = self.df.dropna(subset=[self.discount_col, self.category_col, self.sales_col]).copy()
        if len(df_temp) < 20:
            return {"summary": "数据量不足", "anomaly_count": 0}

        df_temp["_discount_bin"] = pd.cut(
            df_temp[self.discount_col],
            bins=self.DEFAULT_BINS,
            labels=self.DEFAULT_LABELS,
            right=True,
        )

        anomalies = []
        for cat in df_temp[self.category_col].unique():
            cat_df = df_temp[df_temp[self.category_col] == cat]
            if len(cat_df) < 10:
                continue

            median_sales = cat_df[self.sales_col].median()
            # 找高折扣区间
            high_disc = cat_df[
                cat_df["_discount_bin"].isin([">30%", "21-30%"])
            ]
            if len(high_disc) < 3:
                continue

            low_sales_high_disc = high_disc[high_disc[self.sales_col] < median_sales]
            if len(low_sales_high_disc) > 0:
                anomalies.append({
                    "category": str(cat),
                    "anomaly_type": "高折扣低销售",
                    "count": len(low_sales_high_disc),
                    "avg_sales": round(float(low_sales_high_disc[self.sales_col].mean()), 2),
                    "category_median_sales": round(float(median_sales), 2),
                    "avg_discount": round(float(low_sales_high_disc[self.discount_col].mean()), 4),
                })

        anomalies.sort(key=lambda x: x["count"], reverse=True)

        return {
            "anomaly_count": len(anomalies),
            "top_anomalies": anomalies[:10],
            "summary": (
                f"发现 {len(anomalies)} 个品类存在'高折扣但销售仍低于中位数'的异常组合。"
                "这可能表示：1）该品类的需求对折扣不敏感；2）折扣力度不足以刺激购买；"
                "3）这些商品可能本身吸引力不足，即使打折也效果有限。"
                if anomalies else "未检测到显著的高折扣低销售异常组合"
            ),
        }
