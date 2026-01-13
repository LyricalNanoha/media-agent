"""
LLM 分类工具

🔥 核心设计：让 LLM 做所有判断，代码只执行

不再用代码做任何「匹配」或「判断」，所有分类决策由 LLM 完成。
"""

import json
import logging
from typing import Dict, Any, List, Annotated
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from backend.agents.tool_response import make_tool_response
from backend.services.tmdb_service import get_tmdb_service
import re
from backend.agents.models import (
    ScannedFile,
    Classification,
    ClassifiedFile,
    SubtitleFile,
    MediaType,
    determine_subcategory,
    ClassificationResultItem,
    get_or_build_mapping,
    LLMClassifyFileItem,
    LLMClassificationResult,
)
from backend.agents.models.output import SeasonInfo

logger = logging.getLogger(__name__)


def _parse_scanned_files(scanned_files_data: List[Any]) -> List[ScannedFile]:
    """解析扫描文件数据"""
    files = []
    for f in scanned_files_data:
        if isinstance(f, dict):
            files.append(ScannedFile.model_validate(f))
        elif isinstance(f, ScannedFile):
            files.append(f)
    return files


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


def _build_file_list_text(files: List[ScannedFile], max_files: int = 200) -> str:
    """构建文件列表文本（用于 LLM 输入）"""
    video_files = [f for f in files if f.type == 'video']
    
    lines = []
    for i, f in enumerate(video_files[:max_files], 1):
        # 简化文件信息：只保留文件名和目录
        lines.append(f"{i}. {f.name}")
        if f.directory:
            lines.append(f"   目录: {f.directory}")
    
    if len(video_files) > max_files:
        lines.append(f"... 还有 {len(video_files) - max_files} 个文件")
    
    return "\n".join(lines)


def _build_tmdb_info_text(tmdb_ids: List[int]) -> str:
    """构建 TMDB 信息文本（用于 LLM 输入）"""
    tmdb = get_tmdb_service()
    lines = []
    
    for tmdb_id in tmdb_ids:
        mapping = get_or_build_mapping(tmdb_id, tmdb)
        if not mapping:
            continue
        
        lines.append(f"### {mapping.title} (TMDB: {tmdb_id})")
        
        for season_info in mapping.get_all_seasons_info():
            s = season_info['season']
            ep_count = season_info['episode_count']
            ep_start = season_info['tmdb_ep_start']
            ep_end = season_info['tmdb_ep_end']
            lines.append(f"- 第{s}季: {ep_count}集 (E{ep_start:02d}-E{ep_end:02d})")
        
        lines.append("")
    
    return "\n".join(lines)


