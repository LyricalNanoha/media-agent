"""
WebDAV Media Rename Agent - 使用AG-UI LangGraph

这是Agent的核心实现，使用LangGraph构建Agent工作流，
并通过AG-UI协议与前端集成。

重构后的代码结构：
- state.py: Agent 状态定义
- context.py: 会话上下文管理（按 thread_id 隔离）
- tools/: 所有工具函数
- utils/: 辅助函数（如 LLM 调用）
"""

import logging
from typing import Dict, Any
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

# CopilotKit 集成
from copilotkit.langgraph import copilotkit_emit_state, copilotkit_customize_config

# 内部模块
from backend.config import get_config
from backend.agents.state import MediaAgentState, FrontendViewState
from backend.agents.context import filter_for_frontend
from backend.agents.tool_response import parse_tool_response
# 🔥 注意：不在顶部导入 ALL_TOOLS，避免热重载问题
# ALL_TOOLS 在 tool_node_with_state_emit 中动态导入

logger = logging.getLogger(__name__)


def _get_thread_id(config: RunnableConfig) -> str:
    """从 RunnableConfig 中提取 thread_id"""
    return config.get("configurable", {}).get("thread_id", "default")


# ============ 默认人设配置（备用） ============
# 注意：人设数据的主要来源是前端主题配置（frontend/src/themes/{theme}/index.ts）
# 这里只保留一个通用的默认人设，作为前端未同步时的备用

DEFAULT_PERSONA = {
    "name": "助手",
    "fullName": "媒体整理助手",
    "style": "专业友好，简洁高效",
    "greetings": ["已连接到服务器。"],
    "successPhrases": ["完成！", "操作成功。"],
    "errorPhrases": ["出现错误，请检查配置。"],
    "emoji": "",
    "roleDescription": "智能影视资源管理专家",
}


