"""
TMDB 集数映射表

核心设计：代码不判断，只查表
- 从 TMDB API 构建完整的集数映射
- 支持两种查询方式：累计编号 / (季, 集)
"""

from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, field


@dataclass
class EpisodeInfo:
    """单集信息"""
    season: int              # 季号
    episode_in_season: int   # 季内第几集（从1开始）
    tmdb_episode: int        # TMDB 的 episode_number（用于输出文件名）
    cumulative: int          # 累计编号（全系列第几集）
    
    def to_output_name(self) -> str:
        """生成输出文件名格式 SxxExx"""
        return f"S{self.season:02d}E{self.tmdb_episode:02d}"


@dataclass
class TMDBMapping:
    """TMDB 集数映射表"""
    
    tmdb_id: int
    title: str = ""
    media_type: str = "tv"  # tv / movie
    
    # 两种查询索引（自动构建）
    by_cumulative: Dict[int, EpisodeInfo] = field(default_factory=dict)
    by_season_episode: Dict[Tuple[int, int], EpisodeInfo] = field(default_factory=dict)
    
    # 元数据
    total_seasons: int = 0
    total_episodes: int = 0
    
    def lookup(self, context: str, number: int) -> Optional[EpisodeInfo]:
        """
        根据 context 查询集数信息
        
        Args:
            context: "cumulative" 或 "season_N"
            number: 文件中提取的编号
            
        Returns:
            EpisodeInfo 或 None（未找到）
        """
        if context == "cumulative":
            return self.by_cumulative.get(number)
        elif context.startswith("season_"):
            try:
                season = int(context.split("_")[1])
                return self.by_season_episode.get((season, number))
            except (IndexError, ValueError):
                return None
        else:
            return None
    
    def get_season_info(self, season: int) -> Dict:
        """获取某一季的信息"""
        episodes = [
            ep for ep in self.by_cumulative.values() 
            if ep.season == season
        ]
        if not episodes:
            return {}
        
        episodes.sort(key=lambda x: x.episode_in_season)
        return {
            "season": season,
            "episode_count": len(episodes),
            "tmdb_ep_start": episodes[0].tmdb_episode,
            "tmdb_ep_end": episodes[-1].tmdb_episode,
            "cumulative_start": episodes[0].cumulative,
            "cumulative_end": episodes[-1].cumulative,
        }
    
    def get_all_seasons_info(self) -> List[Dict]:
        """获取所有季的信息"""
        seasons = set(ep.season for ep in self.by_cumulative.values())
        return [self.get_season_info(s) for s in sorted(seasons)]


def build_episode_mapping(tmdb_id: int, tmdb_service) -> Optional[TMDBMapping]:
    """
    从 TMDB API 构建集数映射表
    
    Args:
        tmdb_id: TMDB ID
        tmdb_service: TMDBService 实例
        
    Returns:
        TMDBMapping 或 None（获取失败）
    """
    # 获取基本信息
    tv_info = tmdb_service.get_tv_details(tmdb_id)
    if not tv_info:
        return None
    
    mapping = TMDBMapping(
        tmdb_id=tmdb_id,
        title=tv_info.title_zh or tv_info.title or f"TMDB:{tmdb_id}",
        media_type="tv",
        total_seasons=tv_info.seasons_count or 0,
    )
    
    cumulative = 0
    
    # 遍历每一季
    for season_num in range(1, (tv_info.seasons_count or 0) + 1):
        season_info = tmdb_service.get_tv_season(tmdb_id, season_num)
        if not season_info:
            continue
        
        episodes = season_info.get('episodes', [])
        if not episodes:
            continue
        
        # 遍历每一集
        for i, ep in enumerate(episodes):
            cumulative += 1
            tmdb_ep = ep.get('episode_number', i + 1)
            
            episode_info = EpisodeInfo(
                season=season_num,
                episode_in_season=i + 1,
                tmdb_episode=tmdb_ep,
                cumulative=cumulative,
            )
            
            # 添加到两个索引
            mapping.by_cumulative[cumulative] = episode_info
            mapping.by_season_episode[(season_num, i + 1)] = episode_info
    
    mapping.total_episodes = cumulative
    return mapping


# 缓存映射表，避免重复构建
_mapping_cache: Dict[int, TMDBMapping] = {}


def get_or_build_mapping(tmdb_id: int, tmdb_service) -> Optional[TMDBMapping]:
    """获取或构建映射表（带缓存）"""
    if tmdb_id not in _mapping_cache:
        mapping = build_episode_mapping(tmdb_id, tmdb_service)
        if mapping:
            _mapping_cache[tmdb_id] = mapping
    return _mapping_cache.get(tmdb_id)


def clear_mapping_cache():
    """清空缓存"""
    _mapping_cache.clear()

