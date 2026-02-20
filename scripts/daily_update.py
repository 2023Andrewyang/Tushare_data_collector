# -*- coding: utf-8 -*-
"""
每日增量更新脚本
用于盘后更新当日数据
"""
import sys
import os
import logging
import argparse
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.database import get_db_manager
from core.failure_handler import get_failure_handler
from collectors.stock_list import StockListCollector
from collectors.trade_calendar import TradeCalendarCollector
from collectors.daily_quote import DailyQuoteCollector
from collectors.adj_factor import AdjFactorCollector
from collectors.daily_basic import DailyBasicCollector
from collectors.limit_price import LimitPriceCollector
from collectors.suspend import SuspendCollector
from collectors.fina_indicator import FinaIndicatorCollector
from collectors.stock_st import StockSTCollector

# 配置日志
def setup_logging():
    """配置日志"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join(log_dir, f'daily_update_{datetime.now().strftime("%Y%m%d")}.log'),
                encoding='utf-8'
            )
        ]
    )

logger = logging.getLogger(__name__)


def is_trade_day(date: str = None) -> bool:
    """
    判断指定日期是否为交易日
    
    Args:
        date: 日期字符串，默认今天
        
    Returns:
        是否为交易日
    """
    date = date or datetime.now().strftime("%Y%m%d")
    db = get_db_manager()
    
    result = db.find_one(
        settings.COLLECTION_TRADE_CALENDAR,
        {"cal_date": date, "exchange": "SSE"}
    )
    
    return result.get("is_open", 0) == 1 if result else False


def get_latest_trade_date() -> str:
    """获取最近的交易日"""
    db = get_db_manager()
    today = datetime.now().strftime("%Y%m%d")
    
    result = db.find_many(
        settings.COLLECTION_TRADE_CALENDAR,
        {
            "cal_date": {"$lte": today},
            "is_open": 1,
            "exchange": "SSE"
        },
        sort=[("cal_date", -1)],
        limit=1
    )
    
    return result[0]["cal_date"] if result else today


def run_daily_update(trade_date: str = None, force: bool = False,
                     collectors: list = None):
    """
    运行每日增量更新
    
    Args:
        trade_date: 交易日期，默认为最近的交易日
        force: 是否强制更新（即使不是交易日）
        collectors: 指定要运行的采集器列表，None表示全部
    """
    setup_logging()
    # 先更新交易日历，确保日期范围查询准确
    logger.info("更新交易日历...")
    try:
        calendar_collector = TradeCalendarCollector()
        calendar_collector.collect_incremental(trade_date)
        logger.info("交易日历更新完成")
    except Exception as e:
        logger.error(f"交易日历更新失败: {e}")
    
    # 确定更新日期
    if trade_date:
        update_date = trade_date
    else:
        update_date = get_latest_trade_date()
    
    # 检查是否为交易日
    if not force and not is_trade_day(update_date):
        logger.info(f"{update_date} 不是交易日，跳过更新")
        return {}
    
    logger.info("=" * 60)
    logger.info(f"开始每日增量更新: {update_date}")
    logger.info("=" * 60)
    
    # 定义采集器
    all_collectors = {
        'trade_calendar': ('交易日历', TradeCalendarCollector),
        'stock_list': ('股票列表', StockListCollector),
        'daily_quote': ('日K线数据', DailyQuoteCollector),
        'adj_factor': ('复权因子', AdjFactorCollector),
        'daily_basic': ('每日指标', DailyBasicCollector),
        'stk_limit': ('涨跌停价格', LimitPriceCollector),
        'suspend': ('停复牌信息', SuspendCollector),
        'fina_indicator': ('财务指标', FinaIndicatorCollector),
        'stock_st': ('ST股票列表', StockSTCollector),
    }
    
    # 确定要运行的采集器
    if collectors:
        run_collectors = {k: v for k, v in all_collectors.items() if k in collectors}
    else:
        run_collectors = all_collectors
    
    results = {}
    total_start_time = datetime.now()
    
    try:
        for name, (desc, collector_class) in run_collectors.items():
            logger.info(f"\n开始更新: {desc}")
            
            try:
                collector = collector_class()
                result = collector.collect_incremental(update_date)
                results[name] = result
                
                logger.info(f"{desc}: 成功 {result.get('success', 0)}, "
                           f"失败 {result.get('failed', 0)}")
                
            except Exception as e:
                logger.error(f"{desc} 更新失败: {e}")
                results[name] = {"success": 0, "failed": 1, "error": str(e)}
    
    finally:
        # 打印汇总
        total_duration = (datetime.now() - total_start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print(f"每日更新完成 - {update_date}")
        print("=" * 60)
        
        total_success = 0
        total_failed = 0
        
        for name, result in results.items():
            desc = all_collectors.get(name, (name,))[0]
            success = result.get('success', 0)
            failed = result.get('failed', 0)
            
            total_success += success
            total_failed += failed
            
            status = "✓" if failed == 0 else "✗"
            print(f"{status} {desc}: 成功 {success}, 失败 {failed}")
        
        print("-" * 60)
        print(f"总计: 成功 {total_success}, 失败 {total_failed}")
        print(f"耗时: {total_duration:.1f}秒")
        print("=" * 60)
        
        # 如果有失败，打印失败报告
        if total_failed > 0:
            failure_handler = get_failure_handler()
            failure_handler.print_failure_report()
    
    return results


def run_batch_update(start_date: str, end_date: str = None,
                     collectors: list = None):
    """
    批量更新指定日期范围的数据
    用于补充缺失的历史数据
    
    Args:
        start_date: 开始日期
        end_date: 结束日期，默认今天
        collectors: 指定要运行的采集器列表
    """
    setup_logging()
    
    end_date = end_date or datetime.now().strftime("%Y%m%d")
    
    logger.info("=" * 60)
    logger.info(f"批量更新: {start_date} - {end_date}")
    logger.info("=" * 60)
    
    # 先更新交易日历，确保日期范围查询准确
    logger.info("更新交易日历...")
    try:
        calendar_collector = TradeCalendarCollector()
        calendar_collector.collect_incremental(end_date)
        logger.info("交易日历更新完成")
    except Exception as e:
        logger.error(f"交易日历更新失败: {e}")
    
    # 获取日期范围内的交易日
    db = get_db_manager()
    trade_dates = db.find_many(
        settings.COLLECTION_TRADE_CALENDAR,
        {
            "cal_date": {"$gte": start_date, "$lte": end_date},
            "is_open": 1,
            "exchange": "SSE"
        },
        projection={"cal_date": 1, "_id": 0},
        sort=[("cal_date", 1)]
    )
    trade_dates = [d["cal_date"] for d in trade_dates]
    
    if not trade_dates:
        logger.warning("指定日期范围内没有交易日")
        return
    
    logger.info(f"共 {len(trade_dates)} 个交易日需要更新")
    
    all_results = {}
    
    for i, date in enumerate(trade_dates):
        logger.info(f"\n[{i+1}/{len(trade_dates)}] 更新 {date}")
        result = run_daily_update(date, force=True, collectors=collectors)
        all_results[date] = result
    
    # 汇总
    print("\n" + "=" * 60)
    print("批量更新完成汇总")
    print("=" * 60)
    print(f"更新日期范围: {start_date} - {end_date}")
    print(f"交易日数量: {len(trade_dates)}")
    
    total_success = sum(
        sum(r.get('success', 0) for r in day_result.values())
        for day_result in all_results.values()
    )
    total_failed = sum(
        sum(r.get('failed', 0) for r in day_result.values())
        for day_result in all_results.values()
    )
    
    print(f"总成功: {total_success}")
    print(f"总失败: {total_failed}")
    print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='每日增量更新')
    parser.add_argument('--date', '-d', type=str, default=None,
                        help='指定交易日期 (YYYYMMDD)')
    parser.add_argument('--batch', '-b', nargs=2, metavar=('START', 'END'),
                        help='批量更新日期范围')
    parser.add_argument('--force', '-f', action='store_true',
                        help='强制更新（即使不是交易日）')
    parser.add_argument('--collectors', '-c', nargs='+',
                        choices=['trade_calendar', 'stock_list', 'daily_quote',
                                'adj_factor', 'daily_basic', 'stk_limit',
                                'suspend', 'fina_indicator', 'stock_st'],
                        help='指定要运行的采集器')
    
    args = parser.parse_args()
    
    if args.batch:
        run_batch_update(args.batch[0], args.batch[1], args.collectors)
    else:
        run_daily_update(args.date, args.force, args.collectors)


if __name__ == '__main__':
    main()

