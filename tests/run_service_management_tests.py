#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Runner for Service Management Consistency Tests
Executes both unit tests and property-based tests for service management.
"""

import sys
import subprocess
import os
import time

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = ['pytest', 'hypothesis', 'docker', 'psycopg2', 'requests']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Install them with: pip install -r tests/requirements.txt")
        return False
    
    return True

def check_container_status():
    """Check if the container is running"""
    try:
        result = subprocess.run(['docker', 'ps', '--filter', 'name=power-grid-realtime-warehouse', '--format', '{{.Names}}'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and 'power-grid-realtime-warehouse' in result.stdout:
            print("✓ Container is running")
            return True
        else:
            print("✗ Container is not running")
            print("Please start the container with: docker-compose up -d")
            return False
    except Exception as e:
        print(f"Error checking container status: {e}")
        return False

def wait_for_container_ready(max_wait=180):
    """Wait for container to be ready"""
    print(f"Waiting up to {max_wait} seconds for container to be ready...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            # Check if health check passes
            result = subprocess.run(['docker', 'exec', 'power-grid-realtime-warehouse', 
                                   'python3', '/opt/scripts/quick_health_check.py', '--quick'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✓ Container is ready")
                return True
        except Exception:
            pass
        
        print(".", end="", flush=True)
        time.sleep(10)
    
    print("\n✗ Container did not become ready within timeout")
    return False

def run_tests():
    """Run the service management consistency tests"""
    print("=== Running Service Management Consistency Tests ===")
    
    # Change to tests directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(test_dir)
    
    # Run pytest with verbose output
    try:
        cmd = [
            'python', '-m', 'pytest', 
            'test_service_management_consistency.py',
            '-v',
            '--tb=short',
            '--durations=10'
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, timeout=600)  # 10 minute timeout
        
        if result.returncode == 0:
            print("✓ All tests passed successfully")
            return True
        else:
            print("✗ Some tests failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Tests timed out")
        return False
    except Exception as e:
        print(f"✗ Error running tests: {e}")
        return False

def run_direct_test():
    """Run the test directly without pytest"""
    print("=== Running Direct Test Execution ===")
    
    try:
        test_file = os.path.join(os.path.dirname(__file__), 'test_service_management_consistency.py')
        result = subprocess.run(['python3', test_file], timeout=600)
        
        if result.returncode == 0:
            print("✓ Direct test execution passed")
            return True
        else:
            print("✗ Direct test execution failed")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Direct test execution timed out")
        return False
    except Exception as e:
        print(f"✗ Error in direct test execution: {e}")
        return False

def main():
    """Main test runner function"""
    print("=== Service Management Consistency Test Runner ===")
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check container status
    if not check_container_status():
        sys.exit(1)
    
    # Wait for container to be ready
    if not wait_for_container_ready():
        print("Warning: Container may not be fully ready, proceeding with tests...")
    
    # Try pytest first, fall back to direct execution
    success = run_tests()
    
    if not success:
        print("\nPytest execution failed, trying direct execution...")
        success = run_direct_test()
    
    if success:
        print("\n=== All Service Management Consistency Tests Completed Successfully ===")
        sys.exit(0)
    else:
        print("\n=== Service Management Consistency Tests Failed ===")
        sys.exit(1)

if __name__ == "__main__":
    main()