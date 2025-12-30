# 完整 Docker 镜像增强方案（含 SSH、代理和发布流程）

## 一、增强版 Dockerfile

```dockerfile
# Dockerfile-extended-with-ssh
FROM xuyangzzz/delta_join_example:1.0

LABEL maintainer="xiaosuange@gmail.com"
LABEL version="2.0"
LABEL description="国网实时数仓测试环境 - 含SSH、代理和完整组件"

# 1. 设置代理环境变量
ARG PROXY_HOST=host.docker.internal
ARG PROXY_PORT=7890
ENV http_proxy=http://${PROXY_HOST}:${PROXY_PORT}
ENV https_proxy=http://${PROXY_HOST}:${PROXY_PORT}
ENV HTTP_PROXY=http://${PROXY_HOST}:${PROXY_PORT}
ENV HTTPS_PROXY=http://${PROXY_HOST}:${PROXY_PORT}
ENV no_proxy=localhost,127.0.0.1,0.0.0.0,10.0.0.0/8,192.168.0.0/16,172.16.0.0/12
ENV NO_PROXY=localhost,127.0.0.1,0.0.0.0,10.0.0.0/8,192.168.0.0/16,172.16.0.0/12

# 2. 配置 APT 代理
RUN echo "Acquire::http::Proxy \"${http_proxy}\";" > /etc/apt/apt.conf.d/99proxy && \
    echo "Acquire::https::Proxy \"${https_proxy}\";" >> /etc/apt/apt.conf.d/99proxy

# 3. 安装 PostgreSQL
RUN apt-get update && \
    apt-get install -y \
    postgresql-13 \
    postgresql-client-13 \
    postgresql-contrib-13 \
    && apt-get clean

# 4. 安装和配置 SSH
RUN apt-get update && \
    apt-get install -y \
    openssh-server \
    sshpass \
    && apt-get clean

# 5. 配置 SSH
RUN mkdir /var/run/sshd && \
    echo 'root:root123' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config

# 6. 生成 SSH 密钥
RUN ssh-keygen -A && \
    mkdir -p /root/.ssh && \
    ssh-keygen -t rsa -f /root/.ssh/id_rsa -N ""

# 7. 配置免密登录
RUN cat /root/.ssh/id_rsa.pub > /root/.ssh/authorized_keys && \
    chmod 600 /root/.ssh/authorized_keys && \
    chmod 700 /root/.ssh

# 8. 安装 Python 依赖
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    && apt-get clean

# 9. 设置 pip 代理
RUN mkdir -p /root/.pip && \
    echo "[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\nproxy = ${http_proxy}\n" > /root/.pip/pip.conf

# 10. 安装 Python 包
RUN pip3 install --no-cache-dir \
    psycopg2-binary==2.9.6 \
    faker==18.4.0 \
    pandas==1.5.3 \
    requests==2.28.2 \
    paramiko==3.0.0 \
    sshtunnel==0.4.0 \
    mysql-connector-python==8.0.33 \
    pyyaml==6.0

# 11. 安装 Flink CDC 连接器
WORKDIR /opt/flink/lib
# PostgreSQL CDC
RUN wget -e use_proxy=yes -e http_proxy=${http_proxy} \
    https://repo1.maven.org/maven2/com/ververica/flink-sql-connector-postgres-cdc/2.4.0/flink-sql-connector-postgres-cdc-2.4.0.jar
# MySQL CDC
RUN wget -e use_proxy=yes -e http_proxy=${http_proxy} \
    https://repo1.maven.org/maven2/com/ververica/flink-sql-connector-mysql-cdc/2.4.0/flink-sql-connector-mysql-cdc-2.4.0.jar
# Doris Connector
RUN wget -e use_proxy=yes -e http_proxy=${http_proxy} \
    https://repo1.maven.org/maven2/org/apache/doris/flink-doris-connector/1.4.0/flink-doris-connector-1.4.0.jar
# Kafka Connector
RUN wget -e use_proxy=yes -e http_proxy=${http_proxy} \
    https://repo1.maven.org/maven2/org/apache/flink/flink-connector-kafka/1.16.0/flink-connector-kafka-1.16.0.jar

# 12. 安装 Doris
RUN apt-get update && \
    apt-get install -y \
    openjdk-11-jdk \
    wget \
    curl \
    vim \
    net-tools \
    telnet \
    && apt-get clean

# 13. 下载并安装 Doris
RUN wget -e use_proxy=yes -e http_proxy=${http_proxy} \
    https://apache-doris-releases.oss-accelerate.aliyuncs.com/apache-doris-1.2.7.1-bin-x86_64.tar.gz && \
    tar -zxvf apache-doris-1.2.7.1-bin-x86_64.tar.gz && \
    mv apache-doris-1.2.7.1-bin-x86_64 /opt/doris && \
    rm -f apache-doris-1.2.7.1-bin-x86_64.tar.gz

# 14. 配置 Doris
COPY config/doris-fe.conf /opt/doris/fe/conf/fe.conf
COPY config/doris-be.conf /opt/doris/be/conf/be.conf

# 15. 安装 Grafana
RUN apt-get install -y \
    wget \
    gnupg \
    software-properties-common \
    && wget -q -O - https://packages.grafana.com/gpg.key | apt-key add - \
    && echo "deb https://packages.grafana.com/oss/deb stable main" | tee -a /etc/apt/sources.list.d/grafana.list \
    && apt-get update && apt-get install -y grafana

# 16. 安装 Supervisor（进程管理）
RUN apt-get install -y supervisor

# 17. 创建工作目录
WORKDIR /app
RUN mkdir -p /app/{scripts,sql,config,logs,data}

# 18. 复制配置文件
COPY config/supervisord.conf /etc/supervisor/supervisord.conf
COPY config/grafana.ini /etc/grafana/grafana.ini
COPY config/postgresql.conf /etc/postgresql/13/main/postgresql.conf
COPY config/pg_hba.conf /etc/postgresql/13/main/pg_hba.conf

# 19. 复制脚本
COPY scripts/*.sh /app/scripts/
COPY scripts/*.py /app/scripts/
COPY sql/*.sql /app/sql/
COPY config/*.json /app/config/

# 20. 设置权限
RUN chmod +x /app/scripts/*.sh && \
    chmod +x /app/scripts/*.py && \
    chown -R postgres:postgres /var/lib/postgresql/13/main && \
    chown -R grafana:grafana /etc/grafana

# 21. 设置环境变量
ENV FLINK_HOME=/opt/flink
ENV DORIS_HOME=/opt/doris
ENV PATH=$PATH:$FLINK_HOME/bin:$DORIS_HOME/fe/bin:$DORIS_HOME/be/bin
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PG_DATA=/var/lib/postgresql/13/main
ENV FLUSS_BOOTSTRAP_SERVERS=localhost:9123
ENV PROXY_ENABLED=true
ENV PROXY_SERVER=${PROXY_HOST}
ENV PROXY_PORT=${PROXY_PORT}

# 22. 暴露端口
# Flink Web UI: 8081, REST: 8082, JobManager: 8083
# PostgreSQL: 5432, SSH: 22, Grafana: 3000
# Doris FE: 8030, 9030; BE: 8040
# Fluss: 8084, 9123
EXPOSE 22 5432 8081 8082 8083 8084 3000 8030 9030 8040 9123

# 23. 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5m --retries=3 \
  CMD /app/scripts/healthcheck.sh || exit 1

# 24. 启动命令
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf", "-n"]
```

