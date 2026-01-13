"""
前端输出模型

用于工具返回值验证和 pydantic2ts 生成前端 TypeScript 类型

包含：
- StorageConfigOutput: 存储连接配置
- ScanResultOutput: 扫描结果摘要
- ClassificationResultItem: 分类结果项
- ToolProgressOutput: 工具执行进度
- CurrentToolOutput: 当前工具状态
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


class StorageConfigOutput(BaseModel):
    """存储连接配置（前端显示）"""
    url: str = Field(default="", description="存储 URL")
    username: str = Field(default="", description="用户名")
    type: str = Field(default="", description="存储类型: alist | webdav")
    scan_path: str = Field(default="", description="扫描路径")
    target_path: str = Field(default="", description="目标路径")
    connected: bool = Field(default=False, description="是否已连接")


class ScanResultOutput(BaseModel):
    """扫描结果摘要（前端显示）"""
    total_files: int = Field(default=0, description="总文件数")
    video_count: int = Field(default=0, description="视频文件数")
    subtitle_count: int = Field(default=0, description="字幕文件数")
    sample_files: List[str] = Field(default_factory=list, description="示例文件名（前10个）")


class SeasonInfo(BaseModel):
    """单季信息"""
    season: int = Field(description="季号")
    episode_count: int = Field(description="该季集数")
    ep_range: str = Field(description="该季集数范围，如 E01-E24")


class ClassificationResultItem(BaseModel):
    """单个分类结果项（前端显示）"""
    name: str = Field(description="媒体名称")
    file_count: int = Field(description="文件数量")
    ep_range: str = Field(default="-", description="剧集范围（兼容旧版），如 E01-E25")
    type: Literal["tv", "movie"] = Field(description="媒体类型")
    seasons: Optional[List[SeasonInfo]] = Field(default=None, description="按季详情（新版），电影为 None")


class ToolProgressOutput(BaseModel):
    """工具执行进度（前端显示）"""
    current: int = Field(default=0, description="当前进度")
    total: int = Field(default=0, description="总数")
    message: str = Field(default="", description="进度消息")
    percentage: float = Field(default=0.0, description="百分比 0-100")


class CurrentToolOutput(BaseModel):
    """当前工具状态（前端显示）"""
    name: str = Field(default="", description="工具名称")
    status: Literal["idle", "executing", "complete", "error"] = Field(
        default="idle", description="执行状态"
    )
    description: str = Field(default="", description="工具描述")
    progress: Optional[ToolProgressOutput] = Field(default=None, description="执行进度")

