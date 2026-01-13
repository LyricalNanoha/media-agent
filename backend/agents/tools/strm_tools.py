"""
STRM 文件生成工具

🔥 核心设计（见 docs/CONTEXT.md）：
- connect_strm_target：连接 STRM 目标存储
- generate_strm：生成 STRM 文件（合并 TV + 电影）

数据来源：
- state.classifications（由 analyze_and_classify 写入）

输出路径格式（Infuse 兼容）：
- TV: /root_path/剧集/子分类/系列名 (年)/Season XX/系列名.SXX.EXX.strm
- 电影: /root_path/电影/子分类/电影名 (年)/电影名 (年).strm

子分类：
- 根据 TMDB Genres 自动判断（动漫/纪录片/音乐/综艺/默认）

性能优化：
- 使用服务层的 upload_files_batch_async 实现 16 协程并发上传
- 🆕 字幕处理：下载和上传封装为单个并发任务，避免先全部下载再上传

🔥 新架构（2026-01-08）：
- 使用 InjectedState 访问 State
- 返回通用 ToolResponse JSON：{"message": "...", "state_update": {...}}
- 使用 services.py 管理服务实例
"""

import os
import io
import time
import zipfile
import traceback

from backend.agents.state import MediaAgentState
import logging
import asyncio
from typing import Dict, Any, List, Annotated, Optional, Tuple
from urllib.parse import quote
from dataclasses import dataclass
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from backend.agents.state import MediaAgentState
from backend.agents.services import get_storage_service, get_strm_target_service, cache_strm_service
from backend.agents.tool_response import make_tool_response
from backend.services.tmdb_service import get_tmdb_service
from backend.services.storage_factory import create_storage_service_sync
from backend.utils.naming import (
    format_strm_episode_name,
    format_strm_movie_name,
    format_series_folder,
    format_season_folder,
    format_movie_folder,
)
from backend.agents.models import (
    MediaType, SubCategory, determine_subcategory, SubtitleFile,
    Classification, ClassifiedFile
)
from backend.utils.path_utils import get_target_path


# 🔥 字幕语言优先级（用于选择默认字幕）
SUBTITLE_LANGUAGE_PRIORITY = [
    'chs', 'sc', 'chsjp', 'scjp',  # 简中优先
    'cht', 'tc', 'chtjp', 'tcjp',  # 繁中次之
    'eng', 'en',                   # 英文
    'jpn', 'jap', 'jp',            # 日文
    'und',                         # 未知
]

# 🆕 字幕并发处理配置
SUBTITLE_DOWNLOAD_CONCURRENCY = 8  # 下载并发数
SUBTITLE_UPLOAD_CONCURRENCY = 16   # 上传并发数


@dataclass
class SubtitleTask:
    """字幕处理任务"""
    source_path: str      # 源文件路径（从源存储读取）
    target_path: str      # 目标文件路径（写入目标存储）
    is_default: bool      # 是否为默认字幕


def _get_language_priority(lang: str) -> int:
    """获取语言优先级（数字越小优先级越高）"""
    lang_lower = lang.lower() if lang else 'und'
    try:
        return SUBTITLE_LANGUAGE_PRIORITY.index(lang_lower)
    except ValueError:
        return 999  # 未知语言放最后


def _format_subtitle_name(title: str, season: int, episode: int, sub: SubtitleFile, is_default: bool = False) -> str:
    """格式化字幕文件名
    
    格式: 系列名.Sxx.Exx.语言.扩展名（与 STRM 文件名格式一致）
    例如: SeriesA.S01.E01.chs.srt
    
    Args:
        title: 系列名
        season: 季号
        episode: 集号
        sub: 字幕文件
        is_default: 是否为默认字幕（不带语言标识）
    """
    # 从原始文件名获取扩展名
    ext = os.path.splitext(sub.name)[1].lower()  # .srt, .ass, .ssa
    
    if is_default:
        # 🆕 默认字幕不带语言标识，格式与 STRM 一致：S01.E01
        return f"{title}.S{season:02d}.E{episode:02d}{ext}"
    else:
        lang = sub.language or "und"
        # 🔧 格式与 STRM 一致：S01.E01.lang
        return f"{title}.S{season:02d}.E{episode:02d}.{lang}{ext}"


