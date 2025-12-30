# 数据生成连续性测试文档

## 概述

本测试套件实现了 **Property 4: Data Generation Continuity** 的验证，确保数据生成器能够持续生成有效的业务数据并成功插入到源数据库中。

## 验证的需求

- **Requirements 4.3**: Data_Generator SHALL 持续生成模拟的国网业务数据
- **Requirements 4.4**: System SHALL 支持对源数据库的 CRUD 操作测试

## 测试文件

### 1. `test_data_generation_continuity.py`
**真实环境测试文件**
- 连接真实的 PostgreSQL 数据库
- 启动真实的数据生成器进程
- 监控实际的数据生成过程
- 执行真实的 CRUD 操作

**使用场景**：
- 在完整的系统环境中运行
- 需要 PostgreSQL 服务正在运行
- 需要数据生成器脚本可用

### 2. `test_data_generation_continuity_mock.py`
**Mock 环境测试文件**
- 使用 Mock 对象模拟数据库连接
- 模拟数据生成器进程
- 模拟数据增长和 CRUD 操作
- 可在任何环境中运行

**使用场景**：
- 开发和调试阶段
- CI/CD 环境中的快速验证
- 不依赖外部服务的测试

## 属性测试详情

### Property 4: Data Generation Continuity

**属性描述**：
*For any* running data generator, it should continuously produce valid business data that gets successfully inserted into the source database.

**测试逻辑**：
1. **连接验证**：确保能够连接到数据库
2. **初始状态**：记录测试开始时的数据量
3. **生成器启动**：启动数据生成器进程
4. **连续性监控**：在指定时间内监控数据增长
5. **增长验证**：确保数据持续增长
6. **CRUD 测试**：验证完整的 CRUD 操作
7. **最近数据验证**：确保最近时间内有新数据生成

**测试参数**：
- `monitoring_duration_minutes`: 监控持续时间（1-5分钟）
- 使用 Hypothesis 生成不同的监控时长进行测试

## 运行测试

### 运行真实环境测试
```bash
# 确保 PostgreSQL 服务正在运行
# 确保数据生成器脚本可用

# 运行属性测试
pytest tests/test_data_generation_continuity.py::test_data_generation_continuity_property -v -s

# 运行所有测试
pytest tests/test_data_generation_continuity.py -v
```

### 运行 Mock 环境测试
```bash
# 运行属性测试
pytest tests/test_data_generation_continuity_mock.py::test_data_generation_continuity_property_mock -v -s

# 运行所有测试
pytest tests/test_data_generation_continuity_mock.py -v

# 直接运行脚本
python tests/test_data_generation_continuity_mock.py
```

## 测试覆盖范围

### 单元测试
- 数据库连接功能
- 记录数获取功能
- 基本 CRUD 操作
- 数据格式验证

### 边界条件测试
- 单设备 CRUD 操作
- 零设备处理
- 极短时间范围数据查询
- 长时间范围数据查询

### 失败场景测试
- 数据生成停止情况
- 数据生成恢复验证
- 异常情况处理

### 属性测试
- 不同监控时长的连续性验证
- 随机参数下的系统行为
- 通用属性的验证

## 测试结果解释

### 成功指标
- 数据生成器成功启动
- 数据记录数持续增长
- CRUD 操作全部成功
- 最近时间内有新数据生成

### 失败场景
- 数据库连接失败
- 数据生成器启动失败
- 数据记录数未增长
- CRUD 操作失败
- 最近时间内无新数据

## 配置说明

### 数据库配置
```python
host="localhost"
port=5432
database="power_grid"
user="postgres"
password="postgres"
```

### 测试参数
- **监控间隔**：30秒（真实环境）/ 0.1秒（Mock环境）
- **超时时间**：3分钟（真实环境）/ 30秒（Mock环境）
- **测试示例数**：3个（Hypothesis 配置）
- **CRUD 设备数**：根据监控时长动态调整（最多10个）

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查 PostgreSQL 服务是否运行
   - 验证连接参数是否正确
   - 检查网络连接

2. **数据生成器启动失败**
   - 检查脚本路径是否正确
   - 验证 Python 环境和依赖
   - 检查权限设置

3. **数据未增长**
   - 检查数据生成器是否正常运行
   - 验证数据库表结构
   - 检查数据生成逻辑

4. **CRUD 操作失败**
   - 检查数据库权限
   - 验证表结构完整性
   - 检查事务处理

### 调试建议

1. **启用详细日志**：使用 `-s` 参数运行 pytest
2. **单独测试组件**：分别测试数据库连接、数据生成器等
3. **检查系统资源**：确保有足够的内存和磁盘空间
4. **使用 Mock 版本**：先验证测试逻辑是否正确

## 扩展和维护

### 添加新的测试场景
1. 在相应的测试类中添加新方法
2. 遵循现有的命名约定
3. 添加适当的断言和错误处理
4. 更新文档

### 修改测试参数
1. 调整 Hypothesis 的 `@settings` 配置
2. 修改监控时长范围
3. 调整超时时间
4. 更新测试数据量

### 性能优化
1. 减少不必要的数据库查询
2. 优化测试数据生成
3. 并行化独立的测试
4. 使用更高效的断言

## 相关文档

- [Requirements Document](../.kiro/specs/power-grid-realtime-warehouse/requirements.md)
- [Design Document](../.kiro/specs/power-grid-realtime-warehouse/design.md)
- [Data Generator Script](../scripts/data_generator.py)
- [PostgreSQL Configuration](../doc/postgresql_configuration.md)