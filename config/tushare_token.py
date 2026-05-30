# -*- coding: utf-8 -*-
"""Tushare Token（向后兼容）：统一从 settings 读取。

新代码请直接使用 `settings.tushare.token` / `settings.tushare.points`。
保留本模块仅为兼容旧的 `from config.tushare_token import TUSHARE_TOKEN` 引用。
"""
from config.settings import settings

TUSHARE_TOKEN = settings.tushare.token
TUSHARE_POINTS = settings.tushare.points
