# -*- coding: utf-8 -*-
"""
采集器基类
定义所有采集器的通用接口和方法
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

import pandas as pd

from config.settings import settings
from core.database import get_db_manager, MongoDBManager
from core.tushare_client import get_tushare_client, TushareClient
from core.task_manager import get_task_manager, TaskManager, TaskStatus
from core.failure_handler import get_failure_handler, FailureHandler

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """采集器基类"""
    
    # 子类需要覆盖的属性
    TASK_NAME: str = None           # 任务名称
    COLLECTION_NAME: str = None     # 集合名称
    KEY_FIELDS: List[str] = []      # 主键字段
    
    def __init__(self):
        self.db: MongoDBManager = get_db_manager()
        self.client: TushareClient = get_tushare_client()
        self.task_manager: TaskManager = get_task_manager()
        self.failure_handler: FailureHandler = get_failure_handler()
        
        self._validate_config()
    
    def _validate_config(self):
        """验证配置"""
        if not self.TASK_NAME:
            raise ValueError(f"{self.__class__.__name__} 未设置 TASK_NAME")
        if not self.COLLECTION_NAME:
            raise ValueError(f"{self.__class__.__name__} 未设置 COLLECTION_NAME")
    
    @abstractmethod
    def collect_full(self, start_date: str = None, end_date: str = None) -> Dict:
        """
        全量采集数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            采集结果统计
        """
        pass
    
    @abstractmethod
    def collect_incremental(self, trade_date: str = None) -> Dict:
        """
        增量采集数据
        
        Args:
            trade_date: 交易日期，默认为当天
            
        Returns:
            采集结果统计
        """
        pass
    
    def save_data(self, df: pd.DataFrame) -> Dict:
        """
        保存数据到MongoDB
        
        Args:
            df: 数据DataFrame
            
        Returns:
            保存结果 {"success": int, "failed": int}
        """
        if df.empty:
            return {"success": 0, "failed": 0}
        
        # 转换为字典列表
        data_list = df.to_dict('records')
        
        # 批量upsert
        result = self.db.upsert_many(
            self.COLLECTION_NAME,
            data_list,
            self.KEY_FIELDS
        )
        
        logger.info(
            f"[{self.TASK_NAME}] 保存数据: 成功 {result['success']}, 失败 {result['failed']}"
        )
        
        return result
    
    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        获取日期范围内的交易日列表
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            交易日列表
        """
        dates = self.db.find_many(
            settings.COLLECTION_TRADE_CALENDAR,
            {
                "cal_date": {"$gte": start_date, "$lte": end_date},
                "is_open": 1
            },
            projection={"cal_date": 1, "_id": 0},
            sort=[("cal_date", 1)]
        )
        return [d["cal_date"] for d in dates]
    
    def get_stock_list(self, include_delisted: bool = True) -> List[str]:
        """
        获取股票代码列表
        
        Args:
            include_delisted: 是否包含退市股票
            
        Returns:
            股票代码列表
        """
        filter_dict = {}
        if not include_delisted:
            filter_dict["list_status"] = "L"
        
        stocks = self.db.find_many(
            settings.COLLECTION_STOCK_LIST,
            filter_dict,
            projection={"ts_code": 1, "_id": 0}
        )
        return [s["ts_code"] for s in stocks]
    
    def get_latest_date(self, ts_code: str = None) -> Optional[str]:
        """
        获取指定股票或全部数据的最新日期
        
        Args:
            ts_code: 股票代码，None表示全部
            
        Returns:
            最新日期字符串
        """
        filter_dict = {"ts_code": ts_code} if ts_code else {}
        return self.db.get_max_value(
            self.COLLECTION_NAME,
            "trade_date",
            filter_dict
        )
    
    def record_failure(self, ts_code: str = None, trade_date: str = None,
                       error: Exception = None, error_message: str = None,
                       context: Dict = None):
        """记录失败"""
        self.failure_handler.record_failure(
            task_name=self.TASK_NAME,
            ts_code=ts_code,
            trade_date=trade_date,
            error=error,
            error_message=error_message,
            context=context
        )
    
    def get_today(self) -> str:
        """获取今天的日期字符串"""
        return datetime.now().strftime("%Y%m%d")
    
    def print_stats(self, stats: Dict):
        """打印统计信息"""
        print(f"\n[{self.TASK_NAME}] 采集完成:")
        print(f"  成功: {stats.get('success', 0)}")
        print(f"  失败: {stats.get('failed', 0)}")
        if 'total_records' in stats:
            print(f"  总记录数: {stats['total_records']}")
        if 'duration' in stats:
            print(f"  耗时: {stats['duration']:.2f}秒")


