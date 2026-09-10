# stock-data-hub

基于 Tushare Pro 的 A 股行情数据中台。统一 CLI 入口，将结构化行情、财务、板块数据采集到 **PostgreSQL**，为下游分析服务提供稳定的数据基础。

## 功能特性

- **统一 CLI 入口**：`python main.py {init|update|retry|backfill|status}`，无定时任务，手动触发。
- **行级幂等写入**：基于主键 `ON CONFLICT DO NOTHING`，重复写入不会产生重复数据。
- **持久化断点续传**：每个日期、股票、报告期或快照工作项都会记录状态；中断后重跑时，已成功项会跳过且不会再次请求 Tushare。
- **实时进度与 ETA**：日志展示当前模块、当前日期/工作项、`0.00%` 至 `100.00%` 的完成比例和预估剩余时间。
- **失败记录与一键重试**：采集失败写入 `task_failure_log`，Token 恢复后 `retry` 一键重跑。
- **积分门控**：`.env` 中 `TUSHARE_POINTS` 控制高分接口是否采集，积分不足自动跳过、不报错。
- **低频接口自动检测**：日历、股票列表、板块成分股、财务数据在 `update` 时按规则判断是否需要更新。
- **非交易日跳过**：`update` 按日历逐日执行，非交易日自动跳过。

## 数据表清单（21 张业务表 + 2 张系统表）

| 类别 | 表 |
|------|----|
| 基础 | `stock_basic`、`trade_calendar` |
| 行情 | `daily_quote`、`daily_basic`、`index_daily`、`adj_factor`、`stk_limit`、`suspend`、`stock_st` |
| 板块（东财，6000分） | `dc_sector_daily`、`dc_sector_kline`、`dc_sector_member` |
| 资金 | `moneyflow`、`moneyflow_hsgt` |
| 市场行为 | `limit_list`、`top_list`、`top_inst`、`block_trade`、`margin_summary` |
| 财务 | `fina_indicator`、`forecast`、`express` |
| 系统 | `task_failure_log`、`collection_checkpoint` |

> 注意：`stk_limit`（涨跌停"价格"）与 `limit_list`（涨跌停"列表/名单"）是两个不同的接口与表。

## 快速开始

### 1. 安装依赖

Conda：

```bash
conda env create -f environment.yml
conda activate tushare_data
```

或 pip：

```bash
pip install -r requirements.txt
```

### 2. 安装并启动 PostgreSQL（15+）

Windows 任选其一：

- 官方安装包：https://www.postgresql.org/download/windows/
- `winget install PostgreSQL.PostgreSQL.16`
- Docker：`docker run --name pg -e POSTGRES_PASSWORD=yourpwd -p 5432:5432 -d postgres:16`

建库：

```bash
psql -U postgres -f scripts/setup_db.sql
# 或手动: CREATE DATABASE stock_analysis ENCODING 'UTF8';
```

### 3. 配置 `.env`

复制 `.env.example` 为 `.env` 并填写：

```ini
TUSHARE_TOKEN=你的Token
# 留空使用官方 Tushare；临时切换到兼容服务时填写其 DataApi 根地址
TUSHARE_API_URL=
TUSHARE_POINTS=5000          # >=6000 才采集东财板块接口

DB_HOST=localhost
DB_PORT=5432
DB_NAME=stock_analysis
DB_USER=postgres
DB_PASSWORD=你的密码

DATA_START_DATE=20200101
LOG_LEVEL=INFO
MAX_RETRIES=3
RETRY_INTERVAL=30
```

> `.env` 已被 `.gitignore` 忽略，不会提交。Token 获取：https://tushare.pro/user/token

### 4. 建表与采集

```bash
# 仅建表（首次部署）
python main.py init --schema-only

# 全量采集指定区间
python main.py init --start 20200101 --end 20260530

# 先试跑一个采集器验证链路
python main.py init --collector daily_quote --start 20240102 --end 20240102
```

> 首次执行采集器时，程序也会自动创建 `collection_checkpoint` 表，以兼容已有数据库。

## 命令用法

```bash
# 初始化（建表 + 全量采集；默认跳过已成功工作项）
python main.py init [--start YYYYMMDD] [--end YYYYMMDD] [--schema-only] [--collector X]

# 增量更新（日频逐日 + 低频自动检测；默认跳过已成功工作项）
python main.py update [--date YYYYMMDD] [--start YYYYMMDD --end YYYYMMDD] [--collector X]

# 重试失败任务（Token 恢复后直接跑此命令）
python main.py retry [--collector X] [--date D] [--start --end]

# 强制补录（默认重新请求并覆盖写，用于数据修复）
python main.py backfill --start YYYYMMDD --end YYYYMMDD [--collector X]

# 恢复被中断的补录：跳过该范围中已成功的工作项
python main.py backfill --start YYYYMMDD --end YYYYMMDD [--collector X] --resume

# 查看状态
python main.py status                 # 各表行数 + 最新日期
python main.py status --date 20260530 # 当日各接口记录数（对比阈值）
python main.py status --failures      # 失败任务汇总
```

