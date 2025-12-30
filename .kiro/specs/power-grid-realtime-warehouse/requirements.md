# Requirements Document

## Introduction

本文档定义了国网实时数仓测试环境构建与验证系统的需求。该系统基于 Docker 容器技术，集成 PostgreSQL、Apache Flink、Apache Fluss、Apache Doris 和 Grafana 等组件，构建完整的实时数据仓库测试环境，支持端到端的数据流处理、分层数仓架构和可视化展示。

## Glossary

- **System**: 国网实时数仓测试环境系统
- **Container**: Docker 容器实例
- **Data_Generator**: Python 数据生成器
- **CDC_Connector**: Flink Change Data Capture 连接器
- **ODS_Layer**: 原始数据层（Operational Data Store）
- **DWD_Layer**: 明细数据层（Data Warehouse Detail）
- **DWS_Layer**: 汇总数据层（Data Warehouse Summary）
- **ADS_Layer**: 应用数据层（Application Data Service）
- **Delta_Join**: Flink Delta Join 算子
- **SSH_Service**: 容器内 SSH 服务
- **Proxy_Service**: HTTP/HTTPS 代理服务
- **Health_Check**: 系统健康检查机制
- **CRUD_Operations**: 创建、读取、更新、删除操作

## Requirements

### Requirement 1

**User Story:** 作为系统管理员，我希望能够快速部署完整的实时数仓测试环境，以便进行国网业务数据处理的验证和测试。

#### Acceptance Criteria

1. THE System SHALL 基于 Docker 容器技术提供一键部署能力
2. WHEN 容器启动时，THE System SHALL 自动启动所有必需的服务组件
3. THE System SHALL 在 5 分钟内完成所有服务的初始化和就绪状态
4. THE System SHALL 提供统一的服务管理和监控机制
5. WHEN 部署完成后，THE System SHALL 提供清晰的访问地址和认证信息

### Requirement 2

**User Story:** 作为开发人员，我希望能够通过 SSH 连接到容器环境，以便进行开发调试和运维操作。

#### Acceptance Criteria

1. THE SSH_Service SHALL 在容器启动时自动启动并监听 22 端口
2. THE SSH_Service SHALL 支持 root 用户密码登录（密码：root123）
3. THE SSH_Service SHALL 支持基于密钥的免密登录
4. WHEN SSH 连接建立后，THE System SHALL 提供完整的 Linux 命令行环境
5. THE SSH_Service SHALL 配置 authorized_keys 文件支持公钥认证

### Requirement 3

**User Story:** 作为网络管理员，我希望系统能够支持 HTTP 代理配置，以便在受限网络环境中正常访问外部资源。

#### Acceptance Criteria

1. THE Proxy_Service SHALL 支持配置 HTTP 和 HTTPS 代理服务器
2. THE System SHALL 在环境变量中设置代理配置（HTTP_PROXY, HTTPS_PROXY）
3. THE System SHALL 为 APT 包管理器配置代理设置
4. THE System SHALL 为 Python pip 配置代理设置
5. WHEN 代理配置生效后，THE System SHALL 能够通过代理访问外部网络资源

### Requirement 4

**User Story:** 作为数据工程师，我希望系统能够提供完整的数据源环境，以便模拟真实的国网业务数据场景。

#### Acceptance Criteria

1. THE System SHALL 集成 PostgreSQL 13 作为源数据库
2. THE System SHALL 创建国网业务相关的数据表结构（设备信息、电表读数、告警信息等）
3. THE Data_Generator SHALL 持续生成模拟的国网业务数据
4. THE System SHALL 支持对源数据库的 CRUD 操作测试
5. THE PostgreSQL SHALL 配置 CDC 复制槽以支持 Flink CDC 连接

### Requirement 5

**User Story:** 作为流处理开发者，我希望系统能够提供 Flink 和 Fluss 集成环境，以便实现基于 Delta Join 的实时数据处理。

#### Acceptance Criteria

1. THE System SHALL 集成 Apache Flink 2.2.0 并自动启动 JobManager 和 TaskManager
2. THE System SHALL 集成 Apache Fluss 0.8 并配置流存储服务
3. THE System SHALL 提供 Flink CDC 连接器支持 PostgreSQL 数据捕获
4. THE Delta_Join SHALL 实现流表与维表的高效关联查询
5. THE System SHALL 提供 Flink Web UI 用于作业监控和管理

### Requirement 6

**User Story:** 作为数据架构师，我希望系统能够实现分层数仓架构，以便构建标准的实时数据仓库。

#### Acceptance Criteria

1. THE ODS_Layer SHALL 直接从 PostgreSQL CDC 捕获原始数据
2. THE DWD_Layer SHALL 实现数据清洗、标准化和维度关联
3. THE DWS_Layer SHALL 提供时间窗口聚合和业务维度汇总
4. THE ADS_Layer SHALL 生成应用层指标和告警分析
5. THE System SHALL 确保各层数据的实时流转和一致性

### Requirement 7

**User Story:** 作为业务分析师，我希望系统能够提供数据存储和可视化能力，以便进行业务数据分析和监控。

#### Acceptance Criteria

1. THE System SHALL 集成 Apache Doris 1.2.7 作为分析型数据库
2. THE System SHALL 将处理后的数据写入 Doris 进行存储
3. THE System SHALL 集成 Grafana 提供数据可视化能力
4. THE System SHALL 预配置国网业务监控仪表板
5. WHEN 数据更新时，THE Grafana SHALL 实时刷新图表显示

### Requirement 8

**User Story:** 作为测试工程师，我希望系统能够提供完整的测试验证机制，以便验证端到端数据流的正确性。

#### Acceptance Criteria

1. THE System SHALL 提供自动化的健康检查脚本
2. THE System SHALL 支持 CRUD 操作的端到端测试
3. THE System SHALL 验证数据从 PostgreSQL 到 Doris 的完整流转
4. THE System SHALL 测试各组件服务的连通性和可用性
5. THE System SHALL 生成详细的测试报告和日志记录

### Requirement 9

**User Story:** 作为运维工程师，我希望系统能够提供监控和日志管理功能，以便进行系统运维和故障排查。

#### Acceptance Criteria

1. THE System SHALL 使用 Supervisor 统一管理所有服务进程
2. THE System SHALL 为每个服务组件提供独立的日志文件
3. THE Health_Check SHALL 定期检查各服务状态并记录结果
4. THE System SHALL 提供实时监控脚本显示系统运行状态
5. WHEN 服务异常时，THE System SHALL 自动重启相关服务

### Requirement 10

**User Story:** 作为 DevOps 工程师，我希望系统能够支持镜像构建、测试和发布流程，以便实现标准化的部署和交付。

#### Acceptance Criteria

1. THE System SHALL 提供完整的 Dockerfile 构建脚本
2. THE System SHALL 支持自动化的镜像构建和测试流程
3. THE System SHALL 生成可分发的镜像包和部署脚本
4. THE System SHALL 提供版本管理和发布说明文档
5. THE System SHALL 支持镜像仓库的推送和拉取操作