# MarketViews 技术文档（中文版）

> 这是本项目唯一的 README，面向新手的完整说明。读完后你应该可以：  
> 1）说清楚项目是做什么的；2）在本地跑起来；3）大致看懂核心代码结构。

---

## 目录

1. [项目简介](#1-项目简介)
2. [整体架构](#2-整体架构)
3. [目录结构详解](#3-目录结构详解)
4. [数据流程（从零到结果）](#4-数据流程从零到结果)
5. [核心技术原理](#5-核心技术原理)
   - 5.1 Wikipedia 获取 S&P 500 列表
   - 5.2 Finviz 新闻抓取
   - 5.3 双车道 + 指数退避策略
   - 5.4 NLTK VADER 情感分析原理
   - 5.5 OpenAI AI 情感分析
   - 5.6 跨股票新闻检测
   - 5.7 数据库三层存储
6. [环境变量配置](#6-环境变量配置)
7. [本地开发启动](#7-本地开发启动)
8. [API 接口文档](#8-api-接口文档)
9. [测试说明](#9-测试说明)
10. [常见问题](#10-常见问题)

---

## 1. 项目简介

**MarketViews** 是一个 S&P 500（标准普尔 500 指数）实时情感分析平台。

**它做什么？**
- 自动从 Wikipedia 获取 500+ 支成分股的股票代码
- 从 Finviz 实时抓取每支股票的最新新闻标题
- 用 NLP（自然语言处理）分析新闻的情感倾向（正面/负面/中性）
- 在 Web 页面上展示情感排行榜和可视化图表

**技术亮点（适合简历描述）：**
- 处理 500+ 支股票，5~10 分钟内完成全量分析
- 容错率 >95%（双车道 + 指数退避策略）
- 支持 NLTK VADER 和 OpenAI ChatGPT API 两种情感引擎（可热切换）
- 微服务架构（4 个 FastAPI 服务 + React 前端）
- 三数据库持久化（MySQL + DynamoDB + ClickHouse）
- 后端 + 前端单元 / 集成测试 130+，全部通过

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器（React）                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP 请求
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway（端口 8080）                       │
│              负责路由转发、JWT 鉴权、限速、日志                    │
└──────┬───────────────────┬──────────────────────┬───────────────┘
       │                   │                      │
       ▼                   ▼                      ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Auth Service │  │  Data Service    │  │  Viz Service     │
│  端口 5001   │  │   端口 5002      │  │   端口 5003      │
│  用户注册    │  │  新闻抓取        │  │  图表数据生成     │
│  JWT 登录    │  │  情感分析        │  │  Treemap/折线图  │
└──────┬───────┘  └────────┬─────────┘  └────────┬─────────┘
       │                   │                      │
       ▼                   ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                        数据存储层                                 │
│  MySQL（用户数据 + 历史快照）                                      │
│  DynamoDB（实时情感缓存，高并发读取）                              │
│  ClickHouse（情感事件流，OLAP 分析）                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 目录结构详解

```
project2/
├── backend/
│   ├── services/
│   │   ├── api-gateway/        ← API 网关（路由 + 鉴权）
│   │   ├── auth-service/       ← 认证服务（注册/登录/JWT）
│   │   ├── data-service/       ← 核心数据服务（爬虫 + 情感分析）
│   │   │   ├── scraper/        ← 爬虫层
│   │   │   │   ├── config.py      所有可调参数（支持环境变量）
│   │   │   │   ├── robots.py      robots.txt 合规检查
│   │   │   │   ├── wikipedia.py   从 Wikipedia 获取股票列表
│   │   │   │   ├── finviz.py      从 Finviz 抓取新闻（双车道）
│   │   │   │   └── parser.py      解析 HTML 表格 → 结构化记录
│   │   │   ├── analyzer/       ← 情感分析层
│   │   │   │   ├── engines.py     VADER / OpenAI 引擎（可插拔）
│   │   │   │   ├── sentiment.py   批量情感评分
│   │   │   │   └── aggregation.py 按股票聚合近期均值
│   │   │   ├── pipeline/       ← 编排层（串联上面两层）
│   │   │   │   └── runner.py      7 步完整流水线
│   │   │   └── app.py          ← FastAPI 服务入口（HTTP API）
│   │   └── viz-service/        ← 可视化服务（Treemap 等）
│   └── shared/                 ← 微服务共享代码
│       ├── models.py           Pydantic 数据模型
│       ├── errors.py           统一异常类
│       └── utils.py            JWT 工具、密码校验
├── database/                   ← 数据库管理器
│   ├── mysql_manager.py        SQLAlchemy ORM（用户/股票/快照）
│   ├── dynamodb_manager.py     boto3（实时缓存）
│   └── clickhouse_manager.py   clickhouse-driver（事件流）
├── frontend/                   ← React + TypeScript 前端
│   └── src/
│       ├── pages/              页面组件（Login/Register/Dashboard）
│       └── api/client.ts       axios 封装（统一 Header + 拦截器）
└── tests/                      ← 测试代码
    ├── unit/                   单元测试（134 个，全部 mock I/O）
    └── integration/            集成测试（HTTP 合约）
```

---

## 4. 数据流程（从零到结果）

以下是一次完整的情感分析运行的 7 个步骤：

### Step 1：获取 S&P 500 股票列表

```
Wikipedia 页面（HTML）
    ↓ pandas.read_html()
    ↓ 正则过滤（只保留 1~5 大写字母的合法 ticker）
["AAPL", "MSFT", "BRK.B", ... 共 503 支]
```

**为什么 Wikipedia 准确？**  
Wikipedia 的 S&P 500 页面由社区持续维护，与标准普尔官方数据高度同步。  
页面中的 HTML 表格包含 `Symbol`（股票代码）和 `GICS Sector`（行业）两列，  
`pandas.read_html()` 直接解析为 DataFrame，无需手动写 HTML 解析代码。

---

### Step 2：抓取 Finviz 新闻

```
对每支 ticker，请求：
  https://finviz.com/quote.ashx?t=AAPL
  ↓
提取 <table id="news-table"> 中的新闻行
```

**原始 HTML 数据格式：**
```html
<table id="news-table">
  <tr>
    <td>Dec-01-24 09:00AM</td>
    <td><a href="...">Apple reports record quarterly revenue</a></td>
  </tr>
  <tr>
    <td>10:30AM</td>  ← 省略日期（同一天后续新闻只有时间）
    <td><a href="...">Tim Cook comments on AI strategy</a></td>
  </tr>
</table>
```

---

### Step 3：解析为结构化记录

```python
# 解析结果：
[
  ["AAPL", "Dec-01-24", "09:00AM", "Apple reports record quarterly revenue"],
  ["AAPL", "Dec-01-24", "10:30AM", "Tim Cook comments on AI strategy"],
  # 跨股票检测：如果标题提到了 MSFT，额外追加一条 MSFT 的记录
  ["MSFT", "Dec-01-24", "09:00AM", "Apple reports record quarterly revenue"],
]
```

---

### Step 4：情感分析

每条记录的 `headline` 字段经过情感引擎处理，得到：

```python
{
  "neg": 0.05,      # 5% 负面词汇
  "neu": 0.72,      # 72% 中性词汇
  "pos": 0.23,      # 23% 正面词汇
  "compound": 0.42  # 综合分数：0.42 表示偏正面
}
```

---

### Step 5：聚合近期均值

对每支股票取最近 2 天所有新闻的 compound 均值：

```
AAPL 今日新闻：compound = [0.42, 0.65, -0.10, 0.38]
平均值 = (0.42 + 0.65 + (-0.10) + 0.38) / 4 = 0.3375
→ AAPL 情感分数 = 0.3375（偏正面）
```

---

### Step 6：合并行业数据

```python
情感分数 DataFrame（来自 Step 5）：
  Ticker  compound  pos   neg   neu
  AAPL    0.3375    0.52  0.11  0.37
  MSFT    0.2100    0.45  0.15  0.40

行业 DataFrame（来自 Wikipedia）：
  Ticker  Sector
  AAPL    Information Technology
  MSFT    Information Technology

inner join on Ticker →
  Ticker  compound  pos   neg   neu   Sector
  AAPL    0.3375    0.52  0.11  0.37  Information Technology
  MSFT    0.2100    0.45  0.15  0.40  Information Technology
```

---

### Step 7：排序输出

最终按 `compound` 降序排列，生成完整结果：

```json
{
  "all_stocks": [
    {
      "ticker": "AAPL",
      "sector": "Information Technology",
      "sentiment_score": 0.3375,
      "positive": 0.52,
      "negative": 0.11,
      "neutral": 0.37,
      "news_count": 12,
      "timestamp": 1733000000
    },
    ...
  ],
  "top_5": [...],
  "low_5": [...]
}
```

---

## 5. 核心技术原理

### 5.1 Wikipedia 获取 S&P 500 列表

**为什么可以准确获取股票名称？**

1. **robots.txt 检查**：Wikipedia 的 `robots.txt` 明确允许爬虫访问 `/wiki/` 路径  
2. **pandas.read_html()** 使用 lxml 解析 HTML，找到包含 `Symbol` 和 `Sector` 列的表格  
3. **正则校验** `^[A-Z]{1,5}(\.[A-Z])?$`：  
   - `AAPL`  ✓（4 个大写字母）  
   - `BRK.B` ✓（3 个字母 + 点 + 1 个字母）  
   - `123`   ✗（数字，过滤掉）  
   - `TOOLONG` ✗（超过 5 个字母，过滤掉）  
4. **容错回退**：任何异常都返回内置的 10 支头部股票列表

---

### 5.2 Finviz 新闻抓取

**Finviz 如何存储新闻数据？**

Finviz 每支股票的报价页面（`/quote.ashx?t=AAPL`）包含一个 `id="news-table"` 的 HTML 表格，  
其中按时间倒序列出最近的新闻标题和来源链接。

**爬取方式**：使用 Python 标准库 `urllib.request`，设置自定义 `User-Agent` 模拟浏览器。

---

### 5.3 双车道 + 指数退避策略

这是实现 **“500+ 支股票 5~10 分钟内完成”** 和 **“>95% 成功率”** 的关键设计。

#### 为什么需要双车道？

串行处理 500 支股票（每支约 2 秒延迟）需要 **1000 秒 ≈ 17 分钟**，  
并发处理虽然更快，但会触发服务器限速（HTTP 429）。

双车道设计将问题分成两个阶段：
- **快车道**：高并发快速处理 ~95% 的股票  
- **慢车道**：保守重试剩余 ~5% 的失败股票

#### 指数退避（Exponential Backoff）原理

```
首次遇到 HTTP 429 → 等待 100ms → 重试
第二次失败       → 等待 200ms → 重试
第三次失败       → 等待 400ms → 重试
第四次失败       → 等待 800ms → 放弃（交给慢车道）

慢车道：2s → 4s → 8s → 16s
```

**为什么用指数而非固定间隔？**  
固定间隔（如每次等 1 秒）可能仍然不够——服务器流量高峰时，  
指数退避会在短暂失败后“给服务器喘息的时间”，显著提高最终成功率。

---

### 5.4 NLTK VADER 情感分析原理

**VADER**（Valence Aware Dictionary and sEntiment Reasoner）是专门为社交媒体文本设计的规则 + 词典方法。

#### 工作流程

```
输入："Apple reports AMAZING earnings beating all expectations!!!"
         ↓
1. 分词：["Apple", "reports", "AMAZING", "earnings", "beating", "all", "expectations", "!!!"]
         ↓
2. 词典查找：
   - "reports"      → 中性（0）
   - "AMAZING"      → 正面（词典分 3.1 × 1.3 全大写加权 = 4.03）
   - "beating"      → 正面（2.1）
   - "expectations" → 中性（0）
   - "!!!"          → 额外加权 +0.292（3 个感叹号）
         ↓
3. 计算比例：
   neg = 0.0（无负面词）
   neu = 0.42
   pos = 0.58
         ↓
4. 归一化 compound（Sigmoid 函数）：
   compound = 0.87（强正面）
```

#### 为什么 compound 范围是 [-1, 1]？

VADER 用 Sigmoid 函数对原始加权和进行归一化：

```
compound = x / sqrt(x² + α)
其中 α = 15（归一化系数）
```

- x 趋向 +∞ → compound 趋向 +1  
- x 趋向 -∞ → compound 趋向 -1  
- x = 0     → compound = 0

#### 常用判断阈值

| compound 值 | 情感判断        |
|-------------|-----------------|
| > 0.05      | 正面（Positive） |
| < -0.05     | 负面（Negative） |
| [-0.05, 0.05] | 中性（Neutral） |

---

### 5.5 OpenAI AI 情感分析

默认使用 OpenAI ChatGPT API 进行分析（需设置 `OPENAI_API_KEY`）；  
若未设置或希望仅用本地引擎，可设置 `SENTIMENT_ENGINE=vader`。

#### 提示词（Prompt）设计

```
System: You are a financial news sentiment analyser.
        For the given headline return ONLY a JSON object with four numeric fields:
        neg, neu, pos (each in [0,1], sum ≈ 1) and compound (in [-1,1]).
        No extra text, no markdown, just JSON.

User: Apple reports record quarterly revenue beating analyst estimates
```

#### ChatGPT 响应

```json
{"neg": 0.02, "neu": 0.55, "pos": 0.43, "compound": 0.76}
```

#### 鲁棒性设计

```
AI 调用成功且结果合法 → 返回 AI 结果
AI 返回非法 JSON     → 回退到 VADER
AI 分数越界          → 回退到 VADER
API 调用超时/报错    → 回退到 VADER
openai 包未安装      → 自动使用 VADER
```

---

### 5.6 跨股票新闻检测

**问题**：一条新闻 `"Apple and Microsoft announce AI partnership"` 不只影响 AAPL，  
也会影响 MSFT 的市场情绪，但这条新闻在 Finviz 只出现在 AAPL 的页面上。

**解决方案**：在解析新闻标题时，用正则 `\b[A-Z]{1,5}\b` 提取所有大写单词，  
与已知的 S&P 500 ticker 集合取交集。找到的额外 ticker 也追加一条记录。

```python
headline = "Apple and MSFT announce AI partnership"
primary  = "AAPL"
candidates = {"Apple", "MSFT", "AI"}   # 正则提取
sp500_set  = {"AAPL", "MSFT", "GOOG", ...}

# 交集 - 主股票 = {"MSFT"}
→ 额外追加 ["MSFT", date, time, headline]
```

---

### 5.7 数据库三层存储

| 数据库 | 用途                    | 适合的查询                 |
|--------|-------------------------|----------------------------|
| **MySQL**      | 用户账户 + 每日情感快照       | 历史趋势、精确查询           |
| **DynamoDB**   | 实时情感缓存               | 高并发读取（毫秒级响应）     |
| **ClickHouse** | 情感事件流（列存储）        | OLAP 分析、聚合统计          |

**为什么需要三个数据库？**
- 没有任何一种数据库在所有场景都最优  
- MySQL 擅长事务和关系查询，但不擅长高并发  
- DynamoDB 擅长高并发 K-V 查找，但不擅长范围查询  
- ClickHouse 擅长大数据分析，但写入延迟相对高

---

## 6. 环境变量配置

### 情感引擎

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SENTIMENT_ENGINE` | `ai` | 情感引擎：`ai`（会调用 OpenAI API）或 `vader`（仅本地） |
| `SENTIMENT_AI_MODEL` | `gpt-4.1-mini` | 使用的 OpenAI 模型 |
| `OPENAI_API_KEY` | 无 | 使用 AI 引擎时必须设置 |

### 爬虫参数

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SCRAPER_MAX_WORKERS` | `3` | 线程池并发数 |
| `SCRAPER_BATCH_SIZE` | `30` | 批次大小（每批后暂停）|
| `SCRAPER_DELAY_FAST_MIN` | `1.0` | 快车道最小延迟（秒）|
| `SCRAPER_DELAY_FAST_MAX` | `3.0` | 快车道最大延迟（秒）|
| `NEWS_QUEUE_BACKEND` | `""` | 慢车道队列：留空 = 线程池，`redis` = Redis |
| `NEWS_QUEUE_REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 URL |

### 数据库

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `MYSQL_HOST` | `localhost` | MySQL 地址 |
| `MYSQL_PORT` | `3306` | MySQL 端口 |
| `MYSQL_DB` | `sentiment_db` | 数据库名 |
| `MYSQL_USER` | `root` | 用户名 |
| `MYSQL_PASSWORD` | `""` | 密码 |
| `AWS_ACCESS_KEY_ID` | 无 | DynamoDB 访问密钥 |
| `CLICKHOUSE_HOST` | `localhost` | ClickHouse 地址 |

---

## 7. 本地开发启动

### 方式一：Docker Compose（推荐）

```bash
# 1. 复制环境变量文件
cp .env.example .env
# 根据需要编辑 .env 文件

# 2. 启动所有服务（包括数据库）
docker-compose up -d

# 3. 查看服务状态
docker-compose ps

# 4. 查看 data-service 日志
docker-compose logs -f data-service
```

启动后访问：
- 前端：`http://localhost:3000`
- API Gateway：`http://localhost:8080`
- Data Service Swagger：`http://localhost:5002/docs`

### 方式二：直接运行 Python

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
# 使用 OpenAI 时需设置（默认已是 ai 引擎）：
export OPENAI_API_KEY=sk-...
# 若只想用本地 VADER，可改为：
# export SENTIMENT_ENGINE=vader

# 仅运行 data-service（不需要数据库）
cd backend/services/data-service
python app.py
```

---

## 8. API 接口文档

### 通用响应格式

所有接口均返回统一格式：

```json
{
  "success": true,
  "code": "SUCCESS",
  "data": { },
  "message": null,
  "timestamp": "2024-12-01T09:00:00Z"
}
```

### 数据服务（端口 5002）

#### `GET /health`
健康检查，API Gateway 使用此接口判断服务是否存活。

#### `GET /data/status`
查询流水线状态。

**响应示例：**
```json
{
  "success": true,
  "code": "SUCCESS",
  "data": {
    "has_data": true,
    "is_generating": false,
    "elapsed_seconds": 0,
    "last_update": 1733000000
  }
}
```

#### `POST /data/refresh`
触发后台刷新（约 5~10 分钟），立即返回。

#### `GET /data/top-stocks?limit=500`
获取所有股票的情感排名（按 `sentiment_score` 降序）。

**响应示例（`data` 数组中的单条记录）：**
```json
{
  "ticker": "AAPL",
  "sector": "Information Technology",
  "sentiment_score": 0.4231,
  "positive": 0.6100,
  "negative": 0.0900,
  "neutral": 0.3000,
  "news_count": 12,
  "timestamp": 1733000000
}
```

#### `GET /sentiment/by-ticker/AAPL`
查询指定股票（大小写不敏感）。

### 认证服务（端口 5001）

#### `POST /auth/register`
```json
请求体：
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!"
}
```

#### `POST /auth/login`
```json
请求体：
{
  "username": "alice",
  "password": "SecurePass123!"
}

响应 data：
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 86400,
  "user": { "id": 1, "username": "alice" }
}
```

---

## 9. 测试说明

### 运行所有测试

```bash
# 安装测试依赖
pip install nltk pandas requests beautifulsoup4 numpy pytest

# 运行全部测试（134 个）
py -3 -m pytest tests/ -v

# 只运行某一层的测试
py -3 -m pytest tests/unit/test_scraper.py -v
py -3 -m pytest tests/unit/test_analyzer.py -v
py -3 -m pytest tests/unit/test_pipeline.py -v
```

### 测试结构说明

```
tests/
├── unit/
│   ├── test_scraper.py           ← 爬虫层：robots/wikipedia/finviz/parser
│   ├── test_analyzer.py          ← 分析层：VADER/AI/情感评分/聚合
│   ├── test_pipeline.py          ← 流水线：PipelineResult/run() 编排
│   ├── test_database_managers.py ← 数据库管理器
│   ├── test_data_service.py      ← 数据服务模型
│   └── test_auth_service.py      ← 认证服务
└── integration/
    └── test_api_endpoints.py     ← HTTP 合约测试
```

---

## 10. 常见问题

### Q：第一次访问前端看不到数据，怎么办？

A：服务启动后会自动触发后台流水线，大约 5~10 分钟后数据就绪。  
   可以访问 `GET /data/status` 查看进度，或点击前端的 Refresh 按钮。

---

### Q：想换成 ChatGPT 分析，如何操作？

A：
1. 获取 OpenAI API Key：`https://platform.openai.com`  
2. 设置环境变量：
   ```bash
   export SENTIMENT_ENGINE=ai
   export OPENAI_API_KEY=sk-...
   ```
3. 重启 data-service，无需修改任何代码。

---

### Q：为什么某些股票没有情感数据？

A：可能原因：
1. Finviz 页面暂时无法访问（慢车道重试后仍失败）  
2. 该股票最近没有新闻（Finviz 页面无 `news-table`）  
3. 行业数据（Wikipedia）中没有该股票（inner join 后被过滤）

---

### Q：如何在没有网络的环境中测试？

A：所有单元测试都使用 Mock 替代网络请求，无需真实网络连接：
```bash
py -3 -m pytest tests/unit/ -v
```

---

### Q：运行测试时遇到 `ModuleNotFoundError: boto3`，怎么办？

A：不需要安装 boto3。测试已通过 `sys.modules` 预注入 Mock，  
   直接运行 `pytest` 即可，无需真实 AWS 环境。

---

*文档版本：v2.0（中文版） | 最后更新：2025 年*

# S&P 500 Stock Sentiment Analysis

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/downloads/)
[![React 18](https://img.shields.io/badge/React-18-61dafb?logo=react)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ed?logo=docker)](https://www.docker.com/)

**Project Status**: ✅ Production Ready (100% Complete)  
**Completion Date**: November 26, 2025  
**Author**: Andy  
**Total Code**: 11,160+ lines  
**Test Coverage**: 85%

---

## 📖 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Development](#development)
- [Contributing](#contributing)

---

## Overview

An **enterprise-grade microservices application** for real-time sentiment analysis of S&P 500 stocks. The system scrapes stock-related news, performs NLP-based sentiment analysis, and presents insights through interactive visualizations.

### Key Highlights

- ✅ **Complete Microservices Architecture** - 4 independent services + API gateway
- ✅ **Modern React Frontend** - TypeScript + Material-UI
- ✅ **Hybrid Database Design** - MySQL + DynamoDB + ClickHouse
- ✅ **Real-Time Sentiment Analysis** - NLTK VADER for 500+ stocks
- ✅ **Comprehensive Testing** - 67 tests with 85% coverage
- ✅ **Production Ready** - Docker Compose deployment
- ✅ **Complete Documentation** - Swagger API docs + guides

---

## Quick Start

### Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- 8GB+ RAM
- 10GB+ available disk space

### 3-Step Setup (5 minutes)

```bash
# 1. Clone the repository
git clone <repository-url>
cd project2

# 2. Start all services
docker-compose up -d

# 3. Wait for services to initialize (2-3 minutes)
docker-compose logs -f
```

### Access the Application

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | React web application |
| **API Gateway** | http://localhost:5000 | Main API endpoint |
| **Auth Service Docs** | http://localhost:5001/docs | Swagger UI |
| **Data Service Docs** | http://localhost:5002/docs | Swagger UI |
| **Viz Service Docs** | http://localhost:5003/docs | Swagger UI |

### Default Test Account

```
Username: testuser
Password: TestPass123!
```

---

## Features

### Core Functionality

- **Real-Time Sentiment Analysis**
  - Scrapes news from Finviz for all S&P 500 stocks
  - NLTK VADER sentiment scoring
  - Processes 500+ stocks in 5-10 minutes
  - Caches results for fast retrieval

- **Interactive Dashboard**
  - Sector-based grouping
  - Color-coded sentiment indicators
  - Trend visualization
  - Real-time updates
  - Responsive design

- **User Management**
  - Secure registration and login
  - JWT authentication
  - Session management
  - User preferences
  - Audit logging

- **Data Visualization**
  - Treemap charts
  - Sentiment timelines
  - Sector analysis
  - Market overview

---

## Architecture

### System Diagram

```
┌─────────────┐
│   Frontend  │  React + TypeScript
│  (Port 3000)│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ API Gateway │  FastAPI
│  (Port 5000)│
└──────┬──────┘
       │
       ├──────────────┬──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│   Auth   │   │   Data   │   │   Viz    │   │  Other   │
│ Service  │   │ Service  │   │ Service  │   │ Services │
│(Port 5001│   │(Port 5002│   │(Port 5003│   │          │
└────┬─────┘   └────┬─────┘   └────┬─────┘   └──────────┘
     │              │              │
     └──────┬───────┴──────┬───────┘
            ▼              ▼
    ┌──────────────────────────────┐
    │       Database Layer         │
    ├──────────┬──────────┬────────┤
    │  MySQL   │ DynamoDB │ClickHse│
    └──────────┴──────────┴────────┘
```

### Microservices

| Service | Port | Responsibility | Tech |
|---------|------|----------------|------|
| **Auth Service** | 5001 | User authentication, JWT tokens | FastAPI, SQLAlchemy |
| **Data Service** | 5002 | Data scraping, sentiment analysis | FastAPI, NLTK, BeautifulSoup |
| **Viz Service** | 5003 | Data visualization, charts | FastAPI, Plotly |
| **API Gateway** | 5000 | Request routing, load balancing | FastAPI |
| **Frontend** | 3000 | User interface | React, TypeScript, Material-UI |

### Database Architecture

- **MySQL** - Transactional data (users, stocks, audit logs)
- **DynamoDB** - High-concurrency cache (sessions, real-time sentiment)
- **ClickHouse** - Real-time analytics (time-series data, aggregations)

---

## Tech Stack

### Backend

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Authentication**: JWT (PyJWT)
- **ORM**: SQLAlchemy
- **NLP**: NLTK VADER
- **Web Scraping**: BeautifulSoup4, Requests
- **Async**: Uvicorn, BackgroundTasks

### Frontend

- **Framework**: React 18
- **Language**: TypeScript
- **Build Tool**: Vite
- **UI Library**: Material-UI (MUI)
- **HTTP Client**: Axios
- **Routing**: React Router v6
- **Visualization**: Plotly.js
- **Testing**: Vitest, Testing Library

### Databases

- **MySQL 8.0** - Relational data
- **DynamoDB** - NoSQL cache
- **ClickHouse** - OLAP analytics

### DevOps

- **Containerization**: Docker
- **Orchestration**: Docker Compose
- **Web Server**: Nginx
- **API Gateway**: FastAPI

---

## Project Structure

```
project2/
├── backend/
│   ├── services/
│   │   ├── auth-service/       # Authentication service
│   │   ├── data-service/       # Data & sentiment analysis
│   │   ├── viz-service/        # Visualization service
│   │   └── api-gateway/        # API gateway
│   └── shared/                 # Shared utilities
├── database/                   # Database managers
│   ├── mysql_manager.py
│   ├── dynamodb_manager.py
│   ├── clickhouse_manager.py
│   └── data_sync_pipeline.py
├── frontend/                   # React application
│   ├── src/
│   │   ├── pages/             # Page components
│   │   ├── api/               # API client
│   │   └── __tests__/         # Component tests
│   └── package.json
├── tests/                      # Backend tests
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── run_tests.py           # Test runner
├── docs/                       # Documentation
│   ├── API_DOCUMENTATION.md
│   ├── TESTING_GUIDE.md
│   ├── SETUP_GUIDE.md
│   └── DATABASE_ANALYSIS.md
├── docker-compose.yml          # Docker orchestration
├── .env                        # Environment variables
└── README.md                   # This file
```

---

## API Documentation

### Interactive Documentation

Each service provides interactive Swagger UI documentation:

- **Auth Service**: http://localhost:5001/docs
- **Data Service**: http://localhost:5002/docs
- **Viz Service**: http://localhost:5003/docs

### Key Endpoints

#### Authentication

```http
POST /api/auth/register     # Register new user
POST /api/auth/login        # Login and get JWT token
POST /api/auth/logout       # Logout user
GET  /api/auth/verify       # Verify token
```

#### Data & Sentiment

```http
POST /api/data/refresh      # Trigger data refresh
GET  /api/data/status       # Get generation status
GET  /api/data/top-stocks   # Get top stocks by sentiment
GET  /api/sentiment/all     # Get all sentiment data
```

#### Visualization

```http
GET /api/viz/treemap        # Get treemap data
GET /api/viz/timeline       # Get sentiment timeline
GET /api/viz/sector-analysis # Get sector analysis
```

For complete API documentation, see [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)

---

## Testing

### Test Suite

- **67 Total Tests**
  - 52 Backend unit tests
  - 15 Integration tests
  - Frontend component tests
- **85% Average Coverage**
  - 90% Backend coverage
  - 80% Frontend coverage

### Run Tests

```bash
# Backend tests
python tests/run_tests.py

# Frontend tests
cd frontend
npm test

# Coverage report
npm run test:coverage
```

For detailed testing guide, see [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md)

---

## Deployment

### Docker Compose (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild services
docker-compose up -d --build
```

### Individual Services

```bash
# Start specific service
docker-compose up -d auth-service

# Scale service
docker-compose up -d --scale data-service=3
```

### Environment Variables

Create `.env` file:

```env
# Database
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=sentiment_user
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=sentiment_db

# DynamoDB
DYNAMODB_ENDPOINT=http://dynamodb:8000
AWS_REGION=us-east-1

# ClickHouse
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_PORT=9000
CLICKHOUSE_USER=sentiment_user
CLICKHOUSE_PASSWORD=your_password

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
```

---

## Development

### Setup Development Environment

```bash
# Backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run dev
```
