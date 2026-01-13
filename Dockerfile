# 🎀 媒体整理助手 - Docker 镜像（优化版）
# 单容器方案：Nginx + Next.js (standalone) + FastAPI
# 优化后预计镜像大小：~500MB（原 ~4GB）

# ==================== 阶段 1: 构建前端 ====================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# 复制 package.json 先安装依赖（利用缓存）
COPY frontend/package*.json ./
RUN npm ci --only=production=false

# 复制前端源码并构建
COPY frontend/ ./

# 🔥 使用 standalone 模式构建，大幅减少输出大小
RUN npm run build

# ==================== 阶段 2: 构建后端依赖 ====================
FROM python:3.11-slim AS backend-builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制并安装 Python 依赖到虚拟环境
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ==================== 阶段 3: 最终镜像（精简版）====================
FROM python:3.11-slim

WORKDIR /app

# 🔥 只安装必要的运行时依赖（移除 npm，使用 standalone 不需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从构建阶段复制 Python 虚拟环境
COPY --from=backend-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制后端代码
COPY backend/ /app/backend/

# 🔥 从构建阶段复制 Next.js standalone 产物（超级精简！）
# standalone 模式只包含必要的运行时文件，不需要 node_modules
COPY --from=frontend-builder /app/frontend/.next/standalone /app/frontend/
COPY --from=frontend-builder /app/frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-builder /app/frontend/public /app/frontend/public

# 复制配置文件
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 创建日志目录
RUN mkdir -p /var/log/supervisor

# 环境变量（运行时覆盖）
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
# Docker 环境中，Next.js API Route 连接本地后端
ENV AGENT_URL=http://127.0.0.1:8000/api/copilotkit
# Next.js standalone 需要的环境变量
ENV HOSTNAME="0.0.0.0"
ENV PORT=3000

# 暴露端口
EXPOSE 3000

# 启动 Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
