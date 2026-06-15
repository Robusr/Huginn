# -*- coding: utf-8 -*-
"""
task_planner.py 模块测试
"""
import pytest
from config import Config
from task_planner import TaskPlanner
from llm_client import CandidateQuestion


class TestTaskValidation:
    """测试任务验证逻辑。"""

    def test_validate_t_test_valid(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        is_valid, msg = planner._validate_t_test(["score", "passed"])
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_t_test_wrong_type(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        is_valid, msg = planner._validate_t_test(["department", "score"])
        assert not is_valid

    def test_validate_t_test_not_binary(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        is_valid, msg = planner._validate_t_test(["score", "department"])
        assert not is_valid

    def test_validate_anova_valid(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        is_valid, msg = planner._validate_anova(["score", "department"])
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_anova_too_few_groups(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        is_valid, msg = planner._validate_anova(["score", "passed"])
        assert not is_valid

    def test_validate_chi_square_valid(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        is_valid, msg = planner._validate_chi_square(["department", "passed"])
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_correlation_valid(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        is_valid, msg = planner._validate_correlation(["score", "hours_studied"])
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_distribution_valid(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        is_valid, msg = planner._validate_distribution_test(["score"])
        assert is_valid, f"Expected valid, got: {msg}"

    def test_validate_unknown_method(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        assert "invalid_method" not in planner.valid_methods


class TestTaskFiltering:
    """测试任务筛选和转换。"""

    def test_filter_invalid_variable_removed(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        questions = [
            CandidateQuestion(
                question="不存在的变量分析",
                variables=["nonexistent_col", "score"],
                method="t检验",
                value="测试",
            )
        ]
        valid = planner.filter_and_convert_tasks(questions)
        # 由于只有1个无效问题被过滤，应自动补充默认任务
        assert len(valid) >= 1

    def test_valid_question_passes(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        questions = [
            CandidateQuestion(
                question="不同passed组在score上是否存在差异？",
                variables=["score", "passed"],
                method="t检验",
                value="了解差异",
            )
        ]
        valid = planner.filter_and_convert_tasks(questions)
        assert any(t["task_id"] == 0 for t in valid)

    def test_priority_sorting(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        questions = [
            CandidateQuestion(
                question="检验分布",
                variables=["score"],
                method="分布检验",
                value="low priority",
            ),
            CandidateQuestion(
                question="ANOVA分析",
                variables=["score", "department"],
                method="ANOVA",
                value="high priority",
            ),
        ]
        valid = planner.filter_and_convert_tasks(questions)
        # ANOVA 应该排在分布检验前面
        anova_idx = next(i for i, t in enumerate(valid) if t["method"] == "ANOVA")
        dist_idx = next(i for i, t in enumerate(valid) if t["method"] == "分布检验")
        assert anova_idx < dist_idx

    def test_minimum_requirements_enforced(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        questions = [
            CandidateQuestion(
                question="solitary question",
                variables=["score"],
                method="分布检验",
                value="only one",
            )
        ]
        valid = planner.filter_and_convert_tasks(questions)
        # 应自动补充以满足最低要求
        method_counts = {}
        for t in valid:
            method_counts[t["method"]] = method_counts.get(t["method"], 0) + 1
        assert len(valid) >= Config.TASK_MIN_COUNT

    def test_max_tasks_not_exceeded(self, sample_data_profile):
        planner = TaskPlanner(sample_data_profile)
        # 生成大量候选问题
        questions = []
        for i in range(20):
            questions.append(CandidateQuestion(
                question=f"检验 {i}",
                variables=["score"],
                method="分布检验",
                value=f"test {i}",
            ))
        valid = planner.filter_and_convert_tasks(questions)
        assert len(valid) <= Config.TASK_MAX_COUNT
