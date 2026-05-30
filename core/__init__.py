# -*- coding: utf-8 -*-
"""核心模块。"""
from core.database import PostgresManager, get_db_manager
from core.tushare_client import TushareClient, get_tushare_client
from core.failure_handler import FailureHandler, get_failure_handler

__all__ = [
    "PostgresManager", "get_db_manager",
    "TushareClient", "get_tushare_client",
    "FailureHandler", "get_failure_handler",
]