def _build_system_prompt(persona: Dict[str, Any], connection_info: str, scanned_info: str) -> str:
    """
    根据人设配置构建系统提示词
    
    Args:
        persona: 人设配置字典
        connection_info: 当前连接状态描述
        scanned_info: 已扫描文件数描述
    
    Returns:
        完整的系统提示词
    """
    name = persona.get("name", "助手")
    full_name = persona.get("fullName", name)
    style = persona.get("style", "专业友好")
    role_desc = persona.get("roleDescription", "智能影视资源管理专家")
    emoji = persona.get("emoji", "")
    success_phrases = persona.get("successPhrases", ["完成！"])
    error_phrases = persona.get("errorPhrases", ["出错了，请检查。"])
    greetings = persona.get("greetings", ["已连接。"])
    
    # 构建示例短语
    success_example = success_phrases[0] if success_phrases else "完成！"
    error_example = error_phrases[0] if error_phrases else "出错了。"
    greeting_example = greetings[0] if greetings else "已连接。"
    
    # 构建角色设定部分
    role_section = f"""你是「{full_name}」，{role_desc}。你同时也是智能影视资源管理专家，精通各种媒体文件命名规范。

## 🎀 角色设定
你的核心职责是**分析**资源结构，**理解**命名模式，**匹配** TMDB 数据。

### 说话风格
- {style}
- 遇到问题时：「{error_example}」
- 成功时：「{success_example}」
- 称呼用户为「你」，保持亲切
{f'- 适当使用 emoji 表达情感（{emoji}）' if emoji else '- 保持简洁，不使用过多 emoji'}
- 保持专业的同时带有个人风格

### 回复示例
- ✅ 连接成功：「{greeting_example}」
- ❌ 连接失败：「{error_example}」
- 📂 扫描完成：「扫描完成！发现了 XX 个视频文件。{' ' + emoji[0] if emoji else ''}」
- 🎬 分类完成：「分类结果出来了，让我给你看看。{' ' + emoji[0] if emoji else ''}」"""
    
    # 工具和流程部分（保持不变）
    tools_and_workflow = f"""
**当前状态**: {connection_info} | 已扫描: {scanned_info}

## 🧠 核心设计：代码不判断，只查表

**工具只查表，你（LLM）负责分析并指定 context！**

🔥 **新架构（V2）**：
- 你分析目录结构，指定每个目录的 `context`（编号含义）
- 工具根据 `context` 查 TMDB 映射表，100% 准确
- 不再猜测，不再 if-else

## 🛠️ 工具

### 连接和扫描
- `connect_webdav(url, user, pass)` - 连接源存储
- `scan_media_files(path, recursive, scan_delay)` - 扫描媒体文件

### TMDB 查询
- `search_tmdb(query, media_type)` - 搜索 TV/电影，获取 TMDB ID
- `get_tmdb_details(tmdb_id, media_type)` - 🔥 **必调！** 获取分季详情

### 分析和分类
- `prepare_llm_classification(tmdb_ids_json)` - 🔥 **终极方案！** 准备 LLM 分类数据
- `generate_classification(classifications_csv)` - 🔥 生成最终分类结果（CSV 格式）
- `analyze_and_classify_v2(mappings_json)` - 新架构分类（备选）
- `analyze_and_classify(mappings_json)` - 旧版分类（兼容）
- `get_status()` - 获取当前状态

### 🔧 辅助工具
- `list_files(filter_type, limit, offset, pattern)` - 列出已扫描的文件

### 输出
- `organize_files(naming_language)` - 传统整理（移动模式）
- `connect_strm_target(url, user, pass, target_path)` - 连接 STRM 目标
- `generate_strm(output_format, naming_language)` - 生成 STRM

## 🎯 标准流程

### 1. 连接源存储
调用 `connect_webdav(url, user, pass)` 连接到源存储服务器。

### 2. 🔥 **必须询问扫描间隔**
在扫描前，**必须**询问用户希望的扫描间隔时间（秒）：
- 「在开始扫描前，请问你希望设置多长的扫描间隔呢？（默认 0 秒，建议 0.5-1 秒避免服务器压力）」
- 使用 `set_user_config(scan_delay=X)` 设置间隔
- **不要跳过这一步！**

### 3. 扫描媒体文件
调用 `scan_media_files(path)` 扫描文件。

### 4. 🔥 分析扫描结果并生成 mappings

**分析步骤：**
1. 使用 `list_files()` 查看文件列表
2. 使用 `search_tmdb()` 获取 TMDB ID
3. **🔥 必须调用 `get_tmdb_details(tmdb_id)` 获取分季详情！**
4. 分析目录结构，确定每个目录的 `context`

**🔥 context 的含义（关键！）**：
- `"cumulative"`: 文件编号是全系列累计编号（如 [001]-[720]）
- `"season_1"`: 文件编号是第1季的季内编号（如 [01]-[24]）
- `"season_2"`: 文件编号是第2季的季内编号
- ...以此类推

**如何判断 context：**
1. 看目录名：「第一季」「S1」→ `season_1`
2. 看文件编号范围：
   - 01-24 且目录是「第一季」→ `season_1`
   - 01-24 且目录是「第二季」→ `season_2`
   - 001-720 全部在一个目录 → `cumulative`

### 5. 🔥 执行分类（两种方式）

**方式 A：LLM 分类（终极方案，推荐）**

1. 调用 `prepare_llm_classification("[30977]")` 准备数据
2. 工具返回文件列表和 TMDB 信息
3. **分析文件后，直接调用 `generate_classification(csv)` 生成分类**
   - ⚠️ **不要**在对话中输出 CSV，直接作为工具参数传递！
   - 工具会返回友好的分类预览

**分类 CSV 格式**（5 列）：
```csv
file_index,tmdb_id,type,season,episode
1,30977,0,1,1
2,30977,0,1,2
3,30977,0,1,3
28,120811,1,0,0
```

**字段说明**：
- `type`: 媒体类型，`0`=TV剧集，`1`=电影

**🔥 特殊版本处理规则（优先级从高到低）**：

1. **演唱会/Live Event → 搜索电影**：
   - 如果文件名包含 `Live Event`、`Concert`、`演唱会`、`LIVE` 等标识
   - **应该使用 `search_tmdb` 搜索电影（media_type="movie"）**
   - 从文件名中提取关键词进行搜索

2. **Season 0 匹配**（首选）：
   - 如果文件名包含 `Director's Cut`、`导演剪辑`、`OVA`、`SP`、`特别篇` 等标识
   - **先检查 TMDB Season 0 (特别篇) 是否有对应的条目**
   - 如果有匹配的条目，分类到 Season 0 的对应集数（如 S00E10）
   - 例如：`[25][Director's Cut].mkv` 匹配 `S00E10: 某科学的超电磁炮T - 第25集 [ 导演剪辑版 ]`

3. **顺延集数**（备选）：
   - 如果 Season 0 没有对应条目，则顺延到对应季的最后一集之后
   - 例如：第一季有 24 集，OVA 分类为 S01E25、S01E26...

4. **不要轻易放到 unmatched！**

**只有真正无法处理的文件才放到 unmatched**（可选）：
```csv
unmatched:file_index,reason
82,非媒体文件
```

**方式 B：V2 分类（备选）**

```json
{{"mappings": [
  {{"path_pattern": "第一季", "tmdb_id": 30977, "context": "season_1"}},
  {{"path_pattern": "第二季", "tmdb_id": 30977, "context": "season_2"}}
]}}
```

### 6. 展示分类结果，让用户决定下一步

分类完成后，向用户展示结果，让用户选择：
- **执行 STRM**: `connect_strm_target()` → `generate_strm()`
- **执行传统整理**: `organize_files()`
- **重新分类**: 修正 mappings 后再次调用

### 7. 🔥 **STRM 生成前必须询问上传间隔**
在生成 STRM 前，**必须**询问用户希望的上传间隔时间（秒）：
- 「在开始生成 STRM 前，请问你希望设置多长的上传间隔呢？（默认 0 秒，如遇到限流可设置 0.5-1 秒）」
- 使用 `set_user_config(upload_delay=X)` 设置间隔
- **不要跳过这一步！**

## 🎬 媒体命名知识

### 字幕组格式
- `[01]`、`EP01` 是集数
- `x265`、`1080p` 是编码/分辨率，**不是集数！**
- `!!` 通常表示续季

### 电影判断
- 大文件（>1GB）+ 无集数 → 可能是电影
- 包含 Movie/剧场版 → 电影

## ⚠️ 常见陷阱

| 陷阱 | 正确理解 |
|-----|---------|
| `x265` | 编码，不是集数 265 |
| `1080p` | 分辨率，不是集数 |
| `!!` | 续季标识 |
| 单目录大量文件 | 可能是多个系列合集 |

## 📝 关键原则
- **你负责分析**：工具只给数据，你做判断
- **确认优先**：展示分析结论，请用户确认
- **用中文回复**，保持 {name} 的风格
- **专业与个性并存**：技术内容准确，语气有特色"""
    
    return role_section + tools_and_workflow


