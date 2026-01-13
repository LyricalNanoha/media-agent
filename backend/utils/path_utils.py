"""
路径生成工具

🔥 核心设计（见 docs/CONTEXT.md）：
- 根据媒体类型和子分类自动生成目标路径
- 用户只需提供根路径，系统自动生成完整的分类目录结构

目录结构示例（中文）：
    /root_path/
    ├── 剧集/
    │   ├── 动漫/
    │   ├── 纪录片/
    │   ├── 音乐/
    │   ├── 综艺/
    │   └── 电视剧/
    └── 电影/
        ├── 动漫/
        ├── 纪录片/
        ├── 音乐/
        └── 电影/
"""

from backend.agents.models import (
    MediaType,
    SubCategory,
    get_subcategory_name,
)


def get_target_path(
    root_path: str,
    media_type: MediaType,
    sub_category: SubCategory,
    language: str = "zh"
) -> str:
    """
    根据媒体类型和子分类生成目标路径
    
    Args:
        root_path: 用户指定的根路径，如 "/kuake/strm"
        media_type: 媒体类型 (TV/MOVIE)
        sub_category: 子分类 (ANIMATION/DOCUMENTARY/MUSIC/VARIETY/DEFAULT)
        language: 语言 (zh/en)
    
    Returns:
        完整的目标路径
    
    Examples:
        >>> get_target_path("/kuake/strm", MediaType.TV, SubCategory.ANIMATION, "zh")
        '/kuake/strm/剧集/动漫'
        
        >>> get_target_path("/kuake/strm", MediaType.MOVIE, SubCategory.DEFAULT, "zh")
        '/kuake/strm/电影/电影'
        
        >>> get_target_path("/media", MediaType.TV, SubCategory.DOCUMENTARY, "en")
        '/media/TV/Documentary'
    """
    root = root_path.rstrip('/')
    
    # 一级分类名称
    if language == "zh":
        type_name = "剧集" if media_type == MediaType.TV else "电影"
    else:
        type_name = "TV" if media_type == MediaType.TV else "Movies"
    
    # 二级分类名称（子分类）
    sub_name = get_subcategory_name(sub_category, media_type, language)
    
    return f"{root}/{type_name}/{sub_name}"


def get_all_target_paths(
    root_path: str,
    language: str = "zh"
) -> dict:
    """
    生成所有可能的目标路径
    
    Args:
        root_path: 用户指定的根路径
        language: 语言
    
    Returns:
        包含所有路径的字典
    
    Examples:
        >>> get_all_target_paths("/kuake/strm", "zh")
        {
            'tv_animation': '/kuake/strm/剧集/动漫',
            'tv_documentary': '/kuake/strm/剧集/纪录片',
            'tv_music': '/kuake/strm/剧集/音乐',
            'tv_variety': '/kuake/strm/剧集/综艺',
            'tv_default': '/kuake/strm/剧集/电视剧',
            'movie_animation': '/kuake/strm/电影/动漫',
            'movie_documentary': '/kuake/strm/电影/纪录片',
            'movie_music': '/kuake/strm/电影/音乐',
            'movie_variety': '/kuake/strm/电影/综艺',
            'movie_default': '/kuake/strm/电影/电影',
        }
    """
    paths = {}
    
    for media_type in MediaType:
        for sub_cat in SubCategory:
            key = f"{media_type.value}_{sub_cat.value}"
            paths[key] = get_target_path(root_path, media_type, sub_cat, language)
    
    return paths


def format_series_path(
    root_path: str,
    media_type: MediaType,
    sub_category: SubCategory,
    series_name: str,
    year: int = None,
    language: str = "zh"
) -> str:
    """
    生成系列的完整路径（包含系列文件夹）
    
    Args:
        root_path: 根路径
        media_type: 媒体类型
        sub_category: 子分类
        series_name: 系列名称
        year: 年份（可选）
        language: 语言
    
    Returns:
        系列的完整路径
    
    Examples:
        >>> format_series_path("/kuake/strm", MediaType.TV, SubCategory.ANIMATION, "火影忍者", 2002, "zh")
        '/kuake/strm/剧集/动漫/火影忍者 (2002)'
        
        >>> format_series_path("/kuake/strm", MediaType.MOVIE, SubCategory.ANIMATION, "轻音少女剧场版", 2011, "zh")
        '/kuake/strm/电影/动漫/轻音少女剧场版 (2011)'
    """
    base_path = get_target_path(root_path, media_type, sub_category, language)
    
    # 清理系列名称中的非法字符
    safe_name = series_name.replace('/', '-').replace('\\', '-').replace(':', '：')
    
    if year:
        folder_name = f"{safe_name} ({year})"
    else:
        folder_name = safe_name
    
    return f"{base_path}/{folder_name}"

