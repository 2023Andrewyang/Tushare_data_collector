# -*- coding: utf-8 -*-
"""
停复牌信息采集器
"""
import logging
from typing import Dict, List

import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

logger = logging.getLogger(__name__)


class SuspendCollector(DateBasedCollector):
    """停复牌信息采集器"""
    
    TASK_NAME = "suspend"
    COLLECTION_NAME = settings.COLLECTION_SUSPEND
    KEY_FIELDS = ["ts_code", "trade_date"]
    
    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定日期的停复牌信息
        
        Args:
            trade_date: 交易日期
            
        Returns:
            停复牌信息DataFrame
        """
        df = self.client.get_suspend(trade_date=trade_date)
        
        if not df.empty:
            # 确保日期字段为字符串
            if 'trade_date' in df.columns:
                df['trade_date'] = df['trade_date'].astype(str)
            if 'suspend_date' in df.columns:
                df['suspend_date'] = df['suspend_date'].astype(str)
            if 'resume_date' in df.columns:
                df['resume_date'] = df['resume_date'].astype(str)
        
        return df
    
    def collect_by_stock(self, ts_code: str, start_date: str = None,
                         end_date: str = None) -> Dict:
        """
        按股票代码采集停复牌信息
        
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
            df = self.client.get_suspend(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if not df.empty:
                if 'trade_date' in df.columns:
                    df['trade_date'] = df['trade_date'].astype(str)
                result = self.save_data(df)
                return result
            
            return {"success": 0, "failed": 0}
            
        except Exception as e:
            logger.error(f"采集股票 {ts_code} 停复牌信息失败: {e}")
            self.record_failure(ts_code=ts_code, error=e)
            return {"success": 0, "failed": 1}
    
    def is_suspended(self, ts_code: str, trade_date: str) -> bool:
        """
        判断指定股票在指定日期是否停牌
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            
        Returns:
            是否停牌
        """
        result = self.db.find_one(
            self.COLLECTION_NAME,
            {
                "ts_code": ts_code,
                "trade_date": trade_date,
                "suspend_type": "S"  # S表示停牌
            }
        )
        return result is not None
    
    def get_suspended_stocks(self, trade_date: str) -> List[str]:
        """
        获取指定日期停牌的股票列表
        
        Args:
            trade_date: 交易日期
            
        Returns:
            停牌股票代码列表
        """
        results = self.db.find_many(
            self.COLLECTION_NAME,
            {
                "trade_date": trade_date,
                "suspend_type": "S"
            },
            projection={"ts_code": 1, "_id": 0}
        )
        return [r["ts_code"] for r in results]
    
    def get_suspend_history(self, ts_code: str, start_date: str = None,
                            end_date: str = None) -> pd.DataFrame:
        """
        获取股票停复牌历史
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            停复牌历史DataFrame
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
    
    def get_suspend_days(self, ts_code: str, start_date: str = None,
                         end_date: str = None) -> int:
        """
        获取股票在指定时间段内的停牌天数
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            停牌天数
        """
        filter_dict = {
            "ts_code": ts_code,
            "suspend_type": "S"
        }
        
        if start_date or end_date:
            filter_dict["trade_date"] = {}
            if start_date:
                filter_dict["trade_date"]["$gte"] = start_date
            if end_date:
                filter_dict["trade_date"]["$lte"] = end_date
        
        return self.db.count(self.COLLECTION_NAME, filter_dict)

