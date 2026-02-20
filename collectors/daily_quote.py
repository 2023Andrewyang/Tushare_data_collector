# -*- coding: utf-8 -*-
"""
日K线数据采集器
"""
import logging
from typing import Dict

import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

logger = logging.getLogger(__name__)


class DailyQuoteCollector(DateBasedCollector):
    """日K线数据采集器"""
    
    TASK_NAME = "daily_quote"
    COLLECTION_NAME = settings.COLLECTION_DAILY_QUOTE
    KEY_FIELDS = ["ts_code", "trade_date"]
    
    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定日期的全市场日K线数据
        
        Args:
            trade_date: 交易日期
            
        Returns:
            日K线数据DataFrame
        """
        df = self.client.get_daily_quote(trade_date=trade_date)
        
        if not df.empty:
            # 数据类型转换和清洗
            df['trade_date'] = df['trade_date'].astype(str)
            
            # 处理可能的空值
            numeric_cols = ['open', 'high', 'low', 'close', 'pre_close', 
                           'change', 'pct_chg', 'vol', 'amount']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def collect_by_stock(self, ts_code: str, start_date: str = None, 
                         end_date: str = None) -> Dict:
        """
        按股票代码采集历史数据
        用于补充单只股票的历史数据
        
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
            df = self.client.get_daily_quote(
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
            logger.error(f"采集股票 {ts_code} 失败: {e}")
            self.record_failure(ts_code=ts_code, error=e)
            return {"success": 0, "failed": 1}
    
    def get_stock_daily(self, ts_code: str, start_date: str = None,
                        end_date: str = None) -> pd.DataFrame:
        """
        从数据库获取股票日K线数据
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            日K线DataFrame
        """
        filter_dict = {"ts_code": ts_code}
        
        if start_date:
            filter_dict["trade_date"] = {"$gte": start_date}
        if end_date:
            if "trade_date" in filter_dict:
                filter_dict["trade_date"]["$lte"] = end_date
            else:
                filter_dict["trade_date"] = {"$lte": end_date}
        
        data = self.db.find_many(
            self.COLLECTION_NAME,
            filter_dict,
            projection={"_id": 0},
            sort=[("trade_date", 1)]
        )
        
        return pd.DataFrame(data)

