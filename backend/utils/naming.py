"""
媒体文件命名工具

统一的文件命名规则，确保 STRM 模式和传统整理模式使用一致的命名格式。

命名格式：
- 剧集：剧名.Sxx.Exx.ext
- 电影：电影名.年份.ext
- Live：Live名.年份.ext
"""

import re
from typing import Optional


def sanitize_filename(name: str) -> str:
    """
    清理文件名中的非法字符
    
    Args:
        name: 原始文件名
        
    Returns:
        清理后的文件名
    """
    # 移除或替换非法字符
    # Windows 禁止的字符: \ / : * ? " < > |
    illegal_chars = r'[\\/:*?"<>|]'
    cleaned = re.sub(illegal_chars, '.', name)
    
    # 特殊字符处理：某些字符可能导致文件系统或URL编码问题
    # ~ 替换为 - (波浪号替换为破折号)
    cleaned = cleaned.replace('~', '-')
    # ' 直接移除 (撇号)
    cleaned = cleaned.replace("'", "")
    # ! 直接移除 (感叹号，但保留在标题开头/结尾之外的位置可能有用)
    # 只在标题末尾的 ! 移除，中间的保留
    cleaned = re.sub(r'!+$', '', cleaned)  # 移除末尾的感叹号
    cleaned = re.sub(r'^!+', '', cleaned)  # 移除开头的感叹号
    
    # 合并连续的点
    cleaned = re.sub(r'\.{2,}', '.', cleaned)
    
    # 移除首尾的点和空格
    cleaned = cleaned.strip('. ')
    
    return cleaned


def format_episode_name(
    title: str, 
    season: int, 
    episode: int, 
    ext: str = ".mkv"
) -> str:
    """
    格式化剧集文件名
    
    格式：剧名.Sxx.Exx.ext
    
    Args:
        title: 剧集名称
        season: 季数
        episode: 集数
        ext: 文件扩展名（包含点）
        
    Returns:
        格式化后的文件名
    
    Examples:
        >>> format_episode_name("轻音少女", 1, 5, ".mkv")
        "轻音少女.S01.E05.mkv"
    """
    clean_title = sanitize_filename(title)
    return f"{clean_title}.S{season:02d}.E{episode:02d}{ext}"


def format_movie_name(
    title: str, 
    year: Optional[int] = None, 
    ext: str = ".mkv"
) -> str:
    """
    格式化电影文件名
    
    格式：电影名.年份.ext 或 电影名.ext（无年份时）
    
    Args:
        title: 电影名称
        year: 上映年份（可选）
        ext: 文件扩展名（包含点）
        
    Returns:
        格式化后的文件名
    
    Examples:
        >>> format_movie_name("轻音少女 剧场版", 2011, ".mkv")
        "轻音少女.剧场版.2011.mkv"
    """
    clean_title = sanitize_filename(title)
    # 将空格替换为点
    clean_title = clean_title.replace(' ', '.')
    
    if year:
        return f"{clean_title}.{year}{ext}"
    return f"{clean_title}{ext}"


def format_live_name(
    title: str, 
    year: Optional[int] = None, 
    ext: str = ".mkv"
) -> str:
    """
    格式化 Live/演唱会文件名
    
    格式与电影相同：Live名.年份.ext 或 Live名.ext
    
    Args:
        title: Live 名称
        year: 年份（可选）
        ext: 文件扩展名（包含点）
        
    Returns:
        格式化后的文件名
    
    Examples:
        >>> format_live_name("K-ON! Live Event LET'S GO!", 2009, ".mkv")
        "K-ON!.Live.Event.LET'S.GO!.2009.mkv"
    """
    # 复用电影命名逻辑
    return format_movie_name(title, year, ext)


def format_strm_episode_name(
    title: str, 
    season: int, 
    episode: int
) -> str:
    """
    格式化剧集 STRM 文件名
    
    Args:
        title: 剧集名称
        season: 季数
        episode: 集数
        
    Returns:
        格式化后的 STRM 文件名
    """
    return format_episode_name(title, season, episode, ".strm")


def format_strm_movie_name(
    title: str, 
    year: Optional[int] = None
) -> str:
    """
    格式化电影 STRM 文件名
    
    Args:
        title: 电影名称
        year: 年份（可选）
        
    Returns:
        格式化后的 STRM 文件名
    """
    return format_movie_name(title, year, ".strm")


def format_series_folder(title: str, year: Optional[int] = None) -> str:
    """
    格式化剧集系列目录名
    
    格式：剧名 (年份)（保持空格和括号，兼容媒体服务器）
    
    Args:
        title: 剧集名称
        year: 首播年份（可选）
        
    Returns:
        格式化后的目录名
    
    Examples:
        >>> format_series_folder("轻音少女", 2009)
        "轻音少女 (2009)"
    """
    clean_title = sanitize_filename(title)
    if year:
        return f"{clean_title} ({year})"
    return clean_title


def format_season_folder(season: int) -> str:
    """
    格式化季目录名
    
    格式：Season XX（保持空格，兼容媒体服务器）
    
    Args:
        season: 季数
        
    Returns:
        格式化后的目录名
    
    Examples:
        >>> format_season_folder(1)
        "Season 01"
    """
    return f"Season {season:02d}"


def format_movie_folder(title: str, year: Optional[int] = None) -> str:
    """
    格式化电影目录名
    
    格式：电影名 (年份)（保持空格和括号，兼容媒体服务器）
    
    Args:
        title: 电影名称
        year: 年份（可选）
        
    Returns:
        格式化后的目录名
    
    Examples:
        >>> format_movie_folder("轻音少女 剧场版", 2011)
        "轻音少女 剧场版 (2011)"
    """
    clean_title = sanitize_filename(title)
    if year:
        return f"{clean_title} ({year})"
    return clean_title