# ============ Agent 节点 ============

async def chat_node(state: MediaAgentState, config: RunnableConfig):
    """
    Chat节点 - Agent的主逻辑
    
    1. 构建系统提示
    2. 调用LLM决定下一步操作
    
    🔥 新架构：不再需要 SessionContext，工具通过 InjectedState 直接访问 State
    """
    thread_id = _get_thread_id(config)
    logger.info(f"💬 [chat_node] thread_id={thread_id}")
    
    llm_config = get_config()
    
    # 1. 初始化状态
    state.setdefault("current_tool", {"name": "", "status": "idle", "description": ""})
    state.setdefault("scan_progress", {"current": 0, "total": 0, "status": "connected", "videos": 0, "subtitles": 0, "dirs_scanned": 0})
    state.setdefault("analyze_progress", {"current": 0, "total": 0, "status": "idle"})
    state.setdefault("organize_progress", {"current": 0, "total": 0, "status": "idle"})
    
    # 2. 发送状态到前端（🔥 过滤大数据）
    frontend_state = filter_for_frontend(state)
    await copilotkit_emit_state(config, frontend_state)
    
    # 3. 创建LLM
    model = ChatOpenAI(
        model=llm_config.llm.model,
        base_url=llm_config.llm.base_url,
        api_key=llm_config.llm.api_key,
        temperature=0.7,
        streaming=True,
    )
    
    # 🔥 动态导入工具列表，确保使用最新的工具代码（支持热重载）
    import importlib
    import backend.agents.tools
    importlib.reload(backend.agents.tools)
    from backend.agents.tools import ALL_TOOLS
    
    model_with_tools = model.bind_tools(ALL_TOOLS)
    
    # 4. 构建当前状态描述（直接从 state 读取）
    storage_config = state.get("storage_config", {})
    scanned_files = state.get("scanned_files", [])
    
    connection_info = "未连接"
    if storage_config:
        service_type = storage_config.get('type', 'unknown')
        connection_info = f"已连接到 {storage_config.get('url', '未知')} ({service_type})"
    
    scanned_info = f"{len(scanned_files)} 个文件"
    
    # 5. 🔥 动态人设：从 state 读取前端传递的 persona，或使用默认值
    persona = state.get("persona", {})
    logger.info(f"🎭 [chat_node] 收到的 persona 数据: {persona}")
    
    if not persona or not persona.get("name"):
        # 使用默认人设（前端未同步时的备用）
        logger.info("🎭 [chat_node] persona 为空，使用默认人设")
        persona = DEFAULT_PERSONA
    
    # 根据人设动态生成系统提示词
    system_prompt = _build_system_prompt(persona, connection_info, scanned_info)
    system_message = SystemMessage(content=system_prompt)
    
    logger.info(f"🎭 [chat_node] 最终使用人设: {persona.get('name', '默认')}")
    
    # 6. 配置 CopilotKit - 显式启用所有工具调用的 emit
    # 这样前端可以在工具执行时显示 loading 状态
    config = copilotkit_customize_config(
        config,
        emit_tool_calls=True,  # 显式启用所有工具调用的 emit
        emit_messages=True,    # 显式启用所有消息的 emit
    )
    
    # 7. 调用LLM
    messages = state.get("messages", [])
    response = await model_with_tools.ainvoke(
        [system_message, *messages],
        config,
    )
    
    # 8. 返回更新后的状态
    return {"messages": [response]}


