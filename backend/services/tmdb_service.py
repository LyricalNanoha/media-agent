"""
TMDB服务

查询TMDB获取影视信息
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from tmdbv3api import TMDb, Movie, TV, Search, Season

from backend.config import get_config


@dataclass
class TMDBMediaInfo:
    """TMDB媒体信息"""
    tmdb_id: int
    media_type: str  # movie 或 tv
    title: str
    original_title: Optional[str] = None
    title_zh: Optional[str] = None
    title_en: Optional[str] = None
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    vote_average: Optional[float] = None
    genres: List[str] = None
    
    # 电视剧特有
    seasons_count: Optional[int] = None
    episodes_count: Optional[int] = None
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []


class TMDBService:
    """TMDB服务"""
    
    POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"
    BACKDROP_BASE_URL = "https://image.tmdb.org/t/p/w1280"
    
    def __init__(self, api_key: Optional[str] = None, language: str = "zh-CN"):
        """
        初始化TMDB服务
        
        Args:
            api_key: TMDB API Key，None则从配置读取
            language: 查询语言
        """
        config = get_config()
        self.api_key = api_key or config.tmdb.api_key
        self.language = language or config.tmdb.language
        
        if not self.api_key:
            raise ValueError("TMDB API Key未配置")
        
        # 初始化TMDb
        self.tmdb = TMDb()
        self.tmdb.api_key = self.api_key
        self.tmdb.language = self.language
        
        # API对象
        self.movie_api = Movie()
        self.tv_api = TV()
        self.search_api = Search()
        self.season_api = Season()
    
    def search_movie(
        self,
        query: str,
        year: Optional[int] = None,
        limit: int = 5
    ) -> List[TMDBMediaInfo]:
        """
        搜索电影
        
        Args:
            query: 搜索关键词
            year: 年份筛选
            limit: 返回数量限制
            
        Returns:
            List[TMDBMediaInfo]: 搜索结果
        """
        try:
            results = self.search_api.movies(query, year=year)
            return [self._parse_movie(m) for m in results[:limit]]
        except Exception as e:
            print(f"搜索电影失败: {e}")
            return []
    
    def search_tv(
        self,
        query: str,
        year: Optional[int] = None,
        limit: int = 5
    ) -> List[TMDBMediaInfo]:
        """
        搜索电视剧
        
        Args:
            query: 搜索关键词
            year: 年份筛选（仅用于结果过滤）
            limit: 返回数量限制
            
        Returns:
            List[TMDBMediaInfo]: 搜索结果
        """
        try:
            # tmdbv3api的tv_shows不支持year参数，手动过滤
            results = self.search_api.tv_shows(query)
            parsed = [self._parse_tv(t) for t in results]
            
            # 如果指定了年份，进行过滤
            if year:
                parsed = [p for p in parsed if p.year and abs(p.year - year) <= 1]
            
            return parsed[:limit]
        except Exception as e:
            print(f"搜索电视剧失败: {e}")
            return []
    
    def search_tv_smart(
        self,
        query: str,
        year: Optional[int] = None,
        limit: int = 5
    ) -> List[TMDBMediaInfo]:
        """
        智能搜索电视剧 - 自动尝试多种变体
        
        Args:
            query: 搜索关键词
            year: 年份筛选
            limit: 返回数量限制
            
        Returns:
            List[TMDBMediaInfo]: 搜索结果
        """
        import re
        
        # 生成搜索变体
        variants = [query]
        
        # 去掉特殊字符的版本
        clean = re.sub(r'[!！?\-_+]', ' ', query).strip()
        if clean != query:
            variants.append(clean)
        
        # 去掉所有非字母数字的版本
        alpha_only = re.sub(r'[^a-zA-Z0-9\s]', '', query).strip()
        if alpha_only and alpha_only not in variants:
            variants.append(alpha_only)
        
        # 尝试各种变体搜索
        all_results = []
        seen_ids = set()
        
        for variant in variants:
            if not variant:
                continue
            results = self.search_tv(variant, year=year, limit=limit)
            for r in results:
                if r.tmdb_id not in seen_ids:
                    all_results.append(r)
                    seen_ids.add(r.tmdb_id)
                    if len(all_results) >= limit:
                        return all_results
        
        return all_results[:limit]
    
    def search_tv_multilang(
        self,
        query: str,
        target_language: str = "zh-CN",
        year: Optional[int] = None,
        limit: int = 5
    ) -> List[TMDBMediaInfo]:
        """
        多语言智能搜索电视剧
        
        策略：
        1. 先用英文搜索（关键词更精确匹配英文标题）
        2. 获取 TMDB ID
        3. 用目标语言获取详情（获取中文标题等）
        
        Args:
            query: 搜索关键词
            target_language: 目标语言（用于获取详情），如 "zh-CN", "en-US", "ja-JP"
            year: 年份筛选
            limit: 返回数量限制
            
        Returns:
            List[TMDBMediaInfo]: 包含双语标题的搜索结果
        """
        import logging
        logger = logging.getLogger(__name__)
        
        results = []
        seen_ids = set()
        
        # 保存原始语言设置
        original_language = self.tmdb.language
        
        try:
            # 1. 先用英文搜索（精确匹配英文/罗马字标题）
            self.tmdb.language = "en-US"
            en_results = self.search_api.tv_shows(query)
            logger.info(f"📡 [TMDB en-US] 搜索 '{query}': 找到 {len(list(en_results))} 个结果")
            
            # 重新获取结果（因为迭代器已消耗）
            en_results = self.search_api.tv_shows(query)
            
            for item in en_results:
                if len(results) >= limit:
                    break
                    
                tmdb_id = item.id
                if tmdb_id in seen_ids:
                    continue
                seen_ids.add(tmdb_id)
                
                # 解析英文信息
                en_info = self._parse_tv(item)
                
                # 2. 用目标语言获取详情
                self.tmdb.language = target_language
                try:
                    details = self.tv_api.details(tmdb_id)
                    target_info = self._parse_tv(details)
                    
                    # 合并信息：使用目标语言的标题，但保留英文原标题
                    target_info.title_en = en_info.title
                    target_info.title_zh = target_info.title if target_language.startswith("zh") else None
                    
                    # 年份过滤
                    if year and target_info.year and abs(target_info.year - year) > 1:
                        continue
                    
                    results.append(target_info)
                    logger.info(f"  → ID {tmdb_id}: {target_info.title} ({target_info.year})")
                    
                except Exception as e:
                    logger.warning(f"  获取 ID {tmdb_id} 详情失败: {e}")
                    results.append(en_info)
            
            # 3. 如果英文搜索结果不够，用目标语言补充搜索
            if len(results) < limit:
                self.tmdb.language = target_language
                target_results = self.search_api.tv_shows(query)
                
                for item in target_results:
                    if len(results) >= limit:
                        break
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        info = self._parse_tv(item)
                        if year and info.year and abs(info.year - year) > 1:
                            continue
                        results.append(info)
                        logger.info(f"  → (补充) ID {item.id}: {info.title} ({info.year})")
            
        finally:
            # 恢复原始语言设置
            self.tmdb.language = original_language
        
        return results
    
    def search_movie_multilang(
        self,
        query: str,
        target_language: str = "zh-CN",
        year: Optional[int] = None,
        limit: int = 10
    ) -> List[TMDBMediaInfo]:
        """
        多语言智能搜索电影
        
        策略：
        1. 先用英文搜索（精确匹配）
        2. 用目标语言获取详情
        
        Args:
            query: 搜索关键词
            target_language: 目标语言
            year: 年份筛选
            limit: 返回数量限制
            
        Returns:
            List[TMDBMediaInfo]: 包含双语标题的搜索结果
        """
        import logging
        logger = logging.getLogger(__name__)
        
        results = []
        seen_ids = set()
        
        original_language = self.tmdb.language
        
        try:
            # 1. 英文搜索
            self.tmdb.language = "en-US"
            en_results = self.search_api.movies(query, year=year)
            
            for item in en_results:
                if len(results) >= limit:
                    break
                    
                tmdb_id = item.id
                if tmdb_id in seen_ids:
                    continue
                seen_ids.add(tmdb_id)
                
                en_info = self._parse_movie(item)
                
                # 2. 目标语言获取详情
                self.tmdb.language = target_language
                try:
                    details = self.movie_api.details(tmdb_id)
                    target_info = self._parse_movie(details)
                    target_info.title_en = en_info.title
                    target_info.title_zh = target_info.title if target_language.startswith("zh") else None
                    results.append(target_info)
                    logger.info(f"📡 [TMDB Movie] ID {tmdb_id}: {target_info.title} ({target_info.year})")
                except Exception as e:
                    logger.warning(f"  获取电影 ID {tmdb_id} 详情失败: {e}")
                    results.append(en_info)
            
            # 3. 补充搜索
            if len(results) < limit:
                self.tmdb.language = target_language
                target_results = self.search_api.movies(query, year=year)
                for item in target_results:
                    if len(results) >= limit:
                        break
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        results.append(self._parse_movie(item))
                        
        finally:
            self.tmdb.language = original_language
        
        return results
    
    def search_multi(
        self,
        query: str,
        limit: int = 10
    ) -> List[TMDBMediaInfo]:
        """
        搜索所有类型
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            List[TMDBMediaInfo]: 搜索结果
        """
        try:
            results = self.search_api.multi(query)
            parsed = []
            for item in results[:limit]:
                media_type = getattr(item, 'media_type', None)
                if media_type == 'movie':
                    parsed.append(self._parse_movie(item))
                elif media_type == 'tv':
                    parsed.append(self._parse_tv(item))
            return parsed
        except Exception as e:
            print(f"搜索失败: {e}")
            return []
    
    def get_movie_details(self, movie_id: int) -> Optional[TMDBMediaInfo]:
        """
        获取电影详情
        
        Args:
            movie_id: TMDB电影ID
            
        Returns:
            TMDBMediaInfo: 电影信息
        """
        try:
            movie = self.movie_api.details(movie_id)
            return self._parse_movie(movie)
        except Exception as e:
            print(f"获取电影详情失败: {e}")
            return None
    
    def get_tv_details(self, tv_id: int) -> Optional[TMDBMediaInfo]:
        """
        获取电视剧详情
        
        Args:
            tv_id: TMDB电视剧ID
            
        Returns:
            TMDBMediaInfo: 电视剧信息
        """
        try:
            tv = self.tv_api.details(tv_id)
            return self._parse_tv(tv)
        except Exception as e:
            print(f"获取电视剧详情失败: {e}")
            return None
    
    def get_tv_season(self, tv_id: int, season_number: int) -> Optional[Dict[str, Any]]:
        """
        获取电视剧季信息
        
        Args:
            tv_id: TMDB电视剧ID
            season_number: 季数
            
        Returns:
            Dict: 季信息
        """
        try:
            season = self.season_api.details(tv_id, season_number)
            return {
                'season_number': season_number,
                'name': getattr(season, 'name', None),
                'overview': getattr(season, 'overview', None),
                'episode_count': len(getattr(season, 'episodes', [])),
                'episodes': [
                    {
                        'episode_number': ep.episode_number,
                        'name': ep.name,
                        'overview': getattr(ep, 'overview', None),
                        'air_date': getattr(ep, 'air_date', None),
                    }
                    for ep in getattr(season, 'episodes', [])
                ]
            }
        except Exception as e:
            print(f"获取季信息失败: {e}")
            return None
    
    def get_tv_all_seasons(self, tv_id: int) -> List[Dict[str, Any]]:
        """
        获取电视剧所有季信息（含 TMDB 实际编号和累计范围）
        
        Args:
            tv_id: TMDB电视剧ID
            
        Returns:
            List[Dict]: 所有季信息，包含：
                - ep_start, ep_end: TMDB 实际编号（用于输出文件名）
                - ep_start_global, ep_end_global: 累计编号（用于匹配全局编号资源）
        """
        tv_info = self.get_tv_details(tv_id)
        if not tv_info or not tv_info.seasons_count:
            return []
        
        seasons = []
        cumulative = 0  # 用于计算累计编号
        
        for s_num in range(1, tv_info.seasons_count + 1):
            season_info = self.get_tv_season(tv_id, s_num)
            if season_info:
                episodes = season_info.get('episodes', [])
                ep_count = len(episodes) if episodes else season_info.get('episode_count', 0)
                
                # 🔥 跳过 0 集的季（TMDB 上可能有占位但还没有内容）
                if ep_count == 0:
                    continue
                
                # 🔥 从 TMDB API 获取实际编号（不是自己计算！）
                if episodes:
                    ep_start_tmdb = episodes[0].get('episode_number', 1)
                    ep_end_tmdb = episodes[-1].get('episode_number', ep_count)
                else:
                    ep_start_tmdb = 1
                    ep_end_tmdb = ep_count
                
                seasons.append({
                    'season_number': s_num,
                    'name': season_info.get('name', f'Season {s_num}'),
                    'episode_count': ep_count,
                    # TMDB 实际编号（用于输出文件名）
                    'ep_start': ep_start_tmdb,
                    'ep_end': ep_end_tmdb,
                    # 累计编号（用于匹配全局编号资源）
                    'ep_start_global': cumulative + 1,
                    'ep_end_global': cumulative + ep_count,
                })
                cumulative += ep_count
        
        return seasons
    
    def get_season_0_episodes(self, tv_id: int) -> List[Dict[str, Any]]:
        """
        获取 Season 0 (特别篇) 的每集信息
        
        Season 0 通常包含：OVA、SP、导演剪辑版、预告片等特殊内容。
        返回每集的编号、名称和描述，供 LLM 匹配特殊版本文件。
        
        Args:
            tv_id: TMDB电视剧ID
            
        Returns:
            List[Dict]: 每集信息，包含 episode_number, name, overview
        """
        season0 = self.get_tv_season(tv_id, 0)
        if not season0:
            return []
        
        episodes = season0.get('episodes', [])
        return [{
            'episode_number': ep.get('episode_number', 0),
            'name': ep.get('name', f"Episode {ep.get('episode_number', 0)}"),
            'overview': ep.get('overview', '')  # 🆕 增加描述字段
        } for ep in episodes]
    
    def get_episode_name(
        self,
        tv_id: int,
        season_number: int,
        episode_number: int
    ) -> Optional[str]:
        """
        获取剧集名称
        
        Args:
            tv_id: TMDB电视剧ID
            season_number: 季数
            episode_number: 集数
            
        Returns:
            str: 集名称
        """
        season_info = self.get_tv_season(tv_id, season_number)
        if season_info and 'episodes' in season_info:
            for ep in season_info['episodes']:
                if ep['episode_number'] == episode_number:
                    return ep['name']
        return None
    
    def _parse_movie(self, movie) -> TMDBMediaInfo:
        """解析电影数据"""
        # 提取年份（确保 release_date 是字符串）
        release_date = getattr(movie, 'release_date', None)
        year = None
        if release_date and isinstance(release_date, str) and len(release_date) >= 4:
            try:
                year = int(release_date[:4])
            except ValueError:
                year = None
        
        # 提取类型
        # 🔥 修复：AsObj 类型不是 list，需要直接遍历
        genres = []
        genre_data = getattr(movie, 'genres', None) or getattr(movie, 'genre_ids', [])
        try:
            for g in genre_data:
                # AsObj 可以用 .get() 或直接取属性
                if hasattr(g, 'get'):
                    name = g.get('name', '')
                elif hasattr(g, 'name'):
                    name = g.name
                elif isinstance(g, int):
                    name = str(g)  # genre_id
                else:
                    name = str(g)
                if name:
                    genres.append(name)
        except (TypeError, AttributeError):
            pass  # genre_data 不可遍历
        
        return TMDBMediaInfo(
            tmdb_id=movie.id,
            media_type='movie',
            title=getattr(movie, 'title', None) or getattr(movie, 'name', ''),
            original_title=getattr(movie, 'original_title', None),
            year=year,
            overview=getattr(movie, 'overview', None),
            poster_path=self._full_poster_url(getattr(movie, 'poster_path', None)),
            backdrop_path=self._full_backdrop_url(getattr(movie, 'backdrop_path', None)),
            vote_average=getattr(movie, 'vote_average', None),
            genres=genres,
        )
    
    def _parse_tv(self, tv) -> TMDBMediaInfo:
        """解析电视剧数据"""
        # 提取年份（确保 first_air_date 是字符串）
        first_air_date = getattr(tv, 'first_air_date', None)
        year = None
        if first_air_date and isinstance(first_air_date, str) and len(first_air_date) >= 4:
            try:
                year = int(first_air_date[:4])
            except ValueError:
                year = None
        
        # 提取类型
        # 🔥 修复：AsObj 类型不是 list，需要直接遍历
        genres = []
        genre_data = getattr(tv, 'genres', None) or getattr(tv, 'genre_ids', [])
        try:
            for g in genre_data:
                # AsObj 可以用 .get() 或直接取属性
                if hasattr(g, 'get'):
                    name = g.get('name', '')
                elif hasattr(g, 'name'):
                    name = g.name
                elif isinstance(g, int):
                    name = str(g)  # genre_id
                else:
                    name = str(g)
                if name:
                    genres.append(name)
        except (TypeError, AttributeError):
            pass  # genre_data 不可遍历
        
        return TMDBMediaInfo(
            tmdb_id=tv.id,
            media_type='tv',
            title=getattr(tv, 'name', None) or getattr(tv, 'title', ''),
            original_title=getattr(tv, 'original_name', None),
            year=year,
            overview=getattr(tv, 'overview', None),
            poster_path=self._full_poster_url(getattr(tv, 'poster_path', None)),
            backdrop_path=self._full_backdrop_url(getattr(tv, 'backdrop_path', None)),
            vote_average=getattr(tv, 'vote_average', None),
            genres=genres,
            seasons_count=getattr(tv, 'number_of_seasons', None),
            episodes_count=getattr(tv, 'number_of_episodes', None),
        )
    
    def _full_poster_url(self, path: Optional[str]) -> Optional[str]:
        """生成完整海报URL"""
        if path:
            return f"{self.POSTER_BASE_URL}{path}"
        return None
    
    def _full_backdrop_url(self, path: Optional[str]) -> Optional[str]:
        """生成完整背景图URL"""
        if path:
            return f"{self.BACKDROP_BASE_URL}{path}"
        return None


# 全局服务实例
_tmdb_service: Optional[TMDBService] = None


def get_tmdb_service() -> TMDBService:
    """获取全局TMDB服务实例"""
    global _tmdb_service
    if _tmdb_service is None:
        _tmdb_service = TMDBService()
    return _tmdb_service