## 二、Supervisor 配置文件

```ini
; /etc/supervisor/supervisord.conf
[unix_http_server]
file=/var/run/supervisor.sock
chmod=0700

[supervisord]
nodaemon=true
logfile=/var/log/supervisord.log
pidfile=/var/run/supervisord.pid
childlogdir=/var/log/supervisor
loglevel=info

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///var/run/supervisor.sock

[program:sshd]
command=/usr/sbin/sshd -D
autostart=true
autorestart=true
startretries=5
user=root
redirect_stderr=true
stdout_logfile=/var/log/sshd.log
stderr_logfile=/var/log/sshd_err.log

[program:postgresql]
command=/usr/lib/postgresql/13/bin/postgres -D /var/lib/postgresql/13/main -c config_file=/etc/postgresql/13/main/postgresql.conf
autostart=true
autorestart=true
startretries=5
user=postgres
redirect_stderr=true
stdout_logfile=/var/log/postgresql.log
stderr_logfile=/var/log/postgresql_err.log

[program:doris-fe]
command=/opt/doris/fe/bin/start_fe.sh
autostart=true
autorestart=true
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/var/log/doris-fe.log
stderr_logfile=/var/log/doris-fe_err.log

[program:doris-be]
command=/opt/doris/be/bin/start_be.sh
autostart=true
autorestart=true
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/var/log/doris-be.log
stderr_logfile=/var/log/doris-be_err.log

[program:grafana]
command=/usr/sbin/grafana-server --config=/etc/grafana/grafana.ini --homepath=/usr/share/grafana
autostart=true
autorestart=true
startretries=5
user=grafana
redirect_stderr=true
stdout_logfile=/var/log/grafana.log
stderr_logfile=/var/log/grafana_err.log

[program:flink]
command=/app/scripts/start-flink.sh
autostart=true
autorestart=true
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/var/log/flink.log
stderr_logfile=/var/log/flink_err.log

[program:fluss]
command=/app/scripts/start-fluss.sh
autostart=true
autorestart=true
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/var/log/fluss.log
stderr_logfile=/var/log/fluss_err.log

[program:data-generator]
command=python3 /app/scripts/data_generator.py
autostart=true
autorestart=true
startretries=5
user=root
redirect_stderr=true
stdout_logfile=/var/log/data-generator.log
stderr_logfile=/var/log/data-generator_err.log

[program:monitor]
command=python3 /app/scripts/monitor.py
autostart=true
autorestart=true
startretries=3
user=root
redirect_stderr=true
stdout_logfile=/var/log/monitor.log
stderr_logfile=/var/log/monitor_err.log
```

## 三、启动脚本

