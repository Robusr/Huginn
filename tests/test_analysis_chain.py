# -*- coding: utf-8 -*-
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from huginn.analysis.engine import AnalysisEngine
from huginn.planning.analysis_planning import build_candidate_task_pool, build_planning_field_map
from huginn.core.config import Config
from huginn.data.loader import DataLoader
from huginn.planning.feature_miner import mine_distinctive_features
from huginn.domain.context import detect_domain_context
from huginn.llm.client import (
    ActionSuggestion,
    DataFinding,
    DiscoveredProblem,
    LLMClient,
    ReportWritingResponse,
)
from huginn.reporting.generator import ReportGenerator
from huginn.reporting.validator import ReportValidator
from huginn.planning.task_planner import TaskPlanner


def _profile():
    return {
        "meta": {"n_rows": 20, "n_columns": 8, "total_missing_pct": 0.0},
        "overview": {"field_type_counts": {"numeric_discrete": 5, "categorical": 3}},
        "fields": [
            {"column": "提交答卷时间", "inferred_type": "datetime", "unique": 20, "stats": {}},
            {"column": "性别", "inferred_type": "categorical", "unique": 2, "stats": {}},
            {"column": "专业", "inferred_type": "categorical", "unique": 3, "stats": {}},
            {"column": "课堂座位", "inferred_type": "categorical", "unique": 4, "stats": {}},
            {"column": "兴趣评分A", "inferred_type": "numeric_discrete", "unique": 5, "stats": {"count": 20}},
            {"column": "技术难度A", "inferred_type": "numeric_discrete", "unique": 5, "stats": {"count": 20}},
            {"column": "专业契合A", "inferred_type": "numeric_discrete", "unique": 5, "stats": {"count": 20}},
            {"column": "社会价值A", "inferred_type": "numeric_discrete", "unique": 5, "stats": {"count": 20}},
        ],
    }


def _retail_profile():
    fields = [
        ("Row ID", "numeric_continuous", 9672),
        ("Order ID", "text", 4922),
        ("Customer ID", "text", 782),
        ("Postal Code", "numeric_continuous", 631),
        ("Category", "categorical", 3),
        ("Sub-Category", "categorical", 17),
        ("Region", "categorical", 4),
        ("Segment", "categorical", 3),
        ("Ship Mode", "categorical", 4),
        ("City", "categorical", 531),
        ("Sales", "numeric_continuous", 5825),
        ("Quantity", "numeric_discrete", 14),
        ("Discount", "numeric_continuous", 12),
        ("Profit", "numeric_continuous", 7211),
    ]
    return {
        "meta": {"n_rows": 9672, "n_columns": 21, "total_missing_pct": 0.0},
        "overview": {"field_type_counts": {"numeric_continuous": 4, "numeric_discrete": 2, "categorical": 13}},
        "fields": [
            {
                "column": column,
                "inferred_type": inferred_type,
                "unique": unique,
                "stats": {"count": 9672},
            }
            for column, inferred_type, unique in fields
        ],
    }


def test_domain_context_detects_retail_and_education_without_forcing_course_language():
    retail = detect_domain_context(_retail_profile(), "分析超市销售与利润并提出经营建议")
    education = detect_domain_context(_profile(), "为下一次课程形成教学建议")

    assert retail["domain"] == "retail_sales"
    assert retail["report_title"] == "超市销售数据分析报告"
    assert "课程" not in retail["recommendation_section"]
    assert education["domain"] == "education_survey"


