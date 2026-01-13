"""
Agent 工具包

================================================================================
🔥 核心工具列表（9 个）
================================================================================

## 连接和扫描（3 个）
1. connect_webdav      - 连接源存储
2. scan_media_files    - 扫描媒体文件
3. connect_strm_target - 连接 STRM 目标存储

## TMDB 查询（2 个）
4. search_tmdb     - 搜索 TMDB（TV/电影）
5. get_tmdb_details - 获取详细信息（季、集数等）

## 分析和分类（2 个）
6. analyze_and_classify - 🔥 一键分析+分类
7. get_status           - 获取当前状态

## 输出（2 个）
8. organize_files - 传统整理：移动/复制文件
9. generate_strm  - STRM 模式：生成 STRM 文件

================================================================================
🔧 辅助工具（不计入核心）
================================================================================

- list_files: 列出已扫描的文件（仅调试/验证时使用）
- set_user_config: 设置用户配置

================================================================================
工作流
================================================================================

标准流程：
1. connect_webdav → 连接源存储
2. scan_media_files → 扫描文件
3. analyze_and_classify → 一键分析+分类
4. 用户确认/修正 → 再次调用 analyze_and_classify（带修正参数）
5. 选择输出方式：
   - organize_files → 传统整理
   - connect_strm_target + generate_strm → STRM 模式

================================================================================
"""

# 连接工具
from .connection_tools import (
    connect_webdav,
    set_user_config,  # 🔧 配置用户参数
)

# 扫描工具
from .scan_tools import (
    scan_media_files,
)

# TMDB 工具（精简版 - 2 个）
from .tmdb_tools import (
    search_tmdb,
    get_tmdb_details,
)

# 智能分析工具
from .smart_analyze_tools import (
    analyze_and_classify,
    analyze_and_classify_v2,  # 🔥 新架构：代码不判断，只查表
    get_status,
    list_files,
)

# 🔥 LLM 分类工具（终极方案：让 LLM 做所有判断）
from .llm_classify_tools import (
    prepare_llm_classification,
    generate_classification,  # 原 apply_llm_classification
)

# 整理工具（合并版 - 1 个）
from .organize_tools import (
    organize_files,
)

# STRM 工具（合并版 - 3 个）
from .strm_tools import (
    connect_strm_target,
    generate_strm,
    retry_failed_uploads,  # 🆕 重试失败的上传
)

# 🧪 测试工具（临时）
from .test_tool import test_card


# ============ 所有工具列表 ============

ALL_TOOLS = [
    # 连接和扫描
    connect_webdav,
    scan_media_files,
    connect_strm_target,
    # TMDB
    search_tmdb,
    get_tmdb_details,
    # 分析
    analyze_and_classify,
    analyze_and_classify_v2,  # 🔥 新架构
    prepare_llm_classification,  # 🔥 终极方案
    generate_classification,     # 🔥 生成最终分类结果
    get_status,
    # 输出
    organize_files,
    generate_strm,
    retry_failed_uploads,  # 🆕 重试失败的上传
    # 辅助工具
    list_files,
    set_user_config,
    # 测试工具
    test_card,
]


__all__ = [
    # 连接和扫描
    "connect_webdav",
    "scan_media_files",
    "connect_strm_target",
    # TMDB
    "search_tmdb",
    "get_tmdb_details",
    # 分析
    "analyze_and_classify",
    "analyze_and_classify_v2",
    "prepare_llm_classification",
    "generate_classification",
    "get_status",
    # 输出
    "organize_files",
    "generate_strm",
    "retry_failed_uploads",
    # 辅助工具
    "list_files",
    "set_user_config",
    # 列表
    "ALL_TOOLS",
]