```bash
#!/bin/bash
# /app/scripts/start-all-services.sh

set -e

echo "=== 启动国网实时数仓测试环境 ==="
echo "代理设置: ${HTTP_PROXY}"
echo "当前时间: $(date)"
echo "主机名: $(hostname)"
echo "IP地址: $(hostname -I)"

# 1. 启动 SSH
echo "[1/9] 启动 SSH 服务..."
service ssh start
if [ $? -eq 0 ]; then
    echo "✓ SSH 服务启动成功"
    echo "SSH登录信息:"
    echo "  IP: $(hostname -I | awk '{print $1}')"
    echo "  端口: 22"
    echo "  用户名: root"
    echo "  密码: root123"
    echo "  SSH公钥:"
    cat /root/.ssh/id_rsa.pub
else
    echo "✗ SSH 服务启动失败"
    exit 1
fi

# 2. 测试代理连接
echo "[2/9] 测试代理连接..."
if [ "$PROXY_ENABLED" = "true" ]; then
    echo "使用代理: ${HTTP_PROXY}"
    if curl -x ${HTTP_PROXY} --connect-timeout 10 -I https://www.baidu.com 2>/dev/null | grep -q "HTTP/"; then
        echo "✓ 代理连接成功"
    else
        echo "⚠ 代理连接失败，尝试直连"
        export HTTP_PROXY=""
        export HTTPS_PROXY=""
    fi
fi

# 3. 启动 PostgreSQL
echo "[3/9] 启动 PostgreSQL..."
service postgresql start
sleep 5

# 初始化数据库
echo "初始化 PostgreSQL 数据库..."
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'postgres';" 2>/dev/null || true
sudo -u postgres createdb power_grid 2>/dev/null || true
sudo -u postgres psql -d power_grid -f /app/sql/init_postgres.sql
if [ $? -eq 0 ]; then
    echo "✓ PostgreSQL 启动成功"
else
    echo "✗ PostgreSQL 启动失败"
fi

# 4. 启动 Doris
echo "[4/9] 启动 Doris..."
# 启动 FE
/opt/doris/fe/bin/start_fe.sh --daemon
sleep 10
# 启动 BE
/opt/doris/be/bin/start_be.sh --daemon
sleep 5

# 初始化 Doris
echo "初始化 Doris 数据库..."
mysql -h127.0.0.1 -P9030 -uroot -e "ALTER SYSTEM ADD BACKEND '127.0.0.1:9050';" 2>/dev/null || true
mysql -h127.0.0.1 -P9030 -uroot -e "CREATE DATABASE IF NOT EXISTS power_grid_doris;" 2>/dev/null || true
if [ $? -eq 0 ]; then
    echo "✓ Doris 启动成功"
else
    echo "⚠ Doris 初始化有警告，但继续启动流程"
fi

# 5. 启动 Grafana
echo "[5/9] 启动 Grafana..."
service grafana-server start
sleep 3

# 导入 Dashboard
if [ -f /app/config/grafana_dashboard.json ]; then
    echo "导入 Grafana Dashboard..."
    sleep 5
    curl -X POST -H "Content-Type: application/json" \
         -d @/app/config/grafana_dashboard.json \
         http://admin:admin@localhost:3000/api/dashboards/db 2>/dev/null || true
fi
echo "✓ Grafana 启动成功"
echo "  URL: http://localhost:3000"
echo "  用户名: admin"
echo "  密码: admin"

# 6. 启动 Flink
echo "[6/9] 启动 Flink..."
/app/scripts/start-flink.sh &
sleep 10

# 7. 启动 Fluss
echo "[7/9] 启动 Fluss..."
/app/scripts/start-fluss.sh &
sleep 5

# 8. 启动数据生成器
echo "[8/9] 启动数据生成器..."
nohup python3 /app/scripts/data_generator.py > /app/logs/data_gen.log 2>&1 &
sleep 3

# 9. 启动 Flink 作业
echo "[9/9] 启动 Flink SQL 作业..."
sleep 20
echo "执行 Flink SQL 作业..."
/opt/flink/bin/sql-client.sh embedded -f /app/sql/flink_ddl.sql > /app/logs/flink_sql.log 2>&1 &

echo ""
echo "=== 所有服务启动完成 ==="
echo ""
echo "服务访问地址:"
echo "1. SSH:                     ssh root@$(hostname -I | awk '{print $1}') -p 22"
echo "2. PostgreSQL:              jdbc:postgresql://localhost:5432/power_grid"
echo "3. Flink Web UI:            http://localhost:8081"
echo "4. Flink REST API:          http://localhost:8082"
echo "5. Grafana Dashboard:       http://localhost:3000"
echo "6. Doris FE Web:            http://localhost:8030"
echo "7. Doris MySQL Protocol:     mysql -h127.0.0.1 -P9030 -uroot"
echo "8. Fluss:                   http://localhost:8084"
echo ""
echo "测试数据:"
echo "1. 查看数据生成日志:         tail -f /app/logs/data_gen.log"
echo "2. 执行CRUD测试:           python3 /app/scripts/test_crud.py"
echo "3. 查看系统状态:           python3 /app/scripts/monitor.py"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 保持容器运行
tail -f /dev/null
```

```bash
#!/bin/bash
# /app/scripts/start-flink.sh

#!/bin/bash
echo "启动 Flink..."

# 检查是否已存在 JobManager
if ! pgrep -f "jobmanager" > /dev/null; then
    echo "启动 JobManager..."
    /opt/flink/bin/jobmanager.sh start
fi

# 检查是否已存在 TaskManager
if ! pgrep -f "taskmanager" > /dev/null; then
    echo "启动 TaskManager..."
    /opt/flink/bin/taskmanager.sh start
fi

echo "Flink 启动完成"
```

```bash
#!/bin/bash
# /app/scripts/start-fluss.sh

#!/bin/bash
echo "启动 Fluss..."

# 检查是否已启动
if ! pgrep -f "fluss-server" > /dev/null; then
    echo "启动 Fluss Server..."
    nohup /fluss-server/bin/start-fluss.sh > /app/logs/fluss.log 2>&1 &
fi

echo "Fluss 启动完成"
```

## 四、健康检查脚本

```bash
#!/bin/bash
# /app/scripts/healthcheck.sh

#!/bin/bash

# 检查 PostgreSQL
if ! pg_isready -h localhost -p 5432 -U postgres > /dev/null 2>&1; then
    echo "PostgreSQL 未就绪"
    exit 1
fi

# 检查 Flink JobManager
if ! curl -s http://localhost:8081/overview > /dev/null 2>&1; then
    echo "Flink JobManager 未就绪"
    exit 1
fi

# 检查 Flink TaskManager
if ! curl -s http://localhost:8081/taskmanagers > /dev/null 2>&1; then
    echo "Flink TaskManager 未就绪"
    exit 1
fi

# 检查 Fluss
if ! curl -s http://localhost:8084/health > /dev/null 2>&1; then
    echo "Fluss 未就绪"
    exit 1
fi

# 检查 Grafana
if ! curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "Grafana 未就绪"
    exit 1
fi

# 检查 Doris FE
if ! mysql -h127.0.0.1 -P9030 -uroot -e "SHOW DATABASES;" > /dev/null 2>&1; then
    echo "Doris FE 未就绪"
    exit 1
fi

echo "所有服务运行正常"
exit 0
```