def test_retail_registry_and_pool_exclude_identifiers_and_use_generic_language():
    profile = _retail_profile()
    context = detect_domain_context(profile, "分析销售和利润")
    registry = build_planning_field_map(profile, context)
    pool = build_candidate_task_pool(profile, registry, domain_context=context)

    columns = {item["column"] for item in registry["fields"]}
    task_text = " ".join(item["question"] + item["value"] for item in pool["tasks"])
    methods = {item["method"] for item in pool["tasks"]}

    assert {"Row ID", "Order ID", "Customer ID", "Postal Code", "City"}.isdisjoint(columns)
    assert {"Sales", "Profit", "Discount", "Quantity", "Category", "Region"}.issubset(columns)
    assert not any(word in task_text for word in ["学生", "课程", "课堂", "评分"])
    assert {"ANOVA", "卡方检验", "相关性分析", "分布检验"}.issubset(methods)
    assert all(
        profile_field["unique"] <= Config.ANALYSIS_MAX_GROUPS
        for task in pool["tasks"]
        for variable in task["variables"][1:]
        for profile_field in profile["fields"]
        if task["method"] in {"ANOVA", "t检验"} and profile_field["column"] == variable
    )


def test_task_planner_rejects_high_cardinality_anova_group():
    planner = TaskPlanner(_retail_profile())

    valid, message = planner._validate_anova(["Profit", "City"])

    assert not valid
    assert "类别数" in message


def test_data_loader_converts_pandas_string_dtype_likert_values():
    df = pd.DataFrame(
        {
            "兴趣评分": pd.Series(
                ["5（非常感兴趣）", "4", "3", "2", "1（完全没兴趣）"],
                dtype="str",
            ),
            "专业": pd.Series(["机械", "计算机", "机械", "电子", "计算机"], dtype="str"),
        }
    )

    converted = DataLoader._infer_and_convert_types(df)

    assert pd.api.types.is_numeric_dtype(converted["兴趣评分"])
    assert converted["兴趣评分"].tolist() == [5, 4, 3, 2, 1]
    assert pd.api.types.is_string_dtype(converted["专业"])


def test_attribution_words_are_not_treated_as_statistical_hedges():
    assert "认为" not in Config.VAGUE_WORDS
    assert "觉得" not in Config.VAGUE_WORDS


def test_normalize_finding_refs_does_not_attach_unrelated_task_ids():
    findings = [
        DataFinding(
            conclusion="人形机器人呈现高兴趣、高难度和高竞争。",
            evidence="兴趣均值=3.79，难度均值=4.69。",
            method="赛道评分矩阵描述统计",
            importance=5,
            source_stat_keys=["distinctive_features.F004"],
            source_task_ids=[6],
        ),
        DataFinding(
            conclusion="数学能力自评与编程能力自评存在关联。",
            evidence="chi2=12.73, p=0.0127",
            method="卡方检验",
            importance=4,
            source_stat_keys=["hypothesis_tests.task_8_chi_square_independence"],
            source_task_ids=[],
        ),
    ]
    suggestions = [
        ActionSuggestion(
            suggestion="为人形机器人案例设置分层任务。",
            evidence="该赛道高兴趣且高难度。",
            direction="区分入门任务与挑战任务。",
            source_stat_keys=["distinctive_features.F004"],
            source_task_ids=[6],
        )
    ]
    evidence_table = [
        {"stat_key": "distinctive_features.F004", "source_task_id": None},
        {"stat_key": "hypothesis_tests.task_8_chi_square_independence", "source_task_id": 8},
    ]

    LLMClient._normalize_finding_refs(findings, suggestions, evidence_table)

    assert findings[0].source_task_ids == []
    assert findings[1].source_task_ids == [8]
    assert suggestions[0].source_task_ids == []


def test_chinese_actionable_suggestion_is_not_rejected_for_lacking_spaces():
    suggestion = (
        "加强数学基础与编程能力的协同辅导，针对数学自评偏弱的学生群体，"
        "通过入门级编程工作坊和配套数学思维训练缩小能力缺口。"
    )
    direction = (
        "在课程前四周设置数学与代码共学模块，使用图形化编程并复习三角函数与向量。"
    )

    assert not ReportValidator._is_vague_suggestion(suggestion, direction)
    assert ReportValidator._is_vague_suggestion("加强教学", "")


