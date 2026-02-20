# -*- coding: utf-8 -*-
"""
股票列表采集器
"""
import logging
from typing import Dict
from datetime import datetime

import pandas as pd

from config.settings import settings
from collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class StockListCollector(BaseCollector):
    """股票列表采集器"""
    
    TASK_NAME = "stock_list"
    COLLECTION_NAME = settings.COLLECTION_STOCK_LIST
    KEY_FIELDS = ["ts_code"]
    
    def collect_full(self, start_date: str = None, end_date: str = None) -> Dict:
        """
        全量采集股票列表
        股票列表不需要日期参数
        """
        logger.info(f"[{self.TASK_NAME}] 开始采集股票列表...")
        
        start_time = datetime.now()
        
        try:
            # 获取所有状态的股票
            df = self.client.get_stock_list(list_status=None)
            
            if df.empty:
                logger.warning("未获取到股票列表数据")
                return {"success": 0, "failed": 0}
            
            # 添加更新时间
            df['update_time'] = datetime.now()
            
            # 保存数据
            result = self.save_data(df)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            stats = {
                "success": result["success"],
                "failed": result["failed"],
                "total_records": len(df),
                "duration": duration
            }
            
            # 统计各类股票数量
            if not df.empty:
                status_counts = df['list_status'].value_counts().to_dict()
                logger.info(f"股票统计: 上市(L)={status_counts.get('L', 0)}, "
                           f"退市(D)={status_counts.get('D', 0)}, "
                           f"暂停(P)={status_counts.get('P', 0)}")
            
            self.print_stats(stats)
            return stats
            
        except Exception as e:
            logger.error(f"[{self.TASK_NAME}] 采集失败: {e}")
            self.record_failure(error=e)
            return {"success": 0, "failed": 1}
    
    def collect_incremental(self, trade_date: str = None) -> Dict:
        """
        增量采集股票列表
        股票列表的增量更新就是重新获取全部数据
        """
        return self.collect_full()
    
    def get_stock_count(self) -> Dict:
        """获取股票数量统计"""
        collection = self.db.get_collection(self.COLLECTION_NAME)
        
        pipeline = [
            {"$group": {
                "_id": "$list_status",
                "count": {"$sum": 1}
            }}
        ]
        
        result = list(collection.aggregate(pipeline))
        return {item["_id"]: item["count"] for item in result}

