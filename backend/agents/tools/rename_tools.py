"""
重命名相关工具

提供文件重命名预览和执行功能

🔥 新架构（2026-01-08）：
- 使用 InjectedState 访问 State
- 返回通用 ToolResponse JSON：{"message": "...", "state_update": {...}}
- 使用 services.py 管理服务实例
"""

import os
from typing import Annotated
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from backend.agents.state import MediaAgentState
from backend.agents.services import get_storage_service
from backend.agents.tool_response import make_tool_response
from backend.services.tmdb_service import get_tmdb_service
from backend.utils.infuse_formatter import InfuseFormatter


@tool
def preview_rename(
    file_path: str,
    tmdb_id: int,
    media_type: str = "movie",
    season: int = 1,
    episode: int = 1,
) -> str:
    """
    预览重命名结果（不实际执行）
    
    Args:
        file_path: 原文件路径
        tmdb_id: TMDB ID
        media_type: 媒体类型，"movie" 或 "tv"
        season: 季数（仅电视剧需要）
        episode: 集数（仅电视剧需要）
    
    Returns:
        ToolResponse JSON
    """
    try:
        tmdb = get_tmdb_service()
        formatter = InfuseFormatter()
        
        # 获取详细信息
        if media_type == "tv":
            info = tmdb.get_tv_details(tmdb_id)
        else:
            info = tmdb.get_movie_details(tmdb_id)
        
        if not info:
            return make_tool_response(f"❌ 无法获取 TMDB ID {tmdb_id} 的详细信息")
        
        # 获取原文件扩展名
        _, ext = os.path.splitext(file_path)
        ext = ext or ".mkv"
        
        # 生成Infuse规范的文件名
        if media_type == "tv":
            formatted = formatter.format_tv_episode(
                series_title=info.title,
                season=season,
                episode=episode,
                extension=ext,
            )
            new_name = formatted.filename
        else:
            formatted = formatter.format_movie(
                title=info.title,
                year=info.year,
                extension=ext,
            )
            new_name = formatted.filename
        
        # 生成新路径
        old_dir = os.path.dirname(file_path)
        new_path = os.path.join(old_dir, new_name) if old_dir else new_name
        
        result = f"📝 重命名预览：\n\n"
        result += f"**原文件**: {file_path}\n"
        result += f"**新文件**: {new_path}\n\n"
        result += f"**匹配信息**:\n"
        result += f"• 标题: {info.title}\n"
        if info.year:
            result += f"• 年份: {info.year}\n"
        if media_type == "tv":
            result += f"• 季/集: S{season:02d}E{episode:02d}\n"
        result += f"• TMDB ID: {tmdb_id}\n"
        
        result += "\n确认后使用 execute_rename 执行重命名"
        
        return make_tool_response(result)
        
    except Exception as e:
        return make_tool_response(f"❌ 预览失败: {str(e)}")


@tool
def execute_rename(
    file_path: str,
    new_name: str,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    执行重命名操作
    
    Args:
        file_path: 原文件完整路径
        new_name: 新文件名（不含路径）
    
    Returns:
        ToolResponse JSON
    """
    # 获取服务实例
    service = get_storage_service(state)
    
    if not service:
        return make_tool_response("❌ 请先使用 connect_webdav 连接到存储服务器")
    
    try:
        # 构建新路径
        old_dir = os.path.dirname(file_path)
        new_path = f"{old_dir}/{new_name}" if old_dir else new_name
        
        # 执行重命名
        success = service.rename(file_path, new_path)
        
        if success:
            return make_tool_response(f"✅ 重命名成功！\n\n`{file_path}`\n→ `{new_path}`")
        else:
            return make_tool_response("❌ 重命名失败")
        
    except Exception as e:
        return make_tool_response(f"❌ 重命名失败: {str(e)}")