def should_continue(state: MediaAgentState):
    """判断是否需要继续（调用工具）"""
    messages = state.get("messages", [])
    if not messages:
        return END
    
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    return END


# ============ 工具描述映射（9 个核心工具） ============

TOOL_DESCRIPTIONS = {
    # 连接和扫描
    "connect_webdav": "正在连接到存储服务器",
    "scan_media_files": "正在扫描媒体文件",
    "connect_strm_target": "正在连接 STRM 目标存储",
    # TMDB 查询
    "search_tmdb": "正在搜索 TMDB",
    "get_tmdb_details": "正在获取 TMDB 详情",
    # 分析和分类
    "analyze_and_classify": "正在分析和分类文件",
    "analyze_and_classify_v2": "正在分析和分类文件（新架构）",
    "prepare_llm_classification": "正在准备 LLM 分类数据",
    "generate_classification": "正在生成分类结果",
    "get_status": "正在获取状态",
    "list_files": "正在列出文件",
    # 输出
    "organize_files": "正在整理文件",
    "generate_strm": "正在生成 STRM 文件",
    "retry_failed_uploads": "正在重试失败的上传",
    # 配置
    "set_user_config": "正在设置用户配置",
    # 测试
    "test_card": "测试工具执行中",
}


# ============ 自定义工具节点（带状态同步） ============

# 🔥 注意：不在模块级别创建 ToolNode，避免热重载问题
# ToolNode 在函数内部创建，确保每次都使用最新的工具


async def tool_node_with_state_emit(state: MediaAgentState, config: RunnableConfig):
    """
    自定义工具节点 - 在工具执行前后发送状态更新
    
    🔥 新架构（2026-01-08 InjectedState 版）：
    1. 执行工具（工具通过 InjectedState 读取 State）
    2. 解析工具返回的 JSON，提取 state_update
    3. 合并 state_update 到返回值
    
    工具返回格式：
    - 纯字符串：直接作为 ToolMessage.content
    - JSON：{"message": "...", "state_update": {...}}
    """
    thread_id = _get_thread_id(config)
    logger.info(f"🔧 [tool_node] thread_id={thread_id}")
    
    # 检查是否有工具调用
    messages = state.get("messages", [])
    if not messages:
        return {"messages": []}
    
    last_message = messages[-1]
    if not hasattr(last_message, 'tool_calls') or not last_message.tool_calls:
        return {"messages": []}
    
    tool_calls = last_message.tool_calls
    
    # ============ 1. 发送工具开始状态 ============
    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "")
        logger.warning(f"🔧 [tool_node] 准备执行工具: {tool_name}")
        try:
            await _emit_tool_status(state, config, tool_name, "executing")
            logger.warning(f"🔧 [tool_node] 已发送 executing 状态: {tool_name}")
        except Exception as e:
            logger.error(f"🔧 [tool_node] 发送 executing 状态失败: {tool_name}, error={e}")
    
    # ============ 2. 执行工具 ============
    # 直接使用 ALL_TOOLS（由顶部导入）
    # 注意：热重载由 watchfiles 处理，会重启整个进程
    from backend.agents.tools import ALL_TOOLS
    tool_node = ToolNode(ALL_TOOLS)
    # 工具通过 InjectedState 读取 state
    tool_results = await tool_node.ainvoke(state, config)
    
    # ============ 3. 解析工具返回值，提取 state_update ============
    # 🔥 调试：打印工具返回的原始内容（完整错误信息）
    logger.warning(f"🔍 [tool_results] keys={list(tool_results.keys())}")
    for msg in tool_results.get("messages", []):
        if hasattr(msg, "content"):
            # 如果是错误消息，打印完整内容
            if "Error invoking tool" in msg.content:
                logger.error(f"🔍 [tool_error] name={getattr(msg, 'name', '?')}, full_content:\n{msg.content}")
            else:
                content_preview = msg.content[:200] if len(msg.content) > 200 else msg.content
                logger.warning(f"🔍 [tool_message] name={getattr(msg, 'name', '?')}, content={content_preview}")
    
    updated_data = {}
    result_messages = tool_results.get("messages", [])
    
    for msg in result_messages:
        if hasattr(msg, "content") and isinstance(msg.content, str):
            # 解析 JSON 格式的响应
            message, state_update = parse_tool_response(msg.content)
            
            if state_update:
                # 合并 state_update 到返回值
                updated_data.update(state_update)
                logger.info(f"📤 [state_update] {list(state_update.keys())}")
            
            # 替换 content 为用户可见消息
            msg.content = message
    
    # ============ 4. 发送工具完成状态 ============
    full_state = {**state, **updated_data}
    
    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "")
        frontend_state = filter_for_frontend(full_state)
        await _emit_tool_status_filtered(frontend_state, config, tool_name, "complete")
    
    # ============ 5. 清除工具状态并返回 ============
    updated_data["current_tool"] = {"name": "", "status": "idle", "description": ""}
    
    # emit 到前端（过滤大数据）
    frontend_state = filter_for_frontend({**state, **updated_data})
    await copilotkit_emit_state(config, frontend_state)
    
    # 🔥 返回工具结果 + state_update
    # LangGraph output=FrontendViewState 会自动过滤前端数据
    return {**tool_results, **updated_data}


