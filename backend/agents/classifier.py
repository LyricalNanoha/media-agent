"""
文件分类器

🔥 核心设计：代码不判断，只查表

输入：
- 文件编号（从文件名提取）
- context（用户指定）
- 映射表（从 TMDB 构建）

输出：
- 分类结果（SxxExx）
- 或「未匹配」

没有 if-else 业务逻辑，只有查表操作。
"""

import re
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from backend.agents.models.tmdb_mapping import TMDBMapping, EpisodeInfo

logger = logging.getLogger(__name__)


@dataclass
class ClassifyResult:
    """分类结果"""
    file_path: str
    file_name: str
    
    # 提取的信息
    extracted_number: int = 0
    
    # 分类结果
    status: str = "pending"  # matched / unmatched / error
    error_message: str = ""
    
    # 匹配成功时的信息
    tmdb_id: int = 0
    season: int = 0
    episode: int = 0  # TMDB episode_number
    output_name: str = ""  # SxxExx 格式
    
    # 关联的字幕
    subtitles: List[Dict] = field(default_factory=list)


def extract_episode_number(filename: str) -> int:
    """
    从文件名提取集数
    
    这是唯一的「提取」操作，不做任何判断。
    
    Args:
        filename: 文件名
        
    Returns:
        提取的编号，0 表示无法提取
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


def classify_file(
    file_path: str,
    file_name: str,
    context: str,
    mapping: TMDBMapping,
) -> ClassifyResult:
    """
    分类单个文件
    
    🔥 核心逻辑：只查表，不判断
    
    Args:
        file_path: 文件路径
        file_name: 文件名
        context: "cumulative" 或 "season_N"
        mapping: TMDB 映射表
        
    Returns:
        ClassifyResult
    """
    result = ClassifyResult(
        file_path=file_path,
        file_name=file_name,
    )
    
    # 1. 提取编号
    number = extract_episode_number(file_name)
    result.extracted_number = number
    
    if number == 0:
        result.status = "error"
        result.error_message = "无法从文件名提取编号"
        return result
    
    # 2. 查映射表（唯一的核心操作）
    episode_info = mapping.lookup(context, number)
    
    if episode_info is None:
        result.status = "unmatched"
        result.error_message = f"编号 {number} 在 context={context} 下未找到对应集数"
        return result
    
    # 3. 填充结果
    result.status = "matched"
    result.tmdb_id = mapping.tmdb_id
    result.season = episode_info.season
    result.episode = episode_info.tmdb_episode
    result.output_name = episode_info.to_output_name()
    
    return result


def classify_files(
    files: List[Dict[str, Any]],
    mappings: List[Dict[str, Any]],
    tmdb_mappings: Dict[int, TMDBMapping],
) -> List[ClassifyResult]:
    """
    分类多个文件
    
    Args:
        files: 文件列表 [{"path": ..., "name": ..., "directory": ...}, ...]
        mappings: 用户指定的映射 [{"path_pattern": ..., "tmdb_id": ..., "context": ...}, ...]
        tmdb_mappings: TMDB 映射表字典 {tmdb_id: TMDBMapping}
        
    Returns:
        分类结果列表
    """
    results = []
    
    for file in files:
        file_path = file.get("path", "")
        file_name = file.get("name", "")
        file_dir = file.get("directory", "")
        
        # 找到匹配的 mapping
        matched_mapping = None
        for m in mappings:
            path_pattern = m.get("path_pattern", "")
            file_pattern = m.get("file_pattern", "")
            
            # 路径匹配
            if path_pattern and path_pattern.lower() in file_path.lower():
                matched_mapping = m
                break
            
            # 文件名匹配
            if file_pattern and file_pattern.lower() in file_name.lower():
                matched_mapping = m
                break
        
        if matched_mapping is None:
            result = ClassifyResult(
                file_path=file_path,
                file_name=file_name,
                status="unmatched",
                error_message="没有匹配的 mapping 规则",
            )
            results.append(result)
            continue
        
        tmdb_id = matched_mapping.get("tmdb_id", 0)
        context = matched_mapping.get("context", "cumulative")
        media_type = matched_mapping.get("media_type", "tv")
        
        # 电影特殊处理
        if media_type == "movie":
            result = ClassifyResult(
                file_path=file_path,
                file_name=file_name,
                status="matched",
                tmdb_id=tmdb_id,
                output_name="",  # 电影不需要 SxxExx
            )
            results.append(result)
            continue
        
        # TV 分类
        tmdb_mapping = tmdb_mappings.get(tmdb_id)
        if tmdb_mapping is None:
            result = ClassifyResult(
                file_path=file_path,
                file_name=file_name,
                status="error",
                error_message=f"TMDB ID {tmdb_id} 的映射表不存在",
            )
            results.append(result)
            continue
        
        result = classify_file(file_path, file_name, context, tmdb_mapping)
        results.append(result)
    
    return results


def summarize_results(results: List[ClassifyResult]) -> Dict[str, Any]:
    """
    汇总分类结果
    
    Returns:
        {
            "total": 总数,
            "matched": 匹配数,
            "unmatched": 未匹配数,
            "error": 错误数,
            "by_season": {tmdb_id: {season: [results]}},
            "unmatched_files": [results],
            "error_files": [results],
        }
    """
    summary = {
        "total": len(results),
        "matched": 0,
        "unmatched": 0,
        "error": 0,
        "by_tmdb": {},
        "unmatched_files": [],
        "error_files": [],
    }
    
    for r in results:
        if r.status == "matched":
            summary["matched"] += 1
            
            tmdb_id = r.tmdb_id
            if tmdb_id not in summary["by_tmdb"]:
                summary["by_tmdb"][tmdb_id] = {"seasons": {}, "files": []}
            
            if r.season > 0:
                if r.season not in summary["by_tmdb"][tmdb_id]["seasons"]:
                    summary["by_tmdb"][tmdb_id]["seasons"][r.season] = []
                summary["by_tmdb"][tmdb_id]["seasons"][r.season].append(r)
            else:
                summary["by_tmdb"][tmdb_id]["files"].append(r)
                
        elif r.status == "unmatched":
            summary["unmatched"] += 1
            summary["unmatched_files"].append(r)
        else:
            summary["error"] += 1
            summary["error_files"].append(r)
    
    return summary

