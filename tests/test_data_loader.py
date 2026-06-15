# -*- coding: utf-8 -*-
"""
data_loader.py 模块测试
"""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from data_loader import load_and_clean, DataLoader


class TestLoadAndClean:
    """测试数据加载与清洗。"""

    def test_load_csv_basic(self, sample_csv):
        df = load_and_clean(sample_csv)
        assert isinstance(df, pd.DataFrame)
        assert df.shape[0] > 0
        assert df.shape[1] >= 4

    def test_load_csv_columns(self, sample_csv):
        df = load_and_clean(sample_csv)
        expected_cols = {"score", "hours_studied", "department", "passed", "satisfaction"}
        assert expected_cols.issubset(set(df.columns))

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_and_clean("/nonexistent/path/file.csv")

    def test_empty_csv(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("col1,col2\n", encoding="utf-8")
        df = load_and_clean(str(path))
        assert isinstance(df, pd.DataFrame)

    def test_column_name_cleaning(self, tmp_path):
        """测试列名去空格和清理。"""
        path = tmp_path / "messy_headers.csv"
        path.write_text(
            "  score , department , passed \n"
            "75,CS,Yes\n"
            "80,Math,No\n",
            encoding="utf-8"
        )
        df = load_and_clean(str(path))
        # 列名不应有首尾空格
        for col in df.columns:
            assert col.strip() == col

    def test_invalid_format(self, tmp_path):
        """测试不支持的格式。"""
        path = tmp_path / "test.pdf"
        path.write_text("not a csv", encoding="utf-8")
        with pytest.raises((ValueError, FileNotFoundError, Exception)):
            load_and_clean(str(path))

    def test_chinese_encoding(self, tmp_path):
        """测试中文编码 CSV。"""
        path = tmp_path / "chinese.csv"
        path.write_text(
            "姓名,分数,部门\n"
            "张三,85,计算机\n"
            "李四,92,数学\n"
            "王五,78,物理\n",
            encoding="gbk"
        )
        df = load_and_clean(str(path))
        assert "姓名" in df.columns
        assert df.shape[0] >= 3


class TestDataLoaderClass:
    """测试 DataLoader 类的核心方法。"""

    def test_init(self, sample_csv):
        loader = DataLoader(sample_csv)
        assert loader.file_path == Path(sample_csv)
        assert loader.df is None  # 尚未加载

    def test_load(self, sample_csv):
        loader = DataLoader(sample_csv)
        df = loader.load()
        assert isinstance(df, pd.DataFrame)
        assert df.shape[0] > 0
