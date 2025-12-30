#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - 数据库初始化脚本
创建业务数据表结构和初始化数据
"""

import psycopg2
import sys
import time
from datetime import datetime

def connect_database():
    """连接 PostgreSQL 数据库"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="power_grid",
            user="postgres",
            password="postgres"
        )
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def create_tables(conn):
    """创建业务数据表"""
    cursor = conn.cursor()
    
    # 创建设备信息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_info (
            device_id BIGSERIAL PRIMARY KEY,
            device_code VARCHAR(50) UNIQUE NOT NULL,
            device_name VARCHAR(100) NOT NULL,
            device_type VARCHAR(50) NOT NULL,
            voltage_level VARCHAR(20),
            status VARCHAR(20) DEFAULT '运行',
            substation_id VARCHAR(50),
            location VARCHAR(200),
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 创建电表读数表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meter_reading (
            reading_id BIGSERIAL PRIMARY KEY,
            device_id BIGINT REFERENCES device_info(device_id),
            reading_time TIMESTAMP NOT NULL,
            active_power DECIMAL(10,2),
            voltage DECIMAL(8,2),
            current DECIMAL(8,2),
            power_factor DECIMAL(4,3),
            energy_consumption DECIMAL(12,2),
            data_quality VARCHAR(50) DEFAULT '正常',
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 创建告警信息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alarm_info (
            alarm_id BIGSERIAL PRIMARY KEY,
            device_id BIGINT REFERENCES device_info(device_id),
            alarm_time TIMESTAMP NOT NULL,
            alarm_level VARCHAR(20) NOT NULL,
            alarm_type VARCHAR(50) NOT NULL,
            alarm_desc TEXT,
            alarm_value DECIMAL(10,2),
            threshold_value DECIMAL(10,2),
            status VARCHAR(20) DEFAULT '未处理',
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 创建用户信息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_info (
            user_id BIGSERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            user_type VARCHAR(20) NOT NULL,
            department VARCHAR(100),
            phone VARCHAR(20),
            email VARCHAR(100),
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # 创建变电站信息表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS substation_info (
            substation_id VARCHAR(50) PRIMARY KEY,
            substation_name VARCHAR(100) NOT NULL,
            voltage_level VARCHAR(20),
            capacity DECIMAL(10,2),
            location VARCHAR(200),
            region VARCHAR(50),
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    conn.commit()
    print("数据表创建完成")

def insert_initial_data(conn):
    """插入初始测试数据"""
    cursor = conn.cursor()
    
    # 插入变电站信息
    substations = [
        ('SS001', '北京变电站', '220kV', 500.00, '北京市朝阳区', '华北'),
        ('SS002', '上海变电站', '110kV', 300.00, '上海市浦东新区', '华东'),
        ('SS003', '广州变电站', '35kV', 200.00, '广州市天河区', '南方'),
        ('SS004', '深圳变电站', '10kV', 150.00, '深圳市南山区', '南方'),
        ('SS005', '成都变电站', '220kV', 400.00, '成都市高新区', '西南')
    ]
    
    for substation in substations:
        cursor.execute("""
            INSERT INTO substation_info (substation_id, substation_name, voltage_level, capacity, location, region)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (substation_id) DO NOTHING
        """, substation)
    
    # 插入设备信息
    devices = [
        ('DEV001', '智能电表-001', '智能电表', '220V', '运行', 'SS001', '1号配电室'),
        ('DEV002', '变压器-001', '变压器', '35kV', '运行', 'SS001', '主变压器室'),
        ('DEV003', '开关设备-001', '开关设备', '10kV', '运行', 'SS002', '开关室'),
        ('DEV004', '保护装置-001', '保护装置', '220V', '运行', 'SS002', '保护室'),
        ('DEV005', '智能电表-002', '智能电表', '380V', '运行', 'SS003', '2号配电室'),
        ('DEV006', '变压器-002', '变压器', '110kV', '检修', 'SS003', '备用变压器室'),
        ('DEV007', '开关设备-002', '开关设备', '35kV', '运行', 'SS004', '高压开关室'),
        ('DEV008', '智能电表-003', '智能电表', '220V', '运行', 'SS004', '3号配电室'),
        ('DEV009', '保护装置-002', '保护装置', '220V', '运行', 'SS005', '继电保护室'),
        ('DEV010', '变压器-003', '变压器', '220kV', '运行', 'SS005', '主变压器室')
    ]
    
    for device in devices:
        cursor.execute("""
            INSERT INTO device_info (device_code, device_name, device_type, voltage_level, status, substation_id, location)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_code) DO NOTHING
        """, device)
    
    # 插入用户信息
    users = [
        ('admin', '系统管理员', '运维部', '13800138000', 'admin@powergrid.com'),
        ('operator1', '运行人员', '运行部', '13800138001', 'operator1@powergrid.com'),
        ('engineer1', '工程师', '技术部', '13800138002', 'engineer1@powergrid.com'),
        ('analyst1', '数据分析师', '数据部', '13800138003', 'analyst1@powergrid.com'),
        ('manager1', '部门经理', '管理部', '13800138004', 'manager1@powergrid.com')
    ]
    
    for user in users:
        cursor.execute("""
            INSERT INTO user_info (username, user_type, department, phone, email)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO NOTHING
        """, user)
    
    conn.commit()
    print("初始数据插入完成")

def setup_cdc_replication(conn):
    """设置 CDC 复制槽"""
    cursor = conn.cursor()
    
    try:
        # 创建复制槽
        cursor.execute("SELECT pg_create_logical_replication_slot('flink_cdc_slot', 'pgoutput');")
        print("CDC 复制槽创建成功")
    except psycopg2.Error as e:
        if "already exists" in str(e):
            print("CDC 复制槽已存在")
        else:
            print(f"创建 CDC 复制槽失败: {e}")
    
    conn.commit()

def main():
    """主函数"""
    print("=== 国网实时数仓数据库初始化 ===")
    print(f"开始时间: {datetime.now()}")
    
    # 等待 PostgreSQL 启动
    max_retries = 30
    for i in range(max_retries):
        conn = connect_database()
        if conn:
            break
        print(f"等待数据库启动... ({i+1}/{max_retries})")
        time.sleep(2)
    
    if not conn:
        print("数据库连接失败，退出初始化")
        sys.exit(1)
    
    try:
        # 创建数据表
        create_tables(conn)
        
        # 插入初始数据
        insert_initial_data(conn)
        
        # 设置 CDC 复制槽
        setup_cdc_replication(conn)
        
        print("=== 数据库初始化完成 ===")
        
        # 显示统计信息
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM device_info")
        device_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM substation_info")
        substation_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_info")
        user_count = cursor.fetchone()[0]
        
        print(f"变电站数量: {substation_count}")
        print(f"设备数量: {device_count}")
        print(f"用户数量: {user_count}")
        
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()