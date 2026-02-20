# -*- coding: utf-8 -*-
"""
失败任务处理模块
记录、分析和重试失败的任务
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import traceback

from config.settings import settings
from core.database import get_db_manager

logger = logging.getLogger(__name__)


class FailureReason(Enum):
    """失败原因枚举"""
    NETWORK_ERROR = "network_error"           # 网络错误
    RATE_LIMIT = "rate_limit"                 # 频率限制
    PERMISSION_DENIED = "permission_denied"   # 权限不足
    DATA_NOT_FOUND = "data_not_found"         # 数据不存在
    INVALID_PARAMS = "invalid_params"         # 参数错误
    API_ERROR = "api_error"                   # API错误
    UNKNOWN = "unknown"                       # 未知错误


class FailureStatus(Enum):
    """失败任务状态"""
    PENDING = "pending"       # 待重试
    RETRYING = "retrying"     # 重试中
    RESOLVED = "resolved"     # 已解决
    IGNORED = "ignored"       # 已忽略


class FailureHandler:
    """失败任务处理器"""
    
    def __init__(self):
        self.db = get_db_manager()
        self.collection = settings.COLLECTION_TASK_FAILURES
    
    def record_failure(self, task_name: str, ts_code: str = None,
                       trade_date: str = None, error: Exception = None,
                       error_message: str = None, 
                       context: Dict = None) -> str:
        """
        记录失败任务
        
        Args:
            task_name: 任务名称
            ts_code: 股票代码
            trade_date: 交易日期
            error: 异常对象
            error_message: 错误消息
            context: 上下文信息
            
        Returns:
            失败记录ID
        """
        # 分析失败原因
        reason = self._analyze_failure_reason(error, error_message)
        
        failure_record = {
            "task_name": task_name,
            "ts_code": ts_code,
            "trade_date": trade_date,
            "status": FailureStatus.PENDING.value,
            "reason": reason.value,
            "error_message": str(error) if error else error_message,
            "error_type": type(error).__name__ if error else None,
            "traceback": traceback.format_exc() if error else None,
            "retry_count": 0,
            "max_retries": 3,
            "context": context or {},
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "resolved_at": None
        }
        
        # 检查是否已存在相同的失败记录
        existing = self.db.find_one(
            self.collection,
            {
                "task_name": task_name,
                "ts_code": ts_code,
                "trade_date": trade_date,
                "status": {"$in": [FailureStatus.PENDING.value, FailureStatus.RETRYING.value]}
            }
        )
        
        if existing:
            # 更新现有记录
            self.db.upsert_one(
                self.collection,
                {"_id": existing["_id"]},
                {
                    "retry_count": existing.get("retry_count", 0) + 1,
                    "error_message": failure_record["error_message"],
                    "updated_at": datetime.now()
                }
            )
            logger.warning(f"更新失败记录: {task_name} - {ts_code} @ {trade_date}")
            return str(existing["_id"])
        else:
            # 插入新记录
            result = self.db.get_collection(self.collection).insert_one(failure_record)
            logger.warning(f"记录失败任务: {task_name} - {ts_code} @ {trade_date}, 原因: {reason.value}")
            return str(result.inserted_id)
    
    def _analyze_failure_reason(self, error: Exception, 
                                 error_message: str) -> FailureReason:
        """分析失败原因"""
        msg = str(error).lower() if error else (error_message or "").lower()
        
        if "timeout" in msg or "connection" in msg or "network" in msg:
            return FailureReason.NETWORK_ERROR
        elif "rate" in msg or "limit" in msg or "too many" in msg or "频率" in msg:
            return FailureReason.RATE_LIMIT
        elif "permission" in msg or "权限" in msg or "积分" in msg:
            return FailureReason.PERMISSION_DENIED
        elif "not found" in msg or "no data" in msg or "无数据" in msg or "empty" in msg:
            return FailureReason.DATA_NOT_FOUND
        elif "invalid" in msg or "parameter" in msg or "参数" in msg:
            return FailureReason.INVALID_PARAMS
        elif "api" in msg or "tushare" in msg:
            return FailureReason.API_ERROR
        else:
            return FailureReason.UNKNOWN
    
    def get_pending_failures(self, task_name: str = None, 
                             limit: int = 100) -> List[Dict]:
        """
        获取待重试的失败任务
        
        Args:
            task_name: 任务名称（可选，筛选特定任务）
            limit: 返回数量限制
            
        Returns:
            失败任务列表
        """
        filter_dict = {"status": FailureStatus.PENDING.value}
        if task_name:
            filter_dict["task_name"] = task_name
        
        return self.db.find_many(
            self.collection,
            filter_dict,
            limit=limit
        )
    
    def get_failures_by_reason(self, reason: FailureReason) -> List[Dict]:
        """按原因获取失败任务"""
        return self.db.find_many(
            self.collection,
            {"reason": reason.value, "status": FailureStatus.PENDING.value}
        )
    
    def mark_as_resolved(self, failure_id: str):
        """标记为已解决"""
        from bson import ObjectId
        self.db.upsert_one(
            self.collection,
            {"_id": ObjectId(failure_id)},
            {
                "status": FailureStatus.RESOLVED.value,
                "resolved_at": datetime.now(),
                "updated_at": datetime.now()
            }
        )
        logger.info(f"失败任务已解决: {failure_id}")
    
    def mark_as_ignored(self, failure_id: str, reason: str = None):
        """标记为已忽略"""
        from bson import ObjectId
        self.db.upsert_one(
            self.collection,
            {"_id": ObjectId(failure_id)},
            {
                "status": FailureStatus.IGNORED.value,
                "ignore_reason": reason,
                "updated_at": datetime.now()
            }
        )
        logger.info(f"失败任务已忽略: {failure_id}")
    
    def mark_batch_resolved(self, task_name: str, ts_code: str = None,
                            trade_date: str = None):
        """批量标记为已解决"""
        filter_dict = {
            "task_name": task_name,
            "status": FailureStatus.PENDING.value
        }
        if ts_code:
            filter_dict["ts_code"] = ts_code
        if trade_date:
            filter_dict["trade_date"] = trade_date
        
        collection = self.db.get_collection(self.collection)
        result = collection.update_many(
            filter_dict,
            {
                "$set": {
                    "status": FailureStatus.RESOLVED.value,
                    "resolved_at": datetime.now(),
                    "updated_at": datetime.now()
                }
            }
        )
        logger.info(f"批量标记已解决: {result.modified_count} 条记录")
    
    def get_failure_summary(self) -> Dict:
        """
        获取失败任务汇总统计
        
        Returns:
            包含各类统计信息的字典
        """
        collection = self.db.get_collection(self.collection)
        
        # 按任务类型统计
        pipeline_by_task = [
            {"$match": {"status": FailureStatus.PENDING.value}},
            {"$group": {
                "_id": "$task_name",
                "count": {"$sum": 1}
            }}
        ]
        by_task = {item["_id"]: item["count"] 
                   for item in collection.aggregate(pipeline_by_task)}
        
        # 按失败原因统计
        pipeline_by_reason = [
            {"$match": {"status": FailureStatus.PENDING.value}},
            {"$group": {
                "_id": "$reason",
                "count": {"$sum": 1}
            }}
        ]
        by_reason = {item["_id"]: item["count"] 
                     for item in collection.aggregate(pipeline_by_reason)}
        
        # 总计
        total_pending = self.db.count(
            self.collection,
            {"status": FailureStatus.PENDING.value}
        )
        total_resolved = self.db.count(
            self.collection,
            {"status": FailureStatus.RESOLVED.value}
        )
        total_ignored = self.db.count(
            self.collection,
            {"status": FailureStatus.IGNORED.value}
        )
        
        return {
            "total_pending": total_pending,
            "total_resolved": total_resolved,
            "total_ignored": total_ignored,
            "by_task": by_task,
            "by_reason": by_reason
        }
    
    def print_failure_report(self, detailed: bool = False):
        """打印失败任务报告"""
        summary = self.get_failure_summary()
        
        print("\n" + "=" * 80)
        print("失败任务报告")
        print("=" * 80)
        
        print(f"\n总计:")
        print(f"  待处理: {summary['total_pending']}")
        print(f"  已解决: {summary['total_resolved']}")
        print(f"  已忽略: {summary['total_ignored']}")
        
        if summary['by_task']:
            print(f"\n按任务类型:")
            for task, count in summary['by_task'].items():
                print(f"  {task}: {count}")
        
        if summary['by_reason']:
            print(f"\n按失败原因:")
            for reason, count in summary['by_reason'].items():
                print(f"  {reason}: {count}")
        
        if detailed and summary['total_pending'] > 0:
            print(f"\n详细失败记录 (最多显示20条):")
            print("-" * 80)
            failures = self.get_pending_failures(limit=20)
            for f in failures:
                print(f"  [{f.get('task_name')}] {f.get('ts_code')} @ {f.get('trade_date')}")
                print(f"    原因: {f.get('reason')}")
                print(f"    错误: {f.get('error_message', '')[:100]}")
                print(f"    重试次数: {f.get('retry_count', 0)}")
                print()
        
        print("=" * 80)
    
    def clear_resolved(self, days_ago: int = 30):
        """清理已解决的旧记录"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days_ago)
        
        deleted = self.db.delete_many(
            self.collection,
            {
                "status": {"$in": [FailureStatus.RESOLVED.value, FailureStatus.IGNORED.value]},
                "updated_at": {"$lt": cutoff_date}
            }
        )
        logger.info(f"清理了 {deleted} 条旧的失败记录")
        return deleted
    
    def get_retry_candidates(self, task_name: str = None) -> List[Dict]:
        """
        获取可重试的任务（未超过最大重试次数）
        """
        filter_dict = {
            "status": FailureStatus.PENDING.value,
            "$expr": {"$lt": ["$retry_count", "$max_retries"]}
        }
        if task_name:
            filter_dict["task_name"] = task_name
        
        return self.db.find_many(self.collection, filter_dict)


def get_failure_handler() -> FailureHandler:
    """获取失败处理器实例"""
    return FailureHandler()

