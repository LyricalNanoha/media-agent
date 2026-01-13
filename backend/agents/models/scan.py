"""
扫描相关模型

包含：
- ScannedFile: 扫描到的文件
"""

from pydantic import BaseModel, Field
from typing import Optional


class ScannedFile(BaseModel):
    """扫描到的文件"""
    name: str = Field(description="文件名")
    path: str = Field(description="完整路径")
    type: str = Field(description="文件类型: video | subtitle")
    size: int = Field(description="文件大小（字节）")
    directory: str = Field(description="所在目录")
    episode: Optional[int] = Field(default=None, description="提取的集数")
    
    # 🆕 字幕专用字段
    language: Optional[str] = Field(default=None, description="字幕语言: chs, cht, eng, jpn")
    video_ref: Optional[str] = Field(default=None, description="关联的视频文件路径")

