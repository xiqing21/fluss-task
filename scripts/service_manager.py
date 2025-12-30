#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - 服务管理器
提供统一的服务管理和监控机制
"""

import subprocess
import time
import json
import logging
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class ServiceManager:
    """服务管理器 - 统一管理所有服务进程"""
    
    def __init__(self, log_level=logging.INFO):
        """初始化服务管理器"""
        self.setup_logging(log_level)
        self.services_config = {
            'sshd': {
                'description': 'SSH 服务',
                'critical': True,
                'startup_time': 5,
                'health_check': self._check_ssh_service
            },
            'postgresql': {
                'description': 'PostgreSQL 数据库',
                'critical': True,
                'startup_time': 30,
                'health_check': self._check_postgresql_service
            },
            'flink-fluss-cluster': {
                'description': 'Flink + Fluss 集群',
                'critical': True,
                'startup_time': 60,
                'health_check': self._check_flink_fluss_service
            },
            'doris-fe': {
                'description': 'Doris Frontend',
                'critical': True,
                'startup_time': 45,
                'health_check': self._check_doris_fe_service
            },
            'doris-be': {
                'description': 'Doris Backend',
                'critical': True,
                'startup_time': 45,
                'health_check': self._check_doris_be_service
            },
            'grafana': {
                'description': 'Grafana 可视化',
                'critical': True,
                'startup_time': 30,
                'health_check': self._check_grafana_service
            },
            'data-generator': {
                'description': '数据生成器',
                'critical': False,
                'startup_time': 10,
                'health_check': self._check_process_service
            },
            'health-check': {
                'description': '健康检查服务',
                'critical': False,
                'startup_time': 5,
                'health_check': self._check_process_service
            }
        }
        
    def setup_logging(self, log_level):
        """设置日志配置"""
        # 创建日志目录
        try:
            log_dir = '/opt/logs'
            os.makedirs(log_dir, exist_ok=True)
        except (OSError, PermissionError):
            log_dir = 'logs'
            os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'service_manager.log')),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('ServiceManager')
        
    def get_supervisor_status(self) -> Dict[str, str]:
        """获取 Supervisor 管理的所有服务状态"""
        try:
            result = subprocess.run(['supervisorctl', 'status'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                self.logger.error(f"Failed to get supervisor status: {result.stderr}")
                return {}
            
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
            self.logger.error(f"Error getting supervisor status: {e}")
            return {}
    
    def start_service(self, service_name: str) -> bool:
        """启动指定服务"""
        try:
            self.logger.info(f"Starting service: {service_name}")
            result = subprocess.run(['supervisorctl', 'start', service_name], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.logger.info(f"Service {service_name} started successfully")
                return True
            else:
                self.logger.error(f"Failed to start service {service_name}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error starting service {service_name}: {e}")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """停止指定服务"""
        try:
            self.logger.info(f"Stopping service: {service_name}")
            result = subprocess.run(['supervisorctl', 'stop', service_name], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.logger.info(f"Service {service_name} stopped successfully")
                return True
            else:
                self.logger.error(f"Failed to stop service {service_name}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping service {service_name}: {e}")
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """重启指定服务"""
        try:
            self.logger.info(f"Restarting service: {service_name}")
            result = subprocess.run(['supervisorctl', 'restart', service_name], 
                                  capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                self.logger.info(f"Service {service_name} restarted successfully")
                return True
            else:
                self.logger.error(f"Failed to restart service {service_name}: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error restarting service {service_name}: {e}")
            return False
    
    def wait_for_service_startup(self, service_name: str, max_wait_time: Optional[int] = None) -> bool:
        """等待服务启动完成"""
        if max_wait_time is None:
            max_wait_time = self.services_config.get(service_name, {}).get('startup_time', 30)
        
        self.logger.info(f"Waiting for service {service_name} to start (max {max_wait_time}s)")
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            supervisor_status = self.get_supervisor_status()
            if service_name in supervisor_status and supervisor_status[service_name] == 'RUNNING':
                # 服务在 supervisor 中显示为运行，进行健康检查
                if self._perform_service_health_check(service_name):
                    self.logger.info(f"Service {service_name} is ready")
                    return True
            
            time.sleep(2)
        
        self.logger.warning(f"Service {service_name} did not start within {max_wait_time} seconds")
        return False
    
    def start_all_services(self) -> Dict[str, bool]:
        """启动所有服务"""
        self.logger.info("Starting all services...")
        results = {}
        
        # 按优先级启动服务（关键服务优先）
        critical_services = [name for name, config in self.services_config.items() if config['critical']]
        non_critical_services = [name for name, config in self.services_config.items() if not config['critical']]
        
        # 启动关键服务
        for service_name in critical_services:
            results[service_name] = self.start_service(service_name)
            if results[service_name]:
                self.wait_for_service_startup(service_name)
        
        # 启动非关键服务
        for service_name in non_critical_services:
            results[service_name] = self.start_service(service_name)
            if results[service_name]:
                self.wait_for_service_startup(service_name)
        
        return results
    
    def get_service_logs(self, service_name: str, lines: int = 50) -> str:
        """获取服务日志"""
        try:
            result = subprocess.run(['supervisorctl', 'tail', '-' + str(lines), service_name], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error getting logs: {result.stderr}"
                
        except Exception as e:
            return f"Error getting logs: {e}"
    
    def _check_ssh_service(self) -> bool:
        """检查 SSH 服务"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', 22))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _check_postgresql_service(self) -> bool:
        """检查 PostgreSQL 服务"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost", port=5432, database="power_grid",
                user="postgres", password="postgres", connect_timeout=5
            )
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception:
            return False
    
    def _check_flink_fluss_service(self) -> bool:
        """检查 Flink + Fluss 服务"""
        try:
            import requests
            # 检查 Flink Web UI
            response = requests.get("http://localhost:8081", timeout=5)
            return response.status_code in [200, 302]
        except Exception:
            return False
    
    def _check_doris_fe_service(self) -> bool:
        """检查 Doris Frontend 服务"""
        try:
            import requests
            response = requests.get("http://localhost:8030", timeout=5)
            return response.status_code in [200, 302, 401]
        except Exception:
            return False
    
    def _check_doris_be_service(self) -> bool:
        """检查 Doris Backend 服务"""
        try:
            import requests
            response = requests.get("http://localhost:8040", timeout=5)
            return response.status_code in [200, 302, 401]
        except Exception:
            return False
    
    def _check_grafana_service(self) -> bool:
        """检查 Grafana 服务"""
        try:
            import requests
            response = requests.get("http://localhost:3000", timeout=5)
            return response.status_code in [200, 302]
        except Exception:
            return False
    
    def _check_process_service(self) -> bool:
        """检查进程类服务（通过 supervisor 状态）"""
        # 对于纯进程服务，只要在 supervisor 中显示 RUNNING 就认为正常
        return True
    
    def _perform_service_health_check(self, service_name: str) -> bool:
        """执行服务健康检查"""
        if service_name not in self.services_config:
            return False
        
        health_check_func = self.services_config[service_name]['health_check']
        try:
            return health_check_func()
        except Exception as e:
            self.logger.error(f"Health check failed for {service_name}: {e}")
            return False
    
    def get_system_status(self) -> Dict:
        """获取系统整体状态"""
        supervisor_status = self.get_supervisor_status()
        service_health = {}
        
        for service_name in self.services_config.keys():
            supervisor_state = supervisor_status.get(service_name, 'UNKNOWN')
            health_ok = False
            
            if supervisor_state == 'RUNNING':
                health_ok = self._perform_service_health_check(service_name)
            
            service_health[service_name] = {
                'supervisor_status': supervisor_state,
                'health_check': health_ok,
                'description': self.services_config[service_name]['description'],
                'critical': self.services_config[service_name]['critical']
            }
        
        # 计算整体健康状态
        total_services = len(service_health)
        healthy_services = len([s for s in service_health.values() 
                              if s['supervisor_status'] == 'RUNNING' and s['health_check']])
        critical_services = len([s for s in service_health.values() if s['critical']])
        healthy_critical = len([s for s in service_health.values() 
                              if s['critical'] and s['supervisor_status'] == 'RUNNING' and s['health_check']])
        
        return {
            'timestamp': datetime.now().isoformat(),
            'services': service_health,
            'summary': {
                'total_services': total_services,
                'healthy_services': healthy_services,
                'health_percentage': (healthy_services / total_services) * 100,
                'critical_services': critical_services,
                'healthy_critical': healthy_critical,
                'critical_health_percentage': (healthy_critical / critical_services) * 100 if critical_services > 0 else 0
            }
        }
    
    def auto_recovery(self) -> Dict[str, bool]:
        """自动恢复异常服务"""
        self.logger.info("Starting auto recovery process...")
        recovery_results = {}
        
        supervisor_status = self.get_supervisor_status()
        
        for service_name, config in self.services_config.items():
            current_status = supervisor_status.get(service_name, 'UNKNOWN')
            
            if current_status != 'RUNNING':
                self.logger.warning(f"Service {service_name} is not running (status: {current_status}), attempting recovery...")
                recovery_results[service_name] = self.restart_service(service_name)
                
                if recovery_results[service_name]:
                    # 等待服务启动并验证健康状态
                    if self.wait_for_service_startup(service_name):
                        self.logger.info(f"Service {service_name} recovered successfully")
                    else:
                        self.logger.error(f"Service {service_name} failed to recover properly")
                        recovery_results[service_name] = False
            else:
                # 服务在运行，检查健康状态
                if not self._perform_service_health_check(service_name):
                    self.logger.warning(f"Service {service_name} health check failed, attempting restart...")
                    recovery_results[service_name] = self.restart_service(service_name)
                    
                    if recovery_results[service_name]:
                        self.wait_for_service_startup(service_name)
        
        return recovery_results
    
    def generate_status_report(self) -> str:
        """生成状态报告"""
        status = self.get_system_status()
        
        report = []
        report.append("=== 国网实时数仓服务状态报告 ===")
        report.append(f"报告时间: {status['timestamp']}")
        report.append("")
        
        # 整体状态
        summary = status['summary']
        report.append("=== 整体状态 ===")
        report.append(f"总服务数: {summary['total_services']}")
        report.append(f"健康服务数: {summary['healthy_services']}")
        report.append(f"整体健康度: {summary['health_percentage']:.1f}%")
        report.append(f"关键服务数: {summary['critical_services']}")
        report.append(f"关键服务健康度: {summary['critical_health_percentage']:.1f}%")
        report.append("")
        
        # 服务详情
        report.append("=== 服务详情 ===")
        for service_name, service_info in status['services'].items():
            status_symbol = "✓" if (service_info['supervisor_status'] == 'RUNNING' and service_info['health_check']) else "✗"
            critical_mark = "[关键]" if service_info['critical'] else "[普通]"
            
            report.append(f"{status_symbol} {service_name:20} {critical_mark:6} - {service_info['description']}")
            report.append(f"    Supervisor: {service_info['supervisor_status']:10} | 健康检查: {'通过' if service_info['health_check'] else '失败'}")
        
        report.append("")
        report.append("=== 报告结束 ===")
        
        return "\n".join(report)


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python3 service_manager.py <command> [args]")
        print("Commands:")
        print("  status                    - 显示系统状态")
        print("  start <service>          - 启动指定服务")
        print("  stop <service>           - 停止指定服务")
        print("  restart <service>        - 重启指定服务")
        print("  start-all                - 启动所有服务")
        print("  logs <service> [lines]   - 显示服务日志")
        print("  auto-recovery            - 自动恢复异常服务")
        print("  report                   - 生成状态报告")
        sys.exit(1)
    
    manager = ServiceManager()
    command = sys.argv[1]
    
    if command == "status":
        status = manager.get_system_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
    
    elif command == "start" and len(sys.argv) >= 3:
        service_name = sys.argv[2]
        success = manager.start_service(service_name)
        if success:
            manager.wait_for_service_startup(service_name)
        sys.exit(0 if success else 1)
    
    elif command == "stop" and len(sys.argv) >= 3:
        service_name = sys.argv[2]
        success = manager.stop_service(sys.argv[2])
        sys.exit(0 if success else 1)
    
    elif command == "restart" and len(sys.argv) >= 3:
        service_name = sys.argv[2]
        success = manager.restart_service(service_name)
        if success:
            manager.wait_for_service_startup(service_name)
        sys.exit(0 if success else 1)
    
    elif command == "start-all":
        results = manager.start_all_services()
        failed_services = [name for name, success in results.items() if not success]
        if failed_services:
            print(f"Failed to start services: {', '.join(failed_services)}")
            sys.exit(1)
        else:
            print("All services started successfully")
            sys.exit(0)
    
    elif command == "logs":
        if len(sys.argv) < 3:
            print("Usage: service_manager.py logs <service> [lines]")
            sys.exit(1)
        
        service_name = sys.argv[2]
        lines = int(sys.argv[3]) if len(sys.argv) >= 4 else 50
        logs = manager.get_service_logs(service_name, lines)
        print(logs)
    
    elif command == "auto-recovery":
        results = manager.auto_recovery()
        recovered_services = [name for name, success in results.items() if success]
        failed_services = [name for name, success in results.items() if not success]
        
        if recovered_services:
            print(f"Recovered services: {', '.join(recovered_services)}")
        if failed_services:
            print(f"Failed to recover services: {', '.join(failed_services)}")
        
        sys.exit(0 if not failed_services else 1)
    
    elif command == "report":
        report = manager.generate_status_report()
        print(report)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()