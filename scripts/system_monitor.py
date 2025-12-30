#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - 系统监控脚本
提供实时监控脚本显示系统运行状态
"""

import time
import os
import sys
import json
import subprocess
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available, some system metrics will be unavailable")

from datetime import datetime, timedelta
from service_manager import ServiceManager
import threading
import signal

class SystemMonitor:
    """系统监控器 - 实时显示系统运行状态"""
    
    def __init__(self):
        self.service_manager = ServiceManager()
        self.running = True
        self.monitor_interval = 10  # 监控间隔（秒）
        self.history_size = 100  # 保留历史记录数量
        self.status_history = []
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        print("\n正在停止监控...")
        self.running = False
    
    def get_system_resources(self):
        """获取系统资源使用情况"""
        if not PSUTIL_AVAILABLE:
            return {
                'error': 'psutil not available',
                'cpu': {'percent': 0, 'count': 0, 'load_avg': [0, 0, 0]},
                'memory': {'total': 0, 'available': 0, 'percent': 0, 'used': 0, 'free': 0},
                'disk': {'total': 0, 'used': 0, 'free': 0, 'percent': 0},
                'network': {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0},
                'processes': 0
            }
        
        try:
            # CPU 使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # 内存使用情况
            memory = psutil.virtual_memory()
            
            # 磁盘使用情况
            disk = psutil.disk_usage('/')
            
            # 网络统计
            network = psutil.net_io_counters()
            
            # 进程数量
            process_count = len(psutil.pids())
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used,
                    'free': memory.free
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': (disk.used / disk.total) * 100
                },
                'network': {
                    'bytes_sent': network.bytes_sent,
                    'bytes_recv': network.bytes_recv,
                    'packets_sent': network.packets_sent,
                    'packets_recv': network.packets_recv
                },
                'processes': process_count
            }
        except Exception as e:
            return {
                'error': str(e),
                'cpu': {'percent': 0, 'count': 0, 'load_avg': [0, 0, 0]},
                'memory': {'total': 0, 'available': 0, 'percent': 0, 'used': 0, 'free': 0},
                'disk': {'total': 0, 'used': 0, 'free': 0, 'percent': 0},
                'network': {'bytes_sent': 0, 'bytes_recv': 0, 'packets_sent': 0, 'packets_recv': 0},
                'processes': 0
            }
    
    def get_service_metrics(self):
        """获取服务相关指标"""
        metrics = {}
        
        try:
            # PostgreSQL 连接数
            import psycopg2
            conn = psycopg2.connect(
                host="localhost", port=5432, database="power_grid",
                user="postgres", password="postgres", connect_timeout=5
            )
            cursor = conn.cursor()
            
            # 获取连接数
            cursor.execute("SELECT count(*) FROM pg_stat_activity")
            pg_connections = cursor.fetchone()[0]
            
            # 获取数据库大小
            cursor.execute("SELECT pg_size_pretty(pg_database_size('power_grid'))")
            db_size = cursor.fetchone()[0]
            
            # 获取表记录数
            cursor.execute("SELECT COUNT(*) FROM device_info")
            device_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM meter_reading WHERE DATE(create_time) = CURRENT_DATE")
            today_readings = cursor.fetchone()[0]
            
            conn.close()
            
            metrics['postgresql'] = {
                'connections': pg_connections,
                'database_size': db_size,
                'device_count': device_count,
                'today_readings': today_readings
            }
        except Exception as e:
            metrics['postgresql'] = {'error': str(e)}
        
        try:
            # Flink 作业信息
            import requests
            response = requests.get("http://localhost:8081/jobs", timeout=5)
            if response.status_code == 200:
                jobs_data = response.json()
                metrics['flink'] = {
                    'total_jobs': len(jobs_data.get('jobs', [])),
                    'running_jobs': len([job for job in jobs_data.get('jobs', []) if job.get('status') == 'RUNNING']),
                    'jobs': jobs_data.get('jobs', [])
                }
            else:
                metrics['flink'] = {'error': f'HTTP {response.status_code}'}
        except Exception as e:
            metrics['flink'] = {'error': str(e)}
        
        return metrics
    
    def format_bytes(self, bytes_value):
        """格式化字节数"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    def display_status(self, system_status, resources, metrics):
        """显示系统状态"""
        # 清屏
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("=" * 80)
        print("国网实时数仓测试环境 - 系统监控")
        print(f"监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # 整体状态
        summary = system_status['summary']
        print(f"\n📊 整体状态:")
        print(f"   总服务数: {summary['total_services']}")
        print(f"   健康服务: {summary['healthy_services']} ({summary['health_percentage']:.1f}%)")
        print(f"   关键服务: {summary['healthy_critical']}/{summary['critical_services']} ({summary['critical_health_percentage']:.1f}%)")
        
        # 系统资源
        print(f"\n💻 系统资源:")
        print(f"   CPU 使用率: {resources['cpu']['percent']:.1f}% ({resources['cpu']['count']} 核)")
        print(f"   内存使用率: {resources['memory']['percent']:.1f}% ({self.format_bytes(resources['memory']['used'])}/{self.format_bytes(resources['memory']['total'])})")
        print(f"   磁盘使用率: {resources['disk']['percent']:.1f}% ({self.format_bytes(resources['disk']['used'])}/{self.format_bytes(resources['disk']['total'])})")
        print(f"   进程数量: {resources['processes']}")
        
        # 服务状态
        print(f"\n🔧 服务状态:")
        for service_name, service_info in system_status['services'].items():
            status_symbol = "✅" if (service_info['supervisor_status'] == 'RUNNING' and service_info['health_check']) else "❌"
            critical_mark = "🔴" if service_info['critical'] else "🟡"
            
            print(f"   {status_symbol} {critical_mark} {service_name:20} - {service_info['description']}")
            if service_info['supervisor_status'] != 'RUNNING' or not service_info['health_check']:
                print(f"      └─ Supervisor: {service_info['supervisor_status']}, 健康检查: {'通过' if service_info['health_check'] else '失败'}")
        
        # 数据库指标
        if 'postgresql' in metrics and 'error' not in metrics['postgresql']:
            pg_metrics = metrics['postgresql']
            print(f"\n🗄️  PostgreSQL 指标:")
            print(f"   连接数: {pg_metrics['connections']}")
            print(f"   数据库大小: {pg_metrics['database_size']}")
            print(f"   设备数量: {pg_metrics['device_count']}")
            print(f"   今日读数: {pg_metrics['today_readings']}")
        
        # Flink 指标
        if 'flink' in metrics and 'error' not in metrics['flink']:
            flink_metrics = metrics['flink']
            print(f"\n⚡ Flink 指标:")
            print(f"   总作业数: {flink_metrics['total_jobs']}")
            print(f"   运行中作业: {flink_metrics['running_jobs']}")
        
        # 历史趋势（如果有历史数据）
        if len(self.status_history) > 1:
            print(f"\n📈 健康度趋势 (最近10次):")
            recent_history = self.status_history[-10:]
            trend_line = ""
            for record in recent_history:
                health_pct = record['summary']['health_percentage']
                if health_pct >= 90:
                    trend_line += "🟢"
                elif health_pct >= 70:
                    trend_line += "🟡"
                else:
                    trend_line += "🔴"
            print(f"   {trend_line}")
        
        print(f"\n⏰ 下次更新: {self.monitor_interval} 秒后")
        print("按 Ctrl+C 停止监控")
        print("=" * 80)
    
    def check_alerts(self, system_status, resources):
        """检查告警条件"""
        alerts = []
        
        # 检查服务状态
        for service_name, service_info in system_status['services'].items():
            if service_info['critical'] and (service_info['supervisor_status'] != 'RUNNING' or not service_info['health_check']):
                alerts.append(f"🚨 关键服务异常: {service_name} - {service_info['description']}")
        
        # 检查资源使用率
        if resources['cpu']['percent'] > 90:
            alerts.append(f"🚨 CPU 使用率过高: {resources['cpu']['percent']:.1f}%")
        
        if resources['memory']['percent'] > 90:
            alerts.append(f"🚨 内存使用率过高: {resources['memory']['percent']:.1f}%")
        
        if resources['disk']['percent'] > 90:
            alerts.append(f"🚨 磁盘使用率过高: {resources['disk']['percent']:.1f}%")
        
        # 检查整体健康度
        if system_status['summary']['critical_health_percentage'] < 80:
            alerts.append(f"🚨 关键服务健康度低: {system_status['summary']['critical_health_percentage']:.1f}%")
        
        return alerts
    
    def log_alerts(self, alerts):
        """记录告警信息"""
        if alerts:
            alert_log_file = "/opt/logs/system_alerts.log"
            timestamp = datetime.now().isoformat()
            
            try:
                with open(alert_log_file, "a") as f:
                    for alert in alerts:
                        f.write(f"{timestamp} - {alert}\n")
            except Exception as e:
                print(f"Failed to log alerts: {e}")
    
    def run_continuous_monitoring(self):
        """运行连续监控"""
        print("启动系统监控...")
        
        while self.running:
            try:
                # 获取系统状态
                system_status = self.service_manager.get_system_status()
                resources = self.get_system_resources()
                metrics = self.get_service_metrics()
                
                # 保存历史记录
                record = {
                    'timestamp': datetime.now().isoformat(),
                    'summary': system_status['summary'],
                    'resources': resources
                }
                self.status_history.append(record)
                
                # 限制历史记录大小
                if len(self.status_history) > self.history_size:
                    self.status_history.pop(0)
                
                # 显示状态
                self.display_status(system_status, resources, metrics)
                
                # 检查告警
                alerts = self.check_alerts(system_status, resources)
                if alerts:
                    print("\n🚨 告警信息:")
                    for alert in alerts:
                        print(f"   {alert}")
                    self.log_alerts(alerts)
                
                # 等待下次监控
                time.sleep(self.monitor_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"监控异常: {e}")
                time.sleep(5)
        
        print("系统监控已停止")
    
    def run_single_check(self):
        """运行单次检查"""
        system_status = self.service_manager.get_system_status()
        resources = self.get_system_resources()
        metrics = self.get_service_metrics()
        
        self.display_status(system_status, resources, metrics)
        
        # 检查告警
        alerts = self.check_alerts(system_status, resources)
        if alerts:
            print("\n🚨 告警信息:")
            for alert in alerts:
                print(f"   {alert}")
        
        return len(alerts) == 0
    
    def export_status_json(self, output_file=None):
        """导出状态为 JSON 格式"""
        system_status = self.service_manager.get_system_status()
        resources = self.get_system_resources()
        metrics = self.get_service_metrics()
        
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'system_status': system_status,
            'resources': resources,
            'metrics': metrics,
            'history': self.status_history[-10:] if self.status_history else []
        }
        
        if output_file:
            try:
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                print(f"状态已导出到: {output_file}")
            except Exception as e:
                print(f"导出失败: {e}")
        else:
            print(json.dumps(export_data, indent=2, ensure_ascii=False))


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python3 system_monitor.py <command> [args]")
        print("Commands:")
        print("  monitor                  - 启动连续监控")
        print("  check                    - 执行单次检查")
        print("  export [file]            - 导出状态为 JSON")
        print("  set-interval <seconds>   - 设置监控间隔")
        sys.exit(1)
    
    monitor = SystemMonitor()
    command = sys.argv[1]
    
    if command == "monitor":
        monitor.run_continuous_monitoring()
    
    elif command == "check":
        success = monitor.run_single_check()
        sys.exit(0 if success else 1)
    
    elif command == "export":
        output_file = sys.argv[2] if len(sys.argv) >= 3 else None
        monitor.export_status_json(output_file)
    
    elif command == "set-interval" and len(sys.argv) >= 3:
        try:
            interval = int(sys.argv[2])
            if interval < 1:
                print("监控间隔必须大于等于1秒")
                sys.exit(1)
            monitor.monitor_interval = interval
            print(f"监控间隔已设置为 {interval} 秒")
        except ValueError:
            print("无效的间隔时间")
            sys.exit(1)
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()