# MySQL Cluster 学习指南

## 什么是 MySQL Cluster？

MySQL Cluster 是一个**高可用**数据库解决方案：
- **高可用性**：一个节点坏了，其他节点继续工作
- **数据同步**：数据自动复制到多个节点
- **可扩展**：可以轻松添加更多节点

## 架构（3种节点）

```
┌─────────────────────────────────────────────┐
│              Management Node                │  ← 指挥中心，管理所有节点
│                 (1 个)                       │
└─────────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│  Data Node 1  │ ◄──同步──► │  Data Node 2  │  ← 存储数据（至少2个）
└───────────────┘           └───────────────┘
        ▲                           ▲
        └─────────────┬─────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│  SQL Node 1   │           │  SQL Node 2   │  ← 连接这里（像普通MySQL）
│  端口 3308    │           │  端口 3309    │
└───────────────┘           └───────────────┘
```

---

## 快速开始

### 1. 启动集群

```bash
cd mysql-cluster
docker-compose -f docker-compose.cluster.yml up -d
```

等待 30 秒让所有服务启动。

### 2. 检查状态

```bash
docker ps | findstr mysql_cluster
```

应该看到 5 个容器都在运行。

### 3. 连接数据库

```bash
# 方法1：从容器内连接
docker exec -it mysql_cluster_sql1 mysql -uroot -proot123

# 方法2：从本地连接（需要安装 MySQL 客户端）
mysql -h 127.0.0.1 -P 3308 -uroot -proot123
```

### 4. 测试数据同步

```sql
-- 使用测试数据库
USE cluster_test;

-- 在 SQL 节点 1 插入数据
INSERT INTO users (username, email) VALUES ('test', 'test@example.com');

-- 在 SQL 节点 2 查询（应该立即看到！）
-- docker exec -it mysql_cluster_sql2 mysql -uroot -proot123 cluster_test -e "SELECT * FROM users;"
```

---

## 重要概念

### NDB 引擎

只有使用 `ENGINE=NDBCLUSTER` 的表才会存储在集群中：

```sql
-- ✅ 正确：存储在集群中
CREATE TABLE my_table (id INT PRIMARY KEY) ENGINE=NDBCLUSTER;

-- ❌ 错误：不会存储在集群中
CREATE TABLE my_table (id INT PRIMARY KEY) ENGINE=InnoDB;
```

### 数据复制

- 每个数据都有 **2 个副本**（NoOfReplicas=2）
- 一个数据节点故障，数据不会丢失

---

## 常用命令

```bash
# 查看容器状态
docker ps | findstr mysql_cluster

# 查看日志
docker logs mysql_cluster_mgmd
docker logs mysql_cluster_sql1

# 停止集群
docker-compose -f docker-compose.cluster.yml down

# 停止并删除数据（重新开始）
docker-compose -f docker-compose.cluster.yml down -v
```

---

## 实验：测试故障转移

```bash
# 1. 停止一个数据节点
docker stop mysql_cluster_ndbd1

# 2. 测试查询（应该还能工作！）
docker exec -it mysql_cluster_sql1 mysql -uroot -proot123 cluster_test -e "SELECT * FROM users;"

# 3. 重启节点
docker start mysql_cluster_ndbd1
```

---

## 端口说明

| 服务 | 端口 | 用途 |
|------|------|------|
| SQL Node 1 | 3308 | 连接数据库 |
| SQL Node 2 | 3309 | 连接数据库 |
| Management Node | 1186 | 管理集群 |

**注意**：主项目使用端口 3307，不会冲突。

---

## 常见问题

### Q: 节点无法启动？
A: 检查端口是否被占用：`netstat -ano | findstr :3308`

### Q: 数据不同步？
A: 确保表使用 `ENGINE=NDBCLUSTER`

### Q: 无法连接？
A: 等待 30 秒让集群完全启动

---

## 学习路径

1. **第 1 天**：启动集群，连接数据库，执行简单查询
2. **第 2 天**：测试数据同步，在两个 SQL 节点间验证
3. **第 3 天**：测试故障转移，停止/启动数据节点
4. **第 4 天**：创建自己的 NDB 表，插入大量数据
5. **第 5 天**：学习监控命令，了解配置参数

---

## 参考资料

- 官方文档：https://dev.mysql.com/doc/refman/8.0/en/mysql-cluster.html
