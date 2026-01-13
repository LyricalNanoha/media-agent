"""
媒体文件匹配工具

提供 LLM 智能匹配功能，用于将文件标题匹配到正确的元数据。
统一的匹配逻辑，供 STRM 生成和传统整理共用。
"""

import re
import logging
from typing import Dict, List, Optional, Any

from backend.agents.utils.llm_utils import call_llm_directly

logger = logging.getLogger(__name__)


def match_media_with_llm(
    file_title: str, 
    candidates: List[Dict[str, Any]], 
    item_type: str = "电影",
    context: str = ""
) -> Optional[Dict[str, Any]]:
    """
    使用 LLM 智能匹配文件标题与元数据候选列表
    
    这是一个通用的匹配函数，可以用于：
    - 电影/剧场版匹配
    - Live/演唱会匹配
    - TV 季匹配（如果需要）
    
    Args:
        file_title: 文件的原始标题（如 "SeriesA Live Event ~XXX~"）
        candidates: 元数据候选列表，每个包含 title, title_zh, title_en, year 等
        item_type: 类型描述（"电影/剧场版" 或 "演唱会/Live"）
        context: 额外的上下文信息（如系列名）
    
    Returns:
        最匹配的候选项，如果无法匹配则返回 None
    """
    if not candidates:
        logger.debug(f"没有候选项可供匹配: {file_title}")
        return None
    
    if len(candidates) == 1:
        # 只有一个候选，直接返回
        logger.info(f"🎯 唯一候选匹配: {file_title} → {candidates[0].get('title_zh', candidates[0].get('title', ''))}")
        return candidates[0]
    
    # 构建候选列表描述
    candidates_desc = []
    for i, c in enumerate(candidates, 1):
        title = c.get("title", "")
        title_zh = c.get("title_zh", "")
        title_en = c.get("title_en", "")
        year = c.get("year", "")
        
        # 构建显示文本
        display = title_zh or title or title_en
        extra_info = []
        if title_en and title_en != display:
            extra_info.append(f"EN: {title_en}")
        if year:
            extra_info.append(f"Year: {year}")
        
        desc = f"{i}. {display}"
        if extra_info:
            desc += f" ({', '.join(extra_info)})"
        candidates_desc.append(desc)
    
    # 构建 LLM prompt
    context_text = f"\n\n## 上下文\n{context}" if context else ""
    
    prompt = f"""请帮我匹配以下{item_type}文件到正确的元数据。

## 文件标题
{file_title}

## 候选元数据列表
{chr(10).join(candidates_desc)}{context_text}

## 匹配规则
1. 优先匹配关键词：文件名中的特定标识词（如 "LET'S GO!"、"Come With Me!!"、"The Movie"、"剧场版"）是重要区分依据
2. 年份参考：如果文件名包含年份，优先匹配相近年份的候选
3. 语言对应：英文文件名匹配英文元数据，中文匹配中文
4. 如果都不匹配，返回 0

请直接返回最匹配的候选项编号（1、2、3 等），只返回数字，不要其他内容。
"""
    
    try:
        result = call_llm_directly(prompt, max_tokens=10)
        if result:
            # 提取数字
            match = re.search(r'\d+', result.strip())
            if match:
                idx = int(match.group())
                if 1 <= idx <= len(candidates):
                    selected = candidates[idx - 1]
                    selected_title = selected.get('title_zh', selected.get('title', selected.get('title_en', '')))
                    logger.info(f"🤖 LLM 匹配: '{file_title}' → #{idx} {selected_title}")
                    return selected
                elif idx == 0:
                    logger.info(f"🤖 LLM 判断无匹配: '{file_title}'")
                    return None
    except Exception as e:
        logger.warning(f"LLM 匹配调用失败: {e}")
    
    # 如果 LLM 匹配失败，尝试简单的关键词匹配作为降级方案
    logger.warning(f"LLM 匹配失败，尝试关键词匹配: {file_title}")
    return _fallback_keyword_match(file_title, candidates)


