# -*- coding: utf-8 -*-
"""
@File    : evidence_table.py
@Author  : Robusr
@Date    : 2026/6/20
@Description: 结构化证据表 — 所有LLM调用只能引用此表中的数据，防止幻觉
"""

"""
证据表模块
功能：集中的结构化发现存储，所有业务分析模块写入，所有LLM轮次只能读取。
每条发现必须包含：结论、规模、比较基准、原因线索、业务含义、统计证据路径。

设计原则：
1. 代码生成事实，LLM 只做排序和解释
2. 每个 finding 绑定真实的 stat_reference_path
3. LLM 不允许引用证据表中不存在的数字
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class EvidenceType(str, Enum):
    """证据类型枚举。"""
    SIGNIFICANT_DIFFERENCE = "significant_difference"
    DISTRIBUTION_SKEW = "distribution_skew"
    CORRELATION = "correlation"
    LOSS_CONCENTRATION = "loss_concentration"
    DISCOUNT_THRESHOLD = "discount_threshold"
    PARETO_CONTRIBUTION = "pareto_contribution"
    CROSS_DIM_PATTERN = "cross_dimension_pattern"
    GRANULARITY_NOTE = "granularity_note"
    DESCRIPTIVE_OBSERVATION = "descriptive_observation"


@dataclass
class EvidenceFinding:
    """单条证据发现。"""
    # 来源
    source_module: str                    # 生成此证据的模块名
    finding_type: EvidenceType            # 证据类型

    # 5大必备要素
    conclusion: str                       # 结论（简洁、明确）
    magnitude: str                        # 规模/量级
    comparison_baseline: str              # 比较基准/参照
    cause_clues: str                      # 原因线索
    business_implications: str            # 业务含义

    # 证据绑定
    stat_reference_path: str              # 在 stats_results.json 或模块结果中的路径
    # 可选的辅助字段
    supporting_data: Optional[Dict[str, Any]] = None  # 补充数据

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finding_id: str = ""                  # 自动生成


class EvidenceTable:
    """结构化证据表。

    使用方式：
        table = EvidenceTable(domain_config)
        table.add_finding(source_module="loss_driver", ...)
        findings = table.get_findings_by_module("loss_driver")
        compact = table.to_compact_dict()  # 供 LLM 上下文使用
    """

    def __init__(self, domain_config=None):
        self.findings: List[EvidenceFinding] = []
        self.domain_config = domain_config
        self._counter = 0

    def add_finding(
        self,
        source_module: str,
        finding_type: str,
        conclusion: str,
        magnitude: str = "",
        comparison_baseline: str = "",
        cause_clues: str = "",
        business_implications: str = "",
        stat_reference_path: str = "",
        supporting_data: Optional[Dict[str, Any]] = None,
    ) -> EvidenceFinding:
        """添加一条证据发现。所有字段建议填写，至少提供 conclusion 和 stat_reference_path。"""
        self._counter += 1
        finding_id = f"{source_module}_{self._counter:04d}"

        ftype = finding_type
        if isinstance(ftype, str):
            try:
                ftype = EvidenceType(ftype)
            except ValueError:
                ftype = EvidenceType.DESCRIPTIVE_OBSERVATION

        finding = EvidenceFinding(
            source_module=source_module,
            finding_type=ftype,
            conclusion=conclusion,
            magnitude=magnitude,
            comparison_baseline=comparison_baseline,
            cause_clues=cause_clues,
            business_implications=business_implications,
            stat_reference_path=stat_reference_path,
            supporting_data=supporting_data,
            finding_id=finding_id,
        )
        self.findings.append(finding)
        return finding

    def get_findings_by_module(self, module_name: str) -> List[EvidenceFinding]:
        """按来源模块获取证据。"""
        return [f for f in self.findings if f.source_module == module_name]

    def get_findings_by_type(self, finding_type: EvidenceType) -> List[EvidenceFinding]:
        """按证据类型获取。"""
        return [f for f in self.findings if f.finding_type == finding_type]

    def get_all(self) -> List[EvidenceFinding]:
        """获取全部证据。"""
        return list(self.findings)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为完整字典（保存用）。"""
        return {
            "meta": {
                "total_findings": len(self.findings),
                "generated_at": datetime.now().isoformat(),
                "domain": self.domain_config.key if self.domain_config else "unknown",
                "module_counts": {
                    mod: len(self.get_findings_by_module(mod))
                    for mod in set(f.source_module for f in self.findings)
                },
            },
            "findings": [asdict(f) for f in self.findings],
        }

    def to_compact_dict(self, max_per_module: int = 8) -> Dict[str, Any]:
        """生成供 LLM 使用的精简证据摘要。

        每个 finding 只保留关键字段，避免 token 浪费。
        """
        compact = {
            "total_findings": len(self.findings),
            "evidence_by_module": {},
        }

        for module in sorted(set(f.source_module for f in self.findings)):
            findings = self.get_findings_by_module(module)[:max_per_module]
            compact["evidence_by_module"][module] = [
                {
                    "id": f.finding_id,
                    "type": f.finding_type.value if isinstance(f.finding_type, EvidenceType) else f.finding_type,
                    "conclusion": f.conclusion,
                    "magnitude": f.magnitude,
                    "baseline": f.comparison_baseline,
                    "cause": f.cause_clues,
                    "implication": f.business_implications,
                    "ref": f.stat_reference_path,
                }
                for f in findings
            ]

        return compact

    def to_llm_context(self, max_total: int = 30) -> str:
        """生成直接可注入 LLM 提示词的证据表文本。

        格式设计为 LLM 易解析的结构化文本。
        """
        if not self.findings:
            return "（证据表为空——无预计算证据可用）"

        lines = [
            "# 证据表（仅供 LLM 引用——禁止编造表中不存在的数据）",
            f"# 共 {len(self.findings)} 条证据，以下展示最重要的条目",
            "",
        ]

        # 按模块分组
        modules = sorted(set(f.source_module for f in self.findings))
        for module in modules:
            mod_findings = self.get_findings_by_module(module)[:5]
            if not mod_findings:
                continue
            lines.append(f"## [{module}]")
            for f in mod_findings:
                ftype = f.finding_type.value if isinstance(f.finding_type, EvidenceType) else f.finding_type
                lines.append(f"  [{ftype}] {f.finding_id}")
                lines.append(f"    结论: {f.conclusion}")
                if f.magnitude:
                    lines.append(f"    规模: {f.magnitude}")
                if f.comparison_baseline:
                    lines.append(f"    基准: {f.comparison_baseline}")
                if f.cause_clues:
                    lines.append(f"    原因线索: {f.cause_clues}")
                if f.business_implications:
                    lines.append(f"    业务含义: {f.business_implications}")
                lines.append(f"    证据路径: {f.stat_reference_path}")
                lines.append("")
        return "\n".join(lines[:max_total * 10])  # 截断防止 token 溢出

    def validate_denominators(self) -> List[str]:
        """验证所有比率类证据是否明确了分母。返回问题列表。"""
        issues = []
        for f in self.findings:
            conclusion = f.conclusion.lower()
            # 检查是否包含比率类关键词但缺少分母说明
            rate_keywords = ["率", "%", "占比", "ratio", "percent", "rate"]
            has_rate = any(kw in conclusion for kw in rate_keywords)
            has_denominator = (
                "分母" in f.magnitude.lower()
                or "行" in f.conclusion
                or "单" in f.conclusion
                or "明细" in f.conclusion
                or "客户" in f.conclusion
                or "产品" in f.conclusion
                or "商品" in f.conclusion
                or "总" in f.magnitude
                or "订单" in f.conclusion
            )
            if has_rate and not has_denominator:
                issues.append(
                    f"[{f.finding_id}] 含比率但可能缺少分母说明: '{f.conclusion}'"
                )
        return issues

    def __len__(self):
        return len(self.findings)

    def __bool__(self):
        return True  # 即使为空也是有效的