def test_word_export_uses_a4_and_heading_page_breaks_without_section_break_paragraphs(tmp_path):
    from docx import Document
    from docx.shared import Cm

    generator = ReportGenerator(tmp_path)
    generator._load_if_needed = lambda: None
    generator.chart_notes = []
    generator._build_sections = lambda: [
        {"id": str(index), "heading": f"第{index}章", "blocks": []}
        for index in range(1, 7)
    ]

    path = generator.export_word("layout.docx")
    document = Document(path)
    section = document.sections[0]

    assert abs(section.page_width - Cm(21)) < 1000
    assert abs(section.page_height - Cm(29.7)) < 1000
    assert document.styles["Heading 1"].paragraph_format.page_break_before is True
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert 'w:type="page"' not in document_xml


def test_toc_page_map_accounts_for_multi_page_findings_and_suggestions(tmp_path):
    generator = ReportGenerator(tmp_path)
    generator.chart_notes = [{} for _ in range(4)]
    generator.findings = [{} for _ in range(8)]
    generator.suggestions = [{} for _ in range(5)]

    page_map = generator._section_page_map()

    assert page_map["4"] == 8
    assert page_map["5"] == 10
    assert page_map["6"] == 12
    assert generator._section_page_map(output_format="pdf")["6"] == 11


def test_field_registry_and_task_pool_use_only_valid_columns():
    registry = build_planning_field_map(_profile())
    pool = build_candidate_task_pool(_profile(), registry)

    columns = {item["column"] for item in registry["fields"]}
    ids = {item["field_id"] for item in registry["fields"]}

    assert "提交答卷时间" not in columns
    assert all(task["task_pool_id"].startswith("T") for task in pool["tasks"])
    assert all(set(task["variables"]).issubset(columns) for task in pool["tasks"])
    assert all(set(task["variable_ids"]).issubset(ids) for task in pool["tasks"])
    assert any(task["method"] == "ANOVA" for task in pool["tasks"])
    assert any(task["method"] == "卡方检验" for task in pool["tasks"])


def test_llm_candidate_selection_maps_pool_ids_back_to_real_columns():
    profile = _profile()
    registry = build_planning_field_map(profile)
    pool = build_candidate_task_pool(profile, registry)
    first = pool["tasks"][0]

    client = LLMClient.__new__(LLMClient)
    client.offline_mode = False

    def fake_call(messages, response_format=None):
        parsed = SimpleNamespace(
            selections=[
                SimpleNamespace(task_pool_id=first["task_pool_id"], value="优先分析该关系", priority=5),
                SimpleNamespace(task_pool_id="missing-task", value="无效选择", priority=4),
            ]
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])

    client._call_with_retry = fake_call
    questions = client.generate_candidate_questions(
        profile,
        "为老师生成课程建议报告",
        field_registry=registry,
        task_pool=pool,
    )

    assert questions[0].variables == first["variables"]
    assert questions[0].task_pool_id == first["task_pool_id"]
    assert all("missing-task" != q.task_pool_id for q in questions)


def test_run_tasks_expands_point_and_interval_estimation_to_core_numeric_fields(tmp_path):
    df = pd.DataFrame({
        "性别": ["男", "女"] * 10,
        "专业": ["A", "B", "C", "A", "B"] * 4,
        "兴趣评分A": [1, 2, 3, 4, 5] * 4,
        "技术难度A": [2, 2, 3, 4, 5] * 4,
        "专业契合A": [3, 3, 4, 4, 5] * 4,
        "社会价值A": [4, 4, 4, 5, 5] * 4,
        "竞争激烈A": [1, 1, 2, 2, 3] * 4,
        "创业机会A": [2, 3, 3, 4, 4] * 4,
    })
    tasks = [
        {
            "task_id": 1,
            "question": "不同性别在兴趣评分上的差异",
            "variables": ["兴趣评分A", "性别"],
            "method": "t检验",
            "value": "测试",
        }
    ]

    results = AnalysisEngine(df, output_dir=tmp_path).run_tasks(tasks)

    assert len(results["point_estimation"]["fields"]) >= 5
    assert len(results["interval_estimation"]["fields"]) >= 5
    assert results["counts_check"]["interval_estimation_fields"] >= 5


