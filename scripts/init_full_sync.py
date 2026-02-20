# -*- coding: utf-8 -*-
"""
首次全量同步脚本
用于初始化数据库，获取所有历史数据
"""
import sys
import os
import logging
import argparse
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.database import get_db_manager
from core.task_manager import get_task_manager
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                        'logs', f'full_sync_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
            encoding='utf-8'
        )
    ]
)

logger = logging.getLogger(__name__)


def ensure_log_dir():
    """确保日志目录存在"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)


def run_full_sync(start_date: str = None, end_date: str = None, 
                  skip_basic: bool = False, collectors: list = None):
    """
    运行全量同步
    
    Args:
        start_date: 开始日期
        end_date: 结束日期
        skip_basic: 是否跳过基础数据（股票列表、交易日历）
        collectors: 指定要运行的采集器列表，None表示全部
    """
    start_date = start_date or settings.data.start_date
    end_date = end_date or datetime.now().strftime("%Y%m%d")
    
    logger.info("=" * 60)
    logger.info("开始全量数据同步")
    logger.info(f"数据范围: {start_date} - {end_date}")
    logger.info("=" * 60)
    
    # 初始化数据库连接
    db = get_db_manager()
    
    # 创建索引
    logger.info("创建数据库索引...")
    db.ensure_indexes()
    
    # 定义采集器及其执行顺序
    all_collectors = {
        # 基础数据
        'stock_list': ('股票列表', StockListCollector),
        'trade_calendar': ('交易日历', TradeCalendarCollector),
        # 行情数据
        'daily_quote': ('日K线数据', DailyQuoteCollector),
        'adj_factor': ('复权因子', AdjFactorCollector),
        'daily_basic': ('每日指标', DailyBasicCollector),
        'stk_limit': ('涨跌停价格', LimitPriceCollector),
        'suspend': ('停复牌信息', SuspendCollector),
        # 财务数据
        'fina_indicator': ('财务指标', FinaIndicatorCollector),
        # 参考数据
        'stock_st': ('ST股票列表', StockSTCollector),
    }
    
    # 确定要运行的采集器
    if collectors:
        run_collectors = {k: v for k, v in all_collectors.items() if k in collectors}
    else:
        run_collectors = all_collectors
    
    # 基础数据采集器（必须优先执行）
    basic_collectors = ['stock_list', 'trade_calendar']
    
    results = {}
    total_start_time = datetime.now()
    
    try:
        # 1. 首先同步基础数据（股票列表和交易日历）
        if not skip_basic:
            for name in basic_collectors:
                if name in run_collectors:
                    desc, collector_class = run_collectors[name]
                    logger.info(f"\n{'='*40}")
                    logger.info(f"开始采集: {desc}")
                    logger.info(f"{'='*40}")
                    
                    try:
                        collector = collector_class()
                        result = collector.collect_full(start_date, end_date)
                        results[name] = result
                    except Exception as e:
                        logger.error(f"{desc} 采集失败: {e}")
                        results[name] = {"success": 0, "failed": 1, "error": str(e)}
        
        # 2. 然后同步行情数据
        for name, (desc, collector_class) in run_collectors.items():
            if name in basic_collectors:
                continue  # 跳过已处理的基础数据
            
            logger.info(f"\n{'='*40}")
            logger.info(f"开始采集: {desc}")
            logger.info(f"{'='*40}")
            
            try:
                collector = collector_class()
                result = collector.collect_full(start_date, end_date)
                results[name] = result
            except KeyboardInterrupt:
                logger.warning("用户中断，已保存进度")
                break
            except Exception as e:
                logger.error(f"{desc} 采集失败: {e}")
                results[name] = {"success": 0, "failed": 1, "error": str(e)}
    
    finally:
        # 打印汇总报告
        total_duration = (datetime.now() - total_start_time).total_seconds()
        
        print("\n" + "=" * 60)
        print("全量同步完成 - 汇总报告")
        print("=" * 60)
        
        total_success = 0
        total_failed = 0
        
        for name, result in results.items():
            desc = all_collectors.get(name, (name,))[0]
            success = result.get('success', 0)
            failed = result.get('failed', 0)
            duration = result.get('duration', 0)
            
            total_success += success
            total_failed += failed
            
            status = "✓" if failed == 0 else "✗"
            print(f"{status} {desc}: 成功 {success}, 失败 {failed}, 耗时 {duration:.1f}秒")
        
        print("-" * 60)
        print(f"总计: 成功 {total_success}, 失败 {total_failed}")
        print(f"总耗时: {total_duration:.1f}秒 ({total_duration/60:.1f}分钟)")
        print("=" * 60)
        
        # 打印失败任务摘要
        failure_handler = get_failure_handler()
        failure_handler.print_failure_report()
    
    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='全量数据同步')
    parser.add_argument('--start-date', '-s', type=str, 
                        default=settings.data.start_date,
                        help='开始日期 (YYYYMMDD)')
    parser.add_argument('--end-date', '-e', type=str, 
                        default=None,
                        help='结束日期 (YYYYMMDD)，默认今天')
    parser.add_argument('--skip-basic', action='store_true',
                        help='跳过基础数据（股票列表、交易日历）')
    parser.add_argument('--collectors', '-c', nargs='+',
                        choices=['stock_list', 'trade_calendar', 'daily_quote', 
                                'adj_factor', 'daily_basic', 'stk_limit',
                                'suspend', 'fina_indicator', 'stock_st'],
                        help='指定要运行的采集器')
    
    args = parser.parse_args()
    
    # 确保日志目录存在
    ensure_log_dir()
    
    # 运行同步
    run_full_sync(
        start_date=args.start_date,
        end_date=args.end_date,
        skip_basic=args.skip_basic,
        collectors=args.collectors
    )


if __name__ == '__main__':
    main()

