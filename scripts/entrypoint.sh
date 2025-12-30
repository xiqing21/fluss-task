#!/bin/bash

# 国网实时数仓测试环境启动脚本

set -e

echo "=== 国网实时数仓测试环境启动 ==="
echo "启动时间: $(date)"

# 设置代理配置（如果提供）
if [ ! -z "$HTTP_PROXY" ]; then
    echo "配置 HTTP 代理: $HTTP_PROXY"
    export http_proxy=$HTTP_PROXY
    export HTTP_PROXY=$HTTP_PROXY
    
    # 配置 APT 代理
    echo "Acquire::http::Proxy \"$HTTP_PROXY\";" > /etc/apt/apt.conf.d/01proxy
fi

if [ ! -z "$HTTPS_PROXY" ]; then
    echo "配置 HTTPS 代理: $HTTPS_PROXY"
    export https_proxy=$HTTPS_PROXY
    export HTTPS_PROXY=$HTTPS_PROXY
    
    # 配置 APT HTTPS 代理
    echo "Acquire::https::Proxy \"$HTTPS_PROXY\";" >> /etc/apt/apt.conf.d/01proxy
fi

# 配置 pip 代理
if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ]; then
    mkdir -p /root/.pip
    cat > /root/.pip/pip.conf << EOF
[global]
proxy = ${HTTP_PROXY:-$HTTPS_PROXY}
trusted-host = pypi.org
               pypi.python.org
               files.pythonhosted.org
EOF
fi

# 创建必要的目录
echo "创建数据和日志目录..."
mkdir -p /opt/logs /opt/data/{postgresql,flink,fluss,doris,grafana}
mkdir -p /opt/data/flink/{checkpoints,savepoints}
mkdir -p /opt/data/doris/{fe/meta,be/storage}
mkdir -p /var/run/grafana

# 设置目录权限
chown -R postgres:postgres /opt/data/postgresql
chown -R grafana:grafana /opt/data/grafana /var/run/grafana

# 复制配置文件到相应位置
echo "复制配置文件..."
cp /opt/config/flink-conf.yaml /opt/flink/conf/flink-conf.yaml
cp /opt/config/fluss-conf.yaml /opt/fluss/conf/fluss-conf.yaml
cp /opt/config/doris-fe.conf /opt/doris/fe/conf/fe.conf
cp /opt/config/doris-be.conf /opt/doris/be/conf/be.conf
cp /opt/config/grafana.ini /etc/grafana/grafana.ini

# 初始化 PostgreSQL 数据目录（如果不存在）
if [ ! -d "/var/lib/postgresql/13/main" ]; then
    echo "初始化 PostgreSQL 数据目录..."
    sudo -u postgres /usr/lib/postgresql/13/bin/initdb -D /var/lib/postgresql/13/main
fi

# 启动 PostgreSQL 并创建数据库结构
echo "初始化 PostgreSQL 数据库..."
service postgresql start
sleep 5

# 创建数据库和表结构
sudo -u postgres psql -c "SELECT 1" > /dev/null 2>&1 || {
    echo "PostgreSQL 启动失败"
    exit 1
}

# 运行数据库初始化脚本
python3 /opt/scripts/init_database.py

service postgresql stop
sleep 2

# 显示系统信息
echo "=== 系统信息 ==="
echo "Java 版本: $(java -version 2>&1 | head -n 1)"
echo "Python 版本: $(python3 --version)"
echo "PostgreSQL 版本: $(sudo -u postgres /usr/lib/postgresql/13/bin/postgres --version)"
echo "Flink 版本: $(cat /opt/flink/VERSION 2>/dev/null || echo 'Unknown')"

# 显示网络端口信息
echo "=== 服务端口信息 ==="
echo "SSH: 22"
echo "PostgreSQL: 5432"
echo "Flink Web UI: 8081"
echo "Flink REST API: 8082"
echo "Fluss Web UI: 8084"
echo "Fluss Bootstrap: 9123"
echo "Grafana: 3000"
echo "Doris FE: 8030"
echo "Doris MySQL: 9030"
echo "Doris BE: 8040"

# 显示访问信息
echo "=== 访问信息 ==="
echo "SSH 登录: ssh root@localhost -p 22 (密码: root123)"
echo "PostgreSQL: psql -h localhost -p 5432 -U postgres -d power_grid (密码: postgres)"
echo "Flink Web UI: http://localhost:8081"
echo "Fluss Web UI: http://localhost:8084"
echo "Grafana: http://localhost:3000 (用户名: admin, 密码: admin)"
echo "Doris FE: http://localhost:8030"

echo "=== 启动 Supervisor 进程管理器 ==="
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf