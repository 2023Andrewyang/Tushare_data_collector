# -*- coding: utf-8 -*-
"""
涨跌停价格采集器
"""
import logging
from typing import Dict

import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

logger = logging.getLogger(__name__)


class LimitPriceCollector(DateBasedCollector):
    """涨跌停价格采集器"""
    
    TASK_NAME = "stk_limit"
    COLLECTION_NAME = settings.COLLECTION_STK_LIMIT
    KEY_FIELDS = ["ts_code", "trade_date"]
    
    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定日期的全市场涨跌停价格
        
        Args:
            trade_date: 交易日期
            
        Returns:
            涨跌停价格DataFrame
        """
        df = self.client.get_stk_limit(trade_date=trade_date)
        
        if not df.empty:
            df['trade_date'] = df['trade_date'].astype(str)
            
            # 处理数值列
            numeric_cols = ['pre_close', 'up_limit', 'down_limit']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def collect_by_stock(self, ts_code: str, start_date: str = None,
                         end_date: str = None) -> Dict:
        """
        按股票代码采集涨跌停价格
        
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
            df = self.client.get_stk_limit(
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
            logger.error(f"采集股票 {ts_code} 涨跌停价格失败: {e}")
            self.record_failure(ts_code=ts_code, error=e)
            return {"success": 0, "failed": 1}
    
    def get_limit_price(self, ts_code: str, trade_date: str) -> Dict:
        """
        获取指定股票指定日期的涨跌停价格
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            
        Returns:
            包含涨跌停价格的字典
        """
        result = self.db.find_one(
            self.COLLECTION_NAME,
            {"ts_code": ts_code, "trade_date": trade_date}
        )
        
        if result:
            return {
                "pre_close": result.get("pre_close"),
                "up_limit": result.get("up_limit"),
                "down_limit": result.get("down_limit")
            }
        return None
    
    def is_limit_up(self, ts_code: str, trade_date: str, 
                    close_price: float) -> bool:
        """
        判断是否涨停
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            close_price: 收盘价
            
        Returns:
            是否涨停
        """
        limit_info = self.get_limit_price(ts_code, trade_date)
        if limit_info and limit_info.get("up_limit"):
            # 考虑浮点数精度，使用近似比较
            return abs(close_price - limit_info["up_limit"]) < 0.01
        return False
    
    def is_limit_down(self, ts_code: str, trade_date: str,
                      close_price: float) -> bool:
        """
        判断是否跌停
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            close_price: 收盘价
            
        Returns:
            是否跌停
        """
        limit_info = self.get_limit_price(ts_code, trade_date)
        if limit_info and limit_info.get("down_limit"):
            return abs(close_price - limit_info["down_limit"]) < 0.01
        return False
    
    def get_limit_history(self, ts_code: str, start_date: str = None,
                          end_date: str = None) -> pd.DataFrame:
        """
        获取股票涨跌停价格历史
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            涨跌停价格DataFrame
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

