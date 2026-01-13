"""
测试工具 - 用于验证 CopilotKit 卡片渲染机制

这个工具不做任何实际操作，只是等待指定秒数然后返回结果。
用于测试：
1. 卡片是否显示
2. loading 状态是否正常
3. 完成后是否变成完成状态

🔥 新架构（2026-01-08）：
- 返回通用 ToolResponse JSON：{"message": "...", "state_update": {...}}
"""

import time
from langchain.tools import tool
from backend.agents.tool_response import make_tool_response


@tool
def test_card(
    wait_seconds: int = 3,
    message: str = "测试消息"
) -> str:
    """
    🧪 测试工具 - 验证卡片渲染
    
    这个工具只是等待指定秒数然后返回结果。
    
    Args:
        wait_seconds: 等待秒数（默认 3 秒）
        message: 返回的测试消息
    
    Returns:
        ToolResponse JSON
    """
    print(f"🧪 测试工具开始，等待 {wait_seconds} 秒...")
    
    # 模拟工具执行时间
    time.sleep(wait_seconds)
    
    print(f"🧪 测试工具完成")
    
    return make_tool_response(f"✅ 测试完成！等待了 {wait_seconds} 秒\n消息: {message}")
