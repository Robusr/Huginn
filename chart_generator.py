"""
可视化图表生成模块 v4 (Patch)
基于 matplotlib + seaborn 生成柱状图、箱线图、散点图、相关性热力图。
已修复：强制中文字体全局配置，杜绝乱码。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import pandas as pd

# =========================================================================
# 必须第一步：导入 matplotlib 并立即设置中文字体
# =========================================================================
import matplotlib
matplotlib.use("Agg")  # 非交互式后端

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib import font_manager as fm

# ── 强制中文字体配置 ────────────────────────────────────────────────
# 策略：删除 matplotlib 字体缓存 → 注册系统字体文件 → 重建 → 设 rcParams

def _install_chinese_font() -> None:
    """搜索并注册系统中文字体，强制 matplotlib 识别。"""
    import glob
    import shutil

    _font_search_paths = [
        # Windows
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/simsun.ttc",
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]

    _found_font = None

    for _fp in _font_search_paths:
        if os.path.exists(_fp):
            _found_font = _fp
            break

    if not _found_font:
        # 全局搜索
        for _pattern in [
            "C:/Windows/Fonts/*.ttf", "C:/Windows/Fonts/*.ttc",
            "/usr/share/fonts/**/*.ttf", "/usr/share/fonts/**/*.ttc",
        ]:
            for _fp in glob.glob(_pattern):
                try:
                    _prop = fm.FontProperties(fname=_fp)
                    if any(0x4E00 <= ord(c) <= 0x9FFF for c in _prop.get_name()):
                        _found_font = _fp
                        break
                except Exception:
                    pass
            if _found_font:
                break

    if _found_font:
        try:
            # 获取字体名
            _prop = fm.FontProperties(fname=_found_font)
            _font_name = _prop.get_name()

            # 注册
            fm.fontManager.addfont(_found_font)

            # 强制设为全家默认
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = [_font_name, 'SimHei', 'Microsoft YaHei',
                                                'DejaVu Sans', 'Arial']
        except Exception:
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei',
                                                'DejaVu Sans', 'Arial']
    else:
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei',
                                            'DejaVu Sans', 'Arial']

    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.dpi'] = 150
    plt.rcParams['savefig.dpi'] = 150
    plt.rcParams['savefig.bbox'] = 'tight'
    plt.rcParams['savefig.pad_inches'] = 0.1

# =========================================================================
# seaborn
# =========================================================================
import seaborn as sns
sns.set_style("whitegrid")
sns.set_context("notebook", font_scale=1.1)

# seaborn 会覆盖 rcParams，必须在 seaborn 之后再次设置字体
_install_chinese_font()

logger = logging.getLogger(__name__)


class ChartGenerator:
    """图表生成器：柱状图、箱线图、散点图、相关性热力图。"""

    def __init__(
        self,
        df: pd.DataFrame,
        *,
        output_dir: Union[str, Path] = "./outputs/charts",
    ) -> None:
        self.df = df
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ==================================================================
    # 公开 API
    # ==================================================================

    def generate_all(self) -> list[str]:
        saved: list[str] = []
        for method in [self.bar_chart, self.box_plot,
                       self.scatter_plot, self.correlation_heatmap]:
            try:
                path = method()
                if path:
                    saved.append(str(path))
                    logger.info("图表已保存: %s", path)
            except Exception as e:
                logger.error("生成图表失败 [%s]: %s", method.__name__, e)
        return saved

    # ==================================================================
    # 1. 柱状图
    # ==================================================================

    def bar_chart(self, filename: str = "bar_chart.png") -> Optional[Path]:
        categorical_cols = self._categorical_columns(max_unique=15)
        numeric_cols = self._numeric_columns()
        if not categorical_cols:
            return None

        cat = categorical_cols[0]
        vc = self.df[cat].value_counts().head(20)

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # 左：频数柱状图
        ax1 = axes[0]
        colors = sns.color_palette("Set2", len(vc))
        bars = ax1.bar(range(len(vc)), vc.values, color=colors)
        ax1.set_xticks(range(len(vc)))
        ax1.set_xticklabels(vc.index.astype(str), rotation=30, ha="right", fontsize=8)
        ax1.set_title(f"{cat} 频数分布", fontweight="bold")
        ax1.set_ylabel("频数")
        for bar, val in zip(bars, vc.values):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                     str(val), ha="center", va="bottom", fontsize=7)

        # 右：按分类的数值均值柱状图
        ax2 = axes[1]
        if numeric_cols:
            num = numeric_cols[0]
            grouped = self.df.groupby(cat)[num].mean().sort_values(ascending=False).head(20)
            bars = ax2.bar(range(len(grouped)), grouped.values,
                           color=sns.color_palette("Blues_d", len(grouped)))
            ax2.set_xticks(range(len(grouped)))
            ax2.set_xticklabels(grouped.index.astype(str), rotation=30, ha="right", fontsize=8)
            ax2.set_title(f"{cat} 分组 - {num} 均值", fontweight="bold")
            ax2.set_ylabel(num)
            for bar, val in zip(bars, grouped.values):
                ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                         f"{val:.2f}", ha="center", va="bottom", fontsize=7)
        else:
            ax2.text(0.5, 0.5, "无数值列", transform=ax2.transAxes,
                     ha="center", va="center", fontsize=12, color="gray")
            ax2.set_title("无数据")

        fig.suptitle(f"柱状图 — {cat}", fontsize=14, fontweight="bold", y=1.02)
        plt.tight_layout()
        path = self._save_fig(fig, filename)
        plt.close(fig)
        return path

    # ==================================================================
    # 2. 箱线图
    # ==================================================================

    def box_plot(self, filename: str = "box_plot.png") -> Optional[Path]:
        numeric_cols = self._numeric_columns()
        if not numeric_cols:
            return None

        categorical_cols = self._categorical_columns(min_unique=2, max_unique=8)
        n_num = min(len(numeric_cols), 4)
        selected_num = numeric_cols[:n_num]
        n_cat = len(categorical_cols)

        if n_cat >= 1:
            cat = categorical_cols[0]
            nrows = (n_num + 1) // 2
            ncols = 2 if n_num > 1 else 1
            fig, axes = plt.subplots(nrows, ncols, figsize=(12, 5 * nrows))
            if n_num == 1:
                axes = np.array([axes])
            axes_flat = axes.flatten()
            for i, num in enumerate(selected_num):
                ax = axes_flat[i]
                order = self.df.groupby(cat)[num].median().sort_values().index.tolist()
                sns.boxplot(data=self.df, x=cat, y=num, order=order, ax=ax,
                            palette="Set3", showfliers=True, fliersize=3)
                ax.set_title(f"{num} 按 {cat} 分组", fontweight="bold")
                ax.tick_params(axis="x", rotation=30, labelsize=8)
                ax.set_xlabel("")
            for j in range(n_num, len(axes_flat)):
                axes_flat[j].set_visible(False)
        else:
            fig, ax = plt.subplots(figsize=(8, 5))
            melted = self.df[selected_num].melt(var_name="变量", value_name="值")
            sns.boxplot(data=melted, x="变量", y="值", ax=ax, palette="Set3",
                        showfliers=True, fliersize=3)
            ax.set_title("数值列箱线图", fontweight="bold")
            ax.tick_params(axis="x", rotation=30, labelsize=9)

        plt.tight_layout()
        path = self._save_fig(fig, filename)
        plt.close(fig)
        return path

    # ==================================================================
    # 3. 散点图
    # ==================================================================

    def scatter_plot(self, filename: str = "scatter_plot.png") -> Optional[Path]:
        numeric_cols = self._numeric_columns()
        if len(numeric_cols) < 2:
            return None

        x_col, y_col = numeric_cols[0], numeric_cols[1]
        categorical_cols = self._categorical_columns(min_unique=2, max_unique=10)

        fig, ax = plt.subplots(figsize=(8, 6))
        if categorical_cols:
            hue_col = categorical_cols[0]
            plot_data = self.df[[x_col, y_col, hue_col]].dropna()
            sns.scatterplot(data=plot_data, x=x_col, y=y_col, hue=hue_col,
                            ax=ax, alpha=0.7, palette="Set2",
                            edgecolor="k", linewidth=0.3)
            ax.legend(title=hue_col, fontsize=8, title_fontsize=9, loc="best")
        else:
            sns.regplot(data=self.df, x=x_col, y=y_col, ax=ax,
                        scatter_kws={"alpha": 0.6, "edgecolor": "k", "linewidth": 0.3},
                        line_kws={"color": "red", "linewidth": 1.5})

        corr = self.df[[x_col, y_col]].corr().iloc[0, 1]
        ax.set_title(f"{y_col} vs {x_col}", fontweight="bold", fontsize=12)
        ax.text(0.97, 0.03, f"Pearson r = {corr:.4f}", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=10,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        plt.tight_layout()
        path = self._save_fig(fig, filename)
        plt.close(fig)
        return path

    # ==================================================================
    # 4. 相关性热力图
    # ==================================================================

    def correlation_heatmap(self, filename: str = "correlation_heatmap.png") -> Optional[Path]:
        numeric_cols = self._numeric_columns()
        if len(numeric_cols) < 2:
            return None

        corr_matrix = self.df[numeric_cols].corr()
        n = len(numeric_cols)
        figsize = max(8, n * 0.9), max(6, n * 0.8)

        fig, ax = plt.subplots(figsize=figsize)
        mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
        cmap = sns.diverging_palette(250, 15, s=75, l=40, n=12, center="light")

        sns.heatmap(
            corr_matrix, mask=mask, annot=True, fmt=".2f", cmap=cmap,
            center=0, vmin=-1, vmax=1, square=True, linewidths=0.5,
            cbar_kws={"shrink": 0.8, "label": "Pearson r"}, ax=ax,
        )
        ax.set_title("相关性热力图", fontweight="bold", fontsize=14, pad=12)
        ax.tick_params(axis="both", labelsize=8, rotation=45)
        plt.tight_layout()
        path = self._save_fig(fig, filename)
        plt.close(fig)
        return path

    # ==================================================================
    # 工具
    # ==================================================================

    def _numeric_columns(self, min_unique: int = 2) -> list[str]:
        return [
            c for c in self.df.columns
            if pd.api.types.is_numeric_dtype(self.df[c])
            and self.df[c].dropna().nunique() >= min_unique
        ]

    def _categorical_columns(self, min_unique: int = 2, max_unique: int = 20) -> list[str]:
        cats = []
        for c in self.df.columns:
            if pd.api.types.is_numeric_dtype(self.df[c]):
                n_u = self.df[c].dropna().nunique()
                if min_unique <= n_u <= max_unique and n_u < len(self.df) * 0.1:
                    cats.append(c)
                continue
            n_u = self.df[c].dropna().nunique()
            if min_unique <= n_u <= max_unique:
                cats.append(c)
        return cats

    def _save_fig(self, fig: plt.Figure, filename: str) -> Path:
        path = self.output_dir / filename
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        return path


# ------------------------------------------------------------------
# 便捷函数
# ------------------------------------------------------------------

def generate_charts(
    df: pd.DataFrame,
    output_dir: Union[str, Path] = "./outputs/charts",
) -> list[str]:
    """一行调用：生成全部图表。"""
    return ChartGenerator(df, output_dir=output_dir).generate_all()


# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    import sys
    if len(sys.argv) < 2:
        print("用法：python chart_generator.py <file_path>")
        sys.exit(1)
    from data_loader import load_and_clean
    df = load_and_clean(sys.argv[1])
    paths = generate_charts(df)
    print("\n生成的图表：")
    for p in paths:
        print(f"  {p}")
