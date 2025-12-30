#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
国网实时数仓测试环境 - 自动恢复机制
实现服务异常自动重启功能
"""

import time
import logging
import sys
import os
import json
import threading
import signal
from datetime import datetime, timedelta
from service_manager import ServiceManager
try:
    from system_monitor import SystemMonitor
    SYSTEM_MONITOR_AVAILABLE = True
except ImportError:
    SYSTEM_MONITOR_AVAILABLE = False
    print("Warning: SystemMonitor not available, some monitoring features will be disabled")

class AutoRecoveryManager:
    """自动恢复管理器"""
    
    def __init__(self, config_file=None):
        """初始化自动恢复管理器"""
        self.setup_logging()
        self.service_manager = ServiceManager()
        if SYSTEM_MONITOR_AVAILABLE:
            self.system_monitor = SystemMonitor()
        else:
            self.system_monitor = None
        
        # 默认配置
        self.config = {
            'check_interval': 30,  # 检查间隔（秒）
            'max_recovery_attempts': 3,  # 最大恢复尝试次数
            'recovery_cooldown': 300,  # 恢复冷却时间（秒）
            'health_check_timeout': 60,  # 健康检查超时时间（秒）
            'critical_services_only': False,  # 是否只恢复关键服务
            'auto_restart_enabled': True,  # 是否启用自动重启
            'notification_enabled': True,  # 是否启用通知
            'max_consecutive_failures': 5  # 最大连续失败次数
        }
        
        # 加载配置文件
        if config_file and os.path.exists(config_file):
            self.load_config(config_file)
        
        # 运行状态
        self.running = True
        self.recovery_history = {}  # 恢复历史记录
        self.failure_counts = {}  # 失败计数
        self.last_recovery_time = {}  # 上次恢复时间
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def setup_logging(self):
        """设置日志配置"""
        # 创建日志目录
        try:
            log_dir = '/opt/logs'
            os.makedirs(log_dir, exist_ok=True)
        except (OSError, PermissionError):
            log_dir = 'logs'
            os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'auto_recovery.log')),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger('AutoRecovery')
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info("收到停止信号，正在关闭自动恢复...")
        self.running = False
    
    def load_config(self, config_file):
        """加载配置文件"""
        try:
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                self.config.update(user_config)
            self.logger.info(f"已加载配置文件: {config_file}")
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
    
    def save_config(self, config_file):
        """保存配置文件"""
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.logger.info(f"配置已保存到: {config_file}")
        except Exception as e:
            self.logger.error(f"保存配置文件失败: {e}")
    
    def should_attempt_recovery(self, service_name):
        """判断是否应该尝试恢复服务"""
        # 检查是否启用自动重启
        if not self.config['auto_restart_enabled']:
            return False
        
        # 检查是否只恢复关键服务
        if self.config['critical_services_only']:
            service_config = self.service_manager.services_config.get(service_name, {})
            if not service_config.get('critical', False):
                return False
        
        # 检查恢复冷却时间
        if service_name in self.last_recovery_time:
            time_since_last = datetime.now() - self.last_recovery_time[service_name]
            if time_since_last.total_seconds() < self.config['recovery_cooldown']:
                self.logger.info(f"服务 {service_name} 在冷却期内，跳过恢复")
                return False
        
        # 检查连续失败次数
        failure_count = self.failure_counts.get(service_name, 0)
        if failure_count >= self.config['max_consecutive_failures']:
            self.logger.warning(f"服务 {service_name} 连续失败次数过多 ({failure_count})，停止自动恢复")
            return False
        
        # 检查恢复尝试次数
        if service_name in self.recovery_history:
            recent_attempts = [
                attempt for attempt in self.recovery_history[service_name]
                if datetime.fromisoformat(attempt['timestamp']) > datetime.now() - timedelta(hours=1)
            ]
            if len(recent_attempts) >= self.config['max_recovery_attempts']:
                self.logger.warning(f"服务 {service_name} 1小时内恢复尝试次数过多，停止自动恢复")
                return False
        
        return True
    
    def record_recovery_attempt(self, service_name, success, error_message=None):
        """记录恢复尝试"""
        if service_name not in self.recovery_history:
            self.recovery_history[service_name] = []
        
        attempt_record = {
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'error_message': error_message
        }
        
        self.recovery_history[service_name].append(attempt_record)
        
        # 限制历史记录大小
        if len(self.recovery_history[service_name]) > 50:
            self.recovery_history[service_name] = self.recovery_history[service_name][-50:]
        
        # 更新失败计数
        if success:
            self.failure_counts[service_name] = 0
            self.last_recovery_time[service_name] = datetime.now()
        else:
            self.failure_counts[service_name] = self.failure_counts.get(service_name, 0) + 1
    
    def attempt_service_recovery(self, service_name):
        """尝试恢复单个服务"""
        self.logger.info(f"开始恢复服务: {service_name}")
        
        try:
            # 尝试重启服务
            success = self.service_manager.restart_service(service_name)
            
            if success:
                # 等待服务启动并验证健康状态
                self.logger.info(f"等待服务 {service_name} 启动...")
                startup_success = self.service_manager.wait_for_service_startup(
                    service_name, self.config['health_check_timeout']
                )
                
                if startup_success:
                    self.logger.info(f"服务 {service_name} 恢复成功")
                    self.record_recovery_attempt(service_name, True)
                    self.send_notification(f"服务恢复成功: {service_name}")
                    return True
                else:
                    error_msg = f"服务 {service_name} 重启后健康检查失败"
                    self.logger.error(error_msg)
                    self.record_recovery_attempt(service_name, False, error_msg)
                    return False
            else:
                error_msg = f"服务 {service_name} 重启失败"
                self.logger.error(error_msg)
                self.record_recovery_attempt(service_name, False, error_msg)
                return False
                
        except Exception as e:
            error_msg = f"恢复服务 {service_name} 时发生异常: {e}"
            self.logger.error(error_msg)
            self.record_recovery_attempt(service_name, False, error_msg)
            return False
    
    def check_and_recover_services(self):
        """检查并恢复异常服务"""
        self.logger.debug("开始检查服务状态...")
        
        # 获取系统状态
        system_status = self.service_manager.get_system_status()
        
        recovery_needed = []
        
        # 检查每个服务
        for service_name, service_info in system_status['services'].items():
            supervisor_status = service_info['supervisor_status']
            health_check = service_info['health_check']
            
            # 判断服务是否需要恢复
            needs_recovery = False
            reason = ""
            
            if supervisor_status != 'RUNNING':
                needs_recovery = True
                reason = f"Supervisor状态异常: {supervisor_status}"
            elif not health_check:
                needs_recovery = True
                reason = "健康检查失败"
            
            if needs_recovery:
                if self.should_attempt_recovery(service_name):
                    recovery_needed.append((service_name, reason))
                    self.logger.warning(f"服务 {service_name} 需要恢复: {reason}")
                else:
                    self.logger.info(f"服务 {service_name} 异常但跳过恢复: {reason}")
        
        # 执行恢复
        recovery_results = {}
        for service_name, reason in recovery_needed:
            self.logger.info(f"正在恢复服务 {service_name} (原因: {reason})")
            recovery_results[service_name] = self.attempt_service_recovery(service_name)
        
        return recovery_results
    
    def send_notification(self, message):
        """发送通知"""
        if not self.config['notification_enabled']:
            return
        
        try:
            # 记录到日志文件
            notification_log = "/opt/logs/notifications.log"
            timestamp = datetime.now().isoformat()
            
            with open(notification_log, "a") as f:
                f.write(f"{timestamp} - {message}\n")
            
            # 这里可以扩展其他通知方式，如邮件、短信、Webhook等
            self.logger.info(f"通知: {message}")
            
        except Exception as e:
            self.logger.error(f"发送通知失败: {e}")
    
    def generate_recovery_report(self):
        """生成恢复报告"""
        report = []
        report.append("=== 自动恢复报告 ===")
        report.append(f"报告时间: {datetime.now().isoformat()}")
        report.append("")
        
        # 配置信息
        report.append("=== 配置信息 ===")
        for key, value in self.config.items():
            report.append(f"{key}: {value}")
        report.append("")
        
        # 恢复历史统计
        report.append("=== 恢复历史统计 ===")
        if self.recovery_history:
            for service_name, attempts in self.recovery_history.items():
                total_attempts = len(attempts)
                successful_attempts = len([a for a in attempts if a['success']])
                success_rate = (successful_attempts / total_attempts) * 100 if total_attempts > 0 else 0
                
                report.append(f"服务 {service_name}:")
                report.append(f"  总尝试次数: {total_attempts}")
                report.append(f"  成功次数: {successful_attempts}")
                report.append(f"  成功率: {success_rate:.1f}%")
                report.append(f"  当前失败计数: {self.failure_counts.get(service_name, 0)}")
                
                # 最近的尝试
                if attempts:
                    last_attempt = attempts[-1]
                    report.append(f"  最后尝试: {last_attempt['timestamp']} ({'成功' if last_attempt['success'] else '失败'})")
                    if not last_attempt['success'] and last_attempt.get('error_message'):
                        report.append(f"  错误信息: {last_attempt['error_message']}")
                
                report.append("")
        else:
            report.append("暂无恢复历史记录")
        
        report.append("=== 报告结束 ===")
        
        return "\n".join(report)
    
    def run_daemon(self):
        """运行守护进程模式"""
        self.logger.info("启动自动恢复守护进程...")
        self.logger.info(f"检查间隔: {self.config['check_interval']} 秒")
        
        while self.running:
            try:
                # 执行检查和恢复
                recovery_results = self.check_and_recover_services()
                
                if recovery_results:
                    successful_recoveries = [name for name, success in recovery_results.items() if success]
                    failed_recoveries = [name for name, success in recovery_results.items() if not success]
                    
                    if successful_recoveries:
                        self.logger.info(f"成功恢复服务: {', '.join(successful_recoveries)}")
                    
                    if failed_recoveries:
                        self.logger.warning(f"恢复失败服务: {', '.join(failed_recoveries)}")
                        self.send_notification(f"服务恢复失败: {', '.join(failed_recoveries)}")
                
                # 等待下次检查
                time.sleep(self.config['check_interval'])
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"自动恢复过程中发生异常: {e}")
                time.sleep(10)  # 异常后等待10秒再继续
        
        self.logger.info("自动恢复守护进程已停止")
    
    def run_single_recovery(self):
        """运行单次恢复"""
        self.logger.info("执行单次自动恢复...")
        
        recovery_results = self.check_and_recover_services()
        
        if recovery_results:
            successful_recoveries = [name for name, success in recovery_results.items() if success]
            failed_recoveries = [name for name, success in recovery_results.items() if not success]
            
            print(f"恢复结果:")
            if successful_recoveries:
                print(f"  成功: {', '.join(successful_recoveries)}")
            if failed_recoveries:
                print(f"  失败: {', '.join(failed_recoveries)}")
            
            return len(failed_recoveries) == 0
        else:
            print("所有服务运行正常，无需恢复")
            return True


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python3 auto_recovery.py <command> [args]")
        print("Commands:")
        print("  daemon                   - 启动守护进程模式")
        print("  recover                  - 执行单次恢复")
        print("  report                   - 生成恢复报告")
        print("  config [file]            - 显示或加载配置")
        print("  save-config <file>       - 保存当前配置")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "daemon":
        config_file = sys.argv[2] if len(sys.argv) >= 3 else None
        manager = AutoRecoveryManager(config_file)
        manager.run_daemon()
    
    elif command == "recover":
        config_file = sys.argv[2] if len(sys.argv) >= 3 else None
        manager = AutoRecoveryManager(config_file)
        success = manager.run_single_recovery()
        sys.exit(0 if success else 1)
    
    elif command == "report":
        config_file = sys.argv[2] if len(sys.argv) >= 3 else None
        manager = AutoRecoveryManager(config_file)
        report = manager.generate_recovery_report()
        print(report)
    
    elif command == "config":
        config_file = sys.argv[2] if len(sys.argv) >= 3 else None
        manager = AutoRecoveryManager(config_file)
        print("当前配置:")
        print(json.dumps(manager.config, indent=2, ensure_ascii=False))
    
    elif command == "save-config" and len(sys.argv) >= 3:
        config_file = sys.argv[2]
        manager = AutoRecoveryManager()
        manager.save_config(config_file)
    
    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()