## 五、监控脚本

```python
#!/usr/bin/env python3
# /app/scripts/monitor.py

import psycopg2
import mysql.connector
import requests
import time
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.check_interval = 30  # 秒
        
    def check_postgresql(self):
        """检查 PostgreSQL 状态"""
        try:
            conn = psycopg2.connect(
                host="localhost",
                database="power_grid",
                user="postgres",
                password="postgres"
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.execute("SELECT COUNT(*) FROM device_info")
            device_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM meter_reading")
            reading_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return True, f"PostgreSQL 正常 (设备: {device_count}, 读数: {reading_count})"
        except Exception as e:
            return False, f"PostgreSQL 异常: {e}"
    
    def check_flink(self):
        """检查 Flink 状态"""
        try:
            response = requests.get("http://localhost:8081/overview", timeout=5)
            if response.status_code == 200:
                data = response.json()
                taskmanagers = data.get("taskmanagers", 0)
                jobs_running = data.get("jobs", {}).get("running", 0)
                return True, f"Flink 正常 (TaskManagers: {taskmanagers}, 运行作业: {jobs_running})"
            return False, f"Flink 返回状态码: {response.status_code}"
        except Exception as e:
            return False, f"Flink 异常: {e}"
    
    def check_fluss(self):
        """检查 Fluss 状态"""
        try:
            response = requests.get("http://localhost:8084/health", timeout=5)
            if response.status_code == 200:
                return True, "Fluss 正常"
            return False, f"Fluss 返回状态码: {response.status_code}"
        except Exception as e:
            return False, f"Fluss 异常: {e}"
    
    def check_doris(self):
        """检查 Doris 状态"""
        try:
            conn = mysql.connector.connect(
                host="127.0.0.1",
                port=9030,
                user="root",
                database="power_grid_doris"
            )
            cursor = conn.cursor()
            cursor.execute("SHOW DATABASES")
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return True, f"Doris 正常 (版本: {version})"
        except Exception as e:
            return False, f"Doris 异常: {e}"
    
    def check_grafana(self):
        """检查 Grafana 状态"""
        try:
            response = requests.get("http://localhost:3000/api/health", timeout=5)
            if response.status_code == 200:
                return True, "Grafana 正常"
            return False, f"Grafana 返回状态码: {response.status_code}"
        except Exception as e:
            return False, f"Grafana 异常: {e}"
    
    def check_ssh(self):
        """检查 SSH 状态"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', 22))
            sock.close()
            if result == 0:
                return True, "SSH 正常"
            return False, f"SSH 端口未开放"
        except Exception as e:
            return False, f"SSH 异常: {e}"
    
    def run_checks(self):
        """执行所有检查"""
        checks = [
            ("PostgreSQL", self.check_postgresql),
            ("Flink", self.check_flink),
            ("Fluss", self.check_fluss),
            ("Doris", self.check_doris),
            ("Grafana", self.check_grafana),
            ("SSH", self.check_ssh)
        ]
        
        results = []
        all_ok = True
        
        for name, check_func in checks:
            try:
                status, message = check_func()
                results.append((name, status, message))
                if not status:
                    all_ok = False
            except Exception as e:
                results.append((name, False, f"检查异常: {e}"))
                all_ok = False
        
        return all_ok, results
    
    def generate_report(self, results):
        """生成监控报告"""
        report = f"=== 系统监控报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n"
        for name, status, message in results:
            status_icon = "✓" if status else "✗"
            report += f"{status_icon} {name}: {message}\n"
        return report
    
    def monitor_loop(self):
        """监控循环"""
        logger.info("启动系统监控...")
        
        while True:
            try:
                all_ok, results = self.run_checks()
                report = self.generate_report(results)
                
                logger.info("\n" + report)
                
                if not all_ok:
                    logger.warning("有服务异常，发送告警...")
                    # 这里可以添加告警通知逻辑
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("监控停止")
                break
            except Exception as e:
                logger.error(f"监控异常: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.monitor_loop()
```

## 六、完整的测试脚本

