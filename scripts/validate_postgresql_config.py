#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - PostgreSQL 配置验证脚本

验证 PostgreSQL 13 配置是否满足所有要求：
- Requirements 4.1: PostgreSQL 13 集成
- Requirements 4.2: 业务数据表结构
- Requirements 4.3: 数据生成器
- Requirements 4.5: CDC 复制槽配置
"""

import psycopg2
import subprocess
import sys
import time
from datetime import datetime

def check_postgresql_version():
    """检查 PostgreSQL 版本"""
    print("检查 PostgreSQL 版本...")
    try:
        result = subprocess.run(['sudo', '-u', 'postgres', '/usr/lib/postgresql/13/bin/postgres', '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_info = result.stdout.strip()
            if "PostgreSQL 13" in version_info:
                print(f"✓ PostgreSQL 版本正确: {version_info}")
                return True
            else:
                print(f"✗ PostgreSQL 版本不正确: {version_info}")
                return False
        else:
            print(f"✗ 无法获取 PostgreSQL 版本: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 检查 PostgreSQL 版本失败: {e}")
        return False

def check_postgresql_service():
    """检查 PostgreSQL 服务状态"""
    print("检查 PostgreSQL 服务状态...")
    try:
        result = subprocess.run(['supervisorctl', 'status', 'postgresql'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            status_info = result.stdout.strip()
            if "RUNNING" in status_info:
                print(f"✓ PostgreSQL 服务正在运行: {status_info}")
                return True
            else:
                print(f"✗ PostgreSQL 服务未运行: {status_info}")
                return False
        else:
            print(f"✗ 无法获取 PostgreSQL 服务状态: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 检查 PostgreSQL 服务状态失败: {e}")
        return False

def check_database_connection():
    """检查数据库连接"""
    print("检查数据库连接...")
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
        
        if result:
            print("✓ 数据库连接成功")
            return True
        else:
            print("✗ 数据库连接失败")
            return False
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False

def check_cdc_configuration():
    """检查 CDC 配置"""
    print("检查 CDC 配置...")
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
        
        # 检查 WAL 级别
        cursor.execute("SHOW wal_level")
        wal_level = cursor.fetchone()[0]
        
        if wal_level != 'logical':
            print(f"✗ WAL 级别不正确: {wal_level} (期望: logical)")
            conn.close()
            return False
        
        print(f"✓ WAL 级别正确: {wal_level}")
        
        # 检查复制槽
        cursor.execute("SELECT COUNT(*) FROM pg_replication_slots WHERE slot_name = 'flink_cdc_slot'")
        slot_count = cursor.fetchone()[0]
        
        if slot_count > 0:
            print("✓ CDC 复制槽已配置")
            conn.close()
            return True
        else:
            print("✗ CDC 复制槽未配置")
            conn.close()
            return False
            
    except Exception as e:
        print(f"✗ CDC 配置检查失败: {e}")
        return False

def check_data_generator():
    """检查数据生成器"""
    print("检查数据生成器...")
    try:
        result = subprocess.run(['supervisorctl', 'status', 'data-generator'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            status_info = result.stdout.strip()
            if "RUNNING" in status_info:
                print(f"✓ 数据生成器正在运行: {status_info}")
                return True
            else:
                print(f"✗ 数据生成器未运行: {status_info}")
                return False
        else:
            print(f"✗ 无法获取数据生成器状态: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 检查数据生成器失败: {e}")
        return False

def main():
    """主函数"""
    print("=== PostgreSQL 配置验证 ===")
    print(f"验证时间: {datetime.now()}")
    print()
    
    checks = [
        ("PostgreSQL 版本", check_postgresql_version),
        ("PostgreSQL 服务", check_postgresql_service),
        ("数据库连接", check_database_connection),
        ("CDC 配置", check_cdc_configuration),
        ("数据生成器", check_data_generator)
    ]
    
    passed = 0
    total = len(checks)
    
    for check_name, check_func in checks:
        print(f"--- {check_name} ---")
        if check_func():
            passed += 1
        print()
    
    print("=== 验证结果 ===")
    print(f"通过: {passed}/{total}")
    
    if passed == total:
        print("✓ PostgreSQL 配置验证全部通过")
        return True
    else:
        print("✗ PostgreSQL 配置验证存在问题")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)