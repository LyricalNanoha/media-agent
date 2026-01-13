"""
Agent 状态定义

🔥 工业级架构设计（2026-01-08）：
- MediaAgentState：完整内部状态（含大数据，用于 LangGraph 和 Checkpointer）
- FrontendViewState：前端可见状态（白名单，CopilotKit 自动过滤）

核心原理：
- LangGraph StateGraph(input, output=FrontendViewState) 
- CopilotKit 调用 get_output_jsonschema() 获取 output schema
- CopilotKit 的 filter_state_on_schema_keys() 自动过滤，只同步白名单字段

优势：
1. 大数据（scanned_files, classifications）持久化到 Checkpointer
2. 前端只收到白名单字段，无需手动过滤
3. 断开重连可恢复完整状态

⚠️ 重要：使用 total=False 让所有字段可选！
TypedDict 不支持 dataclasses.field()，LangGraph 会自动处理缺失字段。
"""

from typing import Dict, Any, List
from typing_extensions import TypedDict

from copilotkit import CopilotKitState


# ============ 前端可见状态（ViewState 白名单）============

class FrontendViewState(TypedDict, total=False):
    """
    前端可见的状态字段（白名单）
    
    🔥 只有这里定义的字段会被 CopilotKit 同步到前端！
    
    使用方式：
        StateGraph(MediaAgentState, output=FrontendViewState)
    
    CopilotKit 会：
    1. 调用 graph.get_output_jsonschema() 获取这个 TypedDict 的 keys
    2. 在 _emit_state_sync_event 中调用 filter_state_on_schema_keys(state, output_keys)
    3. 只同步这里定义的字段到前端
    """
    # === 连接配置 ===
    storage_config: Dict[str, Any]       # WebDAV/Alist 源存储配置
    strm_target_config: Dict[str, Any]   # STRM 目标存储配置
    user_config: Dict[str, Any]          # 用户偏好设置
    
    # === UI 状态 ===
    current_tool: Dict[str, Any]         # 当前执行的工具状态
    
    # === 主题人设 ===
    persona: Dict[str, Any]              # 前端传递的主题人设配置
    
    # === 摘要信息（不是完整数据）===
    scan_result: Dict[str, Any]          # 扫描摘要：total_files, video_count, sample_files
    classification_result: Dict[str, Any] # 分类摘要：每个系列的文件数
    
    # === 进度状态 ===
    scan_progress: Dict[str, Any]        # 扫描进度
    analyze_progress: Dict[str, Any]     # 分析进度
    organize_progress: Dict[str, Any]    # 整理进度
    strm_progress: Dict[str, Any]        # STRM 生成进度
    tmdb_search_result: Dict[str, Any]   # TMDB 搜索结果


# ============ 完整内部状态（AgentState）============

class MediaAgentState(CopilotKitState, total=False):
    """
    完整 Agent 状态 - 包含所有数据（含大数据）
    
    🔥 这是内部状态，包含 scanned_files、classifications 等大数据
    🔥 通过 output=FrontendViewState，CopilotKit 只同步白名单字段到前端
    🔥 大数据会被持久化到 Checkpointer，断开重连可恢复
    
    ⚠️ 重要：使用 total=False 让所有字段可选！
    TypedDict 不支持 dataclasses.field()，LangGraph 会自动处理缺失字段。
    
    🔥 数据结构定义在 models.py 中（Pydantic 模型）
    工具内部使用 model_validate() 和 model_dump() 进行转换。
    """
    
    # ============================================================
    # 🌐 前端可见字段（在 FrontendViewState 中定义）
    # ============================================================
    
    # 连接配置（用于按需创建存储服务）
    storage_config: Dict[str, Any]
    # {
    #     "url": "http://xxx",
    #     "username": "admin",
    #     "type": "alist",
    #     "token": "xxx",
    #     "scan_path": "/115/未整理/动漫",
    #     "target_path": "/kuake/整理好",
    # }
    
    strm_target_config: Dict[str, Any]
    # {
    #     "url": "http://xxx",
    #     "username": "admin",
    #     "type": "webdav",
    #     "target_path": "/kuake/strm",
    # }
    
    user_config: Dict[str, Any]
    # {"scan_delay": 0.5, "upload_delay": 0.0, "naming_language": "zh", "use_copy": true}
    
    # UI 状态
    current_tool: Dict[str, Any]
    # {"name": "tool_name", "status": "executing|complete", "description": "..."}
    
    # 主题人设（从前端同步）
    persona: Dict[str, Any]
    # {"name": "高町奈叶", "style": "温柔亲切", "greetings": [...], "successPhrases": [...], "errorPhrases": [...]}
    
    # 摘要信息
    scan_result: Dict[str, Any]
    # {"total_files": 724, "video_count": 720, "sample_files": [...]}
    
    classification_result: Dict[str, Any]
    # {<tmdb_id>: {"name": "系列名", "file_count": 41, "type": "tv"}}
    
    # 进度状态
    scan_progress: Dict[str, Any]
    analyze_progress: Dict[str, Any]
    organize_progress: Dict[str, Any]
    strm_progress: Dict[str, Any]
    tmdb_search_result: Dict[str, Any]
    
    # ============================================================
    # 🔒 后端专用字段（不会同步到前端，但会持久化到 Checkpointer）
    # ============================================================
    
    scanned_files: List[Dict[str, Any]]
    # [{"name": "EP001.mkv", "path": "/...", "size": 1000, "type": "video", "directory": "..."}]
    # 🔥 大数据：700+ 文件约 200KB
    # 🔥 数据结构：List[ScannedFile] - 见 models.py
    
    classifications: Dict[str, Any]
    # {<tmdb_id>: {"tmdb_id": <id>, "name": "系列名", "type": "tv", "seasons": {...}}}
    # 🔥 大数据：包含每个文件的分类信息
    # 🔥 数据结构：Dict[int, Classification] - 见 models.py
    
    analysis_result: Dict[str, Any]
    # 分析结果详情（目录结构、TMDB 候选等）
    
    # 🔥 LLM 分类临时数据
    llm_classify_files: List[Dict[str, Any]]
    # [{"index": 1, "name": "...", "path": "...", "directory": "..."}]
    
    llm_classify_tmdb_ids: List[int]
    # [30977, 46260]
    
    # 🔥 失败的上传任务（用于重试）
    failed_uploads: List[Dict[str, Any]]
    # [{"source_path": "...", "target_path": "...", "type": "subtitle", "error": "HTTP 403"}]

