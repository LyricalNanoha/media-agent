"""
枚举类型和映射表

包含：
- MediaType: 媒体类型（TV/电影）
- SubCategory: 子分类（动漫/纪录片/音乐/综艺/默认）
- 子分类映射表（中英文）
- TMDB Genre 到 SubCategory 的映射
- 辅助函数
"""

from typing import Dict, List
from enum import Enum


# ============================================================
# 枚举类型
# ============================================================

class MediaType(str, Enum):
    """媒体类型"""
    TV = "tv"
    MOVIE = "movie"


class SubCategory(str, Enum):
    """子分类（基于 TMDB Genres）"""
    ANIMATION = "animation"      # 动漫
    DOCUMENTARY = "documentary"  # 纪录片
    MUSIC = "music"              # 音乐
    VARIETY = "variety"          # 综艺
    DEFAULT = "default"          # 默认


# ============================================================
# 映射表
# ============================================================

# TV 子分类中文名
SUBCATEGORY_TV_ZH: Dict[SubCategory, str] = {
    SubCategory.ANIMATION: "动漫",
    SubCategory.DOCUMENTARY: "纪录片",
    SubCategory.MUSIC: "音乐",
    SubCategory.VARIETY: "综艺",
    SubCategory.DEFAULT: "电视剧",
}

# Movie 子分类中文名
SUBCATEGORY_MOVIE_ZH: Dict[SubCategory, str] = {
    SubCategory.ANIMATION: "动漫",
    SubCategory.DOCUMENTARY: "纪录片",
    SubCategory.MUSIC: "音乐",
    SubCategory.VARIETY: "综艺",
    SubCategory.DEFAULT: "电影",
}

# TV 子分类英文名
SUBCATEGORY_TV_EN: Dict[SubCategory, str] = {
    SubCategory.ANIMATION: "Animation",
    SubCategory.DOCUMENTARY: "Documentary",
    SubCategory.MUSIC: "Music",
    SubCategory.VARIETY: "Variety",
    SubCategory.DEFAULT: "TV Shows",
}

# Movie 子分类英文名
SUBCATEGORY_MOVIE_EN: Dict[SubCategory, str] = {
    SubCategory.ANIMATION: "Animation",
    SubCategory.DOCUMENTARY: "Documentary",
    SubCategory.MUSIC: "Music",
    SubCategory.VARIETY: "Variety",
    SubCategory.DEFAULT: "Movies",
}

# TMDB Genre 到 SubCategory 的映射
# 按 TMDB 返回的顺序，第一个匹配的生效
# 🔥 支持中英文 genre 名称
GENRE_TO_SUBCATEGORY: Dict[str, SubCategory] = {
    # 英文
    "Animation": SubCategory.ANIMATION,
    "Documentary": SubCategory.DOCUMENTARY,
    "Music": SubCategory.MUSIC,
    "Reality": SubCategory.VARIETY,
    "Talk": SubCategory.VARIETY,
    # 中文
    "动画": SubCategory.ANIMATION,
    "纪录": SubCategory.DOCUMENTARY,
    "纪录片": SubCategory.DOCUMENTARY,
    "音乐": SubCategory.MUSIC,
    "真人秀": SubCategory.VARIETY,
    "脱口秀": SubCategory.VARIETY,
}


# ============================================================
# 辅助函数
# ============================================================

def determine_subcategory(genres: List[str]) -> SubCategory:
    """
    根据 TMDB Genres 判断子分类
    
    按 TMDB 返回的顺序，第一个匹配的内置分类即为子分类。
    
    Args:
        genres: TMDB 返回的 genres 列表，如 ["Animation", "Comedy", "Music"]
    
    Returns:
        SubCategory 枚举值
    
    Examples:
        >>> determine_subcategory(["Animation", "Comedy", "Music"])
        SubCategory.ANIMATION
        >>> determine_subcategory(["Music", "Documentary"])
        SubCategory.MUSIC
        >>> determine_subcategory(["Drama", "Crime"])
        SubCategory.DEFAULT
    """
    for genre in genres:
        if genre in GENRE_TO_SUBCATEGORY:
            return GENRE_TO_SUBCATEGORY[genre]
    return SubCategory.DEFAULT


def get_subcategory_name(
    sub_category: SubCategory,
    media_type: MediaType,
    language: str = "zh"
) -> str:
    """
    获取子分类的显示名称
    
    Args:
        sub_category: 子分类枚举
        media_type: 媒体类型
        language: 语言 (zh/en)
    
    Returns:
        子分类显示名称
    """
    if language == "zh":
        if media_type == MediaType.TV:
            return SUBCATEGORY_TV_ZH.get(sub_category, "电视剧")
        else:
            return SUBCATEGORY_MOVIE_ZH.get(sub_category, "电影")
    else:
        if media_type == MediaType.TV:
            return SUBCATEGORY_TV_EN.get(sub_category, "TV Shows")
        else:
            return SUBCATEGORY_MOVIE_EN.get(sub_category, "Movies")

