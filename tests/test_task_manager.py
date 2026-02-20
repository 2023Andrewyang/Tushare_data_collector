# -*- coding: utf-8 -*-
"""
任务管理器测试
"""
import pytest
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.task_manager import TaskStatus


class TestTaskManager:
    """任务管理器测试"""
    
    @pytest.fixture
    def test_task_name(self):
        """测试任务名称"""
        return f"test_task_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    def test_create_task(self, task_manager, test_task_name):
        """测试创建任务"""
        task = task_manager.create_task(
            task_name=test_task_name,
            task_type="test",
            total_items=100,
            metadata={"test_key": "test_value"}
        )
        
        assert task is not None
        assert task["task_name"] == test_task_name
        assert task["status"] == TaskStatus.PENDING.value
        assert task["total_items"] == 100
        
        # 清理
        task_manager.delete_task(test_task_name)
    
    def test_start_task(self, task_manager, test_task_name):
        """测试开始任务"""
        task_manager.create_task(test_task_name, "test", 100)
        task_manager.start_task(test_task_name)
        
        task = task_manager.get_task_progress(test_task_name)
        assert task["status"] == TaskStatus.RUNNING.value
        assert task["start_time"] is not None
        
        # 清理
        task_manager.delete_task(test_task_name)
    
    def test_update_progress(self, task_manager, test_task_name):
        """测试更新进度"""
        task_manager.create_task(test_task_name, "test", 100)
        task_manager.start_task(test_task_name)
        
        # 使用增量更新
        task_manager.update_progress(
            test_task_name,
            increment_processed=10,
            last_processed_code="TEST001.SZ"
        )
        
        task = task_manager.get_task_progress(test_task_name)
        assert task["processed_items"] == 10
        assert task["last_processed_code"] == "TEST001.SZ"
        
        # 再次增量更新
        task_manager.update_progress(
            test_task_name,
            increment_processed=5,
            increment_failed=1
        )
        
        task = task_manager.get_task_progress(test_task_name)
        assert task["processed_items"] == 15
        assert task["failed_items"] == 1
        
        # 清理
        task_manager.delete_task(test_task_name)
    
    def test_complete_task(self, task_manager, test_task_name):
        """测试完成任务"""
        task_manager.create_task(test_task_name, "test", 100)
        task_manager.start_task(test_task_name)
        task_manager.complete_task(test_task_name)
        
        task = task_manager.get_task_progress(test_task_name)
        assert task["status"] == TaskStatus.COMPLETED.value
        assert task["end_time"] is not None
        
        # 清理
        task_manager.delete_task(test_task_name)
    
    def test_pause_task(self, task_manager, test_task_name):
        """测试暂停任务"""
        task_manager.create_task(test_task_name, "test", 100)
        task_manager.start_task(test_task_name)
        task_manager.pause_task(test_task_name)
        
        task = task_manager.get_task_progress(test_task_name)
        assert task["status"] == TaskStatus.PAUSED.value
        
        # 清理
        task_manager.delete_task(test_task_name)
    
    def test_resume_point(self, task_manager, test_task_name):
        """测试断点续传"""
        task_manager.create_task(test_task_name, "test", 100)
        task_manager.start_task(test_task_name)
        task_manager.update_progress(
            test_task_name,
            processed_items=50,
            last_processed_code="TEST050.SZ",
            last_processed_date="20240115"
        )
        task_manager.pause_task(test_task_name)
        
        # 获取断点
        resume = task_manager.get_resume_point(test_task_name)
        assert resume["last_code"] == "TEST050.SZ"
        assert resume["last_date"] == "20240115"
        assert resume["processed_items"] == 50
        
        # 清理
        task_manager.delete_task(test_task_name)
    
    def test_should_resume(self, task_manager, test_task_name):
        """测试是否需要断点续传"""
        task_manager.create_task(test_task_name, "test", 100)
        
        # 新建任务不需要续传
        assert not task_manager.should_resume(test_task_name)
        
        # 运行中的任务需要续传
        task_manager.start_task(test_task_name)
        assert task_manager.should_resume(test_task_name)
        
        # 暂停的任务需要续传
        task_manager.pause_task(test_task_name)
        assert task_manager.should_resume(test_task_name)
        
        # 完成的任务不需要续传
        task_manager.complete_task(test_task_name)
        assert not task_manager.should_resume(test_task_name)
        
        # 清理
        task_manager.delete_task(test_task_name)
    
    def test_reset_task(self, task_manager, test_task_name):
        """测试重置任务"""
        task_manager.create_task(test_task_name, "test", 100)
        task_manager.start_task(test_task_name)
        task_manager.update_progress(test_task_name, processed_items=50)
        task_manager.reset_task(test_task_name)
        
        task = task_manager.get_task_progress(test_task_name)
        assert task["status"] == TaskStatus.PENDING.value
        assert task["processed_items"] == 0
        
        # 清理
        task_manager.delete_task(test_task_name)

