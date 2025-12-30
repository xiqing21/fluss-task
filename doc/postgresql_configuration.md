# PostgreSQL 数据源环境配置文档

## 概述

本文档描述了国网实时数仓测试环境中 PostgreSQL 13 数据源的完整配置，包括安装、配置、数据结构、CDC 设置和测试验证。

## 配置要求

根据需求文档 Requirements 4.1-4.5，PostgreSQL 数据源环境需要满足以下要求：

- **4.1**: 集成 PostgreSQL 13 作为源数据库
- **4.2**: 创建国网业务相关的数据表结构
- **4.3**: 持续生成模拟的国网业务数据
- **4.4**: 支持对源数据库的 CRUD 操作测试
- **4.5**: 配置 CDC 复制槽以支持 Flink CDC 连接

## 安装配置

### 1. PostgreSQL 13 安装

在 Dockerfile 中配置：

```dockerfile
# 安装 PostgreSQL 13
RUN apt-get update && apt-get install -y \
    postgresql-13 \
    postgresql-client-13 \
    postgresql-contrib-13 \
    && rm -rf /var/lib/apt/lists/*
```

### 2. 数据库配置

#### 基本配置
- 数据库名称: `power_grid`
- 用户名: `postgres`
- 密码: `postgres`
- 端口: `5432`

#### CDC 配置
在 `/etc/postgresql/13/main/postgresql.conf` 中配置：

```conf
# CDC 相关配置
wal_level = logical
max_wal_senders = 10
max_replication_slots = 10
```

#### 网络配置
在 `/etc/postgresql/13/main/pg_hba.conf` 中配置：

```conf
# 允许远程连接
host all all 0.0.0.0/0 md5
```

### 3. 服务管理

通过 Supervisor 管理 PostgreSQL 服务：

```ini
[program:postgresql]
command=/usr/lib/postgresql/13/bin/postgres -D /var/lib/postgresql/13/main -c config_file=/etc/postgresql/13/main/postgresql.conf
user=postgres
autostart=true
autorestart=true
stdout_logfile=/opt/logs/postgresql.log
stderr_logfile=/opt/logs/postgresql_error.log
```

## 数据库结构

### 1. 设备信息表 (device_info)

存储电力设备的基本信息：

