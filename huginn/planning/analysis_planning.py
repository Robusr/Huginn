# -*- coding: utf-8 -*-
"""Deterministic planning helpers for analysis task generation.

The LLM should rank and explain valid analysis tasks, not invent column names.
This module builds a compact field registry and an executable task pool from
``data_profile.json`` so downstream model calls can refer to stable IDs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from huginn.core.config import Config
from huginn.domain.context import detect_domain_context, domain_keywords, is_identifier_or_noise
from huginn.core.label_utils import humanize_column_name


NOISE_KEYWORDS = ["序号", "提交答卷时间", "所用时间", "来源", "来源详情"]


def build_planning_field_map(
    data_profile: Dict[str, Any],
    domain_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a stable registry of usable fields from a data profile."""
    rows: List[Dict[str, Any]] = []
    n_rows = int(data_profile.get("meta", {}).get("n_rows") or 0)
    for field in data_profile.get("fields", []):
        column = field.get("column")
        if not column or is_identifier_or_noise(column, field, n_rows):
            continue
        inferred_type = field.get("inferred_type", "")
        if inferred_type == "datetime":
            continue

        field_id = f"F{len(rows) + 1:03d}"
        unique = int(field.get("unique") or 0)
        methods = _available_methods(inferred_type, unique)
        if not methods:
            continue

        rows.append(
            {
                "field_id": field_id,
                "column": column,
                "label": humanize_column_name(column),
                "inferred_type": inferred_type,
                "unique": unique,
                "valid_n": _field_count(field, data_profile),
                "available_methods": methods,
                "roles": _available_roles(inferred_type, unique),
            }
        )

    return {
        "fields": rows,
        "field_id_to_column": {item["field_id"]: item["column"] for item in rows},
        "column_to_field_id": {item["column"]: item["field_id"] for item in rows},
    }


