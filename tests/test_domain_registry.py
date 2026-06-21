# -*- coding: utf-8 -*-
"""Tests for domain_registry.py and field_registry.py."""
import pytest
from huginn.domain.registry import (
    detect_domain, get_domain_config, FieldRole,
    RETAIL_SALES, EDUCATION_SURVEY, GENERAL_BUSINESS,
)
from huginn.domain.fields import build_field_registry, infer_field_role


class TestDomainDetection:
    def test_retail_detection(self):
        cols = ['Order_ID', 'Sales', 'Profit', 'Discount', 'Category',
                'SubCategory', 'Region', 'Segment', 'Ship_Mode', 'Quantity']
        domain = detect_domain(cols)
        assert domain.key == 'retail_sales'

    def test_education_detection(self):
        cols = ['col_1_性别', 'col_2_年级', 'col_3_满意度', 'col_4_能力自评',
                'col_5_学习时间', '提交答卷时间', '序号']
        domain = detect_domain(cols)
        # Education survey or general
        assert domain.key in ('education_survey', 'general_business')

    def test_general_fallback(self):
        cols = ['Name', 'Age', 'City', 'Height']
        domain = detect_domain(cols)
        assert domain.key == 'general_business'

    def test_domain_config_retail(self):
        dc = RETAIL_SALES
        assert dc.name == '零售销售'
        assert 'loss_driver_analysis' in dc.active_modules
        assert 'discount_response_analysis' in dc.active_modules

    def test_domain_config_education(self):
        dc = EDUCATION_SURVEY
        assert dc.name == '教育问卷'
        assert len(dc.active_modules) == 0  # No business modules

    def test_get_domain_by_key(self):
        got = get_domain_config(domain_key='retail_sales')
        assert got.name == '零售销售'

    def test_get_domain_by_columns(self):
        cols = ['Order_ID', 'Sales', 'Profit', 'Category']
        got = get_domain_config(column_names=cols)
        assert got.key == 'retail_sales'

    def test_empty_columns(self):
        domain = detect_domain([])
        assert domain.key == 'general_business'


class TestFieldRole:
    def test_retail_col_roles(self):
        profile = {
            "fields": [
                {"column": "Order_ID", "inferred_type": "categorical", "unique": 5000, "missing_pct": 0},
                {"column": "Sales", "inferred_type": "numeric_continuous", "unique": 9000, "missing_pct": 0},
                {"column": "Profit", "inferred_type": "numeric_continuous", "unique": 8000, "missing_pct": 0},
                {"column": "Category", "inferred_type": "categorical", "unique": 5, "missing_pct": 0},
            ]
        }
        registry = build_field_registry(profile, RETAIL_SALES)
        assert registry['fields']['Order_ID']['role'] == FieldRole.ID
        assert registry['fields']['Sales']['role'] == FieldRole.REVENUE
        assert registry['fields']['Profit']['role'] == FieldRole.PROFIT
        assert registry['fields']['Category']['role'] == FieldRole.CATEGORY_DIM

    def test_id_field_filtering(self):
        registry = build_field_registry(
            {"fields": [{"column": "zip", "inferred_type": "numeric_discrete", "unique": 100, "missing_pct": 0}]},
            GENERAL_BUSINESS,
        )
        # zip/postal should be meaningless
        assert registry['fields']['zip']['is_meaningless'] is True

    def test_summary_has_profit(self):
        profile = {
            "fields": [
                {"column": "Profit", "inferred_type": "numeric_continuous", "unique": 100, "missing_pct": 0},
            ]
        }
        registry = build_field_registry(profile, RETAIL_SALES)
        assert registry['summary']['has_profit_data'] is True
