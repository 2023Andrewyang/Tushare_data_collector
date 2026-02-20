# Tushare Data Collector

基于Tushare Pro的A股数据采集系统，将数据存储到MongoDB，支持全量同步、增量更新、断点续传和失败重试。

## 📋 功能特性

- ✅ **全量数据同步** - 支持从2015年开始的历史数据采集
- ✅ **增量更新** - 每日盘后自动更新当日数据
- ✅ **断点续传** - 中断后可从上次位置继续
- ✅ **失败记录与重试** - 自动记录失败任务，支持手动重试
- ✅ **并发控制** - 自动控制请求速率，避免超过API限制
- ✅ **数据完整性检查** - 检查数据覆盖率和缺失情况

## 📊 数据内容

### 行情数据（每日更新）

| 数据类型 | 集合名称 | 说明 |
|---------|---------|------|
| 股票列表 | `stock_list` | 所有A股代码、名称、行业等 |
| 交易日历 | `trade_calendar` | 交易日/节假日信息 |
| 日K线 | `daily_quote` | 开高低收、成交量等 |
| 复权因子 | `adj_factor` | 用于计算前/后复权价格 |
| 每日指标 | `daily_basic` | PE、PB、市值、换手率等 |
| 涨跌停价格 | `stk_limit` | 每日涨跌停限价 |
| 停复牌 | `suspend` | 停复牌信息 |

### 财务数据（季度更新）

| 数据类型 | 集合名称 | 说明 |
|---------|---------|------|
| 财务指标 | `fina_indicator` | ROE、ROA、毛利率、成长率等核心指标 |

**财务指标包含的核心字段：**
- 每股指标：EPS、BPS、每股现金流等
- 盈利能力：ROE、ROA、毛利率、净利率等
- 成长能力：营收增长率、净利润增长率等
- 偿债能力：流动比率、速动比率、资产负债率等
- 运营效率：应收账款周转率、存货周转率等

## 🚀 快速开始

### 1. 环境配置

使用Conda创建环境：

```bash
cd Tushare_Data
conda env create -f environment.yml
conda activate tushare_data
```

或使用pip：

```bash
pip install -r requirements.txt
```

### 2. 配置Tushare Token

在项目根目录创建 `.env` 文件，写入你的 Token：

```bash
TUSHARE_TOKEN=你的Tushare Token
```

> Token获取：https://tushare.pro/user/token
> 
> ⚠️ `.env` 文件已被 `.gitignore` 忽略，不会提交到仓库，请妥善保管。

### 3. 确保MongoDB运行

```bash
# 检查MongoDB状态
mongod --version

# 如果未运行，启动MongoDB
mongod --dbpath /your/data/path
```

### 4. 首次全量同步

```bash
# 运行全量同步（从2015年开始）
python scripts/init_full_sync.py

# 或指定日期范围
python scripts/init_full_sync.py --start-date 20200101 --end-date 20241231

# 只同步特定数据
python scripts/init_full_sync.py --collectors daily_quote adj_factor
```

### 5. 每日增量更新

```bash
# 更新最新交易日数据
python scripts/daily_update.py

# 更新指定日期
python scripts/daily_update.py --date 20240102

# 批量补充历史数据
python scripts/daily_update.py --batch 20240101 20240131
```

### 6. 检查数据状态

```bash
# 查看数据统计
python scripts/check_status.py stats

# 检查数据覆盖率
python scripts/check_status.py coverage

# 检查最近数据
python scripts/check_status.py recent

# 查看所有状态
python scripts/check_status.py all
```

### 7. 处理失败任务

```bash
# 查看失败任务汇总
python scripts/retry_failures.py summary

# 列出失败任务
python scripts/retry_failures.py list --verbose

# 重试所有失败任务
python scripts/retry_failures.py retry --all

# 重试指定任务类型
python scripts/retry_failures.py retry --task daily_quote

# 重试指定日期
python scripts/retry_failures.py retry --date 20240102
```

## 📁 项目结构

