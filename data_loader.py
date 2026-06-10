"""
数据读取与预处理模块
功能：识别并读取 .xlsx / .csv 文件，清洗表头、处理空行与缺失值，
      返回标准化的 pandas DataFrame。
"""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class DataLoader:
    """高鲁棒性数据加载器：自动识别格式、清洗字段名、处理空值与空行。"""

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def __init__(
        self,
        file_path: Union[str, Path],
        *,
        encoding: Optional[str] = None,
        csv_sep: Optional[str] = None,
        na_values: Optional[list[str]] = None,
        drop_empty_threshold: float = 0.9,
    ) -> None:
        """
        Parameters
        ----------
        file_path : str or Path
            数据文件路径（.xlsx 或 .csv）。
        encoding : str, optional
            CSV 编码。不指定时自动探测常见编码。
        csv_sep : str, optional
            CSV 分隔符。不指定时自动探测。
        na_values : list[str], optional
            额外视为缺失值的字符串列表。
        drop_empty_threshold : float, default 0.9
            当某行缺失比例 >= 此值时，删除该行。
        """
        self.file_path = Path(file_path)
        self.encoding = encoding
        self.csv_sep = csv_sep
        self.na_values = na_values or [
            "", "NA", "N/A", "n/a", "null", "NULL", "None", "none", "#N/A",
            "#VALUE!", "#REF!", "#DIV/0!", "#NUM!", "#NAME?", "NaN", "nan",
        ]
        self.drop_empty_threshold = drop_empty_threshold

        # 运行后填充
        self.raw_df: Optional[pd.DataFrame] = None
        self.cleaned_df: Optional[pd.DataFrame] = None
        self.meta: dict = {}

    # ------------------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """主入口：加载 → 清洗 → 返回清洗后 DataFrame。"""
        self._read_file()
        self._clean()
        logger.info(
            "数据加载完成。原始形状=%s，清洗后形状=%s",
            self.raw_df.shape,
            self.cleaned_df.shape,
        )
        return self.cleaned_df

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _read_file(self) -> None:
        """根据后缀分派读取方法。"""
        suffix = self.file_path.suffix.lower()
        readers = {
            ".csv": self._read_csv,
            ".xlsx": self._read_excel,
            ".xls": self._read_excel,
        }
        if suffix not in readers:
            raise ValueError(f"不支持的文件格式：{suffix}。仅支持 .csv / .xlsx / .xls")
        readers[suffix]()

    # ------------------------------------------------------------------

    def _read_csv(self) -> None:
        """读取 CSV，自动探测编码与分隔符。"""
        encodings_to_try = [self.encoding] if self.encoding else [
            "utf-8", "utf-8-sig", "gbk", "gb18030", "gb2312", "latin-1",
        ]
        seps_to_try = [self.csv_sep] if self.csv_sep else [",", ";", "\t", "|"]

        last_error: Optional[Exception] = None
        for enc in encodings_to_try:
            for sep in seps_to_try:
                try:
                    self.raw_df = pd.read_csv(
                        self.file_path,
                        encoding=enc,
                        sep=sep,
                        na_values=self.na_values,
                        keep_default_na=True,
                        skip_blank_lines=True,
                    )
                    self.meta["source_encoding"] = enc
                    self.meta["source_separator"] = sep
                    logger.debug("CSV 读取成功：encoding=%s, sep=%r", enc, sep)
                    return
                except (UnicodeDecodeError, UnicodeError) as e:
                    last_error = e
                    continue
                except Exception as e:
                    last_error = e
                    continue
        raise ValueError(
            f"无法读取 CSV 文件。尝试了 {len(encodings_to_try)} 种编码 × "
            f"{len(seps_to_try)} 种分隔符。最后错误：{last_error}"
        )

    # ------------------------------------------------------------------

    def _read_excel(self) -> None:
        """读取 Excel 文件（支持多 sheet —— 默认读取第一个）。"""
        engine = "openpyxl" if self.file_path.suffix.lower() == ".xlsx" else "xlrd"
        try:
            xls = pd.ExcelFile(self.file_path, engine=engine)
        except Exception:
            # 回退尝试
            xls = pd.ExcelFile(self.file_path, engine="openpyxl")

        sheet_names = xls.sheet_names
        self.meta["sheet_names"] = sheet_names
        self.meta["active_sheet"] = sheet_names[0]
        self.raw_df = pd.read_excel(
            xls,
            sheet_name=sheet_names[0],
            na_values=self.na_values,
            keep_default_na=True,
        )

    # ------------------------------------------------------------------

    def _clean(self) -> None:
        """执行完整清洗流水线。"""
        df = self.raw_df.copy()

        df = self._clean_column_names(df)
        df = self._drop_fully_empty_columns(df)
        df = self._drop_empty_rows(df, threshold=self.drop_empty_threshold)
        df = self._drop_duplicate_columns(df)
        df = self._infer_and_convert_types(df)
        df = df.reset_index(drop=True)

        self.cleaned_df = df
        self.meta["n_rows"] = len(df)
        self.meta["n_cols"] = len(df.columns)
        self.meta["columns"] = list(df.columns)
        self.meta["dtypes"] = {col: str(dt) for col, dt in df.dtypes.items()}

    # ------------------------------------------------------------------

    @staticmethod
    def _clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
        """清洗字段名：去首尾空白、替换非法字符、处理重复名。"""
        def _sanitize(name: str) -> str:
            name = str(name).strip()
            # 替换空白字符为下划线
            name = re.sub(r"\s+", "_", name)
            # 仅保留中英文、数字、下划线、点号
            name = re.sub(r"[^一-龥A-Za-z0-9_\.]", "", name)
            # 不能以数字或点开头
            if re.match(r"^[\d\.]", name):
                name = "col_" + name
            return name or "unnamed"

        df = df.copy()
        # 如果第一行看起来像表头但 pandas 未识别，则提升
        if all(df.columns.astype(str).str.match(r"^\d+$")):
            # 列名是数字（可能无表头），检查第一行
            first_row = df.iloc[0].astype(str)
            if first_row.apply(lambda s: bool(re.search(r"[一-龥A-Za-z]", s))).sum() >= len(df.columns) * 0.5:
                df.columns = first_row.values
                df = df.iloc[1:].reset_index(drop=True)

        df.columns = [_sanitize(c) for c in df.columns]

        # 处理重复列名：追加 _1, _2
        seen: dict[str, int] = {}
        new_cols = []
        for c in df.columns:
            if c in seen:
                seen[c] += 1
                new_cols.append(f"{c}_{seen[c]}")
            else:
                seen[c] = 0
                new_cols.append(c)
        df.columns = new_cols
        return df

    # ------------------------------------------------------------------

    @staticmethod
    def _drop_fully_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
        """删除全部为空的列。"""
        return df.dropna(axis=1, how="all")

    # ------------------------------------------------------------------

    @staticmethod
    def _drop_empty_rows(df: pd.DataFrame, threshold: float = 0.9) -> pd.DataFrame:
        """
        删除缺失比例 >= threshold 的行。
        同时删除所有值都是空字符串的行。
        """
        min_non_na = max(1, int(df.shape[1] * (1 - threshold)))
        df = df.dropna(thresh=min_non_na, axis=0)
        # 删除全为空字符串的行
        str_empty_mask = df.apply(
            lambda row: row.astype(str).str.strip().eq("").all(), axis=1
        )
        return df[~str_empty_mask]

    # ------------------------------------------------------------------

    @staticmethod
    def _drop_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
        """删除内容完全重复的列（保留第一个）。"""
        seen = {}
        keep = []
        for col in df.columns:
            # 将列转为 tuple 以便哈希
            col_tuple = tuple(df[col].values)
            if col_tuple not in seen:
                seen[col_tuple] = col
                keep.append(col)
        return df[keep]

    # ------------------------------------------------------------------

    @staticmethod
    def _infer_and_convert_types(df: pd.DataFrame) -> pd.DataFrame:
        """
        推断并转换数据类型：
        - 看起来是数值的 object 列 → numeric
        - 看起来是日期时间的 object 列 → datetime
        """
        df = df.copy()
        for col in df.columns:
            if df[col].dtype != "object":
                continue
            series = df[col].dropna()
            if len(series) == 0:
                continue

            # 尝试转数值
            converted = pd.to_numeric(series, errors="coerce")
            valid_ratio = converted.notna().sum() / len(series)
            if valid_ratio >= 0.85:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                continue

            # 尝试转日期时间
            converted_dt = pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
            dt_valid_ratio = converted_dt.notna().sum() / len(series)
            if dt_valid_ratio >= 0.85:
                df[col] = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)

        return df

    # ------------------------------------------------------------------

    def get_meta(self) -> dict:
        """返回加载元信息。"""
        return self.meta


# ------------------------------------------------------------------
# 便捷函数
# ------------------------------------------------------------------

def load_and_clean(
    file_path: Union[str, Path],
    **kwargs,
) -> pd.DataFrame:
    """一行调用：加载并清洗数据文件。"""
    loader = DataLoader(file_path, **kwargs)
    return loader.load()


# ------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    import sys

    if len(sys.argv) < 2:
        print("用法：python data_loader.py <file_path>")
        sys.exit(1)

    df = load_and_clean(sys.argv[1])
    print("\n清洗后数据预览：")
    print(df.head(10))
    print(f"\n形状：{df.shape}")
    print(f"列名：{list(df.columns)}")
    print(f"数据类型：\n{df.dtypes}")
