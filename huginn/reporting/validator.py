# -*- coding: utf-8 -*-
"""
@File    : report_validator.py
@Author  : Robusr
@Date    : 2026/6/10 16:46
@Description: 报告合规性验证器
@Software: PyCharm
"""

"""
报告合规性验证器
功能：自动检查数据分析报告的完整性与统计合规性
检查项：
1.  统计数量硬指标（5点估计/5区间估计/5假设检验/2ANOVA/2卡方）
2.  统计结果有效性（p值范围、样本量、无编造数据）
3.  数据发现合规性（引用正确p值、无因果错误、无模糊表述）
4.  行动建议合理性（有数据依据、可落地）
5.  报告完整性（数据概况、局限性说明）
输出：JSON格式机器可读结果 + Markdown格式人类可读报告
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any

from huginn.core.config import Config
from huginn.core.logger import get_logger

logger = get_logger(__name__)


class ReportValidator:
    # 默认分析完整性要求（从 Config 读取）
    REQUIREMENTS = Config.REQUIREMENTS
    CAUSAL_WORDS = Config.CAUSAL_WORDS
    VAGUE_WORDS = Config.VAGUE_WORDS

    def __init__(self, run_dir: str):
        self.run_dir = Path(run_dir)
        self.results: Dict[str, Any] = {
            "meta": {
                "run_dir": str(self.run_dir.resolve()),
                "generated_at": "",
                "overall_pass": False,
                "score": 0,
                "total_checks": 0,
                "passed_checks": 0,
            },
            "checks": {
                "statistical_quantity": {"pass": False, "details": [], "score": 0, "max_score": 30},
                "statistical_validity": {"pass": False, "details": [], "score": 0, "max_score": 20},
                "findings_compliance": {"pass": False, "details": [], "score": 0, "max_score": 20},
                "business_analysis_completeness": {"pass": True, "details": [], "score": 10, "max_score": 10},
                "suggestions_quality": {"pass": False, "details": [], "score": 0, "max_score": 10},
                "report_completeness": {"pass": False, "details": [], "score": 0, "max_score": 10},
            },
            "improvement_suggestions": [],
        }
        self._load_files()

    def _load_files(self) -> None:
        """加载验证所需的所有JSON文件。"""
        required_files = [
            "data_profile.json",
            "stats_results.json",
            "valid_tasks.json",
            "findings.json",
            "suggestions.json",
        ]

        self.files = {}
        for filename in required_files:
            file_path = self.run_dir / filename
            if not file_path.exists():
                raise FileNotFoundError(f"缺少必要文件: {filename}")
            with open(file_path, "r", encoding="utf-8") as f:
                self.files[filename] = json.load(f)

        self.data_profile = self.files["data_profile.json"]
        self.stats_results = self.files["stats_results.json"]
        self.valid_tasks = self.files["valid_tasks.json"]
        self.findings = self.files["findings.json"]
        self.suggestions = self.files["suggestions.json"]
        domain_path = self.run_dir / "domain_context.json"
        self.domain_context = json.loads(domain_path.read_text(encoding="utf-8")) if domain_path.exists() else {}
        distinctive_path = self.run_dir / "distinctive_features.json"
        if distinctive_path.exists():
            with open(distinctive_path, "r", encoding="utf-8") as f:
                self.distinctive_features = json.load(f)
        else:
            self.distinctive_features = {"features": []}
        final_report_path = self.run_dir / "final_report.md"
        self.final_report_text = final_report_path.read_text(encoding="utf-8") if final_report_path.exists() else ""

        # 可选文件
        self.evidence_table = self._load_optional_json("evidence_table.json")
        self.field_registry = self._load_optional_json("field_registry.json")
        self.granularity = self._load_optional_json("granularity.json")
        self.loss_driver = self._load_optional_json("loss_driver_results.json")
        self.discount_analysis = self._load_optional_json("discount_analysis_results.json")
        self.pareto_analysis = self._load_optional_json("pareto_analysis_results.json")
        self.cross_dimension = self._load_optional_json("cross_dimension_results.json")

    def _load_optional_json(self, filename: str) -> dict:
        path = self.run_dir / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def run_all_checks(self) -> Dict[str, Any]:
        """执行所有检查项，生成完整验证报告。"""
        from datetime import datetime
        self.results["meta"]["generated_at"] = datetime.now().isoformat()

        self._check_statistical_quantity()
        self._check_statistical_validity()
        self._check_findings_compliance()
        self._check_business_analysis_completeness()
        self._check_suggestions_quality()
        self._check_report_completeness()

        total_score = sum(c["score"] for c in self.results["checks"].values())
        self.results["meta"]["score"] = round(total_score, 1)
        self.results["meta"]["overall_pass"] = total_score >= 60
        self.results["meta"]["total_checks"] = sum(
            len(c["details"]) for c in self.results["checks"].values()
        )
        self.results["meta"]["passed_checks"] = sum(
            1 for c in self.results["checks"].values() for d in c["details"] if d.get("pass", False)
        )

        self._generate_overall_suggestions()
        self._save_results()
        return self.results

    # ------------------------------
    # 结构化统计证据工具
    # ------------------------------
    def _iter_stat_results_with_keys(self) -> List[Tuple[str, Dict[str, Any]]]:
        pairs: List[Tuple[str, Dict[str, Any]]] = []

        for section in ["hypothesis_tests", "anova", "chi_square_goodness_of_fit", "distribution_tests"]:
            tests = self.stats_results.get(section, {}).get("tests", {})
            self._collect_stat_results(section, tests, pairs)

        self._collect_stat_results("point_estimation", self.stats_results.get("point_estimation", {}).get("fields", {}), pairs)
        self._collect_stat_results("interval_estimation", self.stats_results.get("interval_estimation", {}).get("fields", {}), pairs)
        self._collect_stat_results("correlations", self.stats_results.get("correlations", {}), pairs)
        for feature in self.distinctive_features.get("features", []):
            if not isinstance(feature, dict) or not feature.get("source_key"):
                continue
            pairs.append((feature["source_key"], feature))
        return pairs

    def _collect_stat_results(self, prefix: str, node: Any, pairs: List[Tuple[str, Dict[str, Any]]]) -> None:
        if not isinstance(node, dict) or "error" in node:
            return
        if "p_value" in node or any(key in node for key in ["F_statistic", "chi2_statistic", "t_statistic", "statistic", "mean", "mean_ci"]):
            pairs.append((prefix, node))
            return
        for key, value in node.items():
            if isinstance(value, dict):
                self._collect_stat_results(f"{prefix}.{key}", value, pairs)

    @staticmethod
    def _item_stat_keys(item: Dict[str, Any], valid_stat_keys: Any) -> List[str]:
        valid = set(valid_stat_keys)
        refs = item.get("source_stat_keys") or []
        if isinstance(refs, str):
            refs = [refs]
        return [str(ref) for ref in refs if str(ref) in valid]

    # ------------------------------
    # 1. 统计数量硬指标检查（40分）
    # ------------------------------
    def _check_statistical_quantity(self) -> None:
        """检查是否满足最低统计数量要求（权重从40降至30）。"""
        check = self.results["checks"]["statistical_quantity"]
        check["score"] = check["max_score"]  # 30分

        # 1. 点估计数量
        pe_count = len(self.stats_results.get("point_estimation", {}).get("fields", {}))
        numeric_usable = sum(
            1
            for field in self.data_profile.get("fields", [])
            if str(field.get("inferred_type", "")).startswith("numeric")
            and field.get("column") in self.stats_results.get("point_estimation", {}).get("fields", {})
        )
        point_min = min(self.REQUIREMENTS["point_estimation_min"], numeric_usable)
        if pe_count >= point_min:
            check["details"].append({
                "item": "点估计数量",
                "actual": pe_count,
                "required": f"≥{point_min}",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "点估计数量",
                "actual": pe_count,
                "required": f"≥{point_min}",
                "pass": False,
                "error": "点估计数量不足，需增加数值列"
            })
            check["score"] -= 8

        # 2. 区间估计数量
        ie_count = len(self.stats_results.get("interval_estimation", {}).get("fields", {}))
        interval_min = min(self.REQUIREMENTS["interval_estimation_min"], numeric_usable)
        if ie_count >= interval_min:
            check["details"].append({
                "item": "区间估计数量",
                "actual": ie_count,
                "required": f"≥{interval_min}",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "区间估计数量",
                "actual": ie_count,
                "required": f"≥{interval_min}",
                "pass": False,
                "error": "区间估计数量不足，需增加数值列"
            })
            check["score"] -= 8

        # 3. 假设检验数量（排除有error的）
        ht_tests = self.stats_results.get("hypothesis_tests", {}).get("tests", {})
        ht_count = sum(1 for v in ht_tests.values() if isinstance(v, dict) and "error" not in v)
        ht_count += sum(
            1 for value in self.stats_results.get("correlations", {}).values()
            if isinstance(value, dict) and "error" not in value and value.get("p_value") is not None
        )
        ht_count += sum(
            1 for value in self.stats_results.get("distribution_tests", {}).get("tests", {}).values()
            if isinstance(value, dict) and "error" not in value
        )
        if ht_count >= self.REQUIREMENTS["hypothesis_test_min"]:
            check["details"].append({
                "item": "假设检验数量",
                "actual": ht_count,
                "required": f"≥{self.REQUIREMENTS['hypothesis_test_min']}",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "假设检验数量",
                "actual": ht_count,
                "required": f"≥{self.REQUIREMENTS['hypothesis_test_min']}",
                "pass": False,
                "error": "假设检验数量不足，需增加更多分析任务"
            })
            check["score"] -= 8

        # 4. ANOVA数量（排除有error的）
        anova_tests = self.stats_results.get("anova", {}).get("tests", {})
        anova_count = sum(1 for v in anova_tests.values() if isinstance(v, dict) and "error" not in v)
        if anova_count >= self.REQUIREMENTS["anova_min"]:
            check["details"].append({
                "item": "ANOVA数量",
                "actual": anova_count,
                "required": f"≥{self.REQUIREMENTS['anova_min']}",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "ANOVA数量",
                "actual": anova_count,
                "required": f"≥{self.REQUIREMENTS['anova_min']}",
                "pass": False,
                "error": "ANOVA数量不足，需增加多分类变量的分析任务"
            })
            check["score"] -= 8

        # 5. 卡方检验数量（包括拟合优度和独立性检验）
        chi_gof = self.stats_results.get("chi_square_goodness_of_fit", {}).get("tests", {})
        chi_independence = {k: v for k, v in ht_tests.items() if "chi_square" in k}
        chi_count = len(chi_gof) + len(chi_independence)
        if chi_count >= self.REQUIREMENTS["chi_square_min"]:
            check["details"].append({
                "item": "卡方检验数量",
                "actual": chi_count,
                "required": f"≥{self.REQUIREMENTS['chi_square_min']}",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "卡方检验数量",
                "actual": chi_count,
                "required": f"≥{self.REQUIREMENTS['chi_square_min']}",
                "pass": False,
                "error": "卡方检验数量不足，需增加分类变量的分析任务"
            })
            check["score"] -= 8

        # 检查引擎自带的数量自查结果
        counts_check = self.stats_results.get("counts_check", {})
        if counts_check.get("all_checks_pass"):
            check["details"].append({
                "item": "统计引擎数量自查",
                "actual": "通过",
                "required": "通过",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "统计引擎数量自查",
                "actual": "失败",
                "required": "通过",
                "pass": False,
                "error": f"引擎自查失败: {counts_check.get('notes', [])}"
            })
            check["score"] -= 4

        check["pass"] = all(d["pass"] for d in check["details"])
        check["score"] = max(0, check["score"])  # 最低0分

    # ------------------------------
    # 2. 统计结果有效性检查（20分）
    # ------------------------------
    def _check_statistical_validity(self) -> None:
        """检查统计结果的数学有效性和可靠性"""
        check = self.results["checks"]["statistical_validity"]
        check["score"] = 20  # 满分20分

        # 1. 所有p值在0-1之间
        invalid_p_values = []
        for stat_key, test_result in self._iter_stat_results_with_keys():
            if isinstance(test_result, dict) and "p_value" in test_result:
                p_val = test_result["p_value"]
                if p_val is None:
                    continue
                if not isinstance(p_val, (int, float)) or not (0 <= p_val <= 1):
                    invalid_p_values.append(f"{stat_key}: p={p_val}")

        if not invalid_p_values:
            check["details"].append({
                "item": "p值有效性",
                "actual": "所有p值在0-1之间",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "p值有效性",
                "actual": f"发现{len(invalid_p_values)}个无效p值",
                "pass": False,
                "error": f"无效p值: {invalid_p_values[:3]}"
            })
            check["score"] -= 6

        # 2. 所有显著发现的p值都<0.05
        invalid_significant = []
        stat_result_by_key = dict(self._iter_stat_results_with_keys())
        for finding in self.findings:
            evidence = finding.get("evidence", "")
            conclusion = finding.get("conclusion", "")
            explicitly_non_significant = any(
                phrase in conclusion for phrase in ["不显著", "无显著", "未达显著", "未达到显著", "未达统计显著"]
            )
            # 提取证据中的p值（支持科学记数法：p=3.7e-118, p≈1.0e-55, p = 0.003）
            p_match = re.search(r"p\s*[=≈]\s*([\d\.]+(?:[eE][+-]?\d+)?)", evidence)
            if p_match and not explicitly_non_significant:
                try:
                    p_val = float(p_match.group(1))
                except ValueError:
                    p_val = None
                if p_val is not None and p_val >= self.REQUIREMENTS["significant_p_threshold"]:
                    invalid_significant.append(f"发现[{finding['conclusion']}]: p={p_match.group(1)}")
                    continue
            for stat_key in self._item_stat_keys(finding, stat_result_by_key.keys()):
                if explicitly_non_significant:
                    break
                p_val = stat_result_by_key.get(stat_key, {}).get("p_value")
                if isinstance(p_val, (int, float)) and p_val >= self.REQUIREMENTS["significant_p_threshold"]:
                    invalid_significant.append(f"发现[{finding['conclusion']}]: {stat_key} p={p_val}")
                    break

        if not invalid_significant:
            check["details"].append({
                "item": "显著发现p值合规性",
                "actual": "所有显著发现的p值均<0.05",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "显著发现p值合规性",
                "actual": f"发现{len(invalid_significant)}个不显著的结果被作为显著发现",
                "pass": False,
                "error": f"问题发现: {invalid_significant[:3]}"
            })
            check["score"] -= 6

        # 3. 没有空的统计结果
        empty_sections = []
        for section in ["point_estimation", "interval_estimation", "hypothesis_tests"]:
            if not self.stats_results.get(section, {}).get("fields", {}) and not self.stats_results.get(section, {}).get("tests", {}):
                empty_sections.append(section)

        if not empty_sections:
            check["details"].append({
                "item": "统计结果完整性",
                "actual": "所有统计模块都有结果",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "统计结果完整性",
                "actual": f"以下模块为空: {empty_sections}",
                "pass": False,
                "error": "部分统计模块未生成结果，可能是数据不足"
            })
            check["score"] -= 4

        # 4. 样本量满足要求
        sample_issues = []
        pe_fields = self.stats_results.get("point_estimation", {}).get("fields", {})
        for col, result in pe_fields.items():
            if isinstance(result, dict) and "n" in result and result["n"] < 3:
                sample_issues.append(f"{col}: n={result['n']}")

        if not sample_issues:
            check["details"].append({
                "item": "样本量要求",
                "actual": "所有变量样本量≥3",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "样本量要求",
                "actual": f"发现{len(sample_issues)}个变量样本量不足",
                "pass": False,
                "error": f"样本量不足的变量: {sample_issues[:3]}"
            })
            check["score"] -= 4

        check["pass"] = all(d["pass"] for d in check["details"])
        check["score"] = max(0, check["score"])

    # ------------------------------
    # 3. 数据发现合规性检查（20分）
    # ------------------------------
    def _check_findings_compliance(self) -> None:
        """检查数据发现是否符合要求（不编造数据、无因果错误、引用正确）"""
        check = self.results["checks"]["findings_compliance"]
        check["score"] = 20  # 满分20分

        if not self.findings:
            check["details"].append({
                "item": "数据发现数量",
                "actual": 0,
                "required": "≥5条",
                "pass": False,
                "error": "没有生成任何数据发现"
            })
            check["score"] = 0
            check["pass"] = False
            return

        # 1. 数据发现数量≥5条
        if len(self.findings) >= 5:
            check["details"].append({
                "item": "数据发现数量",
                "actual": len(self.findings),
                "required": "≥5条",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "数据发现数量",
                "actual": len(self.findings),
                "required": "≥5条",
                "pass": False,
                "error": "数据发现数量不足，需增加更多分析任务"
            })
            check["score"] -= 5

        # 2. 每个发现都有明确的证据（引用统计量和p值，或描述性统计量）
        missing_evidence = []
        valid_stat_keys = set(dict(self._iter_stat_results_with_keys()).keys())
        for i, finding in enumerate(self.findings):
            evidence = finding.get("evidence", "")
            has_text_evidence = bool(re.search(r"[tFχ²Wr]=[\d\.\-]+.*p=[\d\.]+", evidence))
            has_structured_evidence = bool(self._item_stat_keys(finding, valid_stat_keys))
            if not has_text_evidence and not has_structured_evidence:
                missing_evidence.append(f"发现{i+1}: {finding['conclusion']}")

        if not missing_evidence:
            check["details"].append({
                "item": "数据发现证据完整性",
                "actual": "所有发现都引用了统计量/p值或结构化统计证据",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "数据发现证据完整性",
                "actual": f"发现{len(missing_evidence)}个发现缺少证据",
                "pass": False,
                "error": f"缺少证据的发现: {missing_evidence[:3]}"
            })
            check["score"] -= 5

        # 3. 没有因果关系错误
        causal_errors = []
        for i, finding in enumerate(self.findings):
            conclusion = finding.get("conclusion", "")
            for word in self.CAUSAL_WORDS:
                if word in conclusion:
                    if word == "影响" and "极端值" in conclusion:
                        continue
                    causal_errors.append(f"发现{i+1}: 使用了因果词汇'{word}'")
                    break

        if not causal_errors:
            check["details"].append({
                "item": "因果关系表述",
                "actual": "未发现因果关系错误",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "因果关系表述",
                "actual": f"发现{len(causal_errors)}个因果关系错误",
                "pass": False,
                "error": f"问题发现: {causal_errors[:3]}",
                "suggestion": "将'导致'改为'相关'，'影响'改为'存在关联'"
            })
            check["score"] -= 5

        # 4. 没有模糊词汇（排除字段名中天然包含的词汇）
        vague_errors = []
        for i, finding in enumerate(self.findings):
            conclusion = finding.get("conclusion", "")
            for word in self.VAGUE_WORDS:
                if word in conclusion:
                    idx = conclusion.find(word)
                    # 如果该词出现在结论开头附近（前10字符内），很可能是字段名的一部分
                    if idx < 10:
                        continue
                    # 检查前后中文上下文：如果嵌入在长中文字段名中则跳过
                    before = conclusion[max(0, idx-3):idx]
                    after = conclusion[idx+len(word):idx+len(word)+3]
                    chinese_before = sum(1 for c in before if '一' <= c <= '鿿')
                    chinese_after = sum(1 for c in after if '一' <= c <= '鿿')
                    if chinese_before >= 1 or chinese_after >= 1:
                        continue
                    vague_errors.append(f"发现{i+1}: 使用了模糊词汇'{word}'")
                    break

        if not vague_errors:
            check["details"].append({
                "item": "表述准确性",
                "actual": "未发现模糊词汇",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "表述准确性",
                "actual": f"发现{len(vague_errors)}个模糊表述",
                "pass": False,
                "error": f"问题发现: {vague_errors[:3]}",
                "suggestion": "删除模糊词汇，使用明确的统计结论"
            })
            check["score"] -= 5

        check["pass"] = all(d["pass"] for d in check["details"])
        check["score"] = max(0, check["score"])

    # ------------------------------
    # 4. 业务分析完整度检查（10分）
    # ------------------------------
    def _check_business_analysis_completeness(self) -> None:
        """检查业务分析模块是否完整覆盖（零售领域自动激活的模块）。"""
        check = self.results["checks"]["business_analysis_completeness"]
        check["score"] = 10  # 满分10分

        # 检测领域类型
        domain = self.data_profile.get("meta", {}).get("domain", "")
        is_retail = domain == "retail_sales" or bool(self.loss_driver or self.discount_analysis)

        if not is_retail:
            check["details"].append({
                "item": "业务分析模块",
                "actual": f"当前领域({domain or '通用'})不需要业务分析模块",
                "pass": True,
                "note": "非零售领域跳过业务分析模块检查"
            })
            check["pass"] = True
            return

        # 零售领域：检查四大业务模块
        expected_modules = {
            "loss_driver": "亏损驱动分析",
            "discount_analysis": "折扣响应分析",
            "pareto_analysis": "集中度分析",
            "cross_dimension": "交叉维度分析",
        }

        module_results = {
            "loss_driver": self.loss_driver,
            "discount_analysis": self.discount_analysis,
            "pareto_analysis": self.pareto_analysis,
            "cross_dimension": self.cross_dimension,
        }

        all_present = True
        for key, label in expected_modules.items():
            has_data = bool(module_results.get(key))
            if has_data:
                check["details"].append({
                    "item": label,
                    "actual": "已生成",
                    "pass": True,
                })
            else:
                check["details"].append({
                    "item": label,
                    "actual": "缺失",
                    "required": "零售领域需包含此分析",
                    "pass": False,
                    "error": f"缺少{label}结果"
                })
                all_present = False
                check["score"] -= 2

        if all_present:
            check["details"].append({
                "item": "业务分析覆盖度",
                "actual": "四大业务模块全部覆盖",
                "pass": True,
            })

        check["pass"] = all_present
        check["score"] = max(0, check["score"])

    # ------------------------------
    # 5. 行动建议合理性检查（10分）
    # ------------------------------
    def _check_suggestions_quality(self) -> None:
        """检查行动建议是否有数据依据、是否可落地"""
        check = self.results["checks"]["suggestions_quality"]
        check["score"] = 10  # 满分10分

        if not self.suggestions:
            check["details"].append({
                "item": "行动建议数量",
                "actual": 0,
                "required": "≥3条",
                "pass": False,
                "error": "没有生成任何行动建议"
            })
            check["score"] = 0
            check["pass"] = False
            return

        # 1. 行动建议数量≥3条
        if len(self.suggestions) >= 3:
            check["details"].append({
                "item": "行动建议数量",
                "actual": len(self.suggestions),
                "required": "≥3条",
                "pass": True,
            })
        else:
            check["details"].append({
                "item": "行动建议数量",
                "actual": len(self.suggestions),
                "required": "≥3条",
                "pass": False,
                "error": "行动建议数量不足"
            })
            check["score"] -= 3

        # 2. 每个建议都有数据依据（使用子串匹配，因为建议中可能截断结论）
        missing_evidence = []
        valid_stat_keys = set(dict(self._iter_stat_results_with_keys()).keys())
        finding_conclusions = [f["conclusion"] for f in self.findings]
        finding_stat_keys = {
            key
            for finding in self.findings
            for key in self._item_stat_keys(finding, valid_stat_keys)
        }
        for i, suggestion in enumerate(self.suggestions):
            evidence = suggestion.get("evidence", "")
            suggestion_keys = set(self._item_stat_keys(suggestion, valid_stat_keys))
            has_text_basis = bool(evidence and evidence in finding_conclusions)
            has_structured_basis = bool(suggestion_keys and (suggestion_keys & finding_stat_keys or suggestion_keys <= valid_stat_keys))
            if not has_text_basis and not has_structured_basis:
                missing_evidence.append(f"建议{i+1}: {suggestion['suggestion']}")

        if not missing_evidence:
            check["details"].append({
                "item": "建议依据有效性",
                "actual": "所有建议都有对应的数据发现",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "建议依据有效性",
                "actual": f"发现{len(missing_evidence)}个建议缺少有效依据",
                "pass": False,
                "error": f"缺少依据的建议: {missing_evidence[:3]}"
            })
            check["score"] -= 4

        # 3. 建议具体可落地（中文字数≥20且有具体措施的不算笼统）
        vague_suggestions = []
        vague_phrases = ["加强", "改进", "提高", "优化", "完善"]
        for i, suggestion in enumerate(self.suggestions):
            sug_text = suggestion.get("suggestion", "")
            direction = suggestion.get("direction", "")
            chinese_chars = len(sug_text)
            if self._is_vague_suggestion(sug_text, direction):
                vague_suggestions.append(f"建议{i+1}: {sug_text}")
            elif chinese_chars < 40 and any(phrase in sug_text for phrase in vague_phrases):
                # 中等长度但仅含模糊动词，检查direction是否具体
                if not any(kw in direction for kw in ["预期", "具体", "每周", "每学期", "比例", "次数", "频率"]):
                    vague_suggestions.append(f"建议{i+1}: {sug_text}")

        if not vague_suggestions:
            check["details"].append({
                "item": "建议可落地性",
                "actual": "所有建议都具体可落地",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "建议可落地性",
                "actual": f"发现{len(vague_suggestions)}个建议过于笼统",
                "pass": False,
                "error": f"笼统建议: {vague_suggestions[:3]}",
                "suggestion": "补充具体的改进措施和预期效果"
            })
            check["score"] -= 3

        check["pass"] = all(d["pass"] for d in check["details"])
        check["score"] = max(0, check["score"])

    @staticmethod
    def _is_vague_suggestion(suggestion: str, direction: str = "") -> bool:
        """兼容中文无空格文本：只有泛化动词且正文、落地方向都过短时才判为笼统。"""
        text = str(suggestion).strip()
        detail = str(direction).strip()
        if len(text) < 10:
            return True
        vague_phrases = ["加强", "改进", "提高", "优化", "完善"]
        has_generic_verb = any(phrase in text for phrase in vague_phrases)
        return has_generic_verb and len(text) < 30 and len(detail) < 15

    # ------------------------------
    # 6. 报告完整性检查（10分）
    # ------------------------------
    def _check_report_completeness(self) -> None:
        """检查报告是否包含所有必要部分"""
        check = self.results["checks"]["report_completeness"]
        check["score"] = 10  # 满分10分

        # 1. 数据概况完整
        if self.data_profile.get("meta", {}).get("total_missing_pct") is not None:
            check["details"].append({
                "item": "数据概况完整性",
                "actual": "包含数据行数、列数、缺失率等信息",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "数据概况完整性",
                "actual": "数据概况信息不完整",
                "pass": False,
                "error": "缺少缺失率、字段类型等关键信息"
            })
            check["score"] -= 3

        # 2. 包含局限性说明（检查建议、发现、以及实际报告文件）
        has_limitation = False
        if any(term in self.final_report_text for term in ["局限性", "相关性不等于因果", "不能推断因果", "因果关系"]):
            has_limitation = True

        for suggestion in self.suggestions:
            if "局限性" in suggestion.get("direction", "") or "相关性不等于因果" in suggestion.get("direction", ""):
                has_limitation = True
                break

        # 检查发现中是否有因果提醒
        if not has_limitation:
            for finding in self.findings:
                if "相关性不等于因果" in finding.get("conclusion", ""):
                    has_limitation = True
                    break

        # 检查报告 Markdown 文件是否包含局限性章节
        if not has_limitation:
            report_path = self.run_dir / "final_report.md"
            if report_path.exists():
                report_text = report_path.read_text(encoding="utf-8")
                limitation_keywords = ["局限性", "相关性不等于因果", "不代表因果关系", "相关关系", "不等于因果"]
                if "局限性" in report_text and any(kw in report_text for kw in limitation_keywords[1:]):
                    has_limitation = True

        if has_limitation:
            check["details"].append({
                "item": "局限性说明",
                "actual": "包含相关性不等于因果关系的提醒",
                "pass": True
            })
        else:
            check["details"].append({
                "item": "局限性说明",
                "actual": "未包含局限性说明",
                "pass": False,
                "error": "必须在报告中明确说明相关性不等于因果关系",
                "suggestion": "在报告末尾添加局限性章节，说明样本量、测量偏差等限制"
            })
            check["score"] -= 4

        # 3. 图表数量足够
        chart_dir = self.run_dir / "charts"
        if chart_dir.exists():
            chart_count = len(list(chart_dir.glob("*.png")))
            if chart_count >= 3:
                check["details"].append({
                    "item": "图表数量",
                    "actual": f"{chart_count}张",
                    "required": "≥3张",
                    "pass": True
                })
            else:
                check["details"].append({
                    "item": "图表数量",
                    "actual": f"{chart_count}张",
                    "required": "≥3张",
                    "pass": False,
                    "error": "图表数量不足，需增加更多可视化"
                })
                check["score"] -= 3
        else:
            check["details"].append({
                "item": "图表数量",
                "actual": 0,
                "required": "≥3张",
                "pass": False,
                "error": "未生成任何图表"
            })
            check["score"] -= 3

        check["pass"] = all(d["pass"] for d in check["details"])
        check["score"] = max(0, check["score"])

    # ------------------------------
    # 生成整体改进建议
    # ------------------------------
    def _generate_overall_suggestions(self) -> None:
        """基于检查结果生成整体改进建议"""
        suggestions = []

        # 统计数量问题
        if not self.results["checks"]["statistical_quantity"]["pass"]:
            suggestions.append(
                " 统计数量不达标：请增加更多数值列和分类列的分析任务，"
                "确保满足5点估计/5区间估计/5假设检验/2ANOVA/2卡方的最低要求"
            )

        # 统计结果有效性问题
        if not self.results["checks"]["statistical_validity"]["pass"]:
            suggestions.append(
                " 统计结果存在无效值：请检查数据质量，确保所有p值在0-1之间，"
                "且只有p<0.05的结果被作为显著发现"
            )

        # 数据发现合规性问题
        if not self.results["checks"]["findings_compliance"]["pass"]:
            suggestions.append(
                " 数据发现存在合规性问题：请删除因果词汇（如'导致'、'影响'）和模糊词汇，"
                "确保每个发现都引用具体的统计量和p值"
            )

        # 行动建议问题
        if not self.results["checks"]["suggestions_quality"]["pass"]:
            suggestions.append(
                " 行动建议不够合理：请确保每个建议都有对应的数据发现，"
                "并补充具体的改进措施和预期效果"
            )

        # 业务分析覆盖问题
        if not self.results["checks"]["business_analysis_completeness"]["pass"]:
            suggestions.append(
                " 业务分析覆盖不足：数据中存在利润/折扣/维度等关键字段，"
                "但未充分执行亏损驱动、折扣响应或交叉维度分析"
            )

        # 报告完整性问题
        if not self.results["checks"]["report_completeness"]["pass"]:
            suggestions.append(
                " 报告不够完整：请在报告末尾添加局限性说明，"
                "明确指出相关性不等于因果关系，并增加更多可视化图表"
            )

        if not suggestions:
            suggestions.append(" 所有检查项均通过，报告符合默认分析完整性要求！")

        self.results["improvement_suggestions"] = suggestions

    # ------------------------------
    # 保存结果
    # ------------------------------
    def _save_results(self) -> None:
        """保存验证结果为JSON和Markdown格式"""
        # 保存JSON格式
        json_path = self.run_dir / "validation_result.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)

        # 保存Markdown格式
        md_path = self.run_dir / "validation_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._render_markdown())

        print(f"\n Done 验证完成！结果已保存到:")
        print(f"   - JSON: {json_path}")
        print(f"   - Markdown: {md_path}")
        print(f"\nScore 总分: {self.results['meta']['score']}/100")
        print(f"\nResult 整体结果: {'通过' if self.results['meta']['overall_pass'] else '不通过'}")

    def _render_markdown(self) -> str:
        """渲染Markdown格式的验证报告"""
        res = self.results
        lines = [
            "# 报告合规性验证报告",
            "",
            f"> 生成时间：{res['meta']['generated_at']}",
            f"> 输出目录：{res['meta']['run_dir']}",
            f"> 总分：**{res['meta']['score']}/100**",
            f"> 整体结果：{' 通过' if res['meta']['overall_pass'] else '❌ 不通过'}",
            "",
            "---",
            "",
            "## 1. 验证概览",
            "",
            f"| 检查模块 | 得分 | 满分 | 结果 |",
            f"|----------|------|------|------|",
        ]

        for name, check in res["checks"].items():
            module_name = {
                "statistical_quantity": "统计数量硬指标",
                "statistical_validity": "统计结果有效性",
                "findings_compliance": "数据发现合规性",
                "suggestions_quality": "行动建议合理性",
                "business_analysis_completeness": "业务分析完整度",
                "report_completeness": "报告完整性"
            }[name]
            result_emoji = "Done" if check["pass"] else "Error"
            lines.append(f"| {module_name} | {check['score']} | {check['max_score']} | {result_emoji} |")

        lines.extend([
            "",
            "---",
            "",
            "## 2. 详细检查结果",
            "",
        ])

        for name, check in res["checks"].items():
            module_name = {
                "statistical_quantity": "2.1 统计数量硬指标（30分）",
                "statistical_validity": "2.2 统计结果有效性（20分）",
                "findings_compliance": "2.3 数据发现合规性（20分）",
                "suggestions_quality": "2.4 行动建议合理性（10分）",
                "business_analysis_completeness": "2.5 业务分析完整度（10分）",
                "report_completeness": "2.6 报告完整性（10分）"
            }[name]
            lines.append(f"### {module_name}")
            lines.append("")
            lines.append("| 检查项 | 实际值 | 要求 | 结果 | 说明 |")
            lines.append("|--------|--------|------|------|------|")

            for detail in check["details"]:
                result_emoji = "Done" if detail["pass"] else "Error"
                note = detail.get("error", "") or detail.get("suggestion", "")
                lines.append(f"| {detail['item']} | {detail['actual']} | {detail.get('required', '-')} | {result_emoji} | {note} |")

            lines.append("")

        lines.extend([
            "---",
            "",
            "## 3. 整体改进建议",
            "",
        ])

        for i, sug in enumerate(res["improvement_suggestions"], 1):
            lines.append(f"{i}. {sug}")

        lines.extend([
            "",
            "---",
            "",
            "*此报告由 report_validator.py 自动生成，所有检查项遵循默认分析完整性标准。*"
        ])

        return "\n".join(lines)

# ------------------------------------------------------------------
# 命令行入口
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法：python report_validator.py <运行输出目录路径>")
        print("示例：python report_validator.py outputs/20260610_143022_销售数据")
        sys.exit(1)

    try:
        validator = ReportValidator(sys.argv[1])
        validator.run_all_checks()
    except Exception as e:
        print(f"\nError 验证失败: {str(e)}")
        sys.exit(1)
