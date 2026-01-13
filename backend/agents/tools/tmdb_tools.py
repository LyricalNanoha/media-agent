"""
TMDB 知识工具

提供 TMDB 搜索和查询功能，让 Agent 能够理解和使用 TMDB 数据

🔥 新架构（2026-01-08）：
- 返回通用 JSON 格式：{"message": "...", "state_update": {...}}
- TMDB 工具不需要访问 State，只是查询外部 API
"""

import logging
from langchain.tools import tool

from backend.services.tmdb_service import get_tmdb_service
from backend.agents.tool_response import make_tool_response

logger = logging.getLogger(__name__)


@tool
def search_tmdb(query: str, media_type: str = "tv", language: str = "zh-CN") -> str:
    """
    搜索 TMDB 媒体（TV 系列或电影）

    使用场景：
    - 用户提供了剧名/电影名，需要查找对应的 TMDB 信息
    - 验证文件对应的影视作品
    - 查找可能的续作/相关系列

    Args:
        query: 搜索关键词（动漫名称、电影名称等）
        media_type: 媒体类型，"tv" 表示电视剧/动漫，"movie" 表示电影
        language: 语言偏好，"zh-CN" 中文，"en-US" 英文

    Returns:
        JSON: {"message": "搜索结果", "state_update": {}}
    """
    try:
        tmdb = get_tmdb_service()

        if media_type == "movie":
            results = tmdb.search_movie_multilang(query, target_language=language, limit=10)
            if not results:
                return make_tool_response(
                    f"❌ 未找到与 '{query}' 相关的电影\n\n建议：\n- 尝试使用不同的搜索词\n- 尝试英文名或原名"
                )

            output = f"## 🎬 TMDB 电影搜索: \"{query}\"\n\n"
            output += "| # | 标题 | 原名 | 年份 | TMDB ID |\n"
            output += "|---|------|------|------|--------|\n"

            for i, m in enumerate(results, 1):
                title = m.title or m.title_zh or "未知"
                original = m.original_title or ""
                year = m.year or "?"
                tmdb_id = m.tmdb_id

                output += f"| {i} | **{title}** | {original} | {year} | `{tmdb_id}` |\n"

            return make_tool_response(output)

        else:  # tv
            results = tmdb.search_tv_multilang(query, target_language=language, limit=5)
            if not results:
                return make_tool_response(
                    f"❌ 未找到与 '{query}' 相关的 TV 系列\n\n建议：\n- 尝试使用不同的搜索词\n- 尝试英文名或原名"
                )

            output = f"## 📺 TMDB TV 搜索: \"{query}\"\n\n"
            output += "| # | 标题 | 原名 | 年份 | 季数 | 集数 | TMDB ID |\n"
            output += "|---|------|------|------|------|------|--------|\n"

            for i, r in enumerate(results, 1):
                title = r.title or r.title_zh or "未知"
                original = r.original_title or ""
                year = r.year or "?"
                seasons = r.seasons_count or "?"
                episodes = r.episodes_count or "?"
                tmdb_id = r.tmdb_id

                output += f"| {i} | **{title}** | {original} | {year} | {seasons} | {episodes} | `{tmdb_id}` |\n"

            output += "\n**💡 提示**：使用 `get_tmdb_details(tmdb_id, media_type=\"tv\")` 获取详细的季信息\n"

            return make_tool_response(output)

    except Exception as e:
        logger.error(f"TMDB 搜索失败: {e}")
        return make_tool_response(f"❌ TMDB 搜索失败: {str(e)}")