```sql
CREATE TABLE device_info (
    device_id BIGSERIAL PRIMARY KEY,
    device_code VARCHAR(50) UNIQUE NOT NULL,
    device_name VARCHAR(100) NOT NULL,
    device_type VARCHAR(50) NOT NULL,
    voltage_level VARCHAR(20),
    status VARCHAR(20) DEFAULT '运行',
    substation_id VARCHAR(50),
    location VARCHAR(200),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. 电表读数表 (meter_reading)

存储电表的实时读数数据：

```sql
CREATE TABLE meter_reading (
    reading_id BIGSERIAL PRIMARY KEY,
    device_id BIGINT REFERENCES device_info(device_id),
    reading_time TIMESTAMP NOT NULL,
    active_power DECIMAL(10,2),
    voltage DECIMAL(8,2),
    current DECIMAL(8,2),
    power_factor DECIMAL(4,3),
    energy_consumption DECIMAL(12,2),
    data_quality VARCHAR(50) DEFAULT '正常',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. 告警信息表 (alarm_info)

存储设备告警信息：

```sql
CREATE TABLE alarm_info (
    alarm_id BIGSERIAL PRIMARY KEY,
    device_id BIGINT REFERENCES device_info(device_id),
    alarm_time TIMESTAMP NOT NULL,
    alarm_level VARCHAR(20) NOT NULL,
    alarm_type VARCHAR(50) NOT NULL,
    alarm_desc TEXT,
    alarm_value DECIMAL(10,2),
    threshold_value DECIMAL(10,2),
    status VARCHAR(20) DEFAULT '未处理',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. 用户信息表 (user_info)

存储系统用户信息：

```sql
CREATE TABLE user_info (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    user_type VARCHAR(20) NOT NULL,
    department VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5. 变电站信息表 (substation_info)

存储变电站基本信息：

```sql
CREATE TABLE substation_info (
    substation_id VARCHAR(50) PRIMARY KEY,
    substation_name VARCHAR(100) NOT NULL,
    voltage_level VARCHAR(20),
    capacity DECIMAL(10,2),
    location VARCHAR(200),
    region VARCHAR(50),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## CDC 复制槽配置

### 1. 创建复制槽

```sql
SELECT pg_create_logical_replication_slot('flink_cdc_slot', 'pgoutput');
```

### 2. 验证复制槽

```sql
SELECT slot_name, plugin, slot_type, active 
FROM pg_replication_slots 
WHERE slot_name = 'flink_cdc_slot';
```

## 数据生成器

### 1. 功能特性

数据生成器 (`scripts/data_generator.py`) 提供以下功能：

- **持续数据生成**: 每10秒生成一批电表读数数据
- **告警数据生成**: 随机生成设备告警信息
- **设备状态更新**: 随机更新设备运行状态
- **数据质量控制**: 生成符合业务规则的测试数据

### 2. 生成策略

- **电表读数**: 每次生成 5-15 条随机读数
- **告警信息**: 10% 概率生成告警
- **状态更新**: 5% 概率更新设备状态
- **数据统计**: 每分钟输出数据统计信息

### 3. 数据范围

- **有功功率**: 10.0 - 1000.0 kW
- **电压**: 200.0 - 240.0 V
- **电流**: 5.0 - 50.0 A
- **功率因数**: 0.8 - 1.0
- **能耗**: 100.0 - 10000.0 kWh

## 测试验证

### 1. 配置验证脚本

`scripts/validate_postgresql_config.py` 验证以下配置：

- PostgreSQL 版本检查
- 服务状态检查
- 数据库连接测试
- CDC 配置验证
- 数据生成器状态检查

### 2. CRUD 操作测试

`scripts/test_crud_operations.py` 测试以下操作：

- **CREATE**: 创建测试设备和读数数据
- **READ**: 查询设备信息和联合查询
- **UPDATE**: 更新设备状态和批量更新
- **DELETE**: 删除测试数据和级联删除

### 3. 完整功能测试

`tests/test_postgresql_data_source.py` 提供完整的功能测试：

- PostgreSQL 版本验证
- 业务数据表结构检查
- CDC 复制槽配置验证
- 初始数据验证
- CRUD 操作测试
- 数据生成器功能测试

## 使用方法

### 1. 启动服务

PostgreSQL 服务通过 Supervisor 自动启动：

```bash
supervisorctl start postgresql
```

### 2. 连接数据库

```bash
psql -h localhost -p 5432 -U postgres -d power_grid
```

### 3. 运行验证

```bash
# 配置验证
python3 /opt/scripts/validate_postgresql_config.py

# CRUD 测试
python3 /opt/scripts/test_crud_operations.py

# 完整测试
python3 /opt/tests/test_postgresql_data_source.py
```

### 4. 监控数据生成

```bash
# 查看数据生成器日志
tail -f /opt/logs/data-generator.log

# 查看数据统计
psql -h localhost -p 5432 -U postgres -d power_grid -c "
SELECT 
    (SELECT COUNT(*) FROM device_info) as devices,
    (SELECT COUNT(*) FROM meter_reading) as readings,
    (SELECT COUNT(*) FROM alarm_info) as alarms;
"
```

## 故障排查

### 1. 常见问题

#### PostgreSQL 服务无法启动
- 检查数据目录权限: `chown -R postgres:postgres /var/lib/postgresql/13/main`
- 检查配置文件语法: `sudo -u postgres /usr/lib/postgresql/13/bin/postgres --check-config`

#### 数据库连接失败
- 检查服务状态: `supervisorctl status postgresql`
- 检查端口监听: `netstat -tlnp | grep 5432`
- 检查防火墙设置

#### CDC 复制槽问题
- 检查 WAL 级别: `SHOW wal_level;`
- 检查复制槽状态: `SELECT * FROM pg_replication_slots;`
- 重新创建复制槽: `SELECT pg_drop_replication_slot('flink_cdc_slot');`

### 2. 日志文件

- PostgreSQL 服务日志: `/opt/logs/postgresql.log`
- PostgreSQL 错误日志: `/opt/logs/postgresql_error.log`
- 数据生成器日志: `/opt/logs/data-generator.log`
- 系统日志: `/var/log/postgresql/postgresql-13-main.log`

## 性能优化

### 1. 数据库配置优化

```conf
# 内存配置
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB

# 检查点配置
checkpoint_completion_target = 0.9
wal_buffers = 16MB

# 连接配置
max_connections = 100
```

### 2. 索引优化

```sql
-- 为常用查询字段创建索引
CREATE INDEX idx_device_info_code ON device_info(device_code);
CREATE INDEX idx_device_info_type ON device_info(device_type);
CREATE INDEX idx_meter_reading_device_time ON meter_reading(device_id, reading_time);
CREATE INDEX idx_alarm_info_device_time ON alarm_info(device_id, alarm_time);
```

### 3. 数据清理

```sql
-- 定期清理旧数据（保留最近30天）
DELETE FROM meter_reading WHERE create_time < NOW() - INTERVAL '30 days';
DELETE FROM alarm_info WHERE create_time < NOW() - INTERVAL '30 days' AND status = '已处理';
```

## 安全配置

### 1. 用户权限

```sql
-- 创建只读用户
CREATE USER readonly_user WITH PASSWORD 'readonly_password';
GRANT CONNECT ON DATABASE power_grid TO readonly_user;
GRANT USAGE ON SCHEMA public TO readonly_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;

-- 创建应用用户
CREATE USER app_user WITH PASSWORD 'app_password';
GRANT CONNECT ON DATABASE power_grid TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
```

### 2. 连接安全

```conf
# pg_hba.conf 安全配置
local   all             postgres                                peer
host    power_grid      app_user        127.0.0.1/32           md5
host    power_grid      readonly_user   127.0.0.1/32           md5
host    all             all             0.0.0.0/0               reject
```

## 备份恢复

### 1. 数据备份

```bash
# 全量备份
pg_dump -h localhost -U postgres -d power_grid > power_grid_backup.sql

# 压缩备份
pg_dump -h localhost -U postgres -d power_grid | gzip > power_grid_backup.sql.gz

# 定时备份脚本
0 2 * * * pg_dump -h localhost -U postgres -d power_grid | gzip > /opt/backups/power_grid_$(date +\%Y\%m\%d).sql.gz
```

### 2. 数据恢复

```bash
# 恢复数据库
psql -h localhost -U postgres -d power_grid < power_grid_backup.sql

# 从压缩文件恢复
gunzip -c power_grid_backup.sql.gz | psql -h localhost -U postgres -d power_grid
```

## 总结

PostgreSQL 13 数据源环境已完全配置，满足所有需求要求：

✅ **Requirements 4.1**: PostgreSQL 13 已安装并配置
✅ **Requirements 4.2**: 完整的国网业务数据表结构已创建
✅ **Requirements 4.3**: 数据生成器持续生成模拟数据
✅ **Requirements 4.4**: 支持完整的 CRUD 操作测试
✅ **Requirements 4.5**: CDC 复制槽已配置，支持 Flink CDC 连接

系统提供了完整的测试验证脚本，确保所有功能正常工作，为后续的流处理和数据仓库构建提供了可靠的数据源基础。