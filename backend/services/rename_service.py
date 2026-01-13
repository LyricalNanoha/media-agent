"""
重命名服务

核心的重命名逻辑，协调各个服务
"""

import os
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from backend.models.schemas import ParsedMediaFile, RenamePreviewItem
from backend.utils.media_parser import MediaParser, ParsedInfo
from backend.utils.infuse_formatter import InfuseFormatter
from backend.services.tmdb_service import TMDBService, TMDBMediaInfo


@dataclass
class RenameResult:
    """重命名结果"""
    success: bool
    original_path: str
    new_path: str
    error: Optional[str] = None


class RenameService:
    """重命名服务"""
    
    def __init__(
        self,
        tmdb_service: Optional[TMDBService] = None,
        language: str = "zh"
    ):
        """
        初始化重命名服务
        
        Args:
            tmdb_service: TMDB服务实例
            language: 命名语言偏好 (zh/en/original)
        """
        self.tmdb = tmdb_service
        self.language = language
        self.parser = MediaParser()
        self.formatter = InfuseFormatter()
    
    def parse_file(self, file_path: str) -> ParsedMediaFile:
        """
        解析媒体文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            ParsedMediaFile: 解析后的文件信息
        """
        filename = os.path.basename(file_path)
        parsed = self.parser.parse(filename)
        
        return ParsedMediaFile(
            path=file_path,
            filename=filename,
            extension=os.path.splitext(filename)[1],
            media_type=parsed.media_type,
            parsed_title=parsed.title,
            parsed_year=parsed.year,
            parsed_season=parsed.season,
            parsed_episode=parsed.episode,
            parsed_episode_title=parsed.episode_title,
            quality=parsed.quality,
        )
    
    def parse_files(self, file_paths: List[str]) -> List[ParsedMediaFile]:
        """
        批量解析媒体文件
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            List[ParsedMediaFile]: 解析后的文件列表
        """
        return [self.parse_file(p) for p in file_paths]
    
    async def match_tmdb(
        self,
        parsed_file: ParsedMediaFile
    ) -> Tuple[Optional[TMDBMediaInfo], float]:
        """
        匹配TMDB信息
        
        Args:
            parsed_file: 解析后的文件信息
            
        Returns:
            Tuple[TMDBMediaInfo, float]: (TMDB信息, 置信度)
        """
        if not self.tmdb or not parsed_file.parsed_title:
            return None, 0.0
        
        query = parsed_file.parsed_title
        year = parsed_file.parsed_year
        
        if parsed_file.media_type == "movie":
            results = self.tmdb.search_movie(query, year=year, limit=3)
        elif parsed_file.media_type == "tv":
            results = self.tmdb.search_tv(query, year=year, limit=3)
        else:
            # 类型不明确，搜索所有类型
            results = self.tmdb.search_multi(query, limit=5)
        
        if not results:
            return None, 0.0
        
        # 简单的置信度计算
        best_match = results[0]
        confidence = self._calculate_confidence(parsed_file, best_match)
        
        return best_match, confidence
    
    def _calculate_confidence(
        self,
        parsed: ParsedMediaFile,
        tmdb_info: TMDBMediaInfo
    ) -> float:
        """计算匹配置信度"""
        confidence = 0.5
        
        # 年份匹配加分
        if parsed.parsed_year and tmdb_info.year:
            if parsed.parsed_year == tmdb_info.year:
                confidence += 0.3
            elif abs(parsed.parsed_year - tmdb_info.year) <= 1:
                confidence += 0.1
        
        # 标题相似度（简单比较）
        if parsed.parsed_title and tmdb_info.title:
            parsed_lower = parsed.parsed_title.lower()
            tmdb_lower = tmdb_info.title.lower()
            
            if parsed_lower == tmdb_lower:
                confidence += 0.2
            elif parsed_lower in tmdb_lower or tmdb_lower in parsed_lower:
                confidence += 0.1
        
        return min(confidence, 1.0)
    
    def generate_new_path(
        self,
        parsed_file: ParsedMediaFile,
        tmdb_info: Optional[TMDBMediaInfo],
        base_path: str = "",
        language: Optional[str] = None
    ) -> str:
        """
        生成新路径
        
        Args:
            parsed_file: 解析后的文件信息
            tmdb_info: TMDB信息
            base_path: 基础路径
            language: 命名语言
            
        Returns:
            str: 新路径
        """
        lang = language or self.language
        
        # 确定使用的标题
        if tmdb_info:
            if lang == "zh" and tmdb_info.title:
                title = tmdb_info.title
            elif lang == "en" and tmdb_info.original_title:
                title = tmdb_info.original_title
            else:
                title = tmdb_info.title or tmdb_info.original_title
            year = tmdb_info.year
        else:
            title = parsed_file.parsed_title or "Unknown"
            year = parsed_file.parsed_year
        
        extension = parsed_file.extension
        
        if parsed_file.media_type == "movie" or (tmdb_info and tmdb_info.media_type == "movie"):
            return self.formatter.generate_movie_path(
                title=title,
                year=year,
                extension=extension,
                base_path=base_path,
            )
        else:
            # 电视剧
            season = parsed_file.parsed_season or 1
            episode = parsed_file.parsed_episode or 1
            
            # 尝试获取集名
            episode_title = None
            if tmdb_info and self.tmdb:
                episode_title = self.tmdb.get_episode_name(
                    tmdb_info.tmdb_id, season, episode
                )
            
            return self.formatter.generate_tv_path(
                series_title=title,
                season=season,
                episode=episode,
                extension=extension,
                episode_title=episode_title,
                base_path=base_path,
            )
    
    async def preview_rename(
        self,
        file_paths: List[str],
        base_path: str = "",
        language: Optional[str] = None
    ) -> List[RenamePreviewItem]:
        """
        生成重命名预览
        
        Args:
            file_paths: 文件路径列表
            base_path: 目标基础路径
            language: 命名语言
            
        Returns:
            List[RenamePreviewItem]: 预览项列表
        """
        previews = []
        
        for file_path in file_paths:
            parsed = self.parse_file(file_path)
            tmdb_info, confidence = await self.match_tmdb(parsed)
            
            new_path = self.generate_new_path(
                parsed, tmdb_info, base_path, language
            )
            
            preview = RenamePreviewItem(
                original_path=file_path,
                new_path=new_path,
                media_type=parsed.media_type,
                tmdb_id=tmdb_info.tmdb_id if tmdb_info else None,
                title=tmdb_info.title if tmdb_info else parsed.parsed_title,
                year=tmdb_info.year if tmdb_info else parsed.parsed_year,
                season=parsed.parsed_season,
                episode=parsed.parsed_episode,
                confidence=confidence,
                needs_confirmation=confidence < 0.7,
            )
            
            # 添加警告
            if not tmdb_info:
                preview.warning = "未能匹配TMDB信息，将使用解析的文件名"
            elif confidence < 0.5:
                preview.warning = "匹配置信度较低，请确认是否正确"
            
            previews.append(preview)
        
        return previews
    
    async def execute_rename(
        self,
        webdav_service,
        rename_items: List[RenamePreviewItem],
        dry_run: bool = False
    ) -> List[RenameResult]:
        """
        执行重命名
        
        Args:
            webdav_service: WebDAV服务实例
            rename_items: 重命名项列表
            dry_run: 是否只是模拟运行
            
        Returns:
            List[RenameResult]: 重命名结果列表
        """
        import time
        
        results = []
        
        # 🔥 不再使用 config.storage.request_delay
        # 延迟由 user_config.upload_delay 控制（通过工具层传入）
        # 此服务是底层服务，不应自行添加延迟
        
        for i, item in enumerate(rename_items):
            if dry_run:
                results.append(RenameResult(
                    success=True,
                    original_path=item.original_path,
                    new_path=item.new_path,
                ))
                continue
            
            try:
                # 确保目标目录存在
                new_dir = os.path.dirname(item.new_path)
                if new_dir:
                    webdav_service.create_directory(new_dir)
                
                # 执行移动
                webdav_service.move_file(item.original_path, item.new_path)
                
                results.append(RenameResult(
                    success=True,
                    original_path=item.original_path,
                    new_path=item.new_path,
                ))
            except Exception as e:
                results.append(RenameResult(
                    success=False,
                    original_path=item.original_path,
                    new_path=item.new_path,
                    error=str(e),
                ))
        
        return results

