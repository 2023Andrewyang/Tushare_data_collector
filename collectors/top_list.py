# -*- coding: utf-8 -*-
"""龙虎榜采集器（接口 top_list + top_inst，2000 分）。

特殊：一次抓取写入两张表（top_list + top_inst）。
fetch_by_date 顺带把 top_inst 写库，再返回 top_list 数据走基类正常流程。
"""
import logging

import pandas as pd

from config.settings import settings
from collectors.base_collector import DateBasedCollector

logger = logging.getLogger(__name__)

_LIST_FIELDS = ("ts_code,trade_date,name,close,pct_change,turnover_rate,amount,"
                "l_sell,l_buy,l_amount,net_amount,net_rate,amount_rate,"
                "float_values,reason")
_INST_FIELDS = ("ts_code,trade_date,exalter,side,buy,buy_rate,sell,sell_rate,"
                "net_buy,reason")


class TopListCollector(DateBasedCollector):
    """龙虎榜股票列表 + 机构席位明细，按交易日采集。"""

    TASK_NAME = "top_list"
    TABLE_NAME = settings.TBL_TOP_LIST
    KEY_FIELDS = ["ts_code", "trade_date"]
    REQUIRED_POINTS = 2000

    def fetch_by_date(self, trade_date: str) -> pd.DataFrame:
        # 两个接口必须同时成功，才能把该日期标为已完成；否则断点续传会重试。
        try:
            inst = self.client.query("top_inst", trade_date=trade_date,
                                     fields=_INST_FIELDS)
            if inst is not None and not inst.empty:
                self.save(inst, table_name=settings.TBL_TOP_INST,
                          key_fields=["ts_code", "trade_date", "exalter"])
        except Exception as e:
            logger.error(f"[top_inst] {trade_date} 失败: {e}")
            self.failure.record_failure("top_inst", trade_date=trade_date, error=e)
            raise

        return self.client.query("top_list", trade_date=trade_date, fields=_LIST_FIELDS)
