#!/bin/bash

# 国网实时数仓测试环境 - 构建脚本

set -e

echo "=== 国网实时数仓测试环境构建脚本 ==="
echo "构建时间: $(date)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}警告: Docker Compose 未安装，将使用 docker compose 命令${NC}"
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p data logs config scripts

# 设置目录权限
chmod -R 755 scripts
chmod +x scripts/*.sh scripts/*.py

# 构建镜像
echo -e "${GREEN}开始构建 Docker 镜像...${NC}"
IMAGE_NAME="power-grid-realtime-warehouse"
IMAGE_TAG="latest"

# 检查是否需要使用代理
if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ]; then
    echo -e "${YELLOW}检测到代理配置:${NC}"
    echo "  HTTP_PROXY: ${HTTP_PROXY:-未设置}"
    echo "  HTTPS_PROXY: ${HTTPS_PROXY:-未设置}"
    
    docker build \
        --build-arg HTTP_PROXY=$HTTP_PROXY \
        --build-arg HTTPS_PROXY=$HTTPS_PROXY \
        --build-arg NO_PROXY=$NO_PROXY \
        -t ${IMAGE_NAME}:${IMAGE_TAG} \
        -f Dockerfile \
        .
else
    docker build \
        -t ${IMAGE_NAME}:${IMAGE_TAG} \
        -f Dockerfile \
        .
fi

# 检查构建结果
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker 镜像构建成功${NC}"
    echo "镜像名称: ${IMAGE_NAME}:${IMAGE_TAG}"
    
    # 显示镜像信息
    echo ""
    echo "=== 镜像信息 ==="
    docker images ${IMAGE_NAME}:${IMAGE_TAG}
    
    # 显示镜像大小
    IMAGE_SIZE=$(docker images ${IMAGE_NAME}:${IMAGE_TAG} --format "{{.Size}}")
    echo "镜像大小: ${IMAGE_SIZE}"
    
else
    echo -e "${RED}✗ Docker 镜像构建失败${NC}"
    exit 1
fi

# 询问是否启动容器
echo ""
read -p "是否立即启动容器? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}启动容器...${NC}"
    $DOCKER_COMPOSE up -d
    
    echo ""
    echo "=== 容器启动完成 ==="
    echo "容器名称: power-grid-realtime-warehouse"
    echo ""
    echo "访问信息:"
    echo "  SSH:           ssh root@localhost -p 2222 (密码: root123)"
    echo "  PostgreSQL:    psql -h localhost -p 5432 -U postgres -d power_grid (密码: postgres)"
    echo "  Flink Web UI:  http://localhost:8081"
    echo "  Fluss Web UI:  http://localhost:8084"
    echo "  Grafana:       http://localhost:3000 (用户名: admin, 密码: admin)"
    echo "  Doris FE:      http://localhost:8030"
    echo ""
    echo "查看日志: docker logs -f power-grid-realtime-warehouse"
    echo "进入容器: docker exec -it power-grid-realtime-warehouse bash"
    echo "停止容器: docker-compose down"
fi

echo ""
echo "=== 构建脚本完成 ==="