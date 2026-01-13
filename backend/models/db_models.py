"""
数据库模型定义

使用SQLAlchemy 2.0声明式映射
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Boolean, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class WebDAVConnection(Base):
    """WebDAV连接配置表"""
    
    __tablename__ = "webdav_connections"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="连接名称")
    type: Mapped[str] = mapped_column(String(50), default="alist", comment="服务类型: alist/nextcloud/generic")
    url: Mapped[str] = mapped_column(String(500), nullable=False, comment="服务器地址")
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="用户名")
    password: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="密码(加密存储)")
    base_path: Mapped[str] = mapped_column(String(500), default="/", comment="基础路径")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")
    
    # 关系
    rename_histories: Mapped[list["RenameHistory"]] = relationship(back_populates="connection", cascade="all, delete-orphan")
    scan_sessions: Mapped[list["ScanSession"]] = relationship(back_populates="connection", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<WebDAVConnection(id={self.id}, name='{self.name}', url='{self.url}')>"


class RenameHistory(Base):
    """重命名历史记录表"""
    
    __tablename__ = "rename_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(Integer, ForeignKey("webdav_connections.id"), nullable=False)
    original_path: Mapped[str] = mapped_column(String(1000), nullable=False, comment="原始路径")
    new_path: Mapped[str] = mapped_column(String(1000), nullable=False, comment="新路径")
    media_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="媒体类型: movie/tv")
    tmdb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="TMDB ID")
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="标题")
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="年份")
    season: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="季数")
    episode: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="集数")
    renamed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="重命名时间")
    status: Mapped[str] = mapped_column(String(20), default="success", comment="状态: success/failed/rollback")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="错误信息")
    
    # 关系
    connection: Mapped["WebDAVConnection"] = relationship(back_populates="rename_histories")
    
    def __repr__(self) -> str:
        return f"<RenameHistory(id={self.id}, original='{self.original_path}', new='{self.new_path}')>"


class MediaCache(Base):
    """TMDB媒体信息缓存表"""
    
    __tablename__ = "media_cache"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tmdb_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, comment="TMDB ID")
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="媒体类型: movie/tv")
    title_en: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="英文标题")
    title_zh: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="中文标题")
    original_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="原始标题")
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="年份")
    poster_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="海报路径")
    backdrop_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="背景图路径")
    overview: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="简介")
    genres: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="类型(JSON数组)")
    vote_average: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="评分")
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="缓存时间")
    
    def __repr__(self) -> str:
        return f"<MediaCache(tmdb_id={self.tmdb_id}, title='{self.title_zh or self.title_en}')>"


class ScanSession(Base):
    """扫描会话表"""
    
    __tablename__ = "scan_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(Integer, ForeignKey("webdav_connections.id"), nullable=False)
    root_path: Mapped[str] = mapped_column(String(500), nullable=False, comment="扫描根路径")
    total_files: Mapped[int] = mapped_column(Integer, default=0, comment="总文件数")
    processed_files: Mapped[int] = mapped_column(Integer, default=0, comment="已处理文件数")
    movies_count: Mapped[int] = mapped_column(Integer, default=0, comment="电影数量")
    tv_count: Mapped[int] = mapped_column(Integer, default=0, comment="电视剧数量")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="开始时间")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="完成时间")
    status: Mapped[str] = mapped_column(String(20), default="running", comment="状态: running/completed/failed/cancelled")
    
    # 关系
    connection: Mapped["WebDAVConnection"] = relationship(back_populates="scan_sessions")
    
    def __repr__(self) -> str:
        return f"<ScanSession(id={self.id}, root_path='{self.root_path}', status='{self.status}')>"

