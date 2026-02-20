# -*- coding: utf-8 -*-
"""
任务管理模块
负责同步进度追踪和断点续传
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from config.settings import settings
from core.database import get_db_manager

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 待执行
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    PAUSED = "paused"             # 已暂停


class TaskType(Enum):
    """任务类型枚举"""
    STOCK_LIST = "stock_list"
    TRADE_CALENDAR = "trade_calendar"
    DAILY_QUOTE = "daily_quote"
    ADJ_FACTOR = "adj_factor"
    DAILY_BASIC = "daily_basic"
    STK_LIMIT = "stk_limit"
    SUSPEND = "suspend"
    FINA_INDICATOR = "fina_indicator"
    STOCK_ST = "stock_st"


class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.db = get_db_manager()
        self.collection = settings.COLLECTION_SYNC_PROGRESS
    
    def get_task_progress(self, task_name: str) -> Optional[Dict]:
        """
        获取任务进度
        
        Args:
            task_name: 任务名称
            
        Returns:
            任务进度字典，不存在返回None
        """
        return self.db.find_one(self.collection, {"task_name": task_name})
    
    def create_task(self, task_name: str, task_type: str, 
                    total_items: int = 0, 
                    metadata: Dict = None) -> Dict:
        """
        创建新任务
        
        Args:
            task_name: 任务名称（唯一标识）
            task_type: 任务类型
            total_items: 总项目数
            metadata: 额外元数据
            
        Returns:
            创建的任务记录
        """
        task = {
            "task_name": task_name,
            "task_type": task_type,
            "status": TaskStatus.PENDING.value,
            "total_items": total_items,
            "processed_items": 0,
            "failed_items": 0,
            "last_processed_code": None,
            "last_processed_date": None,
            "start_time": None,
            "end_time": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "metadata": metadata or {}
        }
        
        self.db.upsert_one(
            self.collection,
            {"task_name": task_name},
            task
        )
        
        logger.info(f"任务创建成功: {task_name}")
        return task
    
    def start_task(self, task_name: str):
        """开始任务"""
        self.db.upsert_one(
            self.collection,
            {"task_name": task_name},
            {
                "status": TaskStatus.RUNNING.value,
                "start_time": datetime.now(),
                "updated_at": datetime.now()
            }
        )
        logger.info(f"任务开始: {task_name}")
    
    def update_progress(self, task_name: str, 
                        processed_items: int = None,
                        failed_items: int = None,
                        last_processed_code: str = None,
                        last_processed_date: str = None,
                        increment_processed: int = 0,
                        increment_failed: int = 0):
        """
        更新任务进度
        
        Args:
            task_name: 任务名称
            processed_items: 已处理项目数（绝对值）
            failed_items: 失败项目数（绝对值）
            last_processed_code: 最后处理的股票代码
            last_processed_date: 最后处理的日期
            increment_processed: 处理数增量
            increment_failed: 失败数增量
        """
        update_dict = {"updated_at": datetime.now()}
        
        if processed_items is not None:
            update_dict["processed_items"] = processed_items
        if failed_items is not None:
            update_dict["failed_items"] = failed_items
        if last_processed_code:
            update_dict["last_processed_code"] = last_processed_code
        if last_processed_date:
            update_dict["last_processed_date"] = last_processed_date
        
        # 获取当前进度
        if increment_processed > 0 or increment_failed > 0:
            current = self.get_task_progress(task_name)
            if current:
                if increment_processed > 0:
                    update_dict["processed_items"] = current.get("processed_items", 0) + increment_processed
                if increment_failed > 0:
                    update_dict["failed_items"] = current.get("failed_items", 0) + increment_failed
        
        self.db.upsert_one(
            self.collection,
            {"task_name": task_name},
            update_dict
        )
    
    def complete_task(self, task_name: str, status: TaskStatus = TaskStatus.COMPLETED):
        """完成任务"""
        self.db.upsert_one(
            self.collection,
            {"task_name": task_name},
            {
                "status": status.value,
                "end_time": datetime.now(),
                "updated_at": datetime.now()
            }
        )
        logger.info(f"任务完成: {task_name}, 状态: {status.value}")
    
    def pause_task(self, task_name: str):
        """暂停任务"""
        self.db.upsert_one(
            self.collection,
            {"task_name": task_name},
            {
                "status": TaskStatus.PAUSED.value,
                "updated_at": datetime.now()
            }
        )
        logger.info(f"任务暂停: {task_name}")
    
    def reset_task(self, task_name: str):
        """重置任务"""
        self.db.upsert_one(
            self.collection,
            {"task_name": task_name},
            {
                "status": TaskStatus.PENDING.value,
                "processed_items": 0,
                "failed_items": 0,
                "last_processed_code": None,
                "last_processed_date": None,
                "start_time": None,
                "end_time": None,
                "updated_at": datetime.now()
            }
        )
        logger.info(f"任务重置: {task_name}")
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        return self.db.find_many(self.collection)
    
    def get_running_tasks(self) -> List[Dict]:
        """获取正在运行的任务"""
        return self.db.find_many(
            self.collection,
            {"status": TaskStatus.RUNNING.value}
        )
    
    def get_resume_point(self, task_name: str) -> Dict:
        """
        获取断点续传的起始点
        
        Returns:
            包含 last_processed_code 和 last_processed_date 的字典
        """
        task = self.get_task_progress(task_name)
        if task and task.get("status") in [TaskStatus.RUNNING.value, TaskStatus.PAUSED.value]:
            return {
                "last_code": task.get("last_processed_code"),
                "last_date": task.get("last_processed_date"),
                "processed_items": task.get("processed_items", 0)
            }
        return {"last_code": None, "last_date": None, "processed_items": 0}
    
    def should_resume(self, task_name: str) -> bool:
        """判断任务是否需要断点续传"""
        task = self.get_task_progress(task_name)
        if not task:
            return False
        return task.get("status") in [TaskStatus.RUNNING.value, TaskStatus.PAUSED.value]
    
    def is_completed(self, task_name: str) -> bool:
        """判断任务是否已完成"""
        task = self.get_task_progress(task_name)
        if not task:
            return False
        return task.get("status") == TaskStatus.COMPLETED.value
    
    def delete_task(self, task_name: str):
        """删除任务记录"""
        self.db.delete_many(self.collection, {"task_name": task_name})
        logger.info(f"任务已删除: {task_name}")
    
    def print_task_status(self, task_name: str = None):
        """打印任务状态"""
        if task_name:
            tasks = [self.get_task_progress(task_name)]
        else:
            tasks = self.get_all_tasks()
        
        print("\n" + "=" * 80)
        print("任务状态概览")
        print("=" * 80)
        
        for task in tasks:
            if not task:
                continue
            
            status = task.get("status", "unknown")
            processed = task.get("processed_items", 0)
            total = task.get("total_items", 0)
            failed = task.get("failed_items", 0)
            progress = (processed / total * 100) if total > 0 else 0
            
            print(f"\n任务: {task.get('task_name')}")
            print(f"  类型: {task.get('task_type')}")
            print(f"  状态: {status}")
            print(f"  进度: {processed}/{total} ({progress:.1f}%)")
            print(f"  失败: {failed}")
            print(f"  最后处理: {task.get('last_processed_code')} @ {task.get('last_processed_date')}")
            print(f"  更新时间: {task.get('updated_at')}")
        
        print("\n" + "=" * 80)


def get_task_manager() -> TaskManager:
    """获取任务管理器实例"""
    return TaskManager()