def _fallback_keyword_match(
    file_title: str, 
    candidates: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    降级的关键词匹配
    
    当 LLM 不可用时使用。提取文件名中的关键词并尝试匹配。
    """
    file_lower = file_title.lower()
    
    # 尝试提取关键标识词（引号内、波浪号内的内容）
    identifiers = []
    
    # 匹配 ~xxx~ 格式
    tilde_matches = re.findall(r'~([^~]+)~', file_title)
    identifiers.extend([m.lower().strip() for m in tilde_matches])
    
    # 匹配常见关键词
    keywords = ["the movie", "movie", "film", "剧场版", "劇場版", "concert", "live", "演唱会"]
    for kw in keywords:
        if kw in file_lower:
            identifiers.append(kw)
    
    best_match = None
    best_score = 0
    
    for candidate in candidates:
        score = 0
        c_title = (candidate.get("title", "") or "").lower()
        c_title_zh = (candidate.get("title_zh", "") or "").lower()
        c_title_en = (candidate.get("title_en", "") or "").lower()
        
        all_titles = f"{c_title} {c_title_zh} {c_title_en}"
        
        # 检查关键标识词
        for identifier in identifiers:
            if identifier in all_titles:
                score += 10
        
        # 基本的标题包含检查
        if file_lower in all_titles or any(t in file_lower for t in [c_title, c_title_zh, c_title_en] if t):
            score += 5
        
        if score > best_score:
            best_score = score
            best_match = candidate
    
    if best_match and best_score > 0:
        matched_title = best_match.get('title_zh', best_match.get('title', ''))
        logger.info(f"📎 关键词匹配: '{file_title}' → {matched_title} (score: {best_score})")
        return best_match
    
    return None


def match_movie(
    file_title: str, 
    movies: List[Dict[str, Any]], 
    series_name: str = ""
) -> Optional[Dict[str, Any]]:
    """
    匹配电影/剧场版
    
    便捷函数，专门用于电影匹配。
    """
    context = f"系列名: {series_name}" if series_name else ""
    return match_media_with_llm(file_title, movies, "电影/剧场版", context)


def match_live_event(
    file_title: str, 
    live_events: List[Dict[str, Any]], 
    series_name: str = "",
    movies_fallback: List[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """
    匹配 Live/演唱会
    
    便捷函数，专门用于 Live 事件匹配。
    支持在 movies 列表中查找（因为 TMDB 元数据可能将 Live 分类为 movie）
    
    Args:
        file_title: 文件标题
        live_events: Live 事件候选列表
        series_name: 系列名（上下文）
        movies_fallback: 如果在 live_events 中找不到，尝试在 movies 中查找
    """
    context = f"系列名: {series_name}" if series_name else ""
    
    # 先在 Live 列表中查找
    if live_events:
        result = match_media_with_llm(file_title, live_events, "演唱会/Live", context)
        if result:
            return result
    
    # 如果没找到且有 movies 备选列表，也在其中查找
    # （某些 Live 事件在 TMDB 中可能被分类为电影）
    if movies_fallback:
        logger.info(f"🔄 在电影列表中搜索 Live: {file_title}")
        # 过滤可能是 Live 的电影（标题包含 Live 相关词）
        live_keywords = ["live", "concert", "演唱会", "演唱會", "ライブ", "event"]
        potential_lives = [
            m for m in movies_fallback 
            if any(kw in (m.get("title", "") + m.get("title_en", "") + m.get("title_zh", "")).lower() 
                   for kw in live_keywords)
        ]
        if potential_lives:
            result = match_media_with_llm(file_title, potential_lives, "演唱会/Live", context)
            if result:
                logger.info(f"✅ 在电影列表中找到 Live: {result.get('title_zh', result.get('title', ''))}")
                return result
    
    return None

