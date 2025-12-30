# Service Management Consistency Tests

This directory contains tests for validating the Service Management Consistency property of the Power Grid Realtime Warehouse system.

## Property Being Tested

**Property 1: Service Management Consistency**
*For any* container deployment, all required services (PostgreSQL, Flink, Fluss, Doris, Grafana, SSH) should be automatically started and managed by Supervisor, with each service maintaining their expected running state.

**Validates: Requirements 1.2, 1.4, 9.1**

## Test Structure

### Property-Based Tests
- `test_service_management_consistency_property()`: Uses Hypothesis to generate test scenarios and validate the core property across multiple deployment scenarios.

### Unit Tests
- `test_service_management_consistency_unit()`: Basic validation that all services are running under Supervisor management.
- `test_critical_services_accessibility()`: Validates that critical services are accessible on their expected ports.
- `test_postgresql_database_functionality()`: Validates PostgreSQL database functionality beyond just connectivity.

## Prerequisites

1. **Container Running**: The power-grid-realtime-warehouse container must be running:
   ```bash
   docker-compose up -d
   ```

2. **Dependencies**: Install test dependencies:
   ```bash
   pip install -r tests/requirements.txt
   ```

## Running Tests

### Option 1: Using the Test Runner (Recommended)
```bash
python3 tests/run_service_management_tests.py
```

### Option 2: Using pytest directly
```bash
cd tests
python -m pytest test_service_management_consistency.py -v
```

### Option 3: Direct execution
```bash
python3 tests/test_service_management_consistency.py
```

## Test Services

The tests validate the following services:

| Service | Port | Type | Description |
|---------|------|------|-------------|
| sshd | 22 | TCP | SSH access service |
| postgresql | 5432 | Database | PostgreSQL database |
| flink-jobmanager | 8081 | HTTP | Flink JobManager web UI |
| flink-taskmanager | 8082 | TCP | Flink TaskManager |
| fluss-server | 9123 | TCP | Fluss bootstrap server |
| doris-fe | 8030 | HTTP | Doris Frontend |
| doris-be | 8040 | HTTP | Doris Backend |
| grafana | 3000 | HTTP | Grafana web UI |
| data-generator | - | Process | Data generation service |
| health-check | - | Process | Health monitoring service |

## Expected Behavior

1. **All services should be managed by Supervisor** with status "RUNNING"
2. **Network services should be accessible** on their designated ports
3. **HTTP services should respond** with valid HTTP status codes
4. **PostgreSQL should be functional** for database operations
5. **Services should maintain consistency** across multiple test runs

## Troubleshooting

### Container Not Running
```bash
docker-compose up -d
docker logs power-grid-realtime-warehouse
```

### Services Not Starting
```bash
docker exec -it power-grid-realtime-warehouse supervisorctl status
docker exec -it power-grid-realtime-warehouse bash
```

### Port Accessibility Issues
```bash
docker exec -it power-grid-realtime-warehouse netstat -tlnp
```

### Database Connection Issues
```bash
docker exec -it power-grid-realtime-warehouse psql -U postgres -d power_grid -c "SELECT 1"
```

## Test Output

Successful test output should show:
- ✓ All services running under Supervisor management
- ✓ All critical services accessible on their ports
- ✓ PostgreSQL database functionality validated
- ✓ Property test passed across multiple scenarios

## Integration with CI/CD

These tests can be integrated into CI/CD pipelines:

```bash
# In your CI script
docker-compose up -d
sleep 60  # Wait for services to start
python3 tests/run_service_management_tests.py
docker-compose down
```