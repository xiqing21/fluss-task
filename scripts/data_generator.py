#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - 数据生成器
持续生成模拟的国网业务数据
"""

import psycopg2
import random
import time
import schedule
from datetime import datetime, timedelta
from faker import Faker
import json
import sys

# 初始化 Faker
fake = Faker('zh_CN')

class PowerGridDataGenerator:
    def __init__(self):
        self.conn = None
        self.device_ids = []
        self.substation_ids = []
        self.connect_database()
        self.load_reference_data()
    
    def connect_database(self):
        """连接数据库"""
        max_retries = 10
        for i in range(max_retries):
            try:
                self.conn = psycopg2.connect(
                    host="localhost",
                    port=5432,
                    database="power_grid",
                    user="postgres",
                    password="postgres"
                )
                print(f"数据库连接成功 - {datetime.now()}")
                return
            except Exception as e:
                print(f"数据库连接失败 ({i+1}/{max_retries}): {e}")
                time.sleep(5)
        
        print("数据库连接失败，退出程序")
        sys.exit(1)
    
    def load_reference_data(self):
        """加载参考数据"""
        cursor = self.conn.cursor()
        
        # 获取设备ID列表
        cursor.execute("SELECT device_id FROM device_info WHERE status = '运行'")
        self.device_ids = [row[0] for row in cursor.fetchall()]
        
        # 获取变电站ID列表
        cursor.execute("SELECT substation_id FROM substation_info")
        self.substation_ids = [row[0] for row in cursor.fetchall()]
        
        print(f"加载参考数据 - 设备: {len(self.device_ids)}, 变电站: {len(self.substation_ids)}")
    
    def generate_meter_reading(self):
        """生成电表读数数据"""
        if not self.device_ids:
            return
        
        cursor = self.conn.cursor()
        
        # 随机选择设备
        device_id = random.choice(self.device_ids)
        
        # 生成读数数据
        reading_data = {
            'device_id': device_id,
            'reading_time': datetime.now(),
            'active_power': round(random.uniform(10.0, 1000.0), 2),
            'voltage': round(random.uniform(200.0, 240.0), 2),
            'current': round(random.uniform(5.0, 50.0), 2),
            'power_factor': round(random.uniform(0.8, 1.0), 3),
            'energy_consumption': round(random.uniform(100.0, 10000.0), 2),
            'data_quality': random.choice(['正常', '正常', '正常', '异常', '缺失'])
        }
        
        try:
            cursor.execute("""
                INSERT INTO meter_reading 
                (device_id, reading_time, active_power, voltage, current, power_factor, energy_consumption, data_quality)
                VALUES (%(device_id)s, %(reading_time)s, %(active_power)s, %(voltage)s, %(current)s, %(power_factor)s, %(energy_consumption)s, %(data_quality)s)
            """, reading_data)
            
            self.conn.commit()
            print(f"生成电表读数 - 设备: {device_id}, 功率: {reading_data['active_power']}kW")
            
        except Exception as e:
            print(f"插入电表读数失败: {e}")
            self.conn.rollback()
    
    def generate_alarm_info(self):
        """生成告警信息数据"""
        if not self.device_ids:
            return
        
        # 随机决定是否生成告警（10% 概率）
        if random.random() > 0.1:
            return
        
        cursor = self.conn.cursor()
        
        # 随机选择设备
        device_id = random.choice(self.device_ids)
        
        # 告警类型和描述
        alarm_types = [
            ('电压异常', '电压超出正常范围'),
            ('电流异常', '电流过载'),
            ('功率异常', '功率波动异常'),
            ('温度异常', '设备温度过高'),
            ('通信异常', '设备通信中断'),
            ('设备故障', '设备运行异常')
        ]
        
        alarm_type, alarm_desc = random.choice(alarm_types)
        
        # 生成告警数据
        alarm_data = {
            'device_id': device_id,
            'alarm_time': datetime.now(),
            'alarm_level': random.choice(['低', '中', '高', '紧急']),
            'alarm_type': alarm_type,
            'alarm_desc': alarm_desc,
            'alarm_value': round(random.uniform(0.0, 1000.0), 2),
            'threshold_value': round(random.uniform(0.0, 1000.0), 2),
            'status': '未处理'
        }
        
        try:
            cursor.execute("""
                INSERT INTO alarm_info 
                (device_id, alarm_time, alarm_level, alarm_type, alarm_desc, alarm_value, threshold_value, status)
                VALUES (%(device_id)s, %(alarm_time)s, %(alarm_level)s, %(alarm_type)s, %(alarm_desc)s, %(alarm_value)s, %(threshold_value)s, %(status)s)
            """, alarm_data)
            
            self.conn.commit()
            print(f"生成告警信息 - 设备: {device_id}, 级别: {alarm_data['alarm_level']}, 类型: {alarm_type}")
            
        except Exception as e:
            print(f"插入告警信息失败: {e}")
            self.conn.rollback()
    
    def update_device_status(self):
        """随机更新设备状态"""
        if not self.device_ids:
            return
        
        # 随机决定是否更新设备状态（5% 概率）
        if random.random() > 0.05:
            return
        
        cursor = self.conn.cursor()
        
        # 随机选择设备
        device_id = random.choice(self.device_ids)
        
        # 随机选择新状态
        new_status = random.choice(['运行', '运行', '运行', '检修', '故障'])
        
        try:
            cursor.execute("""
                UPDATE device_info 
                SET status = %s, update_time = %s 
                WHERE device_id = %s
            """, (new_status, datetime.now(), device_id))
            
            self.conn.commit()
            print(f"更新设备状态 - 设备: {device_id}, 状态: {new_status}")
            
            # 如果设备状态变为非运行，从运行设备列表中移除
            if new_status != '运行' and device_id in self.device_ids:
                self.device_ids.remove(device_id)
            
        except Exception as e:
            print(f"更新设备状态失败: {e}")
            self.conn.rollback()
    
    def generate_batch_data(self):
        """批量生成数据"""
        print(f"=== 批量数据生成开始 - {datetime.now()} ===")
        
        # 生成多条电表读数
        for _ in range(random.randint(5, 15)):
            self.generate_meter_reading()
            time.sleep(0.1)  # 避免时间戳完全相同
        
        # 生成告警信息
        self.generate_alarm_info()
        
        # 更新设备状态
        self.update_device_status()
        
        print(f"=== 批量数据生成完成 - {datetime.now()} ===")
    
    def get_statistics(self):
        """获取数据统计信息"""
        cursor = self.conn.cursor()
        
        # 获取今日数据统计
        today = datetime.now().date()
        
        cursor.execute("SELECT COUNT(*) FROM meter_reading WHERE DATE(create_time) = %s", (today,))
        today_readings = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM alarm_info WHERE DATE(create_time) = %s", (today,))
        today_alarms = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM device_info WHERE status = '运行'")
        running_devices = cursor.fetchone()[0]
        
        print(f"数据统计 - 今日读数: {today_readings}, 今日告警: {today_alarms}, 运行设备: {running_devices}")
    
    def run(self):
        """运行数据生成器"""
        print("=== 国网实时数仓数据生成器启动 ===")
        
        # 调度任务
        schedule.every(10).seconds.do(self.generate_batch_data)
        schedule.every(1).minutes.do(self.get_statistics)
        schedule.every(5).minutes.do(self.load_reference_data)  # 定期重新加载参考数据
        
        # 立即生成一批数据
        self.generate_batch_data()
        
        # 主循环
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                print("数据生成器停止")
                break
            except Exception as e:
                print(f"数据生成器异常: {e}")
                time.sleep(5)
                # 重新连接数据库
                try:
                    self.connect_database()
                    self.load_reference_data()
                except:
                    print("重新连接失败，退出程序")
                    break

def main():
    """主函数"""
    generator = PowerGridDataGenerator()
    generator.run()

if __name__ == "__main__":
    main()