"""
Infuse命名格式化器

生成符合Infuse规范的文件名和目录结构
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class FormattedPath:
    """格式化后的路径信息"""
    directory: str  # 目录路径
    filename: str   # 文件名（含扩展名）
    full_path: str  # 完整路径


class InfuseFormatter:
    """
    Infuse命名格式化器
    
    Infuse命名规范：
    
    电影:
        电影名 (年份)/电影名 (年份).扩展名
        例: The Matrix (1999)/The Matrix (1999).mkv
    
    电视剧:
        剧名/Season XX/剧名 - SXXEXX - 集名.扩展名
        例: Breaking Bad/Season 01/Breaking Bad - S01E01 - Pilot.mkv
        
        如果没有集名:
        剧名/Season XX/剧名 - SXXEXX.扩展名
        
    特别篇:
        剧名/Specials/剧名 - S00EXX - 特别篇名.扩展名
    """
    
    # 文件名中不允许的字符
    INVALID_CHARS = r'[<>:"/\\|?*]'
    
    def __init__(self):
        pass
    
    def format_movie(
        self,
        title: str,
        year: Optional[int],
        extension: str,
        quality: Optional[str] = None,
        include_quality: bool = False
    ) -> FormattedPath:
        """
        格式化电影路径
        
        Args:
            title: 电影标题
            year: 年份
            extension: 文件扩展名（如 .mkv）
            quality: 质量标识（如 1080p）
            include_quality: 是否在文件名中包含质量标识
            
        Returns:
            FormattedPath: 格式化后的路径
        """
        # 清理标题
        clean_title = self._clean_filename(title)
        
        # 构建基础名称
        if year:
            base_name = f"{clean_title} ({year})"
        else:
            base_name = clean_title
        
        # 添加质量标识（可选）
        if include_quality and quality:
            filename = f"{base_name} - {quality}{extension}"
        else:
            filename = f"{base_name}{extension}"
        
        # 目录名
        directory = base_name
        
        return FormattedPath(
            directory=directory,
            filename=filename,
            full_path=f"{directory}/{filename}"
        )
    
    def format_tv_episode(
        self,
        series_title: str,
        season: int,
        episode: int,
        episode_title: Optional[str] = None,
        extension: str = ".mkv",
        episode_end: Optional[int] = None,
        quality: Optional[str] = None,
        include_quality: bool = False
    ) -> FormattedPath:
        """
        格式化电视剧集路径
        
        Args:
            series_title: 剧集标题
            season: 季数
            episode: 集数
            episode_title: 集标题（可选）
            extension: 文件扩展名
            episode_end: 多集合并时的结束集数
            quality: 质量标识
            include_quality: 是否包含质量标识
            
        Returns:
            FormattedPath: 格式化后的路径
        """
        # 清理标题
        clean_series = self._clean_filename(series_title)
        
        # 构建季数目录
        if season == 0:
            season_dir = "Specials"
        else:
            season_dir = f"Season {season:02d}"
        
        # 构建集数标识
        if episode_end and episode_end > episode:
            episode_tag = f"S{season:02d}E{episode:02d}-E{episode_end:02d}"
        else:
            episode_tag = f"S{season:02d}E{episode:02d}"
        
        # 构建文件名
        if episode_title:
            clean_ep_title = self._clean_filename(episode_title)
            base_name = f"{clean_series} - {episode_tag} - {clean_ep_title}"
        else:
            base_name = f"{clean_series} - {episode_tag}"
        
        # 添加质量标识
        if include_quality and quality:
            filename = f"{base_name} - {quality}{extension}"
        else:
            filename = f"{base_name}{extension}"
        
        # 目录结构
        directory = f"{clean_series}/{season_dir}"
        
        return FormattedPath(
            directory=directory,
            filename=filename,
            full_path=f"{directory}/{filename}"
        )
    
    def format_tv_season(
        self,
        series_title: str,
        season: int
    ) -> str:
        """
        格式化电视剧季目录路径
        
        Args:
            series_title: 剧集标题
            season: 季数
            
        Returns:
            str: 目录路径
        """
        clean_series = self._clean_filename(series_title)
        if season == 0:
            return f"{clean_series}/Specials"
        return f"{clean_series}/Season {season:02d}"
    
    def _clean_filename(self, name: str) -> str:
        """
        清理文件名中的非法字符
        
        Args:
            name: 原始名称
            
        Returns:
            str: 清理后的名称
        """
        # 替换非法字符
        clean = re.sub(self.INVALID_CHARS, '', name)
        
        # 替换多余空格
        clean = re.sub(r'\s+', ' ', clean)
        
        # 去除首尾空格
        clean = clean.strip()
        
        # 去除首尾的点和空格
        clean = clean.strip('. ')
        
        return clean
    
    def generate_movie_path(
        self,
        title: str,
        year: Optional[int],
        extension: str,
        base_path: str = "",
        language: str = "original"
    ) -> str:
        """
        生成电影的完整路径
        
        Args:
            title: 电影标题
            year: 年份
            extension: 扩展名
            base_path: 基础路径
            language: 使用的语言 (zh/en/original)
            
        Returns:
            str: 完整路径
        """
        formatted = self.format_movie(title, year, extension)
        
        if base_path:
            return f"{base_path.rstrip('/')}/{formatted.full_path}"
        return formatted.full_path
    
    def generate_tv_path(
        self,
        series_title: str,
        season: int,
        episode: int,
        extension: str,
        episode_title: Optional[str] = None,
        base_path: str = "",
        language: str = "original"
    ) -> str:
        """
        生成电视剧的完整路径
        
        Args:
            series_title: 剧名
            season: 季数
            episode: 集数
            extension: 扩展名
            episode_title: 集标题
            base_path: 基础路径
            language: 使用的语言
            
        Returns:
            str: 完整路径
        """
        formatted = self.format_tv_episode(
            series_title, season, episode, episode_title, extension
        )
        
        if base_path:
            return f"{base_path.rstrip('/')}/{formatted.full_path}"
        return formatted.full_path


# 便捷函数
def format_movie_path(
    title: str,
    year: Optional[int],
    extension: str,
    base_path: str = ""
) -> str:
    """格式化电影路径的便捷函数"""
    formatter = InfuseFormatter()
    return formatter.generate_movie_path(title, year, extension, base_path)


def format_tv_path(
    series_title: str,
    season: int,
    episode: int,
    extension: str,
    episode_title: Optional[str] = None,
    base_path: str = ""
) -> str:
    """格式化电视剧路径的便捷函数"""
    formatter = InfuseFormatter()
    return formatter.generate_tv_path(
        series_title, season, episode, extension, episode_title, base_path
    )





