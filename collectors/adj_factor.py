# -*- coding: utf-8 -*-
"""
复权因子采集器
"""
import logging
from typing import Dict

import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

logger = logging.getLogger(__name__)


class AdjFactorCollector(DateBasedCollector):
    """复权因子采集器"""
    
    TASK_NAME = "adj_factor"
    COLLECTION_NAME = settings.COLLECTION_ADJ_FACTOR
    KEY_FIELDS = ["ts_code", "trade_date"]
    
    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定日期的全市场复权因子
        
        Args:
            trade_date: 交易日期
            
        Returns:
            复权因子DataFrame
        """
        df = self.client.get_adj_factor(trade_date=trade_date)
        
        if not df.empty:
            df['trade_date'] = df['trade_date'].astype(str)
            df['adj_factor'] = pd.to_numeric(df['adj_factor'], errors='coerce')
        
        return df
    
    def collect_by_stock(self, ts_code: str, start_date: str = None,
                         end_date: str = None) -> Dict:
        """
        按股票代码采集复权因子
        
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
            df = self.client.get_adj_factor(
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
            logger.error(f"采集股票 {ts_code} 复权因子失败: {e}")
            self.record_failure(ts_code=ts_code, error=e)
            return {"success": 0, "failed": 1}
    
    def get_adj_factor(self, ts_code: str, trade_date: str = None) -> float:
        """
        获取指定股票指定日期的复权因子
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期，默认最新
            
        Returns:
            复权因子
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
        
        return result[0]["adj_factor"] if result else None
    
    def get_adj_factors(self, ts_code: str, start_date: str = None,
                        end_date: str = None) -> pd.DataFrame:
        """
        获取股票的复权因子序列
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            复权因子DataFrame
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
    
    def calculate_adjusted_price(self, ts_code: str, trade_date: str,
                                  price: float, adj_type: str = "qfq") -> float:
        """
        计算复权价格
        
        Args:
            ts_code: 股票代码
            trade_date: 交易日期
            price: 原始价格
            adj_type: 复权类型 qfq-前复权, hfq-后复权
            
        Returns:
            复权后价格
        """
        if adj_type == "qfq":
            # 前复权: 当日价格 * (当日复权因子 / 最新复权因子)
            current_factor = self.get_adj_factor(ts_code, trade_date)
            latest_factor = self.get_adj_factor(ts_code)
            
            if current_factor and latest_factor:
                return price * (current_factor / latest_factor)
        
        elif adj_type == "hfq":
            # 后复权: 当日价格 * 当日复权因子
            factor = self.get_adj_factor(ts_code, trade_date)
            if factor:
                return price * factor
        
        return price

