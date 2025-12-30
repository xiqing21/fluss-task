#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - 健康检查脚本
监控各服务组件的运行状态
"""

import psycopg2
import requests
import socket
import subprocess
import time
import json
from datetime import datetime
import schedule
import sys

class HealthChecker:
    def __init__(self):
        self.services = {
            'postgresql': {'port': 5432, 'type': 'database'},
            'flink-web': {'port': 8081, 'type': 'http'},
            'flink-rest': {'port': 8082, 'type': 'http'},
            'fluss-web': {'port': 8084, 'type': 'http'},
            'fluss-bootstrap': {'port': 9123, 'type': 'tcp'},
            'grafana': {'port': 3000, 'type': 'http'},
            'doris-fe': {'port': 8030, 'type': 'http'},
            'doris-mysql': {'port': 9030, 'type': 'tcp'},
            'doris-be': {'port': 8040, 'type': 'http'},
            'ssh': {'port': 22, 'type': 'tcp'}
        }
        self.status_history = {}
    
    def check_port(self, host, port, timeout=5):
        """检查端口连通性"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as e:
            return False
    
    def check_http_service(self, url, timeout=5):
        """检查 HTTP 服务"""
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            return False
    
    def check_postgresql(self):
        """检查 PostgreSQL 数据库"""
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
        except Exception as e:
            return False
    
    def check_flink_jobs(self):
        """检查 Flink 作业状态"""
        try:
            response = requests.get("http://localhost:8081/jobs", timeout=5)
            if response.status_code == 200:
                jobs = response.json()
                return {
                    'total_jobs': len(jobs.get('jobs', [])),
                    'running_jobs': len([job for job in jobs.get('jobs', []) if job.get('status') == 'RUNNING'])
                }
        except Exception as e:
            pass
        return {'total_jobs': 0, 'running_jobs': 0}
    
    def check_supervisor_services(self):
        """检查 Supervisor 管理的服务"""
        try:
            result = subprocess.run(['supervisorctl', 'status'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                services = {}
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 2:
                            service_name = parts[0]
                            service_status = parts[1]
                            services[service_name] = service_status
                return services
        except Exception as e:
            pass
        return {}
    
    def get_system_resources(self):
        """获取系统资源使用情况"""
        try:
            # CPU 使用率
            cpu_result = subprocess.run(['top', '-bn1'], capture_output=True, text=True, timeout=5)
            cpu_usage = "Unknown"
            for line in cpu_result.stdout.split('\n'):
                if 'Cpu(s):' in line:
                    cpu_usage = line.strip()
                    break
            
            # 内存使用情况
            mem_result = subprocess.run(['free', '-h'], capture_output=True, text=True, timeout=5)
            memory_info = mem_result.stdout.strip().split('\n')[1] if mem_result.returncode == 0 else "Unknown"
            
            # 磁盘使用情况
            disk_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
            disk_info = disk_result.stdout.strip().split('\n')[1] if disk_result.returncode == 0 else "Unknown"
            
            return {
                'cpu': cpu_usage,
                'memory': memory_info,
                'disk': disk_info
            }
        except Exception as e:
            return {
                'cpu': f"Error: {e}",
                'memory': f"Error: {e}",
                'disk': f"Error: {e}"
            }
    
    def perform_health_check(self):
        """执行健康检查"""
        print(f"\n=== 健康检查开始 - {datetime.now()} ===")
        
        check_results = {}
        
        # 检查网络端口
        for service_name, config in self.services.items():
            port = config['port']
            service_type = config['type']
            
            if service_type == 'tcp':
                status = self.check_port('localhost', port)
            elif service_type == 'http':
                port_status = self.check_port('localhost', port)
                if port_status:
                    status = self.check_http_service(f'http://localhost:{port}')
                else:
                    status = False
            elif service_type == 'database':
                status = self.check_postgresql()
            else:
                status = self.check_port('localhost', port)
            
            check_results[service_name] = {
                'status': 'UP' if status else 'DOWN',
                'port': port,
                'timestamp': datetime.now().isoformat()
            }
            
            status_symbol = "✓" if status else "✗"
            print(f"{status_symbol} {service_name:15} - 端口 {port:5} - {'UP' if status else 'DOWN'}")
        
        # 检查 PostgreSQL 特殊功能
        if check_results['postgresql']['status'] == 'UP':
            try:
                conn = psycopg2.connect(
                    host="localhost", port=5432, database="power_grid",
                    user="postgres", password="postgres", connect_timeout=5
                )
                cursor = conn.cursor()
                
                # 检查表数量
                cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
                table_count = cursor.fetchone()[0]
                
                # 检查数据量
                cursor.execute("SELECT COUNT(*) FROM device_info")
                device_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM meter_reading WHERE DATE(create_time) = CURRENT_DATE")
                today_readings = cursor.fetchone()[0]
                
                conn.close()
                
                print(f"  数据库详情: 表数量={table_count}, 设备数量={device_count}, 今日读数={today_readings}")
                
            except Exception as e:
                print(f"  数据库详情检查失败: {e}")
        
        # 检查 Flink 作业
        if check_results['flink-web']['status'] == 'UP':
            flink_jobs = self.check_flink_jobs()
            print(f"  Flink 作业: 总数={flink_jobs['total_jobs']}, 运行中={flink_jobs['running_jobs']}")
        
        # 检查 Supervisor 服务
        supervisor_services = self.check_supervisor_services()
        if supervisor_services:
            print("  Supervisor 服务状态:")
            for service, status in supervisor_services.items():
                status_symbol = "✓" if status == 'RUNNING' else "✗"
                print(f"    {status_symbol} {service:20} - {status}")
        
        # 检查系统资源
        resources = self.get_system_resources()
        print("  系统资源:")
        print(f"    CPU: {resources['cpu']}")
        print(f"    内存: {resources['memory']}")
        print(f"    磁盘: {resources['disk']}")
        
        # 保存检查结果
        self.status_history[datetime.now().isoformat()] = check_results
        
        # 计算总体健康状态
        total_services = len(check_results)
        healthy_services = len([s for s in check_results.values() if s['status'] == 'UP'])
        health_percentage = (healthy_services / total_services) * 100
        
        print(f"\n总体健康状态: {healthy_services}/{total_services} ({health_percentage:.1f}%)")
        
        # 如果健康状态低于80%，记录警告
        if health_percentage < 80:
            print("⚠️  警告: 系统健康状态低于80%，请检查故障服务")
        
        print(f"=== 健康检查完成 - {datetime.now()} ===\n")
        
        return check_results
    
    def generate_health_report(self):
        """生成健康检查报告"""
        if not self.status_history:
            return
        
        print("\n=== 健康检查报告 ===")
        
        # 最近的检查结果
        latest_check = list(self.status_history.keys())[-1]
        latest_results = self.status_history[latest_check]
        
        print(f"最近检查时间: {latest_check}")
        print("服务状态汇总:")
        
        for service, result in latest_results.items():
            print(f"  {service:15} - {result['status']:4} - 端口 {result['port']}")
        
        # 如果有历史数据，显示趋势
        if len(self.status_history) > 1:
            print("\n服务可用性趋势 (最近5次检查):")
            recent_checks = list(self.status_history.keys())[-5:]
            
            for service in self.services.keys():
                statuses = []
                for check_time in recent_checks:
                    if check_time in self.status_history:
                        status = self.status_history[check_time].get(service, {}).get('status', 'UNKNOWN')
                        statuses.append('✓' if status == 'UP' else '✗')
                
                print(f"  {service:15} - {' '.join(statuses)}")
        
        print("=== 报告结束 ===\n")
    
    def run(self):
        """运行健康检查器"""
        print("=== 国网实时数仓健康检查器启动 ===")
        
        # 调度任务
        schedule.every(30).seconds.do(self.perform_health_check)
        schedule.every(5).minutes.do(self.generate_health_report)
        
        # 立即执行一次检查
        self.perform_health_check()
        
        # 主循环
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                print("健康检查器停止")
                break
            except Exception as e:
                print(f"健康检查器异常: {e}")
                time.sleep(10)

def main():
    """主函数"""
    checker = HealthChecker()
    checker.run()

if __name__ == "__main__":
    main()