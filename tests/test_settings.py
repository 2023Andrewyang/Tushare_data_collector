# -*- coding: utf-8 -*-
"""配置模块测试（单元，不连库）。"""
from config.settings import settings


def test_db_url_format():
    assert settings.db.url.startswith("postgresql+psycopg2://")


def test_points_is_int():
    assert isinstance(settings.tushare.points, int)


def test_table_name_constants():
    assert settings.TBL_DAILY_QUOTE == "daily_quote"
    assert settings.TBL_STK_LIMIT == "stk_limit"
    assert settings.TBL_LIMIT_LIST == "limit_list"
    assert settings.TBL_MARGIN_SUMMARY == "margin_summary"
    assert settings.TBL_TASK_FAILURE_LOG == "task_failure_log"


def test_start_date_default():
    assert len(settings.data.start_date) == 8
