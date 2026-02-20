# -*- coding: utf-8 -*-
"""
失败任务重试脚本
用于查看和重试失败的采集任务
"""
import sys
import os
import logging
import argparse
from datetime import datetime
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.database import get_db_manager
from core.failure_handler import get_failure_handler, FailureStatus, FailureReason
from collectors.daily_quote import DailyQuoteCollector
from collectors.adj_factor import AdjFactorCollector
from collectors.daily_basic import DailyBasicCollector
from collectors.limit_price import LimitPriceCollector
from collectors.suspend import SuspendCollector
from collectors.fina_indicator import FinaIndicatorCollector
from collectors.stock_st import StockSTCollector

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


# 采集器映射
COLLECTOR_MAP = {
    'daily_quote': DailyQuoteCollector,
    'adj_factor': AdjFactorCollector,
    'daily_basic': DailyBasicCollector,
    'stk_limit': LimitPriceCollector,
    'suspend': SuspendCollector,
    'fina_indicator': FinaIndicatorCollector,
    'stock_st': StockSTCollector,
}


def list_failures(task_name: str = None, reason: str = None, 
                  limit: int = 50) -> List[Dict]:
    """
    列出失败任务
    
    Args:
        task_name: 任务名称筛选
        reason: 失败原因筛选
        limit: 返回数量限制
        
    Returns:
        失败任务列表
    """
    handler = get_failure_handler()
    
    if reason:
        try:
            reason_enum = FailureReason(reason)
            failures = handler.get_failures_by_reason(reason_enum)[:limit]
        except ValueError:
            print(f"无效的失败原因: {reason}")
            print(f"可选值: {[r.value for r in FailureReason]}")
            return []
    else:
        failures = handler.get_pending_failures(task_name, limit)
    
    return failures


def print_failures(failures: List[Dict], verbose: bool = False):
    """打印失败任务列表"""
    if not failures:
        print("没有待处理的失败任务")
        return
    
    print("\n" + "=" * 80)
    print(f"失败任务列表 (共 {len(failures)} 条)")
    print("=" * 80)
    
    for i, f in enumerate(failures, 1):
        print(f"\n[{i}] ID: {f.get('_id')}")
        print(f"    任务: {f.get('task_name')}")
        print(f"    股票: {f.get('ts_code', '-')}")
        print(f"    日期: {f.get('trade_date', '-')}")
        print(f"    原因: {f.get('reason')}")
        print(f"    重试次数: {f.get('retry_count', 0)}/{f.get('max_retries', 3)}")
        print(f"    创建时间: {f.get('created_at')}")
        
        if verbose:
            print(f"    错误类型: {f.get('error_type', '-')}")
            print(f"    错误信息: {f.get('error_message', '-')[:200]}")
            if f.get('traceback'):
                print(f"    堆栈跟踪:")
                for line in f.get('traceback', '').split('\n')[:5]:
                    print(f"        {line}")
    
    print("\n" + "=" * 80)


def retry_single(failure_id: str) -> bool:
    """
    重试单个失败任务
    
    Args:
        failure_id: 失败记录ID
        
    Returns:
        是否成功
    """
    from bson import ObjectId
    
    handler = get_failure_handler()
    db = get_db_manager()
    
    # 获取失败记录
    failure = db.find_one(
        settings.COLLECTION_TASK_FAILURES,
        {"_id": ObjectId(failure_id)}
    )
    
    if not failure:
        print(f"未找到失败记录: {failure_id}")
        return False
    
    task_name = failure.get('task_name')
    ts_code = failure.get('ts_code')
    trade_date = failure.get('trade_date')
    
    print(f"重试任务: {task_name} - {ts_code} @ {trade_date}")
    
    # 获取对应的采集器
    collector_class = COLLECTOR_MAP.get(task_name)
    if not collector_class:
        print(f"未知的任务类型: {task_name}")
        return False
    
    try:
        collector = collector_class()
        
        # 根据任务类型执行不同的重试逻辑
        if ts_code and trade_date:
            # 按股票+日期重试
            result = collector.collect_by_stock(ts_code, trade_date, trade_date)
        elif trade_date:
            # 按日期重试
            result = collector.collect_incremental(trade_date)
        elif ts_code:
            # 按股票重试
            result = collector.collect_by_stock(ts_code)
        else:
            print("缺少必要的参数")
            return False
        
        if result.get('success', 0) > 0 and result.get('failed', 0) == 0:
            # 标记为已解决
            handler.mark_as_resolved(failure_id)
            print(f"✓ 重试成功")
            return True
        else:
            print(f"✗ 重试失败: {result}")
            return False
            
    except Exception as e:
        logger.error(f"重试异常: {e}")
        return False


def retry_by_task(task_name: str, limit: int = 100) -> Dict:
    """
    重试指定任务的所有失败记录
    
    Args:
        task_name: 任务名称
        limit: 最大重试数量
        
    Returns:
        重试结果统计
    """
    handler = get_failure_handler()
    failures = handler.get_pending_failures(task_name, limit)
    
    if not failures:
        print(f"没有 {task_name} 的待处理失败任务")
        return {"success": 0, "failed": 0}
    
    print(f"开始重试 {task_name} 的 {len(failures)} 个失败任务")
    
    success_count = 0
    failed_count = 0
    
    for f in failures:
        failure_id = str(f['_id'])
        if retry_single(failure_id):
            success_count += 1
        else:
            failed_count += 1
    
    print(f"\n重试完成: 成功 {success_count}, 失败 {failed_count}")
    return {"success": success_count, "failed": failed_count}


