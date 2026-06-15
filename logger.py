# -*- coding: utf-8 -*-
"""
@File    : logger.py
@Author  : Huginn
@Date    : 2026/6/16
@Description: 统一日志模块 — 一次性 basicConfig，幂等 get_logger()
@Software: PyCharm
"""

"""
统一日志模块
首次调用 get_logger() 时自动配置 basicConfig，后续调用幂等。
用法：
    from logger import get_logger
    logger = get_logger(__name__)
    logger.info("message")
"""
import logging
import sys

_configured: bool = False


def _setup_logging() -> None:
    """配置根日志器（仅执行一次）。"""
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器（首次调用自动初始化日志系统）。"""
    _setup_logging()
    return logging.getLogger(name)
