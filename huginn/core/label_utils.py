# -*- coding: utf-8 -*-
"""共享字段名与选项名中文化工具。"""

from __future__ import annotations

import re
from typing import Any


BASE_COLUMN_LABELS = {
    "序号": "序号",
    "提交答卷时间": "提交时间",
    "所用时间": "答题用时",
    "来源": "来源",
    "来源详情": "来源详情",
    "col_1_你的性别是": "性别",
    "col_2_你在进入科创实验班之前的专业": "入班前专业",
    "col_3_你觉得与科创实验班其他同学相比你目前大一下学期的数学能力": "数学能力自评",
    "col_4_你觉得与科创实验班其他同学相比你目前大一下学期的编程能力": "编程能力自评",
    "col_5_你平均每周在这门课上花费的时间上课复习完成作业是几小时310小时": "课程投入时间",
    "col_6对这门课的作业你一般是": "作业完成习惯",
    "col_7在这门课的课堂上你一般坐在": "课堂座位区域",
    "col_8_你平均每周花多少时间在运动锻炼上": "每周运动时间",
    "col_9_你平均每周花多少时间在电子游戏上含手机游戏电脑游戏主机游戏等": "每周游戏时间",
    "col_10_你平均每周花多少时间在社交网络与短视频上含微信朋友圈微博小红书抖音快手等": "每周社交短视频时间",
    "Sales": "销售额",
    "Profit": "利润",
    "Quantity": "销售数量",
    "Discount": "折扣率",
    "Category": "产品品类",
    "Sub_Category": "子品类",
    "Sub-Category": "子品类",
    "SubCategory": "子品类",
    "Region": "区域",
    "Segment": "客户类型",
    "Ship_Mode": "运输方式",
    "Ship Mode": "运输方式",
    "Order_Date": "订单日期",
    "Ship_Date": "发货日期",
}


MEASURE_PREFIX_LABELS = [
    ("col_17", "创业意愿"),
    ("col_16", "总体机会判断"),
    ("col_15", "竞争激烈度判断"),
    ("col_14", "社会价值判断"),
    ("col_13", "专业契合度"),
    ("col_12", "技术难度认知"),
    ("col_11", "消费者兴趣"),
]


QUESTION_PHRASE_LABELS = {
    "从消费者而非创业者的角度你对以下每个赛道的兴趣程度如何该领域会出现你希望了解甚至购买的产品吗": "消费者兴趣",
    "从技术人员的角度你觉得该赛道创业所需的平均技术难度如何": "技术难度认知",
    "你认为自己学习的专业技能与以下赛道的契合程度如何": "专业契合度",
    "你认为该赛道创业项目的社会价值有多大": "社会价值判断",
    "你认为今后五年该赛道中的创业竞争激烈程度如何领域内是否容易找到独特的产品定位有多少类似的初创团队及产品在同一领域竞争请评分": "竞争激烈度判断",
    "你认为今后五年该赛道中的创业总体机会如何该领域的初创公司容易成功吗今后五年初创公司进入会不会太早或太晚大企业会不会占据大部分市场": "总体机会判断",
    "你将来有可能在该赛道创业吗请评分": "创业意愿",
}


TRACK_LABELS = {
    "人形机器人": "人形机器人",
    "竞技运动如跑鞋传感器智能教练等": "竞技运动科技",
    "户外休闲如露营装配徒步智能手环等": "户外休闲科技",
    "健康科技如可穿戴监测手环按摩仪等": "健康科技",
    "智能家居如智能台灯扫地机器人等": "智能家居",
    "宠物经济如宠物饮水机宠物洗澡烘干机等": "宠物经济",
    "养老如防摔预警智能药盒等": "养老科技",
    "助残如盲文阅读器脑控轮椅等": "助残科技",
    "教育培训如书法培训机器人编程积木等": "教育培训科技",
    "兴趣爱好如智能绘画笔航模监控模块等": "兴趣爱好类项目",
    "医疗检测如智能血糖仪智慧病理检测装备等": "医疗检测科技",
    "医疗干预如近视防控眼镜超声检测机器人等": "医疗干预科技",
    "元宇宙如AR眼镜导游触觉反馈手套等": "元宇宙体验设备",
    "消费电子如随身AI胸针智能戒指等": "消费电子",
    "移动机器人相关如智能电单车无人艇等": "移动机器人",
    "工业机器人相关如装配机器人工业仓储工业物联网等": "工业机器人",
}


def humanize_column_name(value: Any) -> str:
    """把清洗后的问卷字段名转成适合报告展示的中文名。"""
    if value is None:
        return ""

    text = str(value).strip()
    if not text:
        return ""
    if text in BASE_COLUMN_LABELS:
        return BASE_COLUMN_LABELS[text]

    measure = _measure_label(text)
    track = _track_label(text)
    if measure and track:
        return f"{measure}：{track}"

    cleaned = _plain_column_text(text)
    for old, new in QUESTION_PHRASE_LABELS.items():
        cleaned = cleaned.replace(old, new)

    track = _track_label(cleaned)
    if track:
        for label in QUESTION_PHRASE_LABELS.values():
            if label in cleaned:
                return f"{label}：{track}"
        return track

    return _normalize_spaces(cleaned) or text


def clean_choice(value: Any) -> str:
    """去掉 A./B./C. 这类问卷选项编码，保留可读答案。"""
    text = str(value).strip()
    text = re.sub(r"^[A-Za-z]\s*[\.、]\s*", "", text)
    return _normalize_spaces(text)


def _measure_label(text: str) -> str:
    for prefix, label in MEASURE_PREFIX_LABELS:
        if text.startswith(prefix):
            return label
    for phrase, label in QUESTION_PHRASE_LABELS.items():
        if phrase in text:
            return label
    return ""


def _track_label(text: str) -> str:
    raw = _extract_track_text(text)
    if not raw:
        return ""
    if raw in TRACK_LABELS:
        return TRACK_LABELS[raw]
    for old, new in TRACK_LABELS.items():
        if old in raw:
            return new
    return _shorten_track_examples(raw)


def _extract_track_text(text: str) -> str:
    raw = str(text).strip()
    if "._" in raw:
        raw = raw.split("._")[-1]
    raw = raw.replace("_", " ")
    raw = re.sub(r"^col\s*\d+", "", raw, flags=re.IGNORECASE).strip()
    raw = re.sub(r"^\d+\s*[\.\、]?\s*", "", raw).strip()
    raw = re.sub(r"^[A-Za-z]\s*[\.、]\s*", "", raw).strip()
    raw = raw.strip(" ：:.-")
    return raw


def _plain_column_text(text: str) -> str:
    cleaned = text.replace("_", " ")
    cleaned = re.sub(r"^col\s*", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^\d+\s*[\.\、]?\s*", "", cleaned).strip()
    cleaned = re.sub(r"^[A-Za-z]\s*[\.、]\s*", "", cleaned).strip()
    return cleaned.strip(" ：:.-")


def _shorten_track_examples(text: str) -> str:
    if "如" not in text:
        return _normalize_spaces(text)
    base = text.split("如", 1)[0].strip()
    if base in {"养老", "助残"}:
        return f"{base}科技"
    if base in {"兴趣爱好"}:
        return "兴趣爱好类项目"
    if base in {"医疗检测", "医疗干预", "竞技运动", "户外休闲", "教育培训"}:
        return f"{base}科技"
    if base.endswith("相关"):
        return base[:-2]
    return base


def _normalize_spaces(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = re.sub(r"\s+([，。；：、）])", r"\1", text)
    text = re.sub(r"([（])\s+", r"\1", text)
    return text
