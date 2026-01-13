"""
分类相关模型

包含：
- 分类配置（Agent 输入）：MatchRule, ClassifyRule, ClassifyItem, ClassifyConfig
- 分类结果：SubtitleFile, ClassifiedFile, Classification
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional

from .enums import MediaType, SubCategory


# ============================================================
# 分类配置模型（Agent 输入）
# ============================================================

class MatchRule(BaseModel):
    """匹配规则"""
    directory: Optional[str] = Field(default=None, description="目录名包含")
    filename: Optional[str] = Field(default=None, description="文件名包含")
    episode_range: Optional[List[int]] = Field(default=None, description="集数范围 [start, end]")
    size_mb_greater: Optional[int] = Field(default=None, description="文件大于 X MB")


class ClassifyRule(BaseModel):
    """分类规则"""
    match: MatchRule = Field(description="匹配条件")
    season: Optional[int] = Field(default=None, description="固定季号")
    auto_season: bool = Field(default=False, description="自动分季（根据 TMDB）")
    episode_offset: int = Field(default=0, description="集数偏移（续作重编号）")


class ClassifyItem(BaseModel):
    """单个分类项"""
    tmdb_id: int = Field(description="TMDB ID")
    type: MediaType = Field(description="媒体类型")
    name: str = Field(description="系列名称")
    rules: List[ClassifyRule] = Field(description="分类规则列表")


class ClassifyConfig(BaseModel):
    """分类配置（Agent 生成）"""
    items: List[ClassifyItem] = Field(description="分类项列表")


# ============================================================
# 分类结果模型
# ============================================================

class SubtitleFile(BaseModel):
    """字幕文件"""
    path: str = Field(description="原始路径")
    name: str = Field(description="文件名")
    language: str = Field(description="字幕语言: chs, cht, eng, jpn")


class ClassifiedFile(BaseModel):
    """已分类的文件"""
    path: str = Field(description="原始路径")
    name: str = Field(description="文件名")
    episode: int = Field(description="集数（TMDB episode_number）")
    season: int = Field(description="季数")
    # 🆕 关联的字幕文件
    subtitles: List[SubtitleFile] = Field(default_factory=list, description="关联的字幕文件")


class Classification(BaseModel):
    """分类结果"""
    tmdb_id: int = Field(description="TMDB ID")
    name: str = Field(description="系列名称")
    type: MediaType = Field(description="媒体类型")
    year: Optional[int] = Field(default=None, description="年份")
    genres: List[str] = Field(default_factory=list, description="TMDB Genres")
    sub_category: SubCategory = Field(default=SubCategory.DEFAULT, description="子分类")
    # TV 系列用 seasons
    seasons: Dict[int, List[ClassifiedFile]] = Field(default_factory=dict, description="TV 季数据")
    # 电影用 files
    files: List[ClassifiedFile] = Field(default_factory=list, description="电影文件列表")

