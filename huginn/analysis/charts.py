"""
面向通用分析报告的图表生成模块。
默认生成 4 张重点图，并同步输出 chart_metadata.json 供报告生成器复用。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd

from huginn.core.logger import get_logger

logger = get_logger(__name__)

import matplotlib

matplotlib.use("Agg")

# 提高 PIL 解压炸弹阈值，防止大尺寸图表报错
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # 禁用像素限制

import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import seaborn as sns

from huginn.core.label_utils import humanize_column_name
from huginn.domain.context import domain_keywords, is_identifier_or_noise


def _install_chinese_font() -> None:
    font_candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]

    selected_name = None
    for font_path in font_candidates:
        if not os.path.exists(font_path):
            continue
        try:
            fm.fontManager.addfont(font_path)
            selected_name = fm.FontProperties(fname=font_path).get_name()
            break
        except Exception:
            continue

    if selected_name:
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [
            selected_name,
            "PingFang SC",
            "Heiti SC",
            "SimHei",
            "Microsoft YaHei",
            "DejaVu Sans",
            "Arial",
        ]
    else:
        plt.rcParams["font.sans-serif"] = [
            "PingFang SC",
            "Heiti SC",
            "SimHei",
            "Microsoft YaHei",
            "DejaVu Sans",
            "Arial",
        ]

    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    plt.rcParams["savefig.dpi"] = 150
    plt.rcParams["savefig.bbox"] = "tight"
    plt.rcParams["savefig.pad_inches"] = 0.12


sns.set_style("whitegrid")
sns.set_context("notebook", font_scale=1.08)
_install_chinese_font()


class ChartGenerator:
    """根据统计结果优先生成更贴近报告重点的图表。"""

    _NOISE_KEYWORDS = ["序号", "提交答卷时间", "所用时间", "来源详情"]

    def __init__(
        self,
        df: pd.DataFrame,
        *,
        output_dir: Union[str, Path] = "./outputs/charts",
        stats_results: Optional[Dict[str, Any]] = None,
        domain_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.stats_results = stats_results or {}
        self.domain_context = domain_context or {}
        if self.domain_context.get("domain") == "retail_sales" or {"Sales", "Profit"}.issubset(df.columns):
            self._preferred_numeric_keywords = ["Profit", "Sales", "Discount", "Quantity", "利润", "销售", "折扣", "数量"]
            self._preferred_categorical_keywords = ["Category", "Sub-Category", "Region", "Segment", "Ship Mode", "品类", "区域"]
        else:
            self._preferred_numeric_keywords = domain_keywords(self.domain_context, "metric_keywords")
            self._preferred_categorical_keywords = domain_keywords(self.domain_context, "group_keywords")
        self.metadata_path = self.output_dir.parent / "chart_metadata.json"
        self.chart_metadata: Dict[str, Any] = {
            "generated_at": datetime.now().isoformat(),
            "charts": [],
        }
        self.focus = self._build_focus_context()

    def generate_all(self) -> list[str]:
        saved: list[str] = []
        for method in [
            self.bar_chart,
            self.box_plot,
            self.scatter_plot,
            self.correlation_heatmap,
        ]:
            try:
                path, meta = method()
                if path:
                    saved.append(str(path))
                    if meta:
                        self.chart_metadata["charts"].append(meta)
                    logger.info("图表已保存: %s", path)
            except Exception as exc:
                logger.error("生成图表失败 [%s]: %s", method.__name__, exc)

        self._save_metadata()
        return saved

    def bar_chart(self, filename: str = "bar_chart.png") -> tuple[Optional[Path], Dict[str, Any]]:
        pair = self.focus.get("primary_anova_pair") or self._fallback_group_pair()
        if not pair:
            return None, {}

        factor = pair["factor"]
        dependent = pair["dependent"]
        if factor not in self.df.columns or dependent not in self.df.columns:
            return None, {}

        grouped = self.df.groupby(factor)[dependent].mean().dropna().sort_values(ascending=False)
        counts = self.df[factor].value_counts().reindex(grouped.index).fillna(0)
        if grouped.empty:
            return None, {}

        fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.1))

        ax1 = axes[0]
        bars_left = ax1.bar(
            range(len(counts)),
            counts.values,
            color=sns.color_palette("Set2", len(counts)),
        )
        ax1.set_xticks(range(len(counts)))
        ax1.set_xticklabels(counts.index.astype(str), rotation=25, ha="right", fontsize=8.5)
        ax1.set_title(f"{self._label(factor)}样本分布", fontweight="bold")
        ax1.set_ylabel("记录数")
        for bar, value in zip(bars_left, counts.values):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.15,
                str(int(value)),
                ha="center",
                va="bottom",
                fontsize=8,
            )

        ax2 = axes[1]
        bars_right = ax2.bar(
            range(len(grouped)),
            grouped.values,
            color=sns.color_palette("Blues_d", len(grouped)),
        )
        ax2.set_xticks(range(len(grouped)))
        ax2.set_xticklabels(grouped.index.astype(str), rotation=25, ha="right", fontsize=8.5)
        ax2.set_title(f"{self._label(dependent)}分组均值", fontweight="bold")
        ax2.set_ylabel("均值")
        for bar, value in zip(bars_right, grouped.values):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

        fig.suptitle(
            f"{self._label(factor)}与{self._label(dependent)}对比",
            fontsize=14,
            fontweight="bold",
            y=1.02,
        )
        plt.tight_layout()

        path = self._save_fig(fig, filename)
        plt.close(fig)

        meta = {
            "chart_type": "bar_chart",
            "image": f"charts/{filename}",
            "title": f"{self._label(factor)}与{self._label(dependent)}对比",
            "factor": factor,
            "dependent": dependent,
            "group_count": int(len(grouped)),
            "count_distribution": {str(k): int(v) for k, v in counts.to_dict().items()},
            "group_means": {str(k): round(float(v), 4) for k, v in grouped.to_dict().items()},
            "highest_group": str(grouped.index[0]),
            "highest_mean": round(float(grouped.iloc[0]), 4),
            "lowest_group": str(grouped.index[-1]),
            "lowest_mean": round(float(grouped.iloc[-1]), 4),
            "source_test": pair.get("source_test", {}),
        }
        return path, meta

    def box_plot(self, filename: str = "box_plot.png") -> tuple[Optional[Path], Dict[str, Any]]:
        pair = self.focus.get("secondary_anova_pair") or self.focus.get("primary_anova_pair") or self._fallback_group_pair()
        if not pair:
            return None, {}

        factor = pair["factor"]
        dependent = pair["dependent"]
        if factor not in self.df.columns or dependent not in self.df.columns:
            return None, {}

        plot_data = self.df[[factor, dependent]].dropna()
        if plot_data.empty:
            return None, {}

        medians = plot_data.groupby(factor)[dependent].median().sort_values(ascending=False)
        order = medians.index.tolist()

        fig, ax = plt.subplots(figsize=(9.8, 5.8))
        sns.boxplot(
            data=plot_data,
            x=factor,
            y=dependent,
            order=order,
            ax=ax,
            palette="Set3",
            showfliers=True,
            fliersize=3,
        )
        ax.set_title(
            f"{self._label(dependent)}在{self._label(factor)}分组下的分布差异",
            fontweight="bold",
        )
        ax.set_xlabel("")
        ax.set_ylabel(self._label(dependent))
        ax.tick_params(axis="x", rotation=22, labelsize=8.5)
        plt.tight_layout()

        path = self._save_fig(fig, filename)
        plt.close(fig)

        group_stats = {}
        for group_name, series in plot_data.groupby(factor)[dependent]:
            group_stats[str(group_name)] = {
                "count": int(series.count()),
                "mean": round(float(series.mean()), 4),
                "median": round(float(series.median()), 4),
                "iqr": round(float(series.quantile(0.75) - series.quantile(0.25)), 4),
                "min": round(float(series.min()), 4),
                "max": round(float(series.max()), 4),
            }

        meta = {
            "chart_type": "box_plot",
            "image": f"charts/{filename}",
            "title": f"{self._label(dependent)}在{self._label(factor)}分组下的分布差异",
            "factor": factor,
            "dependent": dependent,
            "ordered_groups": order,
            "group_stats": group_stats,
            "source_test": pair.get("source_test", {}),
        }
        return path, meta

    def scatter_plot(self, filename: str = "scatter_plot.png") -> tuple[Optional[Path], Dict[str, Any]]:
        pair = self.focus.get("scatter_pair") or self._fallback_numeric_pair()
        if not pair:
            return None, {}

        x_col = pair["x"]
        y_col = pair["y"]
        if x_col not in self.df.columns or y_col not in self.df.columns:
            return None, {}

        plot_data = self.df[[x_col, y_col]].dropna()
        if len(plot_data) < 3:
            return None, {}

        corr = float(plot_data[x_col].corr(plot_data[y_col]))

        fig, ax = plt.subplots(figsize=(8.6, 6))
        sns.regplot(
            data=plot_data,
            x=x_col,
            y=y_col,
            ax=ax,
            scatter_kws={"alpha": 0.68, "edgecolor": "k", "s": 42},
            line_kws={"color": "#B23A48", "linewidth": 1.8},
        )
        ax.set_title(
            f"{self._label(y_col)}与{self._label(x_col)}的联动关系",
            fontweight="bold",
        )
        ax.set_xlabel(self._label(x_col))
        ax.set_ylabel(self._label(y_col))
        ax.text(
            0.98,
            0.03,
            f"Pearson r = {corr:.3f}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9.5,
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white", alpha=0.9),
        )
        plt.tight_layout()

        path = self._save_fig(fig, filename)
        plt.close(fig)

        meta = {
            "chart_type": "scatter_plot",
            "image": f"charts/{filename}",
            "title": f"{self._label(y_col)}与{self._label(x_col)}的联动关系",
            "x": x_col,
            "y": y_col,
            "correlation": round(corr, 4),
            "n": int(len(plot_data)),
            "x_mean": round(float(plot_data[x_col].mean()), 4),
            "y_mean": round(float(plot_data[y_col].mean()), 4),
        }
        return path, meta

    def correlation_heatmap(
        self,
        filename: str = "correlation_heatmap.png",
    ) -> tuple[Optional[Path], Dict[str, Any]]:
        numeric_cols = self.focus.get("heatmap_columns") or self._numeric_columns()
        numeric_cols = [c for c in numeric_cols if c in self.df.columns]
        if len(numeric_cols) < 2:
            return None, {}

        # 限制列数，避免热力图过大（PIL DecompressionBombError）
        if len(numeric_cols) > max_cols:
            # 优先选择方差较大的列（更有分析价值）
            variances = self.df[numeric_cols].var().sort_values(ascending=False)
            numeric_cols = list(variances.head(max_cols).index)

        corr_matrix = self.df[numeric_cols].corr()
        if corr_matrix.empty:
            return None, {}

        display_labels = self._unique_display_labels(numeric_cols)
        corr_for_plot = corr_matrix.copy()
        corr_for_plot.index = display_labels
        corr_for_plot.columns = display_labels

        fig, ax = plt.subplots(figsize=(max(8.2, len(numeric_cols) * 1.25), max(6.4, len(numeric_cols) * 0.95)))
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        cmap = sns.diverging_palette(250, 15, s=75, l=42, n=12, center="light")

        sns.heatmap(
            corr_for_plot,
            mask=mask,
            annot=True,
            fmt=".2f",
            cmap=cmap,
            center=0,
            vmin=-1,
            vmax=1,
            square=True,
            linewidths=0.45,
            cbar_kws={"shrink": 0.8, "label": "Pearson r"},
            ax=ax,
        )
        ax.set_title("核心数值指标相关性热力图", fontweight="bold", fontsize=14, pad=12)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.tick_params(axis="x", labelsize=8.5, rotation=28)
        ax.tick_params(axis="y", labelsize=8.5, rotation=0)
        ax.set_xticklabels(ax.get_xticklabels(), ha="right")
        plt.tight_layout()

        path = self._save_fig(fig, filename)
        plt.close(fig)

        meta = {
            "chart_type": "correlation_heatmap",
            "image": f"charts/{filename}",
            "title": "核心数值指标相关性热力图",
            "columns": numeric_cols,
            "top_pairs": self._top_correlation_pairs(corr_matrix, top_n=4),
        }
        return path, meta

    def _build_focus_context(self) -> Dict[str, Any]:
        anova_pairs = self._significant_anova_pairs()
        scatter_pair = self._best_correlation_pair()
        return {
            "primary_anova_pair": anova_pairs[0] if len(anova_pairs) >= 1 else None,
            "secondary_anova_pair": anova_pairs[1] if len(anova_pairs) >= 2 else None,
            "scatter_pair": scatter_pair,
            "heatmap_columns": self._heatmap_columns(scatter_pair, anova_pairs),
        }

    def _significant_anova_pairs(self) -> list[Dict[str, Any]]:
        tests = self.stats_results.get("anova", {}).get("tests", {})
        pairs: list[Dict[str, Any]] = []
        for item in tests.values():
            if not isinstance(item, dict):
                continue
            factor = item.get("factor")
            dependent = item.get("dependent")
            p_value = item.get("p_value")
            if (
                factor in self.df.columns
                and dependent in self.df.columns
                and isinstance(p_value, (int, float))
                and p_value < 0.05
            ):
                pairs.append(
                    {
                        "factor": factor,
                        "dependent": dependent,
                        "source_test": item,
                    }
                )
        pairs.sort(key=lambda x: x["source_test"].get("p_value", 1.0))
        return pairs

    def _fallback_group_pair(self) -> Optional[Dict[str, Any]]:
        categorical = self._categorical_columns(max_unique=8)
        numeric = self._numeric_columns()
        if not categorical or not numeric:
            return None
        return {
            "factor": categorical[0],
            "dependent": numeric[0],
            "source_test": {},
        }

    def _fallback_numeric_pair(self) -> Optional[Dict[str, Any]]:
        numeric = self._numeric_columns()
        if len(numeric) < 2:
            return None
        return {"x": numeric[0], "y": numeric[1]}

    def _best_correlation_pair(self) -> Optional[Dict[str, Any]]:
        numeric = self._numeric_columns()
        if len(numeric) < 2:
            return None

        candidate_cols = numeric[:8]
        corr_matrix = self.df[candidate_cols].corr()
        best_pair = None
        best_value = -1.0

        for i, left in enumerate(candidate_cols):
            for right in candidate_cols[i + 1 :]:
                value = corr_matrix.loc[left, right]
                if pd.isna(value):
                    continue
                if abs(float(value)) > best_value:
                    best_pair = {"x": left, "y": right, "correlation": round(float(value), 4)}
                    best_value = abs(float(value))
        return best_pair

    def _heatmap_columns(
        self,
        scatter_pair: Optional[Dict[str, Any]],
        anova_pairs: list[Dict[str, Any]],
    ) -> list[str]:
        preferred: list[str] = []
        for pair in anova_pairs[:2]:
            dependent = pair.get("dependent")
            if dependent and dependent not in preferred:
                preferred.append(dependent)
        if scatter_pair:
            for col in [scatter_pair.get("x"), scatter_pair.get("y")]:
                if col and col not in preferred:
                    preferred.append(col)

        numeric = self._numeric_columns()
        for col in numeric:
            if col not in preferred:
                preferred.append(col)
        return preferred[:6]

    def _numeric_columns(self, min_unique: int = 2) -> list[str]:
        cols = [
            c
            for c in self.df.columns
            if pd.api.types.is_numeric_dtype(self.df[c]) and self.df[c].dropna().nunique() >= min_unique
        ]
        cols = [
            c for c in cols
            if not is_identifier_or_noise(
                c,
                {"unique": int(self.df[c].nunique(dropna=True)), "inferred_type": "numeric_continuous"},
                len(self.df),
            )
        ]
        preferred = [c for c in cols if any(keyword in c for keyword in self._preferred_numeric_keywords)]
        return preferred + [c for c in cols if c not in preferred]

    def _categorical_columns(self, min_unique: int = 2, max_unique: int = 20) -> list[str]:
        cols: list[str] = []
        for col in self.df.columns:
            inferred_type = "numeric_continuous" if pd.api.types.is_numeric_dtype(self.df[col]) else "categorical"
            if is_identifier_or_noise(
                col,
                {"unique": int(self.df[col].nunique(dropna=True)), "inferred_type": inferred_type},
                len(self.df),
            ):
                continue
            series = self.df[col].dropna()
            unique = series.nunique()
            if pd.api.types.is_numeric_dtype(self.df[col]):
                if min_unique <= unique <= max_unique and unique <= max(8, len(self.df) * 0.12):
                    cols.append(col)
            elif min_unique <= unique <= max_unique:
                cols.append(col)

        preferred = [c for c in cols if any(keyword in c for keyword in self._preferred_categorical_keywords)]
        return preferred + [c for c in cols if c not in preferred]

    def _top_correlation_pairs(
        self,
        corr_matrix: pd.DataFrame,
        top_n: int = 4,
    ) -> list[Dict[str, Any]]:
        pairs: list[Dict[str, Any]] = []
        cols = list(corr_matrix.columns)
        for i, left in enumerate(cols):
            for right in cols[i + 1 :]:
                value = corr_matrix.loc[left, right]
                if pd.isna(value):
                    continue
                pairs.append(
                    {
                        "left": left,
                        "right": right,
                        "correlation": round(float(value), 4),
                        "abs_correlation": round(abs(float(value)), 4),
                    }
                )
        pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
        return pairs[:top_n]

    def _save_fig(self, fig: plt.Figure, filename: str) -> Path:
        path = self.output_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        return path

    def _save_metadata(self) -> None:
        self.metadata_path.write_text(
            json.dumps(self.chart_metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _label(column_name: str) -> str:
        return humanize_column_name(column_name)

    def _unique_display_labels(self, columns: list[str]) -> list[str]:
        seen: dict[str, int] = {}
        labels: list[str] = []
        for column in columns:
            label = self._label(column)
            count = seen.get(label, 0) + 1
            seen[label] = count
            labels.append(label if count == 1 else f"{label}({count})")
        return labels

    @staticmethod
    def _track_name(text: str) -> str:
        if "._" in text:
            return text.split("._")[-1].strip()
        return text


def generate_charts(
    df: pd.DataFrame,
    output_dir: Union[str, Path] = "./outputs/charts",
    stats_results: Optional[Dict[str, Any]] = None,
    domain_context: Optional[Dict[str, Any]] = None,
) -> list[str]:
    return ChartGenerator(
        df,
        output_dir=output_dir,
        stats_results=stats_results,
        domain_context=domain_context,
    ).generate_all()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法：python chart_generator.py <file_path>")
        raise SystemExit(1)

    from huginn.data.loader import load_and_clean

    dataframe = load_and_clean(sys.argv[1])
    paths = generate_charts(dataframe)
    print("\n生成的图表：")
    for item in paths:
        print(f"  {item}")
