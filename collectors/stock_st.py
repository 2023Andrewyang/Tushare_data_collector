# -*- coding: utf-8 -*-
"""
ST股票列表采集器
获取历史上每天的ST股票列表
"""
import logging
from typing import Dict, List

import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

logger = logging.getLogger(__name__)


class StockSTCollector(DateBasedCollector):
    """
    ST股票列表采集器
    
    数据来源: Tushare stock_st 接口
    数据起始: 2016年1月1日
    更新频率: 每日盘前9:20更新
    权限要求: 3000积分
    
    主要用途:
    - 风控过滤：排除ST股票
    - 回测准确性：知道历史上哪些股票是ST状态
    - ST策略研究
    """
    
    TASK_NAME = "stock_st"
    COLLECTION_NAME = settings.COLLECTION_STOCK_ST
    KEY_FIELDS = ["ts_code", "trade_date"]
    
    # ST数据从2016年开始
    DATA_START_DATE = "20160101"
    
    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定日期的ST股票列表
        
        Args:
            trade_date: 交易日期
            
        Returns:
            ST股票列表DataFrame
        """
        df = self.client.query(
            'stock_st',
            trade_date=trade_date,
            fields="ts_code,name,trade_date,type,type_name"
        )
        
        if not df.empty:
            df['trade_date'] = df['trade_date'].astype(str)
        
        return df
    
    def collect_full(self, start_date: str = None, end_date: str = None) -> Dict:
        """
        全量采集ST股票列表
        
        注意：ST数据从2016年开始，早于此日期的数据不可用
        """
        # ST数据从2016年开始
        if start_date is None or start_date < self.DATA_START_DATE:
            start_date = self.DATA_START_DATE
            logger.info(f"[{self.TASK_NAME}] ST数据从2016年开始，调整起始日期为 {start_date}")
        
        return super().collect_full(start_date, end_date)
    
    def collect_by_stock(self, ts_code: str, start_date: str = None,
                         end_date: str = None) -> Dict:
        """
        获取指定股票的ST历史记录
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
        """
        start_date = start_date or self.DATA_START_DATE
        end_date = end_date or self.get_today()
        
        logger.info(f"[{self.TASK_NAME}] 采集股票 {ts_code} ST历史: {start_date} - {end_date}")
        
        try:
            df = self.client.query(
                'stock_st',
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields="ts_code,name,trade_date,type,type_name"
            )
            
            if not df.empty:
                df['trade_date'] = df['trade_date'].astype(str)
                result = self.save_data(df)
                return result
            
            return {"success": 0, "failed": 0}
            
        except Exception as e:
            logger.error(f"采集股票 {ts_code} ST历史失败: {e}")
            self.record_failure(ts_code=ts_code, error=e)
            return {"success": 0, "failed": 1}
    
    # ==================== 数据查询方法 ====================
    
    def is_st(self, ts_code: str, trade_date: str) -> bool:
        """
        判断指定股票在指定日期是否为ST
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            
        Returns:
            是否为ST
        """
        result = self.db.find_one(
            self.COLLECTION_NAME,
            {"ts_code": ts_code, "trade_date": trade_date}
        )
        return result is not None
    
    def get_st_stocks(self, trade_date: str) -> List[str]:
        """
        获取指定日期的所有ST股票代码
        
        Args:
            trade_date: 交易日期
            
        Returns:
            ST股票代码列表
        """
        results = self.db.find_many(
            self.COLLECTION_NAME,
            {"trade_date": trade_date},
            projection={"ts_code": 1, "_id": 0}
        )
        return [r["ts_code"] for r in results]
    
    def get_st_history(self, ts_code: str, start_date: str = None,
                       end_date: str = None) -> pd.DataFrame:
        """
        获取股票的ST历史记录
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            ST历史DataFrame
        """
        filter_dict = {"ts_code": ts_code}
        
        if start_date or end_date:
            filter_dict["trade_date"] = {}
            if start_date:
                filter_dict["trade_date"]["$gte"] = start_date
            if end_date:
                filter_dict["trade_date"]["$lte"] = end_date
        
        data = self.db.find_many(
            self.COLLECTION_NAME,
            filter_dict,
            projection={"_id": 0},
            sort=[("trade_date", 1)]
        )
        
        return pd.DataFrame(data)
    
    def get_st_count(self, trade_date: str) -> int:
        """
        获取指定日期ST股票数量
        
        Args:
            trade_date: 交易日期
            
        Returns:
            ST股票数量
        """
        return self.db.count(self.COLLECTION_NAME, {"trade_date": trade_date})
    
    def get_st_statistics(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日期范围内每天的ST股票数量统计
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            包含每天ST数量的DataFrame
        """
        collection = self.db.get_collection(self.COLLECTION_NAME)
        
        pipeline = [
            {"$match": {
                "trade_date": {"$gte": start_date, "$lte": end_date}
            }},
            {"$group": {
                "_id": "$trade_date",
                "st_count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        result = list(collection.aggregate(pipeline))
        
        df = pd.DataFrame(result)
        if not df.empty:
            df.columns = ["trade_date", "st_count"]
        
        return df
    
    def get_non_st_stocks(self, trade_date: str, stock_list: List[str] = None) -> List[str]:
        """
        获取指定日期的非ST股票列表
        
        Args:
            trade_date: 交易日期
            stock_list: 待筛选的股票列表，None则从stock_list集合获取
            
        Returns:
            非ST股票代码列表
        """
        # 获取当天的ST股票
        st_stocks = set(self.get_st_stocks(trade_date))
        
        # 获取所有股票
        if stock_list is None:
            all_stocks = self.db.find_many(
                settings.COLLECTION_STOCK_LIST,
                {"list_status": "L"},
                projection={"ts_code": 1, "_id": 0}
            )
            stock_list = [s["ts_code"] for s in all_stocks]
        
        # 排除ST股票
        return [s for s in stock_list if s not in st_stocks]

