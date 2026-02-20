# -*- coding: utf-8 -*-
"""
财务指标采集器
采集 fina_indicator 接口的核心财务指标数据
"""
import logging
from typing import Dict, List

import pandas as pd

from config.settings import settings
from collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class FinaIndicatorCollector(BaseCollector):
    """
    财务指标采集器
    
    数据来源: Tushare fina_indicator 接口
    更新频率: 随财报披露更新（季度）
    主要用途: 量化因子计算、基本面分析
    """
    
    TASK_NAME = "fina_indicator"
    COLLECTION_NAME = settings.COLLECTION_FINA_INDICATOR
    KEY_FIELDS = ["ts_code", "end_date"]
    
    # 核心字段定义 - 只采集量化分析最需要的指标
    CORE_FIELDS = [
        # === 基础信息 ===
        "ts_code",          # 股票代码
        "ann_date",         # 公告日期
        "end_date",         # 报告期
        "update_flag",      # 更新标识
        
        # === 每股指标 ===
        "eps",              # 基本每股收益
        "dt_eps",           # 稀释每股收益
        "bps",              # 每股净资产
        "cfps",             # 每股经营现金流
        "ocfps",            # 每股经营活动现金流净额
        "ebit_ps",          # 每股息税前利润
        "fcff_ps",          # 每股企业自由现金流
        "fcfe_ps",          # 每股股东自由现金流
        
        # === 盈利能力 ===
        "roe",              # 净资产收益率
        "roe_waa",          # 加权平均净资产收益率
        "roe_dt",           # 净资产收益率(扣除非经常损益)
        "roa",              # 总资产报酬率
        "roa2",             # 总资产净利率
        "npta",             # 总资产净利润
        "roic",             # 投入资本回报率
        "grossprofit_margin",    # 销售毛利率
        "netprofit_margin",      # 销售净利率
        "op_income",             # 营业利润
        "ebit",                  # 息税前利润
        "ebitda",                # 息税折旧摊销前利润
        "profit_dedt",           # 扣除非经常损益后的净利润
        "op_to_ebt",             # 营业利润/利润总额
        "nop_to_ebt",            # 非营业利润/利润总额
        "ocf_to_profit",         # 经营现金净流量/净利润
        "ocf_to_or",             # 经营现金净流量/营业收入
        
        # === 成长能力 ===
        "or_yoy",           # 营业收入同比增长率
        "op_yoy",           # 营业利润同比增长率
        "ebt_yoy",          # 利润总额同比增长率
        "netprofit_yoy",    # 归属母公司股东净利润同比增长率
        "dt_netprofit_yoy", # 扣非净利润同比增长率
        "ocf_yoy",          # 经营现金流同比增长率
        "roe_yoy",          # 净资产收益率同比增长率
        "bps_yoy",          # 每股净资产同比增长率
        "assets_yoy",       # 总资产同比增长率
        "eqt_yoy",          # 净资产同比增长率
        "tr_yoy",           # 营业总收入同比增长率
        
        # === 偿债能力 ===
        "current_ratio",    # 流动比率
        "quick_ratio",      # 速动比率
        "cash_ratio",       # 保守速动比率
        "debt_to_assets",   # 资产负债率
        "debt_to_eqt",      # 产权比率
        "tangible_asset_to_debt",  # 有形资产/负债合计
        "eqt_to_debt",      # 归属母公司股东权益/负债合计
        "eqt_to_interestdebt",     # 股东权益/带息债务
        "longdebt_to_workingcapital",  # 长期债务与营运资金比率
        
        # === 运营效率 ===
        "ar_turn",          # 应收账款周转率
        "ca_turn",          # 流动资产周转率
        "fa_turn",          # 固定资产周转率
        "assets_turn",      # 总资产周转率
        "inv_turn",         # 存货周转率
        
        # === 收益质量 ===
        "salescash_to_or",  # 销售商品提供劳务收到的现金/营业收入
        "profit_to_op",     # 净利润/营业总收入
        
        # === 资本结构 ===
        "assets_to_eqt",    # 权益乘数
        "ca_to_assets",     # 流动资产/总资产
        "nca_to_assets",    # 非流动资产/总资产
        "eqt_to_assets",    # 股东权益/总资产
    ]
    
    def __init__(self):
        super().__init__()
        self._fields_str = ",".join(self.CORE_FIELDS)
    
    def collect_full(self, start_date: str = None, end_date: str = None) -> Dict:
        """
        全量采集财务指标数据
        
        采集策略：按报告期(period)遍历，每次获取该报告期所有股票的数据
        报告期格式：YYYYMMDD，如 20231231（年报）、20230930（三季报）等
        """
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        
        logger.info(f"[{self.TASK_NAME}] 开始全量采集: {start_date} - {end_date}")
        
        # 生成报告期列表
        periods = self._generate_report_periods(start_date, end_date)
        if not periods:
            logger.warning("无有效报告期")
            return {"success": 0, "failed": 0}
        
        logger.info(f"[{self.TASK_NAME}] 共 {len(periods)} 个报告期需要采集")
        
        # 创建任务
        task_name = f"{self.TASK_NAME}_full_{start_date}_{end_date}"
        
        # 检查断点续传
        resume_point = self.task_manager.get_resume_point(task_name)
        if resume_point["last_date"]:
            original_count = len(periods)
            periods = [p for p in periods if p > resume_point["last_date"]]
            logger.info(f"从断点续传: {resume_point['last_date']}, 剩余 {len(periods)}/{original_count} 个报告期")
        
        self.task_manager.create_task(
            task_name=task_name,
            task_type=self.TASK_NAME,
            total_items=len(periods),
            metadata={"start_date": start_date, "end_date": end_date}
        )
        self.task_manager.start_task(task_name)
        
        total_success = 0
        total_failed = 0
        
        from datetime import datetime
        start_time = datetime.now()
        
        try:
            for i, period in enumerate(periods):
                try:
                    df = self._fetch_by_period(period)
                    
                    if not df.empty:
                        result = self.save_data(df)
                        total_success += result["success"]
                        total_failed += result["failed"]
                        logger.info(f"[{self.TASK_NAME}] 报告期 {period}: {len(df)} 条记录")
                    else:
                        logger.debug(f"[{self.TASK_NAME}] 报告期 {period}: 无数据")
                    
                    self.task_manager.update_progress(
                        task_name,
                        increment_processed=1,
                        last_processed_date=period
                    )
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"[{self.TASK_NAME}] 进度: {i + 1}/{len(periods)}")
                        
                except Exception as e:
                    logger.error(f"[{self.TASK_NAME}] 采集报告期 {period} 失败: {e}")
                    self.record_failure(trade_date=period, error=e)
                    total_failed += 1
                    self.task_manager.update_progress(task_name, increment_failed=1)
            
            self.task_manager.complete_task(task_name)
            
        except KeyboardInterrupt:
            logger.info("用户中断，保存进度...")
            self.task_manager.pause_task(task_name)
            raise
        
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
        增量采集财务指标
        
        策略：获取最近公告的财务数据
        """
        # 获取最近的报告期
        latest_periods = self._get_recent_periods(n=2)
        
        logger.info(f"[{self.TASK_NAME}] 增量采集最近报告期: {latest_periods}")
        
        total_success = 0
        total_failed = 0
        
        for period in latest_periods:
            try:
                df = self._fetch_by_period(period)
                
                if not df.empty:
                    result = self.save_data(df)
                    total_success += result["success"]
                    logger.info(f"[{self.TASK_NAME}] 报告期 {period}: 更新 {result['success']} 条")
                    
            except Exception as e:
                logger.error(f"[{self.TASK_NAME}] 增量采集 {period} 失败: {e}")
                self.record_failure(trade_date=period, error=e)
                total_failed += 1
        
        return {"success": total_success, "failed": total_failed}
    
    def _fetch_by_period(self, period: str) -> pd.DataFrame:
        """
        获取指定报告期的财务指标数据
        
        使用 fina_indicator_vip 接口（需要5000+积分）
        支持按报告期获取全市场数据
        
        Args:
            period: 报告期，如 20231231
            
        Returns:
            财务指标DataFrame
        """
        # 使用VIP接口，支持按period获取全市场数据
        # 普通接口必须提供ts_code，无法批量获取
        df = self.client.query(
            'fina_indicator_vip',
            period=period,
            fields=self._fields_str
        )
        
        if not df.empty:
            # 确保日期字段为字符串
            for col in ['ann_date', 'end_date']:
                if col in df.columns:
                    df[col] = df[col].astype(str)
            
            # 转换数值列
            numeric_cols = [c for c in df.columns 
                          if c not in ['ts_code', 'ann_date', 'end_date', 'update_flag']]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df
    
    def collect_by_stock(self, ts_code: str, start_date: str = None,
                         end_date: str = None) -> Dict:
        """
        按股票代码采集财务指标
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
        """
        start_date = start_date or settings.data.start_date
        end_date = end_date or self.get_today()
        
        logger.info(f"[{self.TASK_NAME}] 采集股票 {ts_code}: {start_date} - {end_date}")
        
        try:
            df = self.client.query(
                'fina_indicator',
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields=self._fields_str
            )
            
            if not df.empty:
                for col in ['ann_date', 'end_date']:
                    if col in df.columns:
                        df[col] = df[col].astype(str)
                
                result = self.save_data(df)
                return result
            
            return {"success": 0, "failed": 0}
            
        except Exception as e:
            logger.error(f"采集股票 {ts_code} 财务指标失败: {e}")
            self.record_failure(ts_code=ts_code, error=e)
            return {"success": 0, "failed": 1}
    
    def _generate_report_periods(self, start_date: str, end_date: str) -> List[str]:
        """
        生成报告期列表
        
        报告期为季度末日期：0331(一季报), 0630(半年报), 0930(三季报), 1231(年报)
        """
        from datetime import datetime
        
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        
        quarters = ['0331', '0630', '0930', '1231']
        periods = []
        
        for year in range(start_year, end_year + 1):
            for q in quarters:
                period = f"{year}{q}"
                if start_date <= period <= end_date:
                    periods.append(period)
        
        return sorted(periods)
    
    def _get_recent_periods(self, n: int = 2) -> List[str]:
        """
        获取最近N个报告期
        """
        from datetime import datetime
        
        today = datetime.now()
        year = today.year
        month = today.month
        
        # 确定当前最新的报告期
        if month >= 10:
            # 10-12月，最新是三季报
            latest_q = f"{year}0930"
        elif month >= 7:
            # 7-9月，最新是半年报
            latest_q = f"{year}0630"
        elif month >= 4:
            # 4-6月，最新是一季报
            latest_q = f"{year}0331"
        else:
            # 1-3月，最新是上年年报
            latest_q = f"{year-1}1231"
        
        # 生成最近N个报告期
        all_periods = self._generate_report_periods(f"{year-2}0101", f"{year}1231")
        
        # 找到latest_q的位置
        try:
            idx = all_periods.index(latest_q)
            return all_periods[max(0, idx-n+1):idx+1]
        except ValueError:
            return all_periods[-n:] if len(all_periods) >= n else all_periods
    
    # ==================== 数据查询方法 ====================
    
    def get_stock_fina(self, ts_code: str, start_date: str = None,
                       end_date: str = None) -> pd.DataFrame:
        """
        从数据库获取股票财务指标
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期（报告期）
            end_date: 结束日期（报告期）
            
        Returns:
            财务指标DataFrame
        """
        filter_dict = {"ts_code": ts_code}
        
        if start_date or end_date:
            filter_dict["end_date"] = {}
            if start_date:
                filter_dict["end_date"]["$gte"] = start_date
            if end_date:
                filter_dict["end_date"]["$lte"] = end_date
        
        data = self.db.find_many(
            self.COLLECTION_NAME,
            filter_dict,
            projection={"_id": 0},
            sort=[("end_date", -1)]
        )
        
        return pd.DataFrame(data)
    
    def get_latest_fina(self, ts_code: str) -> Dict:
        """
        获取股票最新一期财务指标
        
        Args:
            ts_code: 股票代码
            
        Returns:
            最新财务指标字典
        """
        result = self.db.find_many(
            self.COLLECTION_NAME,
            {"ts_code": ts_code},
            projection={"_id": 0},
            sort=[("end_date", -1)],
            limit=1
        )
        
        return result[0] if result else None
    
    def get_period_fina(self, period: str) -> pd.DataFrame:
        """
        获取指定报告期所有股票的财务指标
        
        Args:
            period: 报告期，如 20231231
            
        Returns:
            财务指标DataFrame
        """
        data = self.db.find_many(
            self.COLLECTION_NAME,
            {"end_date": period},
            projection={"_id": 0}
        )
        
        return pd.DataFrame(data)
    
    def get_roe_ranking(self, period: str, top_n: int = 100) -> pd.DataFrame:
        """
        获取指定报告期ROE排名
        
        Args:
            period: 报告期
            top_n: 返回前N名
            
        Returns:
            ROE排名DataFrame
        """
        data = self.db.find_many(
            self.COLLECTION_NAME,
            {"end_date": period, "roe": {"$ne": None}},
            projection={"ts_code": 1, "roe": 1, "roe_dt": 1, "_id": 0},
            sort=[("roe", -1)],
            limit=top_n
        )
        
        return pd.DataFrame(data)

