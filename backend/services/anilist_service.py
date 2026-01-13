"""
AniList服务

使用AniList GraphQL API搜索动漫信息，
获取正确的日文/中文标题后再去TMDB搜索。

AniList是专业的动漫数据库，免费且无需API Key。
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import httpx


ANILIST_API_URL = "https://graphql.anilist.co"


@dataclass
class AniListMedia:
    """AniList媒体信息"""
    id: int
    title_romaji: Optional[str] = None  # 罗马字标题 (如 "K-ON!")
    title_english: Optional[str] = None  # 英文标题
    title_native: Optional[str] = None  # 原生标题（日文）
    title_chinese: Optional[str] = None  # 中文标题（从synonyms提取）
    year: Optional[int] = None
    format: Optional[str] = None  # TV, MOVIE, OVA, etc.
    episodes: Optional[int] = None
    status: Optional[str] = None
    genres: List[str] = None
    
    def __post_init__(self):
        if self.genres is None:
            self.genres = []
    
    @property
    def best_title_for_tmdb(self) -> str:
        """
        获取最适合在TMDB搜索的标题
        优先级：中文 > 日文原名 > 罗马字
        """
        return self.title_chinese or self.title_native or self.title_romaji or ""


class AniListService:
    """AniList服务"""
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    @property
    def sync_client(self) -> httpx.Client:
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=30.0)
        return self._sync_client
    
    def _score_match(self, query: str, media: 'AniListMedia') -> int:
        """
        计算搜索结果与查询词的匹配分数
        分数越高越匹配
        """
        query_lower = query.lower().strip()
        score = 0
        
        # 检查各标题字段
        titles = [
            media.title_english,
            media.title_romaji,
            media.title_native,
            media.title_chinese,
        ]
        
        for title in titles:
            if not title:
                continue
            title_lower = title.lower()
            
            # 完全匹配（最高分）
            if query_lower == title_lower:
                score += 100
            # 查询词是标题的开头
            elif title_lower.startswith(query_lower):
                score += 50
            # 查询词包含在标题中
            elif query_lower in title_lower:
                score += 30
            # 标题包含在查询词中
            elif title_lower in query_lower:
                score += 20
        
        return score
    
    def search_anime(self, query: str, limit: int = 5) -> List[AniListMedia]:
        """
        搜索动漫（同步）
        
        Args:
            query: 搜索关键词（支持英文、日文、罗马字）
            limit: 返回数量限制
            
        Returns:
            List[AniListMedia]: 搜索结果（按匹配度排序）
        """
        graphql_query = """
        query ($search: String, $perPage: Int) {
            Page(page: 1, perPage: $perPage) {
                media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
                    id
                    title {
                        romaji
                        english
                        native
                    }
                    synonyms
                    seasonYear
                    format
                    episodes
                    status
                    genres
                }
            }
        }
        """
        
        variables = {
            "search": query,
            "perPage": limit
        }
        
        try:
            response = self.sync_client.post(
                ANILIST_API_URL,
                json={"query": graphql_query, "variables": variables}
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("data", {}).get("Page", {}).get("media", []):
                # 从synonyms中提取中文标题
                chinese_title = None
                synonyms = item.get("synonyms", []) or []
                for syn in synonyms:
                    # 检查是否包含中文字符
                    if any('\u4e00' <= c <= '\u9fff' for c in syn):
                        chinese_title = syn
                        break
                
                media = AniListMedia(
                    id=item["id"],
                    title_romaji=item.get("title", {}).get("romaji"),
                    title_english=item.get("title", {}).get("english"),
                    title_native=item.get("title", {}).get("native"),
                    title_chinese=chinese_title,
                    year=item.get("seasonYear"),
                    format=item.get("format"),
                    episodes=item.get("episodes"),
                    status=item.get("status"),
                    genres=item.get("genres", []),
                )
                results.append(media)
            
            # 按匹配度排序，优先返回标题匹配的结果
            results.sort(key=lambda x: self._score_match(query, x), reverse=True)
            
            return results
            
        except Exception as e:
            print(f"AniList搜索失败: {e}")
            return []
    
    async def search_anime_async(self, query: str, limit: int = 5) -> List[AniListMedia]:
        """
        搜索动漫（异步）
        """
        graphql_query = """
        query ($search: String, $perPage: Int) {
            Page(page: 1, perPage: $perPage) {
                media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
                    id
                    title {
                        romaji
                        english
                        native
                    }
                    synonyms
                    seasonYear
                    format
                    episodes
                    status
                    genres
                }
            }
        }
        """
        
        variables = {
            "search": query,
            "perPage": limit
        }
        
        try:
            response = await self.client.post(
                ANILIST_API_URL,
                json={"query": graphql_query, "variables": variables}
            )
            response.raise_for_status()
            data = response.json()
            
            results = []
            for item in data.get("data", {}).get("Page", {}).get("media", []):
                chinese_title = None
                synonyms = item.get("synonyms", []) or []
                for syn in synonyms:
                    if any('\u4e00' <= c <= '\u9fff' for c in syn):
                        chinese_title = syn
                        break
                
                media = AniListMedia(
                    id=item["id"],
                    title_romaji=item.get("title", {}).get("romaji"),
                    title_english=item.get("title", {}).get("english"),
                    title_native=item.get("title", {}).get("native"),
                    title_chinese=chinese_title,
                    year=item.get("seasonYear"),
                    format=item.get("format"),
                    episodes=item.get("episodes"),
                    status=item.get("status"),
                    genres=item.get("genres", []),
                )
                results.append(media)
            
            return results
            
        except Exception as e:
            print(f"AniList搜索失败: {e}")
            return []
    
    def get_series_entries(self, media_id: int) -> List[AniListMedia]:
        """
        获取一个系列的所有相关条目（包括续集、前传、电影等）
        
        Args:
            media_id: AniList媒体ID
            
        Returns:
            List[AniListMedia]: 系列的所有相关条目
        """
        graphql_query = """
        query ($id: Int) {
            Media(id: $id, type: ANIME) {
                id
                title { romaji english native }
                synonyms
                seasonYear
                format
                episodes
                status
                relations {
                    edges {
                        relationType
                        node {
                            id
                            title { romaji english native }
                            synonyms
                            seasonYear
                            format
                            episodes
                            status
                        }
                    }
                }
            }
        }
        """
        
        try:
            response = self.sync_client.post(
                ANILIST_API_URL,
                json={"query": graphql_query, "variables": {"id": media_id}}
            )
            response.raise_for_status()
            data = response.json()
            
            media_data = data.get("data", {}).get("Media", {})
            if not media_data:
                return []
            
            # 提取中文标题的辅助函数
            def extract_chinese(synonyms):
                for syn in (synonyms or []):
                    if any('\u4e00' <= c <= '\u9fff' for c in syn):
                        return syn
                return None
            
            # 主条目
            main_entry = AniListMedia(
                id=media_data["id"],
                title_romaji=media_data.get("title", {}).get("romaji"),
                title_english=media_data.get("title", {}).get("english"),
                title_native=media_data.get("title", {}).get("native"),
                title_chinese=extract_chinese(media_data.get("synonyms")),
                year=media_data.get("seasonYear"),
                format=media_data.get("format"),
                episodes=media_data.get("episodes"),
                status=media_data.get("status"),
            )
            
            results = [main_entry]
            
            # 相关条目
            relations = media_data.get("relations", {}).get("edges", [])
            for edge in relations:
                relation_type = edge.get("relationType")
                node = edge.get("node", {})
                
                # 包括所有相关类型（包括电影、外传、演唱会等）
                # SEQUEL: 续集, PREQUEL: 前传, SIDE_STORY: 外传
                # PARENT: 母体, ALTERNATIVE: 改编版, SPIN_OFF: 衍生作品
                # ADAPTATION: 原作改编, SOURCE: 原作
                # SUMMARY: 总集篇, CHARACTER: 角色相关, OTHER: 其他（包括演唱会等）
                # COMPILATION: 合集
                # 注意：不再过滤关系类型，获取所有相关条目
                # 让调用方决定如何处理不同类型
                
                # 跳过非动画类型（如 MANGA, NOVEL）
                node_format = node.get("format")
                if node_format and node_format in ["MANGA", "NOVEL", "ONE_SHOT"]:
                    continue
                
                entry = AniListMedia(
                    id=node["id"],
                    title_romaji=node.get("title", {}).get("romaji"),
                    title_english=node.get("title", {}).get("english"),
                    title_native=node.get("title", {}).get("native"),
                    title_chinese=extract_chinese(node.get("synonyms")),
                    year=node.get("seasonYear"),
                    format=node.get("format"),
                    episodes=node.get("episodes"),
                    status=node.get("status"),
                )
                results.append(entry)
            
            # 按年份和格式排序
            def sort_key(m):
                format_order = {"TV": 0, "OVA": 1, "MOVIE": 2, "SPECIAL": 3, "ONA": 4}
                return (m.year or 9999, format_order.get(m.format, 99))
            
            results.sort(key=sort_key)
            
            return results
            
        except Exception as e:
            print(f"获取系列信息失败: {e}")
            return []
    
    def identify_series_structure(self, query: str) -> Dict[str, Any]:
        """
        识别系列结构 - 搜索并展示系列的所有条目
        
        Args:
            query: 搜索关键词（如"K-ON"）
            
        Returns:
            Dict包含:
            - main: 主条目（最早的TV动画）
            - entries: 所有条目列表
            - structure: 格式化的系列结构说明
        """
        # 先搜索
        search_results = self.search_anime(query, limit=5)
        if not search_results:
            return {"main": None, "entries": [], "structure": "未找到结果"}
        
        # 找到主条目（优先TV格式）
        main = None
        for r in search_results:
            if r.format == "TV":
                main = r
                break
        if not main:
            main = search_results[0]
        
        # 获取系列关系
        entries = self.get_series_entries(main.id)
        
        # 生成结构说明
        structure = f"## 📺 {main.title_romaji or main.title_english} 系列\n\n"
        
        # 按格式分组
        tv_entries = [e for e in entries if e.format == "TV"]
        movie_entries = [e for e in entries if e.format == "MOVIE"]
        ova_entries = [e for e in entries if e.format in ["OVA", "ONA"]]
        special_entries = [e for e in entries if e.format == "SPECIAL"]
        
        if tv_entries:
            structure += "### TV 动画\n\n"
            structure += "| 季数 | 标题 | 集数 | 年份 |\n"
            structure += "|------|------|------|------|\n"
            for i, e in enumerate(tv_entries, 1):
                title = e.title_romaji or e.title_english or ""
                structure += f"| 第{i}季 | {title} | {e.episodes or '?'}集 | {e.year or '?'} |\n"
            structure += "\n"
        
        if movie_entries:
            structure += "### 剧场版\n\n"
            for e in movie_entries:
                title = e.title_romaji or e.title_english or ""
                structure += f"- {title} ({e.year or '?'})\n"
            structure += "\n"
        
        if ova_entries:
            structure += "### OVA/ONA\n\n"
            for e in ova_entries:
                title = e.title_romaji or e.title_english or ""
                structure += f"- {title} ({e.episodes or '?'}集, {e.year or '?'})\n"
            structure += "\n"
        
        return {
            "main": main,
            "entries": entries,
            "tv_entries": tv_entries,
            "structure": structure
        }


# 全局服务实例
_anilist_service: Optional[AniListService] = None


def get_anilist_service() -> AniListService:
    """获取AniList服务单例"""
    global _anilist_service
    if _anilist_service is None:
        _anilist_service = AniListService()
    return _anilist_service