def _format_movie_subtitle_name(title: str, year: int, sub: SubtitleFile, is_default: bool = False) -> str:
    """格式化电影字幕文件名
    
    格式: 电影名.年份.语言.扩展名（与 STRM 文件 format_strm_movie_name 一致）
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
        # 🔧 与 format_strm_movie_name 格式一致：电影名.年份.ext
        if year:
            return f"{clean_title}.{year}{ext}"
        return f"{clean_title}{ext}"
    else:
        lang = sub.language or "und"
        # 🔧 与 format_strm_movie_name 格式一致：电影名.年份.lang.ext
        if year:
            return f"{clean_title}.{year}.{lang}{ext}"
        return f"{clean_title}.{lang}{ext}"


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

logger = logging.getLogger(__name__)

# 并发上传配置
UPLOAD_CONCURRENCY = 16


# ============ 辅助函数 ============

def _build_play_url(base_url: str, file_path: str, storage_type: str) -> str:
    """构建播放 URL（根据存储类型）
    
    使用 JavaScript encodeURI 兼容的编码方式：
    - 不编码：A-Z a-z 0-9 - _ . ! ~ * ' ( ) ; / ? : @ & = + $ , #
    - 编码：[] 空格 中文 及其他特殊字符
    
    Args:
        base_url: 存储服务器地址
        file_path: 文件路径
        storage_type: 存储类型 ("alist" 或 "webdav")
    
    Returns:
        可播放的 URL
    """
    # 🔥 模拟 JavaScript encodeURI 行为
    # encodeURI 不编码的字符（除字母数字外）：- _ . ! ~ * ' ( ) ; / ? : @ & = + $ , #
    # 注意：[] 会被编码为 %5B%5D（这是正确的！播放器需要这样）
    ENCODE_URI_SAFE = "-_.!~*'();/?:@&=+$,#"
    encoded_path = quote(file_path, safe=ENCODE_URI_SAFE)
    base = base_url.rstrip('/')
    
    if storage_type == "alist":
        # Alist: 使用 /d/ 直接下载格式（高效，无需 API 调用）
        return f"{base}/d{encoded_path}"
    else:
        # WebDAV: 使用 /dav/ 格式（标准 WebDAV 路径）
        return f"{base}/dav{encoded_path}"


def _generate_strm_content(storage_config: Dict[str, Any], file_path: str) -> str:
    """生成 STRM 文件内容
    
    自动根据源存储类型生成正确的播放 URL
    从 storage_config 读取 url 和 type
    """
    base_url = storage_config.get('url', '')
    storage_type = storage_config.get('type', 'webdav')
    return _build_play_url(base_url, file_path, storage_type)


def _read_subtitle_content(service, sub_path: str) -> Optional[str]:
    """从源存储读取字幕文件内容
    
    Args:
        service: 源存储服务实例
        sub_path: 字幕文件路径
        
    Returns:
        字幕内容，如果失败返回 None
    """
    try:
        content = service.get_file_content(sub_path)
        if content:
            return content
        else:
            logger.warning(f"读取字幕失败: {sub_path}")
            return None
    except Exception as e:
        logger.warning(f"读取字幕异常 {sub_path}: {e}")
        return None


@dataclass
class SubtitleTaskResult:
    """字幕任务结果"""
    success: bool
    source_path: str
    target_path: str
    error: Optional[str] = None


async def _process_subtitle_task_async(
    task: SubtitleTask,
    source_service,
    target_service,
    semaphore: asyncio.Semaphore
) -> SubtitleTaskResult:
    """
    🆕 异步处理单个字幕任务（下载 + 上传作为一个原子操作）
    
    Args:
        task: 字幕任务
        source_service: 源存储服务
        target_service: 目标存储服务
        semaphore: 并发控制信号量
        
    Returns:
        SubtitleTaskResult 包含成功状态、路径和错误信息
    """
    async with semaphore:
        try:
            # 1. 异步下载字幕内容
            logger.debug(f"📥 开始下载字幕: {task.source_path}")
            content = await source_service.get_file_content_async(task.source_path)
            if not content:
                error_msg = "下载失败（返回空内容或HTTP错误）"
                logger.warning(f"❌ {error_msg}: {task.source_path} -> {task.target_path}")
                return SubtitleTaskResult(
                    success=False,
                    source_path=task.source_path,
                    target_path=task.target_path,
                    error=error_msg
                )
            
            logger.debug(f"📤 开始上传字幕: {task.target_path} (大小: {len(content)} bytes)")
            
            # 2. 立即上传到目标存储
            success = await target_service.put_file_content_async(task.target_path, content)
            if success:
                logger.debug(f"✅ 字幕处理成功: {task.source_path} -> {task.target_path}")
                return SubtitleTaskResult(
                    success=True,
                    source_path=task.source_path,
                    target_path=task.target_path
                )
            else:
                error_msg = "上传失败（API返回失败）"
                logger.warning(f"❌ {error_msg}: {task.source_path} -> {task.target_path}")
                return SubtitleTaskResult(
                    success=False,
                    source_path=task.source_path,
                    target_path=task.target_path,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 处理字幕异常 {task.source_path} -> {task.target_path}: {e}\n{traceback.format_exc()}")
            return SubtitleTaskResult(
                success=False,
                source_path=task.source_path,
                target_path=task.target_path,
                error=error_msg
            )


async def _process_subtitles_batch_async(
    tasks: List[SubtitleTask],
    source_service,
    target_service,
    concurrency: int = SUBTITLE_UPLOAD_CONCURRENCY
) -> Tuple[int, int, List[str], List[Dict[str, Any]]]:
    """
    🆕 批量并发处理字幕任务（下载+上传封装为单个任务）
    
    Args:
        tasks: 字幕任务列表
        source_service: 源存储服务
        target_service: 目标存储服务
        concurrency: 并发数
        
    Returns:
        (成功数, 失败数, 失败路径列表, 失败详情列表)
    """
    if not tasks:
        return (0, 0, [], [])
    
    semaphore = asyncio.Semaphore(concurrency)
    
    # 并发执行所有任务
    results = await asyncio.gather(
        *[_process_subtitle_task_async(task, source_service, target_service, semaphore) 
          for task in tasks],
        return_exceptions=True
    )
    
    success_count = 0
    error_count = 0
    failed_paths = []
    failed_details = []  # 🆕 详细失败信息
    
    for result in results:
        if isinstance(result, Exception):
            error_count += 1
            logger.error(f"字幕任务异常: {result}")
        elif isinstance(result, SubtitleTaskResult):
            if result.success:
                success_count += 1
            else:
                error_count += 1
                failed_paths.append(result.target_path)
                # 🆕 收集详细失败信息
                failed_details.append({
                    "source_path": result.source_path,
                    "target_path": result.target_path,
                    "type": "subtitle",
                    "error": result.error or "未知错误"
                })
        else:
            error_count += 1
    
    return (success_count, error_count, failed_paths, failed_details)


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


# ============ 工具函数 ============

@tool
def connect_strm_target(
    url: str,
    username: str,
    password: str,
    target_path: str = "/",
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    连接 STRM 目标存储
    
    这是 generate_strm 的前置步骤。连接后，generate_strm 会将文件上传到此存储。
    
    Args:
        url: 存储服务器地址（支持 Alist 和 WebDAV）
        username: 用户名
        password: 密码
        target_path: STRM 输出路径，例如 "/kuake/strm"
                     系统会自动在此路径下生成分类目录：剧集/动漫、电影/动漫 等
    
    🔥 注意：上传延迟由 user_config.upload_delay 控制
    
    Returns:
        ToolResponse JSON
    """
    try:
        # 创建服务实例
        service = create_storage_service_sync(
            url=url,
            username=username,
            password=password,
            base_path="/",  # 固定为根目录
        )
        
        # 🔥 立即验证连接（触发登录），确保服务已认证
        try:
            service.list_directory("/")
        except Exception as auth_error:
            return make_tool_response(
                f"❌ 连接失败: 认证错误 - {str(auth_error)}\n\n请检查用户名和密码是否正确。"
            )
        
        strm_target_config = {
            "url": url,
            "target_path": target_path.rstrip('/') if target_path else "/",
            "type": service.service_type,  # 使用实际检测的类型（alist 或 webdav）
            "username": username,
            "password": password,
            "connected": True,  # 标记已连接
        }
        
        # 🔥 缓存服务实例，确保后续工具可以复用
        cache_strm_service(strm_target_config, service)
        
        return make_tool_response(
            f"✅ 已连接 STRM 目标存储\n- URL: {url}\n- 输出路径: {target_path}",
            state_update={"strm_target_config": strm_target_config}
        )
        
    except Exception as e:
        return make_tool_response(f"❌ 连接失败: {e}")


