# -*- coding: utf-8 -*-
"""低频接口更新检测（需求 2.3）。

update 命令逐日采集日频接口时，对低频接口按规则判断「今天要不要更新」：
- trade_calendar : 库中是否有当年数据 -> 无则采全年
- stock_basic    : 距上次采集是否超 30 天 -> 超过则全量刷新
- dc_member      : 上一个交易日是否属于上周 -> 是（本周首个交易日）则触发
- 财务三表        : 财报季（1/4/8/10）每日检查；非财报季每 7 天检查
"""
import logging
from datetime import datetime, timedelta

from config.settings import settings
from core.database import get_db_manager

logger = logging.getLogger(__name__)


class UpdateChecker:
    """低频接口更新检测器。"""

    def __init__(self):
        self.db = get_db_manager()

    @staticmethod
    def _to_datetime(value):
        """把 db 返回的 created_at（datetime 或字符串）统一成 datetime。"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except (ValueError, TypeError):
            return None

    # trade_calendar：无当年数据则需更新
    def should_update_trade_calendar(self, ref_date: str = None) -> bool:
        year = (ref_date or datetime.now().strftime("%Y%m%d"))[:4]
        cnt = self.db.count(settings.TBL_TRADE_CALENDAR,
                            "cal_date >= :s AND cal_date <= :e",
                            {"s": f"{year}0101", "e": f"{year}1231"})
        return cnt == 0

    # stock_basic：距上次采集 > 30 天
    def should_update_stock_basic(self, days: int = 30) -> bool:
        last = self._to_datetime(self.db.get_max(settings.TBL_STOCK_BASIC, "created_at"))
        if last is None:
            return True
        return (datetime.now() - last) > timedelta(days=days)

    # dc_member：本周首个交易日才更新
    def should_update_dc_member(self, ref_date: str = None) -> bool:
        ref_date = ref_date or datetime.now().strftime("%Y%m%d")
        prev = self.db.fetch_one(
            f"SELECT pretrade_date FROM {settings.TBL_TRADE_CALENDAR} "
            f"WHERE exchange='SSE' AND cal_date=:d", {"d": ref_date})
        if not prev or not prev.get("pretrade_date"):
            return True
        prev_date = prev["pretrade_date"]
        d1 = datetime.strptime(ref_date, "%Y%m%d").isocalendar()
        d0 = datetime.strptime(prev_date, "%Y%m%d").isocalendar()
        # 不在同一 ISO 周 -> ref_date 是本周首个交易日
        return (d1[0], d1[1]) != (d0[0], d0[1])

    # 财务：财报季每日，非财报季每 7 天
    def should_update_financials(self, ref_date: str = None,
                                 table: str = None) -> bool:
        ref_date = ref_date or datetime.now().strftime("%Y%m%d")
        month = int(ref_date[4:6])
        in_season = month in (1, 4, 8, 10)
        table = table or settings.TBL_FINA_INDICATOR
        if in_season:
            return True
        last = self._to_datetime(self.db.get_max(table, "created_at"))
        if last is None:
            return True
        return (datetime.now() - last) > timedelta(days=7)


def get_update_checker() -> UpdateChecker:
    return UpdateChecker()