def test_counts_check_treats_chi_square_independence_as_chi_square():
    engine = AnalysisEngine(pd.DataFrame())
    engine.results = {
        "point_estimation": {"fields": {f"n{i}": {} for i in range(5)}},
        "interval_estimation": {"fields": {f"n{i}": {} for i in range(5)}},
        "hypothesis_tests": {
            "tests": {
                "a": {"p_value": 0.1, "t_statistic": 1.0},
                "b": {"p_value": 0.1, "t_statistic": 1.0},
                "c": {"p_value": 0.1, "t_statistic": 1.0},
                "task_1_chi_square_independence": {"p_value": 0.1, "chi2_statistic": 3.2, "method": "皮尔逊卡方独立性检验"},
                "task_2_chi_square_independence": {"p_value": 0.1, "chi2_statistic": 2.4, "method": "皮尔逊卡方独立性检验"},
            }
        },
        "anova": {"tests": {"a1": {"p_value": 0.1, "F_statistic": 1.2}, "a2": {"p_value": 0.1, "F_statistic": 1.5}}},
        "chi_square_goodness_of_fit": {"tests": {}},
    }

    counts = engine._verify_counts()

    assert counts["chi_square_tests"] == 2
    assert counts["all_checks_pass"]


def test_validator_accepts_structured_evidence_refs(tmp_path):
    stat_key = "anova.task_1_one_way_anova"
    (tmp_path / "data_profile.json").write_text(
        json.dumps({"meta": {"n_rows": 20, "n_columns": 4, "total_missing_pct": 0}, "fields": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "stats_results.json").write_text(
        json.dumps(
            {
                "point_estimation": {"fields": {f"n{i}": {} for i in range(5)}},
                "interval_estimation": {"fields": {f"n{i}": {} for i in range(5)}},
                "hypothesis_tests": {"tests": {f"h{i}": {"p_value": 0.1} for i in range(5)}},
                "anova": {"tests": {"task_1_one_way_anova": {"p_value": 0.01}}},
                "chi_square_goodness_of_fit": {"tests": {"c1": {}, "c2": {}}},
                "counts_check": {"all_checks_pass": True, "notes": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "valid_tasks.json").write_text("[]", encoding="utf-8")
    findings = [
        {
            "conclusion": "不同专业学生在兴趣评分上存在显著差异。",
            "evidence": "F=4.20, p=0.010",
            "method": "ANOVA",
            "importance": 5,
            "source_stat_keys": [stat_key],
        }
        for _ in range(5)
    ]
    suggestions = [
        {
            "suggestion": "按专业分层配置不同难度与应用背景的课堂案例。",
            "evidence": findings[0]["conclusion"],
            "direction": "提供不同专业入口案例。",
            "source_stat_keys": [stat_key],
        }
        for _ in range(3)
    ]
    (tmp_path / "findings.json").write_text(json.dumps(findings, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "suggestions.json").write_text(json.dumps(suggestions, ensure_ascii=False), encoding="utf-8")

    result = ReportValidator(str(tmp_path)).run_all_checks()

    assert result["checks"]["findings_compliance"]["score"] == 20
    assert result["checks"]["suggestions_quality"]["score"] == 10


def test_validator_accepts_distinctive_feature_refs(tmp_path):
    stat_key = "distinctive_features.F001"
    (tmp_path / "data_profile.json").write_text(
        json.dumps({"meta": {"n_rows": 20, "n_columns": 4, "total_missing_pct": 0}, "fields": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (tmp_path / "stats_results.json").write_text(
        json.dumps(
            {
                "point_estimation": {"fields": {f"n{i}": {} for i in range(5)}},
                "interval_estimation": {"fields": {f"n{i}": {} for i in range(5)}},
                "hypothesis_tests": {"tests": {f"h{i}": {"p_value": 0.1} for i in range(5)}},
                "anova": {"tests": {"a1": {"p_value": 0.01}, "a2": {"p_value": 0.02}}},
                "chi_square_goodness_of_fit": {"tests": {"c1": {}, "c2": {}}},
                "counts_check": {"all_checks_pass": True, "notes": []},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "valid_tasks.json").write_text("[]", encoding="utf-8")
    (tmp_path / "distinctive_features.json").write_text(
        json.dumps(
            {
                "features": [
                    {
                        "source_key": stat_key,
                        "feature_type": "high_value_low_conversion",
                        "finding": "助残科技社会价值评分较高，但创业意愿评分偏低。",
                        "evidence": "社会价值均值=4.33；创业意愿均值=2.58。",
                        "p_value": None,
                        "score": 88,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    findings = [
        {
            "conclusion": "助残科技社会价值评分较高，但创业意愿评分偏低。",
            "evidence": "社会价值均值=4.33；创业意愿均值=2.58。",
            "method": "赛道评分矩阵描述统计",
            "importance": 5,
            "source_stat_keys": [stat_key],
        }
        for _ in range(5)
    ]
    suggestions = [
        {
            "suggestion": "围绕助残科技设置价值场景与可行路径拆解任务。",
            "evidence": findings[0]["conclusion"],
            "direction": "让学生先理解真实使用场景，再进入项目构思。",
            "source_stat_keys": [stat_key],
        }
        for _ in range(3)
    ]
    (tmp_path / "findings.json").write_text(json.dumps(findings, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "suggestions.json").write_text(json.dumps(suggestions, ensure_ascii=False), encoding="utf-8")

    result = ReportValidator(str(tmp_path)).run_all_checks()

    assert result["checks"]["findings_compliance"]["score"] == 20
    assert result["checks"]["suggestions_quality"]["score"] == 10


def test_evidence_table_includes_point_estimation_keys():
    stats_results = {
        "point_estimation": {
            "fields": {
                "兴趣评分A": {"n": 20, "mean": 4.2, "std": 0.8},
            }
        }
    }

    evidence = LLMClient._build_evidence_table(stats_results)

    assert any(row["stat_key"] == "point_estimation.兴趣评分A" for row in evidence)


def test_offline_findings_fallback_uses_point_estimates_to_reach_minimum():
    client = LLMClient.__new__(LLMClient)
    stats_results = {
        "hypothesis_tests": {"tests": {}},
        "anova": {"tests": {}},
        "distribution_tests": {"tests": {}},
        "point_estimation": {
            "fields": {
                f"兴趣评分{i}": {"n": 20, "mean": 4.0 + i / 10, "std": 0.5}
                for i in range(6)
            }
        },
    }

    findings, suggestions = client._generate_offline_findings_suggestions(stats_results, {}, [])

    assert len(findings) >= 5
    assert len(suggestions) >= 5
    assert all(finding.source_stat_keys for finding in findings[:5])
    assert all(key.startswith("point_estimation.") for finding in findings[:5] for key in finding.source_stat_keys)


def test_offline_findings_use_diverse_distinctive_feature_types():
    client = LLMClient.__new__(LLMClient)
    stats_results = {
        "hypothesis_tests": {"tests": {}},
        "anova": {
            "tests": {
                "task_1_one_way_anova": {
                    "dependent": "消费者兴趣：人形机器人",
                    "factor": "数学能力自评",
                    "F_statistic": 4.2,
                    "p_value": 0.02,
                    "method": "单因素方差分析",
                },
                "task_2_one_way_anova": {
                    "dependent": "技术难度认知：人形机器人",
                    "factor": "编程能力自评",
                    "F_statistic": 4.5,
                    "p_value": 0.01,
                    "method": "单因素方差分析",
                },
            }
        },
        "distribution_tests": {"tests": {}},
        "point_estimation": {"fields": {}},
    }
    distinctive_features = {
        "features": [
            {
                "source_key": "distinctive_features.F001",
                "feature_type": "group_difference",
                "finding": "不同数学能力自评学生在“消费者兴趣：元宇宙体验设备”上的评分差异达到统计显著水平。",
                "evidence": "F=4.50，p=0.0100，eta²=0.2000。",
                "method": "单因素方差分析",
                "score": 95,
                "sector": "元宇宙体验设备",
            },
            {
                "source_key": "distinctive_features.F002",
                "feature_type": "group_difference",
                "finding": "不同数学能力自评学生在“消费者兴趣：人形机器人”上的评分差异达到统计显著水平。",
                "evidence": "F=4.10，p=0.0200，eta²=0.1800。",
                "method": "单因素方差分析",
                "score": 94,
                "sector": "人形机器人",
            },
            {
                "source_key": "distinctive_features.F003",
                "feature_type": "hot_hard_crowded",
                "finding": "人形机器人同时呈现高兴趣、高技术难度和高竞争强度。",
                "evidence": "消费者兴趣均值=3.79，技术难度均值=4.69，竞争激烈度均值=4.69。",
                "method": "赛道评分矩阵描述统计",
                "score": 90,
                "sector": "人形机器人",
            },
            {
                "source_key": "distinctive_features.F004",
                "feature_type": "high_value_low_conversion",
                "finding": "助残科技社会价值评分较高，但创业意愿或专业契合评分偏低。",
                "evidence": "社会价值均值=4.05，创业意愿均值=2.90，专业契合均值=2.72。",
                "method": "赛道评分矩阵描述统计",
                "score": 88,
                "sector": "助残科技",
            },
        ]
    }

    findings, suggestions = client._generate_offline_findings_suggestions(
        stats_results, {}, [], distinctive_features
    )
    source_keys = {key for finding in findings for key in finding.source_stat_keys}

    assert "distinctive_features.F003" in source_keys
    assert "distinctive_features.F004" in source_keys
    assert any("人形机器人" in suggestion.suggestion for suggestion in suggestions)


def test_distinctive_feature_miner_detects_sector_contrasts():
    df = pd.DataFrame({
        "消费者兴趣：人形机器人": [5, 5, 4, 5, 4, 5, 5, 4, 5, 5, 4, 5],
        "技术难度认知：人形机器人": [5, 5, 5, 4, 5, 5, 4, 5, 5, 5, 4, 5],
        "竞争激烈度判断：人形机器人": [5, 5, 4, 5, 5, 4, 5, 5, 5, 4, 5, 5],
        "总体机会判断：人形机器人": [4, 4, 3, 4, 4, 3, 4, 4, 3, 4, 4, 3],
        "社会价值判断：助残科技": [5, 4, 4, 5, 4, 4, 5, 4, 4, 5, 4, 4],
        "专业契合度：助残科技": [3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2],
        "创业意愿：助残科技": [3, 3, 2, 3, 2, 3, 3, 2, 3, 2, 3, 2],
        "消费者兴趣：智能家居": [4, 4, 4, 3, 4, 4, 3, 4, 4, 3, 4, 4],
        "技术难度认知：智能家居": [2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3],
        "专业契合度：智能家居": [4, 4, 3, 4, 4, 3, 4, 4, 3, 4, 4, 3],
        "总体机会判断：智能家居": [3, 2, 3, 2, 3, 2, 3, 2, 3, 2, 3, 2],
        "竞争激烈度判断：智能家居": [4, 4, 4, 5, 4, 4, 5, 4, 4, 5, 4, 4],
    })

    result = mine_distinctive_features(df)
    feature_types = {item["feature_type"] for item in result["features"]}
    matrix_keys = {(row["sector"], row["dimension"]) for row in result["sector_matrix"]}

    assert ("人形机器人", "消费者兴趣") in matrix_keys
    assert "hot_hard_crowded" in feature_types
    assert "high_value_low_conversion" in feature_types
    assert any(item["sector"] == "智能家居" and item["feature_type"] == "easy_but_crowded" for item in result["features"])


def test_distinctive_feature_miner_detects_group_difference_signal():
    df = pd.DataFrame({
        "每周运动时间": ["8小时以上"] * 8 + ["1-2小时"] * 8,
        "消费者兴趣：竞技运动科技": [5, 5, 4, 5, 4, 5, 5, 4, 2, 3, 2, 3, 2, 2, 3, 2],
        "技术难度认知：竞技运动科技": [3, 4, 3, 4, 3, 4, 3, 4, 3, 3, 4, 3, 4, 3, 3, 4],
    })

    result = mine_distinctive_features(df)
    group_features = [item for item in result["features"] if item["feature_type"] == "group_difference"]

    assert group_features
    assert any("每周运动时间" in item["group_column_label"] for item in group_features)
    assert any(item["sector"] == "竞技运动科技" and item["dimension"] == "消费者兴趣" for item in group_features)


def test_evidence_table_includes_distinctive_feature_keys():
    stats_results = {"point_estimation": {"fields": {}}}
    distinctive_features = {
        "features": [
            {
                "source_key": "distinctive_features.F001",
                "feature_type": "high_value_low_conversion",
                "title": "助残科技呈现高价值低转化",
                "finding": "助残科技社会价值评分较高，但创业意愿评分偏低。",
                "evidence": "社会价值均值=4.33；创业意愿均值=2.58。",
                "method": "赛道评分矩阵描述统计",
                "score": 88.0,
                "variables": ["社会价值判断：助残科技", "创业意愿：助残科技"],
                "metrics": {"value_conversion_gap": 1.75},
            }
        ]
    }

    evidence = LLMClient._build_evidence_table(stats_results, distinctive_features)

    assert any(row["stat_key"] == "distinctive_features.F001" for row in evidence)


def test_four_online_model_stages_are_audited_in_order():
    client = LLMClient.__new__(LLMClient)
    client.offline_mode = False
    client.model = "test-model"
    client.call_audit = []

    responses = [
        SimpleNamespace(selections=[SimpleNamespace(task_pool_id="T001", value="重要", priority=5)]),
        SimpleNamespace(
            problems=[
                DiscoveredProblem(
                    title="利润受折扣挤压",
                    description="折扣与利润呈负向关系。",
                    importance=5,
                    source_stat_keys=["point_estimation.Profit"],
                )
            ]
        ),
        SimpleNamespace(
            findings=[
                DataFinding(
                    conclusion="利润均值值得关注。",
                    evidence="均值=28.66。",
                    method="点估计",
                    importance=5,
                    source_stat_keys=["point_estimation.Profit"],
                )
            ],
            suggestions=[
                ActionSuggestion(
                    suggestion="复核高折扣订单。",
                    evidence="利润均值=28.66。",
                    direction="按折扣层级监控利润。",
                    source_stat_keys=["point_estimation.Profit"],
                )
            ],
        ),
        ReportWritingResponse(
            title="销售经营分析报告",
            subtitle="销售、利润与折扣的证据化分析",
            executive_summary="本报告聚焦销售与利润表现。",
            overview_paragraphs=["数据包含销售、利润、折扣与分类字段。"],
            chart_section_intro="图表用于呈现关键差异与关联。",
            findings=[],
            suggestions=[],
            limitations=["结果反映关联而非因果。"],
        ),
    ]

    def fake_call(messages, response_format=None):
        parsed = responses.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])

    client._call_with_retry = fake_call
    profile = _retail_profile()
    context = detect_domain_context(profile, "分析销售和利润")
    registry = build_planning_field_map(profile, context)
    pool = {
        "tasks": [
            {
                "task_pool_id": "T001",
                "question": "不同品类的利润是否存在显著差异？",
                "variables": ["Profit", "Category"],
                "variable_ids": ["F002", "F001"],
                "variable_labels": ["利润", "品类"],
                "method": "ANOVA",
                "value": "识别品类利润差异",
            }
        ]
    }
    stats = {"point_estimation": {"fields": {"Profit": {"n": 9672, "mean": 28.66, "std": 234.3}}}}
    findings = [
        DataFinding(
            conclusion="利润均值值得关注。",
            evidence="均值=28.66。",
            method="点估计",
            importance=5,
            source_stat_keys=["point_estimation.Profit"],
        )
    ]
    suggestions = [
        ActionSuggestion(
            suggestion="复核高折扣订单。",
            evidence="利润均值=28.66。",
            direction="按折扣层级监控利润。",
            source_stat_keys=["point_estimation.Profit"],
        )
    ]

    client.generate_candidate_questions(profile, "分析销售和利润", field_registry=registry, task_pool=pool, domain_context=context)
    problems = client.discover_analysis_problems(stats, profile, [], {}, context)
    client.generate_findings_and_suggestions(stats, profile, [], distinctive_features={}, discovered_problems=problems, domain_context=context)
    client.polish_report_content(profile, stats, findings, suggestions, {}, context, "分析销售和利润")

    assert [item["stage"] for item in client.call_audit] == [
        "task_planning",
        "problem_discovery",
        "findings_suggestions",
        "report_writing",
    ]
    assert all(item["success"] for item in client.call_audit)


def test_critical_date_risk_is_forced_into_findings_and_suggestions():
    feature = {
        "source_key": "distinctive_features.F001",
        "feature_type": "date_quality_risk",
        "title": "日期质量风险",
        "finding": "94.90%的记录存在异常日期间隔。",
        "evidence": "异常占比=94.90%。",
        "method": "日期逻辑一致性检查",
        "score": 100,
    }

    findings, suggestions = LLMClient._ensure_critical_finding_coverage([], [], {"features": [feature]})

    assert findings[0].source_stat_keys == ["distinctive_features.F001"]
    assert suggestions[0].source_stat_keys == ["distinctive_features.F001"]
    assert "日期" in suggestions[0].suggestion


def test_ungrounded_numeric_targets_are_replaced_with_evidence_bound_action():
    suggestion = ActionSuggestion(
        suggestion="将折扣上限设为0.2。",
        evidence="Pearson r=-0.216，p<0.001。",
        direction="把利润率提高到15%。",
        source_stat_keys=["distinctive_features.F003"],
    )
    feature = {
        "source_key": "distinctive_features.F003",
        "feature_type": "discount_profit_relationship",
        "sector": "",
    }

    LLMClient._sanitize_action_suggestions([suggestion], {"features": [feature]})

    assert "0.2" not in suggestion.suggestion
    assert "15%" not in suggestion.direction
    assert "联合监控" in suggestion.suggestion


def test_report_language_sanitizer_downgrades_causal_correlation_claims():
    narrative = ReportWritingResponse(
        title="经营分析报告",
        subtitle="证据化分析",
        executive_summary="折扣让利侵蚀利润，却未能换取销量提升。",
        overview_paragraphs=[],
        chart_section_intro="图表分析。",
        findings=[
            DataFinding(
                conclusion="折扣未有效促进销量，却伴随利润率的降低。",
                evidence="r=-0.216, p<0.001",
                method="相关性分析",
                importance=5,
            )
        ],
        suggestions=[],
        limitations=[],
    )

    LLMClient._sanitize_narrative_language(narrative)

    assert "侵蚀" not in narrative.executive_summary
    assert "促进销量" not in narrative.findings[0].conclusion
    assert "线性关联" in narrative.findings[0].conclusion


def test_problem_coverage_fills_five_top_distinctive_signals_after_bad_model_output():
    features = [
        {
            "source_key": f"distinctive_features.F{index:03d}",
            "title": f"信号{index}",
            "finding": f"特色信号{index}",
            "score": 101 - index,
        }
        for index in range(1, 7)
    ]
    valid_rows = {feature["source_key"]: feature for feature in features}

    problems = LLMClient._ensure_critical_problem_coverage([], {"features": features}, valid_rows)

    assert len(problems) == 5
    assert problems[0].source_stat_keys == ["distinctive_features.F001"]


def test_report_interpretation_separates_significance_from_correlation_strength():
    text = ReportGenerator._significance_text_from_evidence(
        "Pearson r=-0.0286, p=0.0049",
        "皮尔逊相关性分析",
    )

    assert "统计上可检测" in text
    assert "很弱" in text
    assert "较强显著" not in text
