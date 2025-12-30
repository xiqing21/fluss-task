# 国网实时数仓测试环境

基于 Docker 容器技术的国网实时数据仓库测试环境，集成 PostgreSQL、Apache Flink、Apache Fluss、Apache Doris 和 Grafana 等组件，实现完整的实时数据处理链路。

## 系统架构

```
PostgreSQL (源数据) → Flink CDC → Fluss (流存储) → 分层数仓 (ODS/DWD/DWS/ADS) → Doris (分析存储) → Grafana (可视化)
```

## 核心组件

- **PostgreSQL 13**: 源数据库，存储国网业务数据
- **Apache Flink 2.2.0**: 流计算引擎，支持 Delta Join
- **Apache Fluss 0.8**: 流存储引擎，支持流表查询
- **Apache Doris 1.2.7**: 分析型数据库，OLAP 查询
- **Grafana**: 数据可视化平台
- **SSH 服务**: 远程访问和调试
- **Supervisor**: 进程管理和监控

## 快速开始

### 1. 环境要求

- Docker 20.10+
- Docker Compose 1.29+
- 至少 8GB 内存
- 至少 20GB 磁盘空间

### 2. 构建和启动

```bash
# 克隆项目（如果适用）
git clone <repository-url>
cd power-grid-realtime-warehouse

# 构建镜像并启动
chmod +x build.sh
./build.sh

# 或者直接使用 Docker Compose
docker-compose up -d
```

### 3. 访问服务

| 服务 | 地址 | 认证信息 |
|------|------|----------|
| SSH | `ssh root@localhost -p 2222` | 密码: root123 |
| PostgreSQL | `localhost:5432` | 用户: postgres, 密码: postgres |
| Flink Web UI | http://localhost:8081 | 无需认证 |
| Fluss Web UI | http://localhost:8084 | 无需认证 |
| Grafana | http://localhost:3000 | 用户: admin, 密码: admin |
| Doris FE | http://localhost:8030 | 用户: root, 无密码 |

## 数据库结构

### 业务数据表

- `device_info`: 设备信息表
- `meter_reading`: 电表读数表
- `alarm_info`: 告警信息表
- `user_info`: 用户信息表
- `substation_info`: 变电站信息表

### 数仓分层

- **ODS 层**: 原始数据层，直接从 PostgreSQL CDC 获取
- **DWD 层**: 明细数据层，数据清洗和维度关联
- **DWS 层**: 汇总数据层，时间窗口聚合
- **ADS 层**: 应用数据层，业务指标计算

## 代理配置

如果在受限网络环境中部署，可以配置代理：

```bash
# 设置代理环境变量
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080

# 构建时会自动使用代理配置
./build.sh
```

## 监控和运维

### 健康检查

容器内置健康检查脚本，自动监控各服务状态：

```bash
# 查看健康检查日志
docker logs power-grid-realtime-warehouse | grep "健康检查"

# 手动执行健康检查
docker exec power-grid-realtime-warehouse python3 /opt/scripts/health_check.py
```

### 服务管理

使用 Supervisor 管理所有服务进程：

```bash
# 进入容器
docker exec -it power-grid-realtime-warehouse bash

# 查看服务状态
supervisorctl status

# 重启服务
supervisorctl restart flink-jobmanager
supervisorctl restart postgresql

# 查看服务日志
tail -f /opt/logs/flink-jobmanager.log
```

### 数据生成器

内置数据生成器持续生成模拟的国网业务数据：

- 每10秒生成5-15条电表读数
- 10%概率生成告警信息
- 5%概率更新设备状态

## 测试验证

### 数据流测试

```bash
# 连接 PostgreSQL 查看源数据
docker exec -it power-grid-realtime-warehouse psql -U postgres -d power_grid

# 查看今日生成的数据
SELECT COUNT(*) FROM meter_reading WHERE DATE(create_time) = CURRENT_DATE;
SELECT COUNT(*) FROM alarm_info WHERE DATE(create_time) = CURRENT_DATE;

# 查看设备状态
SELECT status, COUNT(*) FROM device_info GROUP BY status;
```

### Flink 作业监控

访问 Flink Web UI (http://localhost:8081) 查看：
- 作业运行状态
- 数据处理吞吐量
- Checkpoint 状态
- 任务执行情况

### Grafana 仪表板

访问 Grafana (http://localhost:3000) 查看：
- 实时设备监控
- 电力负荷趋势
- 告警统计分析
- 系统运行状态

## 故障排查

### 常见问题

1. **容器启动失败**
   ```bash
   # 查看容器日志
   docker logs power-grid-realtime-warehouse
   
   # 检查端口占用
   netstat -tlnp | grep -E "(2222|5432|8081|3000)"
   ```

2. **服务无法访问**
   ```bash
   # 检查服务状态
   docker exec power-grid-realtime-warehouse supervisorctl status
   
   # 重启特定服务
   docker exec power-grid-realtime-warehouse supervisorctl restart <service-name>
   ```

3. **数据库连接失败**
   ```bash
   # 检查 PostgreSQL 状态
   docker exec power-grid-realtime-warehouse pg_isready -h localhost -p 5432
   
   # 查看 PostgreSQL 日志
   docker exec power-grid-realtime-warehouse tail -f /opt/logs/postgresql.log
   ```

### 日志文件位置

- 系统日志: `/opt/logs/`
- PostgreSQL: `/opt/logs/postgresql.log`
- Flink: `/opt/logs/flink-*.log`
- Fluss: `/opt/logs/fluss-*.log`
- Doris: `/opt/logs/doris-*.log`
- Grafana: `/opt/logs/grafana.log`

## 开发和扩展

### 添加新的数据源

1. 修改 `scripts/init_database.py` 添加新表结构
2. 更新 `scripts/data_generator.py` 生成新数据
3. 配置 Flink CDC 连接器捕获新表变更

### 自定义 Flink 作业

1. 将 JAR 文件复制到 `/opt/flink/lib/`
2. 通过 Flink Web UI 提交作业
3. 或者修改启动脚本自动提交作业

### 扩展监控指标

1. 修改 `scripts/health_check.py` 添加新检查项
2. 在 Grafana 中创建新的仪表板
3. 配置告警规则和通知

## 许可证

本项目仅用于测试和学习目的。

## 支持

如有问题或建议，请联系项目维护者。