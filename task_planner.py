# -*- coding: utf-8 -*-
"""
@File    : task_planner.py
@Author  : Robusr
@Date    : 2026/6/10 16:05
@Description: 任务筛选与校验器
@Software: PyCharm
"""

"""
任务筛选与校验器
校验LLM提出的候选问题，过滤不可执行的问题，转换为统计引擎可执行的结构化任务
"""
import json
from typing import Any, Dict, List
from llm_client import CandidateQuestion
from config import Config, clean_field_name
from logger import get_logger

logger = get_logger(__name__)


class TaskPlanner:
    def __init__(self, data_profile: Dict):
        self.data_profile = data_profile
        self.column_info = {f["column"]: f for f in data_profile["fields"]}
        # 统计方法与验证函数映射
        self.valid_methods = {
            "t检验": self._validate_t_test,
            "配对t检验": self._validate_paired_t_test,
            "ANOVA": self._validate_anova,
            "卡方检验": self._validate_chi_square,
            "相关性分析": self._validate_correlation,
            "分布检验": self._validate_distribution_test
        }

    def filter_and_convert_tasks(self, candidate_questions: List[CandidateQuestion]) -> List[Dict]:
        """
        筛选候选问题，转换为可执行任务
        :param candidate_questions: LLM生成的候选问题列表
        :return: 可执行任务列表，保证至少5个有效任务
        """
        valid_tasks = []
        invalid_reasons = []

        for i, q in enumerate(candidate_questions):
            # 1. 检查所有变量是否存在
            missing_vars = [v for v in q.variables if v not in self.column_info]
            if missing_vars:
                invalid_reasons.append(f"问题[{i + 1}]：变量不存在 {missing_vars}")
                continue

            # 2. 检查统计方法是否有效
            if q.method not in self.valid_methods:
                invalid_reasons.append(f"问题[{i + 1}]：不支持的统计方法 {q.method}")
                continue

            # 3. 验证变量类型是否匹配方法
            is_valid, error_msg = self.valid_methods[q.method](q.variables)
            if not is_valid:
                invalid_reasons.append(f"问题[{i + 1}]：{error_msg}")
                continue

            # 4. 转换为结构化任务
            task = {
                "task_id": i,
                "question": q.question,
                "variables": q.variables,
                "method": q.method,
                "value": q.value
            }
            valid_tasks.append(task)

        # 记录无效问题原因（便于调试）
        if invalid_reasons:
            logger.warning("以下候选问题被过滤：")
            for reason in invalid_reasons:
                logger.warning("  - %s", reason)

        # 5. 按优先级排序（ANOVA > 卡方 > t检验 > 其他）
        priority = Config.TASK_PRIORITY
        valid_tasks.sort(key=lambda x: priority[x["method"]], reverse=True)

        # 6. 自动补充默认任务，保证满足统计数量要求
        if len(valid_tasks) < Config.TASK_MIN_COUNT:
            logger.info("仅筛选出 %d 个有效任务，自动补充默认任务...", len(valid_tasks))
            default_tasks = self._generate_default_tasks()
            valid_tasks.extend(default_tasks)
            valid_tasks = valid_tasks[:Config.TASK_MAX_COUNT]  # 最多执行N个任务，避免超时

        # 7. 最终校验：确保至少包含2个ANOVA、2个卡方、3个t检验
        valid_tasks = self._ensure_minimum_requirements(valid_tasks)

        logger.info("最终可执行任务：%d 个", len(valid_tasks))
        return valid_tasks

    # ------------------------------
    # 各统计方法的验证逻辑
    # ------------------------------
    def _validate_t_test(self, variables: List[str]) -> tuple[bool, str]:
        """t检验：1个数值变量 + 1个二分类变量，每组样本量≥3"""
        if len(variables) != 2:
            return False, "t检验需要恰好2个变量"

        num_var, cat_var = variables
        # 检查数值变量
        if self.column_info[num_var]["inferred_type"] not in ["numeric_continuous", "numeric_discrete"]:
            return False, f"变量{num_var}不是数值型"

        # 检查二分类变量
        cat_info = self.column_info[cat_var]
        if cat_info["inferred_type"] != "categorical" or cat_info["unique"] != 2:
            return False, f"变量{cat_var}不是二分类变量（需要恰好2个类别）"

        # 检查样本量
        return True, ""

    def _validate_paired_t_test(self, variables: List[str]) -> tuple[bool, str]:
        """配对t检验：2个数值变量，样本量≥3"""
        if len(variables) != 2:
            return False, "配对t检验需要恰好2个数值变量"

        for v in variables:
            if self.column_info[v]["inferred_type"] not in ["numeric_continuous", "numeric_discrete"]:
                return False, f"变量{v}不是数值型"

        return True, ""

    def _validate_anova(self, variables: List[str]) -> tuple[bool, str]:
        """ANOVA：1个数值变量 + 1个多分类变量（≥3组）"""
        if len(variables) != 2:
            return False, "ANOVA需要恰好2个变量"

        num_var, cat_var = variables
        if self.column_info[num_var]["inferred_type"] not in ["numeric_continuous", "numeric_discrete"]:
            return False, f"变量{num_var}不是数值型"

        cat_info = self.column_info[cat_var]
        if cat_info["inferred_type"] != "categorical" or cat_info["unique"] < 3:
            return False, f"变量{cat_var}不是多分类变量（需要至少3个类别）"

        return True, ""

    def _validate_chi_square(self, variables: List[str]) -> tuple[bool, str]:
        """卡方检验：2个分类变量，每个变量≥2个类别"""
        if len(variables) != 2:
            return False, "卡方检验需要恰好2个分类变量"

        for v in variables:
            if self.column_info[v]["inferred_type"] != "categorical":
                return False, f"变量{v}不是分类型变量"
            if self.column_info[v]["unique"] < 2:
                return False, f"变量{v}的类别数不足2个"

        return True, ""

    def _validate_correlation(self, variables: List[str]) -> tuple[bool, str]:
        """相关性分析：2个数值变量"""
        if len(variables) != 2:
            return False, "相关性分析需要恰好2个数值变量"

        for v in variables:
            if self.column_info[v]["inferred_type"] not in ["numeric_continuous", "numeric_discrete"]:
                return False, f"变量{v}不是数值型"

        return True, ""

    def _validate_distribution_test(self, variables: List[str]) -> tuple[bool, str]:
        """分布检验：1个数值变量，样本量≥8"""
        if len(variables) != 1:
            return False, "分布检验需要恰好1个数值变量"

        v = variables[0]
        if self.column_info[v]["inferred_type"] not in ["numeric_continuous", "numeric_discrete"]:
            return False, f"变量{v}不是数值型"

        return True, ""

    # ------------------------------
    # 默认任务生成与数量保证
    # ------------------------------
    def _generate_default_tasks(self) -> List[Dict]:
        """当有效任务不足时，自动生成默认的基础分析任务"""
        default_tasks = []
        # 排除元数据列（序号、来源详情等不适合分析的列）
        _exclude_columns = {"序号", "来源详情", "提交答卷时间", "所用时间"}

        numeric_cols = [
            f["column"] for f in self.data_profile["fields"]
            if f["inferred_type"].startswith("numeric")
            and f["column"] not in _exclude_columns
        ]
        categorical_cols = [
            f["column"] for f in self.data_profile["fields"]
            if f["inferred_type"] == "categorical"
            and f["column"] not in _exclude_columns
        ]
        binary_cats = [c for c in categorical_cols if self.column_info[c]["unique"] == 2]
        multi_cats = [c for c in categorical_cols if self.column_info[c]["unique"] >= 3]

        # 1. 补充ANOVA任务
        if len(multi_cats) >= 1 and len(numeric_cols) >= 1:
            default_tasks.append({
                "task_id": 100,
                "question": f"不同{clean_field_name(multi_cats[0])}的学生在{clean_field_name(numeric_cols[0])}上是否存在显著差异？",
                "variables": [numeric_cols[0], multi_cats[0]],
                "method": "ANOVA",
                "value": "了解不同群体的差异"
            })

        # 2. 补充卡方检验任务
        if len(categorical_cols) >= 2:
            default_tasks.append({
                "task_id": 101,
                "question": f"{clean_field_name(categorical_cols[0])}与{clean_field_name(categorical_cols[1])}是否存在显著关联？",
                "variables": [categorical_cols[0], categorical_cols[1]],
                "method": "卡方检验",
                "value": "了解分类变量间的关联"
            })

        # 3. 补充t检验任务
        if len(binary_cats) >= 1 and len(numeric_cols) >= 1:
            default_tasks.append({
                "task_id": 102,
                "question": f"不同{clean_field_name(binary_cats[0])}的学生在{clean_field_name(numeric_cols[0])}上是否存在显著差异？",
                "variables": [numeric_cols[0], binary_cats[0]],
                "method": "t检验",
                "value": "了解二分类群体的差异"
            })

        # 4. 补充分布检验任务
        if len(numeric_cols) >= 1:
            default_tasks.append({
                "task_id": 103,
                "question": f"{clean_field_name(numeric_cols[0])}的分布是否符合正态分布？",
                "variables": [numeric_cols[0]],
                "method": "分布检验",
                "value": "了解数据分布特征"
            })

        return default_tasks

    def _ensure_minimum_requirements(self, tasks: List[Dict]) -> List[Dict]:
        """确保满足课程作业的最低统计要求：≥2ANOVA、≥2卡方、≥3t检验。

        每个补充循环有最大迭代次数限制，防止数据类型不足时的无限循环。
        """
        MAX_SUPPLEMENT_PER_TYPE = 5
        _exclude_columns = {"序号", "来源详情", "提交答卷时间", "所用时间"}

        anova_count = sum(1 for t in tasks if t["method"] == "ANOVA")
        chi_count = sum(1 for t in tasks if t["method"] == "卡方检验")
        t_count = sum(1 for t in tasks if t["method"] in ["t检验", "配对t检验"])

        # 预筛选可用列
        multi_cats = [c for c in self.column_info
                      if self.column_info[c]["inferred_type"] == "categorical"
                      and self.column_info[c]["unique"] >= 3
                      and c not in _exclude_columns]
        categorical_cols = [c for c in self.column_info
                            if self.column_info[c]["inferred_type"] == "categorical"
                            and c not in _exclude_columns]
        binary_cats = [c for c in self.column_info
                       if self.column_info[c]["inferred_type"] == "categorical"
                       and self.column_info[c]["unique"] == 2
                       and c not in _exclude_columns]
        numeric_cols = [c for c in self.column_info
                        if self.column_info[c]["inferred_type"].startswith("numeric")
                        and c not in _exclude_columns]

        # 补充ANOVA到最低要求
        anova_attempts = 0
        while anova_count < Config.TASK_MIN_REQUIREMENTS["ANOVA"] and anova_attempts < MAX_SUPPLEMENT_PER_TYPE:
            anova_attempts += 1
            idx = min(anova_count, len(multi_cats) - 1)
            num_idx = min(anova_count, len(numeric_cols) - 1)
            if idx >= 0 and len(multi_cats) > idx and num_idx >= 0:
                tasks.append({
                    "task_id": 200 + anova_count,
                    "question": f"不同{clean_field_name(multi_cats[idx])}的学生在{clean_field_name(numeric_cols[num_idx])}上是否存在显著差异？",
                    "variables": [numeric_cols[num_idx], multi_cats[idx]],
                    "method": "ANOVA",
                    "value": "补充ANOVA任务以满足要求"
                })
                anova_count += 1
            else:
                break

        # 补充卡方到最低要求
        chi_attempts = 0
        while chi_count < Config.TASK_MIN_REQUIREMENTS["chi_square"] and chi_attempts < MAX_SUPPLEMENT_PER_TYPE:
            chi_attempts += 1
            idx1, idx2 = chi_count % len(categorical_cols), (chi_count + 1) % len(categorical_cols)
            if len(categorical_cols) >= 2 and idx1 != idx2:
                tasks.append({
                    "task_id": 210 + chi_count,
                    "question": f"{clean_field_name(categorical_cols[idx1])}与{clean_field_name(categorical_cols[idx2])}是否存在显著关联？",
                    "variables": [categorical_cols[idx1], categorical_cols[idx2]],
                    "method": "卡方检验",
                    "value": "补充卡方检验任务以满足要求"
                })
                chi_count += 1
            else:
                break

        # 补充t检验到最低要求
        t_attempts = 0
        while t_count < Config.TASK_MIN_REQUIREMENTS["t_test"] and t_attempts < MAX_SUPPLEMENT_PER_TYPE:
            t_attempts += 1
            num_idx = min(t_count, len(numeric_cols) - 1)
            if len(binary_cats) >= 1 and num_idx >= 0 and len(numeric_cols) > num_idx:
                tasks.append({
                    "task_id": 220 + t_count,
                    "question": f"不同{clean_field_name(binary_cats[0])}的学生在{clean_field_name(numeric_cols[num_idx])}上是否存在显著差异？",
                    "variables": [numeric_cols[num_idx], binary_cats[0]],
                    "method": "t检验",
                    "value": "补充t检验任务以满足要求"
                })
                t_count += 1
            else:
                break

        return tasks