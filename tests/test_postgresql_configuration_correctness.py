#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Property-Based Test: Configuration Correctness
Feature: power-grid-realtime-warehouse, Property 3: Configuration Correctness

Validates: Requirements 4.1, 4.2, 4.5

This test validates that PostgreSQL configuration is correct across different scenarios:
- Requirements 4.1: PostgreSQL 13 integration as source database
- Requirements 4.2: Business data table structures (device info, meter readings, alarms, etc.)
- Requirements 4.5: CDC replication slot configuration for Flink CDC connection
"""

import psycopg2
import subprocess
import time
import sys
import os
from datetime import datetime
from hypothesis import given, strategies as st, settings
import pytest

class PostgreSQLConfigurationTester:
    def __init__(self):
        self.conn = None
        self.validation_results = []
        
    def connect_database(self):
        """Connect to PostgreSQL database"""
        try:
            self.conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="power_grid",
                user="postgres",
                password="postgres",
                connect_timeout=10
            )
            return True
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False
    
    def validate_postgresql_version(self):
        """Validate PostgreSQL 13 integration (Requirements 4.1)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT version()")
            version_info = cursor.fetchone()[0]
            
            if "PostgreSQL 13" in version_info:
                self.validation_results.append(("PostgreSQL Version", "PASS", version_info))
                return True
            else:
                self.validation_results.append(("PostgreSQL Version", "FAIL", f"Expected PostgreSQL 13, got: {version_info}"))
                return False
        except Exception as e:
            self.validation_results.append(("PostgreSQL Version", "ERROR", str(e)))
            return False
    
    def validate_business_tables(self):
        """Validate business data table structures (Requirements 4.2)"""
        cursor = self.conn.cursor()
        
        # Expected business tables as per requirements
        expected_tables = {
            'device_info': ['device_id', 'device_code', 'device_name', 'device_type', 'voltage_level', 'status', 'substation_id', 'location'],
            'meter_reading': ['reading_id', 'device_id', 'reading_time', 'active_power', 'voltage', 'current', 'power_factor', 'energy_consumption'],
            'alarm_info': ['alarm_id', 'device_id', 'alarm_time', 'alarm_level', 'alarm_type', 'alarm_desc', 'alarm_value', 'threshold_value', 'status'],
            'user_info': ['user_id', 'username', 'user_type', 'department'],
            'substation_info': ['substation_id', 'substation_name', 'voltage_level', 'location']
        }
        
        all_tables_valid = True
        
        for table_name, expected_columns in expected_tables.items():
            try:
                # Check if table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    )
                """, (table_name,))
                
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    self.validation_results.append(("Business Tables", "FAIL", f"Table {table_name} does not exist"))
                    all_tables_valid = False
                    continue
                
                # Check table columns
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s 
                    ORDER BY ordinal_position
                """, (table_name,))
                
                actual_columns = [row[0] for row in cursor.fetchall()]
                
                # Check if all expected columns exist
                missing_columns = set(expected_columns) - set(actual_columns)
                if missing_columns:
                    self.validation_results.append(("Business Tables", "FAIL", f"Table {table_name} missing columns: {missing_columns}"))
                    all_tables_valid = False
                
            except Exception as e:
                self.validation_results.append(("Business Tables", "ERROR", f"Error checking table {table_name}: {e}"))
                all_tables_valid = False
        
        if all_tables_valid:
            self.validation_results.append(("Business Tables", "PASS", f"All {len(expected_tables)} business tables exist with correct structure"))
        
        return all_tables_valid
    
    def validate_cdc_configuration(self):
        """Validate CDC replication slot configuration (Requirements 4.5)"""
        cursor = self.conn.cursor()
        
        try:
            # Check WAL level
            cursor.execute("SHOW wal_level")
            wal_level = cursor.fetchone()[0]
            
            if wal_level != 'logical':
                self.validation_results.append(("CDC Configuration", "FAIL", f"WAL level is {wal_level}, expected 'logical'"))
                return False
            
            # Check max_replication_slots
            cursor.execute("SHOW max_replication_slots")
            max_slots = int(cursor.fetchone()[0])
            
            if max_slots < 1:
                self.validation_results.append(("CDC Configuration", "FAIL", f"max_replication_slots is {max_slots}, should be >= 1"))
                return False
            
            # Check if CDC replication slot exists
            cursor.execute("""
                SELECT slot_name, plugin, slot_type, active, confirmed_flush_lsn
                FROM pg_replication_slots 
                WHERE slot_name = 'flink_cdc_slot'
            """)
            
            slot_info = cursor.fetchone()
            
            if not slot_info:
                self.validation_results.append(("CDC Configuration", "FAIL", "CDC replication slot 'flink_cdc_slot' does not exist"))
                return False
            
            slot_name, plugin, slot_type, active, flush_lsn = slot_info
            
            # Validate slot properties
            if plugin != 'pgoutput':
                self.validation_results.append(("CDC Configuration", "FAIL", f"Replication slot plugin is {plugin}, expected 'pgoutput'"))
                return False
            
            if slot_type != 'logical':
                self.validation_results.append(("CDC Configuration", "FAIL", f"Replication slot type is {slot_type}, expected 'logical'"))
                return False
            
            self.validation_results.append(("CDC Configuration", "PASS", f"CDC replication slot configured correctly: {slot_name} ({plugin})"))
            return True
            
        except Exception as e:
            self.validation_results.append(("CDC Configuration", "ERROR", str(e)))
            return False
    
    def validate_configuration_correctness(self):
        """
        Core property validation: Configuration Correctness
        
        For any system configuration (PostgreSQL version, business tables, CDC setup),
        the configuration should be properly applied and functional when tested.
        """
        if not self.connect_database():
            return False, "Failed to connect to database"
        
        try:
            # Validate all configuration aspects
            version_valid = self.validate_postgresql_version()
            tables_valid = self.validate_business_tables()
            cdc_valid = self.validate_cdc_configuration()
            
            # All configurations must be valid
            if version_valid and tables_valid and cdc_valid:
                return True, "All PostgreSQL configurations are correct"
            else:
                failed_validations = [result for result in self.validation_results if result[1] in ["FAIL", "ERROR"]]
                return False, f"Configuration validation failed: {len(failed_validations)} issues found"
                
        except Exception as e:
            return False, f"Configuration validation error: {e}"
        finally:
            if self.conn:
                self.conn.close()


