# -*- coding: utf-8 -*-
"""全局配置：从 .env 读取，提供 settings 单例与表名常量。"""
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# 加载 .env（项目根目录）
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _strip_inline_comment(val: str) -> str:
    """去掉 .env 值里行内 '# 注释'，并去首尾空白。"""
    if val is None:
        return val
    # 仅当 # 前有空白时视为注释起点，避免误伤含 # 的密码
    idx = val.find("#")
    if idx > 0 and val[idx - 1] in (" ", "\t"):
        val = val[:idx]
    return val.strip()


def _get_int(key: str, default: int) -> int:
    val = _strip_inline_comment(os.getenv(key))
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_float(key: str, default: float) -> float:
    val = _strip_inline_comment(os.getenv(key))
    if not val:
        return default
    try:
        return float(val)
    except ValueError:
        return default


@dataclass
class PostgresConfig:
    """PostgreSQL 连接配置。"""
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: _get_int("DB_PORT", 5432))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "stock_analysis"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))
    pool_size: int = field(default_factory=lambda: _get_int("DB_POOL_SIZE", 5))

    @property
    def url(self) -> str:
        return (f"postgresql+psycopg2://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.name}")


@dataclass
class TushareConfig:
    """Tushare API 配置。"""
    token: str = field(default_factory=lambda: _strip_inline_comment(os.getenv("TUSHARE_TOKEN", "")))
    # 留空时由 Tushare SDK 使用官方地址；填写兼容服务的 DataApi 根地址可临时切换。
    api_url: str = field(default_factory=lambda: _strip_inline_comment(os.getenv("TUSHARE_API_URL", "")))
    points: int = field(default_factory=lambda: _get_int("TUSHARE_POINTS", 5000))  # ★积分门控
    requests_per_minute: int = field(default_factory=lambda: _get_int("REQ_PER_MIN", 480))
    requests_per_second: float = field(default_factory=lambda: _get_float("REQ_PER_SEC", 8.0))
    max_retries: int = field(default_factory=lambda: _get_int("MAX_RETRIES", 3))
    retry_interval: float = field(default_factory=lambda: _get_float("RETRY_INTERVAL", 30))
    retry_backoff: float = 2.0


@dataclass
class DataConfig:
    """数据范围配置。"""
    start_date: str = field(default_factory=lambda: _strip_inline_comment(os.getenv("DATA_START_DATE", "20200101")))
    end_date: str = None
    include_bse: bool = field(default_factory=lambda: _get_bool("INCLUDE_BSE", True))
    markets: List[str] = field(default_factory=lambda: ["SSE", "SZSE", "BSE"])

    def get_end_date(self) -> str:
        return self.end_date or datetime.now().strftime("%Y%m%d")


@dataclass
class LogConfig:
    """日志配置。"""
    dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "./logs"))
    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    fmt: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5


class Settings:
    """全局设置：聚合各配置块 + 表名常量（唯一引用源）。"""

    def __init__(self):
        self.db = PostgresConfig()
        self.tushare = TushareConfig()
        self.data = DataConfig()
        self.log = LogConfig()

    # ===== 表名常量（唯一引用源）=====
    # 基础
    TBL_STOCK_BASIC = "stock_basic"
    TBL_TRADE_CALENDAR = "trade_calendar"
    # 行情
    TBL_DAILY_QUOTE = "daily_quote"
    TBL_DAILY_BASIC = "daily_basic"
    TBL_INDEX_DAILY = "index_daily"
    TBL_ADJ_FACTOR = "adj_factor"
    TBL_STK_LIMIT = "stk_limit"          # 涨跌停"价格"
    TBL_SUSPEND = "suspend"
    TBL_STOCK_ST = "stock_st"
    # 板块（东财，6000分）
    TBL_DC_SECTOR_DAILY = "dc_sector_daily"
    TBL_DC_SECTOR_KLINE = "dc_sector_kline"
    TBL_DC_SECTOR_MEMBER = "dc_sector_member"
    # 资金
    TBL_MONEYFLOW = "moneyflow"
    TBL_MONEYFLOW_HSGT = "moneyflow_hsgt"
    # 市场行为
    TBL_LIMIT_LIST = "limit_list"        # 涨跌停"列表"
    TBL_TOP_LIST = "top_list"
    TBL_TOP_INST = "top_inst"
    TBL_BLOCK_TRADE = "block_trade"
    TBL_MARGIN_SUMMARY = "margin_summary"
    # 财务
    TBL_FINA_INDICATOR = "fina_indicator"
    TBL_FORECAST = "forecast"
    TBL_EXPRESS = "express"
    # 系统
    TBL_TASK_FAILURE_LOG = "task_failure_log"


# 全局设置实例
settings = Settings()
