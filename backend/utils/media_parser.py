"""
媒体文件名解析器

从文件名中提取：标题、年份、季数、集数、质量等信息
"""

import re
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class ParsedInfo:
    """解析结果"""
    title: Optional[str] = None
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_end: Optional[int] = None  # 多集合并时的结束集数
    episode_title: Optional[str] = None
    quality: Optional[str] = None
    source: Optional[str] = None  # BluRay, WEB-DL等
    codec: Optional[str] = None  # x264, HEVC等
    media_type: str = "unknown"  # movie, tv, unknown
    confidence: float = 0.5


class MediaParser:
    """媒体文件名解析器"""
    
    # 常见的视频质量标识
    QUALITY_PATTERNS = [
        r'4K|2160[pP]',
        r'1080[pPiI]',
        r'720[pPiI]',
        r'480[pPiI]',
        r'HDTV',
        r'WEB-?DL',
        r'WEBRip',
        r'BluRay|BD|BDRip',
        r'DVDRip|DVD',
        r'HDCAM|CAM',
    ]
    
    # 视频编码标识
    CODEC_PATTERNS = [
        r'[xXhH]\.?264',
        r'[xXhH]\.?265|HEVC',
        r'AVC',
        r'VP9',
        r'AV1',
    ]
    
    # 来源标识
    SOURCE_PATTERNS = [
        r'BluRay|BD(?:Rip)?',
        r'WEB-?DL',
        r'WEBRip',
        r'HDTV',
        r'DVDRip|DVD',
        r'AMZN|NF|DSNP|HMAX',  # 流媒体平台
    ]
    
    # 季集模式
    SEASON_EPISODE_PATTERNS = [
        # S01E01, S1E1, S01E01E02
        r'[Ss](\d{1,2})[Ee](\d{1,3})(?:[Ee](\d{1,3}))?',
        # Season 01 Episode 01
        r'[Ss]eason\s*(\d{1,2})\s*[Ee]pisode\s*(\d{1,3})',
        # 1x01, 1x01-02
        r'(\d{1,2})[xX](\d{1,3})(?:-(\d{1,3}))?',
        # EP01, Ep01
        r'[Ee][Pp]\.?(\d{1,3})',
        # 第01集, 第1集
        r'第(\d{1,3})[集话話]',
        # [01], [01-02] (通常在标题后)
        r'\[(\d{1,3})(?:-(\d{1,3}))?\]',
        # E01, E01-E02
        r'[Ee](\d{1,3})(?:-[Ee]?(\d{1,3}))?',
    ]
    
    # 年份模式
    YEAR_PATTERNS = [
        r'\((\d{4})\)',  # (2020)
        r'\[(\d{4})\]',  # [2020]
        r'\.(\d{4})\.',  # .2020.
        r'\s(\d{4})\s',  # 空格包围
        r'(\d{4})$',     # 末尾
    ]
    
    # 需要清理的标记
    CLEANUP_PATTERNS = [
        r'\[.*?\]',      # [xxx]
        r'\(.*?\)',      # (xxx) - 但保留年份
        r'【.*?】',      # 【xxx】
        r'\.+',          # 多个点
        r'_+',           # 多个下划线
        r'-+',           # 多个连字符
        r'\s+',          # 多个空格
    ]
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """预编译正则表达式"""
        self.quality_re = re.compile('|'.join(self.QUALITY_PATTERNS), re.IGNORECASE)
        self.codec_re = re.compile('|'.join(self.CODEC_PATTERNS), re.IGNORECASE)
        self.source_re = re.compile('|'.join(self.SOURCE_PATTERNS), re.IGNORECASE)
        self.se_patterns = [(re.compile(p, re.IGNORECASE), p) for p in self.SEASON_EPISODE_PATTERNS]
        self.year_patterns = [re.compile(p) for p in self.YEAR_PATTERNS]
    
    def parse(self, filename: str) -> ParsedInfo:
        """
        解析文件名
        
        Args:
            filename: 文件名（不含路径，可含扩展名）
            
        Returns:
            ParsedInfo: 解析结果
        """
        result = ParsedInfo()
        
        # 移除扩展名
        name = self._remove_extension(filename)
        original_name = name
        
        # 提取质量信息
        result.quality = self._extract_quality(name)
        
        # 提取编码信息
        result.codec = self._extract_codec(name)
        
        # 提取来源信息
        result.source = self._extract_source(name)
        
        # 提取季集信息
        se_info = self._extract_season_episode(name)
        if se_info:
            result.season = se_info.get('season')
            result.episode = se_info.get('episode')
            result.episode_end = se_info.get('episode_end')
            result.media_type = "tv"
            name = se_info.get('remaining', name)
        
        # 提取年份
        year_info = self._extract_year(name)
        if year_info:
            result.year = year_info['year']
            name = year_info['remaining']
        
        # 清理并提取标题
        result.title = self._extract_title(name)
        
        # 如果没有季集信息，可能是电影
        if result.media_type == "unknown" and result.year:
            result.media_type = "movie"
            result.confidence = 0.7
        elif result.media_type == "tv":
            result.confidence = 0.8
        
        # 如果标题为空，尝试从原始名称提取
        if not result.title:
            result.title = self._fallback_title(original_name)
            result.confidence *= 0.5
        
        return result
    
    def _remove_extension(self, filename: str) -> str:
        """移除文件扩展名"""
        video_extensions = [
            '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv',
            '.m4v', '.ts', '.rmvb', '.webm', '.iso'
        ]
        lower_name = filename.lower()
        for ext in video_extensions:
            if lower_name.endswith(ext):
                return filename[:-len(ext)]
        return filename
    
    def _extract_quality(self, name: str) -> Optional[str]:
        """提取质量信息"""
        match = self.quality_re.search(name)
        if match:
            return match.group(0).upper()
        return None
    
    def _extract_codec(self, name: str) -> Optional[str]:
        """提取编码信息"""
        match = self.codec_re.search(name)
        if match:
            return match.group(0).upper()
        return None
    
    def _extract_source(self, name: str) -> Optional[str]:
        """提取来源信息"""
        match = self.source_re.search(name)
        if match:
            return match.group(0)
        return None
    
    def _extract_season_episode(self, name: str) -> Optional[Dict[str, Any]]:
        """提取季集信息"""
        for pattern, _ in self.se_patterns:
            match = pattern.search(name)
            if match:
                groups = match.groups()
                result = {'remaining': name[:match.start()] + name[match.end():]}
                
                if len(groups) >= 2 and groups[0] and groups[1]:
                    # S01E01 格式
                    result['season'] = int(groups[0])
                    result['episode'] = int(groups[1])
                    if len(groups) >= 3 and groups[2]:
                        result['episode_end'] = int(groups[2])
                elif len(groups) >= 1 and groups[0]:
                    # 仅集数 EP01 格式
                    result['episode'] = int(groups[0])
                    result['season'] = 1  # 默认第一季
                    if len(groups) >= 2 and groups[1]:
                        result['episode_end'] = int(groups[1])
                
                return result
        return None
    
    def _extract_year(self, name: str) -> Optional[Dict[str, Any]]:
        """提取年份"""
        for pattern in self.year_patterns:
            match = pattern.search(name)
            if match:
                year = int(match.group(1))
                # 合理年份范围
                if 1900 <= year <= 2100:
                    remaining = name[:match.start()] + name[match.end():]
                    return {'year': year, 'remaining': remaining}
        return None
    
    def _extract_title(self, name: str) -> str:
        """提取并清理标题"""
        # 移除质量、编码、来源等标识
        title = self.quality_re.sub('', name)
        title = self.codec_re.sub('', title)
        title = self.source_re.sub('', title)
        
        # 移除常见的发布组标识
        title = re.sub(r'-[A-Za-z0-9]+$', '', title)  # 末尾的 -GroupName
        
        # 替换分隔符为空格
        title = re.sub(r'[._\-]+', ' ', title)
        
        # 移除方括号内容（但保留中文字符）
        title = re.sub(r'\[[^\u4e00-\u9fff]*\]', '', title)
        
        # 清理多余空格
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title
    
    def _fallback_title(self, name: str) -> str:
        """回退方案：简单清理后的名称"""
        # 简单替换分隔符
        title = re.sub(r'[._\-]+', ' ', name)
        # 移除方括号
        title = re.sub(r'\[.*?\]', '', title)
        title = re.sub(r'\(.*?\)', '', title)
        # 清理空格
        title = re.sub(r'\s+', ' ', title).strip()
        # 截取前面可能的标题部分
        words = title.split()
        if len(words) > 5:
            title = ' '.join(words[:5])
        return title
    
    def is_tv_show(self, filename: str) -> bool:
        """判断是否为电视剧"""
        result = self.parse(filename)
        return result.media_type == "tv"
    
    def is_movie(self, filename: str) -> bool:
        """判断是否为电影"""
        result = self.parse(filename)
        return result.media_type == "movie"


# 便捷函数
def parse_media_filename(filename: str) -> ParsedInfo:
    """解析媒体文件名的便捷函数"""
    parser = MediaParser()
    return parser.parse(filename)





