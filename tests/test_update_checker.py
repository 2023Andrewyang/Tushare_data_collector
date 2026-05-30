# -*- coding: utf-8 -*-
"""低频更新检测测试。

_to_datetime 与财报季月份判断是纯逻辑，可单元测试；
依赖 db 的方法用 @pytest.mark.db。
"""
from datetime import datetime

import pytest

from scheduler.update_checker import UpdateChecker


def _make_checker():
    return object.__new__(UpdateChecker)


def test_to_datetime_handles_none():
    assert UpdateChecker._to_datetime(None) is None


def test_to_datetime_passthrough():
    now = datetime.now()
    assert UpdateChecker._to_datetime(now) is now


def test_to_datetime_from_iso_string():
    d = UpdateChecker._to_datetime("2026-05-30T10:00:00")
    assert isinstance(d, datetime)
    assert d.year == 2026


@pytest.mark.db
def test_empty_db_returns_true(db):
    ck = UpdateChecker()
    assert isinstance(ck.should_update_trade_calendar("20260530"), bool)
    assert isinstance(ck.should_update_dc_member("20260530"), bool)
    # 4 月 -> 财报季 -> True
    assert ck.should_update_financials("20260430") is True
