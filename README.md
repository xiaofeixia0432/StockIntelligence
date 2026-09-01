# 股票分析平台

这是一个面向 `stock_stats.py` 数据库分析的 Python Web 应用，支持：

- 股票数据库概览和趋势分析
- 个股查询与详情展示
- K 线趋势图与回测曲线
- 个股新闻查看与发布
- 自选股管理
- 持仓管理与盈亏分析
- 用户注册登录
- 每个股票单独配置策略
- 策略对比、AI 交易建议与提醒中心
- PC 与移动端响应式布局

## 目录结构

- `stock_stats.py`: 股票数据库统计与分析核心脚本
- `stock_web.py`: 兼容入口
- `stock_app/`: 分模块 Flask 应用（配置、数据库、行情、策略、路由）
- `run.py`: 本地开发启动入口
- `templates/index.html`: 前端页面模板
- `static/css/styles.css`: 前端样式
- `static/js/app.js`: 前端交互逻辑
- `scripts/run.sh`: 本地开发脚本
- `scripts/deploy.sh`: 生产部署脚本
- `gunicorn.conf.py`: Gunicorn 配置
- `Dockerfile`: Docker 镜像构建
- `docker-compose.yml`: Docker Compose 部署配置
- `.env.example`: 环境变量模板
- `stock_app.db`: 用户、新闻、策略、持仓数据存储库
- `stock.db`: 股票行情数据库

## 环境要求

- Python 3.10+
- pip
- Linux/macOS/Windows (WSL 也可)
- Docker（可选，用于容器部署）

## 快速运行

### 方式 1：本地 Python 运行

```bash
cd /Users/apple/Desktop/project/python/fund_sqlite
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 run.py
```

访问：

- http://127.0.0.1:5000

### 方式 2：脚本运行

```bash
cd /Users/apple/Desktop/project/python/fund_sqlite
bash scripts/run.sh
```

### 方式 3：Docker 运行

```bash
cd /Users/apple/Desktop/project/python/fund_sqlite
cp .env.example .env
docker compose up --build
```

访问：

- http://127.0.0.1:5000

## 生产部署

建议使用 Gunicorn 作为生产 WSGI 服务。

```bash
cd /Users/apple/Desktop/project/python/fund_sqlite
bash scripts/deploy.sh
```

启动后可访问：

- http://0.0.0.0:5000

日志输出：

```bash
cd /Users/apple/Desktop/project/python/fund_sqlite
tail -f stock_app.log
```

### Nginx 反向代理（可选）

如需在真实生产环境中放置前端反向代理，可以使用示例配置：

```bash
cd /Users/apple/Desktop/project/python/fund_sqlite
cp nginx.conf.example /etc/nginx/conf.d/stock-app.conf
# 根据实际域名与静态目录进行修改，然后执行：
# nginx -t
# nginx -s reload
```

该配置会将请求转发到本地 Flask 服务，适合配合 HTTPS / 域名访问使用。

### 健康检查脚本

```bash
cd /Users/apple/Desktop/project/python/fund_sqlite
bash scripts/healthcheck.sh
# 或指定 URL
bash scripts/healthcheck.sh http://127.0.0.1:5000
```

## 环境变量

可在 `.env` 或系统环境变量中配置：

```bash
STOCK_SECRET_KEY=your-super-secret-key
PORT=5000
PYTHONUNBUFFERED=1
```

## 常用接口

### 健康检查

```bash
curl http://127.0.0.1:5000/api/health
```

### 注册

```bash
curl -X POST http://127.0.0.1:5000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"demo123"}'
```

### 登录

```bash
curl -X POST http://127.0.0.1:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"demo123"}'
```

### 查询股票

```bash
curl 'http://127.0.0.1:5000/api/stock/search?keyword=bj920000'
```

### 查询股票新闻

```bash
curl 'http://127.0.0.1:5000/api/news?symbol=bj920000'
```

### 保存策略

```bash
curl -X POST http://127.0.0.1:5000/api/strategies \
  -H 'Content-Type: application/json' \
  -d '{
    "symbol":"BJ920000",
    "name":"均线突破",
    "description":"适合趋势跟踪",
    "rule":"5日均线在10日均线上方",
    "entry_condition":"收盘价站上5日均线且量能放大",
    "exit_condition":"跌破10日均线",
    "status":"active"
  }'
```

### 持仓管理

```bash
curl -X POST http://127.0.0.1:5000/api/portfolio \
  -H 'Content-Type: application/json' \
  -d '{
    "symbol": "BJ920000",
    "shares": 10,
    "avg_cost": 9.5,
    "notes": "长期持有"
  }'
```

## 维护建议

- 数据库文件 `stock.db` 存放行情数据
- 用户数据、新闻、策略、持仓均在 `stock_app.db`
- 若需切换生产环境，可在系统中配置 `STOCK_SECRET_KEY`
- 若部署到服务器，建议使用反向代理（如 Nginx）并加上 HTTPS
- 生产环境建议开启日志归档、备份、健康检查和自动重启机制

## 退出说明

如果使用脚本启动了后台服务，可执行：

```bash
ps -ef | grep gunicorn
kill <PID>
```

也可以使用：

```bash
docker compose down
```
