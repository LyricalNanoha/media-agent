"""
数据库模块

SQLite数据库连接和会话管理
"""

import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_config


class Base(DeclarativeBase):
    """SQLAlchemy声明式基类"""
    pass


# 全局引擎和会话工厂
_engine = None
_async_session_factory = None


def get_database_url() -> str:
    """获取数据库URL"""
    config = get_config()
    db_path = config.database.path
    
    # 确保数据目录存在
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # SQLite异步URL
    return f"sqlite+aiosqlite:///{db_path}"


def get_engine():
    """获取数据库引擎（单例）"""
    global _engine
    if _engine is None:
        database_url = get_database_url()
        _engine = create_async_engine(
            database_url,
            echo=False,  # 设为True可以看到SQL语句
            future=True,
        )
    return _engine


def get_session_factory():
    """获取会话工厂（单例）"""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（用于FastAPI依赖注入）
    
    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_db_session)):
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_database():
    """
    初始化数据库（创建所有表）
    
    在应用启动时调用
    """
    # 导入所有模型以确保它们被注册
    from backend.models import db_models  # noqa: F401
    
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ 数据库初始化完成")


async def close_database():
    """
    关闭数据库连接
    
    在应用关闭时调用
    """
    global _engine, _async_session_factory
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
    
    print("✅ 数据库连接已关闭")

