"""
智能文件分析工具

🔥 核心设计（见 docs/CONTEXT.md）：
- analyze_and_classify：一键分析+分类，输出结果供用户确认/修正

数据流：
1. scan_media_files() → scanned_files (List[ScannedFile])
2. analyze_and_classify() → 分析 + 分类 + 输出结果供用户确认
3. 用户确认 → generate_strm / organize_files

🔥 新架构（2026-01-09）：
- 使用 InjectedState 访问 State
- 返回通用 ToolResponse JSON：{"message": "...", "state_update": {...}}
- classifications 通过 state_update 返回

🔥 分类逻辑重构（2026-01-09）：
- 代码不判断，只查表
- 使用 TMDBMapping 映射表
- context 由 LLM 分析生成
"""

import re
import json
import logging
from typing import Dict, Any, List, Tuple, Annotated
from collections import defaultdict
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from backend.agents.state import MediaAgentState
from backend.agents.tool_response import make_tool_response
from backend.services.tmdb_service import get_tmdb_service
from backend.agents.models import (
    ScannedFile,
    Classification,
    ClassifiedFile,
    SubtitleFile,
    MediaType,
    SubCategory,
    determine_subcategory,
    ClassificationResultItem,
    # 新架构：映射表
    TMDBMapping,
    get_or_build_mapping,
)
from backend.agents.models.output import SeasonInfo
from backend.agents.classifier import (
    classify_file,
    classify_files,
    summarize_results,
    ClassifyResult,
    extract_episode_number as new_extract_episode_number,
)

logger = logging.getLogger(__name__)


# ============ 辅助函数 ============

def _extract_episode_number(filename: str) -> int:
    """从文件名提取集数
    
    注意：需要排除常见的编码信息如 x264, x265, h264, h265
    """
    # 先移除可能干扰的编码信息
    clean_name = re.sub(r'[xh]26[45]', '', filename, flags=re.IGNORECASE)
    clean_name = re.sub(r'HEVC|AVC|Ma10p|10bit', '', clean_name, flags=re.IGNORECASE)
    
    patterns = [
        r'EP?\.?(\d{2,4})',           # EP01, E01, EP.01
        r'(?<![xh])E(\d{2,4})',       # E01 但不匹配 x265
        r'第(\d{1,4})[集话話]',        # 第01集
        r'\[(\d{2,4})\]',             # [01]
        r'[\.\s\-_](\d{2,4})[\.\s\-_\[]',  # .01. _01_
        r'S\d+E(\d{2,4})',            # S01E01
    ]
    
    for pattern in patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            ep = int(match.group(1))
            # 排除不合理的集数（如 1080, 720 等分辨率）
            if ep < 1000 and ep > 0:
                return ep
    
    return 0


def _get_base_name(filename: str) -> str:
    """提取文件主名称（去掉语言标识和扩展名）
    
    Examples:
        [001].chs.srt → [001]
        [001].mkv → [001]
        Movie.2020.chs.ass → Movie.2020
        [001].scjp.ass → [001]
        [001].tcjp.ass → [001]
    """
    # 移除扩展名
    name = re.sub(r'\.(srt|ass|ssa|sub|mkv|mp4|avi|wmv|flv|mov)$', '', filename, flags=re.IGNORECASE)
    # 移除语言标识（包括复合语言标识如 scjp, tcjp）
    name = re.sub(r'\.(chs|cht|chi|eng|jpn|jap|kor|und|sc|tc|scjp|tcjp|chtjp|chsjp)$', '', name, flags=re.IGNORECASE)
    return name


def _parse_scanned_files(scanned_files_data: List[Dict[str, Any]]) -> List[ScannedFile]:
    """从 State 中解析 scanned_files 数据为 Pydantic 模型
    
    🔥 使用 Pydantic model_validate 自动验证和转换
    """
    return [ScannedFile.model_validate(f) for f in scanned_files_data]


