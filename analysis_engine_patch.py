# -*- coding: utf-8 -*-
"""
@File    : analysis_engine_patch.py
@Author  : Robusr
@Date    : 2026/6/10 16:07
@Description: 统计引擎扩展补丁
@Software: PyCharm
"""

# analysis_engine_patch.py
"""
统计引擎扩展补丁
在原AnalysisEngine基础上增加按需执行指定任务的能力
"""
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from analysis_engine import AnalysisEngine as OriginalAnalysisEngine


class AnalysisEngine(OriginalAnalysisEngine):
    def __init__(self, df: pd.DataFrame, **kwargs):
        super().__init__(df, **kwargs)
        self.column_info = self._build_column_info()

    def run_tasks(self, tasks: list[dict]) -> dict:
        """
        根据任务列表执行指定的统计分析
        :param tasks: task_planner.py生成的可执行任务列表
        :return: 统计结果JSON，格式与原run_all()完全一致
        """
        self.results = {
            "meta": self._build_meta(),
            "tasks_executed": tasks,
            "point_estimation": {"fields": {}, "description": "点估计"},
            "interval_estimation": {"fields": {}, "description": "区间估计"},
            "hypothesis_tests": {"tests": {}, "description": "假设检验"},
            "anova": {"tests": {}, "description": "方差分析"},
            "distribution_tests": {"tests": {}, "description": "分布检验"},
            "chi_square_goodness_of_fit": {"tests": {}, "description": "卡方拟合优度检验"},
            "correlations": {},
            "counts_check": {}
        }

        # 1. 收集所有涉及的数值列，统一执行点估计和区间估计
        numeric_cols_used = set()
        for task in tasks:
            for var in task["variables"]:
                if self.column_info[var]["inferred_type"].startswith("numeric"):
                    numeric_cols_used.add(var)
        numeric_cols = list(numeric_cols_used)

        if numeric_cols:
            self.results["point_estimation"] = self._run_point_estimation(numeric_cols)
            self.results["interval_estimation"] = self._run_interval_estimation(numeric_cols)

        # 2. 逐个执行任务
        for task in tasks:
            method = task["method"]
            variables = task["variables"]
            task_id = task["task_id"]

            try:
                if method == "t检验":
                    self._execute_t_test(variables[0], variables[1], task_id)
                elif method == "配对t检验":
                    self._execute_paired_t_test(variables[0], variables[1], task_id)
                elif method == "ANOVA":
                    self._execute_anova(variables[0], variables[1], task_id)
                elif method == "卡方检验":
                    self._execute_chi_square(variables[0], variables[1], task_id)
                elif method == "相关性分析":
                    self._execute_correlation(variables[0], variables[1], task_id)
                elif method == "分布检验":
                    self._execute_distribution_test(variables[0], task_id)
            except Exception as e:
                self.results[f"task_{task_id}_error"] = str(e)
                print(f"⚠️  执行任务{task_id}失败: {str(e)}")

        # 3. 执行数量自查（复用原有的_verify_counts方法）
        self.results["counts_check"] = self._verify_counts()

        # 4. 保存结果
        self._save()
        return self.results

    # ------------------------------
    # 各任务的执行方法（复用原有私有方法）
    # ------------------------------
    def _execute_t_test(self, num_col: str, cat_col: str, task_id: int):
        """执行分组独立两样本Welch t检验"""
        groups = self.df[[cat_col, num_col]].dropna()
        vals = groups[cat_col].unique()
        g1 = groups[groups[cat_col] == vals[0]][num_col]
        g2 = groups[groups[cat_col] == vals[1]][num_col]

        t_stat, p_val = scipy_stats.ttest_ind(g1, g2, equal_var=False)
        self.results["hypothesis_tests"]["tests"][f"task_{task_id}_grouped_ttest"] = {
            "method": "分组独立两样本 Welch t 检验",
            "null_hypothesis": f"{num_col} 在 {cat_col}={vals[0]} 与 {cat_col}={vals[1]} 组间均值相等",
            "grouping_column": cat_col,
            "numeric_column": num_col,
            "group_0": str(vals[0]),
            "group_1": str(vals[1]),
            "t_statistic": round(float(t_stat), 6),
            "p_value": round(float(p_val), 6),
            "significant": bool(p_val < self.alpha)
        }

    def _execute_paired_t_test(self, col1: str, col2: str, task_id: int):
        """执行配对t检验"""
        a = self.df[col1].dropna()
        b = self.df[col2].dropna()
        min_len = min(len(a), len(b))

        t_stat, p_val = scipy_stats.ttest_rel(a[:min_len], b[:min_len])
        self.results["hypothesis_tests"]["tests"][f"task_{task_id}_paired_ttest"] = {
            "method": "配对 t 检验",
            "null_hypothesis": f"{col1} 与 {col2} 配对差值为 0",
            "columns": [col1, col2],
            "n_pairs": min_len,
            "t_statistic": round(float(t_stat), 6),
            "p_value": round(float(p_val), 6),
            "significant": bool(p_val < self.alpha)
        }

    def _execute_anova(self, num_col: str, cat_col: str, task_id: int):
        """执行单因素方差分析"""
        clean = self.df[[num_col, cat_col]].dropna()
        groups = [g.dropna() for _, g in clean.groupby(cat_col)[num_col]]
        groups = [g for g in groups if len(g) >= 3]

        f_stat, p_val = scipy_stats.f_oneway(*groups)
        anova_result = {
            "method": "单因素方差分析",
            "dependent": num_col,
            "factor": cat_col,
            "n_groups": len(groups),
            "F_statistic": round(float(f_stat), 6),
            "p_value": round(float(p_val), 6),
            "significant": bool(p_val < self.alpha)
        }

        # 事后检验（Tukey HSD）
        if p_val < self.alpha:
            from statsmodels.stats.multicomp import pairwise_tukeyhsd
            try:
                tukey = pairwise_tukeyhsd(clean[num_col], clean[cat_col], alpha=self.alpha)
                anova_result["tukey_hsd"] = str(tukey)
            except Exception as e:
                anova_result["tukey_hsd_error"] = str(e)

        self.results["anova"]["tests"][f"task_{task_id}_one_way_anova"] = anova_result

    def _execute_chi_square(self, col1: str, col2: str, task_id: int):
        """执行卡方独立性检验"""
        contingency_table = pd.crosstab(self.df[col1], self.df[col2])
        chi2_stat, p_val, dof, expected = scipy_stats.chi2_contingency(contingency_table)

        self.results["hypothesis_tests"]["tests"][f"task_{task_id}_chi_square_independence"] = {
            "method": "皮尔逊卡方独立性检验",
            "null_hypothesis": f"{col1} 与 {col2} 相互独立",
            "variables": [col1, col2],
            "chi2_statistic": round(float(chi2_stat), 6),
            "p_value": round(float(p_val), 6),
            "df": dof,
            "significant": bool(p_val < self.alpha)
        }

    def _execute_correlation(self, col1: str, col2: str, task_id: int):
        """执行皮尔逊相关性分析"""
        corr, p_val = scipy_stats.pearsonr(self.df[col1].dropna(), self.df[col2].dropna())

        self.results["correlations"][f"task_{task_id}_pearson"] = {
            "method": "皮尔逊相关性分析",
            "variables": [col1, col2],
            "correlation_coefficient": round(float(corr), 6),
            "p_value": round(float(p_val), 6),
            "significant": bool(p_val < self.alpha)
        }

    def _execute_distribution_test(self, col: str, task_id: int):
        """执行正态性检验（Shapiro-Wilk + D'Agostino-Pearson）"""
        s = self.df[col].dropna()
        n = len(s)

        result = {"n": n}

        # Shapiro-Wilk检验（3≤n≤5000）
        if 3 <= n <= 5000:
            stat, p = scipy_stats.shapiro(s)
            result["shapiro_wilk"] = {
                "statistic": round(float(stat), 6),
                "p_value": round(float(p), 6),
                "normal": bool(p >= self.alpha)
            }

        # D'Agostino-Pearson检验
        stat, p = scipy_stats.normaltest(s)
        result["dagostino_pearson"] = {
            "statistic": round(float(stat), 6),
            "p_value": round(float(p), 6),
            "normal": bool(p >= self.alpha)
        }

        self.results["distribution_tests"]["tests"][f"task_{task_id}_distribution"] = result

    def _build_column_info(self) -> dict:
        """构建列信息字典，用于任务执行时的类型检查"""
        from data_profiler import DataProfiler
        profiler = DataProfiler(self.df)
        profile = profiler.generate()
        return {f["column"]: f for f in profile["fields"]}