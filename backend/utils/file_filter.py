"""
文件过滤器

过滤视频文件和字幕文件，排除不需要处理的文件
"""

import os
import fnmatch
from typing import List, Optional, Set
from pathlib import Path

from backend.config import get_config


class FileFilter:
    """文件过滤器"""
    
    def __init__(
        self,
        video_extensions: Optional[List[str]] = None,
        subtitle_extensions: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
    ):
        """
        初始化过滤器
        
        Args:
            video_extensions: 视频文件扩展名列表，None则从配置读取
            subtitle_extensions: 字幕文件扩展名列表，None则从配置读取
            exclude_patterns: 排除模式列表，None则从配置读取
        """
        config = get_config()
        
        self.video_extensions: Set[str] = set(
            video_extensions or config.scan.video_extensions
        )
        self.subtitle_extensions: Set[str] = set(
            subtitle_extensions or config.scan.subtitle_extensions
        )
        self.exclude_patterns: List[str] = (
            exclude_patterns or config.scan.exclude_patterns
        )
        
        # 标准化扩展名（确保以点开头，小写）
        self.video_extensions = {
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            for ext in self.video_extensions
        }
        self.subtitle_extensions = {
            ext.lower() if ext.startswith('.') else f'.{ext.lower()}'
            for ext in self.subtitle_extensions
        }
    
    def is_video_file(self, filename: str) -> bool:
        """
        判断是否为视频文件
        
        Args:
            filename: 文件名或路径
            
        Returns:
            bool: 是否为视频文件
        """
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.video_extensions
    
    def is_subtitle_file(self, filename: str) -> bool:
        """
        判断是否为字幕文件
        
        Args:
            filename: 文件名或路径
            
        Returns:
            bool: 是否为字幕文件
        """
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.subtitle_extensions
    
    def is_media_file(self, filename: str) -> bool:
        """
        判断是否为媒体文件（视频或字幕）
        
        Args:
            filename: 文件名或路径
            
        Returns:
            bool: 是否为媒体文件
        """
        return self.is_video_file(filename) or self.is_subtitle_file(filename)
    
    def get_file_type(self, filename: str) -> Optional[str]:
        """
        获取文件类型
        
        Args:
            filename: 文件名或路径
            
        Returns:
            Optional[str]: 'video', 'subtitle', 或 None
        """
        if self.is_video_file(filename):
            return 'video'
        if self.is_subtitle_file(filename):
            return 'subtitle'
        return None
    
    def should_exclude(self, path: str) -> bool:
        """
        判断是否应该排除
        
        Args:
            path: 文件或目录路径
            
        Returns:
            bool: 是否应该排除
        """
        # 获取文件/目录名
        name = os.path.basename(path.rstrip('/'))
        
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
            # 也检查完整路径
            if fnmatch.fnmatch(path, f'*{pattern}*'):
                return True
        
        return False
    
    def filter_files(self, files: List[str]) -> List[str]:
        """
        过滤文件列表
        
        Args:
            files: 文件路径列表
            
        Returns:
            List[str]: 过滤后的视频文件列表
        """
        result = []
        for file_path in files:
            if self.should_exclude(file_path):
                continue
            if self.is_video_file(file_path):
                result.append(file_path)
        return result
    
    def filter_directories(self, directories: List[str]) -> List[str]:
        """
        过滤目录列表
        
        Args:
            directories: 目录路径列表
            
        Returns:
            List[str]: 过滤后的目录列表
        """
        return [d for d in directories if not self.should_exclude(d)]
    
    def get_video_extension(self, filename: str) -> Optional[str]:
        """
        获取视频文件的扩展名
        
        Args:
            filename: 文件名
            
        Returns:
            Optional[str]: 扩展名，非视频文件返回None
        """
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.video_extensions:
            return ext
        return None


# 全局过滤器实例
_filter: Optional[FileFilter] = None


def get_file_filter() -> FileFilter:
    """获取全局过滤器实例"""
    global _filter
    if _filter is None:
        _filter = FileFilter()
    return _filter


def is_video_file(filename: str) -> bool:
    """判断是否为视频文件的便捷函数"""
    return get_file_filter().is_video_file(filename)


def is_subtitle_file(filename: str) -> bool:
    """判断是否为字幕文件的便捷函数"""
    return get_file_filter().is_subtitle_file(filename)


def is_media_file(filename: str) -> bool:
    """判断是否为媒体文件（视频或字幕）的便捷函数"""
    return get_file_filter().is_media_file(filename)


def get_file_type(filename: str) -> Optional[str]:
    """获取文件类型的便捷函数"""
    return get_file_filter().get_file_type(filename)


def should_exclude(path: str) -> bool:
    """判断是否应该排除的便捷函数"""
    return get_file_filter().should_exclude(path)

