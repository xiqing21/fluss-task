# 国网实时数仓测试环境 Docker 镜像
# 基于预配置的 Flink + Fluss Delta Join 示例镜像
FROM xuyangzzz/delta_join_example:1.0

# 设置环境变量（基于基础镜像的配置）
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Shanghai
# 基础镜像中已经配置了 JAVA_HOME, FLINK_HOME, FLUSS_HOME
# 添加额外的环境变量
ENV DORIS_HOME=/opt/doris
ENV PATH=$PATH:$DORIS_HOME/bin

# 代理配置环境变量（可在运行时覆盖）
ENV HTTP_PROXY="http://host.docker.internal:7890"
ENV HTTPS_PROXY="https://host.docker.internal:7890"
ENV NO_PROXY="localhost,127.0.0.1"

# 配置 apt 使用代理
RUN echo 'Acquire::http::Proxy "http://host.docker.internal:7890";' > /etc/apt/apt.conf.d/01proxy && \
    echo 'Acquire::https::Proxy "https://host.docker.internal:7890";' >> /etc/apt/apt.conf.d/01proxy

# 创建工作目录
WORKDIR /opt

# 安装额外的系统包和 PostgreSQL
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    curl \
    vim \
    nano \
    htop \
    net-tools \
    telnet \
    openssh-server \
    supervisor \
    python3 \
    python3-pip \
    postgresql \
    postgresql-client \
    postgresql-contrib \
    sudo \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 配置 SSH 服务
RUN mkdir /var/run/sshd \
    && echo 'root:root123' | chpasswd \
    && sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && mkdir -p /root/.ssh \
    && chmod 700 /root/.ssh

# 创建 SSH 密钥对
RUN ssh-keygen -t rsa -b 4096 -f /root/.ssh/id_rsa -N "" \
    && cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys \
    && chmod 600 /root/.ssh/authorized_keys

# 配置 PostgreSQL
RUN service postgresql start \
    && sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';" \
    && sudo -u postgres createdb power_grid \
    && service postgresql stop

# 配置 PostgreSQL 允许远程连接
RUN PG_VERSION=$(ls /etc/postgresql/) && \
    echo "host all all 0.0.0.0/0 md5" >> /etc/postgresql/$PG_VERSION/main/pg_hba.conf && \
    echo "listen_addresses = '*'" >> /etc/postgresql/$PG_VERSION/main/postgresql.conf && \
    echo "wal_level = logical" >> /etc/postgresql/$PG_VERSION/main/postgresql.conf && \
    echo "max_wal_senders = 10" >> /etc/postgresql/$PG_VERSION/main/postgresql.conf && \
    echo "max_replication_slots = 10" >> /etc/postgresql/$PG_VERSION/main/postgresql.conf

# 下载并安装 Apache Doris 1.2.7
RUN wget -q https://archive.apache.org/dist/doris/1.2/1.2.7/apache-doris-1.2.7-bin-x64.tar.gz \
    && tar -xzf apache-doris-1.2.7-bin-x64.tar.gz \
    && mv apache-doris-1.2.7-bin-x64 doris \
    && rm apache-doris-1.2.7-bin-x64.tar.gz

# 安装 Grafana
RUN wget -q -O - https://packages.grafana.com/gpg.key | apt-key add - \
    && echo "deb https://packages.grafana.com/oss/deb stable main" | tee -a /etc/apt/sources.list.d/grafana.list \
    && apt-get update \
    && apt-get install -y grafana \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip3 install --no-cache-dir \
    psycopg2-binary \
    faker \
    requests \
    pyyaml \
    schedule

# 创建配置目录
RUN mkdir -p /opt/config /opt/scripts /opt/logs

# 复制配置文件
COPY config/ /opt/config/
COPY scripts/ /opt/scripts/

# 设置脚本执行权限
RUN chmod +x /opt/scripts/*.sh /opt/scripts/*.py

# 配置 Supervisor
COPY config/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 创建数据目录
RUN mkdir -p /opt/data/postgresql /opt/data/flink /opt/data/fluss /opt/data/doris /opt/data/grafana

# 设置权限
RUN chown -R postgres:postgres /opt/data/postgresql \
    && chown -R grafana:grafana /opt/data/grafana

# 暴露端口
# SSH: 22, PostgreSQL: 5432, Flink Web: 8081, Flink REST: 8082
# Fluss: 8084, Fluss Bootstrap: 9123, Grafana: 3000
# Doris FE: 8030, Doris MySQL: 9030, Doris BE: 8040
EXPOSE 22 5432 8081 8082 8084 9123 3000 8030 9030 8040

# 设置启动脚本
COPY scripts/entrypoint.sh /opt/scripts/entrypoint.sh
RUN chmod +x /opt/scripts/entrypoint.sh

# 启动命令
CMD ["/opt/scripts/entrypoint.sh"]