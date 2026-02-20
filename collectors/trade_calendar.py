# -*- coding: utf-8 -*-
"""
交易日历采集器
"""
import logging
from typing import Dict, List
from datetime import datetime

import pandas as pd

from config.settings import settings
from collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class TradeCalendarCollector(BaseCollector):
    """交易日历采集器"""
    
    TASK_NAME = "trade_calendar"
    COLLECTION_NAME = settings.COLLECTION_TRADE_CALENDAR
    KEY_FIELDS = ["exchange", "cal_date"]
    
    def collect_full(self, start_date: str = None, end_date: str = None) -> Dict:
        """
        全量采集交易日历
        """
        start_date = start_date or settings.data.start_date
        end_date = end_date or "20301231"  # 获取到2030年
        
        logger.info(f"[{self.TASK_NAME}] 开始采集交易日历: {start_date} - {end_date}")
        
        start_time = datetime.now()
        total_success = 0
        total_failed = 0
        
        # 获取各交易所的交易日历
        exchanges = ["SSE", "SZSE"]  # 上交所、深交所
        if settings.data.include_bse:
            exchanges.append("BSE")  # 北交所
        
        all_dfs = []
        
        for exchange in exchanges:
            try:
                logger.info(f"采集 {exchange} 交易日历...")
                df = self.client.get_trade_calendar(
                    exchange=exchange,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if not df.empty:
                    df['update_time'] = datetime.now()
                    all_dfs.append(df)
                    logger.info(f"{exchange} 获取 {len(df)} 条记录")
                    
            except Exception as e:
                logger.error(f"采集 {exchange} 交易日历失败: {e}")
                self.record_failure(error=e, context={"exchange": exchange})
                total_failed += 1
        
        # 合并并保存
        if all_dfs:
            combined_df = pd.concat(all_dfs, ignore_index=True)
            result = self.save_data(combined_df)
            total_success = result["success"]
        
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
        增量采集交易日历
        通常交易日历不需要频繁更新，可以定期全量更新
        """
        # 获取当前年份到明年的数据
        current_year = datetime.now().year
        start_date = f"{current_year}0101"
        end_date = f"{current_year + 1}1231"
        
        return self.collect_full(start_date, end_date)
    
    def get_trade_dates(self, start_date: str, end_date: str, 
                        exchange: str = "SSE") -> List[str]:
        """
        获取指定范围内的交易日列表
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所代码
            
        Returns:
            交易日列表
        """
        dates = self.db.find_many(
            self.COLLECTION_NAME,
            {
                "exchange": exchange,
                "cal_date": {"$gte": start_date, "$lte": end_date},
                "is_open": 1
            },
            projection={"cal_date": 1, "_id": 0},
            sort=[("cal_date", 1)]
        )
        return [d["cal_date"] for d in dates]
    
    def is_trade_date(self, date: str, exchange: str = "SSE") -> bool:
        """判断是否为交易日"""
        result = self.db.find_one(
            self.COLLECTION_NAME,
            {"exchange": exchange, "cal_date": date}
        )
        return result.get("is_open", 0) == 1 if result else False
    
    def get_previous_trade_date(self, date: str, exchange: str = "SSE") -> str:
        """获取前一个交易日"""
        result = self.db.find_one(
            self.COLLECTION_NAME,
            {"exchange": exchange, "cal_date": date}
        )
        return result.get("pretrade_date") if result else None
    
    def get_next_trade_date(self, date: str, exchange: str = "SSE") -> str:
        """获取下一个交易日"""
        result = self.db.find_many(
            self.COLLECTION_NAME,
            {
                "exchange": exchange,
                "cal_date": {"$gt": date},
                "is_open": 1
            },
            sort=[("cal_date", 1)],
            limit=1
        )
        return result[0]["cal_date"] if result else None

