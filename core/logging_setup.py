# -*- coding: utf-8 -*-
"""日志初始化：控制台 + 按日期滚动文件。"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler

from config.settings import settings

_CONFIGURED = False


def setup_logging():
    global _CONFIGURED
    if _CONFIGURED:
        return
    os.makedirs(settings.log.dir, exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        os.path.join(settings.log.dir, "data_hub.log"),
        when="midnight", backupCount=settings.log.backup_count, encoding="utf-8")
    logging.basicConfig(
        level=getattr(logging, settings.log.level, logging.INFO),
        format=settings.log.fmt,
        handlers=[logging.StreamHandler(), file_handler])
    _CONFIGURED = True