def _execute_classification(
    mappings: List[dict],
    video_files: List[ScannedFile],
    subtitle_files: List[ScannedFile]
) -> Tuple[Dict[int, Classification], List[ScannedFile], int]:
    """
    执行分类逻辑
    
    Returns:
        (classifications, unclassified_files, matched_count)
    """
    tmdb = get_tmdb_service()
    
    # 构建字幕索引
    subtitle_index = defaultdict(list)
    for sub in subtitle_files:
        base_name = _get_base_name(sub.name)
        subtitle_index[(sub.directory, base_name)].append(sub)
    
    # 初始化分类结构
    classifications: Dict[int, Classification] = {}
    tmdb_seasons_cache: Dict[int, List[Dict]] = {}
    
    # 收集所有 TMDB ID
    tv_ids = set()
    movie_ids = set()
    
    for mapping in mappings:
        tmdb_id = mapping.get('tmdb_id')
        if not tmdb_id or tmdb_id == 0:
            continue
            
        if mapping.get('type') == 'tv':
            tv_ids.add(tmdb_id)
        elif mapping.get('type') == 'movie':
            movie_ids.add(tmdb_id)
            for fm in mapping.get('file_mappings', []):
                if fm.get('tmdb_id'):
                    movie_ids.add(fm['tmdb_id'])
    
    # 获取 TV 详情
    for tmdb_id in tv_ids:
        tmdb_info = tmdb.get_tv_details(tmdb_id)
        if tmdb_info:
            genres = tmdb_info.genres if tmdb_info.genres else []
            sub_category = determine_subcategory(genres)
            name = tmdb_info.title_zh or tmdb_info.title or f"TMDB:{tmdb_id}"
            
            classifications[tmdb_id] = Classification(
                tmdb_id=tmdb_id,
                name=name,
                type=MediaType.TV,
                year=tmdb_info.year,
                genres=genres,
                sub_category=sub_category,
                seasons={},
                files=[]
            )
            
            seasons = tmdb.get_tv_all_seasons(tmdb_id)
            tmdb_seasons_cache[tmdb_id] = seasons
    
    # 获取 Movie 详情
    for tmdb_id in movie_ids:
        tmdb_info = tmdb.get_movie_details(tmdb_id)
        if tmdb_info:
            genres = tmdb_info.genres if tmdb_info.genres else []
            sub_category = determine_subcategory(genres)
            name = tmdb_info.title_zh or tmdb_info.title or f"TMDB:{tmdb_id}"
            
            classifications[tmdb_id] = Classification(
                tmdb_id=tmdb_id,
                name=name,
                type=MediaType.MOVIE,
                year=tmdb_info.year,
                genres=genres,
                sub_category=sub_category,
                seasons={},
                files=[]
            )
    
    def _find_season_for_episode(tmdb_id: int, ep: int, use_global: bool = True) -> tuple:
        """根据集数确定季号和 TMDB episode_number"""
        seasons = tmdb_seasons_cache.get(tmdb_id, [])
        
        for s in seasons:
            if use_global:
                if s['ep_start_global'] <= ep <= s['ep_end_global']:
                    pos = ep - s['ep_start_global']
                    tmdb_ep = s['ep_start'] + pos
                    return s['season_number'], tmdb_ep
            else:
                if s['ep_start'] <= ep <= s['ep_end']:
                    return s['season_number'], ep
        
        return None, ep
    
    matched_count = 0
    
    # 处理每个 mapping
    for mapping in mappings:
        path_pattern = mapping.get('path', '')
        mapping_type = mapping.get('type', 'tv')
        
        # 找出匹配此路径的文件
        matching_files = []
        for vf in video_files:
            file_dir = vf.directory
            if path_pattern.lower() in file_dir.lower() or path_pattern.lower() in vf.path.lower():
                matching_files.append(vf)
        
        if mapping_type == 'movie':
            tmdb_id = mapping.get('tmdb_id')
            file_mappings = mapping.get('file_mappings', [])
            
            if file_mappings:
                for fm in file_mappings:
                    pattern = fm.get('pattern', '').lower()
                    fm_tmdb_id = fm.get('tmdb_id')
                    
                    if not fm_tmdb_id or fm_tmdb_id not in classifications:
                        continue
                    
                    for vf in matching_files:
                        if pattern in vf.name.lower():
                            base_name = _get_base_name(vf.name)
                            subs = subtitle_index.get((vf.directory, base_name), [])
                            
                            classified_file = ClassifiedFile(
                                path=vf.path,
                                name=vf.name,
                                episode=0,
                                season=0,
                                subtitles=[
                                    SubtitleFile(path=s.path, name=s.name, language=s.language or "und")
                                    for s in subs
                                ]
                            )
                            classifications[fm_tmdb_id].files.append(classified_file)
                            matched_count += 1
            elif tmdb_id and tmdb_id in classifications:
                for vf in matching_files:
                    base_name = _get_base_name(vf.name)
                    subs = subtitle_index.get((vf.directory, base_name), [])
                    
                    classified_file = ClassifiedFile(
                        path=vf.path,
                        name=vf.name,
                        episode=0,
                        season=0,
                        subtitles=[
                            SubtitleFile(path=s.path, name=s.name, language=s.language or "und")
                            for s in subs
                        ]
                    )
                    classifications[tmdb_id].files.append(classified_file)
                    matched_count += 1
        
        elif mapping_type == 'tv':
            tmdb_id = mapping.get('tmdb_id')
            if not tmdb_id or tmdb_id not in classifications:
                continue
            
            season = mapping.get('season')
            episode_range = mapping.get('episode_range')
            offset = mapping.get('offset', 0)
            numbering = mapping.get('numbering', 'direct')
            
            for vf in matching_files:
                ep = _extract_episode_number(vf.name)
                if ep == 0:
                    continue
                
                if episode_range:
                    ep_start, ep_end = episode_range
                    if not (ep_start <= ep <= ep_end):
                        continue
                
                if season is not None:
                    season_num = season
                    if numbering == 'direct':
                        tmdb_ep = ep
                    elif numbering == 'offset':
                        tmdb_ep = ep + offset
                    elif numbering == 'global_to_season':
                        _, tmdb_ep = _find_season_for_episode(tmdb_id, ep, use_global=True)
                    else:
                        tmdb_ep = ep
                else:
                    adjusted_ep = ep + offset
                    use_global = numbering in ['direct', 'global_to_season']
                    season_num, tmdb_ep = _find_season_for_episode(tmdb_id, adjusted_ep, use_global=use_global)
                    
                    if season_num is None:
                        logger.warning(f"EP{ep} 未找到对应季 (TMDB:{tmdb_id})")
                        continue
                
                if season_num not in classifications[tmdb_id].seasons:
                    classifications[tmdb_id].seasons[season_num] = []
                
                base_name = _get_base_name(vf.name)
                subs = subtitle_index.get((vf.directory, base_name), [])
                
                classified_file = ClassifiedFile(
                    path=vf.path,
                    name=vf.name,
                    episode=tmdb_ep,
                    season=season_num,
                    subtitles=[
                        SubtitleFile(path=s.path, name=s.name, language=s.language or "und")
                        for s in subs
                    ]
                )
                classifications[tmdb_id].seasons[season_num].append(classified_file)
                matched_count += 1
    
    # 找出未分类的文件
    classified_paths = set()
    for cls in classifications.values():
        for files in cls.seasons.values():
            for f in files:
                classified_paths.add(f.path)
        for f in cls.files:
            classified_paths.add(f.path)
    
    unclassified = [f for f in video_files if f.path not in classified_paths]
    
    return classifications, unclassified, matched_count


