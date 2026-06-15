# -*- coding: utf-8 -*-
"""
测试夹具和共享配置
"""
import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

# 将项目根目录加入路径，确保可以导入项目模块
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_df():
    """创建一个具有已知属性的小型 DataFrame 用于测试。"""
    np.random.seed(42)
    n = 60
    return pd.DataFrame({
        "score": np.random.normal(75, 15, n),
        "hours_studied": np.random.uniform(0, 20, n),
        "department": np.random.choice(["CS", "Math", "Physics"], n),
        "passed": np.random.choice(["Yes", "No"], n),
        "satisfaction": np.random.randint(1, 6, n),
    })


@pytest.fixture
def sample_csv(tmp_path, sample_df):
    """将 sample_df 写入临时 CSV 文件。"""
    path = tmp_path / "test.csv"
    sample_df.to_csv(path, index=False, encoding="utf-8")
    return str(path)


@pytest.fixture
def sample_data_profile():
    """构造一个模拟的 data_profile 字典，用于测试 task_planner。"""
    return {
        "meta": {"n_rows": 60, "n_columns": 5, "total_missing_pct": 0.0},
        "overview": {
            "field_type_counts": {
                "numeric_continuous": 2,
                "numeric_discrete": 1,
                "categorical": 2,
            }
        },
        "fields": [
            {"column": "score", "inferred_type": "numeric_continuous", "count": 60, "missing_pct": 0.0, "unique": 55},
            {"column": "hours_studied", "inferred_type": "numeric_continuous", "count": 60, "missing_pct": 0.0, "unique": 58},
            {"column": "satisfaction", "inferred_type": "numeric_discrete", "count": 60, "missing_pct": 0.0, "unique": 5},
            {"column": "department", "inferred_type": "categorical", "count": 60, "missing_pct": 0.0, "unique": 3},
            {"column": "passed", "inferred_type": "categorical", "count": 60, "missing_pct": 0.0, "unique": 2},
        ],
    }
