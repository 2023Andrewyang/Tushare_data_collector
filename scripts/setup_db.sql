-- stock-data-hub 建库脚本
-- 用法: psql -U postgres -f scripts/setup_db.sql
-- 建表交给: python main.py init --schema-only

CREATE DATABASE stock_analysis ENCODING 'UTF8';