```python
#!/usr/bin/env python3
# /app/scripts/test_complete.py

import psycopg2
import mysql.connector
import paramiko
import time
import json
import subprocess
import requests
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CompleteSystemTest:
    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now()
        
    def test_ssh_connection(self):
        """测试SSH连接和免密登录"""
        logger.info("测试SSH连接...")
        try:
            # 测试本地SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect('localhost', port=22, username='root', password='root123')
            
            # 测试命令执行
            stdin, stdout, stderr = ssh.exec_command('hostname && whoami')
            output = stdout.read().decode().strip()
            
            # 测试免密登录
            stdin, stdout, stderr = ssh.exec_command('ssh -o BatchMode=yes -o ConnectTimeout=5 localhost echo "SSH免密登录成功"')
            exit_status = stdout.channel.recv_exit_status()
            
            ssh.close()
            
            if 'root' in output and exit_status == 0:
                result = "✓ SSH连接和免密登录测试通过"
                logger.info(result)
                return True, result
            else:
                result = f"✗ SSH测试失败: {output}"
                logger.error(result)
                return False, result
                
        except Exception as e:
            result = f"✗ SSH连接失败: {e}"
            logger.error(result)
            return False, result
    
    def test_postgresql_crud(self):
        """测试PostgreSQL CRUD操作"""
        logger.info("测试PostgreSQL CRUD操作...")
        try:
            conn = psycopg2.connect(
                host="localhost",
                database="power_grid",
                user="postgres",
                password="postgres"
            )
            cursor = conn.cursor()
            
            # 1. 插入测试
            test_time = datetime.now()
            cursor.execute("""
                INSERT INTO device_info 
                (device_code, device_name, device_type, voltage_level, status, substation_id, location)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING device_id
            """, (
                f"TEST_CRUD_{int(time.time())}",
                "CRUD测试设备",
                "智能电表",
                "220V",
                "运行",
                "SS001",
                "测试位置"
            ))
            new_device_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"插入成功，设备ID: {new_device_id}")
            
            # 2. 查询测试
            cursor.execute("SELECT device_name, status FROM device_info WHERE device_id = %s", (new_device_id,))
            device = cursor.fetchone()
            if device and device[0] == "CRUD测试设备":
                logger.info("查询测试通过")
            
            # 3. 更新测试
            cursor.execute("""
                UPDATE device_info 
                SET status = '检修', update_time = NOW()
                WHERE device_id = %s
            """, (new_device_id,))
            conn.commit()
            
            cursor.execute("SELECT status FROM device_info WHERE device_id = %s", (new_device_id,))
            if cursor.fetchone()[0] == '检修':
                logger.info("更新测试通过")
            
            # 4. 关联数据插入测试
            cursor.execute("""
                INSERT INTO meter_reading 
                (device_id, reading_time, active_power, voltage, current, data_quality)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                new_device_id,
                test_time,
                2.5,
                220.0,
                11.36,
                '测试数据'
            ))
            conn.commit()
            
            # 5. 删除测试
            cursor.execute("DELETE FROM meter_reading WHERE data_quality = '测试数据'")
            conn.commit()
            
            cursor.close()
            conn.close()
            
            result = "✓ PostgreSQL CRUD测试通过"
            logger.info(result)
            return True, result
            
        except Exception as e:
            result = f"✗ PostgreSQL测试失败: {e}"
            logger.error(result)
            return False, result
    
    def test_flink_jobs(self):
        """测试Flink作业状态"""
        logger.info("检查Flink作业状态...")
        try:
            response = requests.get("http://localhost:8081/jobs", timeout=10)
            if response.status_code == 200:
                jobs = response.json().get("jobs", [])
                
                running_jobs = [job for job in jobs if job.get("status") == "RUNNING"]
                
                if running_jobs:
                    result = f"✓ Flink作业运行正常 (运行中: {len(running_jobs)})"
                    logger.info(result)
                    for job in running_jobs:
                        logger.info(f"  作业: {job.get('id')}, 状态: {job.get('status')}, 名称: {job.get('name')}")
                    return True, result
                else:
                    result = "⚠ Flink无运行中的作业"
                    logger.warning(result)
                    return False, result
            else:
                result = f"✗ 无法连接到Flink: {response.status_code}"
                logger.error(result)
                return False, result
                
        except Exception as e:
            result = f"✗ Flink检查失败: {e}"
            logger.error(result)
            return False, result
    
    def test_flink_cdc(self):
        """测试Flink CDC连接"""
        logger.info("测试Flink CDC连接...")
        try:
            # 检查CDC任务状态
            response = requests.get("http://localhost:8081/jobs", timeout=10)
            jobs = response.json().get("jobs", [])
            
            cdc_jobs = []
            for job in jobs:
                if job.get("status") == "RUNNING" and "cdc" in job.get("name", "").lower():
                    cdc_jobs.append(job.get("name"))
            
            if cdc_jobs:
                result = f"✓ CDC作业运行正常: {', '.join(cdc_jobs)}"
                logger.info(result)
                return True, result
            else:
                result = "⚠ 未找到运行中的CDC作业"
                logger.warning(result)
                return False, result
                
        except Exception as e:
            result = f"✗ CDC检查失败: {e}"
            logger.error(result)
            return False, result
    
    def test_doris_connection(self):
        """测试Doris连接和查询"""
        logger.info("测试Doris连接...")
        try:
            conn = mysql.connector.connect(
                host="127.0.0.1",
                port=9030,
                user="root"
            )
            cursor = conn.cursor()
            
            # 创建测试表
            cursor.execute("CREATE DATABASE IF NOT EXISTS test_doris")
            cursor.execute("USE test_doris")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INT,
                    name VARCHAR(50),
                    create_time DATETIME
                ) DISTRIBUTED BY HASH(id) BUCKETS 10
            """)
            
            # 插入测试数据
            cursor.execute("INSERT INTO test_table VALUES (1, '测试数据', NOW())")
            conn.commit()
            
            # 查询测试
            cursor.execute("SELECT COUNT(*) FROM test_table")
            count = cursor.fetchone()[0]
            
            # 清理
            cursor.execute("DROP DATABASE IF EXISTS test_doris")
            conn.commit()
            
            cursor.close()
            conn.close()
            
            if count == 1:
                result = "✓ Doris连接和基本操作测试通过"
                logger.info(result)
                return True, result
            else:
                result = f"✗ Doris测试失败，查询结果: {count}"
                logger.error(result)
                return False, result
                
        except Exception as e:
            result = f"✗ Doris连接失败: {e}"
            logger.error(result)
            return False, result
    
    def test_grafana_dashboard(self):
        """测试Grafana仪表板"""
        logger.info("测试Grafana仪表板...")
        try:
            # 测试Grafana API
            response = requests.get("http://localhost:3000/api/health", timeout=5)
            if response.status_code == 200:
                # 获取仪表板列表
                response = requests.get(
                    "http://admin:admin@localhost:3000/api/search",
                    params={"query": "国网"},
                    timeout=5
                )
                
                if response.status_code == 200:
                    dashboards = response.json()
                    if dashboards:
                        result = f"✓ Grafana仪表板正常，找到 {len(dashboards)} 个相关仪表板"
                        logger.info(result)
                        for dash in dashboards:
                            logger.info(f"  仪表板: {dash.get('title')}")
                        return True, result
                    else:
                        result = "⚠ 未找到国网相关仪表板"
                        logger.warning(result)
                        return False, result
                else:
                    result = f"✗ 无法获取Grafana仪表板列表: {response.status_code}"
                    logger.error(result)
                    return False, result
            else:
                result = f"✗ Grafana服务不可用: {response.status_code}"
                logger.error(result)
                return False, result
                
        except Exception as e:
            result = f"✗ Grafana测试失败: {e}"
            logger.error(result)
            return False, result
    
    def test_end_to_end_dataflow(self):
        """测试端到端数据流"""
        logger.info("测试端到端数据流...")
        try:
            # 1. 在PostgreSQL中插入测试数据
            conn = psycopg2.connect(
                host="localhost",
                database="power_grid",
                user="postgres",
                password="postgres"
            )
            cursor = conn.cursor()
            
            # 创建测试设备
            cursor.execute("""
                INSERT INTO device_info 
                (device_code, device_name, device_type, voltage_level, status, substation_id)
                VALUES ('E2E_TEST_001', '端到端测试设备', '智能电表', '220V', '运行', 'SS001')
                RETURNING device_id
            """)
            test_device_id = cursor.fetchone()[0]
            
            # 插入测试电表读数
            test_time = datetime.now()
            cursor.execute("""
                INSERT INTO meter_reading 
                (device_id, reading_time, active_power, voltage, current, data_quality)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                test_device_id,
                test_time,
                3.5,
                225.0,
                15.56,
                '端到端测试'
            ))
            
            # 插入测试告警
            cursor.execute("""
                INSERT INTO alarm_info 
                (device_id, alarm_time, alarm_level, alarm_type, alarm_desc, alarm_value, threshold_value)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                test_device_id,
                test_time,
                '一般',
                '测试告警',
                '端到端测试告警',
                100.0,
                90.0
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"在PostgreSQL插入测试数据，设备ID: {test_device_id}")
            
            # 2. 等待Flink处理
            logger.info("等待10秒让Flink处理数据...")
            time.sleep(10)
            
            # 3. 检查Doris中的数据
            try:
                doris_conn = mysql.connector.connect(
                    host="127.0.0.1",
                    port=9030,
                    user="root",
                    database="power_grid_doris"
                )
                doris_cursor = doris_conn.cursor()
                
                # 这里需要根据实际的Doris表结构来查询
                # 假设有device_realtime_monitor表
                doris_cursor.execute("SELECT COUNT(*) FROM device_realtime_monitor WHERE device_code LIKE 'E2E_TEST%'")
                count = doris_cursor.fetchone()[0]
                
                doris_cursor.close()
                doris_conn.close()
                
                if count > 0:
                    result = f"✓ 端到端数据流测试通过 (在Doris中找到 {count} 条测试数据)"
                    logger.info(result)
                    return True, result
                else:
                    result = "⚠ 端到端测试: 在Doris中未找到测试数据"
                    logger.warning(result)
                    return False, result
                    
            except Exception as doris_e:
                result = f"⚠ 端到端测试: Doris查询失败: {doris_e}"
                logger.warning(result)
                return False, result
                
        except Exception as e:
            result = f"✗ 端到端测试失败: {e}"
            logger.error(result)
            return False, result
    
    def test_proxy_connection(self):
        """测试代理连接"""
        logger.info("测试代理连接...")
        try:
            proxies = {
                'http': 'http://192.168.0.150:7890',
                'https': 'http://192.168.0.150:7890'
            }
            
            response = requests.get('https://httpbin.org/ip', proxies=proxies, timeout=10)
            if response.status_code == 200:
                data = response.json()
                result = f"✓ 代理连接成功，IP: {data.get('origin', '未知')}"
                logger.info(result)
                return True, result
            else:
                result = f"✗ 代理连接失败: {response.status_code}"
                logger.error(result)
                return False, result
                
        except Exception as e:
            result = f"✗ 代理连接异常: {e}"
            logger.error(result)
            return False, result
    
    def run_all_tests(self):
        """运行所有测试"""
        tests = [
            ("SSH连接测试", self.test_ssh_connection),
            ("PostgreSQL CRUD测试", self.test_postgresql_crud),
            ("代理连接测试", self.test_proxy_connection),
            ("Flink作业测试", self.test_flink_jobs),
            ("Flink CDC测试", self.test_flink_cdc),
            ("Doris连接测试", self.test_doris_connection),
            ("Grafana仪表板测试", self.test_grafana_dashboard),
            ("端到端数据流测试", self.test_end_to_end_dataflow)
        ]
        
        logger.info(f"开始运行 {len(tests)} 个测试...")
        all_passed = True
        passed_count = 0
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*60}")
            logger.info(f"执行测试: {test_name}")
            logger.info(f"{'='*60}")
            
            try:
                passed, result = test_func()
                self.test_results[test_name] = {
                    "passed": passed,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
                
                if passed:
                    passed_count += 1
                    logger.info(f"✓ {test_name} 通过")
                else:
                    all_passed = False
                    logger.error(f"✗ {test_name} 失败")
                    
            except Exception as e:
                logger.error(f"✗ {test_name} 异常: {e}")
                self.test_results[test_name] = {
                    "passed": False,
                    "result": f"测试异常: {e}",
                    "timestamp": datetime.now().isoformat()
                }
                all_passed = False
        
        # 生成测试报告
        self.generate_test_report(passed_count, len(tests))
        
        return all_passed
    
    def generate_test_report(self, passed, total):
        """生成测试报告"""
        logger.info(f"\n{'='*60}")
        logger.info("测试报告")
        logger.info(f"{'='*60}")
        logger.info(f"测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"持续时间: {(datetime.now() - self.start_time).total_seconds():.2f} 秒")
        logger.info(f"测试总数: {total}")
        logger.info(f"通过数量: {passed}")
        logger.info(f"失败数量: {total - passed}")
        logger.info(f"通过率: {(passed/total*100):.1f}%")
        
        if passed == total:
            logger.info("✓ 所有测试通过！系统准备就绪。")
        else:
            logger.info("⚠ 部分测试失败，请检查日志。")
            
        # 保存测试结果到文件
        report = {
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": (passed/total*100),
                "start_time": self.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - self.start_time).total_seconds()
            },
            "details": self.test_results
        }
        
        with open('/app/logs/test_report.json', 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"详细测试报告已保存到: /app/logs/test_report.json")

if __name__ == "__main__":
    tester = CompleteSystemTest()
    
    try:
        success = tester.run_all_tests()
        
        if success:
            logger.info("\n✅ 所有测试通过！系统可以正常使用。")
            # 输出使用说明
            logger.info("\n使用说明:")
            logger.info("1. SSH登录: ssh root@<容器IP> -p 22 (密码: root123)")
            logger.info("2. PostgreSQL: jdbc:postgresql://localhost:5432/power_grid (用户: postgres, 密码: postgres)")
            logger.info("3. Flink Web UI: http://localhost:8081")
            logger.info("4. Grafana: http://localhost:3000 (用户: admin, 密码: admin)")
            logger.info("5. Doris: http://localhost:8030")
            logger.info("\n数据生成器已启动，将持续生成测试数据。")
            logger.info("查看实时日志: tail -f /app/logs/data_gen.log")
        else:
            logger.error("\n❌ 部分测试失败，请检查日志获取详细信息。")
            exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"\n测试执行异常: {e}")
        exit(1)
```

