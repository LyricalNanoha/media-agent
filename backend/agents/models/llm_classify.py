"""
LLM 分类相关模型

🔥 用于 prepare_llm_classification 和 apply_llm_classification 工具之间的数据传递
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class LLMClassifyFileItem(BaseModel):
    """
    LLM 分类文件项
    
    用于 prepare_llm_classification 输出，存储在 state.llm_classify_files 中
    """
    index: int = Field(..., description="文件索引（从1开始）")
    name: str = Field(..., description="文件名")
    path: str = Field(..., description="完整路径")
    directory: str = Field("", description="所在目录")


class LLMClassificationItem(BaseModel):
    """
    LLM 分类结果项
    
    用于 LLM 输出的分类结果
    """
    file_index: int = Field(..., description="文件索引（对应 LLMClassifyFileItem.index）")
    tmdb_id: int = Field(..., description="TMDB ID")
    season: int = Field(0, description="季号（电影为0）")
    episode: int = Field(0, description="集数（电影为0）")


class LLMUnmatchedItem(BaseModel):
    """
    LLM 无法匹配的文件项
    """
    file_index: int = Field(..., description="文件索引")
    reason: str = Field("", description="无法匹配的原因")


class LLMClassificationResult(BaseModel):
    """
    LLM 分类结果（完整）
    
    用于解析 LLM 输出的 JSON
    """
    classifications: List[LLMClassificationItem] = Field(default_factory=list, description="分类结果列表")
    unmatched: List[LLMUnmatchedItem] = Field(default_factory=list, description="无法匹配的文件列表")

