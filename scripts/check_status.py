# -*- coding: utf-8 -*-
"""
数据状态检查脚本
用于检查数据同步状态和数据完整性
"""
import sys
import os
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.database import get_db_manager
from core.task_manager import get_task_manager
from core.failure_handler import get_failure_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_collection_stats() -> Dict:
    """检查各集合的数据统计"""
    db = get_db_manager()
    
    collections = {
        settings.COLLECTION_STOCK_LIST: "股票列表",
        settings.COLLECTION_TRADE_CALENDAR: "交易日历",
        settings.COLLECTION_DAILY_QUOTE: "日K线数据",
        settings.COLLECTION_ADJ_FACTOR: "复权因子",
        settings.COLLECTION_DAILY_BASIC: "每日指标",
        settings.COLLECTION_STK_LIMIT: "涨跌停价格",
        settings.COLLECTION_SUSPEND: "停复牌信息",
        settings.COLLECTION_FINA_INDICATOR: "财务指标",
        settings.COLLECTION_STOCK_ST: "ST股票列表",
    }
    
    stats = {}
    
    print("\n" + "=" * 70)
    print("数据集合统计")
    print("=" * 70)
    print(f"{'集合名称':<20} {'记录数':>15} {'最早日期':>12} {'最新日期':>12}")
    print("-" * 70)
    
    for collection_name, desc in collections.items():
        count = db.count(collection_name)
        
        # 获取日期范围
        if collection_name in [settings.COLLECTION_STOCK_LIST]:
            min_date = "-"
            max_date = "-"
        elif collection_name == settings.COLLECTION_TRADE_CALENDAR:
            min_date = db.get_min_value(collection_name, "cal_date") or "-"
            max_date = db.get_max_value(collection_name, "cal_date") or "-"
        elif collection_name == settings.COLLECTION_FINA_INDICATOR:
            # 财务指标使用 end_date（报告期）
            min_date = db.get_min_value(collection_name, "end_date") or "-"
            max_date = db.get_max_value(collection_name, "end_date") or "-"
        else:
            min_date = db.get_min_value(collection_name, "trade_date") or "-"
            max_date = db.get_max_value(collection_name, "trade_date") or "-"
        
        stats[collection_name] = {
            "count": count,
            "min_date": min_date,
            "max_date": max_date
        }
        
        print(f"{desc:<20} {count:>15,} {min_date:>12} {max_date:>12}")
    
    print("=" * 70)
    
    return stats


def check_data_coverage(start_date: str = None, end_date: str = None) -> Dict:
    """
    检查数据覆盖情况
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
    """
    db = get_db_manager()
    
    start_date = start_date or settings.data.start_date
    end_date = end_date or datetime.now().strftime("%Y%m%d")
    
    # 获取交易日列表
    trade_dates = db.find_many(
        settings.COLLECTION_TRADE_CALENDAR,
        {
            "cal_date": {"$gte": start_date, "$lte": end_date},
            "is_open": 1,
            "exchange": "SSE"
        },
        projection={"cal_date": 1, "_id": 0}
    )
    trade_dates = set(d["cal_date"] for d in trade_dates)
    
    if not trade_dates:
        print("未找到交易日历数据，请先同步交易日历")
        return {}
    
    print("\n" + "=" * 70)
    print(f"数据覆盖检查: {start_date} - {end_date}")
    print(f"交易日总数: {len(trade_dates)}")
    print("=" * 70)
    
    # 检查各数据集的覆盖情况
    collections_to_check = [
        (settings.COLLECTION_DAILY_QUOTE, "日K线数据"),
        (settings.COLLECTION_ADJ_FACTOR, "复权因子"),
        (settings.COLLECTION_DAILY_BASIC, "每日指标"),
        (settings.COLLECTION_STK_LIMIT, "涨跌停价格"),
    ]
    
    coverage = {}
    
    for collection_name, desc in collections_to_check:
        # 获取已有数据的日期
        existing_dates = db.distinct(
            collection_name,
            "trade_date",
            {"trade_date": {"$gte": start_date, "$lte": end_date}}
        )
        existing_dates = set(existing_dates)
        
        # 计算覆盖率
        covered = len(trade_dates & existing_dates)
        missing = trade_dates - existing_dates
        coverage_rate = covered / len(trade_dates) * 100 if trade_dates else 0
        
        coverage[collection_name] = {
            "covered": covered,
            "missing_count": len(missing),
            "coverage_rate": coverage_rate,
            "missing_dates": sorted(missing)[:10]  # 只保留前10个缺失日期
        }
        
        status = "✓" if len(missing) == 0 else "✗"
        print(f"{status} {desc:<15}: 覆盖 {covered}/{len(trade_dates)} "
              f"({coverage_rate:.1f}%), 缺失 {len(missing)}")
        
        if missing and len(missing) <= 5:
            print(f"   缺失日期: {sorted(missing)}")
    
    print("=" * 70)
    
    return coverage


