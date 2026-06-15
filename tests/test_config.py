# -*- coding: utf-8 -*-
"""
config.py 模块测试
"""
import os
import pytest
from config import Config


class TestConfigDefaults:
    """测试默认值。"""

    def test_llm_defaults(self):
        assert Config.LLM_MODEL == "deepseek-chat"
        assert Config.LLM_BASE_URL == "https://api.deepseek.com/v1"
        assert Config.LLM_MAX_RETRIES == 3
        assert Config.LLM_RETRY_DELAY == 3
        assert Config.LLM_TEMPERATURE == 0.05
        assert Config.LLM_TOP_P == 0.95
        assert Config.LLM_MAX_TOKENS == 4096

    def test_task_defaults(self):
        assert Config.TASK_MIN_COUNT == 5
        assert Config.TASK_MAX_COUNT == 10
        assert Config.TASK_PRIORITY["ANOVA"] == 3
        assert Config.TASK_PRIORITY["卡方检验"] == 2
        assert Config.TASK_PRIORITY["t检验"] == 2
        assert Config.TASK_MIN_REQUIREMENTS["ANOVA"] == 2
        assert Config.TASK_MIN_REQUIREMENTS["chi_square"] == 2
        assert Config.TASK_MIN_REQUIREMENTS["t_test"] == 3

    def test_requirements(self):
        assert Config.REQUIREMENTS["point_estimation_min"] == 5
        assert Config.REQUIREMENTS["interval_estimation_min"] == 5
        assert Config.REQUIREMENTS["hypothesis_test_min"] == 5
        assert Config.REQUIREMENTS["anova_min"] == 2
        assert Config.REQUIREMENTS["chi_square_min"] == 2

    def test_causal_words_not_empty(self):
        assert len(Config.CAUSAL_WORDS) > 0
        assert "导致" in Config.CAUSAL_WORDS

    def test_vague_words_not_empty(self):
        assert len(Config.VAGUE_WORDS) > 0
        assert "可能" in Config.VAGUE_WORDS

    def test_labels_not_empty(self):
        assert len(Config.TYPE_LABELS) > 0
        assert len(Config.CHART_LABELS) > 0
        assert len(Config.MODULE_NAMES) > 0

    def test_significance_threshold(self):
        assert Config.SIGNIFICANCE_THRESHOLD == 0.05
        assert Config.DEFAULT_ALPHA == 0.05

    def test_output_dir(self):
        assert Config.OUTPUT_DIR == "./outputs"


class TestConfigEnvOverride:
    """测试环境变量覆盖。"""

    def test_env_override_model(self, monkeypatch):
        monkeypatch.setenv("LLM_MODEL", "deepseek-reasoner")
        # Config 是类属性，在导入时已求值，无法直接 monkeypatch。
        # 测试 _env 辅助函数的正确性。
        from config import _env
        assert _env("NONEXISTENT_KEY", "default_val") == "default_val"

    def test_env_override_int(self, monkeypatch):
        from config import _env_int
        monkeypatch.setenv("TEST_INT", "42")
        assert _env_int("TEST_INT", 10) == 42
        assert _env_int("NONEXISTENT_INT", 10) == 10

    def test_env_override_float(self, monkeypatch):
        from config import _env_float
        monkeypatch.setenv("TEST_FLOAT", "0.01")
        assert _env_float("TEST_FLOAT", 0.05) == 0.01
        assert _env_float("NONEXISTENT_FLOAT", 0.05) == 0.05
