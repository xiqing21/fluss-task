#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - 数据生成连续性测试

Property-based test for Data Generation Continuity:
- Property 4: Data Generation Continuity
- Validates: Requirements 4.3, 4.4

测试数据生成器的连续性和数据库 CRUD 操作的正确性
"""

import psycopg2
import time
import subprocess
import signal
import os
import sys
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
import pytest
import threading
import multiprocessing


class DataGenerationContinuityTester:
    def __init__(self):
        self.conn = None
        self.data_generator_process = None
        
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
    
    def start_data_generator(self):
        """启动数据生成器进程"""
        try:
            # 获取数据生成器脚本路径
            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     "scripts", "data_generator.py")
            
            if not os.path.exists(script_path):
                print(f"数据生成器脚本不存在: {script_path}")
                return False
            
            # 启动数据生成器进程
            self.data_generator_process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # 创建新的进程组
            )
            
            # 等待进程启动
            time.sleep(3)
            
            # 检查进程是否正在运行
            if self.data_generator_process.poll() is None:
                print("数据生成器启动成功")
                return True
            else:
                print("数据生成器启动失败")
                return False
                
        except Exception as e:
            print(f"启动数据生成器失败: {e}")
            return False
    
    def stop_data_generator(self):
        """停止数据生成器进程"""
        if self.data_generator_process:
            try:
                # 发送 SIGTERM 信号给进程组
                os.killpg(os.getpgid(self.data_generator_process.pid), signal.SIGTERM)
                
                # 等待进程结束
                self.data_generator_process.wait(timeout=10)
                print("数据生成器已停止")
                
            except subprocess.TimeoutExpired:
                # 如果进程没有响应，强制终止
                os.killpg(os.getpgid(self.data_generator_process.pid), signal.SIGKILL)
                print("数据生成器已强制终止")
                
            except Exception as e:
                print(f"停止数据生成器失败: {e}")
            
            finally:
                self.data_generator_process = None
    
    def get_record_counts(self):
        """获取各表的记录数量"""
        if not self.conn:
            return None
            
        cursor = self.conn.cursor()
        counts = {}
        
        try:
            # 获取电表读数记录数
            cursor.execute("SELECT COUNT(*) FROM meter_reading")
            counts['meter_reading'] = cursor.fetchone()[0]
            
            # 获取告警信息记录数
            cursor.execute("SELECT COUNT(*) FROM alarm_info")
            counts['alarm_info'] = cursor.fetchone()[0]
            
            # 获取设备信息记录数
            cursor.execute("SELECT COUNT(*) FROM device_info")
            counts['device_info'] = cursor.fetchone()[0]
            
            return counts
            
        except Exception as e:
            print(f"获取记录数失败: {e}")
            return None
    
    def get_recent_records(self, minutes=5):
        """获取最近几分钟内的记录数"""
        if not self.conn:
            return None
            
        cursor = self.conn.cursor()
        recent_counts = {}
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        try:
            # 获取最近的电表读数记录数
            cursor.execute("""
                SELECT COUNT(*) FROM meter_reading 
                WHERE create_time > %s
            """, (cutoff_time,))
            recent_counts['meter_reading'] = cursor.fetchone()[0]
            
            # 获取最近的告警信息记录数
            cursor.execute("""
                SELECT COUNT(*) FROM alarm_info 
                WHERE create_time > %s
            """, (cutoff_time,))
            recent_counts['alarm_info'] = cursor.fetchone()[0]
            
            return recent_counts
            
        except Exception as e:
            print(f"获取最近记录数失败: {e}")
            return None
    
    def test_crud_operations(self, device_count):
        """测试 CRUD 操作"""
        if not self.conn:
            return False
            
        cursor = self.conn.cursor()
        created_device_ids = []
        
        try:
            # CREATE - 批量插入测试设备
            for i in range(device_count):
                test_device_code = f"TEST_CONTINUITY_{int(time.time())}_{i}"
                cursor.execute("""
                    INSERT INTO device_info (device_code, device_name, device_type, voltage_level, status, substation_id, location)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING device_id
                """, (test_device_code, f"连续性测试设备{i}", "智能电表", "220V", "测试", "SS001", f"测试位置{i}"))
                
                device_id = cursor.fetchone()[0]
                created_device_ids.append(device_id)
            
            self.conn.commit()
            
            # READ - 验证所有设备都能读取
            for device_id in created_device_ids:
                cursor.execute("SELECT device_code FROM device_info WHERE device_id = %s", (device_id,))
                result = cursor.fetchone()
                if not result:
                    return False
            
            # UPDATE - 批量更新设备状态
            for device_id in created_device_ids:
                cursor.execute("""
                    UPDATE device_info 
                    SET status = %s, update_time = %s 
                    WHERE device_id = %s
                """, ("运行", datetime.now(), device_id))
            
            self.conn.commit()
            
            # 验证更新结果
            cursor.execute("""
                SELECT COUNT(*) FROM device_info 
                WHERE device_id = ANY(%s) AND status = '运行'
            """, (created_device_ids,))
            
            updated_count = cursor.fetchone()[0]
            if updated_count != len(created_device_ids):
                return False
            
            # DELETE - 清理测试数据
            cursor.execute("""
                DELETE FROM device_info 
                WHERE device_id = ANY(%s)
            """, (created_device_ids,))
            
            self.conn.commit()
            
            # 验证删除结果
            cursor.execute("""
                SELECT COUNT(*) FROM device_info 
                WHERE device_id = ANY(%s)
            """, (created_device_ids,))
            
            remaining_count = cursor.fetchone()[0]
            return remaining_count == 0
            
        except Exception as e:
            print(f"CRUD 操作测试失败: {e}")
            self.conn.rollback()
            
            # 清理可能残留的测试数据
            try:
                if created_device_ids:
                    cursor.execute("""
                        DELETE FROM device_info 
                        WHERE device_id = ANY(%s)
                    """, (created_device_ids,))
                    self.conn.commit()
            except:
                pass
                
            return False
    
    def cleanup(self):
        """清理资源"""
        self.stop_data_generator()
        if self.conn:
            self.conn.close()


# Property-based test implementation
@given(st.integers(min_value=1, max_value=5))  # Test with different monitoring durations
@settings(max_examples=3, deadline=180000)  # 3 minutes timeout for each test
def test_data_generation_continuity_property(monitoring_duration_minutes):
    """
    Property 4: Data Generation Continuity
    Feature: power-grid-realtime-warehouse, Property 4: Data Generation Continuity
    
    For any running data generator, it should continuously produce valid business data 
    that gets successfully inserted into the source database.
    
    Validates: Requirements 4.3, 4.4
    """
    tester = DataGenerationContinuityTester()
    
    try:
        # 尝试连接数据库
        if not tester.connect_database():
            pytest.skip("PostgreSQL 服务未运行，跳过真实环境测试。请确保 PostgreSQL 服务正在运行或使用 Mock 版本测试。")
        
        # 获取初始记录数
        initial_counts = tester.get_record_counts()
        assert initial_counts is not None, "无法获取初始记录数"
        
        print(f"初始记录数: {initial_counts}")
        
        # 启动数据生成器
        assert tester.start_data_generator(), "无法启动数据生成器"
        
        # 监控数据生成的连续性
        monitoring_start = time.time()
        monitoring_end = monitoring_start + (monitoring_duration_minutes * 60)
        
        previous_counts = initial_counts.copy()
        continuous_generation_verified = False
        
        while time.time() < monitoring_end:
            time.sleep(30)  # 每30秒检查一次
            
            current_counts = tester.get_record_counts()
            assert current_counts is not None, "无法获取当前记录数"
            
            # 验证数据持续增长
            meter_reading_increased = current_counts['meter_reading'] > previous_counts['meter_reading']
            
            if meter_reading_increased:
                continuous_generation_verified = True
                print(f"数据生成验证成功: 电表读数从 {previous_counts['meter_reading']} 增加到 {current_counts['meter_reading']}")
            
            previous_counts = current_counts.copy()
        
        # 验证数据生成的连续性
        assert continuous_generation_verified, "数据生成器未能持续生成数据"
        
        # 获取最终记录数
        final_counts = tester.get_record_counts()
        assert final_counts is not None, "无法获取最终记录数"
        
        # 验证总体数据增长
        total_increase = final_counts['meter_reading'] - initial_counts['meter_reading']
        assert total_increase > 0, f"电表读数未增长: 初始 {initial_counts['meter_reading']}, 最终 {final_counts['meter_reading']}"
        
        print(f"数据生成连续性验证成功: 总共生成了 {total_increase} 条电表读数记录")
        
        # 测试 CRUD 操作 (Requirements 4.4)
        crud_device_count = min(monitoring_duration_minutes * 2, 10)  # 根据监控时长调整测试设备数量
        crud_success = tester.test_crud_operations(crud_device_count)
        assert crud_success, f"CRUD 操作测试失败，测试设备数量: {crud_device_count}"
        
        print(f"CRUD 操作验证成功: 成功测试了 {crud_device_count} 个设备的完整 CRUD 操作")
        
        # 验证最近数据的生成
        recent_records = tester.get_recent_records(minutes=2)
        assert recent_records is not None, "无法获取最近记录数"
        assert recent_records['meter_reading'] > 0, "最近2分钟内未生成电表读数记录"
        
        print(f"最近数据验证成功: 最近2分钟内生成了 {recent_records['meter_reading']} 条电表读数记录")
        
    finally:
        tester.cleanup()


def test_data_generation_continuity_unit():
    """
    单元测试：数据生成连续性基础功能
    验证数据生成器的基本启动和数据生成能力
    """
    tester = DataGenerationContinuityTester()
    
    try:
        # 尝试连接数据库
        if not tester.connect_database():
            pytest.skip("PostgreSQL 服务未运行，跳过真实环境测试。请确保 PostgreSQL 服务正在运行或使用 Mock 版本测试。")
        
        # 获取初始记录数
        initial_counts = tester.get_record_counts()
        assert initial_counts is not None, "无法获取初始记录数"
        assert isinstance(initial_counts, dict), "记录数格式不正确"
        assert 'meter_reading' in initial_counts, "缺少电表读数记录数"
        assert 'alarm_info' in initial_counts, "缺少告警信息记录数"
        assert 'device_info' in initial_counts, "缺少设备信息记录数"
        
        # 测试基本 CRUD 操作
        crud_success = tester.test_crud_operations(3)
        assert crud_success, "基本 CRUD 操作测试失败"
        
        print("数据生成连续性单元测试通过")
        
    finally:
        tester.cleanup()


def test_data_generation_continuity_edge_cases():
    """
    边界条件测试：数据生成连续性的边界情况
    """
    tester = DataGenerationContinuityTester()
    
    try:
        # 尝试连接数据库
        if not tester.connect_database():
            pytest.skip("PostgreSQL 服务未运行，跳过真实环境测试。请确保 PostgreSQL 服务正在运行或使用 Mock 版本测试。")
        
        # 测试空设备列表的 CRUD 操作
        crud_success = tester.test_crud_operations(1)
        assert crud_success, "单设备 CRUD 操作测试失败"
        
        # 测试获取不存在时间范围的记录
        very_old_records = tester.get_recent_records(minutes=0.1)  # 6秒内
        assert very_old_records is not None, "获取极短时间范围记录失败"
        
        print("数据生成连续性边界条件测试通过")
        
    finally:
        tester.cleanup()


if __name__ == "__main__":
    # 运行单元测试
    print("=== 数据生成连续性单元测试 ===")
    test_data_generation_continuity_unit()
    
    print("\n=== 数据生成连续性边界条件测试 ===")
    test_data_generation_continuity_edge_cases()
    
    print("\n=== 数据生成连续性属性测试 ===")
    # 运行属性测试（简化版本，用于手动测试）
    test_data_generation_continuity_property(2)  # 2分钟监控
    
    print("\n🎉 所有数据生成连续性测试通过！")