# -*- coding: utf-8 -*-
"""
全局配置文件
"""
from dataclasses import dataclass, field
from typing import List
from datetime import datetime


@dataclass
class MongoDBConfig:
    """MongoDB配置"""
    host: str = "localhost"
    port: int = 27017
    database: str = "Tushare_Data"
    username: str = None
    password: str = None
    auth_source: str = "admin"
    
    @property
    def uri(self) -> str:
        """生成MongoDB连接URI"""
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?authSource={self.auth_source}"
        return f"mongodb://{self.host}:{self.port}"


@dataclass
class TushareConfig:
    """Tushare API配置"""
    # 速率限制 - 5000积分用户
    max_concurrent: int = 5          # 最大并发数
    requests_per_second: float = 8.0  # 每秒请求数
    requests_per_minute: int = 480    # 每分钟请求数（留余量）
    
    # 重试配置
    max_retries: int = 3              # 最大重试次数
    retry_delay: float = 2.0          # 重试延迟（秒）
    retry_backoff: float = 2.0        # 重试退避倍数
    
    # 批量配置
    batch_size: int = 100             # 每批股票数量


@dataclass
class DataConfig:
    """数据范围配置"""
    start_date: str = "20150101"      # 数据起始日期
    end_date: str = None              # 数据结束日期，None表示当天
    
    # 股票类型
    include_delisted: bool = True     # 包含已退市股票
    include_bse: bool = True          # 包含北交所股票
    
    # 市场列表
    markets: List[str] = field(default_factory=lambda: ["SSE", "SZSE", "BSE"])
    
    def get_end_date(self) -> str:
        """获取结束日期，默认为当天"""
        if self.end_date:
            return self.end_date
        return datetime.now().strftime("%Y%m%d")


@dataclass
class LogConfig:
    """日志配置"""
    log_dir: str = "logs"
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


class Settings:
    """全局设置类"""
    
    def __init__(self):
        self.mongodb = MongoDBConfig()
        self.tushare = TushareConfig()
        self.data = DataConfig()
        self.log = LogConfig()
    
    # 集合名称常量 - 基础数据
    COLLECTION_STOCK_LIST = "stock_list"
    COLLECTION_TRADE_CALENDAR = "trade_calendar"
    
    # 集合名称常量 - 行情数据
    COLLECTION_DAILY_QUOTE = "daily_quote"
    COLLECTION_ADJ_FACTOR = "adj_factor"
    COLLECTION_DAILY_BASIC = "daily_basic"
    COLLECTION_STK_LIMIT = "stk_limit"
    COLLECTION_SUSPEND = "suspend"
    
    # 集合名称常量 - 财务数据
    COLLECTION_FINA_INDICATOR = "fina_indicator"
    
    # 集合名称常量 - 参考数据
    COLLECTION_STOCK_ST = "stock_st"
    
    # 系统集合
    COLLECTION_SYNC_PROGRESS = "_sync_progress"
    COLLECTION_TASK_FAILURES = "_task_failures"


# 全局设置实例
settings = Settings()