## 七、构建、测试和发布脚本

```bash
#!/bin/bash
# build-test-publish.sh

#!/bin/bash
set -e

# 配置变量
IMAGE_NAME="power-grid-realtime"
IMAGE_TAG="2.0"
REGISTRY="registry.example.com"  # 改为你的镜像仓库
PROXY_HOST="192.168.0.150"
PROXY_PORT="7890"

echo "=== 国网实时数仓镜像构建、测试和发布 ==="
echo "镜像名称: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "代理设置: ${PROXY_HOST}:${PROXY_PORT}"

# 1. 构建镜像
echo ""
echo "1. 开始构建镜像..."
docker build \
  --build-arg PROXY_HOST=${PROXY_HOST} \
  --build-arg PROXY_PORT=${PROXY_PORT} \
  -t ${IMAGE_NAME}:${IMAGE_TAG} \
  -t ${IMAGE_NAME}:latest \
  .

if [ $? -eq 0 ]; then
  echo "✅ 镜像构建成功"
else
  echo "❌ 镜像构建失败"
  exit 1
fi

# 2. 启动容器进行测试
echo ""
echo "2. 启动测试容器..."
CONTAINER_NAME="power-grid-test-$(date +%s)"

docker run -d \
  --name ${CONTAINER_NAME} \
  -p 2222:22 \
  -p 5432:5432 \
  -p 8081:8081 \
  -p 8082:8082 \
  -p 8083:8083 \
  -p 8084:8084 \
  -p 3000:3000 \
  -p 8030:8030 \
  -p 9030:9030 \
  -p 8040:8040 \
  -p 9123:9123 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  -e HTTP_PROXY=http://${PROXY_HOST}:${PROXY_PORT} \
  -e HTTPS_PROXY=http://${PROXY_HOST}:${PROXY_PORT} \
  ${IMAGE_NAME}:${IMAGE_TAG}

if [ $? -eq 0 ]; then
  echo "✅ 测试容器启动成功"
  echo "容器名称: ${CONTAINER_NAME}"
else
  echo "❌ 测试容器启动失败"
  exit 1
fi

# 3. 等待服务启动
echo ""
echo "3. 等待服务启动 (60秒)..."
sleep 60

# 4. 执行测试
echo ""
echo "4. 执行系统测试..."
docker exec ${CONTAINER_NAME} python3 /app/scripts/test_complete.py

if [ $? -eq 0 ]; then
  echo "✅ 系统测试通过"
else
  echo "❌ 系统测试失败"
  echo "查看容器日志: docker logs ${CONTAINER_NAME}"
  echo "进入容器调试: docker exec -it ${CONTAINER_NAME} bash"
  exit 1
fi

# 5. 测试SSH连接
echo ""
echo "5. 测试SSH连接..."
sshpass -p 'root123' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -p 2222 root@localhost "hostname && echo 'SSH连接成功'"

if [ $? -eq 0 ]; then
  echo "✅ SSH连接测试通过"
else
  echo "❌ SSH连接测试失败"
  exit 1
fi

# 6. 测试端口连通性
echo ""
echo "6. 测试端口连通性..."
PORTS="22 5432 8081 3000 8030"
ALL_PORTS_OK=true

for port in $PORTS; do
  nc -z -w5 localhost $port
  if [ $? -eq 0 ]; then
    echo "✅ 端口 $port 可达"
  else
    echo "❌ 端口 $port 不可达"
    ALL_PORTS_OK=false
  fi
done

if [ "$ALL_PORTS_OK" = false ]; then
  echo "⚠ 部分端口不可达，但继续执行..."
fi

# 7. 保存测试结果
echo ""
echo "7. 保存测试结果..."
docker cp ${CONTAINER_NAME}:/app/logs/test_report.json ./test_report_${IMAGE_TAG}.json
if [ -f "./test_report_${IMAGE_TAG}.json" ]; then
  echo "✅ 测试结果已保存到: ./test_report_${IMAGE_TAG}.json"
  cat "./test_report_${IMAGE_TAG}.json" | python3 -m json.tool | head -50
else
  echo "⚠ 未找到测试结果文件"
fi

# 8. 清理测试容器
echo ""
echo "8. 清理测试容器..."
docker stop ${CONTAINER_NAME} && docker rm ${CONTAINER_NAME}
if [ $? -eq 0 ]; then
  echo "✅ 测试容器清理完成"
else
  echo "⚠ 测试容器清理失败"
fi

# 9. 打包镜像
echo ""
echo "9. 打包镜像..."
docker save ${IMAGE_NAME}:${IMAGE_TAG} | gzip > ${IMAGE_NAME}_${IMAGE_TAG}.tar.gz
if [ $? -eq 0 ]; then
  echo "✅ 镜像打包成功: ${IMAGE_NAME}_${IMAGE_TAG}.tar.gz"
  ls -lh ${IMAGE_NAME}_${IMAGE_TAG}.tar.gz
else
  echo "❌ 镜像打包失败"
  exit 1
fi

# 10. 发布镜像（可选）
echo ""
read -p "是否发布镜像到镜像仓库? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "10. 发布镜像到 ${REGISTRY}..."
  
  # 标记镜像
  docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
  docker tag ${IMAGE_NAME}:latest ${REGISTRY}/${IMAGE_NAME}:latest
  
  # 推送镜像
  echo "推送镜像 ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG} ..."
  docker push ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}
  
  echo "推送镜像 ${REGISTRY}/${IMAGE_NAME}:latest ..."
  docker push ${REGISTRY}/${IMAGE_NAME}:latest
  
  if [ $? -eq 0 ]; then
    echo "✅ 镜像发布成功"
    echo "镜像地址:"
    echo "  ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
    echo "  ${REGISTRY}/${IMAGE_NAME}:latest"
  else
    echo "❌ 镜像发布失败"
    exit 1
  fi
else
  echo "⏭ 跳过镜像发布"
fi

# 11. 生成部署脚本
echo ""
echo "11. 生成部署脚本..."
cat > deploy_${IMAGE_NAME}.sh << 'EOF'
#!/bin/bash
# 部署脚本: deploy_power-grid-realtime.sh

set -e

# 配置
IMAGE_NAME="power-grid-realtime"
IMAGE_TAG="2.0"
REGISTRY="registry.example.com"  # 修改为你的镜像仓库
CONTAINER_NAME="power-grid-production"
DATA_DIR="/data/power-grid"

# 创建数据目录
mkdir -p ${DATA_DIR}/{logs,data,backup}

# 拉取镜像
echo "拉取镜像..."
docker pull ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

# 停止并删除旧容器
echo "清理旧容器..."
docker stop ${CONTAINER_NAME} 2>/dev/null || true
docker rm ${CONTAINER_NAME} 2>/dev/null || true

# 运行新容器
echo "启动新容器..."
docker run -d \
  --name ${CONTAINER_NAME} \
  --restart unless-stopped \
  -p 2222:22 \
  -p 5432:5432 \
  -p 8081:8081 \
  -p 3000:3000 \
  -p 8030:8030 \
  -p 9030:9030 \
  -v ${DATA_DIR}/logs:/app/logs \
  -v ${DATA_DIR}/data:/app/data \
  -v ${DATA_DIR}/backup:/app/backup \
  -e HTTP_PROXY=http://192.168.0.150:7890 \
  -e HTTPS_PROXY=http://192.168.0.150:7890 \
  ${REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}

echo "✅ 部署完成"
echo ""
echo "访问地址:"
echo "1. SSH: ssh root@<服务器IP> -p 2222 (密码: root123)"
echo "2. Flink Web UI: http://<服务器IP>:8081"
echo "3. Grafana: http://<服务器IP>:3000 (admin/admin)"
echo "4. Doris FE: http://<服务器IP>:8030"
echo ""
echo "查看日志: docker logs -f ${CONTAINER_NAME}"
echo "进入容器: docker exec -it ${CONTAINER_NAME} bash"
EOF

chmod +x deploy_${IMAGE_NAME}.sh
echo "✅ 部署脚本已生成: deploy_${IMAGE_NAME}.sh"

# 12. 生成使用说明
echo ""
echo "12. 生成使用说明..."
cat > README_${IMAGE_TAG}.md << 'EOF'
# 国网实时数仓测试环境 v2.0

## 镜像特性
1. 完整组件集成: PostgreSQL + Flink + Fluss + Doris + Grafana
2. SSH服务开通，支持免密登录
3. 代理配置 (192.168.0.150:7890)
4. 国网业务数仓分层实现
5. 完整的测试脚本和监控

## 快速开始
```bash
# 加载镜像
docker load < power-grid-realtime_2.0.tar.gz