@tool
def prepare_llm_classification(
    tmdb_ids_json: str,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    🔥 准备 LLM 分类数据
    
    收集文件列表和 TMDB 信息，生成结构化数据供 LLM 分类使用。
    
    Args:
        tmdb_ids_json: TMDB ID 列表的 JSON，如 "[30977, 46260]"
    
    Returns:
        结构化的分类数据，LLM 可以直接使用
    """
    logger.info("🔥 prepare_llm_classification 被调用")
    
    # 从 State 读取数据
    scanned_files_data = state.get("scanned_files", []) if state else []
    
    if not scanned_files_data:
        return make_tool_response("❌ 请先使用 scan_media_files 扫描文件")
    
    # 解析 TMDB IDs
    try:
        tmdb_ids = json.loads(tmdb_ids_json) if tmdb_ids_json else []
        if isinstance(tmdb_ids, int):
            tmdb_ids = [tmdb_ids]
    except json.JSONDecodeError:
        return make_tool_response("❌ tmdb_ids_json 格式错误")
    
    if not tmdb_ids:
        return make_tool_response("❌ 请提供 TMDB ID 列表")
    
    # 解析文件
    scanned_files = _parse_scanned_files(scanned_files_data)
    video_files = [f for f in scanned_files if f.type == 'video']
    
    if not video_files:
        return make_tool_response("❌ 扫描结果中没有视频文件")
    
    # 构建文件列表
    file_list_text = _build_file_list_text(scanned_files)
    
    # 构建 TMDB 信息
    tmdb_info_text = _build_tmdb_info_text(tmdb_ids)
    
    # 生成分类提示（使用 CSV 格式，更紧凑）
    output = f"""# 🎬 LLM 分类数据

## 文件列表 ({len(video_files)} 个视频)

{file_list_text}

## TMDB 信息

{tmdb_info_text}

---

## 🔥 请为每个文件分类

根据文件名和 TMDB 信息，为每个文件确定正确的分类。

**输出格式（CSV）**:
```csv
file_index,tmdb_id,type,season,episode
1,30977,0,1,1
2,30977,0,1,2
3,30977,0,1,3
28,120811,1,0,0
29,186810,1,0,0
```

**字段说明**:
- `file_index`: 文件序号
- `tmdb_id`: TMDB ID
- `type`: 媒体类型，`0`=TV剧集，`1`=电影
- `season`: 季号（电影为 0）
- `episode`: 集号（电影为 0）

**无法分类的文件**（可选）:
```csv
unmatched:file_index,reason
82,非媒体文件
```

**分类规则**:
1. 根据文件名中的集数（如 [01]、EP01、第01话）确定 episode
2. 根据目录名或文件名中的季标识确定 season:
   - 无标识 / 第一季 / S1 → season 1
   - S / 第二季 / S2 / !! → season 2
   - T / 第三季 / S3 / !!! → season 3
3. **电影/剧场版/演唱会**：type=1, season=0, episode=0
4. 如果无法确定，放入 unmatched 部分

请直接输出 CSV 格式，不要其他说明。
"""
    
    # 保存文件列表到 state，供后续使用
    # 🔥 使用 Pydantic 模型，然后 model_dump() 序列化
    file_list_for_state = [
        LLMClassifyFileItem(
            index=i,
            name=f.name,
            path=f.path,
            directory=f.directory or ""
        ).model_dump()
        for i, f in enumerate(video_files, 1)
    ]
    
    return make_tool_response(
        output,
        state_update={
            "llm_classify_files": file_list_for_state,
            "llm_classify_tmdb_ids": tmdb_ids,
        }
    )


def _parse_csv_classification(csv_data: str) -> tuple:
    """
    解析 CSV 格式的分类结果
    
    格式:
    file_index,tmdb_id,type,season,episode
    1,30977,0,1,1      # type=0 表示 TV
    28,120811,1,0,0    # type=1 表示 Movie
    
    unmatched:file_index,reason
    82,非媒体文件
    
    Returns:
        (classifications, unmatched)
    """
    classifications = []
    unmatched = []
    
    lines = csv_data.strip().split('\n')
    in_unmatched = False
    
    for line in lines:
        line = line.strip()
        
        # 跳过空行和注释
        if not line or line.startswith('#'):
            continue
        
        # 跳过表头
        if line.startswith('file_index,') or line.startswith('unmatched:file_index'):
            if 'unmatched' in line.lower():
                in_unmatched = True
            continue
        
        # 检测 unmatched 部分开始
        if line.lower().startswith('unmatched'):
            in_unmatched = True
            continue
        
        # 跳过 markdown 代码块标记
        if line.startswith('```'):
            continue
        
        parts = line.split(',')
        
        if in_unmatched:
            # 解析 unmatched: file_index,reason
            if len(parts) >= 1:
                try:
                    file_index = int(parts[0].strip())
                    reason = parts[1].strip() if len(parts) > 1 else "未知原因"
                    unmatched.append({
                        'file_index': file_index,
                        'reason': reason
                    })
                except ValueError:
                    continue
        else:
            # 格式: file_index,tmdb_id,type,season,episode (5 列)
            if len(parts) >= 5:
                try:
                    file_index = int(parts[0].strip())
                    tmdb_id = int(parts[1].strip())
                    type_val = parts[2].strip()
                    season = int(parts[3].strip())
                    episode = int(parts[4].strip())
                    
                    # type: 0=TV, 1=Movie
                    media_type = 'movie' if type_val == '1' else 'tv'
                    
                    classifications.append({
                        'file_index': file_index,
                        'tmdb_id': tmdb_id,
                        'media_type': media_type,
                        'season': season,
                        'episode': episode
                    })
                except ValueError:
                    continue
    
    return classifications, unmatched


@tool
def generate_classification(
    classifications_csv: str,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """
    🔥 生成最终分类结果
    
    接收 LLM 生成的分类 CSV，解析并保存到 state。
    返回分类预览供用户确认。
    
    ⚠️ 注意：不要在对话中输出 CSV，直接作为参数传递！
    
    Args:
        classifications_csv: LLM 生成的分类结果 CSV
            格式: file_index,tmdb_id,type,season,episode
            示例: 1,30977,0,1,1
    
    Returns:
        分类结果预览
    """
    logger.info("🔥 generate_classification 被调用")
    
    # 调试日志
    csv_lines = classifications_csv.strip().split('\n') if classifications_csv else []
    logger.info(f"📊 收到 CSV 数据: {len(csv_lines)} 行")
    
    # 🔥 调试：打印 state 的所有 keys
    if state:
        logger.info(f"🔍 state keys: {list(state.keys())}")
        logger.info(f"🔍 llm_classify_files 存在: {'llm_classify_files' in state}")
        logger.info(f"🔍 llm_classify_tmdb_ids 存在: {'llm_classify_tmdb_ids' in state}")
    else:
        logger.warning("🔍 state 为 None")
    
    # 从 State 读取数据
    scanned_files_data = state.get("scanned_files", []) if state else []
    file_list = state.get("llm_classify_files", []) if state else []
    tmdb_ids = state.get("llm_classify_tmdb_ids", []) if state else []
    
    logger.info(f"🔍 file_list 长度: {len(file_list)}, tmdb_ids: {tmdb_ids}")
    
    if not file_list:
        return make_tool_response("❌ 请先调用 prepare_llm_classification")
    
    # 🔥 使用 Pydantic 验证文件列表
    file_list_validated = [LLMClassifyFileItem.model_validate(f) for f in file_list]
    
    # 🔥 解析 CSV 格式的分类结果
    try:
        classifications_list, unmatched_list = _parse_csv_classification(classifications_csv)
        logger.info(f"🔍 解析到 {len(classifications_list)} 个分类, {len(unmatched_list)} 个未匹配")
    except Exception as e:
        return make_tool_response(f"❌ CSV 解析失败: {e}")
    
    if not classifications_list:
        return make_tool_response("❌ 分类结果为空")
    
    # 构建文件索引（使用验证后的 Pydantic 对象）
    file_index_map = {f.index: f for f in file_list_validated}
    
    # 解析原始扫描文件（用于获取字幕）
    scanned_files = _parse_scanned_files(scanned_files_data)
    subtitle_files = [f for f in scanned_files if f.type == 'subtitle']
    
    # 构建字幕索引（使用正确的 base_name 提取函数）
    from collections import defaultdict
    subtitle_index = defaultdict(list)
    for sub in subtitle_files:
        base_name = _get_base_name(sub.name)
        subtitle_index[(sub.directory, base_name)].append(sub)
    
    # 🔍 调试：打印字幕索引的 key 样本
    sample_keys = list(subtitle_index.keys())[:5]
    logger.info(f"🔍 字幕索引样本 keys: {sample_keys}")
    
    # 🔥 先从 CSV 分类结果中提取每个 TMDB ID 的媒体类型
    tmdb_media_types = {}
    for cls_item in classifications_list:
        tmdb_id = cls_item['tmdb_id']
        media_type_str = cls_item.get('media_type', 'tv')
        # 如果同一个 TMDB ID 有多个分类，以第一个为准
        if tmdb_id not in tmdb_media_types:
            tmdb_media_types[tmdb_id] = MediaType.MOVIE if media_type_str == 'movie' else MediaType.TV
    
    # 获取 TMDB 信息（根据 LLM 指定的媒体类型）
    tmdb = get_tmdb_service()
    tmdb_info_cache = {}
    
    for tmdb_id in tmdb_ids:
        # 🔥 根据 LLM 指定的媒体类型获取信息
        media_type = tmdb_media_types.get(tmdb_id, MediaType.TV)
        
        if media_type == MediaType.MOVIE:
            info = tmdb.get_movie_details(tmdb_id)
        else:
            info = tmdb.get_tv_details(tmdb_id)
        
        if info:
            tmdb_info_cache[tmdb_id] = {
                "name": info.title_zh or info.title or f"TMDB:{tmdb_id}",
                "year": info.year,
                "genres": info.genres or [],
                "media_type": media_type,  # 使用 LLM 指定的媒体类型
            }
            logger.info(f"🔍 TMDB {tmdb_id}: name={info.title_zh or info.title}, type={media_type}")
    
    # 构建分类结果
    classifications: Dict[int, Classification] = {}
    
    # 🔥 遍历 CSV 解析出的分类列表（dict 格式）
    for cls_item in classifications_list:
        file_idx = cls_item['file_index']
        tmdb_id = cls_item['tmdb_id']
        season = cls_item['season']
        episode = cls_item['episode']
        
        if file_idx not in file_index_map:
            continue
        
        # 🔥 file_info 是 LLMClassifyFileItem (Pydantic)
        file_info = file_index_map[file_idx]
        
        # 初始化分类结构
        if tmdb_id not in classifications:
            info = tmdb_info_cache.get(tmdb_id, {})
            genres = info.get("genres", [])
            sub_category = determine_subcategory(genres)
            media_type = info.get("media_type", MediaType.TV)  # 🔥 使用缓存的媒体类型
            
            classifications[tmdb_id] = Classification(
                tmdb_id=tmdb_id,
                name=info.get("name", f"TMDB:{tmdb_id}"),
                type=media_type,  # 🔥 使用正确的媒体类型
                year=info.get("year", 0),
                genres=genres,
                sub_category=sub_category,
                seasons={},
                files=[]
            )
        
        # 获取字幕（使用正确的 base_name 提取函数）
        file_name = file_info.name
        file_dir = file_info.directory
        base_name = _get_base_name(file_name)
        subs = subtitle_index.get((file_dir, base_name), [])
        
        # 🔍 调试：如果没有找到字幕，打印匹配信息
        if not subs and file_idx <= 5:
            logger.info(f"🔍 文件 {file_idx}: name={file_name}, dir={file_dir}, base_name={base_name}")
            logger.info(f"🔍 查找 key: ({file_dir}, {base_name})")
        
        # 创建分类文件
        classified_file = ClassifiedFile(
            path=file_info.path,
            name=file_name,
            episode=episode,
            season=season,
            subtitles=[
                SubtitleFile(path=s.path, name=s.name, language=s.language or "und")
                for s in subs
            ]
        )
        
        # 🔥 根据媒体类型决定添加到哪里
        if classifications[tmdb_id].type == MediaType.MOVIE or (season == 0 and episode == 0):
            # 电影：添加到 files 列表
            classifications[tmdb_id].files.append(classified_file)
        else:
            # TV：添加到对应季
            if season not in classifications[tmdb_id].seasons:
                classifications[tmdb_id].seasons[season] = []
            classifications[tmdb_id].seasons[season].append(classified_file)
    
    # 生成报告
    output = "# 📊 分类结果 (LLM 分类)\n\n"
    output += f"**已分类**: {len(classifications_list)} 个文件\n\n"
    
    for tmdb_id, cls in classifications.items():
        # 🔥 根据媒体类型显示不同的图标
        icon = "🎬" if cls.type == MediaType.MOVIE else "📺"
        output += f"### {icon} {cls.name} (TMDB:{tmdb_id})\n\n"
        
        if cls.type == MediaType.MOVIE:
            # 电影：显示文件数
            total_files = len(cls.files) + sum(len(files) for files in cls.seasons.values())
            output += f"**文件数: {total_files}**\n\n"
        else:
            # TV：显示季和集数
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
    
    # 未匹配文件
    if unmatched_list:
        output += f"## ⚠️ 未匹配文件: {len(unmatched_list)} 个\n\n"
        for item in unmatched_list[:10]:
            # 🔥 item 是 dict（从 CSV 解析）
            file_idx = item['file_index']
            reason = item.get('reason', '未知原因')
            file_info = file_index_map.get(file_idx)
            file_name = file_info.name if file_info else f'文件{file_idx}'
            output += f"- {file_name}: {reason}\n"
        if len(unmatched_list) > 10:
            output += f"- ... 还有 {len(unmatched_list) - 10} 个\n"
        output += "\n"
    
    # 下一步提示
    output += "---\n\n"
    output += "## 🎯 下一步\n\n"
    output += "请选择操作：\n"
    output += "- **执行 STRM**: `connect_strm_target` → `generate_strm`\n"
    output += "- **执行传统整理**: `organize_files`\n"
    output += "- **重新分类**: 告诉我需要调整的地方\n"
    
    # 转换为可序列化格式
    def _classification_to_dict(cls: Classification) -> Dict:
        return {
            "tmdb_id": cls.tmdb_id,
            "name": cls.name,
            "type": cls.type.value if hasattr(cls.type, 'value') else str(cls.type),
            "year": cls.year,
            "genres": cls.genres,
            "sub_category": cls.sub_category.value if hasattr(cls.sub_category, 'value') else str(cls.sub_category),
            "seasons": {
                k: [
                    {
                        "path": f.path,
                        "name": f.name,
                        "episode": f.episode,
                        "season": f.season,
                        "subtitles": [{"path": s.path, "name": s.name, "language": s.language} for s in f.subtitles]
                    }
                    for f in v
                ]
                for k, v in cls.seasons.items()
            },
            "files": [
                {
                    "path": f.path,
                    "name": f.name,
                    "episode": f.episode,
                    "season": f.season,
                    "subtitles": [{"path": s.path, "name": s.name, "language": s.language} for s in f.subtitles]
                }
                for f in cls.files
            ]
        }
    
    classifications_list = [_classification_to_dict(cls) for cls in classifications.values()]
    
    # 构建前端期望的 classification_result 格式（按季显示）
    classification_result = {}
    for tmdb_id, cls in classifications.items():
        logger.info(f"🔍 构建 classification_result: tmdb_id={tmdb_id}, type={cls.type}, name={cls.name}")
        if cls.type == MediaType.MOVIE:
            # 🔥 电影类型
            total_files = len(cls.files) + sum(len(files) for files in cls.seasons.values())
            try:
                item = ClassificationResultItem(
                    name=cls.name,
                    file_count=total_files,
                    ep_range="-",
                    type="movie",
                    seasons=None
                )
                logger.info(f"🔍 电影 item 创建成功: {item.model_dump()}")
            except Exception as e:
                logger.error(f"🔍 电影 item 创建失败: {e}")
                raise
        else:
            # 🔥 TV 类型
            total_files = sum(len(files) for files in cls.seasons.values())
            
            # 按季构建详情
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
            
            # 兼容旧版的 ep_range（所有季的 min-max）
            ep_range = f"E{min(all_eps):02d}-E{max(all_eps):02d}" if all_eps else "-"
            
            try:
                item = ClassificationResultItem(
                    name=cls.name,
                    file_count=total_files,
                    ep_range=ep_range,
                    type="tv",
                    seasons=seasons_info  # 🔥 直接传递 SeasonInfo 对象列表
                )
                logger.info(f"🔍 TV item 创建成功: {item.model_dump()}")
            except Exception as e:
                logger.error(f"🔍 TV item 创建失败: {e}, seasons_info={seasons_info}")
                raise
        classification_result[str(tmdb_id)] = item.model_dump()
    
    return make_tool_response(
        output,
        state_update={
            "classifications": classifications_list,
            "classification_result": classification_result,
        }
    )

