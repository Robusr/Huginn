# -*- coding: utf-8 -*-
"""
@File    : llm_client.py
@Author  : Robusr
@Date    : 2026/6/10 15:59
@Description: LLM 客户端 — 域感知四轮调用（task_planning/problem_discovery/findings_suggestions/report_writing）
"""

"""
DeepSeek API 客户端封装
结构化输出分析任务、特色问题、数据发现、行动建议与报告文稿
"""
import os
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from openai import OpenAI, APIError, BadRequestError, RateLimitError, APITimeoutError
from pydantic import BaseModel, Field, ValidationError

from huginn.planning.analysis_planning import build_candidate_task_pool, build_planning_field_map
from huginn.core.config import Config
from huginn.domain.context import detect_domain_context
from huginn.core.label_utils import humanize_column_name
from huginn.core.logger import get_logger

logger = get_logger(__name__)

load_dotenv()


# ============================================================================
# Pydantic 结构化输出模型
# ============================================================================

class CandidateQuestion(BaseModel):
    """单个候选分析问题的结构化格式"""
    question: str = Field(description="自然语言描述的分析问题，必须符合当前数据领域和用户需求")
    variables: List[str] = Field(description="涉及的变量名，必须与数据画像中的column字段完全一致")
    method: str = Field(
        description="建议使用的统计方法：t检验、配对t检验、ANOVA、卡方检验、相关性分析、分布检验"
    )
    value: str = Field(description="该问题的业务分析价值，说明为什么值得研究")
    task_pool_id: Optional[str] = Field(default=None, description="候选任务池中的稳定任务ID")
    variable_ids: List[str] = Field(default_factory=list, description="字段注册表中的字段ID")

class CandidateQuestionsResponse(BaseModel):
    """候选问题列表。"""
    questions: List[CandidateQuestion] = Field(description="8-12个候选分析问题")



class CandidateTaskSelection(BaseModel):
    """模型从合法候选任务池中选择的任务。"""
    task_pool_id: str = Field(description="必须来自候选任务池的task_pool_id")
    value: str = Field(default="", description="选择该任务的业务或决策分析价值")
    priority: int = Field(default=3, description="重要性评分，1-5分，5分最高")


class CandidateTaskSelectionResponse(BaseModel):
    """候选任务池选择结果。"""
    selections: List[CandidateTaskSelection] = Field(description="从候选任务池中选择的8-12个任务")


class DataFinding(BaseModel):
    """单个数据发现。"""
    conclusion: str = Field(description="基于统计结果的明确结论")
    evidence: str = Field(description="数据依据，引用具体的统计量和p值")
    method: str = Field(description="使用的统计方法")
    importance: int = Field(description="重要性评分，1-5分，5分最高")
    source_stat_keys: List[str] = Field(default_factory=list, description="引用的统计结果路径，如anova.task_1_one_way_anova")
    source_task_ids: List[int] = Field(default_factory=list, description="引用的执行任务ID")

class ActionSuggestion(BaseModel):
    """单个行动建议的结构化格式。"""
    suggestion: str = Field(description="具体可落地的改进建议，不能泛泛而谈")
    evidence: str = Field(description="支撑该建议的数据发现，引用具体结论")
    direction: str = Field(description="具体的改进方向和预期效果")
    source_stat_keys: List[str] = Field(default_factory=list, description="支撑该建议的统计结果路径")
    source_task_ids: List[int] = Field(default_factory=list, description="支撑该建议的执行任务ID")

class FindingsAndSuggestionsResponse(BaseModel):
    """发现和建议的统一输出格式"""
    findings: List[DataFinding] = Field(description="5-8条核心数据发现，按重要性从高到低排序")
    suggestions: List[ActionSuggestion] = Field(description="3-5条针对性行动建议，与发现一一对应")


# 保留旧导入名，避免已有调用方中断。
CourseSuggestion = ActionSuggestion


class DiscoveredProblem(BaseModel):
    """模型从统计证据中识别出的特色问题或异常信号。"""
    title: str = Field(description="简洁的问题标题")
    description: str = Field(description="问题或特色信号的清晰说明")
    importance: int = Field(description="重要性评分，1-5分")
    source_stat_keys: List[str] = Field(default_factory=list, description="只能引用证据表中的统计结果路径")
    source_task_ids: List[int] = Field(default_factory=list, description="对应的统计任务ID")


class ProblemDiscoveryResponse(BaseModel):
    problems: List[DiscoveredProblem] = Field(description="3-8个最值得写入报告的问题或特色信号")


class ReportWritingResponse(BaseModel):
    """第四轮报告写作结果，不允许改变统计证据。"""
    title: str = Field(description="符合数据领域的正式报告标题")
    subtitle: str = Field(description="简洁的报告副标题")
    executive_summary: str = Field(description="结论优先的执行摘要")
    overview_paragraphs: List[str] = Field(description="1-3段自然的数据概览文字")
    chart_section_intro: str = Field(description="图表分析章节导语")
    findings: List[DataFinding] = Field(default_factory=list, description="润色后的主要发现，证据引用不得改变")
    suggestions: List[ActionSuggestion] = Field(default_factory=list, description="润色后的行动建议，证据引用不得改变")
    limitations: List[str] = Field(description="数据与方法使用边界")

