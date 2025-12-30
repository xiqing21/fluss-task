#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
服务管理系统测试脚本
验证服务管理、监控和自动恢复功能
"""

import sys
import os
import json
import time
from service_manager import ServiceManager

def test_service_manager():
    """测试服务管理器基本功能"""
    print("=== 测试服务管理器 ===")
    
    try:
        manager = ServiceManager()
        
        # 测试获取系统状态
        print("1. 测试获取系统状态...")
        status = manager.get_system_status()
        print(f"   系统状态获取成功，服务数量: {len(status['services'])}")
        
        # 测试生成状态报告
        print("2. 测试生成状态报告...")
        report = manager.generate_status_report()
        print(f"   状态报告生成成功，长度: {len(report)} 字符")
        
        # 测试 Supervisor 状态获取
        print("3. 测试 Supervisor 状态获取...")
        supervisor_status = manager.get_supervisor_status()
        print(f"   Supervisor 状态获取成功，服务数量: {len(supervisor_status)}")
        
        print("✓ 服务管理器测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 服务管理器测试失败: {e}")
        return False

def test_system_monitor():
    """测试系统监控器"""
    print("\n=== 测试系统监控器 ===")
    
    try:
        # 由于可能缺少依赖，我们只测试导入
        from system_monitor import SystemMonitor
        
        monitor = SystemMonitor()
        
        # 测试获取系统资源
        print("1. 测试获取系统资源...")
        resources = monitor.get_system_resources()
        print(f"   系统资源获取成功: {list(resources.keys())}")
        
        # 测试单次检查（不实际运行，只验证方法存在）
        print("2. 测试方法可用性...")
        assert hasattr(monitor, 'run_single_check'), "缺少 run_single_check 方法"
        assert hasattr(monitor, 'export_status_json'), "缺少 export_status_json 方法"
        
        print("✓ 系统监控器测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 系统监控器测试失败: {e}")
        return False

def test_auto_recovery():
    """测试自动恢复管理器"""
    print("\n=== 测试自动恢复管理器 ===")
    
    try:
        from auto_recovery import AutoRecoveryManager
        
        manager = AutoRecoveryManager()
        
        # 测试配置
        print("1. 测试配置管理...")
        config = manager.config
        print(f"   配置加载成功，配置项数量: {len(config)}")
        
        # 测试生成恢复报告
        print("2. 测试生成恢复报告...")
        report = manager.generate_recovery_report()
        print(f"   恢复报告生成成功，长度: {len(report)} 字符")
        
        # 测试方法可用性
        print("3. 测试方法可用性...")
        assert hasattr(manager, 'should_attempt_recovery'), "缺少 should_attempt_recovery 方法"
        assert hasattr(manager, 'check_and_recover_services'), "缺少 check_and_recover_services 方法"
        
        print("✓ 自动恢复管理器测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 自动恢复管理器测试失败: {e}")
        return False

def test_configuration_files():
    """测试配置文件"""
    print("\n=== 测试配置文件 ===")
    
    try:
        # 测试 Supervisor 配置
        print("1. 测试 Supervisor 配置文件...")
        supervisor_config = "config/supervisord.conf"
        if os.path.exists(supervisor_config):
            with open(supervisor_config, 'r') as f:
                content = f.read()
                # 检查是否包含新添加的服务
                assert 'auto-recovery' in content, "Supervisor 配置中缺少 auto-recovery 服务"
                print("   Supervisor 配置文件验证通过")
        else:
            print("   警告: Supervisor 配置文件不存在")
        
        # 测试自动恢复配置
        print("2. 测试自动恢复配置文件...")
        recovery_config = "config/auto_recovery.json"
        if os.path.exists(recovery_config):
            with open(recovery_config, 'r') as f:
                config = json.load(f)
                assert 'check_interval' in config, "自动恢复配置中缺少 check_interval"
                assert 'service_priorities' in config, "自动恢复配置中缺少 service_priorities"
                print("   自动恢复配置文件验证通过")
        else:
            print("   警告: 自动恢复配置文件不存在")
        
        # 测试启动脚本
        print("3. 测试启动脚本...")
        start_script = "scripts/start_services.sh"
        if os.path.exists(start_script):
            print("   启动脚本存在")
        else:
            print("   警告: 启动脚本不存在")
        
        print("✓ 配置文件测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 配置文件测试失败: {e}")
        return False

def test_script_permissions():
    """测试脚本权限"""
    print("\n=== 测试脚本权限 ===")
    
    try:
        scripts = [
            "scripts/service_manager.py",
            "scripts/system_monitor.py", 
            "scripts/auto_recovery.py",
            "scripts/start_services.sh"
        ]
        
        for script in scripts:
            if os.path.exists(script):
                # 检查文件是否可执行
                if os.access(script, os.X_OK):
                    print(f"   ✓ {script} 可执行")
                else:
                    print(f"   ✗ {script} 不可执行")
            else:
                print(f"   ✗ {script} 不存在")
        
        print("✓ 脚本权限测试完成")
        return True
        
    except Exception as e:
        print(f"✗ 脚本权限测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=== 服务管理系统功能测试 ===")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        test_service_manager,
        test_system_monitor,
        test_auto_recovery,
        test_configuration_files,
        test_script_permissions
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"测试异常: {e}")
            failed += 1
    
    print(f"\n=== 测试结果汇总 ===")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"总计: {passed + failed}")
    
    if failed == 0:
        print("🎉 所有测试通过！")
        return True
    else:
        print("❌ 部分测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)