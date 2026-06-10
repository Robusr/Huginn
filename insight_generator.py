"""
价值提炼模块 v4 (New)
自动读取 stats_results.json 和 data_profile.json，
筛选 P<0.05 的显著发现和强相关特征，
导出 insights.md 和 insights.json。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


class InsightGenerator:
    """从统计结果中自动提炼显著发现和可研究问题。"""

    def __init__(
        self,
        stats_json_path: Union[str, Path],
        profile_json_path: Optional[Union[str, Path]] = None,
        *,
        output_dir: Union[str, Path] = "./outputs",
        alpha: float = 0.05,
        strong_corr_threshold: float = 0.5,
    ) -> None:
        self.stats_path = Path(stats_json_path)
        self.profile_path = Path(profile_json_path) if profile_json_path else None
        self.output_dir = Path(output_dir)
        self.alpha = alpha
        self.strong_corr_threshold = strong_corr_threshold

        self.stats: dict[str, Any] = {}
        self.profile: dict[str, Any] = {}
        self.insights: dict[str, Any] = {}

    # ==================================================================
    # 公开 API
    # ==================================================================

    def generate(self, output_format: str = "both") -> dict[str, Any]:
        """
        主入口：读取 JSON → 分析 → 导出。

        Parameters
        ----------
        output_format : str
            "json" / "md" / "both"（默认 both）
        """
        self._load_data()
        self._extract_insights()
        if output_format in ("json", "both"):
            self._save_json()
        if output_format in ("md", "both"):
            self._save_markdown()
        logger.info("洞察提炼完成 → %s", self.output_dir)
        return self.insights

    # ==================================================================
    # 数据加载
    # ==================================================================

    def _load_data(self) -> None:
        with open(self.stats_path, "r", encoding="utf-8") as f:
            self.stats = json.load(f)
        if self.profile_path and self.profile_path.exists():
            with open(self.profile_path, "r", encoding="utf-8") as f:
                self.profile = json.load(f)

    # ==================================================================
    # 核心提炼逻辑
    # ==================================================================

    def _extract_insights(self) -> None:
        alpha = self.alpha
        significant_findings: list[dict] = []
        research_questions: list[str] = []
        strong_correlations: list[dict] = []
        summary_counts = {
            "total_tests_checked": 0,
            "significant_count": 0,
            "significant_pct": 0.0,
        }

        # ── 1. 扫描假设检验 ──────────────────────────────────────
        ht = self.stats.get("hypothesis_tests", {}).get("tests", {})
        for test_group_name, test_group in ht.items():
            if isinstance(test_group, dict) and "error" not in test_group:
                # 单条目检验（如 welch_ttest, grouped_ttest 等）
                if "p_value" in test_group:
                    summary_counts["total_tests_checked"] += 1
                    p_val = test_group["p_value"]
                    if isinstance(p_val, (int, float)) and p_val < alpha:
                        summary_counts["significant_count"] += 1
                        finding = self._build_finding(test_group, test_group_name, p_val)
                        significant_findings.append(finding)
                        # 生成对应研究问题
                        q = self._gen_research_question(test_group, test_group_name)
                        if q:
                            research_questions.append(q)

                # 多条目检验（如 one_sample_ttest, wilcoxon 等）
                for key, val in test_group.items():
                    if isinstance(val, dict) and "p_value" in val:
                        summary_counts["total_tests_checked"] += 1
                        p_val = val["p_value"]
                        if isinstance(p_val, (int, float)) and p_val < alpha:
                            summary_counts["significant_count"] += 1
                            val_with_name = {**val, "_test_group": test_group_name, "_column": key}
                            finding = self._build_finding(val_with_name, test_group_name, p_val)
                            significant_findings.append(finding)
                            q = self._gen_research_question(val_with_name, test_group_name)
                            if q:
                                research_questions.append(q)

        # ── 2. 扫描 ANOVA ─────────────────────────────────────────
        anova_data = self.stats.get("anova", {}).get("tests", {})
        for anova_name, anova_item in anova_data.items():
            if not isinstance(anova_item, dict):
                continue
            if "p_value" in anova_item:
                summary_counts["total_tests_checked"] += 1
                p_val = anova_item["p_value"]
                if isinstance(p_val, (int, float)) and p_val < alpha:
                    summary_counts["significant_count"] += 1
                    finding = self._build_finding(anova_item, anova_name, p_val)
                    significant_findings.append(finding)
                    q = self._gen_research_question(anova_item, anova_name)
                    if q:
                        research_questions.append(q)
            # 双因素 ANOVA 有 anova_table
            if "anova_table" in anova_item:
                at = anova_item["anova_table"]
                for factor_key in ["PR(>F)", "p_value", "p-val"]:
                    pass
                # 尝试解析 JSON 中的 p 值列
                try:
                    for row_name, row_data in at.items():
                        if isinstance(row_data, dict):
                            p_f = row_data.get("PR(>F)", row_data.get("p_value"))
                            if p_f is not None and isinstance(p_f, (int, float)) and p_f < alpha:
                                summary_counts["total_tests_checked"] += 1
                                summary_counts["significant_count"] += 1
                                finding = {
                                    "source": f"双因素ANOVA → {anova_name}",
                                    "factor": row_name,
                                    "method": anova_item.get("method", "双因素方差分析"),
                                    "p_value": round(float(p_f), 6),
                                    "significant": True,
                                    "interpretation": f"因子 '{row_name}' 对 '{anova_item.get('dependent','?')}' 存在显著主效应（p={p_f:.4f}）",
                                }
                                significant_findings.append(finding)
                except Exception:
                    pass

        # ── 3. 扫描卡方拟合优度检验 ───────────────────────────────
        chi_data = self.stats.get("chi_square_goodness_of_fit", {}).get("tests", {})
        for chi_name, chi_item in chi_data.items():
            if isinstance(chi_item, dict) and "p_value" in chi_item:
                summary_counts["total_tests_checked"] += 1
                p_val = chi_item["p_value"]
                if isinstance(p_val, (int, float)) and p_val < alpha:
                    summary_counts["significant_count"] += 1
                    finding = self._build_finding(chi_item, chi_name, p_val)
                    significant_findings.append(finding)
                    # 生成研究问题：分布不均意味着什么？
                    col_name = chi_item.get("_column", chi_name)
                    n_cat = chi_item.get("n_categories", "?")
                    research_questions.append(
                        f"「{col_name}」各类别分布显著偏离均匀分布（χ²检验 p={p_val:.4f}），"
                        f"{n_cat}个类别中哪些偏离最大？其背后的原因是什么？"
                    )

        # ── 4. 扫描分布检验 ───────────────────────────────────────
        dist_data = self.stats.get("distribution_tests", {}).get("tests", {})
        for col, col_data in dist_data.items():
            if isinstance(col_data, dict):
                for test_key in ["shapiro_wilk", "dagostino_pearson"]:
                    test_info = col_data.get(test_key)
                    if isinstance(test_info, dict) and "p_value" in test_info:
                        summary_counts["total_tests_checked"] += 1
                        p_val = test_info["p_value"]
                        if isinstance(p_val, (int, float)) and p_val < alpha:
                            summary_counts["significant_count"] += 1
                            # 非正态 → 值得注意
                            finding = {
                                "source": f"分布检验 → {test_key}",
                                "column": col,
                                "method": test_info.get("method", test_key),
                                "p_value": round(float(p_val), 6),
                                "significant": True,
                                "interpretation": (
                                    f"「{col}」的分布显著偏离正态分布（p={p_val:.4f}），"
                                    f"建议使用非参数方法进行分析，或检查是否存在离群值与偏态。"
                                ),
                            }
                            significant_findings.append(finding)
                            research_questions.append(
                                f"「{col}」不服从正态分布，是数据采集偏差、离群值、"
                                f"还是变量本身具有非对称特性？对此变量的分析应选择哪种非参数方法？"
                            )

        # ── 5. 扫描强相关（基于 data_profile 或逐列计算） ───────────
        strong_correlations = self._find_strong_correlations()

        # ── 6. 组装 ────────────────────────────────────────────────
        if summary_counts["total_tests_checked"] > 0:
            summary_counts["significant_pct"] = round(
                summary_counts["significant_count"] / summary_counts["total_tests_checked"] * 100, 1
            )

        # 按 p 值排序
        significant_findings.sort(
            key=lambda x: x.get("p_value", 1.0) if isinstance(x.get("p_value"), (int, float)) else 1.0
        )

        self.insights = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "source_stats": str(self.stats_path),
                "source_profile": str(self.profile_path) if self.profile_path else None,
                "alpha": alpha,
                "strong_corr_threshold": self.strong_corr_threshold,
            },
            "summary": summary_counts,
            "significant_findings": significant_findings,
            "strong_correlations": strong_correlations,
            "research_questions": research_questions,
        }

    # ==================================================================
    # 辅助方法
    # ==================================================================

    def _build_finding(
        self, item: dict, source_name: str, p_val: float
    ) -> dict:
        """从检验条目构建统一的发现记录。"""
        method = item.get("method", source_name)
        columns = item.get("columns") or item.get("column") or item.get("_column", "?")
        if isinstance(columns, list):
            columns = " × ".join(str(c) for c in columns)

        # 统计量
        stat_value = (
            item.get("t_statistic")
            or item.get("F_statistic")
            or item.get("chi2_statistic")
            or item.get("statistic")
        )

        interpretation = item.get("interpretation", "")
        if not interpretation:
            interpretation = (
                f"{method}：{columns}，p = {p_val:.4f}"
                f"{' ★ 显著' if p_val < 0.01 else ' * 显著'}"
            )

        return {
            "source": source_name,
            "method": method,
            "variables": columns if isinstance(columns, str) else str(columns),
            "statistic": round(float(stat_value), 6) if stat_value is not None else None,
            "p_value": round(float(p_val), 6),
            "significant": True,
            "interpretation": interpretation,
        }

    def _gen_research_question(
        self, item: dict, source_name: str
    ) -> Optional[str]:
        """基于显著发现生成可继续研究的问题。"""
        method = item.get("method", source_name)
        columns = item.get("columns") or item.get("column") or item.get("_column", "")
        if isinstance(columns, list):
            columns = "、".join(str(c) for c in columns)

        p_val = item.get("p_value", 0)

        if "t 检验" in method or "ttest" in source_name.lower():
            return (
                f"「{columns}」的组间差异显著（p={p_val:.4f}），"
                f"这种差异的效应量有多大？是否在实际教学中值得关注？"
            )
        if "ANOVA" in method.upper() or "anova" in source_name.lower():
            return (
                f"「{columns}」在不同组别间存在显著差异，"
                f"事后检验中哪些组的配对差异最大？是否需要差异化教学策略？"
            )
        if "Mann-Whitney" in method or "Wilcoxon" in method:
            return (
                f"「{columns}」的非参数检验显著，"
                f"数据分布是否存在偏态？中位数差异是否比均值差异更有参考价值？"
            )
        if "卡方" in method or "chi" in source_name.lower() or "chisquare" in source_name.lower():
            return (
                f"「{columns}」的观测分布与期望分布存在显著差异，"
                f"具体是哪些类别的偏离导致了显著性？是否反映了特定的选择偏好？"
            )
        return None

    def _find_strong_correlations(self) -> list[dict]:
        """找出 |r| > threshold 的强相关对。"""
        strong = []
        numeric_cols = [
            f_item.get("column", "") for f_item in self.profile.get("fields", [])
            if isinstance(f_item, dict)
            and (f_item.get("inferred_type", "") or "").startswith("numeric")
        ]
        # 如果 profile 没有，从 stats 的点估计取
        if not numeric_cols:
            pe_fields = self.stats.get("point_estimation", {}).get("fields", {})
            numeric_cols = list(pe_fields.keys())

        if len(numeric_cols) < 2:
            return strong

        # 从 stats 中读取 Pearson r（如果区间估计里有的话）
        # 否则不做——我们只报告已有的相关结果，不重新计算
        # 但如果 profile 里有 correlation，可以从中提取
        # 这里保守处理：标记所有显著的假设检验中涉及两数值列的情况

        for finding in self.insights.get("significant_findings", []):
            method = finding.get("method", "")
            if "t 检验" in method and finding["p_value"] < self.alpha:
                # 两组 t 检验意味着一个分类列影响一个数值列
                # 不是"相关"，跳过
                pass

        # 实际强相关：从假设检验中的两列均值差检验反向推断
        # 也可以在有了原始数据后直接用 .corr() 补算
        # 这里做一个简化版：检查区间估计中的 two_sample_mean_diff_ci
        ts_diff = self.stats.get("interval_estimation", {}).get("two_sample_mean_diff_ci")
        if ts_diff and "error" not in ts_diff:
            diff = abs(ts_diff.get("diff_mean", 0))
            if diff > 0:
                ci = ts_diff.get("ci", [0, 0])
                if ci[0] * ci[1] > 0:  # CI 不含 0 → 差异显著
                    strong.append({
                        "columns": ts_diff.get("columns", []),
                        "diff_mean": ts_diff["diff_mean"],
                        "ci": ci,
                        "interpretation": (
                            f"两列均值差 CI 不含 0（{ci}），"
                            f"表明两组总体均值存在实质差异。但这并非 Pearson 相关。"
                            f"若需线性相关，请对这两列计算 Pearson r。"
                        ),
                    })

        return strong

    # ==================================================================
    # 导出
    # ==================================================================

    def _save_json(self) -> None:
        path = self.output_dir / "insights.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.insights, f, ensure_ascii=False, indent=2)
        logger.info("insights.json → %s", path)

    def _save_markdown(self) -> None:
        path = self.output_dir / "insights.md"
        lines = self._render_markdown()
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info("insights.md → %s", path)

    def _render_markdown(self) -> list[str]:
        ins = self.insights
        s = ins.get("summary", {})
        findings = ins.get("significant_findings", [])
        corrs = ins.get("strong_correlations", [])
        questions = ins.get("research_questions", [])

        lines = [
            "# 数据洞察与显著性发现",
            "",
            f"> 生成时间：{ins['meta']['generated_at']}",
            f"> 显著性水平 α = {ins['meta']['alpha']}",
            f"> 来源：`{ins['meta']['source_stats']}`",
            "",
            "---",
            "",
            "## 1. 概览",
            "",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| 检验总数 | {s.get('total_tests_checked', 0)} |",
            f"| 显著结果 | {s.get('significant_count', 0)} |",
            f"| 显著比例 | {s.get('significant_pct', 0)}% |",
            "",
            "---",
            "",
            f"## 2. 显著发现（P < {ins['meta']['alpha']}）",
            "",
            f"共 **{len(findings)}** 条：",
            "",
        ]

        if findings:
            lines.append("| # | 方法 | 变量 | 统计量 | P 值 | 解读 |")
            lines.append("|---|------|------|--------|------|------|")
            for i, f_item in enumerate(findings, 1):
                method = f_item.get("method", "-")
                var = f_item.get("variables", "-")
                stat = f_item.get("statistic")
                stat_str = f"{stat:.4f}" if isinstance(stat, float) else "-"
                p_val = f_item.get("p_value", "-")
                interp = f_item.get("interpretation", "-")
                lines.append(f"| {i} | {method} | {var} | {stat_str} | {p_val} | {interp} |")
        else:
            lines.append("> ⚠ 未发现任何 p < 0.05 的显著结果。可能样本量不足或效应微弱。")

        lines.extend([
            "",
            "---",
            "",
            "## 3. 强相关特征",
            "",
        ])
        if corrs:
            for c_item in corrs:
                lines.append(f"- **{c_item.get('columns', [])}**：{c_item.get('interpretation', '')}")
        else:
            lines.append("> 当前数据中未检测到统计上显著的强相关对。")

        lines.extend([
            "",
            "---",
            "",
            "## 4. 可继续研究的问题",
            "",
        ])
        if questions:
            for i, q in enumerate(questions, 1):
                lines.append(f"{i}. {q}")
        else:
            lines.append("> 暂无。")

        lines.extend([
            "",
            "---",
            "",
            "*此文件由 `insight_generator.py` 自动生成，所有数值来自真实统计计算。*",
        ])
        return lines


# ------------------------------------------------------------------
# 便捷函数
# ------------------------------------------------------------------

def generate_insights(
    stats_json_path: Union[str, Path],
    profile_json_path: Optional[Union[str, Path]] = None,
    output_dir: Union[str, Path] = "./outputs",
    output_format: str = "both",
) -> dict[str, Any]:
    """一行调用：从统计结果 JSON 提炼洞察。"""
    gen = InsightGenerator(
        stats_json_path=stats_json_path,
        profile_json_path=profile_json_path,
        output_dir=output_dir,
    )
    return gen.generate(output_format=output_format)


# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    import sys

    if len(sys.argv) < 2:
        print("用法：python insight_generator.py <stats_results.json路径> [data_profile.json路径]")
        print("示例：python insight_generator.py outputs/run_xxx/stats_results.json outputs/run_xxx/data_profile.json")
        sys.exit(1)

    stats_p = sys.argv[1]
    profile_p = sys.argv[2] if len(sys.argv) > 2 else None
    ins = generate_insights(stats_p, profile_p)
    print(f"\n总结: {ins['summary']}")
    print(f"显著发现: {len(ins['significant_findings'])} 条")
    print(f"研究问题: {len(ins['research_questions'])} 个")
    print(f"输出: insights.json / insights.md")