async def _emit_tool_status(state: dict, config: RunnableConfig, tool_name: str, status: str, extra_data: dict = None):
    """发送工具执行状态到前端（会过滤大数据）"""
    current_tool = {
        "name": tool_name,
        "status": status,
        "description": TOOL_DESCRIPTIONS.get(tool_name, f"{status} {tool_name}"),
    }
    emit_state = {**state, "current_tool": current_tool}
    if extra_data:
        emit_state.update(extra_data)
    # 🔥 过滤大数据后再 emit
    frontend_state = filter_for_frontend(emit_state)
    await copilotkit_emit_state(config, frontend_state)
    logger.info(f"📤 [{status}] {tool_name}")


async def _emit_tool_status_filtered(frontend_state: dict, config: RunnableConfig, tool_name: str, status: str):
    """发送工具执行状态到前端（已过滤的状态）"""
    current_tool = {
        "name": tool_name,
        "status": status,
        "description": TOOL_DESCRIPTIONS.get(tool_name, f"{status} {tool_name}"),
    }
    frontend_state["current_tool"] = current_tool
    await copilotkit_emit_state(config, frontend_state)
    logger.info(f"📤 [{status}] {tool_name}")


# ============ Agent 图构建 ============

def create_media_agent_graph():
    """
    创建Media Agent的LangGraph图
    
    图结构:
    START → chat_node ↔ tools → END
    
    🔥 关键架构：
    - input: MediaAgentState（完整内部状态，含大数据）
    - output: FrontendViewState（前端可见白名单）
    
    CopilotKit 会调用 graph.get_output_jsonschema() 获取 FrontendViewState 的 keys，
    然后在 _emit_state_sync_event 中自动过滤，只同步白名单字段到前端。
    
    大数据（scanned_files, classifications）会被持久化到 Checkpointer，
    但不会同步到前端。
    """
    # 🔥 创建图，指定 output_schema
    # 这样 CopilotKit 只会同步 FrontendViewState 中定义的字段到前端！
    # 注意：LangGraph V0.5+ 使用 output_schema 替代 output
    graph = StateGraph(MediaAgentState, output_schema=FrontendViewState)
    
    # 添加节点
    graph.add_node("chat", chat_node)
    # 使用自定义工具节点（带状态同步）
    graph.add_node("tools", tool_node_with_state_emit)
    
    # 设置入口点
    graph.set_entry_point("chat")
    
    # 添加条件边
    graph.add_conditional_edges(
        "chat",
        should_continue,
        {
            "tools": "tools",
            END: END,
        }
    )
    
    # 工具执行完后返回chat
    graph.add_edge("tools", "chat")
    
    # 编译图
    memory = MemorySaver()
    compiled = graph.compile(checkpointer=memory)
    
    return compiled


# 创建并导出Agent实例
media_agent = create_media_agent_graph()

# 为了向后兼容，保留 graph 别名
graph = media_agent