def retry_by_date(trade_date: str) -> Dict:
    """
    重试指定日期的所有失败记录
    
    Args:
        trade_date: 交易日期
        
    Returns:
        重试结果统计
    """
    handler = get_failure_handler()
    db = get_db_manager()
    
    failures = db.find_many(
        settings.COLLECTION_TASK_FAILURES,
        {
            "trade_date": trade_date,
            "status": FailureStatus.PENDING.value
        }
    )
    
    if not failures:
        print(f"没有 {trade_date} 的待处理失败任务")
        return {"success": 0, "failed": 0}
    
    print(f"开始重试 {trade_date} 的 {len(failures)} 个失败任务")
    
    success_count = 0
    failed_count = 0
    
    for f in failures:
        failure_id = str(f['_id'])
        if retry_single(failure_id):
            success_count += 1
        else:
            failed_count += 1
    
    print(f"\n重试完成: 成功 {success_count}, 失败 {failed_count}")
    return {"success": success_count, "failed": failed_count}


def retry_all(limit: int = 500) -> Dict:
    """
    重试所有失败任务
    
    Args:
        limit: 最大重试数量
        
    Returns:
        重试结果统计
    """
    handler = get_failure_handler()
    failures = handler.get_retry_candidates()[:limit]
    
    if not failures:
        print("没有可重试的失败任务")
        return {"success": 0, "failed": 0}
    
    print(f"开始重试 {len(failures)} 个失败任务")
    
    success_count = 0
    failed_count = 0
    
    for f in failures:
        failure_id = str(f['_id'])
        if retry_single(failure_id):
            success_count += 1
        else:
            failed_count += 1
    
    print(f"\n重试完成: 成功 {success_count}, 失败 {failed_count}")
    return {"success": success_count, "failed": failed_count}


def ignore_failures(task_name: str = None, reason: str = None,
                    older_than_days: int = None):
    """
    忽略指定条件的失败任务
    
    Args:
        task_name: 任务名称
        reason: 失败原因
        older_than_days: 早于多少天的记录
    """
    db = get_db_manager()
    handler = get_failure_handler()
    
    filter_dict = {"status": FailureStatus.PENDING.value}
    
    if task_name:
        filter_dict["task_name"] = task_name
    if reason:
        filter_dict["reason"] = reason
    if older_than_days:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=older_than_days)
        filter_dict["created_at"] = {"$lt": cutoff}
    
    collection = db.get_collection(settings.COLLECTION_TASK_FAILURES)
    result = collection.update_many(
        filter_dict,
        {
            "$set": {
                "status": FailureStatus.IGNORED.value,
                "updated_at": datetime.now()
            }
        }
    )
    
    print(f"已忽略 {result.modified_count} 条失败记录")


def clear_old_records(days: int = 30):
    """清理旧的已解决记录"""
    handler = get_failure_handler()
    deleted = handler.clear_resolved(days)
    print(f"已清理 {deleted} 条旧记录")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='失败任务管理')
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # list 命令
    list_parser = subparsers.add_parser('list', help='列出失败任务')
    list_parser.add_argument('--task', '-t', type=str, help='按任务名称筛选')
    list_parser.add_argument('--reason', '-r', type=str, help='按失败原因筛选')
    list_parser.add_argument('--limit', '-l', type=int, default=50, help='返回数量')
    list_parser.add_argument('--verbose', '-v', action='store_true', help='显示详细信息')
    
    # summary 命令
    subparsers.add_parser('summary', help='显示失败任务汇总')
    
    # retry 命令
    retry_parser = subparsers.add_parser('retry', help='重试失败任务')
    retry_parser.add_argument('--id', type=str, help='重试指定ID的任务')
    retry_parser.add_argument('--task', '-t', type=str, help='重试指定任务类型')
    retry_parser.add_argument('--date', '-d', type=str, help='重试指定日期')
    retry_parser.add_argument('--all', '-a', action='store_true', help='重试所有')
    retry_parser.add_argument('--limit', '-l', type=int, default=100, help='最大重试数量')
    
    # ignore 命令
    ignore_parser = subparsers.add_parser('ignore', help='忽略失败任务')
    ignore_parser.add_argument('--task', '-t', type=str, help='按任务名称')
    ignore_parser.add_argument('--reason', '-r', type=str, help='按失败原因')
    ignore_parser.add_argument('--older-than', type=int, help='早于多少天')
    
    # clear 命令
    clear_parser = subparsers.add_parser('clear', help='清理旧记录')
    clear_parser.add_argument('--days', '-d', type=int, default=30, 
                              help='清理多少天前的记录')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        failures = list_failures(args.task, args.reason, args.limit)
        print_failures(failures, args.verbose)
    
    elif args.command == 'summary':
        handler = get_failure_handler()
        handler.print_failure_report(detailed=True)
    
    elif args.command == 'retry':
        if args.id:
            retry_single(args.id)
        elif args.task:
            retry_by_task(args.task, args.limit)
        elif args.date:
            retry_by_date(args.date)
        elif args.all:
            retry_all(args.limit)
        else:
            print("请指定重试条件: --id, --task, --date 或 --all")
    
    elif args.command == 'ignore':
        ignore_failures(args.task, args.reason, args.older_than)
    
    elif args.command == 'clear':
        clear_old_records(args.days)
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

