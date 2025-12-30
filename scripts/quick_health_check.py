#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
快速健康检查脚本 - 用于 Docker healthcheck
"""

import socket
import sys

def check_port(host, port, timeout=2):
    """检查端口连通性"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def main():
    """主函数"""
    # 检查关键服务端口
    critical_ports = [22, 5432, 8081]  # SSH, PostgreSQL, Flink
    
    for port in critical_ports:
        if not check_port('localhost', port):
            print(f"Port {port} is not accessible")
            sys.exit(1)
    
    print("Health check passed")
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        main()
    else:
        # 如果不是快速检查，运行完整的健康检查
        import health_check
        health_check.main()