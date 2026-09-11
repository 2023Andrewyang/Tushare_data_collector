# -*- coding: utf-8 -*-
"""PostgreSQL 数据库管理器（SQLAlchemy 2.0 Core）。

对外提供 90 文档第二节定义的固定 API：
create_all_tables / drop_all_tables / healthcheck / bulk_upsert /
fetch_df / fetch_all / fetch_one / count / get_max / get_min / execute。
所有采集器、失败处理、命令层都通过本层访问数据库。
"""
import logging

import pandas as pd
from sqlalchemy import create_engine, text, Table
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.settings import settings
from models.schema import metadata, TABLES

logger = logging.getLogger(__name__)

BATCH_SIZE = 5000


class PostgresManager:
    """PostgreSQL 单例管理器。"""

    _instance = None
    _engine: Engine = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._engine is None:
            self._connect()

    def _connect(self):
        self._engine = create_engine(
            settings.db.url,
            pool_size=settings.db.pool_size,
            max_overflow=10,
            pool_pre_ping=True,
            future=True,
        )
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"PostgreSQL 连接成功: "
                    f"{settings.db.host}:{settings.db.port}/{settings.db.name}")

    @property
    def engine(self) -> Engine:
        return self._engine

    # ---------- 建表 / 维护 ----------
    def create_all_tables(self) -> None:
        metadata.create_all(self._engine)
        logger.info("建表完成（IF NOT EXISTS）")

    def drop_all_tables(self) -> None:
        metadata.drop_all(self._engine)
        logger.warning("已删除所有表")

    def healthcheck(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"healthcheck 失败: {e}")
            return False

    # ---------- 写入（核心）----------
    @staticmethod
    def _dedupe(rows: list, key_fields: list) -> list:
        """按主键去重（同键保留最后一条）。

        ON CONFLICT DO UPDATE 在同一批数据里遇到重复键会直接报
        CardinalityViolation（如 stock_basic 快照跨 list_status 拉取后
        出现重复 ts_code），去重可让写入对上游重复数据免疫。
        """
        if not key_fields:
            return rows
        seen = {}
        for r in rows:
            seen[tuple(r.get(k) for k in key_fields)] = r
        return list(seen.values())

    def bulk_upsert(self, table_name: str, rows: list, key_fields: list,
                    update_on_conflict: bool = False) -> dict:
        """批量写入，基于主键去重。

        update_on_conflict=False -> ON CONFLICT DO NOTHING（幂等，默认）
        update_on_conflict=True  -> ON CONFLICT DO UPDATE（backfill 覆盖）
        返回 {"affected": int, "received": int}。
        """
        if not rows:
            return {"affected": 0, "received": 0}

        table: Table = TABLES[table_name]
        valid_cols = set(c.name for c in table.columns)
        clean_rows = [{k: v for k, v in r.items() if k in valid_cols} for r in rows]
        clean_rows = self._dedupe(clean_rows, key_fields)   # 防 CardinalityViolation

        affected = 0
        with self._engine.begin() as conn:   # 单事务，分批
            for i in range(0, len(clean_rows), BATCH_SIZE):
                batch = clean_rows[i:i + BATCH_SIZE]
                stmt = pg_insert(table).values(batch)
                if update_on_conflict:
                    update_cols = {c.name: stmt.excluded[c.name]
                                   for c in table.columns
                                   if c.name not in key_fields and c.name != "created_at"}
                    if update_cols:
                        stmt = stmt.on_conflict_do_update(
                            index_elements=key_fields, set_=update_cols)
                    else:
                        stmt = stmt.on_conflict_do_nothing(index_elements=key_fields)
                else:
                    stmt = stmt.on_conflict_do_nothing(index_elements=key_fields)
                result = conn.execute(stmt)
                affected += result.rowcount if result.rowcount and result.rowcount > 0 else 0

        logger.info(f"[{table_name}] 写入 received={len(clean_rows)} affected={affected}")
        return {"affected": affected, "received": len(clean_rows)}

    def bulk_upsert_and_complete_checkpoint(
            self, table_name: str, rows: list, key_fields: list,
            checkpoint_id: int, update_on_conflict: bool = False) -> dict:
        """在同一事务中写入业务数据并结束工作项。

        0 行的响应记为 'empty' 而非 'succeeded'：代理在并发压力下会偶发地
        对整日返回空结果，若直接记成功就会留下永久空洞；'empty' 在工作项
        领取时（status <> 'succeeded'）会被下次运行自动重试。
        """
        table: Table = TABLES[table_name]
        valid_cols = set(c.name for c in table.columns)
        clean_rows = [{k: v for k, v in r.items() if k in valid_cols} for r in rows]
        clean_rows = self._dedupe(clean_rows, key_fields)   # 防 CardinalityViolation
        affected = 0
        with self._engine.begin() as conn:
            for i in range(0, len(clean_rows), BATCH_SIZE):
                batch = clean_rows[i:i + BATCH_SIZE]
                stmt = pg_insert(table).values(batch)
                if update_on_conflict:
                    update_cols = {c.name: stmt.excluded[c.name]
                                   for c in table.columns
                                   if c.name not in key_fields and c.name != "created_at"}
                    stmt = (stmt.on_conflict_do_update(index_elements=key_fields,
                                                       set_=update_cols)
                            if update_cols else
                            stmt.on_conflict_do_nothing(index_elements=key_fields))
                else:
                    stmt = stmt.on_conflict_do_nothing(index_elements=key_fields)
                result = conn.execute(stmt)
                affected += result.rowcount if result.rowcount and result.rowcount > 0 else 0
            status = "succeeded" if clean_rows else "empty"
            conn.execute(text(
                "UPDATE collection_checkpoint SET status=:status, "
                "received_rows=:received, affected_rows=:affected, last_error=NULL, "
                "completed_at=now(), updated_at=now() WHERE id=:id"),
                {"id": checkpoint_id, "status": status,
                 "received": len(clean_rows), "affected": affected})
        logger.info(f"[{table_name}] 写入 received={len(clean_rows)} "
                    f"affected={affected} status={status}")
        return {"affected": affected, "received": len(clean_rows)}

    # ---------- 查询 ----------
    def fetch_df(self, sql: str, params: dict = None) -> pd.DataFrame:
        with self._engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def fetch_all(self, sql: str, params: dict = None) -> list:
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params or {}).mappings().all()
            return [dict(r) for r in rows]

    def fetch_one(self, sql: str, params: dict = None):
        with self._engine.connect() as conn:
            row = conn.execute(text(sql), params or {}).mappings().first()
            return dict(row) if row else None

    def count(self, table_name: str, where: str = None, params: dict = None) -> int:
        sql = f"SELECT COUNT(*) AS c FROM {table_name}"
        if where:
            sql += f" WHERE {where}"
        return self.fetch_one(sql, params)["c"]

    def get_max(self, table_name: str, column: str, where: str = None, params: dict = None):
        sql = f"SELECT MAX({column}) AS m FROM {table_name}"
        if where:
            sql += f" WHERE {where}"
        return self.fetch_one(sql, params)["m"]

    def get_min(self, table_name: str, column: str, where: str = None, params: dict = None):
        sql = f"SELECT MIN({column}) AS m FROM {table_name}"
        if where:
            sql += f" WHERE {where}"
        return self.fetch_one(sql, params)["m"]

    def execute(self, sql: str, params: dict = None) -> int:
        with self._engine.begin() as conn:
            return conn.execute(text(sql), params or {}).rowcount


def get_db_manager() -> PostgresManager:
    """获取数据库管理器实例（单例）。"""
    return PostgresManager()