```
Tushare_Data/
├── config/                     # 配置模块
│   ├── settings.py             # 全局配置
│   └── tushare_token.py        # Token配置（从.env读取）
├── core/                       # 核心模块
│   ├── database.py             # MongoDB管理
│   ├── tushare_client.py       # Tushare客户端（含速率限制）
│   ├── task_manager.py         # 任务管理（断点续传）
│   └── failure_handler.py      # 失败处理
├── collectors/                 # 采集器模块
│   ├── base_collector.py       # 采集器基类
│   ├── stock_list.py           # 股票列表
│   ├── trade_calendar.py       # 交易日历
│   ├── daily_quote.py          # 日K线
│   ├── adj_factor.py           # 复权因子
│   ├── daily_basic.py          # 每日指标
│   ├── limit_price.py          # 涨跌停价格
│   └── suspend.py              # 停复牌
├── scripts/                    # 运行脚本
│   ├── init_full_sync.py       # 全量同步
│   ├── daily_update.py         # 增量更新
│   ├── retry_failures.py       # 失败重试
│   └── check_status.py         # 状态检查
├── tests/                      # 测试文件
│   ├── test_database.py
│   ├── test_tushare_client.py
│   ├── test_task_manager.py
│   ├── test_failure_handler.py
│   └── test_collectors.py
├── logs/                       # 日志目录
├── .env                        # 环境变量（需创建，存放Token）
├── .gitignore                  # Git忽略规则
├── environment.yml             # Conda环境
├── requirements.txt            # pip依赖
└── README.md                   # 说明文档
```

## ⚙️ 配置说明

### MongoDB配置

修改 `config/settings.py` 中的 `MongoDBConfig`：

```python
@dataclass
class MongoDBConfig:
    host: str = "localhost"
    port: int = 27017
    database: str = "Tushare_Data"
    username: str = None        # 如需认证
    password: str = None
```

### 数据范围配置

```python
@dataclass
class DataConfig:
    start_date: str = "20150101"    # 数据起始日期
    include_delisted: bool = True   # 包含退市股票
    include_bse: bool = True        # 包含北交所
```

### 速率限制配置

```python
@dataclass
class TushareConfig:
    max_concurrent: int = 5          # 最大并发
    requests_per_second: float = 8.0 # 每秒请求数
    max_retries: int = 3             # 最大重试次数
```

## 🧪 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_database.py -v

# 运行特定测试类
pytest tests/test_collectors.py::TestDailyQuoteCollector -v
```

> ⚠️ 部分测试需要配置有效的Tushare Token才能运行

## 📈 使用示例

### Python代码中使用

```python
from core.database import get_db_manager
from collectors.daily_quote import DailyQuoteCollector
import pandas as pd

# 获取数据库管理器
db = get_db_manager()

# 查询股票日K线数据
data = db.find_many(
    "daily_quote",
    {"ts_code": "000001.SZ", "trade_date": {"$gte": "20240101"}},
    sort=[("trade_date", 1)]
)
df = pd.DataFrame(data)
print(df)

# 使用采集器获取数据
collector = DailyQuoteCollector()
df = collector.get_stock_daily("000001.SZ", "20240101", "20240131")
print(df)
```

### 获取复权价格

```python
from collectors.adj_factor import AdjFactorCollector

collector = AdjFactorCollector()

# 获取前复权价格
adj_price = collector.calculate_adjusted_price(
    ts_code="000001.SZ",
    trade_date="20200101",
    price=10.5,
    adj_type="qfq"  # 前复权
)
```

## ❗ 常见问题

### 1. Token错误

```
ValueError: 请先在 config/tushare_token.py 中配置您的Tushare Token
```

**解决**：在项目根目录创建 `.env` 文件，填入 `TUSHARE_TOKEN=你的Token`。

### 2. MongoDB连接失败

```
pymongo.errors.ServerSelectionTimeoutError
```

**解决**：确保MongoDB服务已启动，端口配置正确。

### 3. 积分不足

```
抱歉，您每分钟最多访问该接口N次
```

**解决**：提升Tushare积分，或降低请求频率（修改 `settings.py`）。

### 4. 数据缺失

使用状态检查脚本定位问题：

```bash
python scripts/check_status.py coverage --start 20240101 --end 20240131
python scripts/check_status.py missing 20240102
```

然后重试失败任务或补充特定日期数据。

## 📄 License

MIT License

