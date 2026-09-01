#!/bin/bash

# 股票分析平台状态检查脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_DIR/stock_app.pid"
LOG_FILE="$PROJECT_DIR/stock_app.log"

cd "$PROJECT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  股票分析平台 - 服务状态${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 获取配置端口
PORT=$(python3 -c "from stock_app.config import CONFIG; print(CONFIG.port)" 2>/dev/null || echo "5858")

# 检查服务状态
RUNNING=false
PID=""

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        RUNNING=true
    fi
fi

# 也检查端口
PORT_PID=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [ -n "$PORT_PID" ]; then
    RUNNING=true
    PID="$PORT_PID"
fi

if [ "$RUNNING" = true ]; then
    echo -e "${GREEN}● 服务状态: 运行中${NC}"
    echo -e "  PID: $PID"
    echo -e "  端口: $PORT"
    echo ""
    
    # 健康检查
    if curl -s -f "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 健康检查: 通过${NC}"
        HEALTH=$(curl -s "http://127.0.0.1:$PORT/api/health" | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['time'])" 2>/dev/null || echo "unknown")
        echo -e "  服务器时间: $HEALTH"
    else
        echo -e "${RED}✗ 健康检查: 失败${NC}"
    fi
    echo ""
    
    # 显示访问地址
    echo -e "${BLUE}访问地址:${NC} http://127.0.0.1:$PORT"
    echo -e "${BLUE}日志文件:${NC} $LOG_FILE"
else
    echo -e "${RED}● 服务状态: 未运行${NC}"
    echo ""
    echo -e "${YELLOW}启动服务: ./start.sh${NC}"
fi

echo ""

# 显示最近的日志
if [ -f "$LOG_FILE" ]; then
    echo -e "${BLUE}最近日志 (最后 5 行):${NC}"
    echo "----------------------------------------"
    tail -n 5 "$LOG_FILE" 2>/dev/null || echo "无日志"
    echo "----------------------------------------"
fi
