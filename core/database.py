# -*- coding: utf-8 -*-
"""
MongoDB数据库连接管理模块
"""
import logging
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, BulkWriteError

from config.settings import settings

logger = logging.getLogger(__name__)


class MongoDBManager:
    """MongoDB数据库管理器"""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._connect()
    
    def _connect(self):
        """建立数据库连接"""
        try:
            self._client = MongoClient(
                settings.mongodb.uri,
                maxPoolSize=50,
                minPoolSize=5,
                serverSelectionTimeoutMS=5000
            )
            # 测试连接
            self._client.admin.command('ping')
            logger.info(f"MongoDB连接成功: {settings.mongodb.host}:{settings.mongodb.port}")
        except Exception as e:
            logger.error(f"MongoDB连接失败: {e}")
            raise
    
    @property
    def client(self) -> MongoClient:
        """获取MongoDB客户端"""
        return self._client
    
    @property
    def db(self) -> Database:
        """获取数据库实例"""
        return self._client[settings.mongodb.database]
    
    def get_collection(self, name: str) -> Collection:
        """获取集合"""
        return self.db[name]
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            logger.info("MongoDB连接已关闭")
    
    def ensure_indexes(self):
        """创建所有必要的索引"""
        logger.info("开始创建数据库索引...")
        
        # 股票列表索引
        self._create_index(
            settings.COLLECTION_STOCK_LIST,
            [("ts_code", ASCENDING)],
            unique=True
        )
        
        # 交易日历索引
        self._create_index(
            settings.COLLECTION_TRADE_CALENDAR,
            [("exchange", ASCENDING), ("cal_date", ASCENDING)],
            unique=True
        )
        self._create_index(
            settings.COLLECTION_TRADE_CALENDAR,
            [("cal_date", ASCENDING)]
        )
        
        # 日K线索引
        self._create_index(
            settings.COLLECTION_DAILY_QUOTE,
            [("ts_code", ASCENDING), ("trade_date", ASCENDING)],
            unique=True
        )
        self._create_index(
            settings.COLLECTION_DAILY_QUOTE,
            [("trade_date", ASCENDING)]
        )
        
        # 复权因子索引
        self._create_index(
            settings.COLLECTION_ADJ_FACTOR,
            [("ts_code", ASCENDING), ("trade_date", ASCENDING)],
            unique=True
        )
        self._create_index(
            settings.COLLECTION_ADJ_FACTOR,
            [("trade_date", ASCENDING)]
        )
        
        # 每日指标索引
        self._create_index(
            settings.COLLECTION_DAILY_BASIC,
            [("ts_code", ASCENDING), ("trade_date", ASCENDING)],
            unique=True
        )
        self._create_index(
            settings.COLLECTION_DAILY_BASIC,
            [("trade_date", ASCENDING)]
        )
        
        # 涨跌停价格索引
        self._create_index(
            settings.COLLECTION_STK_LIMIT,
            [("ts_code", ASCENDING), ("trade_date", ASCENDING)],
            unique=True
        )
        self._create_index(
            settings.COLLECTION_STK_LIMIT,
            [("trade_date", ASCENDING)]
        )
        
        # 停复牌索引
        self._create_index(
            settings.COLLECTION_SUSPEND,
            [("ts_code", ASCENDING), ("trade_date", ASCENDING)],
            unique=True
        )
        
        # 财务指标索引
        self._create_index(
            settings.COLLECTION_FINA_INDICATOR,
            [("ts_code", ASCENDING), ("end_date", ASCENDING)],
            unique=True
        )
        self._create_index(
            settings.COLLECTION_FINA_INDICATOR,
            [("end_date", ASCENDING)]
        )
        self._create_index(
            settings.COLLECTION_FINA_INDICATOR,
            [("ann_date", ASCENDING)]
        )
        
        # ST股票列表索引
        self._create_index(
            settings.COLLECTION_STOCK_ST,
            [("ts_code", ASCENDING), ("trade_date", ASCENDING)],
            unique=True
        )
        self._create_index(
            settings.COLLECTION_STOCK_ST,
            [("trade_date", ASCENDING)]
        )
        
        # 同步进度索引
        self._create_index(
            settings.COLLECTION_SYNC_PROGRESS,
            [("task_name", ASCENDING)],
            unique=True
        )
        
        # 失败任务索引
        self._create_index(
            settings.COLLECTION_TASK_FAILURES,
            [("task_name", ASCENDING), ("ts_code", ASCENDING), ("trade_date", ASCENDING)]
        )
        self._create_index(
            settings.COLLECTION_TASK_FAILURES,
            [("status", ASCENDING)]
        )
        
        logger.info("数据库索引创建完成")
    
    def _create_index(self, collection_name: str, keys: List[tuple], 
                      unique: bool = False, **kwargs):
        """创建单个索引"""
        try:
            collection = self.get_collection(collection_name)
            index_name = collection.create_index(keys, unique=unique, **kwargs)
            logger.debug(f"索引创建成功: {collection_name}.{index_name}")
        except Exception as e:
            logger.warning(f"索引创建失败: {collection_name} - {e}")
    
    def upsert_one(self, collection_name: str, filter_dict: Dict, 
                   data: Dict) -> bool:
        """更新或插入单条记录"""
        try:
            collection = self.get_collection(collection_name)
            result = collection.update_one(
                filter_dict,
                {"$set": data},
                upsert=True
            )
            return True
        except Exception as e:
            logger.error(f"Upsert失败: {collection_name} - {e}")
            return False
    
    def upsert_many(self, collection_name: str, data_list: List[Dict], 
                    key_fields: List[str]) -> Dict[str, int]:
        """批量更新或插入记录
        
        Args:
            collection_name: 集合名称
            data_list: 数据列表
            key_fields: 用于匹配的键字段列表
            
        Returns:
            包含成功和失败数量的字典
        """
        if not data_list:
            return {"success": 0, "failed": 0}
        
        collection = self.get_collection(collection_name)
        success_count = 0
        failed_count = 0
        
        from pymongo import UpdateOne
        
        operations = []
        for data in data_list:
            filter_dict = {k: data[k] for k in key_fields if k in data}
            operations.append(
                UpdateOne(filter_dict, {"$set": data}, upsert=True)
            )
        
        try:
            if operations:
                result = collection.bulk_write(operations, ordered=False)
                success_count = result.upserted_count + result.modified_count + result.matched_count
        except BulkWriteError as e:
            # 部分成功的情况
            success_count = e.details.get('nUpserted', 0) + e.details.get('nModified', 0)
            failed_count = len(e.details.get('writeErrors', []))
            logger.warning(f"批量写入部分失败: 成功 {success_count}, 失败 {failed_count}")
        except Exception as e:
            logger.error(f"批量写入失败: {e}")
            failed_count = len(data_list)
        
        return {"success": success_count, "failed": failed_count}
    
    def insert_many_ignore_duplicates(self, collection_name: str, 
                                       data_list: List[Dict]) -> Dict[str, int]:
        """批量插入，忽略重复记录
        
        Args:
            collection_name: 集合名称
            data_list: 数据列表
            
        Returns:
            包含插入数量的字典
        """
        if not data_list:
            return {"inserted": 0, "duplicates": 0}
        
        collection = self.get_collection(collection_name)
        
        try:
            result = collection.insert_many(data_list, ordered=False)
            return {"inserted": len(result.inserted_ids), "duplicates": 0}
        except BulkWriteError as e:
            inserted = e.details.get('nInserted', 0)
            duplicates = len([err for err in e.details.get('writeErrors', []) 
                            if err.get('code') == 11000])
            return {"inserted": inserted, "duplicates": duplicates}
        except Exception as e:
            logger.error(f"批量插入失败: {e}")
            return {"inserted": 0, "duplicates": 0}
    
    def find_one(self, collection_name: str, filter_dict: Dict) -> Optional[Dict]:
        """查询单条记录"""
        collection = self.get_collection(collection_name)
        return collection.find_one(filter_dict)
    
    def find_many(self, collection_name: str, filter_dict: Dict = None,
                  projection: Dict = None, sort: List[tuple] = None,
                  limit: int = 0) -> List[Dict]:
        """查询多条记录"""
        collection = self.get_collection(collection_name)
        cursor = collection.find(filter_dict or {}, projection)
        
        if sort:
            cursor = cursor.sort(sort)
        if limit > 0:
            cursor = cursor.limit(limit)
        
        return list(cursor)
    
    def count(self, collection_name: str, filter_dict: Dict = None) -> int:
        """统计记录数"""
        collection = self.get_collection(collection_name)
        return collection.count_documents(filter_dict or {})
    
    def distinct(self, collection_name: str, field: str, 
                 filter_dict: Dict = None) -> List:
        """获取字段的唯一值列表"""
        collection = self.get_collection(collection_name)
        return collection.distinct(field, filter_dict or {})
    
    def get_max_value(self, collection_name: str, field: str,
                      filter_dict: Dict = None) -> Any:
        """获取字段的最大值"""
        collection = self.get_collection(collection_name)
        result = collection.find_one(
            filter_dict or {},
            sort=[(field, DESCENDING)]
        )
        return result.get(field) if result else None
    
    def get_min_value(self, collection_name: str, field: str,
                      filter_dict: Dict = None) -> Any:
        """获取字段的最小值"""
        collection = self.get_collection(collection_name)
        result = collection.find_one(
            filter_dict or {},
            sort=[(field, ASCENDING)]
        )
        return result.get(field) if result else None
    
    def delete_many(self, collection_name: str, filter_dict: Dict) -> int:
        """删除多条记录"""
        collection = self.get_collection(collection_name)
        result = collection.delete_many(filter_dict)
        return result.deleted_count
    
    def drop_collection(self, collection_name: str):
        """删除集合"""
        self.db.drop_collection(collection_name)
        logger.info(f"集合已删除: {collection_name}")


# 便捷函数
def get_db_manager() -> MongoDBManager:
    """获取数据库管理器实例"""
    return MongoDBManager()