# Property-based test implementation
@given(st.integers(min_value=1, max_value=3))  # Test with different retry attempts
@settings(max_examples=5, deadline=120000)  # 2 minutes timeout for each test
def test_configuration_correctness_property(retry_count):
    """
    Property Test: Configuration Correctness
    Feature: power-grid-realtime-warehouse, Property 3: Configuration Correctness
    
    For any system configuration (proxy settings, SSH keys, database connections), 
    the configuration should be properly applied and functional when tested.
    
    **Validates: Requirements 4.1, 4.2, 4.5**
    """
    tester = PostgreSQLConfigurationTester()
    
    # Try validation with retries
    for attempt in range(retry_count):
        print(f"Configuration correctness validation attempt {attempt + 1}/{retry_count}")
        
        success, message = tester.validate_configuration_correctness()
        
        if success:
            print(f"✓ Property validation successful: {message}")
            return  # Test passed
        else:
            print(f"✗ Attempt {attempt + 1} failed: {message}")
            if attempt < retry_count - 1:
                time.sleep(2)  # Wait before retry
    
    # If we get here, all attempts failed
    pytest.fail(f"Configuration Correctness property failed after {retry_count} attempts: {message}")


def run_standalone_test():
    """Run the test as a standalone script"""
    print("=== PostgreSQL Configuration Correctness Property Test ===")
    print(f"Test time: {datetime.now()}")
    print("Note: This test requires PostgreSQL 13 running in Docker container environment")
    print()
    
    try:
        # Run property test
        test_configuration_correctness_property(2)
        print("✓ Property test passed")
        return True
    except Exception as e:
        error_msg = str(e)
        if "Connection refused" in error_msg:
            print("✗ Property test failed: PostgreSQL not running")
            print("This is expected when running outside the Docker container environment.")
            print("To run this test properly:")
            print("1. Start the power-grid-realtime-warehouse Docker container")
            print("2. Run this test inside the container where PostgreSQL 13 is configured")
            print("3. Or use the mock version: python tests/test_postgresql_configuration_correctness_mock.py")
            return False
        else:
            print(f"✗ Property test failed: {e}")
            return False


if __name__ == "__main__":
    success = run_standalone_test()
    
    if success:
        print("\n🎉 PostgreSQL Configuration Correctness validation successful!")
        sys.exit(0)
    else:
        print("\n❌ PostgreSQL Configuration Correctness validation failed!")
        sys.exit(1)