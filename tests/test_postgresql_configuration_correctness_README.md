# PostgreSQL Configuration Correctness Property Test

## Overview

This test implements **Property 3: Configuration Correctness** for the power-grid-realtime-warehouse feature.

**Validates: Requirements 4.1, 4.2, 4.5**

## Property Definition

*For any* system configuration (PostgreSQL version, business tables, CDC setup), the configuration should be properly applied and functional when tested.

## Test Coverage

### Requirements 4.1: PostgreSQL 13 Integration
- Validates that PostgreSQL 13 is properly installed and running
- Checks database version information
- Verifies database connectivity

### Requirements 4.2: Business Data Table Structures  
- Validates existence of all required business tables:
  - `device_info` - Device information table
  - `meter_reading` - Meter reading data table
  - `alarm_info` - Alarm information table
  - `user_info` - User information table
  - `substation_info` - Substation information table
- Checks that each table has the correct column structure
- Verifies table schema matches business requirements

### Requirements 4.5: CDC Replication Slot Configuration
- Validates WAL level is set to 'logical' for CDC support
- Checks that max_replication_slots is configured appropriately
- Verifies that the 'flink_cdc_slot' replication slot exists
- Validates replication slot configuration (plugin: pgoutput, type: logical)

## Running the Test

### In Docker Container Environment

```bash
# Inside the power-grid-realtime-warehouse container
python tests/test_postgresql_configuration_correctness.py

# Or using pytest
pytest tests/test_postgresql_configuration_correctness.py::test_configuration_correctness_property -v
```

### Expected Environment

This test requires:
1. PostgreSQL 13 running on localhost:5432
2. Database named 'power_grid' 
3. User 'postgres' with password 'postgres'
4. All business tables created and configured
5. CDC replication slot 'flink_cdc_slot' configured

### Test Behavior

The property-based test uses Hypothesis to:
- Generate different retry scenarios (1-3 attempts)
- Run 5 test examples with 2-minute timeout per test
- Validate configuration correctness across multiple attempts
- Provide detailed failure information for debugging

## Expected Results

When running in the proper Docker container environment:
- ✅ PostgreSQL Version validation should pass
- ✅ Business Tables validation should pass  
- ✅ CDC Configuration validation should pass
- ✅ Overall Configuration Correctness property should pass

## Failure Analysis

Common failure scenarios:
1. **Database Connection Failed**: PostgreSQL service not running or wrong connection parameters
2. **Version Mismatch**: PostgreSQL version is not 13.x
3. **Missing Tables**: Business tables not created or have wrong names
4. **Missing Columns**: Tables exist but missing required columns
5. **CDC Not Configured**: WAL level not set to logical or replication slot missing

## Integration with Task System

This test is part of task 3.1 in the implementation plan and validates the data source configuration setup completed in task 3.