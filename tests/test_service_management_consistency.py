#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Property-Based Test: Service Management Consistency
Feature: power-grid-realtime-warehouse, Property 1: Service Management Consistency
Validates: Requirements 1.2, 1.4, 9.1

This test validates that for any container deployment, all required services 
(PostgreSQL, Flink, Fluss, Doris, Grafana, SSH) should be automatically started 
and managed by Supervisor, with each service maintaining its expected running state.
"""

import subprocess
import socket
import time
import requests
import psycopg2
from hypothesis import given, strategies as st, settings
import pytest
import docker
import os
import sys

class ServiceManagementTester:
    """Service Management Consistency Tester"""
    
    def __init__(self):
        self.required_services = {
            'sshd': {'port': 22, 'type': 'tcp'},
            'postgresql': {'port': 5432, 'type': 'database'},
            'flink-fluss-cluster': {'port': 8081, 'type': 'http'},  # Flink Web UI
            'doris-fe': {'port': 8030, 'type': 'http'},
            'doris-be': {'port': 8040, 'type': 'http'},
            'grafana': {'port': 3000, 'type': 'http'},
            'data-generator': {'port': None, 'type': 'process'},
            'health-check': {'port': None, 'type': 'process'}
        }
        self.docker_client = docker.from_env()
        self.container_name = "power-grid-realtime-warehouse"
    
    def check_port_connectivity(self, host, port, timeout=5):
        """Check if a port is accessible"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def check_http_service(self, url, timeout=5):
        """Check if HTTP service is responding"""
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code in [200, 302, 401]  # Allow redirects and auth pages
        except Exception:
            return False
    
    def check_postgresql_service(self):
        """Check PostgreSQL database connectivity"""
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="power_grid",
                user="postgres",
                password="postgres",
                connect_timeout=5
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception:
            return False
    
    def get_supervisor_status(self):
        """Get status of all services managed by Supervisor"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            result = container.exec_run("supervisorctl status", timeout=10)
            
            if result.exit_code != 0:
                return {}
            
            services = {}
            for line in result.output.decode().strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        service_name = parts[0]
                        service_status = parts[1]
                        services[service_name] = service_status
            
            return services
        except Exception as e:
            print(f"Error getting supervisor status: {e}")
            return {}
    
    def check_container_running(self):
        """Check if the container is running"""
        try:
            container = self.docker_client.containers.get(self.container_name)
            return container.status == 'running'
        except Exception:
            return False
    
    def wait_for_services_startup(self, max_wait_time=120):
        """Wait for services to start up"""
        print(f"Waiting up to {max_wait_time} seconds for services to start...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            supervisor_status = self.get_supervisor_status()
            if supervisor_status:
                running_services = [name for name, status in supervisor_status.items() 
                                  if status == 'RUNNING']
                if len(running_services) >= len(self.required_services) * 0.8:  # 80% of services
                    print(f"Services started: {running_services}")
                    return True
            time.sleep(5)
        
        return False
    
    def validate_service_consistency(self):
        """
        Core property validation: Service Management Consistency
        For any container deployment, all required services should be automatically 
        started and managed by Supervisor, with each service maintaining its expected running state.
        """
        # Check container is running
        if not self.check_container_running():
            return False, "Container is not running"
        
        # Wait for services to start
        if not self.wait_for_services_startup():
            return False, "Services failed to start within timeout"
        
        # Get supervisor status
        supervisor_status = self.get_supervisor_status()
        if not supervisor_status:
            return False, "Cannot get supervisor status"
        
        # Check each required service
        failed_services = []
        service_details = {}
        
        for service_name, config in self.required_services.items():
            # Check if service is managed by supervisor
            if service_name not in supervisor_status:
                failed_services.append(f"{service_name}: not managed by supervisor")
                continue
            
            supervisor_state = supervisor_status[service_name]
            service_details[service_name] = {
                'supervisor_status': supervisor_state,
                'port_check': None,
                'service_check': None
            }
            
            # Check if service is running in supervisor
            if supervisor_state != 'RUNNING':
                failed_services.append(f"{service_name}: supervisor status is {supervisor_state}")
                continue
            
            # Check port connectivity if service has a port
            port = config.get('port')
            if port:
                port_accessible = self.check_port_connectivity('localhost', port)
                service_details[service_name]['port_check'] = port_accessible
                
                if not port_accessible:
                    failed_services.append(f"{service_name}: port {port} not accessible")
                    continue
                
                # Additional service-specific checks
                service_type = config.get('type')
                if service_type == 'http':
                    http_ok = self.check_http_service(f'http://localhost:{port}')
                    service_details[service_name]['service_check'] = http_ok
                    if not http_ok:
                        failed_services.append(f"{service_name}: HTTP service not responding on port {port}")
                
                elif service_type == 'database' and service_name == 'postgresql':
                    db_ok = self.check_postgresql_service()
                    service_details[service_name]['service_check'] = db_ok
                    if not db_ok:
                        failed_services.append(f"{service_name}: database connection failed")
        
        # Return results
        if failed_services:
            return False, f"Service consistency validation failed: {'; '.join(failed_services)}"
        
        return True, f"All {len(self.required_services)} services are running consistently"


# Property-based test implementation
@given(st.integers(min_value=1, max_value=3))  # Test with different retry attempts
@settings(max_examples=5, deadline=300000)  # 5 minutes timeout for each test
def test_service_management_consistency_property(retry_count):
    """
    Property Test: Service Management Consistency
    Feature: power-grid-realtime-warehouse, Property 1: Service Management Consistency
    
    For any container deployment, all required services (PostgreSQL, Flink, Fluss, 
    Doris, Grafana, SSH) should be automatically started and managed by Supervisor, 
    with each service maintaining its expected running state.
    
    **Validates: Requirements 1.2, 1.4, 9.1**
    """
    tester = ServiceManagementTester()
    
    # Allow multiple attempts for service startup (services may take time to initialize)
    for attempt in range(retry_count):
        print(f"\n=== Service Management Consistency Test - Attempt {attempt + 1}/{retry_count} ===")
        
        success, message = tester.validate_service_consistency()
        
        if success:
            print(f"✓ Property validation successful: {message}")
            return  # Test passed
        else:
            print(f"✗ Attempt {attempt + 1} failed: {message}")
            if attempt < retry_count - 1:
                print("Waiting 30 seconds before retry...")
                time.sleep(30)
    
    # If we get here, all attempts failed
    pytest.fail(f"Service Management Consistency property failed after {retry_count} attempts: {message}")


def test_service_management_consistency_unit():
    """
    Unit Test: Basic Service Management Consistency
    Validates that the container has all required services configured and running.
    """
    tester = ServiceManagementTester()
    
    # Check container is running
    assert tester.check_container_running(), "Container must be running for tests"
    
    # Wait for services to start
    assert tester.wait_for_services_startup(180), "Services must start within 3 minutes"
    
    # Get supervisor status
    supervisor_status = tester.get_supervisor_status()
    assert supervisor_status, "Must be able to get supervisor status"
    
    # Check that all required services are managed by supervisor
    for service_name in tester.required_services.keys():
        assert service_name in supervisor_status, f"Service {service_name} must be managed by supervisor"
        assert supervisor_status[service_name] == 'RUNNING', f"Service {service_name} must be running"
    
    print(f"✓ All {len(tester.required_services)} services are running under supervisor management")


def test_critical_services_accessibility():
    """
    Unit Test: Critical Services Port Accessibility
    Validates that critical services are accessible on their expected ports.
    """
    tester = ServiceManagementTester()
    
    critical_services = {
        'SSH': 22,
        'PostgreSQL': 5432,
        'Flink Web UI': 8081,
        'Grafana': 3000,
        'Doris FE': 8030
    }
    
    for service_name, port in critical_services.items():
        assert tester.check_port_connectivity('localhost', port, timeout=10), \
            f"{service_name} must be accessible on port {port}"
    
    print(f"✓ All {len(critical_services)} critical services are accessible")


def test_postgresql_database_functionality():
    """
    Unit Test: PostgreSQL Database Functionality
    Validates that PostgreSQL is not only running but also functional.
    """
    tester = ServiceManagementTester()
    
    # Test database connectivity
    assert tester.check_postgresql_service(), "PostgreSQL database must be accessible"
    
    # Test basic database operations
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="power_grid",
            user="postgres",
            password="postgres",
            connect_timeout=10
        )
        cursor = conn.cursor()
        
        # Test table existence
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('device_info', 'meter_reading', 'alarm_info')
        """)
        table_count = cursor.fetchone()[0]
        assert table_count >= 3, "Required tables must exist in database"
        
        # Test basic query
        cursor.execute("SELECT COUNT(*) FROM device_info")
        device_count = cursor.fetchone()[0]
        assert device_count >= 0, "Device table must be queryable"
        
        conn.close()
        print("✓ PostgreSQL database functionality validated")
        
    except Exception as e:
        pytest.fail(f"PostgreSQL functionality test failed: {e}")


if __name__ == "__main__":
    # Run the tests directly
    print("=== Running Service Management Consistency Tests ===")
    
    # Run unit tests first
    try:
        test_service_management_consistency_unit()
        test_critical_services_accessibility()
        test_postgresql_database_functionality()
        print("✓ All unit tests passed")
    except Exception as e:
        print(f"✗ Unit test failed: {e}")
        sys.exit(1)
    
    # Run property test
    try:
        test_service_management_consistency_property(2)
        print("✓ Property test passed")
    except Exception as e:
        print(f"✗ Property test failed: {e}")
        sys.exit(1)
    
    print("=== All Service Management Consistency Tests Passed ===")