# -*- coding: utf-8 -*-
"""财务指标采集器（接口 fina_indicator，5000 分）。

按报告期(period)批量取全市场财务指标。主键 (ts_code, ann_date, end_date)，
保留财报重述记录（修复 D4）。CORE_FIELDS 必须是 schema fina_indicator 列的子集。

降级补齐：代理对个别报告期（如 20230331、20260630）的「整期全市场」查询会因为
结果集过大而稳定返回 HTTP 400，按单只股票查询则完全正常。此时自动降级为逐股
补齐，保证 retry 命令能真正修好这些报告期，而不是反复撞同一个 400。
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd

from config.settings import settings
from collectors.base_collector import PeriodBasedCollector

logger = logging.getLogger(__name__)

# 与 models/schema.py 的 fina_indicator 列对齐（除 created_at）
CORE_FIELDS = [
    "ts_code", "ann_date", "end_date", "update_flag",
    # 每股指标
    "eps", "dt_eps", "bps", "cfps", "ocfps", "ebit_ps", "fcff_ps", "fcfe_ps",
    # 盈利能力
    "roe", "roe_waa", "roe_dt", "roa", "roa2", "npta", "roic",
    "grossprofit_margin", "netprofit_margin", "op_income", "ebit", "ebitda",
    "profit_dedt", "op_to_ebt", "nop_to_ebt", "ocf_to_profit", "ocf_to_or",
    # 成长能力
    "or_yoy", "op_yoy", "ebt_yoy", "netprofit_yoy", "dt_netprofit_yoy",
    "ocf_yoy", "roe_yoy", "bps_yoy", "assets_yoy", "eqt_yoy", "tr_yoy",
    # 偿债能力
    "current_ratio", "quick_ratio", "cash_ratio", "debt_to_assets",
    "debt_to_eqt", "tangible_asset_to_debt", "eqt_to_debt",
    "eqt_to_interestdebt", "longdebt_to_workingcapital",
    # 运营效率
    "ar_turn", "ca_turn", "fa_turn", "assets_turn", "inv_turn",
    # 收益质量
    "salescash_to_or", "profit_to_op",
    # 资本结构
    "assets_to_eqt", "ca_to_assets", "nca_to_assets", "eqt_to_assets",
]


class FinaIndicatorCollector(PeriodBasedCollector):
    """全市场财务指标，按报告期采集。"""

    TASK_NAME = "fina_indicator"
    TABLE_NAME = settings.TBL_FINA_INDICATOR
    KEY_FIELDS = ["ts_code", "ann_date", "end_date"]
    REQUIRED_POINTS = 5000

    # 降级逐股补齐的并发度（取数走客户端共享令牌桶限频）
    FALLBACK_WORKERS = 4

    _FIELDS = ",".join(CORE_FIELDS)

    def fetch_by_period(self, period: str) -> pd.DataFrame:
        # 不传 fields：兼容代理对本接口的字段白名单较窄，传长字段列表会瞬间
        # 返回空结果（实测）；返回的全字段由 align_columns 按 schema 裁剪。
        try:
            df = self.client.query("fina_indicator", period=period)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[fina_indicator] 报告期 {period} 整期查询失败"
                           f"（{e}），降级为按个股补齐")
            return self._fetch_missing_by_stock(period)
        return df if df is not None else pd.DataFrame()

    def _fetch_missing_by_stock(self, period: str) -> pd.DataFrame:
        """逐股补齐整期查询取不到数据的报告期。

        只查询库中尚无该报告期记录的股票，因此重复运行会快速收敛到 0 次请求。
        """
        # 报告期尚未结束（未来报告期）时不可能有数据，避免白白打满全市场。
        if period > datetime.now().strftime("%Y%m%d"):
            logger.info(f"[fina_indicator] 报告期 {period} 尚未结束，跳过降级补齐")
            return pd.DataFrame()

        have = {r["ts_code"] for r in self.db.fetch_all(
            f"SELECT DISTINCT ts_code FROM {self.TABLE_NAME} WHERE end_date=:p",
            {"p": period})}
        codes = [c for c in self.get_stock_codes() if c not in have]
        if not codes:
            logger.info(f"[fina_indicator] 报告期 {period} 已覆盖"
                        f"（{len(have)} 只），无缺失股票")
            return pd.DataFrame()

        logger.info(f"[fina_indicator] 报告期 {period} 降级逐股补齐："
                    f"已有 {len(have)} 只，待补 {len(codes)} 只")
        frames, errors = [], 0
        with ThreadPoolExecutor(max_workers=self.FALLBACK_WORKERS) as ex:
            futures = [ex.submit(self.client.query, "fina_indicator", None,
                                 ts_code=c, period=period) for c in codes]
            for f in as_completed(futures):
                try:
                    df = f.result()
                except Exception as e:  # noqa: BLE001
                    errors += 1
                    if errors <= 5:
                        logger.warning(f"[fina_indicator] 逐股补齐失败: {e}")
                    continue
                if df is not None and not df.empty:
                    frames.append(df)
        if errors:
            logger.warning(f"[fina_indicator] 报告期 {period} 逐股补齐共 "
                           f"{errors} 次请求失败")
        if not frames:
            logger.warning(f"[fina_indicator] 报告期 {period} 逐股补齐未取到任何数据")
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)