@tool
def get_tmdb_details(tmdb_id: int, media_type: str = "tv") -> str:
    """
    获取 TMDB 媒体的详细信息

    对于 TV 系列：返回每一季的集数和累计集数范围（用于文件分类）
    对于电影：返回电影的详细信息

    Args:
        tmdb_id: TMDB ID（从 search_tmdb 获取）
        media_type: 媒体类型，"tv" 或 "movie"

    Returns:
        JSON: {"message": "详细信息", "state_update": {}}
    """
    try:
        tmdb = get_tmdb_service()

        if media_type == "movie":
            details = tmdb.get_movie_details(tmdb_id)
            if not details:
                return make_tool_response(f"❌ 未找到 TMDB ID: {tmdb_id} 的电影")

            output = f"## 🎬 {details.title}\n\n"
            output += f"| 属性 | 值 |\n"
            output += f"|------|----|\n"
            output += f"| TMDB ID | `{tmdb_id}` |\n"
            output += f"| 原名 | {details.original_title or '-'} |\n"
            output += f"| 年份 | {details.year or '-'} |\n"

            return make_tool_response(output)

        else:  # tv
            details = tmdb.get_tv_details(tmdb_id)
            if not details:
                return make_tool_response(f"❌ 未找到 TMDB ID: {tmdb_id} 的 TV 系列")

            # 使用 TMDBService 获取每季详细信息
            seasons = tmdb.get_tv_all_seasons(tmdb_id)

            # 构建输出
            title = details.title_zh or details.title
            original_title = details.original_title or ""
            first_air = str(details.year) if details.year else "?"
            total_episodes = details.episodes_count or 0
            total_seasons = details.seasons_count or 0

            output = f"## 📺 {title}\n\n"
            output += f"| 属性 | 值 |\n"
            output += f"|------|----|\n"
            output += f"| TMDB ID | `{tmdb_id}` |\n"
            output += f"| 原名 | {original_title} |\n"
            output += f"| 首播年份 | {first_air} |\n"
            output += f"| 总季数 | {total_seasons} |\n"
            output += f"| 总集数 | **{total_episodes}** |\n"
            output += "\n"

            # 每季详情
            output += "### 📋 各季详情\n\n"
            output += "| 季 | 名称 | 集数 | 资源编号范围 | 输出文件名 |\n"
            output += "|---|------|-----|------------|----------|\n"
            
            total_global = 0
            for s in seasons:
                s_num = s.get("season_number", 0)
                s_name = s.get("name", f"Season {s_num}")
                s_eps = s.get("episode_count", 0)
                # TMDB 实际编号（用于输出文件名）
                ep_start = s.get("ep_start", 1)
                ep_end = s.get("ep_end", s_eps)
                # 累计编号（用于匹配资源文件）
                ep_start_global = s.get("ep_start_global", total_global + 1)
                ep_end_global = s.get("ep_end_global", total_global + s_eps)
                total_global = ep_end_global

                # 更清晰的输出：资源编号 → 输出文件名
                output += f"| S{s_num:02d} | {s_name[:15]} | {s_eps} | EP{ep_start_global:03d}-EP{ep_end_global:03d} | S{s_num:02d}E{ep_start:02d}-E{ep_end:02d} |\n"

            output += f"\n**总计: {total_global} 集**\n"

            # 🆕 获取 Season 0 (特别篇) 信息
            season0_episodes = tmdb.get_season_0_episodes(tmdb_id)
            if season0_episodes:
                output += "\n### 🎬 Season 0 (特别篇)\n\n"
                output += "**用于匹配 OVA、SP、导演剪辑版等特殊内容**\n\n"
                output += "| 集 | 名称 | 描述 |\n"
                output += "|---|------|------|\n"
                for ep in season0_episodes:
                    ep_num = ep.get('episode_number', 0)
                    ep_name = ep.get('name', '')[:30]  # 截断过长的名称
                    ep_overview = ep.get('overview', '')[:30]  # 截断过长的描述
                    if ep_overview:
                        output += f"| S00E{ep_num:02d} | {ep_name} | {ep_overview}... |\n"
                    else:
                        output += f"| S00E{ep_num:02d} | {ep_name} | - |\n"
                output += "\n⚠️ **特殊版本匹配**：如果文件名包含 `Director's Cut`、`OVA`、`SP` 等标识，请检查是否对应 Season 0 的某一集。\n"

            # 🔥 添加转换示例，避免用户误解
            output += "\n### 📌 编号转换示例\n\n"
            if len(seasons) >= 2:
                s2 = seasons[1]
                s2_num = s2.get("season_number", 2)
                s2_global_start = s2.get("ep_start_global", 1)
                output += f"| 资源文件 | 转换为 |\n"
                output += f"|---------|-------|\n"
                output += f"| `[{s2_global_start:03d}].mkv` | **S{s2_num:02d}E01.mkv** |\n"
                output += f"| `EP{s2_global_start:03d}.mkv` | **S{s2_num:02d}E01.mkv** |\n"
                output += f"\n⚠️ **注意**：资源编号 EP{s2_global_start:03d} 会被转换为 S{s2_num:02d}E01（不是 S{s2_num:02d}E{s2_global_start:02d}）\n"

            return make_tool_response(output)

    except Exception as e:
        logger.error(f"获取 TMDB 详情失败: {e}")
        return make_tool_response(f"❌ 获取详情失败: {str(e)}")
