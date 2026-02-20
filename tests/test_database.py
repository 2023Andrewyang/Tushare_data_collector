# -*- coding: utf-8 -*-
"""
数据库模块测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings


class TestMongoDBManager:
    """MongoDB管理器测试"""
    
    def test_connection(self, db_manager):
        """测试数据库连接"""
        assert db_manager.client is not None
        # 测试ping
        result = db_manager.client.admin.command('ping')
        assert result.get('ok') == 1.0
    
    def test_get_database(self, db_manager):
        """测试获取数据库"""
        db = db_manager.db
        assert db is not None
        assert db.name == settings.mongodb.database
    
    def test_get_collection(self, db_manager):
        """测试获取集合"""
        collection = db_manager.get_collection("test_collection")
        assert collection is not None
    
    def test_upsert_one(self, db_manager):
        """测试单条upsert"""
        test_data = {
            "ts_code": "TEST001.SZ",
            "trade_date": "20240101",
            "close": 10.5
        }
        
        result = db_manager.upsert_one(
            "test_collection",
            {"ts_code": "TEST001.SZ", "trade_date": "20240101"},
            test_data
        )
        assert result is True
        
        # 验证数据
        found = db_manager.find_one(
            "test_collection",
            {"ts_code": "TEST001.SZ", "trade_date": "20240101"}
        )
        assert found is not None
        assert found["close"] == 10.5
    
    def test_upsert_many(self, db_manager):
        """测试批量upsert"""
        test_data = [
            {"ts_code": "TEST002.SZ", "trade_date": "20240101", "close": 11.0},
            {"ts_code": "TEST002.SZ", "trade_date": "20240102", "close": 11.5},
            {"ts_code": "TEST002.SZ", "trade_date": "20240103", "close": 12.0},
        ]
        
        result = db_manager.upsert_many(
            "test_collection",
            test_data,
            ["ts_code", "trade_date"]
        )
        
        assert result["success"] >= 0
    
    def test_find_many(self, db_manager):
        """测试批量查询"""
        results = db_manager.find_many(
            "test_collection",
            {"ts_code": "TEST002.SZ"},
            sort=[("trade_date", 1)]
        )
        
        assert isinstance(results, list)
    
    def test_count(self, db_manager):
        """测试计数"""
        count = db_manager.count("test_collection", {"ts_code": "TEST002.SZ"})
        assert isinstance(count, int)
        assert count >= 0
    
    def test_distinct(self, db_manager):
        """测试去重查询"""
        dates = db_manager.distinct("test_collection", "trade_date")
        assert isinstance(dates, list)
    
    def test_get_max_value(self, db_manager):
        """测试获取最大值"""
        max_date = db_manager.get_max_value(
            "test_collection",
            "trade_date",
            {"ts_code": "TEST002.SZ"}
        )
        # 可能为None或字符串
        assert max_date is None or isinstance(max_date, str)
    
    def test_cleanup(self, db_manager):
        """清理测试数据"""
        db_manager.delete_many("test_collection", {"ts_code": {"$regex": "^TEST"}})
        db_manager.drop_collection("test_collection")


class TestMongoDBSingleton:
    """测试单例模式"""
    
    def test_singleton(self):
        """测试单例模式"""
        from core.database import get_db_manager
        
        manager1 = get_db_manager()
        manager2 = get_db_manager()
        
        assert manager1 is manager2

