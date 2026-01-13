"""
Pydantic模型定义

用于API请求/响应的数据验证
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl


# ============ WebDAV连接 ============

class WebDAVConnectionCreate(BaseModel):
    """创建WebDAV连接的请求模型"""
    name: Optional[str] = Field(None, description="连接名称，不填则自动生成")
    url: str = Field(..., description="WebDAV服务器地址")
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    base_path: str = Field("/", description="基础路径")
    type: str = Field("alist", description="服务类型: alist/nextcloud/generic")


class WebDAVConnectionResponse(BaseModel):
    """WebDAV连接响应模型"""
    id: int
    name: str
    type: str
    url: str
    username: Optional[str]
    base_path: str
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


class WebDAVConnectionTest(BaseModel):
    """测试WebDAV连接的响应"""
    success: bool
    message: str
    server_info: Optional[dict] = None


# ============ TMDB媒体信息 ============

class MediaInfo(BaseModel):
    """媒体信息模型"""
    tmdb_id: int
    media_type: str = Field(..., description="movie 或 tv")
    title: str = Field(..., description="标题")
    original_title: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    vote_average: Optional[float] = None
    genres: List[str] = Field(default_factory=list)
    
    # 电视剧特有
    seasons_count: Optional[int] = None
    episodes_count: Optional[int] = None


class TMDBSearchResult(BaseModel):
    """TMDB搜索结果"""
    results: List[MediaInfo]
    total_results: int
    query: str


# ============ 文件扫描 ============

class ParsedMediaFile(BaseModel):
    """解析后的媒体文件信息"""
    path: str = Field(..., description="文件完整路径")
    filename: str = Field(..., description="文件名")
    extension: str = Field(..., description="扩展名")
    size: Optional[int] = Field(None, description="文件大小(字节)")
    
    # 解析出的信息
    media_type: str = Field("unknown", description="媒体类型: movie/tv/unknown")
    parsed_title: Optional[str] = Field(None, description="解析出的标题")
    parsed_year: Optional[int] = Field(None, description="解析出的年份")
    parsed_season: Optional[int] = Field(None, description="解析出的季数")
    parsed_episode: Optional[int] = Field(None, description="解析出的集数")
    parsed_episode_title: Optional[str] = Field(None, description="解析出的集标题")
    quality: Optional[str] = Field(None, description="质量标识: 1080p/4K等")


class ScanResult(BaseModel):
    """扫描结果"""
    scan_id: str
    root_path: str
    total_files: int
    movies: List[ParsedMediaFile]
    tv_shows: List[ParsedMediaFile]
    unknown: List[ParsedMediaFile]
    scan_time: float = Field(..., description="扫描耗时(秒)")


# ============ 重命名 ============

class RenamePreviewItem(BaseModel):
    """重命名预览项"""
    original_path: str
    new_path: str
    media_type: str
    tmdb_id: Optional[int] = None
    title: Optional[str] = None
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    confidence: float = Field(1.0, description="匹配置信度 0-1")
    needs_confirmation: bool = Field(False, description="是否需要用户确认")
    warning: Optional[str] = Field(None, description="警告信息")


class RenamePreview(BaseModel):
    """重命名预览结果"""
    items: List[RenamePreviewItem]
    total_count: int
    auto_match_count: int
    need_confirmation_count: int
    language: str = Field("zh", description="命名语言")


class RenameExecuteRequest(BaseModel):
    """执行重命名的请求"""
    items: List[RenamePreviewItem]
    dry_run: bool = Field(False, description="是否只是模拟运行")


class RenameExecuteResult(BaseModel):
    """执行重命名的结果"""
    success_count: int
    failed_count: int
    skipped_count: int
    results: List[dict]


# ============ 历史记录 ============

class RenameHistoryResponse(BaseModel):
    """重命名历史响应"""
    id: int
    original_path: str
    new_path: str
    media_type: Optional[str]
    title: Optional[str]
    year: Optional[int]
    season: Optional[int]
    episode: Optional[int]
    renamed_at: datetime
    status: str
    
    class Config:
        from_attributes = True


class RenameHistoryList(BaseModel):
    """重命名历史列表"""
    items: List[RenameHistoryResponse]
    total: int
    page: int
    page_size: int


# ============ Agent状态 ============

class AgentState(BaseModel):
    """Agent状态模型"""
    current_connection_id: Optional[int] = None
    current_scan_result: Optional[ScanResult] = None
    current_preview: Optional[RenamePreview] = None
    language_preference: str = "zh"





