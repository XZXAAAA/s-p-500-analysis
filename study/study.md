1. 环境一致性 (Environment Consistency)
问题: "在我的机器上能运行" → 在生产环境却失败
解决: 容器打包了应用及其所有依赖，确保开发、测试、生产环境完全一致
你的项目: 4个微服务（Auth、Data、Viz、Gateway）+ 3个数据库（MySQL、DynamoDB、ClickHouse）+ 前端，都在隔离的容器中运行
2. 快速部署和扩展 (Rapid Deployment & Scaling)
优势: 一条命令 docker-compose up 启动整个系统
扩展: 需要更多Data Service实例？docker-compose up --scale data-service=3
你的项目: 8个服务同时启动，无需手动配置每个服务
3. 资源隔离 (Resource Isolation)
隔离: 每个容器有独立的文件系统、网络、进程空间
安全: 一个服务崩溃不会影响其他服务
你的项目: MySQL在端口3307，ClickHouse在9000/8123，互不干扰
4. 依赖管理 (Dependency Management)
问题: 不同项目需要不同版本的Python、Node.js、数据库
解决: 每个容器有自己的依赖版本
你的项目:
后端服务: Python 3.11
前端: Node.js (构建) + Nginx (运行)
数据库: MySQL 8.0, ClickHouse latest
5. 微服务架构支持 (Microservices Architecture)
解耦: 每个服务独立开发、部署、扩展
技术栈自由: 可以混合使用不同语言和框架
你的项目:
Auth Service (端口5001): 用户认证
Data Service (端口5002): 数据采集和情感分析
Viz Service (端口5003): 数据可视化
API Gateway (端口5000): 统一入口
6. 开发效率 (Development Efficiency)
新成员: 克隆代码 → docker-compose up → 开始工作
无需安装: 不需要在本地安装MySQL、ClickHouse等
版本控制: docker-compose.yml 记录了整个架构

.env 是一个环境变量配置文件，存储项目的配置参数。
1. Docker Compose 启动
   ↓
2. 自动查找同目录下的 .env 文件
   ↓
3. 读取所有 KEY=VALUE 配置
   ↓
4. 在 docker-compose.yml 中替换 ${KEY} 变量
   ↓
5. 启动容器

“I built the FastAPI gateway in gateway.py with /health for itself and /api/health to ping auth/data/viz with timeouts. Services talk over Docker aliases like auth-service:5001 on the shared sentiment_network. In Docker Compose, each service has a simple curl healthcheck and depends_on so the gateway waits for them. The frontend shares the same network and calls the gateway via REACT_APP_API_BASE_URL.”

docker-compose.yml：每个服务都配置了 healthcheck，用容器内的 curl 打各自的 /health 路由（例如 http://localhost:5001/health 等），并设置 timeout、retries。depends_on 结合健康检查，确保依赖服务变为 healthy 后再启动后续服务。
auth-service healthcheck: ["CMD", "curl", "-f", "http://localhost:5001/health"]
data-service healthcheck: ["CMD", "curl", "-f", "http://localhost:5002/health"]
viz-service healthcheck: ["CMD", "curl", "-f", "http://localhost:5003/health"]
api-gateway healthcheck: ["CMD", "curl", "-f", "http://localhost:5000/health"]
底层依赖（如 mysql、dynamodb、clickhouse）也有各自的 healthcheck。
网络互通通过 networks: - sentiment_network，健康检查在容器内部本地主机端口上执行。
网关代码 backend/services/api-gateway/gateway.py：
/health：自身健康检查。
/api/health：聚合探测下游 auth/data/viz 的 /health，通过 Docker 内部别名 auth-service:5001 等发请求，失败会记录错误并标记 unreachable。

都会用 Compose 默认间隔 30s，文件里只自定义了 timeout 和 retries


“I built a concurrent Finviz news pipeline with ThreadPoolExecutor (3 workers), per-request random delays (3–6s) and batch sleeps (8–12s) to rate-limit, plus 3 retries with exponential backoff on HTTP 429/Network errors. It scrapes S&P 500 tickers from Wikipedia, parses headlines, and runs NLTK VADER sentiment scoring; end-to-end it processes 500+ tickers in about 5–10 minutes.”