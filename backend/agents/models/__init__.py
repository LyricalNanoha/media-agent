"""
数据模型定义

🔥 核心设计（见 docs/CONTEXT.md）：
- 所有数据结构使用 Pydantic 模型
- 提供类型安全、自动验证、IDE 补全
- 支持 pydantic2ts 自动生成前端 TypeScript 类型

模型分类：
- enums.py: 枚举类型 + 映射表 + 辅助函数
- scan.py: 扫描相关模型
- classify.py: 分类相关模型
- config.py: 配置模型
- output.py: 前端输出模型

🔧 工具内部使用方式：
- 输入验证：Model.model_validate(dict_data)
- 输出序列化：model_instance.model_dump()

🔧 生成前端 TypeScript 类型：
PYTHONPATH=/path/to/project pydantic2ts \\
    --module backend.agents.models \\
    --output frontend/src/types/generated-state.ts
"""

# 枚举类型和映射表
from .enums import (
    MediaType,
    SubCategory,
    SUBCATEGORY_TV_ZH,
    SUBCATEGORY_MOVIE_ZH,
    SUBCATEGORY_TV_EN,
    SUBCATEGORY_MOVIE_EN,
    GENRE_TO_SUBCATEGORY,
    determine_subcategory,
    get_subcategory_name,
)

# 扫描相关模型
from .scan import ScannedFile

# 分类相关模型
from .classify import (
    MatchRule,
    ClassifyRule,
    ClassifyItem,
    ClassifyConfig,
    SubtitleFile,
    ClassifiedFile,
    Classification,
)

# 配置模型
from .config import UserConfig

# 前端输出模型
from .output import (
    StorageConfigOutput,
    ScanResultOutput,
    ClassificationResultItem,
    ToolProgressOutput,
    CurrentToolOutput,
)

# TMDB 映射表（新架构：代码不判断，只查表）
from .tmdb_mapping import (
    EpisodeInfo,
    TMDBMapping,
    build_episode_mapping,
    get_or_build_mapping,
    clear_mapping_cache,
)

# LLM 分类模型
from .llm_classify import (
    LLMClassifyFileItem,
    LLMClassificationItem,
    LLMUnmatchedItem,
    LLMClassificationResult,
)

__all__ = [
    # 枚举
    "MediaType",
    "SubCategory",
    # 映射表
    "SUBCATEGORY_TV_ZH",
    "SUBCATEGORY_MOVIE_ZH",
    "SUBCATEGORY_TV_EN",
    "SUBCATEGORY_MOVIE_EN",
    "GENRE_TO_SUBCATEGORY",
    # 辅助函数
    "determine_subcategory",
    "get_subcategory_name",
    # 扫描
    "ScannedFile",
    # 分类配置
    "MatchRule",
    "ClassifyRule",
    "ClassifyItem",
    "ClassifyConfig",
    # 分类结果
    "SubtitleFile",
    "ClassifiedFile",
    "Classification",
    # 配置
    "UserConfig",
    # 前端输出
    "StorageConfigOutput",
    "ScanResultOutput",
    "ClassificationResultItem",
    "ToolProgressOutput",
    "CurrentToolOutput",
    # TMDB 映射表
    "EpisodeInfo",
    "TMDBMapping",
    "build_episode_mapping",
    "get_or_build_mapping",
    "clear_mapping_cache",
    # LLM 分类
    "LLMClassifyFileItem",
    "LLMClassificationItem",
    "LLMUnmatchedItem",
    "LLMClassificationResult",
]