## 进度日志与断点续传

每个采集工作项都会记录在 `collection_checkpoint`：成功为 `succeeded`，普通异常为 `failed`，按 **Ctrl+C** 中断时为 `interrupted`。业务数据写入和将工作项标记为成功在同一个数据库事务中完成，因此只有完整落库的工作项才会在后续运行时跳过。

运行日志示例：

```text
[进度] 模块=daily_quote | 当前日期=20240910 | 进度=37.50% (15/40) | 预计剩余=00:02:18
[daily_quote] date=20240909 已完成，断点续传跳过
```

- 首个工作项完成前，ETA 显示为“计算中”；之后按当前模块已完成工作项的平均耗时估算。
- 进度按工作项计数，而不是按写入行数计数；合法的空数据响应同样会被标记为完成，避免重复请求。
- `init` 和 `update` 默认启用断点续传。中断后直接使用相同参数重新运行即可。
- `backfill` 默认保持“强制补录”语义，会重新请求并覆盖写；只有显式传入 `--resume` 时才跳过已完成项。
- 已成功的工作项仍由业务表的主键幂等性兜底；checkpoint 用于避免重复网络请求，二者互补。

## 积分门控（TUSHARE_POINTS）

每个采集器声明 `REQUIRED_POINTS`，框架执行前比较 `settings.tushare.points >= REQUIRED_POINTS`，不足则跳过并打印 WARNING，不算失败。改积分只需改 `.env` 一行。

| 积分档 | 代表接口 |
|--------|---------|
| 120+ | stock_basic, trade_cal, daily, adj_factor, stk_limit, suspend_d, index_daily |
| 2000+ | daily_basic, moneyflow, moneyflow_hsgt, limit_list, top_list, block_trade, margin, forecast, express |
| 3000+ | stock_st |
| 5000+ | fina_indicator_vip |
| 6000+ | dc_index, dc_daily, dc_member（东方财富板块） |

## 项目结构

```
Tushare_Data/
├── main.py                  # CLI 统一入口
├── config/settings.py       # 配置 + 表名常量
├── core/
│   ├── checkpoint.py        # 工作项状态与断点续传
│   ├── database.py          # PostgresManager（SQLAlchemy Core）
│   ├── tushare_client.py    # Tushare 客户端（限频 + 重试）
│   ├── failure_handler.py   # 失败记录与重试
│   ├── logging_setup.py     # 日志（按日期滚动）
│   └── progress.py          # 模块进度与 ETA 日志
├── models/schema.py         # 全部表定义（DDL 唯一真源）
├── collectors/              # 21 个采集器 + 注册表
├── scheduler/update_checker.py  # 低频接口更新检测
├── commands/                # 5 个命令实现
├── scripts/setup_db.sql     # 建库脚本
├── tests/                   # 单元 + db + integration 测试
├── .env / .env.example
├── requirements.txt / environment.yml
└── README.md
```

## 运行测试

```bash
# 单元测试（不连库、不联网，默认）
pytest -q

# 含数据库测试（需本地 PostgreSQL）
pytest -m "db" -q

# 含联网集成测试（需 Tushare Token）
pytest -m "integration" -q
```

> 标记说明：`db` 需要本地 PostgreSQL；`integration` 需要 Token + 联网，默认 `addopts = -m "not integration"` 跳过。

## 常见问题

**PostgreSQL 连接失败**：确认服务已启动、`.env` 中 `DB_*` 正确、`stock_analysis` 库已建。

**积分不足跳过**：东财 `dc_*` 等高分接口在 `TUSHARE_POINTS` 不达标时自动跳过，属正常行为，调高 `.env` 中积分后即参与采集。

**Token 失效导致大量失败**：换好 Token 后运行 `python main.py retry`，自动重跑所有 pending 失败任务。

**采集被 Ctrl+C 中断**：无需从头重复请求。对 `init` 或 `update`，使用相同参数再次执行即可跳过已成功工作项并继续未完成项。对于强制补录，重新运行时加 `--resume`。

**幂等与断点续传的区别**：幂等写入保证重复数据行不会被插入；断点续传通过 `collection_checkpoint` 跳过已成功工作项，从而避免重复发起 API 请求。若需要强制重新拉取并覆盖数据，请使用不带 `--resume` 的 `backfill`。

## License

MIT License