class DateBasedCollector(BaseCollector):
    """
    基于日期的采集器基类
    适用于按日期批量获取全市场数据的场景
    """
    
    @abstractmethod
    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定日期的数据
        
        Args:
            trade_date: 交易日期
            
        Returns:
            数据DataFrame
        """
        pass
    
    def collect_full(self, start_date: str = None, end_date: str = None) -> Dict:
        """全量采集（按日期遍历）"""
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        
        logger.info(f"[{self.TASK_NAME}] 开始全量采集: {start_date} - {end_date}")
        
        # 创建/恢复任务
        task_name = f"{self.TASK_NAME}_full_{start_date}_{end_date}"
        
        # 获取交易日列表
        trade_dates = self.get_trade_dates(start_date, end_date)
        if not trade_dates:
            logger.warning("未找到交易日数据，请先同步交易日历")
            return {"success": 0, "failed": 0}
        
        total_trade_dates = len(trade_dates)
        
        # 检查是否需要断点续传
        resume_point = self.task_manager.get_resume_point(task_name)
        if resume_point["last_date"]:
            # 从断点继续
            original_count = len(trade_dates)
            trade_dates = [d for d in trade_dates if d > resume_point["last_date"]]
            skipped_count = original_count - len(trade_dates)
            
            logger.info("=" * 60)
            logger.info(f"[{self.TASK_NAME}] ★★★ 检测到断点续传 ★★★")
            logger.info(f"[{self.TASK_NAME}] 上次进度: 已处理到 {resume_point['last_date']}")
            logger.info(f"[{self.TASK_NAME}] 已完成: {skipped_count} 个交易日")
            logger.info(f"[{self.TASK_NAME}] 剩余待处理: {len(trade_dates)} 个交易日")
            logger.info(f"[{self.TASK_NAME}] 总计: {total_trade_dates} 个交易日")
            logger.info("=" * 60)
        else:
            logger.info("=" * 60)
            logger.info(f"[{self.TASK_NAME}] 全新任务开始（无断点记录）")
            logger.info(f"[{self.TASK_NAME}] 待处理: {len(trade_dates)} 个交易日")
            logger.info("=" * 60)
        
        # 创建任务
        self.task_manager.create_task(
            task_name=task_name,
            task_type=self.TASK_NAME,
            total_items=len(trade_dates),
            metadata={"start_date": start_date, "end_date": end_date}
        )
        self.task_manager.start_task(task_name)
        
        total_success = resume_point.get("processed_items", 0)
        total_failed = 0
        start_time = datetime.now()
        
        try:
            for i, trade_date in enumerate(trade_dates):
                try:
                    df = self.fetch_by_date(trade_date)
                    
                    if not df.empty:
                        result = self.save_data(df)
                        total_success += result["success"]
                        total_failed += result["failed"]
                    
                    # 更新进度
                    self.task_manager.update_progress(
                        task_name,
                        increment_processed=1,
                        last_processed_date=trade_date
                    )
                    
                    if (i + 1) % 50 == 0:
                        logger.info(f"[{self.TASK_NAME}] 进度: {i + 1}/{len(trade_dates)}")
                        
                except Exception as e:
                    logger.error(f"[{self.TASK_NAME}] 采集失败 {trade_date}: {e}")
                    self.record_failure(trade_date=trade_date, error=e)
                    total_failed += 1
                    self.task_manager.update_progress(task_name, increment_failed=1)
            
            # 完成任务
            self.task_manager.complete_task(task_name)
            
        except KeyboardInterrupt:
            logger.info("用户中断，保存进度...")
            self.task_manager.pause_task(task_name)
            raise
        except Exception as e:
            logger.error(f"任务异常: {e}")
            self.task_manager.complete_task(task_name, TaskStatus.FAILED)
            raise
        
        duration = (datetime.now() - start_time).total_seconds()
        
        stats = {
            "success": total_success,
            "failed": total_failed,
            "duration": duration
        }
        self.print_stats(stats)
        
        return stats
    
    def collect_incremental(self, trade_date: str = None) -> Dict:
        """增量采集（指定日期或最新）"""
        trade_date = trade_date or self.get_today()
        
        logger.info(f"[{self.TASK_NAME}] 增量采集: {trade_date}")
        
        try:
            df = self.fetch_by_date(trade_date)
            
            if df.empty:
                logger.info(f"[{self.TASK_NAME}] {trade_date} 无数据")
                return {"success": 0, "failed": 0}
            
            result = self.save_data(df)
            return result
            
        except Exception as e:
            logger.error(f"[{self.TASK_NAME}] 增量采集失败: {e}")
            self.record_failure(trade_date=trade_date, error=e)
            return {"success": 0, "failed": 1}


class StockBasedCollector(BaseCollector):
    """
    基于股票的采集器基类
    适用于按股票代码逐个获取数据的场景
    """
    
    @abstractmethod
    def fetch_by_stock(self, ts_code: str, start_date: str = None, 
                       end_date: str = None) -> pd.DataFrame:
        """
        获取指定股票的数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            数据DataFrame
        """
        pass
    
    def collect_full(self, start_date: str = None, end_date: str = None) -> Dict:
        """全量采集（按股票遍历）"""
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        
        logger.info(f"[{self.TASK_NAME}] 开始全量采集: {start_date} - {end_date}")
        
        # 创建任务
        task_name = f"{self.TASK_NAME}_full_{start_date}_{end_date}"
        
        # 获取股票列表
        stock_list = self.get_stock_list(include_delisted=settings.data.include_delisted)
        if not stock_list:
            logger.warning("未找到股票数据，请先同步股票列表")
            return {"success": 0, "failed": 0}
        
        total_stocks = len(stock_list)
        
        # 检查断点续传
        resume_point = self.task_manager.get_resume_point(task_name)
        if resume_point["last_code"]:
            # 从断点继续
            try:
                idx = stock_list.index(resume_point["last_code"])
                skipped_count = idx + 1
                stock_list = stock_list[idx + 1:]
                
                logger.info("=" * 60)
                logger.info(f"[{self.TASK_NAME}] ★★★ 检测到断点续传 ★★★")
                logger.info(f"[{self.TASK_NAME}] 上次进度: 已处理到 {resume_point['last_code']}")
                logger.info(f"[{self.TASK_NAME}] 已完成: {skipped_count} 只股票")
                logger.info(f"[{self.TASK_NAME}] 剩余待处理: {len(stock_list)} 只股票")
                logger.info(f"[{self.TASK_NAME}] 总计: {total_stocks} 只股票")
                logger.info("=" * 60)
            except ValueError:
                logger.warning(f"[{self.TASK_NAME}] 断点股票 {resume_point['last_code']} 不在当前列表中，从头开始")
        else:
            logger.info("=" * 60)
            logger.info(f"[{self.TASK_NAME}] 全新任务开始（无断点记录）")
            logger.info(f"[{self.TASK_NAME}] 待处理: {len(stock_list)} 只股票")
            logger.info("=" * 60)
        
        # 创建任务
        self.task_manager.create_task(
            task_name=task_name,
            task_type=self.TASK_NAME,
            total_items=len(stock_list),
            metadata={"start_date": start_date, "end_date": end_date}
        )
        self.task_manager.start_task(task_name)
        
        total_success = 0
        total_failed = 0
        start_time = datetime.now()
        
        try:
            for i, ts_code in enumerate(stock_list):
                try:
                    df = self.fetch_by_stock(ts_code, start_date, end_date)
                    
                    if not df.empty:
                        result = self.save_data(df)
                        total_success += result["success"]
                        total_failed += result["failed"]
                    
                    # 更新进度
                    self.task_manager.update_progress(
                        task_name,
                        increment_processed=1,
                        last_processed_code=ts_code
                    )
                    
                    if (i + 1) % 100 == 0:
                        logger.info(f"[{self.TASK_NAME}] 进度: {i + 1}/{len(stock_list)}")
                        
                except Exception as e:
                    logger.error(f"[{self.TASK_NAME}] 采集失败 {ts_code}: {e}")
                    self.record_failure(ts_code=ts_code, error=e)
                    total_failed += 1
                    self.task_manager.update_progress(task_name, increment_failed=1)
            
            # 完成任务
            self.task_manager.complete_task(task_name)
            
        except KeyboardInterrupt:
            logger.info("用户中断，保存进度...")
            self.task_manager.pause_task(task_name)
            raise
        except Exception as e:
            logger.error(f"任务异常: {e}")
            self.task_manager.complete_task(task_name, TaskStatus.FAILED)
            raise
        
        duration = (datetime.now() - start_time).total_seconds()
        
        stats = {
            "success": total_success,
            "failed": total_failed,
            "duration": duration
        }
        self.print_stats(stats)
        
        return stats
    
    def collect_incremental(self, trade_date: str = None) -> Dict:
        """
        增量采集
        对于基于股票的采集器，增量采集通常是获取最新一天的数据
        """
        # 默认实现：遍历所有股票获取最新数据
        # 子类可以覆盖此方法使用更高效的方式
        trade_date = trade_date or self.get_today()
        
        logger.info(f"[{self.TASK_NAME}] 增量采集: {trade_date}")
        
        stock_list = self.get_stock_list(include_delisted=False)  # 增量只处理上市股票
        
        total_success = 0
        total_failed = 0
        
        for ts_code in stock_list:
            try:
                df = self.fetch_by_stock(ts_code, trade_date, trade_date)
                
                if not df.empty:
                    result = self.save_data(df)
                    total_success += result["success"]
                    
            except Exception as e:
                logger.error(f"[{self.TASK_NAME}] 增量采集失败 {ts_code}: {e}")
                self.record_failure(ts_code=ts_code, trade_date=trade_date, error=e)
                total_failed += 1
        
        return {"success": total_success, "failed": total_failed}