def _classifications_to_list(classifications: Dict[int, Classification]) -> List[Dict[str, Any]]:
    """将 classifications 转换为可序列化的列表格式
    
    🔥 使用 Pydantic model_dump 自动递归序列化嵌套对象
    """
    return [cls.model_dump() for cls in classifications.values()]


# ============ 工具函数 ============

@tool
def analyze_and_classify(
    mappings_json: str,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    🔥 执行文件分类（根据 LLM 的 mappings）
    
    根据 LLM 分析后生成的 mappings，将文件分类到正确的 TMDB 条目和季。
    
    Args:
        mappings_json: LLM 生成的 mappings JSON，格式：
            {
              "mappings": [
                // 类型 1：按目录/季
                {"path": "<目录名>", "tmdb_id": <TV系列ID>, "type": "tv", "season": 1},
                
                // 类型 2：按集数范围/系列（混合目录）
                {"path": "<目录名>", "episode_range": [1, 220], "tmdb_id": <系列A_ID>, "type": "tv"},
                {"path": "<目录名>", "episode_range": [221, 720], "tmdb_id": <续作ID>, "type": "tv", "offset": -220},
                
                // 类型 3：按文件名/电影
                {"path": "电影/", "type": "movie", "file_mappings": [
                    {"pattern": "Iron Man", "tmdb_id": 1726}
                ]}
              ]
            }
    
    Returns:
        ToolResponse JSON，包含分类结果
    
    使用流程（LLM 驱动）：
    1. scan_media_files() → 扫描文件
    2. LLM 分析文件名/目录结构 → 生成 mappings JSON
    3. analyze_and_classify(mappings_json) → 执行分类并返回结果
    4. 用户确认 → generate_strm 或 organize_files
    """
    # 🔥 首先记录收到的参数 - 使用 print 确保输出
    print(f"🔥🔥🔥 analyze_and_classify 被调用")
    logger.info(f"📊 analyze_and_classify 被调用")
    logger.info(f"📊 mappings_json 类型: {type(mappings_json)}, 长度: {len(mappings_json) if mappings_json else 0}")
    logger.info(f"📊 mappings_json 内容: {mappings_json[:500] if mappings_json else 'None'}...")
    logger.info(f"📊 state 类型: {type(state)}, 是否为空: {state is None}")
    
    # 从 State 读取数据
    scanned_files_data = state.get("scanned_files", []) if state else []
    logger.info(f"📊 scanned_files_data 长度: {len(scanned_files_data)}")
    
    if not scanned_files_data:
        logger.warning("❌ scanned_files_data 为空")
        return make_tool_response("❌ 请先使用 scan_media_files 扫描文件")
    
    # 解析 scanned_files
    scanned_files = _parse_scanned_files(scanned_files_data)
    
    # 分离视频和字幕文件
    video_files = [f for f in scanned_files if f.type == 'video']
    subtitle_files = [f for f in scanned_files if f.type == 'subtitle']
    
    if not video_files:
        return make_tool_response("❌ 扫描结果中没有视频文件")
    
    # ============ 1. 解析 mappings ============
    
    logger.info(f"📊 analyze_and_classify 收到 mappings_json: {mappings_json[:200] if mappings_json else 'None'}...")
    
    if not mappings_json or not mappings_json.strip():
        logger.warning("❌ mappings_json 为空")
        return make_tool_response("❌ 请提供 mappings_json 参数")
    
    mappings_json = mappings_json.strip()
    mappings = []
    
    try:
        if mappings_json.startswith('{') or mappings_json.startswith('['):
            parsed = json.loads(mappings_json)
            if isinstance(parsed, dict) and 'mappings' in parsed:
                mappings = parsed['mappings']
            elif isinstance(parsed, list):
                mappings = parsed
            logger.info(f"📊 解析得到 {len(mappings)} 个 mappings")
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON 解析失败: {e}")
        return make_tool_response(f"❌ JSON 解析失败: {e}\n请检查 mappings 格式")
    
    if not mappings:
        logger.warning("❌ mappings 为空列表")
        return make_tool_response("❌ mappings 为空，请提供有效的分类配置")
    
    # ============ 2. 执行分类 ============
    
    classifications, unclassified, matched_count = _execute_classification(
        mappings, video_files, subtitle_files
    )
    
    # ============ 3. 生成分类结果报告 ============
    
    output = "# 📊 分类结果\n\n"
    output += f"**已分类**: {matched_count} / {len(video_files)} 个文件\n\n"
    
    # 分类结果
    for tmdb_id, cls in classifications.items():
        if cls.type == MediaType.TV:
            output += f"### 📺 {cls.name} (TMDB:{tmdb_id})\n\n"
            output += "| 季 | 文件数 | 集数范围 |\n"
            output += "|---|--------|----------|\n"
            
            total_files = 0
            for season_num in sorted(cls.seasons.keys()):
                files = cls.seasons[season_num]
                if files:
                    eps = sorted([f.episode for f in files if f.episode > 0])
                    if eps:
                        output += f"| S{season_num:02d} | {len(files)} | E{eps[0]:02d}-E{eps[-1]:02d} |\n"
                    else:
                        output += f"| S{season_num:02d} | {len(files)} | - |\n"
                    total_files += len(files)
            
            output += f"\n**小计: {total_files} 个文件**\n\n"
        
        else:  # movie
            output += f"### 🎬 {cls.name} (TMDB:{tmdb_id})\n\n"
            output += f"**文件数**: {len(cls.files)} 个\n\n"
    
    # 未分类文件
    if unclassified:
        output += f"## ⚠️ 未分类文件: {len(unclassified)} 个\n\n"
        for f in unclassified[:10]:
            ep = _extract_episode_number(f.name)
            ep_str = f"EP{ep:03d}" if ep else "-"
            output += f"- {f.name} ({ep_str})\n"
        if len(unclassified) > 10:
            output += f"- ... 还有 {len(unclassified) - 10} 个\n"
        output += "\n"
    
    # 下一步提示
    output += "---\n\n"
    output += "## 🎯 下一步\n\n"
    if unclassified:
        output += "⚠️ 有未分类文件，可能需要修正 mappings 后重新分类。\n\n"
    output += "请选择操作：\n"
    output += "- **执行 STRM**: `connect_strm_target` → `generate_strm`\n"
    output += "- **执行传统整理**: `organize_files`\n"
    output += "- **重新分类**: 修正 mappings 后再次调用 `analyze_and_classify`\n"
    
    logger.info(f"📊 analyze_and_classify 输出: {len(output)} 字符")
    
    # 转换 classifications 为可序列化格式
    classifications_list = _classifications_to_list(classifications)
    
    # 构建前端期望的 classification_result 格式（按季显示）
    # 🔥 使用 Pydantic ClassificationResultItem 验证输出格式
    classification_result = {}
    for tmdb_id, cls in classifications.items():
        if cls.type == MediaType.TV:
            # 计算总文件数
            total_files = sum(len(files) for files in cls.seasons.values())
            
            # 🔥 按季构建详情
            seasons_info = []
            all_eps = []
            for season_num, files in sorted(cls.seasons.items()):
                eps = [f.episode for f in files if f.episode > 0]
                if eps:
                    all_eps.extend(eps)
                    season_ep_range = f"E{min(eps):02d}-E{max(eps):02d}"
                    seasons_info.append(SeasonInfo(
                        season=season_num,
                        episode_count=len(eps),
                        ep_range=season_ep_range
                    ))
            
            # 兼容旧版的 ep_range
            ep_range = f"E{min(all_eps):02d}-E{max(all_eps):02d}" if all_eps else "-"
            
            # 使用 Pydantic 模型验证
            item = ClassificationResultItem(
                name=cls.name,
                file_count=total_files,
                ep_range=ep_range,
                type="tv",
                seasons=[s.model_dump() for s in seasons_info]  # 🆕 按季详情
            )
            classification_result[str(tmdb_id)] = item.model_dump()
        else:  # movie
            item = ClassificationResultItem(
                name=cls.name,
                file_count=len(cls.files),
                ep_range="-",
                type="movie",
                seasons=[]  # 电影没有季
            )
            classification_result[str(tmdb_id)] = item.model_dump()
    
    # 返回 ToolResponse JSON（包含 classifications）
    return make_tool_response(
        output,
        state_update={
            "classifications": classifications_list,
            "classification_result": classification_result,
        }
    )


@tool
def analyze_and_classify_v2(
    mappings_json: str,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    🔥 执行文件分类 V2（新架构：代码不判断，只查表）
    
    根据 LLM 分析后生成的 mappings，将文件分类到正确的 TMDB 条目和季。
    
    Args:
        mappings_json: LLM 生成的 mappings JSON，格式：
            {
              "mappings": [
                // TV：指定 context
                {"path_pattern": "第一季", "tmdb_id": 30977, "context": "season_1"},
                {"path_pattern": "第二季", "tmdb_id": 30977, "context": "season_2"},
                {"path_pattern": "全集", "tmdb_id": 46260, "context": "cumulative"},
                
                // Movie
                {"file_pattern": "钢铁侠", "tmdb_id": 1726, "media_type": "movie"}
              ]
            }
            
            context 说明：
            - "cumulative": 文件编号是全系列累计编号
            - "season_N": 文件编号是第 N 季的季内编号
    
    Returns:
        ToolResponse JSON，包含分类结果
    """
    logger.info(f"🔥 analyze_and_classify_v2 被调用")
    
    # 从 State 读取数据
    scanned_files_data = state.get("scanned_files", []) if state else []
    
    if not scanned_files_data:
        return make_tool_response("❌ 请先使用 scan_media_files 扫描文件")
    
    # 解析 scanned_files
    scanned_files = _parse_scanned_files(scanned_files_data)
    
    # 分离视频和字幕文件
    video_files = [f for f in scanned_files if f.type == 'video']
    subtitle_files = [f for f in scanned_files if f.type == 'subtitle']
    
    if not video_files:
        return make_tool_response("❌ 扫描结果中没有视频文件")
    
    # 解析 mappings
    if not mappings_json or not mappings_json.strip():
        return make_tool_response("❌ 请提供 mappings_json 参数")
    
    mappings_json = mappings_json.strip()
    mappings = []
    
    try:
        if mappings_json.startswith('{') or mappings_json.startswith('['):
            parsed = json.loads(mappings_json)
            if isinstance(parsed, dict) and 'mappings' in parsed:
                mappings = parsed['mappings']
            elif isinstance(parsed, list):
                mappings = parsed
    except json.JSONDecodeError as e:
        return make_tool_response(f"❌ JSON 解析失败: {e}\n请检查 mappings 格式")
    
    if not mappings:
        return make_tool_response("❌ mappings 为空，请提供有效的分类配置")
    
    # ============ 构建 TMDB 映射表 ============
    
    tmdb = get_tmdb_service()
    tmdb_mappings: Dict[int, TMDBMapping] = {}
    tmdb_info_cache: Dict[int, Any] = {}
    
    # 收集所有 TMDB ID
    for m in mappings:
        tmdb_id = m.get("tmdb_id", 0)
        media_type = m.get("media_type", "tv")
        
        if tmdb_id and tmdb_id not in tmdb_mappings and media_type == "tv":
            mapping = get_or_build_mapping(tmdb_id, tmdb)
            if mapping:
                tmdb_mappings[tmdb_id] = mapping
                tmdb_info_cache[tmdb_id] = {
                    "name": mapping.title,
                    "type": "tv",
                }
        
        if tmdb_id and media_type == "movie":
            movie_info = tmdb.get_movie_details(tmdb_id)
            if movie_info:
                tmdb_info_cache[tmdb_id] = {
                    "name": movie_info.title_zh or movie_info.title or f"TMDB:{tmdb_id}",
                    "type": "movie",
                }
    
    # ============ 执行分类（只查表） ============
    
    files_for_classify = [
        {
            "path": f.path,
            "name": f.name,
            "directory": f.directory,
        }
        for f in video_files
    ]
    
    results = classify_files(files_for_classify, mappings, tmdb_mappings)
    summary = summarize_results(results)
    
    # ============ 构建字幕索引 ============
    
    subtitle_index = defaultdict(list)
    for sub in subtitle_files:
        base_name = _get_base_name(sub.name)
        subtitle_index[(sub.directory, base_name)].append(sub)
    
    # ============ 转换为旧格式（兼容后续工具） ============
    
    classifications: Dict[int, Classification] = {}
    
    for r in results:
        if r.status != "matched":
            continue
        
        tmdb_id = r.tmdb_id
        if tmdb_id not in classifications:
            info = tmdb_info_cache.get(tmdb_id, {})
            tmdb_info = tmdb.get_tv_details(tmdb_id) if info.get("type") == "tv" else tmdb.get_movie_details(tmdb_id)
            genres = tmdb_info.genres if tmdb_info else []
            sub_category = determine_subcategory(genres)
            
            classifications[tmdb_id] = Classification(
                tmdb_id=tmdb_id,
                name=info.get("name", f"TMDB:{tmdb_id}"),
                type=MediaType.TV if info.get("type") == "tv" else MediaType.MOVIE,
                year=tmdb_info.year if tmdb_info else 0,
                genres=genres,
                sub_category=sub_category,
                seasons={},
                files=[]
            )
        
        # 添加字幕
        base_name = _get_base_name(r.file_name)
        file_dir = "/".join(r.file_path.rsplit("/", 1)[:-1]) if "/" in r.file_path else ""
        subs = subtitle_index.get((file_dir, base_name), [])
        
        classified_file = ClassifiedFile(
            path=r.file_path,
            name=r.file_name,
            episode=r.episode,
            season=r.season,
            subtitles=[
                SubtitleFile(path=s.path, name=s.name, language=s.language or "und")
                for s in subs
            ]
        )
        
        if r.season > 0:
            if r.season not in classifications[tmdb_id].seasons:
                classifications[tmdb_id].seasons[r.season] = []
            classifications[tmdb_id].seasons[r.season].append(classified_file)
        else:
            classifications[tmdb_id].files.append(classified_file)
    
    # ============ 生成报告 ============
    
    output = "# 📊 分类结果 (V2 新架构)\n\n"
    output += f"**已分类**: {summary['matched']} / {summary['total']} 个文件\n\n"
    
    # 分类结果
    for tmdb_id, cls in classifications.items():
        if cls.type == MediaType.TV:
            output += f"### 📺 {cls.name} (TMDB:{tmdb_id})\n\n"
            output += "| 季 | 文件数 | 集数范围 |\n"
            output += "|---|--------|----------|\n"
            
            total_files = 0
            for season_num in sorted(cls.seasons.keys()):
                files = cls.seasons[season_num]
                if files:
                    eps = sorted([f.episode for f in files if f.episode > 0])
                    if eps:
                        output += f"| S{season_num:02d} | {len(files)} | E{eps[0]:02d}-E{eps[-1]:02d} |\n"
                    else:
                        output += f"| S{season_num:02d} | {len(files)} | - |\n"
                    total_files += len(files)
            
            output += f"\n**小计: {total_files} 个文件**\n\n"
        else:
            output += f"### 🎬 {cls.name} (TMDB:{tmdb_id})\n\n"
            output += f"**文件数**: {len(cls.files)} 个\n\n"
    
    # 未分类文件
    if summary["unmatched_files"]:
        output += f"## ⚠️ 未匹配文件: {summary['unmatched']} 个\n\n"
        for r in summary["unmatched_files"][:10]:
            output += f"- {r.file_name}: {r.error_message}\n"
        if len(summary["unmatched_files"]) > 10:
            output += f"- ... 还有 {len(summary['unmatched_files']) - 10} 个\n"
        output += "\n"
    
    # 错误文件
    if summary["error_files"]:
        output += f"## ❌ 错误文件: {summary['error']} 个\n\n"
        for r in summary["error_files"][:10]:
            output += f"- {r.file_name}: {r.error_message}\n"
        if len(summary["error_files"]) > 10:
            output += f"- ... 还有 {len(summary['error_files']) - 10} 个\n"
        output += "\n"
    
    # 下一步提示
    output += "---\n\n"
    output += "## 🎯 下一步\n\n"
    if summary["unmatched"] > 0 or summary["error"] > 0:
        output += "⚠️ 有未匹配/错误文件，可能需要修正 mappings 后重新分类。\n\n"
    output += "请选择操作：\n"
    output += "- **执行 STRM**: `connect_strm_target` → `generate_strm`\n"
    output += "- **执行传统整理**: `organize_files`\n"
    output += "- **重新分类**: 修正 mappings 后再次调用 `analyze_and_classify_v2`\n"
    
    # 转换为可序列化格式
    classifications_list = _classifications_to_list(classifications)
    
    # 构建前端期望的 classification_result 格式（按季显示）
    classification_result = {}
    for tmdb_id, cls in classifications.items():
        if cls.type == MediaType.TV:
            total_files = sum(len(files) for files in cls.seasons.values())
            
            # 🔥 按季构建详情
            seasons_info = []
            all_eps = []
            for season_num, files in sorted(cls.seasons.items()):
                eps = [f.episode for f in files if f.episode > 0]
                if eps:
                    all_eps.extend(eps)
                    season_ep_range = f"E{min(eps):02d}-E{max(eps):02d}"
                    seasons_info.append(SeasonInfo(
                        season=season_num,
                        episode_count=len(eps),
                        ep_range=season_ep_range
                    ))
            
            ep_range = f"E{min(all_eps):02d}-E{max(all_eps):02d}" if all_eps else "-"
            
            item = ClassificationResultItem(
                name=cls.name,
                file_count=total_files,
                ep_range=ep_range,
                type="tv",
                seasons=[s.model_dump() for s in seasons_info]  # 🆕 按季详情
            )
            classification_result[str(tmdb_id)] = item.model_dump()
        else:
            item = ClassificationResultItem(
                name=cls.name,
                file_count=len(cls.files),
                ep_range="-",
                type="movie",
                seasons=[]
            )
            classification_result[str(tmdb_id)] = item.model_dump()
    
    return make_tool_response(
        output,
        state_update={
            "classifications": classifications_list,
            "classification_result": classification_result,
        }
    )


@tool
def get_status(
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    获取当前状态摘要
    
    Returns:
        ToolResponse JSON，包含当前状态摘要
    """
    # 🔥 调试日志
    logger.info(f"📊 get_status 被调用")
    logger.info(f"📊 state 类型: {type(state)}, 是否为 None: {state is None}")
    if state:
        logger.info(f"📊 state keys: {list(state.keys()) if hasattr(state, 'keys') else 'N/A'}")
        scanned_count = len(state.get("scanned_files", []))
        logger.info(f"📊 scanned_files 数量: {scanned_count}")
    
    # 从 State 读取数据
    storage_config = state.get("storage_config", {}) if state else {}
    strm_target_config = state.get("strm_target_config", {}) if state else {}
    scanned_files_data = state.get("scanned_files", []) if state else []
    classifications_data = state.get("classifications", []) if state else []
    
    output = "## 📊 当前状态\n\n"
    
    # 连接状态
    if storage_config.get("url"):
        output += f"### 源存储\n"
        output += f"- 已连接: {storage_config.get('url', '?')}\n"
        output += f"- 基础路径: {storage_config.get('base_path', '/')}\n\n"
    else:
        output += "### 源存储\n- ❌ 未连接\n\n"
    
    # STRM 目标
    if strm_target_config.get("connected"):
        output += f"### STRM 目标存储\n"
        output += f"- 已连接: {strm_target_config.get('url', '?')}\n\n"
    
    # 扫描结果
    if scanned_files_data:
        videos = [f for f in scanned_files_data if f.get("type") == 'video']
        output += f"### 扫描结果\n"
        output += f"- 视频文件: {len(videos)} 个\n\n"
    else:
        output += "### 扫描结果\n- 未扫描\n\n"
    
    # 分类结果
    if classifications_data:
        output += "### 分类结果\n"
        for cls_dict in classifications_data:
            tmdb_id = cls_dict.get("tmdb_id")
            name = cls_dict.get("name", "Unknown")
            cls_type = cls_dict.get("type", "tv")
            
            if cls_type == "tv":
                total = sum(len(files) for files in cls_dict.get("seasons", {}).values())
            else:
                total = len(cls_dict.get("files", []))
            output += f"- {name} (TMDB:{tmdb_id}): {total} 个文件\n"
    else:
        output += "### 分类结果\n- 未分类\n"
    
    return make_tool_response(output)


@tool
def list_files(
    filter_type: str = "all",
    limit: int = 50,
    offset: int = 0,
    pattern: str = "",
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    🔧 辅助工具：列出已扫描的文件（仅在需要调试或验证时使用）
    
    ⚠️ 使用场景（仅限以下情况）：
    - 用户明确要求查看具体文件列表
    - 分类结果有疑问，需要验证原始文件名
    - 调试时需要确认哪些文件没被正确分类
    
    ❌ 不应使用（正常流程中）：
    - 常规流程（scan → analyze_and_classify → generate）不需要此工具
    - analyze_and_classify 已返回目录结构和未分类文件
    
    Args:
        filter_type: 筛选类型
            - "all": 所有文件
            - "video": 仅视频文件
            - "subtitle": 仅字幕文件
            - "unclassified": 仅未分类文件（需先执行 analyze_and_classify）
        limit: 返回数量限制（默认50，最大200）
        offset: 偏移量（分页用，从0开始）
        pattern: 文件名匹配模式（可选，如 "EP72" 匹配包含 EP72 的文件）
    
    Returns:
        ToolResponse JSON，包含文件列表
    """
    # 🔥 调试日志 - 使用 print 和 logger 确保输出
    import sys
    print(f"🔥🔥🔥 list_files 被调用: filter_type={filter_type}, limit={limit}, offset={offset}, pattern={pattern}", file=sys.stderr)
    print(f"🔥🔥🔥 state 类型: {type(state)}, 是否为 None: {state is None}", file=sys.stderr)
    sys.stderr.flush()
    logger.warning(f"📋 list_files 被调用: filter_type={filter_type}, limit={limit}, offset={offset}, pattern={pattern}")
    logger.warning(f"📋 state 类型: {type(state)}, 是否为 None: {state is None}")
    if state:
        logger.info(f"📋 state keys: {list(state.keys()) if hasattr(state, 'keys') else 'N/A'}")
    
    # 从 State 读取数据
    scanned_files_data = state.get("scanned_files", []) if state else []
    classifications_data = state.get("classifications", []) if state else []
    
    logger.info(f"📋 scanned_files_data 长度: {len(scanned_files_data)}")
    
    if not scanned_files_data:
        logger.warning("📋 scanned_files_data 为空，返回错误")
        return make_tool_response("❌ 未扫描，请先使用 scan_media_files 扫描目录")
    
    # 解析 scanned_files
    scanned_files = _parse_scanned_files(scanned_files_data)
    
    # 限制 limit 最大值
    limit = min(limit, 200)
    
    # 筛选文件
    files = scanned_files
    
    if filter_type == "video":
        files = [f for f in files if f.type == 'video']
    elif filter_type == "subtitle":
        files = [f for f in files if f.type == 'subtitle']
    elif filter_type == "unclassified":
        # 获取已分类的文件路径
        classified_paths = set()
        for cls_dict in classifications_data:
            cls_type = cls_dict.get("type", "tv")
            if cls_type == "movie":
                for cf in cls_dict.get("files", []):
                    classified_paths.add(cf.get("path"))
            else:
                for season_files in cls_dict.get("seasons", {}).values():
                    for cf in season_files:
                        classified_paths.add(cf.get("path"))
        files = [f for f in files if f.path not in classified_paths and f.type == 'video']
    
    # 按模式筛选
    if pattern:
        files = [f for f in files if pattern.lower() in f.name.lower()]
    
    # 分页
    total = len(files)
    files = files[offset:offset + limit]
    
    if not files:
        return make_tool_response(f"🔍 没有找到匹配的文件（筛选: {filter_type}, 模式: '{pattern}'）")
    
    # 构建输出
    output = f"## 📋 文件列表\n\n"
    output += f"- 筛选: `{filter_type}`"
    if pattern:
        output += f", 模式: `{pattern}`"
    output += f"\n- 显示: {offset + 1} - {offset + len(files)} / 共 {total} 个\n\n"
    
    output += "| 序号 | 文件名 | 集数 | 目录 |\n"
    output += "|-----|--------|-----|------|\n"
    
    for i, f in enumerate(files, start=offset + 1):
        name = f.name
        if len(name) > 40:
            name = name[:37] + '...'
        
        # 提取集数
        episode = _extract_episode_number(f.name)
        ep_str = f"EP{episode:03d}" if episode else "-"
        
        # 提取目录
        path = f.path
        parts = path.rsplit('/', 2)
        directory = parts[-2] if len(parts) >= 2 else '/'
        if len(directory) > 25:
            directory = directory[:22] + '...'
        
        output += f"| {i} | {name} | {ep_str} | {directory} |\n"
    
    if total > offset + limit:
        output += f"\n💡 还有 {total - offset - limit} 个文件未显示，使用 `offset={offset + limit}` 查看下一页"
    
    return make_tool_response(output)
# Force reload Thu Jan  8 10:02:50 CST 2026
