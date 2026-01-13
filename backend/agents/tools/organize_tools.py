"""
传统整理工具

🔥 核心设计（见 docs/CONTEXT.md）：
- organize_files：整理文件（合并 TV + 电影）

数据来源：
- state.classifications（由 analyze_and_classify 写入）

输出路径格式（Infuse 兼容）：
- TV: /root_path/剧集/子分类/系列名 (年)/Season XX/系列名 - SXX.EXX.扩展名
- 电影: /root_path/电影/子分类/电影名 (年)/电影名 (年).扩展名

子分类：
- 根据 TMDB Genres 自动判断（动漫/纪录片/音乐/综艺/默认）

🔥 新架构（2026-01-08）：
- 使用 InjectedState 访问 State
- 返回通用 ToolResponse JSON：{"message": "...", "state_update": {...}}
- 使用 services.py 管理服务实例
"""

import os
import logging
from typing import Dict, Any, List, Annotated
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from backend.agents.state import MediaAgentState
from backend.agents.services import get_storage_service
from backend.agents.tool_response import make_tool_response
from backend.services.tmdb_service import get_tmdb_service
from backend.utils.naming import (
    format_episode_name,
    format_movie_name,
    format_series_folder,
    format_season_folder,
    format_movie_folder,
)
from backend.agents.models import (
    MediaType, SubCategory, determine_subcategory, get_subcategory_name, SubtitleFile,
    Classification, ClassifiedFile
)
from backend.utils.path_utils import get_target_path

logger = logging.getLogger(__name__)


# 🔥 字幕语言优先级（用于选择默认字幕）
SUBTITLE_LANGUAGE_PRIORITY = [
    'chs', 'sc', 'chsjp', 'scjp',  # 简中优先
    'cht', 'tc', 'chtjp', 'tcjp',  # 繁中次之
    'eng', 'en',                   # 英文
    'jpn', 'jap', 'jp',            # 日文
    'und',                         # 未知
]


def _get_language_priority(lang: str) -> int:
    """获取语言优先级（数字越小优先级越高）"""
    lang_lower = lang.lower() if lang else 'und'
    try:
        return SUBTITLE_LANGUAGE_PRIORITY.index(lang_lower)
    except ValueError:
        return 999  # 未知语言放最后


def _select_default_subtitle(subtitles: list) -> SubtitleFile:
    """根据优先级选择默认字幕
    
    Args:
        subtitles: 字幕文件列表
    
    Returns:
        优先级最高的字幕
    """
    if not subtitles:
        return None
    
    return min(subtitles, key=lambda s: _get_language_priority(s.language))


def _format_subtitle_name(title: str, season: int, episode: int, sub: SubtitleFile, is_default: bool = False) -> str:
    """格式化字幕文件名 (TV)
    
    格式: 系列名.Sxx.Exx.语言.扩展名（与视频文件 format_episode_name 一致）
    例如: SeriesA.S01.E01.chs.srt
    
    Args:
        title: 系列名
        season: 季号
        episode: 集号
        sub: 字幕文件
        is_default: 是否为默认字幕（不带语言标识）
    """
    from backend.utils.naming import sanitize_filename
    clean_title = sanitize_filename(title)
    ext = os.path.splitext(sub.name)[1].lower()  # .srt, .ass, .ssa
    
    if is_default:
        # 🔧 与 format_episode_name 格式一致：系列名.Sxx.Exx.ext
        return f"{clean_title}.S{season:02d}.E{episode:02d}{ext}"
    else:
        lang = sub.language or "und"
        # 🔧 与 format_episode_name 格式一致：系列名.Sxx.Exx.lang.ext
        return f"{clean_title}.S{season:02d}.E{episode:02d}.{lang}{ext}"


