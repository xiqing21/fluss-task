#!/bin/bash

# 代理配置脚本

echo "=== 配置系统代理 ==="

# 检查代理环境变量
if [ ! -z "$HTTP_PROXY" ]; then
    echo "HTTP 代理: $HTTP_PROXY"
    
    # 配置 APT 代理
    echo "Acquire::http::Proxy \"$HTTP_PROXY\";" > /etc/apt/apt.conf.d/01proxy
    
    # 配置 wget 代理
    echo "http_proxy = $HTTP_PROXY" >> /etc/wgetrc
    echo "use_proxy = on" >> /etc/wgetrc
fi

if [ ! -z "$HTTPS_PROXY" ]; then
    echo "HTTPS 代理: $HTTPS_PROXY"
    
    # 配置 APT HTTPS 代理
    echo "Acquire::https::Proxy \"$HTTPS_PROXY\";" >> /etc/apt/apt.conf.d/01proxy
    
    # 配置 wget HTTPS 代理
    echo "https_proxy = $HTTPS_PROXY" >> /etc/wgetrc
fi

# 配置 pip 代理
if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ]; then
    mkdir -p /root/.pip
    cat > /root/.pip/pip.conf << EOF
[global]
proxy = ${HTTP_PROXY:-$HTTPS_PROXY}
trusted-host = pypi.org
               pypi.python.org
               files.pythonhosted.org
EOF
    echo "pip 代理配置完成"
fi

# 配置 curl 代理
if [ ! -z "$HTTP_PROXY" ] || [ ! -z "$HTTPS_PROXY" ]; then
    cat > /root/.curlrc << EOF
proxy = ${HTTP_PROXY:-$HTTPS_PROXY}
EOF
    echo "curl 代理配置完成"
fi

echo "代理配置完成"