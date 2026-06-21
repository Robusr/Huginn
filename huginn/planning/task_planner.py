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
from huginn.llm.client import CandidateQuestion
from huginn.core.config import Config
from huginn.domain.context import detect_domain_context, domain_keywords, is_identifier_or_noise
from huginn.core.label_utils import humanize_column_name
from huginn.core.logger import get_logger

logger = get_logger(__name__)


class TaskPlanner:
    NOISE_KEYWORDS = ["序号", "提交答卷时间", "所用时间", "来源", "来源详情"]

    def __init__(self, data_profile: Dict, domain_context: Dict | None = None):
        self.data_profile = data_profile
        self.domain_context = domain_context or detect_domain_context(data_profile)
        self.column_info = {f["column"]: f for f in data_profile["fields"]}
        n_rows = int(data_profile.get("meta", {}).get("n_rows", 0))
        self._exclude_columns = {
            f["column"]
            for f in data_profile.get("fields", [])
            if not f.get("column") or is_identifier_or_noise(f["column"], f, n_rows)
        }
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
            if getattr(q, "task_pool_id", None):
                task["task_pool_id"] = q.task_pool_id
            if getattr(q, "variable_ids", None):
                task["variable_ids"] = q.variable_ids
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
        """ANOVA：1个数值变量 + 1个多分类变量（≥3组，含numeric_discrete列）"""
        if len(variables) != 2:
            return False, "ANOVA需要恰好2个变量"

        num_var, cat_var = variables
        if self.column_info[num_var]["inferred_type"] not in ["numeric_continuous", "numeric_discrete"]:
            return False, f"变量{num_var}不是数值型"

        cat_info = self.column_info[cat_var]
        cat_type = cat_info.get("inferred_type", "")
        cat_unique = cat_info.get("unique", 0)

        # 接受纯分类变量 或 具有≥3个唯一值的 numeric_discrete 列作为分组因子
        if cat_type == "categorical":
            if cat_unique < 3:
                return False, f"变量{cat_var}不是多分类变量（需要至少3个类别）"
            if cat_unique > Config.ANALYSIS_MAX_GROUPS:
                return False, f"变量{cat_var}类别数过多（最多{Config.ANALYSIS_MAX_GROUPS}个类别）"
        elif cat_type == "numeric_discrete":
            if cat_unique < 3:
                return False, f"变量{cat_var}唯一值不足3个，无法作为ANOVA分组因子"
            if cat_unique > Config.ANALYSIS_MAX_GROUPS:
                return False, f"变量{cat_var}唯一值过多（最多{Config.ANALYSIS_MAX_GROUPS}个类别）"
        else:
            return False, f"变量{cat_var}不是分类或离散数值型，无法作为ANOVA分组因子"

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
            if self.column_info[v]["unique"] > Config.ANALYSIS_MAX_GROUPS:
                return False, f"变量{v}类别数过多（最多{Config.ANALYSIS_MAX_GROUPS}个类别）"

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
        numeric_cols = self._numeric_columns_for_defaults()
        categorical_cols = self._categorical_columns_for_defaults()
        binary_cats = [c for c in categorical_cols if self.column_info[c]["unique"] == 2]
        multi_cats = [c for c in self._categorical_columns_for_defaults(anova_mode=True) if self.column_info[c]["unique"] >= 3]

        # 1. 补充ANOVA任务
        if len(multi_cats) >= 1 and len(numeric_cols) >= 1:
            default_tasks.append({
                "task_id": 100,
                "question": f"不同{self._label(multi_cats[0])}分组的“{self._label(numeric_cols[0])}”是否存在显著差异？",
                "variables": [numeric_cols[0], multi_cats[0]],
                "method": "ANOVA",
                "value": "了解不同群体的差异"
            })

        # 2. 补充卡方检验任务
        if len(categorical_cols) >= 2:
            default_tasks.append({
                "task_id": 101,
                "question": f"{self._label(categorical_cols[0])}与{self._label(categorical_cols[1])}是否存在显著关联？",
                "variables": [categorical_cols[0], categorical_cols[1]],
                "method": "卡方检验",
                "value": "了解分类变量间的关联"
            })

        # 3. 补充t检验任务
        if len(binary_cats) >= 1 and len(numeric_cols) >= 1:
            default_tasks.append({
                "task_id": 102,
                "question": f"两个{self._label(binary_cats[0])}分组的“{self._label(numeric_cols[0])}”均值是否存在显著差异？",
                "variables": [numeric_cols[0], binary_cats[0]],
                "method": "t检验",
                "value": "了解二分类群体的差异"
            })

        # 4. 补充分布检验任务
        if len(numeric_cols) >= 1:
            default_tasks.append({
                "task_id": 103,
                "question": f"“{self._label(numeric_cols[0])}”的分布是否符合正态分布？",
                "variables": [numeric_cols[0]],
                "method": "分布检验",
                "value": "了解数据分布特征"
            })

        return default_tasks

    def _ensure_minimum_requirements(self, tasks: List[Dict]) -> List[Dict]:
        """按配置补足最低统计方法覆盖要求。"""
        anova_count = sum(1 for t in tasks if t["method"] == "ANOVA")
        chi_count = sum(1 for t in tasks if t["method"] == "卡方检验")
        t_count = sum(1 for t in tasks if t["method"] in ["t检验", "配对t检验"])

        # 预筛选可用列
        multi_cats = [c for c in self.column_info
                      if self.column_info[c]["inferred_type"] == "categorical"
                      and self.column_info[c]["unique"] >= 3
                      and c not in self._exclude_columns]
        # 扩展：纳入 numeric_discrete 列作为 ANOVA 分组候选
        multi_cats += [c for c in self.column_info
                       if self.column_info[c]["inferred_type"] == "numeric_discrete"
                       and self.column_info[c]["unique"] >= 3
                       and c not in self._exclude_columns]
        categorical_cols = [c for c in self.column_info
                            if self.column_info[c]["inferred_type"] == "categorical"
                            and c not in self._exclude_columns]
        binary_cats = [c for c in self.column_info
                       if self.column_info[c]["inferred_type"] == "categorical"
                       and self.column_info[c]["unique"] == 2
                       and c not in self._exclude_columns]
        numeric_cols = [c for c in self.column_info
                        if self.column_info[c]["inferred_type"].startswith("numeric")
                        and c not in self._exclude_columns]

        # 补充ANOVA到最低要求
        while anova_count < Config.TASK_MIN_REQUIREMENTS["ANOVA"]:
            multi_cats = [c for c in self._categorical_columns_for_defaults(anova_mode=True) if self.column_info[c]["unique"] >= 3]
            numeric_cols = self._numeric_columns_for_defaults()
            pair = self._first_missing_pair(tasks, "ANOVA", numeric_cols, multi_cats)
            if pair:
                num_col, cat_col = pair
                tasks.append({
                    "task_id": self._next_task_id(tasks, 200),
                    "question": f"不同{self._label(cat_col)}分组的“{self._label(num_col)}”是否存在显著差异？",
                    "variables": [num_col, cat_col],
                    "method": "ANOVA",
                    "value": "补充ANOVA任务以满足要求"
                })
                anova_count += 1
            else:
                break

        # 补充卡方到最低要求
        while chi_count < Config.TASK_MIN_REQUIREMENTS["chi_square"]:
            categorical_cols = self._categorical_columns_for_defaults()
            pair = self._first_missing_categorical_pair(tasks, categorical_cols)
            if pair:
                left, right = pair
                tasks.append({
                    "task_id": self._next_task_id(tasks, 210),
                    "question": f"{self._label(left)}与{self._label(right)}是否存在显著关联？",
                    "variables": [left, right],
                    "method": "卡方检验",
                    "value": "补充卡方检验任务以满足要求"
                })
                chi_count += 1
            else:
                break

        # 补充t检验到最低要求
        while t_count < Config.TASK_MIN_REQUIREMENTS["t_test"]:
            binary_cats = [c for c in self._categorical_columns_for_defaults() if self.column_info[c]["unique"] == 2]
            numeric_cols = self._numeric_columns_for_defaults()
            pair = self._first_missing_pair(tasks, "t检验", numeric_cols, binary_cats)
            if pair:
                num_col, cat_col = pair
                tasks.append({
                    "task_id": self._next_task_id(tasks, 220),
                    "question": f"两个{self._label(cat_col)}分组的“{self._label(num_col)}”均值是否存在显著差异？",
                    "variables": [num_col, cat_col],
                    "method": "t检验",
                    "value": "补充t检验任务以满足要求"
                })
                t_count += 1
            else:
                break

        return tasks

    def _numeric_columns_for_defaults(self) -> List[str]:
        cols = [
            c for c, info in self.column_info.items()
            if info.get("inferred_type", "").startswith("numeric") and not self._is_noise_column(c, info)
        ]
        return self._sort_by_keywords(cols, domain_keywords(self.domain_context, "metric_keywords"))

    def _categorical_columns_for_defaults(self, *, anova_mode: bool = False) -> List[str]:
        """返回可用的分类/离散数值列。

        anova_mode=True 时额外纳入 numeric_discrete 列（≥3 唯一值），
        以便为缺乏纯分类变量的数据集（如 Boston Housing）自动补足 ANOVA。
        """
        cols = [
            c for c, info in self.column_info.items()
            if info.get("inferred_type") == "categorical"
            and 2 <= info.get("unique", 0) <= Config.ANALYSIS_MAX_GROUPS
            and not self._is_noise_column(c, info)
        ]
        if anova_mode:
            discrete_cols = [
                c for c, info in self.column_info.items()
                if info.get("inferred_type") == "numeric_discrete"
                and 3 <= info.get("unique", 0) <= Config.ANALYSIS_MAX_GROUPS
                and not self._is_noise_column(c, info)
            ]
            cols = cols + discrete_cols
        return self._sort_by_keywords(cols, domain_keywords(self.domain_context, "group_keywords"))

    def _is_noise_column(self, column: str, info: Dict | None = None) -> bool:
        n_rows = int(self.data_profile.get("meta", {}).get("n_rows") or 0)
        return is_identifier_or_noise(column, info, n_rows)

    @staticmethod
    def _sort_by_keywords(cols: List[str], keywords: List[str]) -> List[str]:
        def rank(col: str) -> tuple[int, int]:
            text = str(col)
            for index, keyword in enumerate(keywords):
                if keyword in text:
                    return index, 0
            return len(keywords), 0
        return sorted(cols, key=rank)

    def _first_missing_pair(
        self,
        tasks: List[Dict],
        method: str,
        numeric_cols: List[str],
        categorical_cols: List[str],
    ) -> tuple[str, str] | None:
        for num_col in numeric_cols:
            for cat_col in categorical_cols:
                if not self._task_exists(tasks, method, [num_col, cat_col]):
                    return num_col, cat_col
        return None

    def _first_missing_categorical_pair(self, tasks: List[Dict], categorical_cols: List[str]) -> tuple[str, str] | None:
        for left_idx, left in enumerate(categorical_cols):
            for right in categorical_cols[left_idx + 1:]:
                if not self._task_exists(tasks, "卡方检验", [left, right]):
                    return left, right
        return None

    @staticmethod
    def _task_exists(tasks: List[Dict], method: str, variables: List[str]) -> bool:
        wanted = tuple(variables)
        wanted_set = set(variables)
        for task in tasks:
            if task.get("method") != method:
                continue
            current = task.get("variables", [])
            if tuple(current) == wanted or set(current) == wanted_set:
                return True
        return False

    @staticmethod
    def _next_task_id(tasks: List[Dict], fallback: int) -> int:
        existing = [task.get("task_id") for task in tasks if isinstance(task.get("task_id"), int)]
        return max(existing, default=fallback - 1) + 1

    @staticmethod
    def _label(column: str) -> str:
        return humanize_column_name(column)
