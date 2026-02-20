# -*- coding: utf-8 -*-
"""
每日指标采集器（PE、市值等）
"""
import logging
from typing import Dict

import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

logger = logging.getLogger(__name__)


class DailyBasicCollector(DateBasedCollector):
    """每日指标采集器"""
    
    TASK_NAME = "daily_basic"
    COLLECTION_NAME = settings.COLLECTION_DAILY_BASIC
    KEY_FIELDS = ["ts_code", "trade_date"]
    
    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定日期的全市场每日指标
        
        Args:
            trade_date: 交易日期
            
        Returns:
            每日指标DataFrame
        """
        df = self.client.get_daily_basic(trade_date=trade_date)
        
        if not df.empty:
            df['trade_date'] = df['trade_date'].astype(str)
            
            # 处理数值列
            numeric_cols = ['close', 'turnover_rate', 'turnover_rate_f', 
                           'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 
                           'ps_ttm', 'dv_ratio', 'dv_ttm', 'total_share',
                           'float_share', 'free_share', 'total_mv', 'circ_mv']
            
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def collect_by_stock(self, ts_code: str, start_date: str = None,
                         end_date: str = None) -> Dict:
        """
        按股票代码采集每日指标
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            采集结果
        """
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        
        logger.info(f"[{self.TASK_NAME}] 采集股票 {ts_code}: {start_date} - {end_date}")
        
        try:
            df = self.client.get_daily_basic(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if not df.empty:
                df['trade_date'] = df['trade_date'].astype(str)
                result = self.save_data(df)
                return result
            
            return {"success": 0, "failed": 0}
            
        except Exception as e:
            logger.error(f"采集股票 {ts_code} 每日指标失败: {e}")
            self.record_failure(ts_code=ts_code, error=e)
            return {"success": 0, "failed": 1}
    
    def get_pe_history(self, ts_code: str, start_date: str = None,
                       end_date: str = None) -> pd.DataFrame:
        """
        获取股票PE历史数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            PE历史数据DataFrame
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
            projection={"_id": 0, "ts_code": 1, "trade_date": 1, 
                       "pe": 1, "pe_ttm": 1},
            sort=[("trade_date", 1)]
        )
        
        return pd.DataFrame(data)
    
    def get_market_cap(self, ts_code: str, trade_date: str = None) -> Dict:
        """
        获取股票市值信息
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期，默认最新
            
        Returns:
            包含总市值和流通市值的字典
        """
        filter_dict = {"ts_code": ts_code}
        if trade_date:
            filter_dict["trade_date"] = trade_date
        
        result = self.db.find_many(
            self.COLLECTION_NAME,
            filter_dict,
            sort=[("trade_date", -1)],
            limit=1
        )
        
        if result:
            return {
                "total_mv": result[0].get("total_mv"),
                "circ_mv": result[0].get("circ_mv"),
                "trade_date": result[0].get("trade_date")
            }
        return None
    
    def get_daily_basic_data(self, ts_code: str, start_date: str = None,
                              end_date: str = None) -> pd.DataFrame:
        """
        获取股票每日指标完整数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            每日指标DataFrame
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

