# -*- coding: utf-8 -*-
"""
失败处理器测试
"""
import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.failure_handler import FailureReason, FailureStatus


class TestFailureHandler:
    """失败处理器测试"""
    
    @pytest.fixture
    def test_task_name(self):
        """测试任务名称"""
        return f"test_failure_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def test_record_failure(self, failure_handler, test_task_name):
        """测试记录失败"""
        failure_id = failure_handler.record_failure(
            task_name=test_task_name,
            ts_code="TEST001.SZ",
            trade_date="20240101",
            error_message="Test error message"
        )
        
        assert failure_id is not None
        
        # 清理
        failure_handler.mark_as_ignored(failure_id)
    
    def test_record_failure_with_exception(self, failure_handler, test_task_name):
        """测试记录异常"""
        try:
            raise ConnectionError("Network timeout")
        except Exception as e:
            failure_id = failure_handler.record_failure(
                task_name=test_task_name,
                ts_code="TEST002.SZ",
                error=e
            )
        
        assert failure_id is not None
        
        # 验证原因分析
        from config.settings import settings
        from core.database import get_db_manager
        from bson import ObjectId
        
        db = get_db_manager()
        failure = db.find_one(
            settings.COLLECTION_TASK_FAILURES,
            {"_id": ObjectId(failure_id)}
        )
        
        assert failure["reason"] == FailureReason.NETWORK_ERROR.value
        
        # 清理
        failure_handler.mark_as_ignored(failure_id)
    
    def test_analyze_failure_reason(self, failure_handler):
        """测试失败原因分析"""
        # 测试各种错误消息
        test_cases = [
            ("Connection timeout", FailureReason.NETWORK_ERROR),
            ("Rate limit exceeded", FailureReason.RATE_LIMIT),
            ("Permission denied", FailureReason.PERMISSION_DENIED),
            ("No data found", FailureReason.DATA_NOT_FOUND),
            ("Invalid parameter", FailureReason.INVALID_PARAMS),
            ("Tushare API error", FailureReason.API_ERROR),
            ("Something else", FailureReason.UNKNOWN),
        ]
        
        for msg, expected_reason in test_cases:
            reason = failure_handler._analyze_failure_reason(None, msg)
            assert reason == expected_reason, f"Failed for message: {msg}"
    
    def test_get_pending_failures(self, failure_handler, test_task_name):
        """测试获取待处理失败"""
        # 创建测试失败记录
        failure_ids = []
        for i in range(3):
            fid = failure_handler.record_failure(
                task_name=test_task_name,
                ts_code=f"TEST{i:03d}.SZ",
                trade_date="20240101",
                error_message=f"Test error {i}"
            )
            failure_ids.append(fid)
        
        # 获取待处理失败
        failures = failure_handler.get_pending_failures(test_task_name)
        assert len(failures) >= 3
        
        # 清理
        for fid in failure_ids:
            failure_handler.mark_as_ignored(fid)
    
    def test_mark_as_resolved(self, failure_handler, test_task_name):
        """测试标记为已解决"""
        failure_id = failure_handler.record_failure(
            task_name=test_task_name,
            ts_code="TEST001.SZ",
            error_message="Test error"
        )
        
        failure_handler.mark_as_resolved(failure_id)
        
        # 验证状态
        from config.settings import settings
        from core.database import get_db_manager
        from bson import ObjectId
        
        db = get_db_manager()
        failure = db.find_one(
            settings.COLLECTION_TASK_FAILURES,
            {"_id": ObjectId(failure_id)}
        )
        
        assert failure["status"] == FailureStatus.RESOLVED.value
        assert failure["resolved_at"] is not None
    
    def test_get_failure_summary(self, failure_handler, test_task_name):
        """测试获取失败汇总"""
        # 创建一些测试数据
        failure_ids = []
        for i in range(2):
            fid = failure_handler.record_failure(
                task_name=test_task_name,
                ts_code=f"TEST{i:03d}.SZ",
                error_message="Network error" if i == 0 else "Unknown error"
            )
            failure_ids.append(fid)
        
        summary = failure_handler.get_failure_summary()
        
        assert "total_pending" in summary
        assert "by_task" in summary
        assert "by_reason" in summary
        
        # 清理
        for fid in failure_ids:
            failure_handler.mark_as_ignored(fid)
    
    def test_duplicate_failure_handling(self, failure_handler, test_task_name):
        """测试重复失败处理"""
        # 第一次记录
        fid1 = failure_handler.record_failure(
            task_name=test_task_name,
            ts_code="TEST001.SZ",
            trade_date="20240101",
            error_message="First error"
        )
        
        # 第二次记录同一任务
        fid2 = failure_handler.record_failure(
            task_name=test_task_name,
            ts_code="TEST001.SZ",
            trade_date="20240101",
            error_message="Second error"
        )
        
        # 应该返回相同的ID（更新现有记录）
        assert fid1 == fid2
        
        # 验证重试次数增加
        from config.settings import settings
        from core.database import get_db_manager
        from bson import ObjectId
        
        db = get_db_manager()
        failure = db.find_one(
            settings.COLLECTION_TASK_FAILURES,
            {"_id": ObjectId(fid1)}
        )
        
        assert failure["retry_count"] >= 1
        
        # 清理
        failure_handler.mark_as_ignored(fid1)