def build_candidate_task_pool(
    data_profile: Dict[str, Any],
    field_registry: Optional[Dict[str, Any]] = None,
    *,
    max_tasks: int = 48,
    domain_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build executable candidate tasks with real columns and stable pool IDs."""
    context = domain_context or detect_domain_context(data_profile)
    registry = field_registry or build_planning_field_map(data_profile, context)
    fields = registry.get("fields", [])
    by_column = {item["column"]: item for item in fields}

    numeric = _sort_fields(
        [f for f in fields if _is_numeric_type(f.get("inferred_type", ""))],
        domain_keywords(context, "metric_keywords"),
    )
    categorical = _sort_fields(
        [f for f in fields if f.get("inferred_type") == "categorical"],
        domain_keywords(context, "group_keywords"),
    )
    binary_cats = [f for f in categorical if f.get("unique") == 2]
    multi_cats = [f for f in categorical if 3 <= f.get("unique", 0) <= Config.ANALYSIS_MAX_GROUPS]

    tasks: List[Dict[str, Any]] = []

    def add_task(method: str, variables: List[str], value: str, priority: int) -> None:
        if len(tasks) >= max_tasks:
            return
        if any(var not in by_column for var in variables):
            return
        if _task_exists(tasks, method, variables):
            return

        task_id = f"T{len(tasks) + 1:03d}"
        labels = [by_column[var]["label"] for var in variables]
        if method == "ANOVA":
            question = f"不同{labels[1]}分组的“{labels[0]}”是否存在显著差异？"
        elif method == "t检验":
            question = f"两个{labels[1]}分组的“{labels[0]}”均值是否存在显著差异？"
        elif method == "卡方检验":
            question = f"{labels[0]}与{labels[1]}之间是否存在显著关联？"
        elif method == "相关性分析":
            question = f"“{labels[0]}”与“{labels[1]}”之间是否存在显著线性相关？"
        elif method == "配对t检验":
            question = f"“{labels[0]}”与“{labels[1]}”的配对均值是否存在显著差异？"
        else:
            question = f"“{labels[0]}”的分布是否符合正态分布？"

        tasks.append(
            {
                "task_pool_id": task_id,
                "question": question,
                "variables": variables,
                "variable_ids": [by_column[var]["field_id"] for var in variables],
                "variable_labels": labels,
                "method": method,
                "value": value,
                "priority": priority,
            }
        )

    for cat in multi_cats[:4]:
        for num in numeric[:4]:
            add_task("ANOVA", [num["column"], cat["column"]], "识别多分组指标差异，支持针对性决策。", 90)

    for left, right in _pairs(categorical[:10], limit=12):
        add_task("卡方检验", [left["column"], right["column"]], "识别分类变量之间的结构性关联。", 80)

    for cat in binary_cats[:6]:
        for num in numeric[:8]:
            add_task("t检验", [num["column"], cat["column"]], "识别两个分组的指标差异，支持针对性决策。", 75)

    for left, right in _pairs(numeric[:8], limit=10):
        add_task("相关性分析", [left["column"], right["column"]], "识别数值指标之间的联动关系。", 60)

    if context.get("domain") == "education_survey":
        for left, right in _pairs(numeric[:6], limit=4):
            add_task("配对t检验", [left["column"], right["column"]], "比较同一批观测中两个同量纲指标的均值差异。", 55)

    for num in numeric[:8]:
        add_task("分布检验", [num["column"]], "判断核心数值指标的分布特征。", 45)

    tasks = sorted(tasks, key=lambda item: item["priority"], reverse=True)
    for index, task in enumerate(tasks, 1):
        task["task_pool_id"] = f"T{index:03d}"

    return {"tasks": tasks, "total_tasks": len(tasks)}


def save_planning_artifacts(
    output_dir: str | Path,
    field_registry: Dict[str, Any],
    task_pool: Dict[str, Any],
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    registry_path = output / "field_registry.json"
    pool_path = output / "candidate_task_pool.json"
    registry_path.write_text(json.dumps(field_registry, ensure_ascii=False, indent=2), encoding="utf-8")
    pool_path.write_text(json.dumps(task_pool, ensure_ascii=False, indent=2), encoding="utf-8")
    return registry_path, pool_path


def _field_count(field: Dict[str, Any], data_profile: Dict[str, Any]) -> int:
    stats = field.get("stats") or {}
    if isinstance(stats.get("count"), (int, float)):
        return int(stats["count"])
    n_rows = data_profile.get("meta", {}).get("n_rows")
    missing = field.get("missing_count", 0)
    if isinstance(n_rows, int):
        return max(0, n_rows - int(missing or 0))
    return 0


def _available_methods(inferred_type: str, unique: int) -> List[str]:
    if _is_numeric_type(inferred_type):
        return ["点估计", "区间估计", "分布检验", "相关性分析", "t检验", "ANOVA", "配对t检验"]
    if inferred_type == "categorical" and 2 <= unique <= Config.ANALYSIS_MAX_GROUPS:
        methods = ["卡方检验"]
        if unique == 2:
            methods.append("t检验")
        if 3 <= unique <= Config.ANALYSIS_MAX_GROUPS:
            methods.append("ANOVA")
        return methods
    return []


def _available_roles(inferred_type: str, unique: int) -> List[str]:
    if _is_numeric_type(inferred_type):
        return ["metric", "paired_metric"]
    if inferred_type == "categorical":
        roles = ["grouping", "chi_square_variable"]
        if unique == 2:
            roles.append("binary_grouping")
        if unique >= 3:
            roles.append("multi_grouping")
        return roles
    return []


def _is_numeric_type(inferred_type: str) -> bool:
    return inferred_type in {"numeric_continuous", "numeric_discrete"}


def _is_noise_column(column: str) -> bool:
    return is_identifier_or_noise(column)


def _sort_fields(fields: Iterable[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    def rank(field: Dict[str, Any]) -> tuple[int, int, str]:
        text = f"{field.get('column', '')} {field.get('label', '')}"
        for index, keyword in enumerate(keywords):
            if keyword in text:
                return index, -int(field.get("valid_n") or 0), str(field.get("label", ""))
        return len(keywords), -int(field.get("valid_n") or 0), str(field.get("label", ""))

    return sorted(fields, key=rank)


def _pairs(items: List[Dict[str, Any]], *, limit: int) -> List[tuple[Dict[str, Any], Dict[str, Any]]]:
    pairs: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
    for left_idx, left in enumerate(items):
        for right in items[left_idx + 1:]:
            pairs.append((left, right))
            if len(pairs) >= limit:
                return pairs
    return pairs


def _task_exists(tasks: List[Dict[str, Any]], method: str, variables: List[str]) -> bool:
    wanted = set(variables)
    return any(task.get("method") == method and set(task.get("variables", [])) == wanted for task in tasks)