@tool
def generate_strm(
    output_format: str = "webdav",
    naming_language: str = "",
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    🔥 生成 STRM 文件
    
    根据 classification 中的分类结果，为所有系列生成 STRM 文件。
    支持自动子分类：根据 TMDB Genres 自动归类到 动漫/纪录片/音乐/综艺/默认。
    使用 16 协程并发上传，大幅提升上传速度。
    
    🔥 Alist 播放地址自动从源存储配置读取，无需手动指定！
    
    前置条件：
    1. 已使用 connect_webdav 连接源存储
    2. 已使用 analyze_and_classify 分类文件
    3. 如果 output_format="webdav"，需要先 connect_strm_target（设置 target_path）
    
    路径生成方式：
    使用 strm_target_config.target_path 作为根路径，自动根据子分类生成完整路径
    例如：target_path="/kuake/strm" + Animation → "/kuake/strm/剧集/动漫/..."
    
    Args:
        output_format: 输出方式
            - "webdav": 上传到目标存储（需要先 connect_strm_target）
            - "zip": 生成 ZIP 文件下载
            - "list": 仅列出文件（不生成）
        naming_language: 命名语言（zh/en），留空则使用 user_config.naming_language
    
    Returns:
        ToolResponse JSON
    """
    # 从 State 读取数据
    storage_config = state.get("storage_config", {}) if state else {}
    strm_target_config = state.get("strm_target_config", {}) if state else {}
    user_config = state.get("user_config", {}) if state else {}
    classifications_data = state.get("classifications", []) if state else []
    
    # 解析 classifications
    classifications = _parse_classifications(classifications_data)
    
    if not classifications:
        return make_tool_response("❌ 请先使用 analyze_and_classify 分类文件")
    
    if output_format == "webdav" and not strm_target_config.get("connected"):
        return make_tool_response("❌ 请先使用 connect_strm_target 连接目标存储")
    
    # 🔥 检查是否已连接源存储（用于生成播放 URL）
    if not storage_config.get('url'):
        return make_tool_response("❌ 未连接源存储。请先使用 connect_webdav 连接存储服务器")
    
    # 🆕 获取源存储服务实例（用于读取字幕内容）
    source_service = get_storage_service(state)
    if not source_service:
        return make_tool_response("❌ 源存储服务未初始化。请先使用 connect_webdav 连接存储服务器")
    
    # 使用 strm_target_config.target_path 作为根路径
    target_path = strm_target_config.get('target_path', '/') if strm_target_config else '/'
    
    # 使用 user_config 中的配置（如果未传参）
    effective_language = naming_language or user_config.get("naming_language") or "zh"
    
    tmdb = get_tmdb_service()
    all_strm_files = []  # [(路径, 内容)]
    all_subtitle_tasks: List[SubtitleTask] = []  # 🆕 字幕任务列表（下载+上传封装为单个任务）
    
    output = "## 🎬 生成 STRM 文件\n\n"
    output += f"📂 输出路径: `{target_path}` (自动子分类)\n\n"
    
    # 遍历所有分类的系列（使用 Pydantic 模型）
    for tmdb_id, cls in classifications.items():
        series_name = cls.name
        series_type = cls.type  # MediaType.TV or MediaType.MOVIE
        year = cls.year
        genres = cls.genres  # TMDB Genres
        
        # 使用已确定的子分类（analyze_and_classify 已设置）
        sub_category = cls.sub_category
        
        # 获取 TMDB 详情（用于获取正确的标题）
        if series_type == MediaType.TV:
            tmdb_info = tmdb.get_tv_details(tmdb_id)
        else:
            tmdb_info = tmdb.get_movie_details(tmdb_id)
        
        if tmdb_info:
            if effective_language == "en":
                title = tmdb_info.title or tmdb_info.title_zh or series_name
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
        from backend.agents.models import get_subcategory_name
        sub_name = get_subcategory_name(sub_category, series_type, effective_language)
        
        output += f"### 📺 {title} (TMDB:{tmdb_id}) - {sub_name}\n\n"
        
        if series_type == MediaType.TV:
            # TV 系列：按季生成
            series_folder = format_series_folder(title, year)
            
            # 使用 target_path + 自动子分类
            category_path = get_target_path(target_path, MediaType.TV, sub_category, effective_language)
            base_folder = f"{category_path}/{series_folder}"
            
            total_subtitle_count = 0
            for season_num in sorted(cls.seasons.keys()):
                files = cls.seasons[season_num]  # List[ClassifiedFile]
                season_folder = format_season_folder(season_num)
                season_subtitle_count = 0
                
                for cf in files:
                    episode = cf.episode
                    if episode <= 0:
                        continue
                    
                    # 视频 STRM
                    strm_name = format_strm_episode_name(title, season_num, episode)
                    strm_path = f"{base_folder}/{season_folder}/{strm_name}"
                    strm_content = _generate_strm_content(storage_config, cf.path)
                    all_strm_files.append((strm_path, strm_content))
                    
                    # 🆕 收集字幕任务（不在此处读取内容）
                    if cf.subtitles:
                        # 🔥 先生成默认字幕任务（根据优先级选择）
                        default_sub = _select_default_subtitle(cf.subtitles)
                        if default_sub:
                            default_sub_name = _format_subtitle_name(title, season_num, episode, default_sub, is_default=True)
                            default_sub_path = f"{base_folder}/{season_folder}/{default_sub_name}"
                            all_subtitle_tasks.append(SubtitleTask(
                                source_path=default_sub.path,
                                target_path=default_sub_path,
                                is_default=True
                            ))
                            season_subtitle_count += 1
                        
                        # 🔥 再收集所有带语言标识的字幕任务
                        for sub in cf.subtitles:
                            sub_name = _format_subtitle_name(title, season_num, episode, sub, is_default=False)
                            sub_path = f"{base_folder}/{season_folder}/{sub_name}"
                            all_subtitle_tasks.append(SubtitleTask(
                                source_path=sub.path,
                                target_path=sub_path,
                                is_default=False
                            ))
                            season_subtitle_count += 1
                
                total_subtitle_count += season_subtitle_count
                output += f"- S{season_num:02d}: {len(files)} 个文件"
                if season_subtitle_count > 0:
                    output += f" (+{season_subtitle_count} 字幕)"
                output += "\n"
        
        else:
            # 电影：直接生成
            files = cls.files  # List[ClassifiedFile]
            movie_folder = format_movie_folder(title, year)
            strm_name = format_strm_movie_name(title, year)
            
            # 使用 target_path + 自动子分类
            category_path = get_target_path(target_path, MediaType.MOVIE, sub_category, effective_language)
            base_folder = f"{category_path}/{movie_folder}"
            
            movie_subtitle_count = 0
            for cf in files:
                strm_path = f"{base_folder}/{strm_name}"
                strm_content = _generate_strm_content(storage_config, cf.path)
                all_strm_files.append((strm_path, strm_content))
                
                # 🆕 收集字幕任务（不在此处读取内容）
                if cf.subtitles:
                    # 🔥 先生成默认字幕任务（根据优先级选择）
                    default_sub = _select_default_subtitle(cf.subtitles)
                    if default_sub:
                        default_sub_name = _format_movie_subtitle_name(title, year, default_sub, is_default=True)
                        default_sub_path = f"{base_folder}/{default_sub_name}"
                        all_subtitle_tasks.append(SubtitleTask(
                            source_path=default_sub.path,
                            target_path=default_sub_path,
                            is_default=True
                        ))
                        movie_subtitle_count += 1
                    
                    # 🔥 再收集所有带语言标识的字幕任务
                    for sub in cf.subtitles:
                        sub_name = _format_movie_subtitle_name(title, year, sub, is_default=False)
                        sub_path = f"{base_folder}/{sub_name}"
                        all_subtitle_tasks.append(SubtitleTask(
                            source_path=sub.path,
                            target_path=sub_path,
                            is_default=False
                        ))
                        movie_subtitle_count += 1
            
            output += f"- {len(files)} 个文件"
            if movie_subtitle_count > 0:
                output += f" (+{movie_subtitle_count} 字幕)"
            output += "\n"
        
        output += "\n"
    
    total_strm = len(all_strm_files)
    total_subtitle = len(all_subtitle_tasks)
    total_files = total_strm + total_subtitle
    output += f"---\n**总计: {total_strm} 个 STRM 文件 + {total_subtitle} 个字幕文件**\n\n"
    
    # 根据输出格式处理
    if output_format == "list":
        output += "### 📋 文件列表（预览）\n\n"
        for path, _ in all_strm_files[:20]:
            output += f"- {path}\n"
        if total_strm > 20:
            output += f"- ... 还有 {total_strm - 20} 个 STRM\n"
        if total_subtitle > 0:
            output += f"\n**字幕文件**: {total_subtitle} 个\n"
            for task in all_subtitle_tasks[:10]:
                output += f"- {task.target_path}\n"
            if total_subtitle > 10:
                output += f"- ... 还有 {total_subtitle - 10} 个字幕\n"
        return make_tool_response(output)
    
    elif output_format == "zip":
        output += "### 📦 生成 ZIP 文件\n\n"
        
        # 🔥 ZIP 模式需要先下载字幕内容
        output += "⏳ 正在下载字幕文件...\n"
        all_subtitle_files = []
        for task in all_subtitle_tasks:
            content = _read_subtitle_content(source_service, task.source_path)
            if content:
                all_subtitle_files.append((task.target_path, content))
        
        # 合并 STRM 和字幕文件
        all_files = all_strm_files + all_subtitle_files
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for path, content in all_files:
                zf.writestr(path, content)
        
        zip_buffer.seek(0)
        zip_size = len(zip_buffer.getvalue())
        
        output += f"✅ ZIP 生成完成\n"
        output += f"- 大小: {zip_size / 1024:.1f} KB\n"
        output += f"- 文件数: {len(all_files)}\n\n"
        output += "**注意**: ZIP 文件已在内存中生成，但 Agent 无法直接发送文件。\n"
        output += "请使用 webdav 模式直接上传到目标存储。\n"
        
        return make_tool_response(output)
    
    elif output_format == "webdav":
        output += "### 📤 上传到目标存储\n\n"
        
        # 从 services.py 获取服务实例
        thread_id = "default"  # 在 InjectedState 模式下，thread_id 需要从 config 获取
        # 但这里我们直接创建服务实例，因为 strm_target 是临时的
        target_service = create_storage_service_sync(
            url=strm_target_config.get("url", ""),
            username=strm_target_config.get("username", ""),
            password=strm_target_config.get("password", ""),
            base_path="/",
        )
        
        upload_delay = user_config.get("upload_delay", 0)  # 🔥 从用户配置读取
        
        # 🔥 如果设置了 upload_delay，使用串行上传（带延迟）
        if upload_delay > 0:
            output += f"⏱️ 使用串行上传 (延迟: {upload_delay}s/文件)\n"
        else:
            output += f"⚡ 使用异步并行上传 (并发: {UPLOAD_CONCURRENCY})\n"
            output += f"🆕 字幕处理: 下载+上传封装为单个并发任务\n"
        output += f"- 服务类型: {target_service.service_type}\n"
        output += f"- 输出路径: {target_path}\n\n"
        
        start_time = time.perf_counter()
        strm_success = 0
        strm_error = 0
        sub_success = 0
        sub_error = 0
        failed_paths = []
        
        try:
            if upload_delay > 0:
                # 🔥 串行上传（带延迟）- STRM 和字幕分开处理
                import time as time_module
                
                # 1. 先上传 STRM 文件
                output += "📤 上传 STRM 文件...\n"
                for i, (path, content) in enumerate(all_strm_files):
                    if i > 0:
                        time_module.sleep(upload_delay)
                    try:
                        if target_service.put_file_content(path, content):
                            strm_success += 1
                        else:
                            strm_error += 1
                            failed_paths.append(path)
                    except Exception as e:
                        strm_error += 1
                        failed_paths.append(path)
                        logger.warning(f"上传 STRM 失败 {path}: {e}")
                
                # 2. 再处理字幕（串行：下载+上传）
                output += "📝 处理字幕文件...\n"
                for i, task in enumerate(all_subtitle_tasks):
                    if i > 0:
                        time_module.sleep(upload_delay)
                    try:
                        # 下载字幕内容
                        content = _read_subtitle_content(source_service, task.source_path)
                        if content:
                            # 上传到目标
                            if target_service.put_file_content(task.target_path, content):
                                sub_success += 1
                            else:
                                sub_error += 1
                                failed_paths.append(task.target_path)
                        else:
                            sub_error += 1
                            failed_paths.append(task.target_path)
                    except Exception as e:
                        sub_error += 1
                        failed_paths.append(task.target_path)
                        logger.warning(f"处理字幕失败 {task.source_path}: {e}")
            else:
                # 🆕 异步并行上传 + 刷新
                # 🔥 收集需要刷新的目录（在上传前收集）
                dirs_to_refresh = set()
                for path, _ in all_strm_files:
                    dir_path = os.path.dirname(path)
                    if dir_path:
                        dirs_to_refresh.add(dir_path)
                for task in all_subtitle_tasks:
                    dir_path = os.path.dirname(task.target_path)
                    if dir_path:
                        dirs_to_refresh.add(dir_path)
                
                # 🔥 将上传和刷新放在同一个 async 函数中，避免事件循环关闭问题
                async def _upload_and_refresh_async():
                    nonlocal strm_success, strm_error, sub_success, sub_error, failed_paths
                    
                    # 1. 并行上传 STRM 文件
                    logger.info(f"开始并行上传 {len(all_strm_files)} 个 STRM 文件...")
                    s_success, s_error, s_failed = await target_service.upload_files_batch_async(
                        all_strm_files, concurrency=UPLOAD_CONCURRENCY
                    )
                    strm_success = s_success
                    strm_error = s_error
                    failed_paths.extend(s_failed)
                    
                    # 2. 并行处理字幕（下载+上传封装为单个任务）
                    _failed_upload_details = []  # 🆕 收集详细失败信息
                    if all_subtitle_tasks:
                        logger.info(f"开始并行处理 {len(all_subtitle_tasks)} 个字幕任务...")
                        sub_s, sub_e, sub_f, sub_details = await _process_subtitles_batch_async(
                            all_subtitle_tasks,
                            source_service,
                            target_service,
                            concurrency=SUBTITLE_UPLOAD_CONCURRENCY
                        )
                        sub_success = sub_s
                        sub_error = sub_e
                        failed_paths.extend(sub_f)
                        _failed_upload_details.extend(sub_details)  # 🆕 收集详细失败信息
                    
                    # 3. 🔥 刷新目录缓存（在同一个事件循环中）
                    refresh_results = {}
                    if dirs_to_refresh and hasattr(target_service, 'refresh_directories_batch_async'):
                        logger.info(f"刷新目录缓存: {len(dirs_to_refresh)} 个目录")
                        refresh_results = await target_service.refresh_directories_batch_async(
                            list(dirs_to_refresh), concurrency=4
                        )
                    
                    return refresh_results, _failed_upload_details  # 🆕 返回失败详情
                
                refresh_results, failed_upload_details = asyncio.run(_upload_and_refresh_async())
            
            elapsed = time.perf_counter() - start_time
            total_success = strm_success + sub_success
            total_error = strm_error + sub_error
            
            output += f"✅ 上传完成 ({elapsed:.1f}s)\n"
            output += f"- STRM: {strm_success} 成功"
            if strm_error > 0:
                output += f", {strm_error} 失败"
            output += "\n"
            output += f"- 字幕: {sub_success} 成功"
            if sub_error > 0:
                output += f", {sub_error} 失败"
            output += "\n"
            if total_error > 0:
                logger.warning(f"上传失败的文件 ({len(failed_paths)} 个): {failed_paths[:10]}...")
                output += f"- 失败文件示例: {failed_paths[:3]}\n"
            if elapsed > 0:
                output += f"- 平均速度: {total_success / elapsed:.1f} 文件/秒\n"
            
            # 输出刷新结果
            if refresh_results:
                refresh_success = sum(1 for v in refresh_results.values() if v)
                output += f"🔄 刷新目录: {refresh_success}/{len(refresh_results)} 成功\n"
            
        except Exception as e:
            output += f"❌ 上传失败: {e}\n"
            logger.exception("上传失败")
        
        # 清除已处理的分类数据（通过返回空 classifications）
        total_success = strm_success + sub_success
        total_error = strm_error + sub_error
        
        # 🆕 构建 state_update
        state_update = {
            "classifications": [],  # 清空分类数据
            "strm_progress": {
                "total": total_files,
                "success": total_success,
                "error": total_error,
                "status": "completed",
            }
        }
        
        # 🆕 如果有失败的上传，保存到 state 供重试
        try:
            if failed_upload_details:
                state_update["failed_uploads"] = failed_upload_details
                output += f"\n💡 **提示**: 有 {len(failed_upload_details)} 个字幕文件上传失败，可以使用 `retry_failed_uploads` 重试\n"
        except NameError:
            pass  # 同步模式下没有 failed_upload_details
        
        return make_tool_response(output, state_update=state_update)
    
    else:
        return make_tool_response(f"❌ 未知的输出格式: {output_format}")


@tool
def retry_failed_uploads(
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    🔄 重试失败的上传任务
    
    从 state.failed_uploads 读取失败的任务并重试。
    使用同步方法避免事件循环问题。
    
    Returns:
        重试结果摘要
    """
    logger.info("🔄 retry_failed_uploads 被调用")
    
    # 获取失败的任务列表
    failed_uploads = state.get("failed_uploads", []) if state else []
    
    if not failed_uploads:
        return make_tool_response("✅ 没有需要重试的失败任务")
    
    # 获取存储服务
    source_service = get_storage_service(state)
    target_service = get_strm_target_service(state)
    
    if not source_service or not target_service:
        return make_tool_response("❌ 请先连接源存储和目标存储")
    
    output = f"## 🔄 重试失败的上传任务\n\n"
    output += f"共有 {len(failed_uploads)} 个任务需要重试\n\n"
    
    # 🔥 使用同步方法逐个重试，避免事件循环问题
    success_count = 0
    error_count = 0
    still_failed = []
    
    for item in failed_uploads:
        if item.get("type") != "subtitle":
            continue
            
        source_path = item["source_path"]
        target_path = item["target_path"]
        
        try:
            # 1. 同步下载字幕内容
            logger.info(f"📥 重试下载: {os.path.basename(source_path)}")
            content = source_service.get_file_content(source_path)
            
            if not content:
                error_msg = "下载失败（返回空内容）"
                logger.warning(f"❌ {error_msg}: {source_path}")
                error_count += 1
                still_failed.append({
                    "source_path": source_path,
                    "target_path": target_path,
                    "type": "subtitle",
                    "error": error_msg
                })
                continue
            
            # 2. 同步上传到目标
            logger.info(f"📤 重试上传: {os.path.basename(target_path)}")
            success = target_service.put_file_content(target_path, content)
            
            if success:
                logger.info(f"✅ 重试成功: {os.path.basename(source_path)}")
                success_count += 1
            else:
                error_msg = "上传失败（API返回失败）"
                logger.warning(f"❌ {error_msg}: {target_path}")
                error_count += 1
                still_failed.append({
                    "source_path": source_path,
                    "target_path": target_path,
                    "type": "subtitle",
                    "error": error_msg
                })
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 重试异常 {source_path}: {e}")
            error_count += 1
            still_failed.append({
                "source_path": source_path,
                "target_path": target_path,
                "type": "subtitle",
                "error": error_msg
            })
    
    output += f"✅ 重试完成\n"
    output += f"- 成功: {success_count}\n"
    output += f"- 仍然失败: {error_count}\n"
    
    if still_failed:
        output += f"\n### ⚠️ 仍然失败的文件\n"
        for item in still_failed[:5]:
            output += f"- `{os.path.basename(item['source_path'])}`: {item['error']}\n"
        if len(still_failed) > 5:
            output += f"- ... 还有 {len(still_failed) - 5} 个\n"
    
    # 更新 state
    state_update = {}
    if still_failed:
        state_update["failed_uploads"] = still_failed
        output += f"\n💡 可以再次使用 `retry_failed_uploads` 重试\n"
    else:
        state_update["failed_uploads"] = []  # 清空
        output += f"\n🎉 所有任务已成功完成！\n"
    
    return make_tool_response(output, state_update=state_update)
