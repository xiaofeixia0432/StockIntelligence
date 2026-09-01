#!/bin/bash

# 股票分析平台一键启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$PROJECT_DIR/stock_app.log"
PID_FILE="$PROJECT_DIR/stock_app.pid"

# 切换到项目目录
cd "$PROJECT_DIR"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  股票分析平台 - 一键启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Python 版本
echo -e "${YELLOW}[1/5] 检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 Python3，请先安装 Python 3.10+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓ $PYTHON_VERSION${NC}"

# 检查依赖
echo -e "${YELLOW}[2/5] 检查并安装依赖...${NC}"
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt
echo -e "${GREEN}✓ 依赖安装完成${NC}"

# 检查是否已有服务在运行
echo -e "${YELLOW}[3/5] 检查服务状态...${NC}"
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}发现正在运行的服务 (PID: $OLD_PID)${NC}"
        read -p "是否停止旧服务并重新启动？(y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "停止旧服务..."
            kill "$OLD_PID" 2>/dev/null || true
            sleep 2
            rm -f "$PID_FILE"
        else
            echo -e "${YELLOW}操作已取消${NC}"
            exit 0
        fi
    else
        rm -f "$PID_FILE"
    fi
fi

# 检查端口占用
PORT=$(python3 -c "from stock_app.config import CONFIG; print(CONFIG.port)")
if lsof -i :"$PORT" > /dev/null 2>&1; then
    echo -e "${RED}错误: 端口 $PORT 已被占用${NC}"
    lsof -i :"$PORT"
    exit 1
fi
echo -e "${GREEN}✓ 端口 $PORT 可用${NC}"

# 启动服务
echo -e "${YELLOW}[4/5] 启动服务...${NC}"
nohup python3 -u run.py > "$LOG_FILE" 2>&1 &
SERVICE_PID=$!
echo "$SERVICE_PID" > "$PID_FILE"

echo -e "${GREEN}✓ 服务已启动 (PID: $SERVICE_PID)${NC}"

# 等待服务启动
echo -e "${YELLOW}[5/5] 等待服务就绪...${NC}"
MAX_WAIT=30
WAITED=0

while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s -f "http://127.0.0.1:$PORT/api/health" > /dev/null 2>&1; then
        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  ✓ 服务启动成功！${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo -e "${BLUE}访问地址:${NC} http://127.0.0.1:$PORT"
        echo -e "${BLUE}日志文件:${NC} $LOG_FILE"
        echo -e "${BLUE}进程PID:${NC} $SERVICE_PID"
        echo ""
        echo -e "${YELLOW}停止服务:${NC} ./stop.sh"
        echo -e "${YELLOW}查看日志:${NC} tail -f $LOG_FILE"
        echo ""
        exit 0
    fi
    sleep 1
    WAITED=$((WAITED + 1))
    printf "."
done

echo ""
echo -e "${RED}警告: 服务启动超时，请检查日志${NC}"
echo -e "${YELLOW}查看日志: tail -f $LOG_FILE${NC}"
exit 1
