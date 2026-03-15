#!/bin/bash
# MySQL Cluster 测试脚本

echo "=========================================="
echo "MySQL Cluster 测试脚本"
echo "=========================================="

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. 检查集群状态
echo -e "\n${YELLOW}1. 检查集群状态...${NC}"
docker exec -it mysql_cluster_mgmd ndb_mgm -e "SHOW" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 集群状态正常${NC}"
else
    echo -e "${RED}✗ 无法连接到管理节点${NC}"
    exit 1
fi

# 2. 测试 SQL 节点连接
echo -e "\n${YELLOW}2. 测试 SQL 节点连接...${NC}"
docker exec -it mysql_cluster_sql1 mysql -uroot -proot123 -e "SELECT 'SQL Node 1 Connected' AS status;" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ SQL 节点 1 连接正常${NC}"
else
    echo -e "${RED}✗ SQL 节点 1 连接失败${NC}"
fi

docker exec -it mysql_cluster_sql2 mysql -uroot -proot123 -e "SELECT 'SQL Node 2 Connected' AS status;" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ SQL 节点 2 连接正常${NC}"
else
    echo -e "${RED}✗ SQL 节点 2 连接失败${NC}"
fi

# 3. 测试数据同步
echo -e "\n${YELLOW}3. 测试数据同步...${NC}"
# 在节点1插入数据
docker exec -it mysql_cluster_sql1 mysql -uroot -proot123 cluster_test -e "INSERT INTO users (username, email) VALUES ('test_user', 'test@example.com');" 2>/dev/null

# 在节点2查询数据
RESULT=$(docker exec -it mysql_cluster_sql2 mysql -uroot -proot123 cluster_test -e "SELECT COUNT(*) FROM users WHERE username='test_user';" 2>/dev/null | grep -v "COUNT" | tr -d ' ')

if [ "$RESULT" = "1" ]; then
    echo -e "${GREEN}✓ 数据同步正常${NC}"
else
    echo -e "${RED}✗ 数据同步失败${NC}"
fi

# 4. 显示表信息
echo -e "\n${YELLOW}4. 显示表信息...${NC}"
docker exec -it mysql_cluster_sql1 mysql -uroot -proot123 cluster_test -e "SHOW TABLES;" 2>/dev/null

echo -e "\n${GREEN}测试完成！${NC}"

