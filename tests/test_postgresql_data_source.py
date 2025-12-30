#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - PostgreSQL 数据源配置测试

测试 PostgreSQL 13 数据源环境的完整配置，包括：
- 数据库连接和基本功能
- 业务数据表结构验证
- CDC 复制槽配置验证
- 数据生成器功能验证
- CRUD 操作测试

Requirements: 4.1, 4.2, 4.3, 4.5
"""

import psycopg2
import time
import subprocess
import json
from datetime import datetime, timedelta
import sys
import os

class PostgreSQLDataSourceTester:
    def __init__(self):
        self.conn = None
        self.test_results = []
        
    def connect_database(self):
        """连接 PostgreSQL 数据库"""
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
            print(f"数据库连接失败: {e}")
            return False
    
    def test_postgresql_version(self):
        """测试 PostgreSQL 版本是否为 13"""
        print("测试 PostgreSQL 版本...")
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT version()")
            version_info = cursor.fetchone()[0]
            
            if "PostgreSQL 13" in version_info:
                print(f"✓ PostgreSQL 版本正确: {version_info}")
                self.test_results.append(("PostgreSQL 版本", "PASS", version_info))
                return True
            else:
                print(f"✗ PostgreSQL 版本不正确: {version_info}")
                self.test_results.append(("PostgreSQL 版本", "FAIL", version_info))
                return False
        except Exception as e:
            print(f"✗ 版本检查失败: {e}")
            self.test_results.append(("PostgreSQL 版本", "ERROR", str(e)))
            return False
    
    def test_database_tables(self):
        """测试业务数据表结构"""
        print("测试业务数据表结构...")
        cursor = self.conn.cursor()
        
        # 期望的表列表
        expected_tables = [
            'device_info',
            'meter_reading', 
            'alarm_info',
            'user_info',
            'substation_info'
        ]
        
        all_tables_exist = True
        
        for table_name in expected_tables:
            try:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    )
                """, (table_name,))
                
                table_exists = cursor.fetchone()[0]
                
                if table_exists:
                    print(f"✓ 表 {table_name} 存在")
                    
                    # 检查表结构
                    cursor.execute("""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = %s 
                        ORDER BY ordinal_position
                    """, (table_name,))
                    
                    columns = cursor.fetchall()
                    print(f"  - 列数: {len(columns)}")
                    
                else:
                    print(f"✗ 表 {table_name} 不存在")
                    all_tables_exist = False
                    
            except Exception as e:
                print(f"✗ 检查表 {table_name} 失败: {e}")
                all_tables_exist = False
        
        if all_tables_exist:
            self.test_results.append(("业务数据表结构", "PASS", f"所有 {len(expected_tables)} 个表都存在"))
        else:
            self.test_results.append(("业务数据表结构", "FAIL", "部分表缺失"))
            
        return all_tables_exist
    
    def test_cdc_replication_slot(self):
        """测试 CDC 复制槽配置"""
        print("测试 CDC 复制槽配置...")
        cursor = self.conn.cursor()
        
        try:
            # 检查 WAL 级别
            cursor.execute("SHOW wal_level")
            wal_level = cursor.fetchone()[0]
            
            if wal_level == 'logical':
                print(f"✓ WAL 级别正确: {wal_level}")
            else:
                print(f"✗ WAL 级别不正确: {wal_level} (期望: logical)")
                self.test_results.append(("CDC WAL 级别", "FAIL", f"当前: {wal_level}, 期望: logical"))
                return False
            
            # 检查复制槽
            cursor.execute("""
                SELECT slot_name, plugin, slot_type, active 
                FROM pg_replication_slots 
                WHERE slot_name = 'flink_cdc_slot'
            """)
            
            slot_info = cursor.fetchone()
            
            if slot_info:
                slot_name, plugin, slot_type, active = slot_info
                print(f"✓ CDC 复制槽存在: {slot_name}")
                print(f"  - 插件: {plugin}")
                print(f"  - 类型: {slot_type}")
                print(f"  - 活跃: {active}")
                
                self.test_results.append(("CDC 复制槽", "PASS", f"槽名: {slot_name}, 插件: {plugin}"))
                return True
            else:
                print("✗ CDC 复制槽不存在")
                self.test_results.append(("CDC 复制槽", "FAIL", "flink_cdc_slot 不存在"))
                return False
                
        except Exception as e:
            print(f"✗ CDC 配置检查失败: {e}")
            self.test_results.append(("CDC 复制槽", "ERROR", str(e)))
            return False
    
    def test_crud_operations(self):
        """测试 CRUD 操作"""
        print("测试 CRUD 操作...")
        cursor = self.conn.cursor()
        
        try:
            # CREATE - 插入测试数据
            test_device_code = f"TEST_DEV_{int(time.time())}"
            cursor.execute("""
                INSERT INTO device_info (device_code, device_name, device_type, voltage_level, status, substation_id, location)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING device_id
            """, (test_device_code, "测试设备", "智能电表", "220V", "测试", "SS001", "测试位置"))
            
            device_id = cursor.fetchone()[0]
            print(f"✓ CREATE: 插入设备成功，ID: {device_id}")
            
            # READ - 读取数据
            cursor.execute("SELECT * FROM device_info WHERE device_id = %s", (device_id,))
            device_data = cursor.fetchone()
            
            if device_data:
                print(f"✓ READ: 读取设备成功，设备码: {device_data[1]}")
            else:
                print("✗ READ: 读取设备失败")
                return False
            
            # UPDATE - 更新数据
            cursor.execute("""
                UPDATE device_info 
                SET status = %s, update_time = %s 
                WHERE device_id = %s
            """, ("运行", datetime.now(), device_id))
            
            cursor.execute("SELECT status FROM device_info WHERE device_id = %s", (device_id,))
            updated_status = cursor.fetchone()[0]
            
            if updated_status == "运行":
                print(f"✓ UPDATE: 更新设备状态成功")
            else:
                print(f"✗ UPDATE: 更新设备状态失败，当前状态: {updated_status}")
                return False
            
            # DELETE - 删除数据
            cursor.execute("DELETE FROM device_info WHERE device_id = %s", (device_id,))
            
            cursor.execute("SELECT COUNT(*) FROM device_info WHERE device_id = %s", (device_id,))
            count = cursor.fetchone()[0]
            
            if count == 0:
                print(f"✓ DELETE: 删除设备成功")
            else:
                print(f"✗ DELETE: 删除设备失败，仍存在 {count} 条记录")
                return False
            
            self.conn.commit()
            self.test_results.append(("CRUD 操作", "PASS", "所有 CRUD 操作成功"))
            return True
            
        except Exception as e:
            print(f"✗ CRUD 操作失败: {e}")
            self.conn.rollback()
            self.test_results.append(("CRUD 操作", "ERROR", str(e)))
            return False
    
    def test_data_generator_functionality(self):
        """测试数据生成器功能"""
        print("测试数据生成器功能...")
        cursor = self.conn.cursor()
        
        try:
            # 获取当前数据量
            cursor.execute("SELECT COUNT(*) FROM meter_reading")
            initial_count = cursor.fetchone()[0]
            print(f"初始电表读数记录数: {initial_count}")
            
            cursor.execute("SELECT COUNT(*) FROM alarm_info")
            initial_alarm_count = cursor.fetchone()[0]
            print(f"初始告警记录数: {initial_alarm_count}")
            
            # 检查是否有最近的数据（最近5分钟内）
            cursor.execute("""
                SELECT COUNT(*) FROM meter_reading 
                WHERE create_time > %s
            """, (datetime.now() - timedelta(minutes=5),))
            
            recent_readings = cursor.fetchone()[0]
            
            if recent_readings > 0:
                print(f"✓ 数据生成器正在工作，最近5分钟内生成了 {recent_readings} 条读数记录")
                self.test_results.append(("数据生成器", "PASS", f"最近5分钟生成 {recent_readings} 条记录"))
                return True
            else:
                print("⚠ 数据生成器可能未运行或刚启动，最近5分钟内无新数据")
                self.test_results.append(("数据生成器", "WARNING", "最近5分钟内无新数据"))
                return False
                
        except Exception as e:
            print(f"✗ 数据生成器测试失败: {e}")
            self.test_results.append(("数据生成器", "ERROR", str(e)))
            return False
    
    def test_initial_data(self):
        """测试初始数据是否正确加载"""
        print("测试初始数据...")
        cursor = self.conn.cursor()
        
        try:
            # 检查各表的初始数据量
            tables_data = {}
            
            cursor.execute("SELECT COUNT(*) FROM device_info")
            tables_data['device_info'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM substation_info")
            tables_data['substation_info'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM user_info")
            tables_data['user_info'] = cursor.fetchone()[0]
            
            print("初始数据统计:")
            for table, count in tables_data.items():
                print(f"  - {table}: {count} 条记录")
            
            # 验证是否有基础数据
            if all(count > 0 for count in tables_data.values()):
                print("✓ 所有基础表都有初始数据")
                self.test_results.append(("初始数据", "PASS", f"总计: {sum(tables_data.values())} 条记录"))
                return True
            else:
                print("✗ 部分基础表缺少初始数据")
                self.test_results.append(("初始数据", "FAIL", "部分表无数据"))
                return False
                
        except Exception as e:
            print(f"✗ 初始数据检查失败: {e}")
            self.test_results.append(("初始数据", "ERROR", str(e)))
            return False
    
    def generate_test_report(self):
        """生成测试报告"""
        print("\n" + "="*60)
        print("PostgreSQL 数据源配置测试报告")
        print("="*60)
        print(f"测试时间: {datetime.now()}")
        print(f"测试项目数: {len(self.test_results)}")
        
        passed = sum(1 for _, status, _ in self.test_results if status == "PASS")
        failed = sum(1 for _, status, _ in self.test_results if status == "FAIL")
        errors = sum(1 for _, status, _ in self.test_results if status == "ERROR")
        warnings = sum(1 for _, status, _ in self.test_results if status == "WARNING")
        
        print(f"通过: {passed}, 失败: {failed}, 错误: {errors}, 警告: {warnings}")
        print("-"*60)
        
        for test_name, status, details in self.test_results:
            status_symbol = {
                "PASS": "✓",
                "FAIL": "✗", 
                "ERROR": "⚠",
                "WARNING": "!"
            }.get(status, "?")
            
            print(f"{status_symbol} {test_name}: {status}")
            if details:
                print(f"  详情: {details}")
        
        print("-"*60)
        
        if failed == 0 and errors == 0:
            print("✓ PostgreSQL 数据源配置测试全部通过")
            return True
        else:
            print("✗ PostgreSQL 数据源配置测试存在问题")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=== PostgreSQL 数据源环境配置测试 ===")
        
        # 连接数据库
        if not self.connect_database():
            print("无法连接数据库，测试终止")
            return False
        
        try:
            # 运行各项测试
            tests = [
                self.test_postgresql_version,
                self.test_database_tables,
                self.test_cdc_replication_slot,
                self.test_initial_data,
                self.test_crud_operations,
                self.test_data_generator_functionality
            ]
            
            for test_func in tests:
                try:
                    test_func()
                    print()  # 空行分隔
                except Exception as e:
                    print(f"测试执行异常: {e}")
                    self.test_results.append((test_func.__name__, "ERROR", str(e)))
            
            # 生成报告
            return self.generate_test_report()
            
        finally:
            if self.conn:
                self.conn.close()

def main():
    """主函数"""
    tester = PostgreSQLDataSourceTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 PostgreSQL 数据源配置验证成功！")
        sys.exit(0)
    else:
        print("\n❌ PostgreSQL 数据源配置验证失败！")
        sys.exit(1)

if __name__ == "__main__":
    main()