def _format_movie_subtitle_name(title: str, year: int, sub: SubtitleFile, is_default: bool = False) -> str:
    """格式化字幕文件名 (电影)
    
    格式: 电影名.年份.语言.扩展名（与视频文件 format_movie_name 一致）
    例如: MovieA.2011.chs.srt
    
    Args:
        title: 电影名
        year: 年份
        sub: 字幕文件
        is_default: 是否为默认字幕（不带语言标识）
    """
    from backend.utils.naming import sanitize_filename
    clean_title = sanitize_filename(title)
    clean_title = clean_title.replace(' ', '.')  # 与 format_movie_name 一致
    ext = os.path.splitext(sub.name)[1].lower()
    
    if is_default:
        # 🔧 与 format_movie_name 格式一致：电影名.年份.ext
        if year:
            return f"{clean_title}.{year}{ext}"
        return f"{clean_title}{ext}"
    else:
        lang = sub.language or "und"
        # 🔧 与 format_movie_name 格式一致：电影名.年份.lang.ext
        if year:
            return f"{clean_title}.{year}.{lang}{ext}"
        return f"{clean_title}.{lang}{ext}"


def _parse_classifications(classifications_data: List[Dict[str, Any]]) -> Dict[int, Classification]:
    """从 State 中解析 classifications 数据为 Pydantic 模型"""
    result = {}
    for cls_dict in classifications_data:
        tmdb_id = cls_dict.get("tmdb_id")
        if tmdb_id:
            # 解析 seasons
            seasons = {}
            for season_num, files_data in cls_dict.get("seasons", {}).items():
                season_files = []
                for f in files_data:
                    subtitles = [SubtitleFile(**s) for s in f.get("subtitles", [])]
                    season_files.append(ClassifiedFile(
                        path=f["path"],
                        name=f["name"],
                        episode=f.get("episode", 0),
                        season=f.get("season", 0),
                        subtitles=subtitles
                    ))
                seasons[int(season_num)] = season_files
            
            # 解析 files (for movies)
            files = []
            for f in cls_dict.get("files", []):
                subtitles = [SubtitleFile(**s) for s in f.get("subtitles", [])]
                files.append(ClassifiedFile(
                    path=f["path"],
                    name=f["name"],
                    episode=f.get("episode", 0),
                    season=f.get("season", 0),
                    subtitles=subtitles
                ))
            
            result[tmdb_id] = Classification(
                tmdb_id=tmdb_id,
                name=cls_dict.get("name", ""),
                type=MediaType(cls_dict.get("type", "tv")),
                year=cls_dict.get("year"),
                genres=cls_dict.get("genres", []),
                sub_category=SubCategory(cls_dict.get("sub_category", "default")),
                seasons=seasons,
                files=files
            )
    return result


