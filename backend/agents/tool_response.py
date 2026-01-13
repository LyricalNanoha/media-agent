"""
工具响应格式定义

🔥 新架构（2026-01-08）：
- 工具通过 InjectedState 读取 State
- 工具返回通用 JSON 格式：{"message": "...", "state_update": {...}}
- tool_node 解析 JSON 并将 state_update 合并到 State

设计原则：
- 通用处理：tool_node 不需要知道具体有哪些字段
- 解耦：工具可以返回任意 State 字段更新
- 向后兼容：纯文本响应也能正常处理

使用方式：
    import json
    
    @tool
    def my_tool(state: Annotated[dict, InjectedState]) -> str:
        # ... 执行逻辑 ...
        return json.dumps({
            "message": "操作完成",
            "state_update": {
                "scanned_files": [...],
                "scan_result": {...}
            }
        }, ensure_ascii=False)
"""

import json
from typing import Dict, Any, Tuple


def make_tool_response(message: str, state_update: Dict[str, Any] = None) -> str:
    """
    创建工具响应 JSON
    
    Args:
        message: 用户可见的消息（会显示在聊天中）
        state_update: 要更新的 State 字段（可选）
    
    Returns:
        JSON 字符串
    
    Example:
        # 只返回消息
        return make_tool_response("操作完成")
        
        # 返回消息 + 更新 State
        return make_tool_response(
            "扫描完成",
            {"scanned_files": [...], "scan_result": {...}}
        )
    """
    if state_update:
        return json.dumps({
            "message": message,
            "state_update": state_update
        }, ensure_ascii=False)
    else:
        # 没有 state_update 时也返回 JSON 格式（便于统一解析）
        return json.dumps({
            "message": message,
            "state_update": {}
        }, ensure_ascii=False)


def parse_tool_response(content: str) -> Tuple[str, Dict[str, Any]]:
    """
    解析工具响应
    
    Args:
        content: 工具返回的内容（JSON 字符串或纯文本）
    
    Returns:
        (message, state_update) 元组
        - message: 用户可见的消息
        - state_update: 要更新的 State 字段（可能为空 dict）
    """
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "message" in data:
            return data["message"], data.get("state_update", {})
    except json.JSONDecodeError:
        pass
    
    # 不是 JSON 格式，直接返回原内容
    return content, {}