def check_recent_data(days: int = 5) -> Dict:
    """
    检查最近N天的数据情况
    
    Args:
        days: 检查最近多少天
    """
    db = get_db_manager()
    
    # 获取最近的交易日
    today = datetime.now().strftime("%Y%m%d")
    trade_dates = db.find_many(
        settings.COLLECTION_TRADE_CALENDAR,
        {
            "cal_date": {"$lte": today},
            "is_open": 1,
            "exchange": "SSE"
        },
        sort=[("cal_date", -1)],
        limit=days
    )
    trade_dates = [d["cal_date"] for d in trade_dates]
    
    if not trade_dates:
        print("未找到交易日历数据")
        return {}
    
    print("\n" + "=" * 70)
    print(f"最近 {days} 个交易日数据检查")
    print("=" * 70)
    
    collections = [
        (settings.COLLECTION_DAILY_QUOTE, "日K线"),
        (settings.COLLECTION_ADJ_FACTOR, "复权因子"),
        (settings.COLLECTION_DAILY_BASIC, "每日指标"),
        (settings.COLLECTION_STK_LIMIT, "涨跌停"),
    ]
    
    # 表头
    header = f"{'日期':<12}"
    for _, desc in collections:
        header += f"{desc:>10}"
    print(header)
    print("-" * 70)
    
    result = {}
    
    for date in trade_dates:
        row = f"{date:<12}"
        date_stats = {}
        
        for collection_name, desc in collections:
            count = db.count(collection_name, {"trade_date": date})
            date_stats[collection_name] = count
            
            # 根据数量判断状态
            if count == 0:
                row += f"{'缺失':>10}"
            elif count < 100:
                row += f"{count:>10}"
            else:
                row += f"{count:>10}"
        
        result[date] = date_stats
        print(row)
    
    print("=" * 70)
    
    return result


def check_task_status():
    """检查任务状态"""
    task_manager = get_task_manager()
    task_manager.print_task_status()


def check_failures():
    """检查失败任务"""
    failure_handler = get_failure_handler()
    failure_handler.print_failure_report(detailed=True)


def find_missing_stocks(trade_date: str) -> List[str]:
    """
    查找指定日期缺失数据的股票
    
    Args:
        trade_date: 交易日期
        
    Returns:
        缺失数据的股票代码列表
    """
    db = get_db_manager()
    
    # 获取所有上市股票
    all_stocks = set(
        s["ts_code"] for s in db.find_many(
            settings.COLLECTION_STOCK_LIST,
            {"list_status": "L"},
            projection={"ts_code": 1, "_id": 0}
        )
    )
    
    # 获取该日期有数据的股票
    stocks_with_data = set(
        db.distinct(
            settings.COLLECTION_DAILY_QUOTE,
            "ts_code",
            {"trade_date": trade_date}
        )
    )
    
    missing = all_stocks - stocks_with_data
    
    print(f"\n{trade_date} 缺失日K线数据的股票: {len(missing)} 只")
    if missing and len(missing) <= 20:
        print(f"股票代码: {sorted(missing)}")
    
    return sorted(missing)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='数据状态检查')
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # stats 命令
    subparsers.add_parser('stats', help='显示数据统计')
    
    # coverage 命令
    coverage_parser = subparsers.add_parser('coverage', help='检查数据覆盖率')
    coverage_parser.add_argument('--start', '-s', type=str, help='开始日期')
    coverage_parser.add_argument('--end', '-e', type=str, help='结束日期')
    
    # recent 命令
    recent_parser = subparsers.add_parser('recent', help='检查最近数据')
    recent_parser.add_argument('--days', '-d', type=int, default=5, help='天数')
    
    # tasks 命令
    subparsers.add_parser('tasks', help='显示任务状态')
    
    # failures 命令
    subparsers.add_parser('failures', help='显示失败任务')
    
    # missing 命令
    missing_parser = subparsers.add_parser('missing', help='查找缺失数据的股票')
    missing_parser.add_argument('date', type=str, help='交易日期')
    
    # all 命令
    subparsers.add_parser('all', help='显示所有状态')
    
    args = parser.parse_args()
    
    if args.command == 'stats':
        check_collection_stats()
    
    elif args.command == 'coverage':
        check_data_coverage(args.start, args.end)
    
    elif args.command == 'recent':
        check_recent_data(args.days)
    
    elif args.command == 'tasks':
        check_task_status()
    
    elif args.command == 'failures':
        check_failures()
    
    elif args.command == 'missing':
        find_missing_stocks(args.date)
    
    elif args.command == 'all':
        check_collection_stats()
        check_recent_data()
        check_task_status()
        check_failures()
    
    else:
        # 默认显示统计和最近数据
        check_collection_stats()
        check_recent_data()


if __name__ == '__main__':
    main()

