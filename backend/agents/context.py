"""
会话上下文管理（简化版）

🔥 新架构（2026-01-08）：
- 工具使用 InjectedState 直接访问 State
- 服务实例由 services.py 管理
- 此文件仅保留线程上下文管理和前端数据过滤

设计原则：
1. LangGraph State 是唯一的数据源（Dict，可序列化）
2. 工具通过 InjectedState 访问 State，返回 ToolResponse JSON
3. 服务实例由 services.py 按 thread_id + config_hash 缓存
4. 大数据（scanned_files, classifications）通过 output_schema 自动过滤
"""

import logging
import contextvars
from typing import Dict, Any

_logger = logging.getLogger(__name__)


# ============ 线程上下文管理 ============

# 当前线程的 thread_id（用于服务缓存）
_current_thread_id: contextvars.ContextVar[str] = contextvars.ContextVar("thread_id", default="default")


def set_current_thread(thread_id: str):
    """设置当前线程的 thread_id（在 tool_node 开始时调用）"""
    _current_thread_id.set(thread_id)
    _logger.debug(f"📌 [thread] 设置当前线程: {thread_id}")


def get_current_thread() -> str:
    """获取当前线程的 thread_id"""
    return _current_thread_id.get()


# ============ 前端数据过滤 ============

# 需要 emit 到前端的字段（白名单）
FRONTEND_FIELDS = {
    # 配置（前端需要显示连接状态）
    "storage_config",
    "strm_target_config",
    "user_config",
    # UI 状态
    "current_tool",
    # 主题人设（前端同步到后端）
    "persona",
    # 摘要数据（前端显示用）
    "scan_result",
    "classification_result",
    # 进度状态
    "scan_progress",
    "analyze_progress",
    "organize_progress",
    "strm_progress",
    "tmdb_search_result",
    # messages 由 CopilotKit 处理
    "messages",
    # CopilotKit 内部字段
    "copilotkit",
}


def filter_for_frontend(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    过滤 State，只保留前端需要的字段
    
    🔥 主要过滤由 LangGraph output_schema=FrontendViewState 自动完成
    此函数作为 copilotkit_emit_state 的双重保险
    
    Args:
        state: 完整的 State
    
    Returns:
        Dict: 只包含前端需要的字段
    """
    return {k: v for k, v in state.items() if k in FRONTEND_FIELDS}


# ============ 兼容性别名（逐步废弃）============

def get_context():
    """
    🚨 已废弃：请使用 InjectedState 访问 State
    
    此函数保留仅为兼容旧代码，将在未来版本移除。
    """
    _logger.warning("⚠️ get_context() 已废弃，请使用 InjectedState 访问 State")
    raise NotImplementedError(
        "get_context() 已废弃。请使用 InjectedState 访问 State。\n"
        "示例：\n"
        "  @tool\n"
        "  def my_tool(state: Annotated[MediaAgentState, InjectedState] = None):\n"
        "      storage_config = state.get('storage_config', {})\n"
    )
