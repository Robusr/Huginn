# -*- coding: utf-8 -*-
"""
@File    : analysis_engine_patch.py
@Author  : Huginn
@Date    : 2026/6/16
@Description: 向后兼容 shim — 所有功能已合并至 analysis_engine.AnalysisEngine
@Software: PyCharm
"""

"""
向后兼容封装
run_tasks() 及所有 _execute_* 方法已直接集成到 analysis_engine.AnalysisEngine 中。
此文件保留以确保现有 import 路径不中断。
"""
from analysis_engine import AnalysisEngine  # noqa: F401
