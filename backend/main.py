"""
WebDAV Media Rename Agent - FastAPI主入口

使用AG-UI LangGraph集成

启动方式：
    cd webdav-tools
    source .venv/bin/activate
    python -m uvicorn backend.main:app --reload --port 8002
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

# 确保可以找到backend包
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get_config
from backend.database import init_database, close_database, get_db_session

# AG-UI LangGraph 集成 - 使用 CopilotKit 的 LangGraphAGUIAgent 支持状态同步
from ag_ui_langgraph import add_langgraph_fastapi_endpoint
from copilotkit import LangGraphAGUIAgent

# 导入我们的Agent
from backend.agents.media_agent import graph


# 配置日志
config = get_config()
logging.basicConfig(
    level=getattr(logging, config.logging.level),
    format=config.logging.format,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 启动 WebDAV Media Rename Agent...")
    await init_database()
    logger.info("✅ 服务启动完成")
    
    yield
    
    # 关闭时
    logger.info("🛑 关闭服务...")
    await close_database()
    logger.info("✅ 服务已关闭")


# 创建FastAPI应用
app = FastAPI(
    title="WebDAV Media Rename Agent",
    description="基于AI的影视资源管理Agent，支持WebDAV扫描和Infuse规范重命名",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ AG-UI LangGraph 集成 ============

# 创建 Agent 实例（复用）
media_agent = LangGraphAGUIAgent(
    name="media_agent",
    description="WebDAV影视资源管理助手，帮助扫描、查询和重命名影视文件",
    graph=graph,
    # 增加递归限制，避免长时间扫描导致超时
    config={"recursion_limit": 50},
)

# 使用AG-UI协议添加LangGraph端点
# 统一使用 /api/copilotkit 路径（前端和后端保持一致）
add_langgraph_fastapi_endpoint(
    app=app,
    agent=media_agent,
    path="/api/copilotkit"
)

logger.info("✅ AG-UI LangGraph端点已配置: /api/copilotkit")


# ============ 健康检查 ============

@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "webdav-media-agent",
        "version": "0.1.0",
    }


# ============ API路由 ============

@app.get("/api/connections")
async def list_connections(session: AsyncSession = Depends(get_db_session)):
    """获取所有WebDAV连接"""
    from sqlalchemy import select
    from backend.models.db_models import WebDAVConnection
    
    result = await session.execute(
        select(WebDAVConnection).where(WebDAVConnection.is_active == True)
    )
    connections = result.scalars().all()
    
    return {
        "connections": [
            {
                "id": c.id,
                "name": c.name,
                "url": c.url,
                "type": c.type,
                "base_path": c.base_path,
                "created_at": c.created_at.isoformat(),
            }
            for c in connections
        ]
    }


@app.get("/api/history")
async def get_history(
    limit: int = 20,
    session: AsyncSession = Depends(get_db_session)
):
    """获取重命名历史"""
    from sqlalchemy import select
    from backend.models.db_models import RenameHistory
    
    result = await session.execute(
        select(RenameHistory)
        .order_by(RenameHistory.renamed_at.desc())
        .limit(limit)
    )
    history = result.scalars().all()
    
    return {
        "history": [
            {
                "id": h.id,
                "original_path": h.original_path,
                "new_path": h.new_path,
                "media_type": h.media_type,
                "title": h.title,
                "status": h.status,
                "renamed_at": h.renamed_at.isoformat(),
            }
            for h in history
        ]
    }


# ============ 开发服务器启动 ============

if __name__ == "__main__":
    import uvicorn
    import os
    
    # 切换到项目根目录
    os.chdir(Path(__file__).parent.parent)
    
    uvicorn.run(
        "backend.main:app",
        host=config.server.backend_host,
        port=config.server.backend_port,
        reload=True,
    )
