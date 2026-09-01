#!/bin/bash

# 股票分析平台停止脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_DIR/stock_app.pid"

cd "$PROJECT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  股票分析平台 - 停止服务${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 PID 文件
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}未找到 PID 文件，尝试查找运行中的服务...${NC}"
    
    # 尝试通过端口查找
    PORT=$(python3 -c "from stock_app.config import CONFIG; print(CONFIG.port)" 2>/dev/null || echo "5858")
    PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
    
    if [ -z "$PIDS" ]; then
        echo -e "${YELLOW}未发现运行中的服务${NC}"
        exit 0
    fi
    
    echo -e "${YELLOW}发现端口 $PORT 上的进程: $PIDS${NC}"
    read -p "是否停止这些进程？(y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}操作已取消${NC}"
        exit 0
    fi
    
    for PID in $PIDS; do
        echo "停止进程 $PID..."
        kill "$PID" 2>/dev/null || true
    done
else
    PID=$(cat "$PID_FILE")
    
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}服务未运行 (PID: $PID 已失效)${NC}"
        rm -f "$PID_FILE"
        exit 0
    fi
    
    echo -e "${YELLOW}正在停止服务 (PID: $PID)...${NC}"
    kill "$PID"
    
    # 等待进程结束
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    
    # 如果还在运行，强制结束
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}强制停止服务...${NC}"
        kill -9 "$PID" 2>/dev/null || true
    fi
    
    rm -f "$PID_FILE"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ 服务已停止${NC}"
echo -e "${GREEN}========================================${NC}"
