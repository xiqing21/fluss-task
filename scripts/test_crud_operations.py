#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - CRUD 操作测试脚本

测试 PostgreSQL 数据库的 CRUD 操作功能
Requirements: 4.4 - 支持对源数据库的 CRUD 操作测试
"""

import psycopg2
import time
import random
from datetime import datetime
from faker import Faker

fake = Faker('zh_CN')

class CRUDOperationsTester:
    def __init__(self):
        self.conn = None
        self.test_device_ids = []
        
    def connect_database(self):
        """连接数据库"""
        try:
            self.conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="power_grid",
                user="postgres",
                password="postgres",
                connect_timeout=10
            )
            print("✓ 数据库连接成功")
            return True
        except Exception as e:
            print(f"✗ 数据库连接失败: {e}")
            return False
    
    def test_create_operations(self):
        """测试 CREATE 操作"""
        print("\n=== 测试 CREATE 操作 ===")
        cursor = self.conn.cursor()
        
        try:
            # 创建测试设备
            for i in range(3):
                device_code = f"TEST_CRUD_{int(time.time())}_{i}"
                device_name = f"CRUD测试设备{i+1}"
                device_type = random.choice(["智能电表", "变压器", "开关设备"])
                voltage_level = random.choice(["220V", "380V", "10kV", "35kV"])
                
                cursor.execute("""
                    INSERT INTO device_info (device_code, device_name, device_type, voltage_level, status, substation_id, location)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING device_id
                """, (device_code, device_name, device_type, voltage_level, "测试", "SS001", "测试位置"))
                
                device_id = cursor.fetchone()[0]
                self.test_device_ids.append(device_id)
                print(f"✓ 创建设备成功: ID={device_id}, 设备码={device_code}")
            
            # 为每个设备创建电表读数
            for device_id in self.test_device_ids:
                cursor.execute("""
                    INSERT INTO meter_reading (device_id, reading_time, active_power, voltage, current, power_factor, energy_consumption)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (device_id, datetime.now(), 
                     round(random.uniform(10.0, 1000.0), 2),
                     round(random.uniform(200.0, 240.0), 2),
                     round(random.uniform(5.0, 50.0), 2),
                     round(random.uniform(0.8, 1.0), 3),
                     round(random.uniform(100.0, 10000.0), 2)))
                
                print(f"✓ 为设备 {device_id} 创建电表读数")
            
            self.conn.commit()
            print(f"✓ CREATE 操作测试完成，创建了 {len(self.test_device_ids)} 个设备和对应的读数")
            return True
            
        except Exception as e:
            print(f"✗ CREATE 操作失败: {e}")
            self.conn.rollback()
            return False
    
    def test_read_operations(self):
        """测试 READ 操作"""
        print("\n=== 测试 READ 操作 ===")
        cursor = self.conn.cursor()
        
        try:
            # 读取设备信息
            cursor.execute("SELECT COUNT(*) FROM device_info WHERE device_id = ANY(%s)", (self.test_device_ids,))
            device_count = cursor.fetchone()[0]
            print(f"✓ 读取到 {device_count} 个测试设备")
            
            # 读取设备详细信息
            for device_id in self.test_device_ids:
                cursor.execute("""
                    SELECT device_code, device_name, device_type, status 
                    FROM device_info 
                    WHERE device_id = %s
                """, (device_id,))
                
                device_info = cursor.fetchone()
                if device_info:
                    device_code, device_name, device_type, status = device_info
                    print(f"✓ 设备 {device_id}: {device_code} - {device_name} ({device_type}) - {status}")
                else:
                    print(f"✗ 无法读取设备 {device_id}")
                    return False
            
            # 读取电表读数
            cursor.execute("""
                SELECT COUNT(*) FROM meter_reading 
                WHERE device_id = ANY(%s)
            """, (self.test_device_ids,))
            
            reading_count = cursor.fetchone()[0]
            print(f"✓ 读取到 {reading_count} 条电表读数")
            
            # 联合查询测试
            cursor.execute("""
                SELECT d.device_code, d.device_name, COUNT(m.reading_id) as reading_count
                FROM device_info d
                LEFT JOIN meter_reading m ON d.device_id = m.device_id
                WHERE d.device_id = ANY(%s)
                GROUP BY d.device_id, d.device_code, d.device_name
                ORDER BY d.device_code
            """, (self.test_device_ids,))
            
            join_results = cursor.fetchall()
            print("✓ 联合查询结果:")
            for device_code, device_name, reading_count in join_results:
                print(f"  - {device_code} ({device_name}): {reading_count} 条读数")
            
            print("✓ READ 操作测试完成")
            return True
            
        except Exception as e:
            print(f"✗ READ 操作失败: {e}")
            return False
    
    def test_update_operations(self):
        """测试 UPDATE 操作"""
        print("\n=== 测试 UPDATE 操作 ===")
        cursor = self.conn.cursor()
        
        try:
            # 更新设备状态
            new_statuses = ["运行", "检修", "故障"]
            
            for i, device_id in enumerate(self.test_device_ids):
                new_status = new_statuses[i % len(new_statuses)]
                
                cursor.execute("""
                    UPDATE device_info 
                    SET status = %s, update_time = %s 
                    WHERE device_id = %s
                """, (new_status, datetime.now(), device_id))
                
                print(f"✓ 更新设备 {device_id} 状态为: {new_status}")
            
            # 验证更新结果
            cursor.execute("""
                SELECT device_id, device_code, status 
                FROM device_info 
                WHERE device_id = ANY(%s)
                ORDER BY device_id
            """, (self.test_device_ids,))
            
            updated_devices = cursor.fetchall()
            print("✓ 更新后的设备状态:")
            for device_id, device_code, status in updated_devices:
                print(f"  - 设备 {device_id} ({device_code}): {status}")
            
            # 批量更新测试
            cursor.execute("""
                UPDATE device_info 
                SET location = %s, update_time = %s 
                WHERE device_id = ANY(%s)
            """, ("批量更新测试位置", datetime.now(), self.test_device_ids))
            
            affected_rows = cursor.rowcount
            print(f"✓ 批量更新完成，影响 {affected_rows} 行")
            
            self.conn.commit()
            print("✓ UPDATE 操作测试完成")
            return True
            
        except Exception as e:
            print(f"✗ UPDATE 操作失败: {e}")
            self.conn.rollback()
            return False
    
    def test_delete_operations(self):
        """测试 DELETE 操作"""
        print("\n=== 测试 DELETE 操作 ===")
        cursor = self.conn.cursor()
        
        try:
            # 先删除相关的电表读数（外键约束）
            cursor.execute("""
                DELETE FROM meter_reading 
                WHERE device_id = ANY(%s)
            """, (self.test_device_ids,))
            
            deleted_readings = cursor.rowcount
            print(f"✓ 删除了 {deleted_readings} 条电表读数")
            
            # 删除设备信息
            cursor.execute("""
                DELETE FROM device_info 
                WHERE device_id = ANY(%s)
            """, (self.test_device_ids,))
            
            deleted_devices = cursor.rowcount
            print(f"✓ 删除了 {deleted_devices} 个设备")
            
            # 验证删除结果
            cursor.execute("""
                SELECT COUNT(*) FROM device_info 
                WHERE device_id = ANY(%s)
            """, (self.test_device_ids,))
            
            remaining_devices = cursor.fetchone()[0]
            
            if remaining_devices == 0:
                print("✓ 所有测试设备已成功删除")
            else:
                print(f"✗ 仍有 {remaining_devices} 个设备未删除")
                return False
            
            self.conn.commit()
            print("✓ DELETE 操作测试完成")
            return True
            
        except Exception as e:
            print(f"✗ DELETE 操作失败: {e}")
            self.conn.rollback()
            return False
    
    def run_crud_tests(self):
        """运行所有 CRUD 测试"""
        print("=== PostgreSQL CRUD 操作测试 ===")
        print(f"测试时间: {datetime.now()}")
        
        if not self.connect_database():
            return False
        
        try:
            tests = [
                ("CREATE", self.test_create_operations),
                ("READ", self.test_read_operations),
                ("UPDATE", self.test_update_operations),
                ("DELETE", self.test_delete_operations)
            ]
            
            passed = 0
            total = len(tests)
            
            for test_name, test_func in tests:
                print(f"\n--- {test_name} 操作测试 ---")
                if test_func():
                    passed += 1
                    print(f"✓ {test_name} 操作测试通过")
                else:
                    print(f"✗ {test_name} 操作测试失败")
            
            print(f"\n=== CRUD 测试结果 ===")
            print(f"通过: {passed}/{total}")
            
            if passed == total:
                print("🎉 所有 CRUD 操作测试通过！")
                return True
            else:
                print("❌ 部分 CRUD 操作测试失败！")
                return False
                
        finally:
            if self.conn:
                self.conn.close()

def main():
    """主函数"""
    tester = CRUDOperationsTester()
    success = tester.run_crud_tests()
    
    if success:
        print("\n✅ PostgreSQL CRUD 操作验证成功！")
        return 0
    else:
        print("\n❌ PostgreSQL CRUD 操作验证失败！")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())