@tool
def organize_files(
    naming_language: str = "",
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    🔥 整理媒体文件（移动模式）
    
    将分类后的文件**移动**到目标目录，按 Infuse 规范命名。
    支持自动子分类：根据 TMDB Genres 自动归类到 动漫/纪录片/音乐/综艺/默认。
    
    ⚠️ 注意：此操作会移动原文件，不保留原文件！
    
    前置条件：
    1. 已使用 analyze_and_classify 分类文件
    2. 已使用 connect_webdav 连接存储（设置 target_path）
    
    路径生成方式：
    使用 storage_config.target_path 作为根路径，自动根据子分类生成完整路径
    例如：target_path="/kuake/整理好" + Animation → "/kuake/整理好/剧集/动漫/..."
    
    Args:
        naming_language: 命名语言（zh/en/both），留空则使用 user_config.naming_language
    
    Returns:
        ToolResponse JSON
    """
    # 从 State 读取数据
    storage_config = state.get("storage_config", {}) if state else {}
    user_config = state.get("user_config", {}) if state else {}
    classifications_data = state.get("classifications", []) if state else []
    
    # 解析 classifications
    classifications = _parse_classifications(classifications_data)
    
    if not classifications:
        return make_tool_response("❌ 请先使用 analyze_and_classify 分类文件")
    
    # 获取服务实例
    service = get_storage_service(state)
    
    if not service:
        return make_tool_response("❌ 请先使用 connect_webdav 连接存储")
    
    # 使用 storage_config.target_path 作为根路径
    target_path = storage_config.get('target_path', '') if storage_config else ''
    
    if not target_path:
        return make_tool_response("❌ 请在 connect_webdav 时设置 target_path 参数")
    
    # 使用 user_config 中的配置（如果未传参）
    effective_language = naming_language or user_config.get("naming_language") or "zh"
    
    tmdb = get_tmdb_service()
    
    output = "## 📁 整理文件\n\n"
    output += f"📂 输出路径: `{target_path}` (自动子分类)\n"
    output += f"- 模式: **移动** (原文件将被移走)\n"
    output += f"- 命名语言: {effective_language}\n\n"
    
    total_success = 0
    total_error = 0
    
    # 遍历所有分类的系列（使用 Pydantic 模型）
    for tmdb_id, cls in classifications.items():
        series_name = cls.name
        series_type = cls.type  # MediaType.TV or MediaType.MOVIE
        year = cls.year
        genres = cls.genres
        
        # 使用已确定的子分类（analyze_and_classify 已设置）
        sub_category = cls.sub_category
        
        # 获取 TMDB 详情
        if series_type == MediaType.TV:
            tmdb_info = tmdb.get_tv_details(tmdb_id)
        else:
            tmdb_info = tmdb.get_movie_details(tmdb_id)
        
        if tmdb_info:
            if effective_language == "en":
                title = tmdb_info.title or tmdb_info.title_zh or series_name
            elif effective_language == "both":
                title_zh = tmdb_info.title_zh or tmdb_info.title
                title_en = tmdb_info.title or tmdb_info.title_zh
                title = f"{title_zh} - {title_en}" if title_zh != title_en else title_zh
            else:
                title = tmdb_info.title_zh or tmdb_info.title or series_name
            year = tmdb_info.year or year
            # 如果 classification 没有 genres，从 TMDB 获取
            if not genres and tmdb_info.genres:
                genres = tmdb_info.genres
                sub_category = determine_subcategory(genres)
        else:
            title = series_name
        
        # 获取子分类显示名称
        sub_name = get_subcategory_name(sub_category, series_type, effective_language)
        
        output += f"### 📺 {title} (TMDB:{tmdb_id}) - {sub_name}\n\n"
        
        if series_type == MediaType.TV:
            # TV 系列：按季整理
            series_folder = format_series_folder(title, year)
            
            # 使用 target_path + 自动子分类
            category_path = get_target_path(target_path, MediaType.TV, sub_category, effective_language)
            series_path = f"{category_path}/{series_folder}"
            
            # 创建系列目录
            try:
                service.create_directory(series_path)
            except Exception:
                pass
            
            for season_num in sorted(cls.seasons.keys()):
                files = cls.seasons[season_num]  # List[ClassifiedFile]
                season_folder = format_season_folder(season_num)
                season_path = f"{series_path}/{season_folder}"
                
                # 创建季目录
                try:
                    service.create_directory(season_path)
                except Exception:
                    pass
                
                season_success = 0
                season_error = 0
                
                season_subtitle_success = 0
                season_subtitle_error = 0
                
                for cf in files:
                    episode = cf.episode
                    if episode <= 0:
                        continue
                    
                    # 视频文件
                    ext = os.path.splitext(cf.name)[1]
                    new_name = format_episode_name(title, season_num, episode, ext)
                    new_path = f"{season_path}/{new_name}"
                    
                    try:
                        service.move_file(cf.path, new_path)
                        season_success += 1
                    except Exception as e:
                        logger.error(f"整理失败 {cf.path}: {e}")
                        season_error += 1
                    
                    # 🆕 处理关联的字幕文件
                    if cf.subtitles:
                        # 🔥 先复制默认字幕（根据优先级选择）
                        default_sub = _select_default_subtitle(cf.subtitles)
                        if default_sub:
                            default_sub_name = _format_subtitle_name(title, season_num, episode, default_sub, is_default=True)
                            default_sub_path = f"{season_path}/{default_sub_name}"
                            try:
                                service.copy_file(default_sub.path, default_sub_path)
                                season_subtitle_success += 1
                            except Exception as e:
                                logger.error(f"默认字幕复制失败 {default_sub.path}: {e}")
                                season_subtitle_error += 1
                        
                        # 🔥 再移动所有带语言标识的字幕
                        for sub in cf.subtitles:
                            sub_new_name = _format_subtitle_name(title, season_num, episode, sub, is_default=False)
                            sub_new_path = f"{season_path}/{sub_new_name}"
                            
                            try:
                                service.move_file(sub.path, sub_new_path)
                                season_subtitle_success += 1
                            except Exception as e:
                                logger.error(f"字幕整理失败 {sub.path}: {e}")
                                season_subtitle_error += 1
                
                output += f"- S{season_num:02d}: {season_success} 成功"
                if season_subtitle_success > 0:
                    output += f" (+{season_subtitle_success} 字幕)"
                if season_error > 0:
                    output += f", {season_error} 失败"
                if season_subtitle_error > 0:
                    output += f" ({season_subtitle_error} 字幕失败)"
                output += "\n"
                
                total_success += season_success
                total_error += season_error
        
        else:
            # 电影：直接整理
            files = cls.files  # List[ClassifiedFile]
            movie_folder = format_movie_folder(title, year)
            
            # 使用 target_path + 自动子分类
            category_path = get_target_path(target_path, MediaType.MOVIE, sub_category, effective_language)
            movie_full_path = f"{category_path}/{movie_folder}"
            
            try:
                service.create_directory(movie_full_path)
            except Exception:
                pass
            
            movie_subtitle_success = 0
            movie_subtitle_error = 0
            
            for cf in files:
                # 视频文件
                ext = os.path.splitext(cf.name)[1]
                new_name = format_movie_name(title, year, ext)
                new_path = f"{movie_full_path}/{new_name}"
                
                try:
                    service.move_file(cf.path, new_path)
                    total_success += 1
                except Exception as e:
                    logger.error(f"整理失败 {cf.path}: {e}")
                    total_error += 1
                
                # 🆕 处理关联的字幕文件
                if cf.subtitles:
                    # 🔥 先复制默认字幕（根据优先级选择）
                    default_sub = _select_default_subtitle(cf.subtitles)
                    if default_sub:
                        default_sub_name = _format_movie_subtitle_name(title, year, default_sub, is_default=True)
                        default_sub_path = f"{movie_full_path}/{default_sub_name}"
                        try:
                            service.copy_file(default_sub.path, default_sub_path)
                            movie_subtitle_success += 1
                        except Exception as e:
                            logger.error(f"默认字幕复制失败 {default_sub.path}: {e}")
                            movie_subtitle_error += 1
                    
                    # 🔥 再移动所有带语言标识的字幕
                    for sub in cf.subtitles:
                        sub_new_name = _format_movie_subtitle_name(title, year, sub, is_default=False)
                        sub_new_path = f"{movie_full_path}/{sub_new_name}"
                        
                        try:
                            service.move_file(sub.path, sub_new_path)
                            movie_subtitle_success += 1
                        except Exception as e:
                            logger.error(f"字幕整理失败 {sub.path}: {e}")
                            movie_subtitle_error += 1
            
            output += f"- {len(files)} 个文件"
            if movie_subtitle_success > 0:
                output += f" (+{movie_subtitle_success} 字幕)"
            if movie_subtitle_error > 0:
                output += f" ({movie_subtitle_error} 字幕失败)"
            output += "\n"
        
        output += "\n"
    
    output += f"---\n**总计**\n"
    output += f"- 成功: {total_success}\n"
    if total_error > 0:
        output += f"- 失败: {total_error}\n"
    
    output += "\n**注意**: 使用的是移动模式，原文件已被移走。\n"
    
    # 返回 ToolResponse JSON（清空分类数据）
    return make_tool_response(
        output,
        state_update={
            "classifications": [],  # 清空分类数据
            "organize_progress": {
                "total_success": total_success,
                "total_error": total_error,
                "status": "completed",
            }
        }
    )
