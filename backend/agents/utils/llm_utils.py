"""
LLM 辅助函数

提供直接调用 LLM API 的功能，绕过 LangChain 的追踪系统，
避免内部 LLM 调用的输出被流式传输到前端。
"""

import logging
from typing import List, Optional
import httpx

from backend.config import get_config

logger = logging.getLogger(__name__)


def call_llm_directly(prompt: str, max_tokens: int = 4096) -> str:
    """
    直接调用 LLM API，不通过 LangChain（避免流式追踪输出到前端）
    
    Args:
        prompt: 提示词
        max_tokens: 最大输出 token 数
        
    Returns:
        LLM 响应内容
    """
    config = get_config()
    
    try:
        response = httpx.post(
            f"{config.llm.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {config.llm.api_key}"},
            json={
                "model": config.llm.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": max_tokens,
            },
            timeout=60
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"LLM API 错误: {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return ""


def extract_series_name_with_llm(
    sample_files: List[str], 
    sample_dirs: Optional[List[str]] = None
) -> str:
    """
    使用 LLM 从文件名和目录名中提取剧集名称
    
    Args:
        sample_files: 样本文件名列表
        sample_dirs: 样本目录名列表（可选）
        
    Returns:
        提取的剧集名称，用于搜索 AniList/TMDB
    """
    import json
    import re
    
    # 构建文件列表字符串
    files_str = "\n".join([f"- {f}" for f in sample_files[:10]])
    dirs_str = "\n".join([f"- {d}" for d in (sample_dirs or [])[:5]])
    
    # 使用更明确的 JSON 格式提示词
    prompt = f"""任务：从文件名中提取剧集名称

文件名列表：
{files_str}

目录名：
{dirs_str}

示例输入输出：
- 输入文件: "[VCB-Studio] SeriesA! [01][1080p].mkv" → 输出: "SeriesA!"
- 输入文件: "某动漫 EP001.mp4" → 输出: "某动漫"
- 输入文件: "Anime Name - 001 [1080p].mkv" → 输出: "Anime Name"
- 输入目录: "系列名" → 如果文件名不明确，使用目录名

规则：
1. 只提取剧集名称，不要集数、分辨率、字幕组
2. 返回格式必须是 JSON: {{"name": "剧集名"}}

请直接返回 JSON，不要任何解释："""

    logger.info("🤖 [LLM] 正在提取剧集名称...")
    
    result = call_llm_directly(prompt, max_tokens=100)
    
    if result:
        result = result.strip()
        logger.info(f"  LLM 原始响应: {repr(result)}")
        
        # 尝试解析 JSON
        try:
            # 提取 JSON 部分（可能被包裹在其他文本中）
            json_match = re.search(r'\{[^{}]*"name"\s*:\s*"([^"]+)"[^{}]*\}', result)
            if json_match:
                name = json_match.group(1).strip()
                if name and len(name) > 1:
                    logger.info(f"  JSON 解析成功: {name}")
                    return name
            
            # 直接尝试 JSON 解析
            data = json.loads(result)
            if isinstance(data, dict) and data.get("name"):
                name = data["name"].strip()
                if name and len(name) > 1:
                    logger.info(f"  JSON 解析成功: {name}")
                    return name
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # 降级：如果不是 JSON，尝试直接使用结果
        # 清理常见的废话前缀
        clean_result = result
        for prefix in ["好的", "请提供", "输出:", "答案:", "剧集名称:"]:
            if clean_result.startswith(prefix):
                clean_result = clean_result[len(prefix):].strip()
        
        # 移除引号和句号
        clean_result = clean_result.strip('"\'').rstrip('。.')
        
        # 验证结果（应该是短字符串，不包含废话）
        if clean_result and len(clean_result) < 50 and not any(kw in clean_result for kw in ["请", "提供", "需要", "文件"]):
            logger.info(f"  清理后结果: {clean_result}")
            return clean_result
    
    # LLM 失败，尝试从目录名提取
    if sample_dirs:
        for d in sample_dirs:
            if d and len(d) > 1 and d not in ["/", ".", ".."]:
                # 清理目录名
                clean_dir = re.sub(r'\s*[\(\[].*?[\)\]]', '', d).strip()
                if clean_dir and len(clean_dir) > 1:
                    logger.info(f"  使用目录名作为剧名: {clean_dir}")
                    return clean_dir
    
    return ""