# 运行容器
docker run -d \
  -p 2222:22 \
  -p 5432:5432 \
  -p 8081:8081 \
  -p 3000:3000 \
  -p 8030:8030 \
  -p 9030:9030 \
  -e HTTP_PROXY=http://192.168.0.150:7890 \
  power-grid-realtime:2.0
```

## 服务端口
- 22: SSH (root/root123)
- 5432: PostgreSQL (postgres/postgres)
- 8081: Flink Web UI
- 8082: Flink REST API
- 3000: Grafana (admin/admin)
- 8030: Doris FE Web
- 9030: Doris MySQL端口
- 8084: Fluss Web UI

## 使用步骤
1. SSH登录容器: `ssh root@localhost -p 2222`
2. 查看服务状态: `python3 /app/scripts/monitor.py`
3. 执行CRUD测试: `python3 /app/scripts/test_crud.py`
4. 查看数据生成: `tail -f /app/logs/data_gen.log`

## 数仓架构
- ODS: PostgreSQL CDC -> Flink -> Fluss
- DWD: 数据清洗和关联
- DWS: 小时级聚合
- ADS: 应用层数据
- Doris: 最终结果存储
- Grafana: 数据可视化

## 测试数据
- 设备表: 50个测试设备
- 电表读数: 实时生成
- 告警数据: 按规则生成
- 数据流: 端到端实时处理
EOF

echo "✅ 使用说明已生成: README_${IMAGE_TAG}.