# -*- coding: utf-8 -*-
"""挖掘领域数据中的特色数据信号。

该模块不依赖模型生成分析问题，而是直接从原始 DataFrame 中识别赛道
评分矩阵、反差型模式和群体差异，用作第 7 步发现生成的结构化证据。
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

try:  # pragma: no cover - scipy 是否存在由运行环境决定
    from scipy import stats
except Exception:  # pragma: no cover
    stats = None

from huginn.core.label_utils import clean_choice, humanize_column_name


DIMENSION_ALIASES = {
    "消费者兴趣": "消费者兴趣",
    "技术难度认知": "技术难度",
    "技术难度": "技术难度",
    "专业契合度": "专业契合",
    "专业契合": "专业契合",
    "社会价值判断": "社会价值",
    "社会价值": "社会价值",
    "竞争激烈度判断": "竞争激烈",
    "竞争激烈": "竞争激烈",
    "总体机会判断": "总体机会",
    "总体机会": "总体机会",
    "创业意愿": "创业意愿",
}

QUESTION_DIMENSIONS = {
    "11": "消费者兴趣",
    "12": "技术难度",
    "13": "专业契合",
    "14": "社会价值",
    "15": "竞争激烈",
    "16": "总体机会",
    "17": "创业意愿",
}

NOISE_COLUMNS = ["序号", "提交", "所用时间", "来源", "详情"]


def mine_distinctive_features(
    df: pd.DataFrame,
    *,
    max_features: int = 30,
    domain_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """返回可写入报告的领域特色信号候选。"""
    domain = (domain_context or {}).get("domain")
    if domain == "retail_sales" or {"Sales", "Profit"}.issubset(df.columns):
        return _mine_retail_features(df, max_features=max_features)

    rating_columns = _extract_rating_columns(df)
    sector_matrix = _build_sector_matrix(df, rating_columns)
    sector_summary = _build_sector_summary(sector_matrix)

    features: List[Dict[str, Any]] = []
    features.extend(_mine_sector_pattern_features(sector_summary))
    features.extend(_mine_group_difference_features(df, rating_columns))

    features = _dedupe_features(features)
    features.sort(key=lambda item: item.get("score", 0), reverse=True)
    for index, feature in enumerate(features[:max_features], 1):
        feature["source_key"] = f"distinctive_features.F{index:03d}"

    selected = features[:max_features]
    return {
        "meta": {
            "n_rows": int(len(df)),
            "n_rating_fields": len(rating_columns),
            "n_sector_dimension_rows": len(sector_matrix),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "sector_matrix": sector_matrix,
        "sector_summary": sector_summary,
        "features": selected,
        "feature_type_counts": dict(Counter(item["feature_type"] for item in selected)),
    }


def _mine_retail_features(df: pd.DataFrame, *, max_features: int) -> Dict[str, Any]:
    """从销售、利润、折扣和品类结构中提取可追溯的经营信号。"""
    features: List[Dict[str, Any]] = []
    sales = pd.to_numeric(df.get("Sales"), errors="coerce")
    profit = pd.to_numeric(df.get("Profit"), errors="coerce")
    discount = pd.to_numeric(df.get("Discount"), errors="coerce") if "Discount" in df else None
    valid = sales.notna() & profit.notna()

    if valid.any():
        loss_rate = float((profit[valid] < 0).mean() * 100)
        total_sales = float(sales[valid].sum())
        total_profit = float(profit[valid].sum())
        margin = total_profit / total_sales * 100 if total_sales else 0.0
        features.append(
            {
                "feature_type": "loss_exposure",
                "title": "亏损订单占比与整体利润率",
                "finding": f"亏损记录占比为{loss_rate:.2f}%，整体利润率为{margin:.2f}%。",
                "evidence": f"销售额合计={total_sales:.2f}，利润合计={total_profit:.2f}，亏损记录占比={loss_rate:.2f}%。",
                "method": "经营指标描述统计",
                "score": min(100.0, 70 + loss_rate),
                "variables": ["Sales", "Profit"],
                "metrics": {"loss_rate_pct": round(loss_rate, 4), "overall_margin_pct": round(margin, 4)},
            }
        )

    if discount is not None:
        clean = pd.DataFrame({"Discount": discount, "Profit": profit}).dropna()
        if len(clean) >= 3:
            corr = float(clean["Discount"].corr(clean["Profit"]))
            features.append(
                {
                    "feature_type": "discount_profit_relationship",
                    "title": "折扣与利润的联动关系",
                    "finding": f"折扣与利润的Pearson相关系数为{corr:.3f}，高折扣记录需要结合利润表现重点复核。",
                    "evidence": f"n={len(clean)}，Pearson r={corr:.4f}。",
                    "method": "Pearson相关性描述",
                    "score": min(98.0, 65 + abs(corr) * 60),
                    "variables": ["Discount", "Profit"],
                    "metrics": {"correlation": round(corr, 6), "n": int(len(clean))},
                }
            )

    for group_col in ["Category", "Sub-Category", "Sub_Category", "Region", "Segment", "Ship Mode", "Ship_Mode"]:
        if group_col not in df.columns:
            continue
        grouped = pd.DataFrame({group_col: df[group_col], "Sales": sales, "Profit": profit}).dropna()
        summary = grouped.groupby(group_col).agg(Sales=("Sales", "sum"), Profit=("Profit", "sum"), n=("Profit", "size"))
        summary = summary[summary["Sales"] != 0].copy()
        if summary.empty:
            continue
        summary["Margin"] = summary["Profit"] / summary["Sales"] * 100
        worst = summary.sort_values("Margin").iloc[0]
        best = summary.sort_values("Margin", ascending=False).iloc[0]
        worst_name = str(summary["Margin"].idxmin())
        best_name = str(summary["Margin"].idxmax())
        features.append(
            {
                "feature_type": "group_margin_contrast",
                "title": f"{group_col}利润率分化",
                "finding": f"{group_col}中，{best_name}利润率最高（{best['Margin']:.2f}%），{worst_name}最低（{worst['Margin']:.2f}%）。",
                "evidence": f"{best_name}: 销售额={best['Sales']:.2f}、利润={best['Profit']:.2f}；{worst_name}: 销售额={worst['Sales']:.2f}、利润={worst['Profit']:.2f}。",
                "method": "分组汇总与利润率对比",
                "score": min(96.0, 60 + abs(float(best["Margin"] - worst["Margin"]))),
                "variables": [group_col, "Sales", "Profit"],
                "metrics": {
                    "best_group": best_name,
                    "best_margin_pct": round(float(best["Margin"]), 4),
                    "worst_group": worst_name,
                    "worst_margin_pct": round(float(worst["Margin"]), 4),
                },
            }
        )

    for order_col, ship_col in [
        ("Order Date", "Ship Date"),
        ("Order_Date", "Ship_Date"),
        ("订单日期", "发货日期"),
    ]:
        if order_col not in df.columns or ship_col not in df.columns:
            continue
        order_date = pd.to_datetime(df[order_col], errors="coerce")
        ship_date = pd.to_datetime(df[ship_col], errors="coerce")
        days = (ship_date - order_date).dt.days.dropna()
        if days.empty:
            continue
        abnormal_rate = float(((days < 0) | (days > 60)).mean() * 100)
        if abnormal_rate > 1:
            features.append(
                {
                    "feature_type": "date_quality_risk",
                    "title": "订单与发货日期存在质量风险",
                    "finding": f"{abnormal_rate:.2f}%的可计算记录显示发货间隔小于0天或超过60天，日期趋势不宜直接用于经营判断。",
                    "evidence": f"日期间隔中位数={days.median():.1f}天，异常占比={abnormal_rate:.2f}%。",
                    "method": "日期逻辑一致性检查",
                    "score": min(100.0, 75 + abnormal_rate / 2),
                    "variables": [order_col, ship_col],
                    "metrics": {"abnormal_rate_pct": round(abnormal_rate, 4), "median_days": round(float(days.median()), 2)},
                }
            )

    features = _dedupe_features(features)
    features.sort(key=lambda item: item.get("score", 0), reverse=True)
    selected = features[:max_features]
    for index, feature in enumerate(selected, 1):
        feature["source_key"] = f"distinctive_features.F{index:03d}"
    return {
        "meta": {"n_rows": int(len(df)), "domain": "retail_sales", "generated_at": datetime.now().isoformat(timespec="seconds")},
        "sector_matrix": [],
        "sector_summary": [],
        "features": selected,
        "feature_type_counts": dict(Counter(item["feature_type"] for item in selected)),
    }


def save_distinctive_features(output_dir: str | Path, features: Dict[str, Any]) -> Path:
    """保存特色信号挖掘结果。"""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "distinctive_features.json"
    path.write_text(json.dumps(features, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _extract_rating_columns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    columns: List[Dict[str, Any]] = []
    for column in df.columns:
        parsed = _extract_dimension_sector(column)
        if not parsed:
            continue
        dimension, sector = parsed
        scores = df[column].map(_parse_score)
        valid = scores.dropna()
        if len(valid) < 3:
            continue
        if not valid.between(1, 5).mean() >= 0.85:
            continue
        columns.append(
            {
                "column": column,
                "label": humanize_column_name(column),
                "dimension": dimension,
                "sector": sector,
                "scores": scores,
            }
        )
    return columns


def _extract_dimension_sector(column: Any) -> Optional[Tuple[str, str]]:
    raw = str(column).strip()
    candidates = [raw, humanize_column_name(raw)]
    for text in candidates:
        for sep in ["：", ":"]:
            if sep in text:
                left, right = text.split(sep, 1)
                dimension = _normalize_dimension(left)
                sector = _normalize_sector(right)
                if dimension and sector:
                    return dimension, sector

    question_match = re.search(r"(?:^|_)col_?(1[1-7])|^1[1-7]", raw)
    question_no = None
    if question_match:
        question_no = next((group for group in question_match.groups() if group), None)
    if not question_no:
        prefix_match = re.match(r"^(?:col_)?(1[1-7])", raw)
        question_no = prefix_match.group(1) if prefix_match else None
    dimension = QUESTION_DIMENSIONS.get(question_no or "")
    if not dimension:
        return None

    sector = ""
    for pattern in [r"\._(.+)$", r"\t(.+)$", r"\d+\s*[\.、]\s*(.+)$"]:
        match = re.search(pattern, raw)
        if match:
            sector = match.group(1)
            break
    sector = _normalize_sector(sector or humanize_column_name(raw))
    return (dimension, sector) if sector else None


def _normalize_dimension(value: Any) -> str:
    text = str(value).strip()
    return DIMENSION_ALIASES.get(text, "")


def _normalize_sector(value: Any) -> str:
    text = humanize_column_name(str(value).strip())
    if "：" in text:
        text = text.split("：", 1)[1]
    text = re.sub(r"^[\dA-Za-z]+\s*[\.、]\s*", "", text)
    text = text.strip(" ：:._-")
    return text


def _parse_score(value: Any) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else np.nan


def _build_sector_matrix(df: pd.DataFrame, rating_columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in rating_columns:
        values = item["scores"].dropna()
        if values.empty:
            continue
        rows.append(
            {
                "sector": item["sector"],
                "dimension": item["dimension"],
                "column": item["column"],
                "label": item["label"],
                "n": int(values.count()),
                "mean": _round(values.mean()),
                "std": _round(values.std(ddof=1)),
                "median": _round(values.median()),
                "top2_pct": _round((values >= 4).mean() * 100),
                "bottom2_pct": _round((values <= 2).mean() * 100),
            }
        )
    return rows


def _build_sector_summary(sector_matrix: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_sector: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in sector_matrix:
        by_sector.setdefault(row["sector"], {})[row["dimension"]] = row

    summary: List[Dict[str, Any]] = []
    for sector, dims in sorted(by_sector.items()):
        metrics = {dimension: dims[dimension]["mean"] for dimension in dims}
        summary.append(
            {
                "sector": sector,
                "dimensions": dims,
                "metrics": {
                    **metrics,
                    "value_conversion_gap": _round(_get(metrics, "社会价值") - _get(metrics, "创业意愿")),
                    "value_fit_gap": _round(_get(metrics, "社会价值") - _get(metrics, "专业契合")),
                    "interest_opportunity_gap": _round(_get(metrics, "消费者兴趣") - _get(metrics, "总体机会")),
                    "fit_difficulty_gap": _round(_get(metrics, "专业契合") - _get(metrics, "技术难度")),
                },
            }
        )
    return summary


def _mine_sector_pattern_features(sector_summary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    features: List[Dict[str, Any]] = []
    for item in sector_summary:
        sector = item["sector"]
        dims = item["dimensions"]
        metrics = item["metrics"]
        interest = _get(metrics, "消费者兴趣")
        difficulty = _get(metrics, "技术难度")
        fit = _get(metrics, "专业契合")
        value = _get(metrics, "社会价值")
        competition = _get(metrics, "竞争激烈")
        opportunity = _get(metrics, "总体机会")
        startup = _get(metrics, "创业意愿")

        if interest >= 3.6 and difficulty >= 4.2 and competition >= 4.0:
            features.append(_sector_feature(
                "hot_hard_crowded",
                sector,
                "热门高难高竞争赛道",
                f"{sector}同时呈现高兴趣、高技术难度和高竞争强度。",
                (
                    f"消费者兴趣均值={interest:.2f}，技术难度均值={difficulty:.2f}，"
                    f"竞争激烈度均值={competition:.2f}。"
                ),
                "赛道评分矩阵描述统计",
                72 + (interest + difficulty + competition - 11.8) * 8,
                dims,
                {"interest": interest, "difficulty": difficulty, "competition": competition},
                actionability="适合作为高阶挑战案例，需同步提供技术拆解和差异化定位讨论。",
            ))

        if value >= 4.0 and (startup <= 3.2 or fit <= 3.0):
            features.append(_sector_feature(
                "high_value_low_conversion",
                sector,
                "高社会价值低转化赛道",
                f"{sector}社会价值评分较高，但创业意愿或专业契合评分偏低。",
                (
                    f"社会价值均值={value:.2f}，创业意愿均值={startup:.2f}，"
                    f"专业契合均值={fit:.2f}。"
                ),
                "赛道评分矩阵描述统计",
                74 + max(value - startup, value - fit) * 6,
                dims,
                {"social_value": value, "startup_intent": startup, "fit": fit},
                actionability="适合补充真实案例、可行路径和低门槛项目切入点。",
            ))

        if fit >= 3.5 and difficulty <= 3.0 and opportunity <= 3.0 and competition >= 3.7:
            features.append(_sector_feature(
                "easy_but_crowded",
                sector,
                "低难度高竞争赛道",
                f"{sector}专业契合度较高、技术难度较低，但机会评分偏低且竞争评分较高。",
                (
                    f"专业契合均值={fit:.2f}，技术难度均值={difficulty:.2f}，"
                    f"总体机会均值={opportunity:.2f}，竞争激烈度均值={competition:.2f}。"
                ),
                "赛道评分矩阵描述统计",
                70 + (fit - difficulty + competition - opportunity) * 5,
                dims,
                {"fit": fit, "difficulty": difficulty, "opportunity": opportunity, "competition": competition},
                actionability="适合作为差异化定位练习，强调细分需求而非泛化产品方案。",
            ))

        if opportunity >= 3.3 and interest <= 3.1 and competition <= 3.2:
            features.append(_sector_feature(
                "underrecognized_opportunity",
                sector,
                "低关注潜力赛道",
                f"{sector}总体机会评分不低，但消费者兴趣和竞争强度评分相对偏低。",
                (
                    f"总体机会均值={opportunity:.2f}，消费者兴趣均值={interest:.2f}，"
                    f"竞争激烈度均值={competition:.2f}。"
                ),
                "赛道评分矩阵描述统计",
                68 + (opportunity - interest + 3.2 - competition) * 6,
                dims,
                {"opportunity": opportunity, "interest": interest, "competition": competition},
                actionability="适合作为认知拓展型选题，让学生先理解应用场景再判断机会。",
            ))

        interest_row = dims.get("消费者兴趣", {})
        if interest_row.get("std") and interest_row["std"] >= 1.2:
            features.append(_sector_feature(
                "polarized_interest",
                sector,
                "兴趣分化赛道",
                f"{sector}消费者兴趣评分离散度较高，学生偏好分化明显。",
                f"消费者兴趣均值={interest:.2f}，标准差={interest_row['std']:.2f}。",
                "赛道评分矩阵描述统计",
                64 + interest_row["std"] * 9,
                dims,
                {"interest": interest, "interest_std": interest_row["std"]},
                actionability="适合采用自选题或分层讨论，避免用单一案例覆盖所有学生。",
            ))

    return features


def _mine_group_difference_features(
    df: pd.DataFrame,
    rating_columns: List[Dict[str, Any]],
    *,
    max_pairs: int = 160,
) -> List[Dict[str, Any]]:
    if stats is None or not rating_columns:
        return []

    categorical_columns = _candidate_group_columns(df)
    features: List[Dict[str, Any]] = []
    checked = 0
    for group_column in categorical_columns:
        group_values = df[group_column].map(clean_choice)
        for rating in rating_columns:
            if checked >= max_pairs:
                break
            checked += 1
            values = rating["scores"]
            frame = pd.DataFrame({"group": group_values, "score": values}).dropna()
            grouped = [
                group["score"].astype(float).to_numpy()
                for _, group in frame.groupby("group")
                if len(group) >= 3
            ]
            if len(grouped) < 2:
                continue
            f_stat, p_value = stats.f_oneway(*grouped)
            if not np.isfinite(f_stat) or not np.isfinite(p_value):
                continue
            eta = _eta_squared(frame)
            group_means = {
                str(name): _round(group["score"].mean())
                for name, group in frame.groupby("group")
                if len(group) >= 3
            }
            if len(group_means) < 2:
                continue
            mean_range = max(group_means.values()) - min(group_means.values())
            if not (p_value < 0.05 and eta >= 0.10 or p_value < 0.08 and eta >= 0.18):
                continue

            high_group = max(group_means, key=group_means.get)
            low_group = min(group_means, key=group_means.get)
            group_label = humanize_column_name(group_column)
            metric_label = rating["label"]
            score = min(96, 58 + eta * 80 + min(mean_range, 2.5) * 8 - p_value * 20)
            features.append(
                {
                    "feature_type": "group_difference",
                    "sector": rating["sector"],
                    "dimension": rating["dimension"],
                    "title": f"{group_label}对应的{metric_label}评分差异",
                    "finding": (
                        f"不同{group_label}学生在“{metric_label}”上的评分差异达到统计显著水平。"
                    ),
                    "evidence": (
                        f"{high_group}均值={group_means[high_group]:.2f}，"
                        f"{low_group}均值={group_means[low_group]:.2f}，"
                        f"F={f_stat:.4f}，p={p_value:.4f}，eta²={eta:.4f}。"
                    ),
                    "method": "单因素方差分析",
                    "score": _round(score),
                    "p_value": _round(p_value, 6),
                    "significant": bool(p_value < 0.05),
                    "eta_squared": _round(eta, 6),
                    "group_column": group_column,
                    "group_column_label": group_label,
                    "variables": [rating["column"], group_column],
                    "readable_variables": [metric_label, group_label],
                    "metrics": {
                        "group_means": group_means,
                        "range": _round(mean_range),
                        "F_statistic": _round(f_stat, 6),
                        "p_value": _round(p_value, 6),
                        "eta_squared": _round(eta, 6),
                    },
                    "actionability": "适合按该分组配置案例、讨论题或项目入口。",
                }
            )
        if checked >= max_pairs:
            break
    return features


def _candidate_group_columns(df: pd.DataFrame) -> List[str]:
    columns: List[str] = []
    for column in df.columns:
        if _extract_dimension_sector(column):
            continue
        label = humanize_column_name(column)
        if any(keyword in str(column) + label for keyword in NOISE_COLUMNS):
            continue
        series = df[column].dropna().map(clean_choice)
        unique = series.nunique()
        if 2 <= unique <= 8 and not pd.api.types.is_numeric_dtype(df[column]):
            columns.append(column)
    preferred = ["专业", "数学能力", "编程能力", "课程投入", "作业", "课堂", "运动", "游戏", "社交"]
    return sorted(columns, key=lambda col: _preference_rank(humanize_column_name(col), preferred))


def _sector_feature(
    feature_type: str,
    sector: str,
    title_suffix: str,
    finding: str,
    evidence: str,
    method: str,
    score: float,
    dims: Dict[str, Dict[str, Any]],
    metrics: Dict[str, Any],
    *,
    actionability: str,
) -> Dict[str, Any]:
    columns = [row.get("column") for row in dims.values() if row.get("column")]
    labels = [row.get("label") for row in dims.values() if row.get("label")]
    return {
        "feature_type": feature_type,
        "sector": sector,
        "dimension": "",
        "title": f"{sector}{title_suffix}",
        "finding": finding,
        "evidence": evidence,
        "method": method,
        "score": _round(score),
        "p_value": None,
        "significant": None,
        "variables": columns,
        "readable_variables": labels,
        "metrics": metrics,
        "actionability": actionability,
    }


def _eta_squared(frame: pd.DataFrame) -> float:
    grand_mean = frame["score"].mean()
    ss_between = sum(len(group) * (group["score"].mean() - grand_mean) ** 2 for _, group in frame.groupby("group"))
    ss_total = sum((frame["score"] - grand_mean) ** 2)
    if not ss_total:
        return 0.0
    return float(ss_between / ss_total)


def _dedupe_features(features: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in features:
        key = (
            item.get("feature_type"),
            item.get("sector"),
            item.get("dimension"),
            tuple(item.get("variables", [])[:2]),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _get(metrics: Dict[str, Any], key: str) -> float:
    value = metrics.get(key)
    return float(value) if isinstance(value, (int, float)) and np.isfinite(value) else float("nan")


def _round(value: Any, digits: int = 4) -> Any:
    if isinstance(value, (int, float, np.integer, np.floating)) and np.isfinite(value):
        return round(float(value), digits)
    return None


def _preference_rank(text: str, preferred: List[str]) -> Tuple[int, str]:
    for index, keyword in enumerate(preferred):
        if keyword in text:
            return index, text
    return len(preferred), text
