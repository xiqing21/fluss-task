#!/bin/bash

# 国网实时数仓测试环境 - 服务启动脚本
# 提供统一的服务启动和监控机制

set -e

echo "=== 国网实时数仓服务启动脚本 ==="
echo "启动时间: $(date)"

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/opt/logs"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 日志函数
log_info() {
    echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_DIR/service_startup.log"
}

log_error() {
    echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_DIR/service_startup.log" >&2
}

log_warn() {
    echo "[WARN] $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_DIR/service_startup.log"
}

# 检查 Python 依赖
check_python_dependencies() {
    log_info "检查 Python 依赖..."
    
    local required_packages=("psycopg2" "requests" "psutil" "schedule")
    local missing_packages=()
    
    for package in "${required_packages[@]}"; do
        if ! python3 -c "import $package" 2>/dev/null; then
            missing_packages+=("$package")
        fi
    done
    
    if [ ${#missing_packages[@]} -gt 0 ]; then
        log_warn "缺少 Python 包: ${missing_packages[*]}"
        log_info "尝试安装缺少的包..."
        
        for package in "${missing_packages[@]}"; do
            if [ "$package" = "psycopg2" ]; then
                pip3 install psycopg2-binary || log_error "安装 psycopg2-binary 失败"
            else
                pip3 install "$package" || log_error "安装 $package 失败"
            fi
        done
    else
        log_info "所有 Python 依赖已满足"
    fi
}

# 设置文件权限
setup_permissions() {
    log_info "设置文件权限..."
    
    # 设置脚本执行权限
    chmod +x "$SCRIPT_DIR"/*.py
    chmod +x "$SCRIPT_DIR"/*.sh
    
    # 设置日志目录权限
    chmod 755 "$LOG_DIR"
    
    # 设置 SSH 相关权限
    if [ -f "/root/.ssh/authorized_keys" ]; then
        chmod 600 /root/.ssh/authorized_keys
        chmod 700 /root/.ssh
    fi
    
    log_info "文件权限设置完成"
}

# 验证 Supervisor 配置
validate_supervisor_config() {
    log_info "验证 Supervisor 配置..."
    
    if supervisord -t -c /etc/supervisor/conf.d/supervisord.conf; then
        log_info "Supervisor 配置验证通过"
        return 0
    else
        log_error "Supervisor 配置验证失败"
        return 1
    fi
}

# 启动服务管理器
start_service_manager() {
    log_info "启动服务管理器..."
    
    # 检查服务管理器是否可用
    if python3 "$SCRIPT_DIR/service_manager.py" status > /dev/null 2>&1; then
        log_info "服务管理器可用"
    else
        log_error "服务管理器不可用"
        return 1
    fi
    
    # 启动所有服务
    log_info "启动所有服务..."
    if python3 "$SCRIPT_DIR/service_manager.py" start-all; then
        log_info "所有服务启动成功"
    else
        log_warn "部分服务启动失败，将尝试自动恢复"
    fi
    
    return 0
}

# 等待服务就绪
wait_for_services() {
    log_info "等待服务就绪..."
    
    local max_wait=300  # 最大等待时间（秒）
    local wait_interval=10
    local elapsed=0
    
    while [ $elapsed -lt $max_wait ]; do
        log_info "检查服务状态... (${elapsed}/${max_wait}s)"
        
        # 使用服务管理器检查状态
        if python3 "$SCRIPT_DIR/service_manager.py" status | grep -q '"health_percentage": 100'; then
            log_info "所有服务已就绪"
            return 0
        fi
        
        sleep $wait_interval
        elapsed=$((elapsed + wait_interval))
    done
    
    log_warn "服务启动超时，但将继续运行"
    return 1
}

# 启动监控和恢复服务
start_monitoring() {
    log_info "启动监控和恢复服务..."
    
    # 这些服务将由 Supervisor 自动启动
    # 这里只是验证它们是否正常运行
    
    sleep 5  # 等待 Supervisor 启动这些服务
    
    # 检查健康检查服务
    if supervisorctl status health-check | grep -q "RUNNING"; then
        log_info "健康检查服务已启动"
    else
        log_warn "健康检查服务未启动"
    fi
    
    # 检查自动恢复服务
    if supervisorctl status auto-recovery | grep -q "RUNNING"; then
        log_info "自动恢复服务已启动"
    else
        log_warn "自动恢复服务未启动"
    fi
}

# 生成启动报告
generate_startup_report() {
    log_info "生成启动报告..."
    
    local report_file="$LOG_DIR/startup_report_$(date +%Y%m%d_%H%M%S).json"
    
    # 使用系统监控器生成报告
    if python3 "$SCRIPT_DIR/system_monitor.py" export "$report_file"; then
        log_info "启动报告已生成: $report_file"
    else
        log_warn "启动报告生成失败"
    fi
    
    # 显示简要状态
    log_info "=== 启动完成状态 ==="
    python3 "$SCRIPT_DIR/service_manager.py" report || log_warn "无法生成状态报告"
}

# 主函数
main() {
    log_info "开始启动国网实时数仓服务..."
    
    # 检查依赖
    check_python_dependencies
    
    # 设置权限
    setup_permissions
    
    # 验证配置
    if ! validate_supervisor_config; then
        log_error "配置验证失败，退出启动"
        exit 1
    fi
    
    # 启动服务
    if ! start_service_manager; then
        log_error "服务启动失败"
        exit 1
    fi
    
    # 等待服务就绪
    wait_for_services
    
    # 启动监控
    start_monitoring
    
    # 生成报告
    generate_startup_report
    
    log_info "=== 服务启动完成 ==="
    log_info "可以使用以下命令管理服务:"
    log_info "  python3 $SCRIPT_DIR/service_manager.py status     # 查看状态"
    log_info "  python3 $SCRIPT_DIR/system_monitor.py monitor     # 启动监控"
    log_info "  python3 $SCRIPT_DIR/auto_recovery.py recover      # 手动恢复"
    log_info "  supervisorctl status                               # Supervisor 状态"
}

# 处理命令行参数
case "${1:-start}" in
    "start")
        main
        ;;
    "check-deps")
        check_python_dependencies
        ;;
    "validate-config")
        validate_supervisor_config
        ;;
    "report")
        generate_startup_report
        ;;
    *)
        echo "Usage: $0 [start|check-deps|validate-config|report]"
        echo "  start           - 启动所有服务（默认）"
        echo "  check-deps      - 检查 Python 依赖"
        echo "  validate-config - 验证 Supervisor 配置"
        echo "  report          - 生成状态报告"
        exit 1
        ;;
esac