# -*- coding: utf-8 -*-
"""失败处理模块测试。

_classify 是纯逻辑，可单元测试；记录/查询需要 PG。
"""
import pytest

from core.failure_handler import FailureHandler


def _make_handler():
    return object.__new__(FailureHandler)


def test_classify_token():
    fh = _make_handler()
    assert fh._classify(Exception("invalid token")) == "token_invalid"


def test_classify_network():
    fh = _make_handler()
    assert fh._classify(Exception("connection timeout")) == "network_timeout"


def test_classify_rate_limit():
    fh = _make_handler()
    assert fh._classify(Exception("too many requests")) == "rate_limit"


def test_classify_unknown():
    fh = _make_handler()
    assert fh._classify(Exception("something weird")) == "unknown"


@pytest.mark.db
def test_record_dedup_and_resolve(db):
    from core.failure_handler import get_failure_handler
    fh = get_failure_handler()
    # 清理可能的遗留
    db.execute("DELETE FROM task_failure_log WHERE collector='test_dq'")

    fid = fh.record_failure("test_dq", trade_date="20240101",
                            error=Exception("timeout"))
    assert fid > 0
    fid2 = fh.record_failure("test_dq", trade_date="20240101",
                             error=Exception("timeout again"))
    assert fid2 == fid                        # 去重累加
    assert len(fh.get_pending("test_dq")) == 1
    fh.mark_resolved(fid)
    assert len(fh.get_pending("test_dq")) == 0
    db.execute("DELETE FROM task_failure_log WHERE collector='test_dq'")
