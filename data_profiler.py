"""
数据画像生成模块
功能：对 DataFrame 进行总结，判断字段类型、统计缺失值/分布/频数，
      生成《数据画像 JSON》保存到本地。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

logger = logging.getLogger(__name__)

# 类型推断阈值
_UNIQUE_RATIO_THRESHOLD = 0.05       # 唯一值占比 < 5% 且唯一数 <= 50 → 分类
_MAX_CATEGORY_CARDINALITY = 50        # 分类变量最大基数
_MIN_NUMERIC_UNIQUE = 10              # 至少 10 个唯一值才视为连续


class DataProfiler:
    """数据画像器：字段级 + 整体级画像，输出为 JSON。"""

    def __init__(
        self,
        df: pd.DataFrame,
        *,
        output_dir: Union[str, Path] = "./outputs",
        profile_filename: str = "data_profile.json",
        categorical_cardinality: int = _MAX_CATEGORY_CARDINALITY,
    ) -> None:
        self.df = df
        self.output_dir = Path(output_dir)
        self.profile_filename = profile_filename
        self.categorical_cardinality = categorical_cardinality
        self.profile: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def generate(self) -> dict[str, Any]:
        """主入口：生成完整数据画像并保存 JSON。"""
        self.profile = {
            "meta": self._build_meta(),
            "overview": self._build_overview(),
            "fields": self._build_field_profiles(),
        }
        self._save()
        logger.info("数据画像已保存至 %s", self.output_dir / self.profile_filename)
        return self.profile

    # ------------------------------------------------------------------
    # 内部：整体信息
    # ------------------------------------------------------------------

    def _build_meta(self) -> dict:
        return {
            "generated_at": datetime.now().isoformat(),
            "n_rows": len(self.df),
            "n_columns": len(self.df.columns),
            "total_missing": int(self.df.isna().sum().sum()),
            "total_missing_pct": round(
                self.df.isna().sum().sum() / (len(self.df) * len(self.df.columns)) * 100, 2
            ),
        }

    def _build_overview(self) -> dict:
        types_summary = {}
        for col in self.df.columns:
            ftype = self._classify_field(self.df[col])
            types_summary[ftype] = types_summary.get(ftype, 0) + 1
        return {
            "field_type_counts": types_summary,
            "duplicate_rows": int(self.df.duplicated().sum()),
            "memory_usage_mb": round(self.df.memory_usage(deep=True).sum() / (1024 * 1024), 3),
        }

    # ------------------------------------------------------------------
    # 内部：逐字段画像
    # ------------------------------------------------------------------

    def _build_field_profiles(self) -> list[dict]:
        profiles = []
        for col in self.df.columns:
            series = self.df[col]
            ftype = self._classify_field(series)
            field_info: dict[str, Any] = {
                "column": col,
                "dtype": str(series.dtype),
                "inferred_type": ftype,
                "count": int(len(series)),
                "missing": int(series.isna().sum()),
                "missing_pct": round(series.isna().sum() / len(series) * 100, 2),
                "unique": int(series.nunique(dropna=True)),
            }

            if ftype == "numeric_continuous":
                field_info["stats"] = self._numeric_stats(series)
            elif ftype == "datetime":
                field_info["stats"] = self._datetime_stats(series)
            else:
                field_info["stats"] = self._categorical_stats(series)

            profiles.append(field_info)
        return profiles

    # ------------------------------------------------------------------

    def _classify_field(self, series: pd.Series) -> str:
        """
        推断字段类型，返回以下之一：
        - numeric_continuous
        - numeric_discrete
        - categorical
        - datetime
        - text
        - unknown
        """
        non_null = series.dropna()
        if len(non_null) == 0:
            return "unknown"

        dtype = series.dtype

        # datetime
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return "datetime"

        # 数值型细分
        if pd.api.types.is_numeric_dtype(dtype):
            n_unique = non_null.nunique()
            if n_unique <= 2:
                return "categorical"          # 二值变量 → 分类更合适
            if n_unique <= self.categorical_cardinality:
                return "numeric_discrete"
            return "numeric_continuous"

        # object / string
        if dtype == "object" or pd.api.types.is_string_dtype(dtype):
            n_unique = non_null.nunique()
            n_total = len(non_null)
            ratio = n_unique / max(n_total, 1)

            # 唯一值极少 → 分类
            if n_unique <= self.categorical_cardinality:
                return "categorical"

            # 唯一值占比低且总数可控 → 分类
            if ratio <= _UNIQUE_RATIO_THRESHOLD and n_unique <= self.categorical_cardinality:
                return "categorical"

            # 检查是否实际为文本
            avg_len = non_null.astype(str).str.len().mean()
            if avg_len > 50 and n_unique > self.categorical_cardinality:
                return "text"

            return "categorical"

        return "unknown"

    # ------------------------------------------------------------------

    def _numeric_stats(self, series: pd.Series) -> dict:
        """数值型字段的统计摘要。"""
        non_null = series.dropna()
        if len(non_null) < 2:
            return {"error": "样本量不足（< 2）", "n": len(non_null)}

        n = len(non_null)
        mean = round(float(non_null.mean()), 6)
        std = round(float(non_null.std(ddof=1)), 6)
        skew = round(float(scipy_stats.skew(non_null)), 6)
        kurt = round(float(scipy_stats.kurtosis(non_null)), 6)

        # 百分位数
        percentiles = [0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100]
        p_values = np.percentile(non_null, percentiles)

        return {
            "n": n,
            "mean": mean,
            "median": round(float(non_null.median()), 6),
            "std": std,
            "variance": round(float(non_null.var(ddof=1)), 6),
            "min": round(float(non_null.min()), 6),
            "max": round(float(non_null.max()), 6),
            "range": round(float(non_null.max() - non_null.min()), 6),
            "iqr": round(float(np.percentile(non_null, 75) - np.percentile(non_null, 25)), 6),
            "skewness": skew,
            "kurtosis": kurt,
            "cv": round(std / mean * 100, 4) if mean != 0 else None,  # 变异系数 %
            "percentiles": {f"p{p}": round(float(v), 6) for p, v in zip(percentiles, p_values)},
            "outliers_iqr": self._count_outliers_iqr(non_null),
            "normality_shapiro": self._shapiro_safe(non_null),
        }

    # ------------------------------------------------------------------

    def _datetime_stats(self, series: pd.Series) -> dict:
        """日期时间型字段的摘要。"""
        non_null = series.dropna()
        if len(non_null) == 0:
            return {"error": "无有效值"}
        return {
            "n": len(non_null),
            "min": str(non_null.min()),
            "max": str(non_null.max()),
            "range_days": (non_null.max() - non_null.min()).days,
        }

    # ------------------------------------------------------------------

    def _categorical_stats(self, series: pd.Series) -> dict:
        """分类型字段的频数摘要。"""
        non_null = series.dropna()
        n_total = len(series)
        n_missing = int(series.isna().sum())

        vc = non_null.value_counts()
        freq_dist: dict[str, Any] = {}
        for i, (val, cnt) in enumerate(vc.items()):
            if i >= 20:  # 最多展示前 20 类
                freq_dist["_others_count"] = len(vc) - 20
                freq_dist["_others_total"] = int(vc.iloc[20:].sum())
                break
            key = str(val)
            freq_dist[key] = {
                "count": int(cnt),
                "pct": round(cnt / n_total * 100, 2),
            }

        return {
            "n_total": n_total,
            "n_missing": n_missing,
            "n_unique": int(non_null.nunique()),
            "mode": str(vc.idxmax()) if len(vc) > 0 else None,
            "mode_count": int(vc.iloc[0]) if len(vc) > 0 else 0,
            "mode_pct": round(vc.iloc[0] / n_total * 100, 2) if len(vc) > 0 else 0,
            "frequency_distribution": freq_dist,
        }

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _count_outliers_iqr(series: pd.Series) -> int:
        """按 IQR 规则统计离群值数量。"""
        q1 = np.percentile(series, 25)
        q3 = np.percentile(series, 75)
        iqr = q3 - q1
        if iqr == 0:
            return 0
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        return int(((series < lower) | (series > upper)).sum())

    @staticmethod
    def _shapiro_safe(series: pd.Series) -> Optional[dict]:
        """
        Shapiro-Wilk 正态性检验。
        scipy 要求 3 ≤ n ≤ 5000；超出范围或报错时返回 None。
        """
        n = len(series)
        if n < 3 or n > 5000:
            return None
        try:
            stat, p = scipy_stats.shapiro(series)
            return {"statistic": round(float(stat), 6), "p_value": round(float(p), 6)}
        except Exception:
            return None

    # ------------------------------------------------------------------

    def _save(self) -> None:
        """保存画像 JSON。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / self.profile_filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.profile, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 便捷函数
# ------------------------------------------------------------------

def generate_profile(
    df: pd.DataFrame,
    output_dir: Union[str, Path] = "./outputs",
    profile_filename: str = "data_profile.json",
) -> dict[str, Any]:
    """一行调用：生成并保存数据画像 JSON。"""
    profiler = DataProfiler(df, output_dir=output_dir, profile_filename=profile_filename)
    return profiler.generate()


# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    import sys

    if len(sys.argv) < 2:
        print("用法：python data_profiler.py <file_path>")
        sys.exit(1)

    # 用 data_loader 先加载
    from data_loader import load_and_clean

    df = load_and_clean(sys.argv[1])
    profile = generate_profile(df)
    print(json.dumps(profile, ensure_ascii=False, indent=2))
