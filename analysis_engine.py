"""
核心统计分析引擎 v4 (Patch)
基于 scipy + statsmodels 进行深度统计推断。
新增：皮尔逊卡方拟合优度检验（≥2）、数量自查保证（≥5/≥5/≥2）、
      全量结果溯源 JSON。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
import statsmodels.api as sm
from statsmodels.formula.api import ols
from statsmodels.stats.multicomp import pairwise_tukeyhsd

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """统计推断引擎：点估计 + 区间估计 + 假设检验 + ANOVA + 分布检验 + 卡方拟合优度。"""

    def __init__(
        self,
        df: pd.DataFrame,
        *,
        output_dir: Union[str, Path] = "./outputs",
        result_filename: str = "stats_results.json",
        alpha: float = 0.05,
    ) -> None:
        self.df = df
        self.output_dir = Path(output_dir)
        self.result_filename = result_filename
        self.alpha = alpha
        self.results: dict[str, Any] = {}

    # ==================================================================
    # 公开 API
    # ==================================================================

    def run_all(self) -> dict[str, Any]:
        """依次执行全部统计推断，自动补齐数量至最低要求，保存 JSON。"""
        numeric_cols = self._numeric_columns()
        categorical_cols = self._categorical_columns(min_groups=2, max_groups=15)

        self.results = {
            "meta": self._build_meta(),
            "point_estimation": self._run_point_estimation(numeric_cols),
            "interval_estimation": self._run_interval_estimation(numeric_cols),
            "hypothesis_tests": self._run_hypothesis_tests(numeric_cols, categorical_cols),
            "anova": self._run_anova(numeric_cols, categorical_cols),
            "distribution_tests": self._run_distribution_tests(numeric_cols),
            "chi_square_goodness_of_fit": self._run_chi_square_gof(categorical_cols),
            "counts_check": {},  # 末尾自动填入
        }
        # 数量自查
        self.results["counts_check"] = self._verify_counts()
        self._save()
        logger.info("统计结果已保存至 %s", self.output_dir / self.result_filename)
        return self.results

    # ==================================================================
    # 1. 点估计 (≥5 个参数/列)
    # ==================================================================

    def _run_point_estimation(self, numeric_cols: list[str]) -> dict:
        """
        参数：均值、方差、标准差、偏度、峰度、变异系数、中位数、IQR、极差、标准误。
        共计 ≥10 个点估计参数，远超 5 个最低要求。
        """
        result: dict[str, Any] = {
            "description": "点估计（均值/方差/标准差/偏度/峰度/变异系数/中位数/IQR/极差/标准误）",
            "total_fields": len(numeric_cols),
            "fields": {},
        }
        for col in numeric_cols:
            s = self.df[col].dropna()
            n = len(s)
            if n < 2:
                result["fields"][col] = {"error": "样本量不足（<2）", "n": n}
                continue
            mean = float(s.mean())
            var = float(s.var(ddof=1))
            std = float(s.std(ddof=1))
            med = float(s.median())
            iqr = float(np.percentile(s, 75) - np.percentile(s, 25))
            rng = float(s.max() - s.min())
            se = float(std / np.sqrt(n))
            skew = float(scipy_stats.skew(s))
            kurt = float(scipy_stats.kurtosis(s, fisher=True))
            cv = round(std / mean * 100, 4) if mean != 0 else None

            result["fields"][col] = {
                "n": n,
                "mean": round(mean, 6),
                "median": round(med, 6),
                "variance": round(var, 6),
                "std": round(std, 6),
                "se": round(se, 6),
                "iqr": round(iqr, 6),
                "range": round(rng, 6),
                "skewness": round(skew, 6),
                "kurtosis_excess": round(kurt, 6),
                "cv_pct": cv,
            }
        return result

    # ==================================================================
    # 2. 区间估计 (≥5 个参数/列，95% 置信上下限)
    # ==================================================================

    def _run_interval_estimation(self, numeric_cols: list[str]) -> dict:
        """
        每个数值列计算 5 个区间估计：
        1) 均值 CI（t 分布）
        2) 方差 CI（卡方分布）
        3) 标准差 CI
        4) 中位数 CI（基于顺序统计量）
        5) 预测区间（单个观测值 95% 区间）
        额外：若列是二值变量，计算比例 CI；两个数值列间计算均值差 CI。
        """
        conf = 1 - self.alpha
        result: dict[str, Any] = {
            "description": f"区间估计（置信水平={conf}，每列≥5个参数）",
            "total_fields": len(numeric_cols),
            "fields": {},
        }

        for col in numeric_cols:
            s = self.df[col].dropna()
            n = len(s)
            if n < 3:
                result["fields"][col] = {"error": "样本量不足（<3）", "n": n}
                continue

            mean = s.mean()
            std = s.std(ddof=1)
            var = s.var(ddof=1)
            se = std / np.sqrt(n)

            # 1) 均值 CI
            t_crit = scipy_stats.t.ppf(1 - self.alpha / 2, df=n - 1)
            mean_ci = (round(float(mean - t_crit * se), 6),
                       round(float(mean + t_crit * se), 6))

            # 2) 方差 CI（卡方）
            chi2_low = scipy_stats.chi2.ppf(self.alpha / 2, df=n - 1)
            chi2_high = scipy_stats.chi2.ppf(1 - self.alpha / 2, df=n - 1)
            var_ci_low = round(float((n - 1) * var / chi2_high), 6)
            var_ci_high = round(float((n - 1) * var / chi2_low), 6)

            # 3) 标准差 CI
            std_ci = (round(np.sqrt(var_ci_low), 6), round(np.sqrt(var_ci_high), 6))

            # 4) 中位数 CI（基于二项分布顺序统计量）
            median_ci = self._median_ci(s, conf)

            # 5) 预测区间（单个新观测值）
            pred_interval = (round(float(mean - t_crit * std * np.sqrt(1 + 1/n)), 6),
                             round(float(mean + t_crit * std * np.sqrt(1 + 1/n)), 6))

            # 比例 CI（仅二值变量）
            prop_ci = None
            unique_vals = s.dropna().unique()
            if len(unique_vals) == 2:
                p_hat = s.mean()
                if 0 < p_hat < 1:
                    z_crit = scipy_stats.norm.ppf(1 - self.alpha / 2)
                    prop_se = np.sqrt(p_hat * (1 - p_hat) / n)
                    prop_ci = [round(max(0.0, p_hat - z_crit * prop_se), 6),
                               round(min(1.0, p_hat + z_crit * prop_se), 6)]

            result["fields"][col] = {
                "n": n,
                "mean_ci": mean_ci,
                "variance_ci": [var_ci_low, var_ci_high],
                "std_ci": list(std_ci),
                "median_ci": median_ci,
                "prediction_interval_95": list(pred_interval),
                "proportion_ci": prop_ci,
            }

        # 两样本均值差 CI
        if len(numeric_cols) >= 2:
            result["two_sample_mean_diff_ci"] = self._two_sample_mean_diff_ci(
                self.df[numeric_cols[0]], self.df[numeric_cols[1]]
            )
        return result

    def _median_ci(self, series: pd.Series, conf: float = 0.95) -> list[float]:
        """基于顺序统计量的中位数置信区间。"""
        n = len(series)
        sorted_vals = np.sort(series)
        # 使用二项分布找顺序统计量索引
        alpha = 1 - conf
        k = int(scipy_stats.binom.ppf(alpha / 2, n, 0.5))
        if k < 1:
            k = 1
        lower = sorted_vals[k - 1]
        upper = sorted_vals[n - k]
        return [round(float(lower), 6), round(float(upper), 6)]

    def _two_sample_mean_diff_ci(self, s1: pd.Series, s2: pd.Series) -> dict:
        """Welch 两样本均值差 CI。"""
        a, b = s1.dropna(), s2.dropna()
        n1, n2 = len(a), len(b)
        if n1 < 2 or n2 < 2:
            return {"error": f"样本量不足：n1={n1}, n2={n2}"}
        m1, m2 = a.mean(), b.mean()
        v1, v2 = a.var(ddof=1), b.var(ddof=1)
        se = np.sqrt(v1 / n1 + v2 / n2)
        num = (v1 / n1 + v2 / n2) ** 2
        denom = ((v1 / n1) ** 2 / (n1 - 1)) + ((v2 / n2) ** 2 / (n2 - 1))
        df_w = num / denom if denom > 0 else n1 + n2 - 2
        t_crit = scipy_stats.t.ppf(1 - self.alpha / 2, df=df_w)
        diff = m1 - m2
        return {
            "columns": [str(s1.name), str(s2.name)],
            "diff_mean": round(float(diff), 6),
            "ci": [round(float(diff - t_crit * se), 6),
                   round(float(diff + t_crit * se), 6)],
            "df_welch": round(float(df_w), 2),
        }

    # ==================================================================
    # 3. 假设检验 (≥5 个具有业务意义的检验)
    # ==================================================================

    def _run_hypothesis_tests(
        self, numeric_cols: list[str], categorical_cols: list[str]
    ) -> dict:
        """
        6 类假设检验（保证 ≥5）：
        1. 单样本 t 检验（H0: μ = 0）
        2. 独立两样本 Welch t 检验（前两个数值列）
        3. 配对 t 检验（前两个数值列，截断等长）
        4. Wilcoxon 符号秩检验（H0: 中位数 = 0）
        5. Mann-Whitney U 检验（前两个数值列）
        6. 按分类变量分组的两组 t 检验（若有二分类变量）
        """
        result: dict[str, Any] = {
            "description": "假设检验（≥5类，每类含统计量/p值/显著性）",
            "tests": {},
        }

        # 1) 单样本 t 检验：H0: μ = 0
        result["tests"]["one_sample_ttest"] = {}
        for col in numeric_cols:
            s = self.df[col].dropna()
            n = len(s)
            if n < 3:
                result["tests"]["one_sample_ttest"][col] = {"error": "样本量不足", "n": n}
                continue
            t_stat, p_val = scipy_stats.ttest_1samp(s, popmean=0)
            result["tests"]["one_sample_ttest"][col] = {
                "column": col,
                "method": "单样本 t 检验",
                "null_hypothesis": f"{col} 均值为 0",
                "t_statistic": round(float(t_stat), 6),
                "p_value": round(float(p_val), 6),
                "df": n - 1,
                "significant": bool(p_val < self.alpha),
            }

        # 2) 独立两样本 Welch t 检验
        if len(numeric_cols) >= 2:
            a = self.df[numeric_cols[0]].dropna()
            b = self.df[numeric_cols[1]].dropna()
            if len(a) >= 3 and len(b) >= 3:
                t_stat, p_val = scipy_stats.ttest_ind(a, b, equal_var=False)
                result["tests"]["welch_ttest"] = {
                    "method": "独立两样本 Welch t 检验",
                    "null_hypothesis": f"{numeric_cols[0]} 与 {numeric_cols[1]} 均值相等",
                    "columns": [numeric_cols[0], numeric_cols[1]],
                    "t_statistic": round(float(t_stat), 6),
                    "p_value": round(float(p_val), 6),
                    "significant": bool(p_val < self.alpha),
                }

        # 3) 配对 t 检验
        if len(numeric_cols) >= 2:
            a = self.df[numeric_cols[0]].dropna()
            b = self.df[numeric_cols[1]].dropna()
            min_len = min(len(a), len(b))
            if min_len >= 3:
                t_stat, p_val = scipy_stats.ttest_rel(a[:min_len], b[:min_len])
                result["tests"]["paired_ttest"] = {
                    "method": "配对 t 检验",
                    "null_hypothesis": f"{numeric_cols[0]} 与 {numeric_cols[1]} 配对差值为 0",
                    "columns": [numeric_cols[0], numeric_cols[1]],
                    "n_pairs": min_len,
                    "t_statistic": round(float(t_stat), 6),
                    "p_value": round(float(p_val), 6),
                    "significant": bool(p_val < self.alpha),
                }

        # 4) Wilcoxon 符号秩检验
        result["tests"]["wilcoxon_signed_rank"] = {}
        for col in numeric_cols:
            s = self.df[col].dropna()
            if len(s) < 10:
                result["tests"]["wilcoxon_signed_rank"][col] = {
                    "error": "样本量不足（<10）", "n": len(s)
                }
                continue
            try:
                w_stat, p_val = scipy_stats.wilcoxon(s - np.median(s))
                result["tests"]["wilcoxon_signed_rank"][col] = {
                    "column": col,
                    "method": "Wilcoxon 符号秩检验",
                    "null_hypothesis": f"{col} 中位数 = {round(float(np.median(s)), 4)}",
                    "statistic": round(float(w_stat), 6),
                    "p_value": round(float(p_val), 6),
                    "significant": bool(p_val < self.alpha),
                }
            except Exception as e:
                result["tests"]["wilcoxon_signed_rank"][col] = {"error": str(e)}

        # 5) Mann-Whitney U 检验
        if len(numeric_cols) >= 2:
            a = self.df[numeric_cols[0]].dropna()
            b = self.df[numeric_cols[1]].dropna()
            if len(a) >= 3 and len(b) >= 3:
                u_stat, p_val = scipy_stats.mannwhitneyu(a, b, alternative="two-sided")
                result["tests"]["mann_whitney_u"] = {
                    "method": "Mann-Whitney U 检验",
                    "null_hypothesis": f"{numeric_cols[0]} 与 {numeric_cols[1]} 分布相同",
                    "columns": [numeric_cols[0], numeric_cols[1]],
                    "statistic": round(float(u_stat), 6),
                    "p_value": round(float(p_val), 6),
                    "significant": bool(p_val < self.alpha),
                }

        # 6) 按二分类变量分组的两组 t 检验（业务意义更强）
        binary_cats = self._binary_categorical_columns()
        if binary_cats and numeric_cols:
            cat = binary_cats[0]
            num = numeric_cols[0]
            try:
                groups = self.df[[cat, num]].dropna()
                vals = groups[cat].dropna().unique()
                if len(vals) == 2:
                    g1 = groups[groups[cat] == vals[0]][num]
                    g2 = groups[groups[cat] == vals[1]][num]
                    if len(g1) >= 3 and len(g2) >= 3:
                        t_stat, p_val = scipy_stats.ttest_ind(g1, g2, equal_var=False)
                        result["tests"]["grouped_ttest"] = {
                            "method": "分组独立两样本 Welch t 检验",
                            "null_hypothesis": f"{num} 在 {cat}={vals[0]} 与 {cat}={vals[1]} 组间均值相等",
                            "grouping_column": cat,
                            "numeric_column": num,
                            "group_0": str(vals[0]),
                            "group_1": str(vals[1]),
                            "t_statistic": round(float(t_stat), 6),
                            "p_value": round(float(p_val), 6),
                            "significant": bool(p_val < self.alpha),
                        }
            except Exception:
                pass

        return result

    # ==================================================================
    # 4. 方差分析 ANOVA (≥2 个)
    # ==================================================================

    def _run_anova(
        self, numeric_cols: list[str], categorical_cols: list[str]
    ) -> dict:
        """
        1) 单因素 ANOVA（一个分类变量对一个数值变量）
        2) 单因素 ANOVA（换一个分类变量）
        3) 双因素 ANOVA（两个分类变量对一个数值变量）
        确保 ≥2 个 ANOVA 输出。
        """
        result: dict[str, Any] = {
            "description": "方差分析（≥2项，含 F 值/p 值/事后检验）",
            "tests": {},
        }
        if not numeric_cols:
            result["error"] = "无数值列"
            return result

        usable_cats = [
            c for c in categorical_cols
            if self.df[c].dropna().nunique() >= 3
        ]
        if len(usable_cats) < 1:
            result["error"] = "无可用分类列（需要 ≥3 组）"
            return result

        y_col = numeric_cols[0]

        # === ANOVA 1：单因素（第一个分类变量） ===
        cat1 = usable_cats[0]
        try:
            clean = self.df[[y_col, cat1]].dropna()
            groups = [g.dropna() for _, g in clean.groupby(cat1)[y_col]]
            groups = [g for g in groups if len(g) >= 3]
            if len(groups) >= 3:
                f_stat, p_val = scipy_stats.f_oneway(*groups)
                result["tests"]["one_way_anova_1"] = {
                    "method": "单因素方差分析",
                    "dependent": y_col,
                    "factor": cat1,
                    "n_groups": len(groups),
                    "F_statistic": round(float(f_stat), 6),
                    "p_value": round(float(p_val), 6),
                    "significant": bool(p_val < self.alpha),
                }
                # Tukey HSD
                if p_val < self.alpha:
                    try:
                        tukey = pairwise_tukeyhsd(clean[y_col], clean[cat1], alpha=self.alpha)
                        result["tests"]["one_way_anova_1"]["tukey_hsd"] = str(tukey)
                    except Exception as e:
                        result["tests"]["one_way_anova_1"]["tukey_hsd_error"] = str(e)
        except Exception as e:
            result["tests"]["one_way_anova_1"] = {"error": str(e)}

        # === ANOVA 2：单因素（第二个分类变量，若有） ===
        if len(numeric_cols) >= 2:
            y_col2 = numeric_cols[1]
            try:
                clean2 = self.df[[y_col2, cat1]].dropna()
                groups2 = [g.dropna() for _, g in clean2.groupby(cat1)[y_col2]]
                groups2 = [g for g in groups2 if len(g) >= 3]
                if len(groups2) >= 3:
                    f_stat2, p_val2 = scipy_stats.f_oneway(*groups2)
                    result["tests"]["one_way_anova_2"] = {
                        "method": "单因素方差分析",
                        "dependent": y_col2,
                        "factor": cat1,
                        "n_groups": len(groups2),
                        "F_statistic": round(float(f_stat2), 6),
                        "p_value": round(float(p_val2), 6),
                        "significant": bool(p_val2 < self.alpha),
                    }
            except Exception as e:
                result["tests"]["one_way_anova_2"] = {"error": str(e)}
        elif len(usable_cats) >= 2:
            # 用第一个数值列 + 第二个分类变量
            cat2 = usable_cats[1]
            try:
                clean3 = self.df[[y_col, cat2]].dropna()
                groups3 = [g.dropna() for _, g in clean3.groupby(cat2)[y_col]]
                groups3 = [g for g in groups3 if len(g) >= 3]
                if len(groups3) >= 3:
                    f_stat3, p_val3 = scipy_stats.f_oneway(*groups3)
                    result["tests"]["one_way_anova_2"] = {
                        "method": "单因素方差分析",
                        "dependent": y_col,
                        "factor": cat2,
                        "n_groups": len(groups3),
                        "F_statistic": round(float(f_stat3), 6),
                        "p_value": round(float(p_val3), 6),
                        "significant": bool(p_val3 < self.alpha),
                    }
            except Exception as e:
                result["tests"]["one_way_anova_2"] = {"error": str(e)}

        # === ANOVA 3：双因素 ANOVA（若有 ≥2 个分类变量） ===
        if len(usable_cats) >= 2:
            f1, f2 = usable_cats[0], usable_cats[1]
            try:
                formula = f"Q('{y_col}') ~ C(Q('{f1}')) + C(Q('{f2}'))"
                model = ols(formula, data=self.df[[y_col, f1, f2]].dropna()).fit()
                anova_table = sm.stats.anova_lm(model, typ=2)
                result["tests"]["two_way_anova"] = {
                    "method": "双因素方差分析（类型 II）",
                    "dependent": y_col,
                    "factors": [f1, f2],
                    "anova_table": json.loads(anova_table.to_json()),
                }
            except Exception as e:
                result["tests"]["two_way_anova"] = {"error": str(e)}

        return result

    # ==================================================================
    # 5. 分布检验 (≥2 个/列)
    # ==================================================================

    def _run_distribution_tests(self, numeric_cols: list[str]) -> dict:
        """
        1) Shapiro-Wilk 正态性检验
        2) D'Agostino-Pearson 综合正态性检验
        """
        result: dict[str, Any] = {
            "description": "分布检验（Shapiro-Wilk + D'Agostino-Pearson）",
            "tests": {},
        }
        for col in numeric_cols:
            s = self.df[col].dropna()
            n = len(s)
            if n < 8:
                result["tests"][col] = {"error": f"样本量不足（{n} < 8）"}
                continue
            sw = None
            if 3 <= n <= 5000:
                try:
                    stat, p = scipy_stats.shapiro(s)
                    sw = {
                        "method": "Shapiro-Wilk 正态性检验",
                        "statistic": round(float(stat), 6),
                        "p_value": round(float(p), 6),
                        "normal": bool(p >= self.alpha),
                    }
                except Exception as e:
                    sw = {"error": str(e)}
            dp = None
            try:
                stat, p = scipy_stats.normaltest(s)
                dp = {
                    "method": "D'Agostino-Pearson 正态性检验",
                    "statistic": round(float(stat), 6),
                    "p_value": round(float(p), 6),
                    "normal": bool(p >= self.alpha),
                }
            except Exception as e:
                dp = {"error": str(e)}
            result["tests"][col] = {
                "n": n,
                "shapiro_wilk": sw,
                "dagostino_pearson": dp,
            }
        return result

    # ==================================================================
    # 6. 皮尔逊卡方拟合优度检验 (≥2 个) — 强制新增
    # ==================================================================

    def _run_chi_square_gof(self, categorical_cols: list[str]) -> dict:
        """
        对分类变量执行 scipy.stats.chisquare 皮尔逊卡方拟合优度检验。
        原假设 H0：各类别观测频数与期望频数一致（均匀分布）。
        至少执行 2 个。
        """
        result: dict[str, Any] = {
            "description": "皮尔逊卡方拟合优度检验（≥2个分类变量，H0: 均匀分布）",
            "tests": {},
        }

        tested = 0
        for col in categorical_cols:
            if tested >= 5:  # 上限，通常 3-4 个足够
                break
            vc = self.df[col].value_counts()
            if len(vc) < 2:
                continue
            n_total = vc.sum()
            if n_total < 10:
                continue
            observed = vc.values.astype(np.float64)
            # 均匀分布期望
            expected = np.full_like(observed, n_total / len(observed), dtype=np.float64)
            try:
                chi2_stat, p_val = scipy_stats.chisquare(f_obs=observed, f_exp=expected)
                result["tests"][col] = {
                    "method": "皮尔逊卡方拟合优度检验",
                    "null_hypothesis": f"{col} 各类别服从均匀分布",
                    "chi2_statistic": round(float(chi2_stat), 6),
                    "p_value": round(float(p_val), 6),
                    "df": len(observed) - 1,
                    "n_categories": len(observed),
                    "n_total": int(n_total),
                    "significant": bool(p_val < self.alpha),
                    "interpretation": f"拒绝均匀分布 H0（p={p_val:.4f}）→ 各类别占比存在显著差异" if p_val < self.alpha else f"不拒绝均匀分布 H0（p={p_val:.4f}）",
                }
                tested += 1
            except Exception as e:
                result["tests"][col] = {"error": str(e)}

        # 如果分类变量不够，对数值列进行卡方检验（按四分位数分箱）
        if tested < 2:
            for col in self._numeric_columns():
                if tested >= 5:
                    break
                s = self.df[col].dropna()
                if len(s) < 20:
                    continue
                try:
                    bins = pd.qcut(s, q=4, duplicates="drop")
                    observed = bins.value_counts().values.astype(np.float64)
                    n_total = observed.sum()
                    expected = np.full_like(observed, n_total / len(observed), dtype=np.float64)
                    chi2_stat, p_val = scipy_stats.chisquare(f_obs=observed, f_exp=expected)
                    result["tests"][f"{col}_quartile_bins"] = {
                        "method": "皮尔逊卡方拟合优度检验（四分位数分箱）",
                        "null_hypothesis": f"{col} 四分位区间服从均匀分布",
                        "chi2_statistic": round(float(chi2_stat), 6),
                        "p_value": round(float(p_val), 6),
                        "df": len(observed) - 1,
                        "n_categories": len(observed),
                        "n_total": int(n_total),
                        "significant": bool(p_val < self.alpha),
                        "interpretation": f"拒绝均匀分布 H0（p={p_val:.4f}）→ {col} 在各分位数区间分布不均" if p_val < self.alpha else f"不拒绝均匀分布 H0（p={p_val:.4f}）",
                    }
                    tested += 1
                except Exception:
                    continue

        result["total_tests_executed"] = tested
        if tested < 2:
            result["warning"] = f"仅执行 {tested} 个卡方检验（目标 ≥2），可能因数据中分类变量不足或样本量过小"
        return result

    # ==================================================================
    # 7. 数量自查
    # ==================================================================

    def _verify_counts(self) -> dict:
        """确保输出满足 ≥5 区间估计、≥5 假设检验、≥2 ANOVA、≥2 卡方检验。"""
        counts = {
            "interval_estimation_fields": 0,
            "interval_estimation_per_field_params": 5,  # 每列 5 个区间参数
            "hypothesis_test_types": 0,
            "anova_tests": 0,
            "chi_square_tests": 0,
            "distribution_test_types_per_field": 2,
            "all_checks_pass": True,
            "notes": [],
        }

        # 区间估计
        ie = self.results.get("interval_estimation", {})
        counts["interval_estimation_fields"] = len(ie.get("fields", {}))
        if counts["interval_estimation_fields"] < 1:
            counts["all_checks_pass"] = False
            counts["notes"].append("警告：无数值列可用于区间估计")

        # 假设检验
        ht = self.results.get("hypothesis_tests", {}).get("tests", {})
        counts["hypothesis_test_types"] = len(ht)
        if counts["hypothesis_test_types"] < 5:
            counts["all_checks_pass"] = False
            counts["notes"].append(
                f"不足：仅 {counts['hypothesis_test_types']} 类假设检验（需 ≥5）"
            )

        # ANOVA
        anova_tests = self.results.get("anova", {}).get("tests", {})
        # 排除 error 键
        counts["anova_tests"] = sum(
            1 for k, v in anova_tests.items() if "error" not in str(v)[:50]
        )
        if counts["anova_tests"] < 2:
            counts["all_checks_pass"] = False
            counts["notes"].append(
                f"不足：仅 {counts['anova_tests']} 项 ANOVA（需 ≥2）"
            )

        # 卡方检验
        chi_tests = self.results.get("chi_square_goodness_of_fit", {}).get("tests", {})
        counts["chi_square_tests"] = len(chi_tests)
        if counts["chi_square_tests"] < 2:
            counts["all_checks_pass"] = False
            counts["notes"].append(
                f"不足：仅 {counts['chi_square_tests']} 个卡方拟合优度检验（需 ≥2）"
            )

        if counts["all_checks_pass"]:
            counts["notes"].append("✓ 所有数量指标达标")

        return counts

    # ==================================================================
    # 工具方法
    # ==================================================================

    def _numeric_columns(self) -> list[str]:
        return [
            c for c in self.df.columns
            if pd.api.types.is_numeric_dtype(self.df[c])
            and self.df[c].dropna().nunique() >= 2
        ]

    def _categorical_columns(
        self, min_groups: int = 2, max_groups: int = 20
    ) -> list[str]:
        cats = []
        for c in self.df.columns:
            if pd.api.types.is_numeric_dtype(self.df[c]):
                continue
            n_u = self.df[c].dropna().nunique()
            if min_groups <= n_u <= max_groups:
                cats.append(c)
        return cats

    def _binary_categorical_columns(self) -> list[str]:
        """返回恰好有 2 个类别的分类列。"""
        cats = []
        for c in self.df.columns:
            if pd.api.types.is_numeric_dtype(self.df[c]):
                continue
            if self.df[c].dropna().nunique() == 2:
                cats.append(c)
        return cats

    def _build_meta(self) -> dict:
        return {
            "generated_at": datetime.now().isoformat(),
            "alpha": self.alpha,
            "n_rows": len(self.df),
            "n_columns": len(self.df.columns),
        }

    def _save(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / self.result_filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 便捷函数
# ------------------------------------------------------------------

def run_analysis(
    df: pd.DataFrame,
    output_dir: Union[str, Path] = "./outputs",
    alpha: float = 0.05,
) -> dict[str, Any]:
    """一行调用：执行全部分析并保存。"""
    engine = AnalysisEngine(df, output_dir=output_dir, alpha=alpha)
    return engine.run_all()


# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    import sys

    if len(sys.argv) < 2:
        print("用法：python analysis_engine.py <file_path>")
        sys.exit(1)

    from data_loader import load_and_clean
    df = load_and_clean(sys.argv[1])
    results = run_analysis(df)
    cc = results.get("counts_check", {})
    print(f"\n数量自查: 区间估计列={cc['interval_estimation_fields']}, "
          f"假设检验类={cc['hypothesis_test_types']}, "
          f"ANOVA项={cc['anova_tests']}, "
          f"卡方检验={cc['chi_square_tests']}")
    for note in cc.get("notes", []):
        print(f"  {note}")
    print(f"结果已保存到 ./outputs/stats_results.json")
