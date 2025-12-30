#!/bin/bash

# 容器功能测试脚本

set -e

echo "=== 国网实时数仓容器功能测试 ==="

CONTAINER_NAME="power-grid-realtime-warehouse"

# 检查容器是否运行
if ! docker ps | grep -q $CONTAINER_NAME; then
    echo "错误: 容器 $CONTAINER_NAME 未运行"
    echo "请先启动容器: docker-compose up -d"
    exit 1
fi

echo "✓ 容器正在运行"

# 测试 SSH 连接
echo "测试 SSH 连接..."
if timeout 5 ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@localhost -p 2222 "echo 'SSH连接成功'" 2>/dev/null; then
    echo "✓ SSH 连接正常"
else
    echo "✗ SSH 连接失败"
fi

# 测试 PostgreSQL 连接
echo "测试 PostgreSQL 连接..."
if docker exec $CONTAINER_NAME pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; then
    echo "✓ PostgreSQL 连接正常"
    
    # 测试数据库查询
    DEVICE_COUNT=$(docker exec $CONTAINER_NAME psql -U postgres -d power_grid -t -c "SELECT COUNT(*) FROM device_info;" 2>/dev/null | xargs)
    if [ ! -z "$DEVICE_COUNT" ] && [ "$DEVICE_COUNT" -gt 0 ]; then
        echo "✓ 数据库查询正常，设备数量: $DEVICE_COUNT"
    else
        echo "✗ 数据库查询失败"
    fi
else
    echo "✗ PostgreSQL 连接失败"
fi

# 测试 HTTP 服务
echo "测试 HTTP 服务..."

# Flink Web UI
if curl -s -f http://localhost:8081 >/dev/null 2>&1; then
    echo "✓ Flink Web UI 正常"
else
    echo "✗ Flink Web UI 无法访问"
fi

# Grafana
if curl -s -f http://localhost:3000 >/dev/null 2>&1; then
    echo "✓ Grafana 正常"
else
    echo "✗ Grafana 无法访问"
fi

# Doris FE
if curl -s -f http://localhost:8030 >/dev/null 2>&1; then
    echo "✓ Doris FE 正常"
else
    echo "✗ Doris FE 无法访问"
fi

# 检查服务进程状态
echo "检查服务进程状态..."
SUPERVISOR_STATUS=$(docker exec $CONTAINER_NAME supervisorctl status 2>/dev/null || echo "supervisorctl 命令失败")

if echo "$SUPERVISOR_STATUS" | grep -q "RUNNING"; then
    RUNNING_COUNT=$(echo "$SUPERVISOR_STATUS" | grep -c "RUNNING" || echo "0")
    echo "✓ Supervisor 管理的服务正在运行: $RUNNING_COUNT 个"
else
    echo "✗ Supervisor 服务状态异常"
fi

# 检查数据生成
echo "检查数据生成..."
sleep 5  # 等待数据生成

TODAY_READINGS=$(docker exec $CONTAINER_NAME psql -U postgres -d power_grid -t -c "SELECT COUNT(*) FROM meter_reading WHERE DATE(create_time) = CURRENT_DATE;" 2>/dev/null | xargs || echo "0")

if [ ! -z "$TODAY_READINGS" ] && [ "$TODAY_READINGS" -gt 0 ]; then
    echo "✓ 数据生成正常，今日读数: $TODAY_READINGS 条"
else
    echo "✗ 数据生成异常"
fi

echo ""
echo "=== 测试完成 ==="
echo "如需查看详细日志: docker logs $CONTAINER_NAME"
echo "如需进入容器: docker exec -it $CONTAINER_NAME bash"