class LLMClient:
    SKILL_REFERENCE_FILES = {
        "question_planning": "question_planning.md",
        "problem_discovery": "problem_discovery.md",
        "findings_suggestions": "findings_suggestions.md",
        "report_writing": "report_writing.md",
    }

    def __init__(self, offline_mode: bool = False):
        """
        初始化LLM客户端
        :param offline_mode: 离线模式，仅加载预生成的结果，不调用API
        """
        self.offline_mode = offline_mode
        self.call_audit: List[Dict[str, Any]] = []
        if not offline_mode:
            self.client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url=os.getenv("DEEPSEEK_BASE_URL", Config.LLM_BASE_URL),
            )
            self.model = Config.LLM_MODEL
            self.max_retries = Config.LLM_MAX_RETRIES
            self.retry_delay = Config.LLM_RETRY_DELAY

    @classmethod
    def _skill_references_dir(cls) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "skill" / "references"

    @classmethod
    def _load_step_skill_prompt(cls, step: str) -> str:
        filename = cls.SKILL_REFERENCE_FILES.get(step)
        if not filename:
            return ""

        path = cls._skill_references_dir() / filename
        try:
            content = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            logger.warning("未找到步骤专用 skill 文件: %s", path)
            return ""

        return (
            "你正在作为 Huginn 通用数据分析报告智能体工作。"
            "以下是本次模型调用必须遵守的步骤专用规范：\n\n"
            f"{content}"
        )

    @classmethod
    def _build_step_messages(cls, step: str, prompt: str) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        skill_prompt = cls._load_step_skill_prompt(step)
        if skill_prompt:
            messages.append({"role": "system", "content": skill_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _record_call(self, stage: str, *, success: bool, error: str = "") -> None:
        """记录一次业务层模型调用；传输重试不重复计数。"""
        audit = getattr(self, "call_audit", None)
        if audit is None:
            self.call_audit = []
            audit = self.call_audit
        audit.append(
            {
                "sequence": len(audit) + 1,
                "stage": stage,
                "model": getattr(self, "model", "offline"),
                "success": success,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "error": error,
            }
        )

    def save_call_audit(self, output_dir: str | Path) -> Path:
        path = Path(output_dir) / "llm_call_audit.json"
        payload = {
            "expected_rounds": 0 if self.offline_mode else 4,
            "actual_rounds": len(self.call_audit),
            "all_success": all(item.get("success") for item in self.call_audit),
            "calls": self.call_audit,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def _questions_from_task_pool(
        task_pool: Dict[str, Any],
        selections: List[CandidateTaskSelection],
    ) -> List[CandidateQuestion]:
        pool_tasks = task_pool.get("tasks", [])
        by_id = {item.get("task_pool_id"): item for item in pool_tasks}
        selected: List[CandidateQuestion] = []
        seen: set[str] = set()

        ordered_selections = sorted(
            selections,
            key=lambda item: item.priority,
            reverse=True,
        )
        selection_values = {item.task_pool_id: item.value for item in ordered_selections}

        def append_task(task: Dict[str, Any]) -> None:
            task_id = task.get("task_pool_id")
            if not task_id or task_id in seen or len(selected) >= 12:
                return
            seen.add(task_id)
            selected.append(
                CandidateQuestion(
                    question=task["question"],
                    variables=task["variables"],
                    method=task["method"],
                    value=selection_values.get(task_id) or task.get("value", ""),
                    task_pool_id=task_id,
                    variable_ids=task.get("variable_ids", []),
                )
            )

        has_t_family = any(task.get("method") in {"t检验", "配对t检验"} for task in pool_tasks)
        quotas = {"ANOVA": 2, "卡方检验": 2, "相关性分析": 2, "分布检验": 2}
        if has_t_family:
            quotas["t_family"] = 3
        else:
            quotas["ANOVA"] = 3
            quotas["相关性分析"] = 3

        for method, quota in quotas.items():
            candidates = [
                task for task in pool_tasks
                if task.get("method") in ({"t检验", "配对t检验"} if method == "t_family" else {method})
            ]
            for task in candidates[:quota]:
                append_task(task)

        for selection in ordered_selections:
            task = by_id.get(selection.task_pool_id)
            if task:
                append_task(task)

        # Defensive fill: keep the downstream statistical coverage stable even
        # if the model selects too few IDs or returns stale IDs.
        for task in pool_tasks:
            if len(selected) >= 12:
                break
            append_task(task)

        return selected[:12]

    def _call_with_retry(self, messages: List[Dict], response_format: Optional[type[BaseModel]] = None) -> Any:
        """带重试机制的API调用，处理速率限制和超时"""
        if self.offline_mode:
            raise Exception("离线模式下无法调用API")

        if response_format:
            schema_json = response_format.model_json_schema()
            schema_str = json.dumps(schema_json, ensure_ascii=False)
            augmented_messages = [
                *messages[:-1],
                {
                    "role": messages[-1]["role"],
                    "content": messages[-1]["content"] + (
                        f"\n\n【输出格式 - JSON Schema】\n{schema_str}"
                    ),
                },
            ]
        else:
            augmented_messages = messages

        for attempt in range(self.max_retries):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": augmented_messages,
                    "temperature": Config.LLM_TEMPERATURE,
                    "top_p": Config.LLM_TOP_P,
                    "max_tokens": Config.LLM_MAX_TOKENS,
                }
                if response_format:
                    kwargs["response_format"] = response_format
                try:
                    return self.client.beta.chat.completions.parse(**kwargs)
                except BadRequestError as e:
                    if self._should_fallback_to_json_text(e):
                        logger.warning("当前模型不支持 response_format，自动切换为 JSON 文本解析模式")
                        return self._call_json_text_fallback(messages, response_format)
                    raise
            except RateLimitError:
                if attempt == self.max_retries - 1:
                    raise Exception("DeepSeek API 速率限制超限")
                time.sleep(self.retry_delay * (attempt + 1))
            except APITimeoutError:
                if attempt == self.max_retries - 1:
                    raise Exception("DeepSeek API 超时")
                time.sleep(self.retry_delay)
            except APIError as e:
                raise Exception(f"DeepSeek API 调用失败: {str(e)}")

    @staticmethod
    def _should_fallback_to_json_text(error: BadRequestError) -> bool:
        message = str(error).lower()
        return "response_format" in message and (
            "unavailable" in message
            or "not support" in message
            or "unsupported" in message
        )

    def _call_json_text_fallback(
        self,
        messages: List[Dict],
        response_model: type[BaseModel],
    ) -> Any:
        """兼容不支持 response_format 的 OpenAI 兼容模型。"""
        schema = response_model.model_json_schema()
        json_messages = [
            {
                "role": "system",
                "content": (
                    "你必须只输出一个合法 JSON 对象，不要输出 Markdown、解释文字或代码块。"
                    "JSON 必须符合用户要求的结构。"
                ),
            },
            *messages,
            {
                "role": "user",
                "content": (
                    "再次强调：最终回答只能是 JSON 对象。"
                    f"目标 JSON Schema 如下：{json.dumps(schema, ensure_ascii=False)}"
                ),
            },
        ]
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=json_messages,
            temperature=Config.LLM_TEMPERATURE,
            top_p=Config.LLM_TOP_P,
            max_tokens=Config.LLM_MAX_TOKENS,
        )
        content = completion.choices[0].message.content or ""
        try:
            json_text = self._extract_json_object(content)
            parsed = response_model.model_validate_json(json_text)
        except (ValidationError, Exception) as exc:
            logger.warning("模型返回 JSON 不完整或不合规，尝试请求模型修复一次")
            parsed = self._repair_and_parse_json(content, response_model, schema, exc)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        parsed=parsed,
                        content=content,
                    )
                )
            ]
        )

    def _repair_and_parse_json(
        self,
        content: str,
        response_model: type[BaseModel],
        schema: Dict[str, Any],
        original_error: Exception,
    ) -> BaseModel:
        repair_messages = [
            {
                "role": "system",
                "content": "你是 JSON 修复器。只输出一个完整合法 JSON 对象，不要解释，不要 Markdown。",
            },
            {
                "role": "user",
                "content": (
                    "下面的模型输出不是完整合法 JSON，或不符合目标结构。"
                    "请根据已有内容补全/修正为一个完整 JSON 对象。"
                    f"\n目标 JSON Schema：{json.dumps(schema, ensure_ascii=False)}"
                    f"\n原始错误：{original_error}"
                    f"\n待修复内容：\n{content}"
                ),
            },
        ]
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=repair_messages,
            temperature=0,
            top_p=1,
            max_tokens=Config.LLM_MAX_TOKENS,
        )
        repaired_content = completion.choices[0].message.content or ""
        try:
            repaired_json = self._extract_json_object(repaired_content)
            return response_model.model_validate_json(repaired_json)
        except Exception as exc:
            raise Exception(f"模型返回内容无法通过结构化校验: {exc}") from exc

    @staticmethod
    def _extract_json_object(content: str) -> str:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.removeprefix("json").strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise Exception("模型未返回可解析的 JSON 对象")
        return text[start:end + 1]

    @classmethod
    def _build_evidence_table(
        cls,
        stats_results: Dict[str, Any],
        distinctive_features: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        evidence: List[Dict[str, Any]] = []

        for key, item in stats_results.get("point_estimation", {}).get("fields", {}).items():
            if not isinstance(item, dict) or "error" in item:
                continue
            evidence.append(
                {
                    "stat_key": f"point_estimation.{key}",
                    "method": "点估计",
                    "variables": [key],
                    "readable_variables": [cls._humanize_column_name(key)],
                    "statistic": item.get("mean"),
                    "p_value": None,
                    "significant": None,
                    "n": item.get("n"),
                    "mean": item.get("mean"),
                    "std": item.get("std"),
                    "source_task_id": None,
                }
            )

        for key, item in stats_results.get("anova", {}).get("tests", {}).items():
            if not isinstance(item, dict) or "error" in item:
                continue
            evidence.append(
                {
                    "stat_key": f"anova.{key}",
                    "method": item.get("method", "ANOVA"),
                    "variables": [item.get("dependent"), item.get("factor")],
                    "readable_variables": [cls._humanize_column_name(item.get("dependent")), cls._humanize_column_name(item.get("factor"))],
                    "statistic": cls._first_present(item, ["F_statistic"]),
                    "p_value": item.get("p_value"),
                    "significant": item.get("significant"),
                    "source_task_id": cls._task_id_from_key(key),
                }
            )

        for key, item in stats_results.get("hypothesis_tests", {}).get("tests", {}).items():
            cls._append_hypothesis_evidence(evidence, f"hypothesis_tests.{key}", item, key)

        for key, item in stats_results.get("correlations", {}).items():
            if not isinstance(item, dict) or "error" in item:
                continue
            evidence.append(
                {
                    "stat_key": f"correlations.{key}",
                    "method": item.get("method", "相关性分析"),
                    "variables": item.get("variables", []),
                    "readable_variables": [cls._humanize_column_name(v) for v in item.get("variables", [])],
                    "statistic": item.get("correlation_coefficient"),
                    "p_value": item.get("p_value"),
                    "significant": item.get("significant"),
                    "source_task_id": cls._task_id_from_key(key),
                }
            )

        for key, item in stats_results.get("distribution_tests", {}).get("tests", {}).items():
            if not isinstance(item, dict) or "error" in item:
                continue
            p_values = [
                value.get("p_value")
                for value in item.values()
                if isinstance(value, dict) and value.get("p_value") is not None
            ]
            evidence.append(
                {
                    "stat_key": f"distribution_tests.{key}",
                    "method": "分布检验",
                    "variables": [key],
                    "readable_variables": [cls._humanize_column_name(key)],
                    "p_value": min(p_values) if p_values else None,
                    "significant": any(p is not None and p < Config.SIGNIFICANCE_THRESHOLD for p in p_values),
                    "source_task_id": cls._task_id_from_key(key),
                }
            )

        for key, item in stats_results.get("chi_square_goodness_of_fit", {}).get("tests", {}).items():
            if not isinstance(item, dict) or "error" in item:
                continue
            evidence.append(
                {
                    "stat_key": f"chi_square_goodness_of_fit.{key}",
                    "method": item.get("method", "卡方检验"),
                    "variables": [key],
                    "readable_variables": [cls._humanize_column_name(key)],
                    "statistic": item.get("chi2_statistic"),
                    "p_value": item.get("p_value"),
                    "significant": item.get("significant"),
                    "source_task_id": cls._task_id_from_key(key),
                }
            )

        for feature in (distinctive_features or {}).get("features", [])[:20]:
            if not isinstance(feature, dict) or not feature.get("source_key"):
                continue
            variables = feature.get("variables", [])
            evidence.append(
                {
                    "stat_key": feature["source_key"],
                    "method": feature.get("method", "特色信号挖掘"),
                    "variables": variables,
                    "readable_variables": feature.get("readable_variables") or [
                        cls._humanize_column_name(v) for v in variables
                    ],
                    "statistic": feature.get("score"),
                    "p_value": feature.get("p_value"),
                    "significant": feature.get("significant"),
                    "source_task_id": None,
                    "feature_type": feature.get("feature_type"),
                    "title": feature.get("title"),
                    "finding": feature.get("finding"),
                    "evidence": feature.get("evidence"),
                    "metrics": feature.get("metrics", {}),
                }
            )

        def evidence_rank(row: Dict[str, Any]) -> tuple:
            stat_key = str(row.get("stat_key", ""))
            p_value = row.get("p_value")
            is_distinctive = stat_key.startswith("distinctive_features.")
            if isinstance(p_value, (int, float)) and p_value < Config.SIGNIFICANCE_THRESHOLD:
                tier = 0
            elif is_distinctive:
                tier = 1
            elif isinstance(p_value, (int, float)):
                tier = 2
            else:
                tier = 3
            return (
                tier,
                p_value if isinstance(p_value, (int, float)) else 1,
                -float(row.get("statistic") or 0),
            )

        evidence.sort(key=evidence_rank)
        return evidence[:45]

    @classmethod
    def _append_hypothesis_evidence(
        cls,
        evidence: List[Dict[str, Any]],
        prefix: str,
        item: Any,
        raw_key: str,
    ) -> None:
        if not isinstance(item, dict) or "error" in item:
            return
        if "p_value" in item:
            variables = item.get("variables") or item.get("columns") or [
                item.get("numeric_column"),
                item.get("grouping_column"),
            ]
            variables = [v for v in variables if v]
            evidence.append(
                {
                    "stat_key": prefix,
                    "method": item.get("method", "假设检验"),
                    "variables": variables,
                    "readable_variables": [cls._humanize_column_name(v) for v in variables],
                    "statistic": cls._first_present(item, ["t_statistic", "chi2_statistic", "statistic"]),
                    "p_value": item.get("p_value"),
                    "significant": item.get("significant"),
                    "source_task_id": cls._task_id_from_key(raw_key),
                }
            )
            return
        for sub_key, sub_item in item.items():
            cls._append_hypothesis_evidence(evidence, f"{prefix}.{sub_key}", sub_item, sub_key)

    @staticmethod
    def _first_present(item: Dict[str, Any], keys: List[str]) -> Any:
        for key in keys:
            if item.get(key) is not None:
                return item[key]
        return None

    @staticmethod
    def _task_id_from_key(key: Any) -> Optional[int]:
        import re

        match = re.search(r"task_(\d+)", str(key))
        return int(match.group(1)) if match else None

    @staticmethod
    def _valid_stat_keys(stats_results: Dict[str, Any]) -> set[str]:
        return {
            row["stat_key"]
            for row in LLMClient._build_evidence_table(stats_results)
            if row.get("stat_key")
        }

    @staticmethod
    def _count_significant_results(stats_results: Dict[str, Any]) -> int:
        """统计所有 p < 0.05 的结果数量（用于 LLM 预扫描提示）。"""
        count = 0

        # 假设检验
        for test in stats_results.get("hypothesis_tests", {}).get("tests", {}).values():
            if isinstance(test, dict) and "p_value" in test:
                p = test.get("p_value")
                if isinstance(p, (int, float)) and p < 0.05:
                    count += 1

        # ANOVA
        for test in stats_results.get("anova", {}).get("tests", {}).values():
            if isinstance(test, dict) and "p_value" in test:
                p = test.get("p_value")
                if isinstance(p, (int, float)) and p < 0.05:
                    count += 1

        # 卡方检验
        for test in stats_results.get("chi_square", {}).get("tests", {}).values():
            if isinstance(test, dict) and "p_value" in test:
                p = test.get("p_value")
                if isinstance(p, (int, float)) and p < 0.05:
                    count += 1

        # 相关性分析
        for test in stats_results.get("correlations", {}).values():
            if isinstance(test, dict) and "p_value" in test:
                p = test.get("p_value")
                if isinstance(p, (int, float)) and p < 0.05:
                    count += 1

        # 分布检验
        for test in stats_results.get("distribution_tests", {}).get("tests", {}).values():
            if isinstance(test, dict) and "p_value" in test:
                p = test.get("p_value")
                if isinstance(p, (int, float)) and p < 0.05:
                    count += 1

        return count

    @classmethod
    def _normalize_finding_refs(
        cls,
        findings: List[DataFinding],
        suggestions: List[CourseSuggestion],
        evidence_table: List[Dict[str, Any]],
    ) -> None:
        evidence_by_key = {
            row["stat_key"]: row
            for row in evidence_table
            if row.get("stat_key")
        }
        valid_keys = set(evidence_by_key)
        if not valid_keys:
            return
        first_key = next(iter(evidence_by_key))

        def task_ids_for(stat_keys: List[str]) -> List[int]:
            task_ids: List[int] = []
            for key in stat_keys:
                task_id = evidence_by_key[key].get("source_task_id")
                if task_id is not None and int(task_id) not in task_ids:
                    task_ids.append(int(task_id))
            return task_ids

        for finding in findings:
            finding.source_stat_keys = [key for key in finding.source_stat_keys if key in valid_keys]
            if not finding.source_stat_keys:
                finding.source_stat_keys = [first_key]
            finding.source_task_ids = task_ids_for(finding.source_stat_keys)

        for suggestion in suggestions:
            suggestion.source_stat_keys = [key for key in suggestion.source_stat_keys if key in valid_keys]
            if not suggestion.source_stat_keys and findings:
                suggestion.source_stat_keys = findings[0].source_stat_keys[:1]
            suggestion.source_task_ids = task_ids_for(suggestion.source_stat_keys)

    def generate_candidate_questions(
        self,
        data_profile: Dict,
        user_requirement: str,
        *,
        field_registry: Optional[Dict[str, Any]] = None,
        task_pool: Optional[Dict[str, Any]] = None,
        domain_context: Optional[Dict[str, Any]] = None,
    ) -> List[CandidateQuestion]:
        """
        基于数据画像和用户需求生成候选分析问题
        :param data_profile: data_profiler.py生成的数据画像JSON
        :param user_requirement: 用户输入的分析需求
        :return: 候选问题列表
        """
        self._last_data_profile = data_profile
        context = domain_context or detect_domain_context(data_profile, user_requirement)
        field_registry = field_registry or build_planning_field_map(data_profile, context)
        task_pool = task_pool or build_candidate_task_pool(data_profile, field_registry, domain_context=context)
        if self.offline_mode:
            return self._load_offline_questions()

        compact_registry = [
            {
                "field_id": item["field_id"],
                "label": item["label"],
                "inferred_type": item["inferred_type"],
                "unique": item["unique"],
                "available_methods": item["available_methods"],
            }
            for item in field_registry.get("fields", [])
        ]
        compact_pool = [
            {
                "task_pool_id": item["task_pool_id"],
                "question": item["question"],
                "method": item["method"],
                "variable_ids": item["variable_ids"],
                "variable_labels": item["variable_labels"],
                "value": item["value"],
            }
            for item in task_pool.get("tasks", [])
        ]

        prompt = f"""
你是一位严谨的数据分析专家。请从候选任务池中选择8-12个最有业务价值、最符合当前数据领域的统计分析任务。

【数据领域】
{json.dumps(context, ensure_ascii=False, indent=2)}

【字段注册表】
{json.dumps(compact_registry, ensure_ascii=False, indent=2)}

【合法候选任务池】
{json.dumps(compact_pool, ensure_ascii=False, indent=2)}

【用户需求】
{user_requirement}

【严格要求】
1. 只能选择【合法候选任务池】中已经存在的 task_pool_id，禁止发明新变量、新字段ID或新任务ID。
2. 优先选择能体现核心指标水平、分组差异、变量关联和数据异常的问题。
3. 尽量覆盖至少2个ANOVA、2个卡方检验、3个t检验，并兼顾相关性分析或分布检验。
4. 每个选择给出简短 value，说明它对当前业务或决策问题的价值。
5. 输出必须严格符合指定的JSON格式，不能有任何额外的解释、markdown标记或注释。
"""
        messages = self._build_step_messages("question_planning", prompt)
        try:
            response = self._call_with_retry(messages, response_format=CandidateTaskSelectionResponse)
            selections = response.choices[0].message.parsed.selections
            result = self._questions_from_task_pool(task_pool, selections)
            self._record_call("task_planning", success=True)
            return result
        except Exception as exc:
            self._record_call("task_planning", success=False, error=str(exc))
            raise

    def discover_analysis_problems(
        self,
        stats_results: Dict[str, Any],
        data_profile: Dict[str, Any],
        executed_tasks: List[Dict[str, Any]],
        distinctive_features: Optional[Dict[str, Any]],
        domain_context: Optional[Dict[str, Any]] = None,
    ) -> List[DiscoveredProblem]:
        """第二轮：从代码计算出的合法证据中发现特色问题。"""
        context = domain_context or detect_domain_context(data_profile)
        evidence_table = self._build_evidence_table(stats_results, distinctive_features)
        if self.offline_mode:
            problems = [
                DiscoveredProblem(
                    title=row.get("title") or "值得关注的数据信号",
                    description=row.get("finding") or f"{row.get('readable_variables', [])}呈现值得进一步解释的特征。",
                    importance=5 if row.get("significant") else 4,
                    source_stat_keys=[row["stat_key"]],
                    source_task_ids=[row["source_task_id"]] if row.get("source_task_id") is not None else [],
                )
                for row in evidence_table[:6]
            ]
            return problems

        prompt = f"""
你是一位负责问题发现的数据分析专家。请在给定证据中识别最有特点、最值得解释的问题，而不是复述所有通用统计量。

【数据领域】
{json.dumps(context, ensure_ascii=False, indent=2)}

【用户需求】
{context.get('user_requirement', '')}

【已执行任务】
{json.dumps(executed_tasks, ensure_ascii=False, indent=2)}

【可引用证据表】
{json.dumps(evidence_table, ensure_ascii=False, indent=2)}

【要求】
1. 只能依据证据表，source_stat_keys 只能使用其中已有的 stat_key。
2. 优先发现反差、异常、集中、分化、显著分组差异及有决策价值的关联。
3. 不将相关性写成因果关系；p>=0.05 的结果不得写成“显著”。
4. 不套用教育、零售或其他领域的固定措辞，必须服从【数据领域】。
5. 若证据表包含日期逻辑、缺失、重复、异常值等数据质量风险，必须纳入问题列表并明确其对后续分析的限制。
6. 输出3-8个问题，严格符合JSON结构。
"""
        try:
            response = self._call_with_retry(
                self._build_step_messages("problem_discovery", prompt),
                response_format=ProblemDiscoveryResponse,
            )
            problems = response.choices[0].message.parsed.problems
            valid_rows = {row["stat_key"]: row for row in evidence_table if row.get("stat_key")}
            for problem in problems:
                problem.source_stat_keys = [key for key in problem.source_stat_keys if key in valid_rows]
                problem.source_task_ids = [
                    int(valid_rows[key]["source_task_id"])
                    for key in problem.source_stat_keys
                    if valid_rows[key].get("source_task_id") is not None
                ]
            problems = [problem for problem in problems if problem.source_stat_keys]
            problems = self._ensure_critical_problem_coverage(
                problems, distinctive_features or {}, valid_rows
            )
            self._record_call("problem_discovery", success=True)
            return problems
        except Exception as exc:
            self._record_call("problem_discovery", success=False, error=str(exc))
            raise

    def generate_findings_and_suggestions(
        self,
        stats_results: Dict,
        data_profile: Dict,
        executed_tasks: List[Dict],
        distinctive_features: Optional[Dict[str, Any]] = None,
        discovered_problems: Optional[List[DiscoveredProblem]] = None,
        domain_context: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[DataFinding], List[CourseSuggestion]]:
        """
        基于统计结果生成主要发现和行动建议
        :param stats_results: analysis_engine.py生成的统计结果JSON
        :param data_profile: 数据画像JSON
        :param executed_tasks: 已执行的任务列表
        :return: (数据发现列表, 行动建议列表)
        """
        self._last_stats_results = stats_results
        self._last_data_profile = data_profile
        self._last_executed_tasks = executed_tasks
        self._last_distinctive_features = distinctive_features or {}
        context = domain_context or detect_domain_context(data_profile)
        if self.offline_mode:
            return self._load_offline_findings_suggestions(stats_results)

        sig_count = self._count_significant_results(stats_results)

        # 问题上下文
        problems_context = ""
        if discovered_problems:
            problems_context = "\n".join(
                f"- {p.title}（{p.description}）"
                for p in discovered_problems[:5]
            )
            problems_context = f"\n【Round 2 发现的问题】\n{problems_context}\n"

        evidence_table = self._build_evidence_table(stats_results, distinctive_features)
        compact_features = (distinctive_features or {}).get("features", [])[:15]
        prompt = f"""
你是一位严谨的数据分析专家。请根据以下统计结果和问题发现，生成主要数据发现和行动建议。

【数据领域】
{json.dumps(context, ensure_ascii=False, indent=2)}

【数据画像】
{json.dumps(data_profile, ensure_ascii=False, indent=2)[:2000]}

【已执行任务数】{len(executed_tasks)}

【统计结果】
预扫描发现 {sig_count} 个统计显著（p<0.05）的结果。

【特色信号候选】
{json.dumps(compact_features, ensure_ascii=False, indent=2)}

【第二轮识别的问题】
{json.dumps([item.model_dump() for item in (discovered_problems or [])], ensure_ascii=False, indent=2)}

【可引用证据表】
{json.dumps(evidence_table, ensure_ascii=False, indent=2)}

【绝对禁止】
1. 禁止编造任何数据，所有结论必须严格基于提供的统计结果
2. 禁止将相关性表述为因果关系，必须使用"相关"而非"导致"
3. 禁止引用p≥0.05的结果作为显著发现
4. 禁止添加任何没有数据支撑的主观臆断
5. 禁止使用"可能"、"大概"等模糊词汇
6. 禁止使用“带动”“侵蚀”“影响”等因果式措辞解释相关系数；应写成“伴随”“线性解释力有限”或“对极端值敏感”
7. 禁止在建议中自行设定证据未提供的目标比例、阈值、增长率、折扣上限或金额

【要求】
1. 每个发现必须引用具体的统计量和p值，例如："模块A的平均难度显著高于其他模块（F=4.23, p=0.023）"
2. 主要发现筛选最有价值的5-8条，按重要性从高到低排序
3. 行动建议必须与数据发现一一对应，每条建议要有明确的数据依据和可落地的改进方向
4. 每条发现和建议都必须填写 source_stat_keys，且只能使用【可引用证据表】中的 stat_key
5. 如证据表中有 source_task_id，也应填写 source_task_ids
6. 当【特色信号候选】证据清晰时，主要发现中至少优先纳入2条能体现数据特点的发现
7. 描述性特色信号不要写成“显著”，除非该证据包含 p<0.05；可使用“明显”“值得关注”“呈现反差”等稳健表述
8. 除非当前领域是教育问卷，否则不得出现学生、课程、教师、老师、教学、课堂、问卷等措辞
9. 若第二轮问题包含数据质量风险，主要发现和建议中必须各保留至少一条对应内容
10. 输出必须严格符合指定的JSON格式，不能有任何额外的解释或markdown标记
"""
        messages = self._build_step_messages("findings_suggestions", prompt)
        try:
            response = self._call_with_retry(messages, response_format=FindingsAndSuggestionsResponse)
            parsed = response.choices[0].message.parsed
            self._normalize_finding_refs(parsed.findings, parsed.suggestions, evidence_table)
            parsed.findings, parsed.suggestions = self._ensure_critical_finding_coverage(
                parsed.findings,
                parsed.suggestions,
                distinctive_features or {},
            )
            self._sanitize_action_suggestions(parsed.suggestions, distinctive_features or {})
            self._record_call("findings_suggestions", success=True)
            return parsed.findings, parsed.suggestions
        except Exception as exc:
            self._record_call("findings_suggestions", success=False, error=str(exc))
            raise

    def polish_report_content(
        self,
        data_profile: Dict[str, Any],
        stats_results: Dict[str, Any],
        findings: List[DataFinding],
        suggestions: List[ActionSuggestion],
        chart_metadata: Dict[str, Any],
        domain_context: Dict[str, Any],
        user_requirement: str,
    ) -> ReportWritingResponse:
        """第四轮：在不改变证据的前提下完成报告语言与结构化写作。"""
        if self.offline_mode:
            return ReportWritingResponse(
                title=domain_context.get("report_title", "数据分析报告"),
                subtitle=domain_context.get("report_subtitle", "主要发现与行动建议"),
                executive_summary=f"本报告基于{data_profile.get('meta', {}).get('n_rows', '?')}条记录，聚焦主要发现、图表证据与行动建议。",
                overview_paragraphs=["数据概览以自然语言说明样本、字段和质量边界。"],
                chart_section_intro="本节结合关键数据、主要发现和统计方法解读图表。",
                findings=findings,
                suggestions=suggestions,
                limitations=["统计关联不等同于因果关系，结论应结合实际场景复核。"],
            )

        prompt = f"""
你是一位正式分析报告的资深编辑。请完成最后一轮报告写作与语言润色。

【数据领域】
{json.dumps(domain_context, ensure_ascii=False, indent=2)}
【用户需求】
{user_requirement}
【数据画像摘要】
{json.dumps(data_profile, ensure_ascii=False, indent=2)}
【图表元数据】
{json.dumps(chart_metadata, ensure_ascii=False, indent=2)}
【已验证发现】
{json.dumps([item.model_dump() for item in findings], ensure_ascii=False, indent=2)}
【已验证建议】
{json.dumps([item.model_dump() for item in suggestions], ensure_ascii=False, indent=2)}

【不可违反的事实约束】
1. 只能润色和组织，不能新增、删除或修改统计数字、p值、方法和证据含义。
2. findings/suggestions 中的 source_stat_keys 与 source_task_ids 必须逐项原样保留。
3. 不得把相关关系写成因果关系，不得把不显著结果写成显著。
4. 全文服从当前数据领域；除非领域本身是教育问卷，否则不得出现学生、课程、教师、老师、教学、课堂、问卷等措辞。
5. 数据概览写成自然段，不罗列生成时间、分析主题等机械元数据。
6. 行文正式、简洁、结论优先，输出严格符合JSON结构。
7. 不得在建议中新增原建议证据没有出现的数字目标、阈值、比例或金额。
"""
        try:
            response = self._call_with_retry(
                self._build_step_messages("report_writing", prompt),
                response_format=ReportWritingResponse,
            )
            narrative = response.choices[0].message.parsed
            self._preserve_evidence_refs(narrative, findings, suggestions)
            self._sanitize_narrative_language(narrative)
            self._record_call("report_writing", success=True)
            return narrative
        except Exception as exc:
            self._record_call("report_writing", success=False, error=str(exc))
            raise

    @staticmethod
    def _ensure_critical_problem_coverage(
        problems: List[DiscoveredProblem],
        distinctive_features: Dict[str, Any],
        valid_rows: Dict[str, Dict[str, Any]],
    ) -> List[DiscoveredProblem]:
        """保证最高优先级特色信号不会被模型排序遗漏。"""
        referenced = {key for problem in problems for key in problem.source_stat_keys}
        features = sorted(
            distinctive_features.get("features", []),
            key=lambda item: float(item.get("score") or 0),
            reverse=True,
        )
        additions: List[DiscoveredProblem] = []
        required_count = min(5, len(features))
        for feature in features[:required_count]:
            source_key = feature.get("source_key")
            if not source_key or source_key in referenced or source_key not in valid_rows:
                continue
            additions.append(
                DiscoveredProblem(
                    title=feature.get("title") or "高优先级特色信号",
                    description=feature.get("finding") or feature.get("evidence") or "该信号需要优先复核。",
                    importance=5,
                    source_stat_keys=[source_key],
                    source_task_ids=[],
                )
            )
            referenced.add(source_key)
        return (additions + problems)[:8]

    @classmethod
    def _ensure_critical_finding_coverage(
        cls,
        findings: List[DataFinding],
        suggestions: List[ActionSuggestion],
        distinctive_features: Dict[str, Any],
    ) -> tuple[List[DataFinding], List[ActionSuggestion]]:
        """把代码已确认的最高优先级特色信号保留到最终证据链。"""
        features = sorted(
            distinctive_features.get("features", []),
            key=lambda item: float(item.get("score") or 0),
            reverse=True,
        )
        finding_refs = {key for item in findings for key in item.source_stat_keys}
        for feature in reversed(features[:2]):
            source_key = feature.get("source_key")
            if not source_key or source_key in finding_refs:
                continue
            findings.insert(
                0,
                DataFinding(
                    conclusion=feature.get("finding") or feature.get("title") or "发现高优先级特色信号。",
                    evidence=feature.get("evidence") or "结构化特色信号证据。",
                    method=feature.get("method", "特色信号挖掘"),
                    importance=5,
                    source_stat_keys=[source_key],
                    source_task_ids=[],
                ),
            )
            finding_refs.add(source_key)
        findings = findings[:8]

        critical_features = [item for item in features if item.get("feature_type") == "date_quality_risk"]
        suggestion_refs = {key for item in suggestions for key in item.source_stat_keys}
        for feature in critical_features[:1]:
            source_key = feature.get("source_key")
            if not source_key or source_key in suggestion_refs:
                continue
            suggestion_text, direction = cls._suggestion_from_distinctive_feature(feature)
            suggestions.insert(
                0,
                ActionSuggestion(
                    suggestion=suggestion_text,
                    evidence=feature.get("finding") or feature.get("evidence") or "日期质量风险需要先处理。",
                    direction=direction,
                    source_stat_keys=[source_key],
                    source_task_ids=[],
                ),
            )
        return findings, suggestions[:5]

    @classmethod
    def _sanitize_action_suggestions(
        cls,
        suggestions: List[ActionSuggestion],
        distinctive_features: Dict[str, Any],
    ) -> None:
        """移除没有在对应证据中出现的模型自设数字目标。"""
        feature_by_key = {
            feature.get("source_key"): feature
            for feature in distinctive_features.get("features", [])
            if feature.get("source_key")
        }
        for suggestion in suggestions:
            allowed = cls._number_tokens(suggestion.evidence)
            proposed = cls._number_tokens(f"{suggestion.suggestion} {suggestion.direction}")
            if proposed <= allowed:
                continue
            feature = next(
                (feature_by_key[key] for key in suggestion.source_stat_keys if key in feature_by_key),
                None,
            )
            if feature:
                suggestion.suggestion, suggestion.direction = cls._suggestion_from_distinctive_feature(feature)
            else:
                suggestion.suggestion = "围绕该发现建立分组复核与持续监测机制"
                suggestion.direction = "先核对证据对应的分组和指标，再根据后续验证结果设定执行阈值"

    @staticmethod
    def _number_tokens(text: str) -> set[str]:
        import re

        tokens = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?%?", str(text))
        return {token.replace(",", "").rstrip("%") for token in tokens}

    @staticmethod
    def _sanitize_narrative_language(narrative: ReportWritingResponse) -> None:
        """把因果式相关表述降级为统计证据允许的关联语言。"""
        def clean(text: str) -> str:
            replacements = {
                "折扣让利侵蚀利润，却未能换取销量提升": "较高折扣同时伴随较低利润，而与销售额的线性关联接近于零",
                "折扣对销售额的拉动效应微弱": "折扣率与销售额的线性关联极弱",
                "折扣策略未有效促进销售增长": "折扣率与销售额未呈正向线性关联",
                "少数大额交易对整体指标产生显著拉动": "少数大额交易对总体指标贡献较大",
                "针对折扣率与销售额无正向关联的商品分组": "针对折扣率与销售额未呈正向线性关联的现象",
                "逐步取消或降低无效折扣": "识别并复核未改善销售表现的折扣",
                "折扣率与销售额未呈正向线性关联，折扣率与销售额的线性关联几乎为零": "折扣率与销售额的线性关联几乎为零",
                "无效折扣退出": "折扣有效性复核",
                "折扣未有效促进销量，却伴随利润率的降低": "折扣率与销售额的线性关联接近于零，并与较低利润同时出现",
                "减少无效折扣对利润的侵蚀": "减少高折扣与低利润同时出现的风险",
                "真正能拉动销量或利润": "具有更好销售或利润表现",
                "说明区域间利润率差异更源自品类结构、折扣水平或销量规模的差异，而非单笔订单盈利能力的固有差别": "提示还需进一步检验品类结构、折扣水平和销量规模能否解释区域利润率差异",
                "说明区域间利润率差异更可能源自品类结构、折扣水平或销量规模的差异，而非单笔订单盈利能力的固有差别": "提示还需进一步检验品类结构、折扣水平和销量规模能否解释区域利润率差异",
                "表明差距源自品类结构、折扣水平和销量规模的区域分布不同": "提示应进一步检验品类结构、折扣水平和销量规模对区域差异的解释程度",
                "侵蚀利润": "与较低利润同时出现",
                "带动利润增长": "单独解释利润增长",
                "识别导致亏损的共性因素": "识别与亏损同时出现的共性特征",
                "表明其利润创造效率存在系统性缺陷": "提示其利润结构值得进一步诊断",
                "品类对利润影响显著": "不同品类的利润均值差异显著",
                "该数据质量问题将直接影响任何基于时间的业务分析": "该日期字段在修复前不适用于基于时间的业务分析",
                "表明“薄利多销”的假设在本经营环境不成立，单纯提高销量并非提升利润的有效路径": "说明销售数量单一指标对利润的线性解释力有限，非线性或分组关系仍需进一步检验",
            }
            result = str(text)
            for old, new in replacements.items():
                result = result.replace(old, new)
            return result

        narrative.executive_summary = clean(narrative.executive_summary)
        narrative.overview_paragraphs = [clean(text) for text in narrative.overview_paragraphs]
        narrative.chart_section_intro = clean(narrative.chart_section_intro)
        narrative.limitations = [clean(text) for text in narrative.limitations]
        for finding in narrative.findings:
            finding.conclusion = clean(finding.conclusion)
            finding.evidence = clean(finding.evidence)
            if any(phrase in finding.conclusion for phrase in ["不显著", "无显著", "未达显著", "未达到显著"]):
                finding.conclusion = finding.conclusion.replace("显著偏低", "汇总值偏低").replace("显著偏高", "汇总值偏高")
        for suggestion in narrative.suggestions:
            suggestion.suggestion = clean(suggestion.suggestion)
            suggestion.evidence = clean(suggestion.evidence)
            suggestion.direction = clean(suggestion.direction)

    @staticmethod
    def _preserve_evidence_refs(
        narrative: ReportWritingResponse,
        findings: List[DataFinding],
        suggestions: List[ActionSuggestion],
    ) -> None:
        """第四轮无权改变证据引用；数量不一致时保留原始条目。"""
        if len(narrative.findings) != len(findings):
            narrative.findings = findings
        else:
            for polished, original in zip(narrative.findings, findings):
                polished.source_stat_keys = list(original.source_stat_keys)
                polished.source_task_ids = list(original.source_task_ids)
                polished.evidence = original.evidence
                polished.method = original.method
                if not LLMClient._number_tokens(polished.conclusion) <= LLMClient._number_tokens(
                    f"{original.conclusion} {original.evidence}"
                ):
                    polished.conclusion = original.conclusion
        if len(narrative.suggestions) != len(suggestions):
            narrative.suggestions = suggestions
        else:
            for polished, original in zip(narrative.suggestions, suggestions):
                polished.source_stat_keys = list(original.source_stat_keys)
                polished.source_task_ids = list(original.source_task_ids)
                polished.evidence = original.evidence
                if not LLMClient._number_tokens(
                    f"{polished.suggestion} {polished.direction}"
                ) <= LLMClient._number_tokens(original.evidence):
                    polished.suggestion = original.suggestion
                    polished.direction = original.direction

    def _load_offline_questions(self) -> List[CandidateQuestion]:
        """基于真实数据画像启发式生成候选问题（离线模式）。"""
        logger.info("离线模式：基于数据画像自动生成候选问题")
        context = detect_domain_context(self._last_data_profile)
        registry = build_planning_field_map(self._last_data_profile, context)
        pool = build_candidate_task_pool(self._last_data_profile, registry, domain_context=context)
        selections = [
            CandidateTaskSelection(task_pool_id=item["task_pool_id"], value=item.get("value", ""), priority=3)
            for item in pool.get("tasks", [])[:12]
        ]
        return self._questions_from_task_pool(pool, selections)

    def _load_offline_findings_suggestions(self) -> tuple[List[DataFinding], List[CourseSuggestion]]:
        """基于真实统计结果启发式生成发现和建议（离线模式）。"""
        logger.info("离线模式：基于统计结果自动生成发现和建议")
        return self._generate_offline_findings_suggestions(
            self._last_stats_results,
            self._last_data_profile,
            self._last_executed_tasks,
            self._last_distinctive_features,
        )

    # ------------------------------
    # 离线模式：基于真实输入的启发式生成
    # ------------------------------
    _last_data_profile: Dict[str, Any] = {}
    _last_stats_results: Dict[str, Any] = {}
    _last_executed_tasks: List[Dict[str, Any]] = []
    _last_distinctive_features: Dict[str, Any] = {}

    def _generate_offline_questions_from_profile(self, data_profile: Dict[str, Any]) -> List[CandidateQuestion]:
        context = detect_domain_context(data_profile)
        fields = data_profile.get("fields", [])
        column_info = {f["column"]: f for f in fields}
        numeric_cols = [
            f["column"] for f in fields
            if f.get("inferred_type") in ["numeric_continuous", "numeric_discrete"]
        ]
        numeric_cols = [c for c in numeric_cols if self._is_meaningful_numeric_column(c)]
        categorical_cols = [
            f["column"] for f in fields
            if f.get("inferred_type") == "categorical"
        ]
        categorical_cols = [c for c in categorical_cols if self._is_meaningful_categorical_column(c, column_info)]
        binary_cats = [c for c in categorical_cols if column_info[c].get("unique") == 2]
        multi_cats = [c for c in categorical_cols if column_info[c].get("unique", 0) >= 3]

        metric_keywords = context.get("metric_keywords", [])
        group_keywords = context.get("group_keywords", [])
        preferred_numeric = [
            c for c in numeric_cols
            if any(keyword in str(c) for keyword in metric_keywords)
        ]
        if preferred_numeric:
            numeric_cols = preferred_numeric + [c for c in numeric_cols if c not in preferred_numeric]

        preferred_cats = [
            c for c in categorical_cols
            if any(keyword in str(c) for keyword in group_keywords)
        ]
        if preferred_cats:
            categorical_cols = preferred_cats + [c for c in categorical_cols if c not in preferred_cats]
            binary_cats = [c for c in categorical_cols if column_info[c].get("unique") == 2]
            multi_cats = [c for c in categorical_cols if column_info[c].get("unique", 0) >= 3]

        def label(col: str) -> str:
            return self._humanize_column_name(col)

        questions: List[CandidateQuestion] = []

        for cat in multi_cats[:4]:
            for num in numeric_cols[:5]:
                questions.append(CandidateQuestion(
                    question=f"不同{label(cat)}分组的“{label(num)}”是否存在显著差异？",
                    variables=[num, cat],
                    method="ANOVA",
                    value="识别多分组之间的指标差异，为差异化行动提供依据"
                ))

        for cat in binary_cats[:4]:
            for num in numeric_cols[:5]:
                questions.append(CandidateQuestion(
                    question=f"两个{label(cat)}分组的“{label(num)}”均值是否存在显著差异？",
                    variables=[num, cat],
                    method="t检验",
                    value="识别二元群体差异，为更有针对性的支持策略提供依据"
                ))

        for left_idx, left in enumerate(categorical_cols[:6]):
            for right in categorical_cols[left_idx + 1: left_idx + 6]:
                questions.append(CandidateQuestion(
                    question=f"{label(left)}与{label(right)}之间是否存在显著关联？",
                    variables=[left, right],
                    method="卡方检验",
                    value="了解分类变量之间的结构性关系"
                ))

        for left_idx, left in enumerate(numeric_cols[:4]):
            for right in numeric_cols[left_idx + 1: left_idx + 4]:
                questions.append(CandidateQuestion(
                    question=f"“{label(left)}”与“{label(right)}”之间是否存在显著线性相关？",
                    variables=[left, right],
                    method="相关性分析",
                    value="识别数值指标之间的联动关系，提炼关键结构"
                ))

        for num in numeric_cols[:3]:
            questions.append(CandidateQuestion(
                question=f"“{label(num)}”的分布是否满足正态性假设？",
                variables=[num],
                method="分布检验",
                value="为后续选择参数检验还是非参数检验提供依据"
            ))

        deduped: List[CandidateQuestion] = []
        seen = set()
        for q in questions:
            key = (tuple(q.variables), q.method)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(q)
        return deduped[:18]

    def _generate_offline_findings_suggestions(
        self,
        stats_results: Dict[str, Any],
        data_profile: Dict[str, Any],
        executed_tasks: List[Dict[str, Any]],
        distinctive_features: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[DataFinding], List[CourseSuggestion]]:
        findings: List[DataFinding] = []
        suggestions: List[CourseSuggestion] = []

        task_map = {task.get("task_id"): task for task in executed_tasks}
        distinctive_by_key = {
            item.get("source_key"): item
            for item in (distinctive_features or {}).get("features", [])
            if isinstance(item, dict) and item.get("source_key")
        }

        def add_finding(
            conclusion: str,
            evidence: str,
            method: str,
            importance: int,
            *,
            source_stat_key: Optional[str] = None,
            source_task_id: Optional[int] = None,
        ) -> None:
            if not conclusion or not evidence:
                return
            if any(item.conclusion == conclusion for item in findings):
                return
            findings.append(DataFinding(
                conclusion=conclusion,
                evidence=evidence,
                method=method,
                importance=importance,
                source_stat_keys=[source_stat_key] if source_stat_key else [],
                source_task_ids=[source_task_id] if source_task_id is not None else [],
            ))

        hypothesis_tests = stats_results.get("hypothesis_tests", {}).get("tests", {})
        for test_name, item in hypothesis_tests.items():
            if not isinstance(item, dict):
                continue
            p_val = item.get("p_value")
            if not isinstance(p_val, (int, float)) or p_val >= Config.SIGNIFICANCE_THRESHOLD:
                continue
            variables = item.get("variables") or [
                item.get("numeric_column"), item.get("grouping_column")
            ]
            variables = [v for v in variables if v]
            readable_vars = "与".join(self._humanize_column_name(v) for v in variables)
            stat = (
                item.get("t_statistic")
                or item.get("chi2_statistic")
                or item.get("correlation_coefficient")
                or item.get("statistic")
            )
            method = item.get("method", "假设检验")
            if "相关" in method:
                conclusion = f"{readable_vars}之间存在统计显著的线性相关关系"
            elif "卡方" in method:
                conclusion = f"{readable_vars}之间存在统计显著的结构性关联"
            else:
                conclusion = f"围绕 {readable_vars} 的组间差异达到统计显著水平"
            evidence = self._format_evidence(method, stat, p_val)
            add_finding(
                conclusion,
                evidence,
                method,
                4,
                source_stat_key=f"hypothesis_tests.{test_name}",
                source_task_id=self._task_id_from_key(test_name),
            )

        anova_tests = stats_results.get("anova", {}).get("tests", {})
        for _name, item in anova_tests.items():
            if not isinstance(item, dict):
                continue
            p_val = item.get("p_value")
            if not isinstance(p_val, (int, float)) or p_val >= Config.SIGNIFICANCE_THRESHOLD:
                continue
            dependent = self._humanize_column_name(item.get("dependent", "相关指标"))
            factor = self._humanize_column_name(item.get("factor", "相关分组"))
            f_stat = item.get("F_statistic")
            add_finding(
                f"不同{factor}分组的“{dependent}”存在显著差异",
                self._format_evidence(item.get("method", "ANOVA"), f_stat, p_val, stat_label="F"),
                item.get("method", "单因素方差分析"),
                5,
                source_stat_key=f"anova.{_name}",
                source_task_id=self._task_id_from_key(_name),
            )

        dist_tests = stats_results.get("distribution_tests", {}).get("tests", {})
        for col, item in list(dist_tests.items())[:4]:
            if not isinstance(item, dict):
                continue
            shapiro = item.get("shapiro_wilk", {})
            if isinstance(shapiro, dict):
                p_val = shapiro.get("p_value")
                if isinstance(p_val, (int, float)) and p_val < Config.SIGNIFICANCE_THRESHOLD:
                    stat = shapiro.get("statistic")
                    add_finding(
                        f"“{self._humanize_column_name(col)}”的分布显著偏离正态",
                        self._format_evidence("Shapiro-Wilk 正态性检验", stat, p_val, stat_label="W"),
                        "分布检验",
                        3,
                        source_stat_key=f"distribution_tests.{col}",
                    )

        for feature in self._select_distinctive_features_for_findings(
            (distinctive_features or {}).get("features", [])
        ):
            if len(findings) >= 6:
                break
            source_key = feature.get("source_key")
            finding_text = feature.get("finding") or feature.get("title")
            evidence_text = feature.get("evidence")
            if not source_key or not finding_text or not evidence_text:
                continue
            add_finding(
                finding_text,
                evidence_text,
                feature.get("method", "特色信号挖掘"),
                5 if (feature.get("score") or 0) >= 80 else 4,
                source_stat_key=source_key,
            )

        if len(findings) < 5:
            point_fields = stats_results.get("point_estimation", {}).get("fields", {})
            sorted_points = sorted(
                [
                    (col, item)
                    for col, item in point_fields.items()
                    if isinstance(item, dict) and "error" not in item and isinstance(item.get("mean"), (int, float))
                ],
                key=lambda pair: (
                    -self._priority_metric_score(pair[0]),
                    -float(pair[1].get("mean") or 0),
                    self._humanize_column_name(pair[0]),
                ),
            )
            for col, item in sorted_points:
                if len(findings) >= 5:
                    break
                mean = float(item.get("mean"))
                n = item.get("n")
                label = self._humanize_column_name(col)
                add_finding(
                    f"“{label}”的平均值为 {mean:.2f}，可作为后续分析与行动的重要参考",
                    f"均值={mean:.4f}, n={n}",
                    "点估计",
                    3,
                    source_stat_key=f"point_estimation.{col}",
                )

        findings = sorted(findings, key=lambda x: x.importance, reverse=True)[:6]

        for finding in findings[:5]:
            conclusion = finding.conclusion
            source_key = finding.source_stat_keys[0] if finding.source_stat_keys else ""
            distinctive_feature = distinctive_by_key.get(source_key)
            if distinctive_feature:
                suggestion_text, direction = self._suggestion_from_distinctive_feature(distinctive_feature)
            elif "显著差异" in conclusion:
                suggestion_text = "围绕显著差异对应的分组制定差异化行动策略"
                direction = "先识别不同组别的指标差距，再在资源、流程和跟踪频率上作差异化安排"
            elif "结构性关联" in conclusion:
                suggestion_text = "将存在显著关联的分类变量纳入后续监测"
                direction = "把相关变量组合成观察维度，在后续数据更新中持续跟踪变化趋势"
            elif "线性相关" in conclusion:
                suggestion_text = "把强相关指标作为联动改进对象，避免只优化单一维度"
                direction = "优先同时调整关联度高的题项或能力维度，观察是否带来整体评分提升"
            elif "平均评分" in conclusion:
                suggestion_text = "优先复核平均值较高的指标及其业务含义"
                direction = "将高值指标与分组结构结合观察，确认其稳定性和行动价值"
            else:
                suggestion_text = "针对非正态或分布异常的指标补充更细致的分层观察"
                direction = "检查是否存在离群群体、极端评分或量表理解偏差，并在后续分析中优先采用稳健统计方法"

            suggestions.append(CourseSuggestion(
                suggestion=suggestion_text,
                evidence=conclusion,
                direction=direction,
                source_stat_keys=finding.source_stat_keys,
                source_task_ids=finding.source_task_ids,
            ))

        if not suggestions:
            suggestions.append(CourseSuggestion(
                suggestion="优先复核波动较大和分组差异明显的指标",
                evidence="当前统计结果中可直接形成行动建议的显著发现较少",
                direction="结合图表和描述统计，先聚焦均值异常、离散度偏高的指标进行人工复核"
            ))

        return findings, suggestions[:5]

    @staticmethod
    def _select_distinctive_features_for_findings(features: List[Dict[str, Any]], limit: int = 4) -> List[Dict[str, Any]]:
        selected: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()

        def add_first(feature_type: str) -> None:
            if len(selected) >= limit:
                return
            for feature in features:
                source_key = feature.get("source_key")
                if feature.get("feature_type") == feature_type and source_key and source_key not in seen_keys:
                    selected.append(feature)
                    seen_keys.add(source_key)
                    return

        add_first("group_difference")
        for feature_type in [
            "hot_hard_crowded",
            "high_value_low_conversion",
            "easy_but_crowded",
            "underrecognized_opportunity",
            "polarized_interest",
        ]:
            add_first(feature_type)

        for feature in features:
            if len(selected) >= limit:
                break
            source_key = feature.get("source_key")
            if source_key and source_key not in seen_keys:
                selected.append(feature)
                seen_keys.add(source_key)

        return selected

    @staticmethod
    def _suggestion_from_distinctive_feature(feature: Dict[str, Any]) -> tuple[str, str]:
        feature_type = feature.get("feature_type")
        sector = feature.get("sector", "相关赛道")
        if feature_type == "loss_exposure":
            return (
                "建立亏损记录分层复核清单",
                "按品类、折扣和区域拆分亏损记录，优先复核亏损占比高且销售规模较大的分组",
            )
        if feature_type == "discount_profit_relationship":
            return (
                "将折扣与利润纳入联合监控",
                "按折扣区间跟踪销售额、利润和亏损率，识别需要调整的折扣策略",
            )
        if feature_type == "group_margin_contrast":
            return (
                "针对利润率分化制定分组行动方案",
                "分别复核高利润率与低利润率分组的销售结构、折扣和产品组合",
            )
        if feature_type == "date_quality_risk":
            return (
                "修复日期口径后再开展时序分析",
                "核对订单日期和发货日期的源字段编码，完成异常日期修复与抽样验证",
            )
        if feature_type == "high_value_low_conversion":
            return (
                f"围绕{sector}设置价值场景与可行路径拆解任务",
                "先明确应用对象、真实约束和低门槛切入点，再评估方案与现有能力的连接方式",
            )
        if feature_type == "hot_hard_crowded":
            return (
                f"将{sector}作为高阶挑战案例并配套技术分层材料",
                "把技术难点、竞争格局和差异化定位拆成可验证的问题，避免只停留在热门概念介绍",
            )
        if feature_type == "easy_but_crowded":
            return (
                f"用{sector}训练细分需求和差异化定位",
                "比较同类方案、用户场景和产品边界，再选择更具体的行动切口",
            )
        if feature_type == "underrecognized_opportunity":
            return (
                f"为{sector}补充应用案例和需求访谈材料",
                "先补充真实使用场景证据，再进入机会判断和方案构思",
            )
        if feature_type == "group_difference":
            return (
                "按显著差异对应的分组配置行动入口",
                "分别复核高值组与低值组的特征，形成更有针对性的支持措施",
            )
        return (
            f"围绕{sector}补充一页数据证据卡片",
            "将该信号对应的均值、差距和样本说明纳入决策材料，支持基于数据选择行动方向",
        )

    @staticmethod
    def _format_evidence(method: str, statistic: Any, p_val: float, stat_label: Optional[str] = None) -> str:
        if stat_label is None:
            if "方差" in method or method == "ANOVA":
                stat_label = "F"
            elif "卡方" in method:
                stat_label = "χ²"
            elif "相关" in method:
                stat_label = "r"
            elif "Shapiro" in method:
                stat_label = "W"
            else:
                stat_label = "t"
        if isinstance(statistic, (int, float)):
            return f"{stat_label}={statistic:.4f}, p={p_val:.4f}"
        return f"p={p_val:.4f}"

    @staticmethod
    def _humanize_column_name(column: str) -> str:
        return humanize_column_name(column)

    @staticmethod
    def _is_meaningful_numeric_column(column: str) -> bool:
        text = str(column)
        blocked_keywords = ["序号", "提交答卷时间", "所用时间", "来源", "来源详情"]
        return not any(keyword in text for keyword in blocked_keywords)

    @staticmethod
    def _is_meaningful_categorical_column(column: str, column_info: Dict[str, Any]) -> bool:
        text = str(column)
        if any(keyword in text for keyword in ["来源详情", "提交答卷时间"]):
            return False
        unique = column_info.get(column, {}).get("unique", 0)
        return 2 <= unique <= 12

    def _priority_metric_score(self, column: str) -> int:
        text = str(column)
        context = detect_domain_context(self._last_data_profile)
        priority_keywords = context.get("metric_keywords", [])
        for index, keyword in enumerate(priority_keywords):
            if keyword in text:
                return len(priority_keywords) - index
        return 0
