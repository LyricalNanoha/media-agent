"""
连接相关工具

提供存储服务器连接和状态查询功能

🔥 新架构（2026-01-08）：
- 工具通过 InjectedState 直接访问 State
- 工具通过 get_storage_service(state) 获取服务实例
- 返回通用 JSON 格式：{"message": "...", "state_update": {...}}

路径设计：
- storage_config.scan_path: 从 URL 解析，用于扫描
- storage_config.target_path: 传统整理的目标路径
- strm_target_config.target_path: STRM 输出路径
"""

from typing import Dict, Any
from typing_extensions import Annotated
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from backend.services.storage_factory import create_storage_service_sync
from backend.agents.tool_response import make_tool_response
from backend.agents.services import get_storage_service, get_strm_target_service, cache_storage_service, cache_strm_service
from backend.agents.state import MediaAgentState


@tool
def connect_webdav(
    url: str, 
    username: str, 
    password: str, 
    target_path: str = "",
    state: Annotated[dict, InjectedState] = None
) -> str:
    """
    连接到存储服务器（支持Alist和标准WebDAV）
    
    会自动检测服务器类型：
    - Alist服务器：使用REST API（避免WAF拦截）
    - 标准WebDAV：使用WebDAV协议
    
    Args:
        url: 服务器地址，例如 http://192.168.1.1:5244 或带路径 http://192.168.1.1:5244/115/剧集
             URL 中的路径会作为扫描路径（scan_path）
        username: 用户名
        password: 密码
        target_path: 传统整理的目标路径（可选），如 "/kuake/整理好"
    
    Returns:
        JSON: {"message": "...", "state_update": {"storage_config": {...}, "scanned_files": []}}
    """
    try:
        from urllib.parse import urlparse, unquote
        
        # 清理URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
        
        # 解析URL，提取 scan_path
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        scan_path = unquote(parsed.path) if parsed.path else "/"
        
        # 确保 scan_path 格式正确
        if not scan_path:
            scan_path = "/"
        if not scan_path.startswith('/'):
            scan_path = '/' + scan_path
        
        # 使用工厂函数创建存储服务（自动检测类型）
        service = create_storage_service_sync(
            url=base_url,
            username=username,
            password=password,
            base_path="/",  # 固定为根目录
        )
        
        # 🔥 立即验证连接（触发登录），确保服务已认证
        # 对于 Alist 服务，这会调用 _login_sync() 获取 token
        try:
            # 尝试列出根目录来验证连接和认证
            service.list_directory("/")
        except Exception as auth_error:
            return make_tool_response(
                f"❌ 连接失败: 认证错误 - {str(auth_error)}\n\n请检查用户名和密码是否正确。",
                {"storage_config": {}}
            )
        
        # 构建新的 storage_config
        new_storage_config = {
            "url": base_url,
            "scan_path": scan_path,
            "target_path": target_path.rstrip('/') if target_path else "",
            "username": username,
            "password": password,
            "type": service.service_type,
            "connected": True,
        }
        
        # 🔥 缓存服务实例，确保后续工具可以复用
        cache_storage_service(new_storage_config, service)
        
        # 构建返回消息
        service_name = "Alist API" if service.service_type == "alist" else "WebDAV"
        message = f"✅ 成功连接到存储服务器!\n\n"
        message += f"• 服务器: {base_url}\n"
        message += f"• 连接方式: {service_name}\n"
        message += f"• 用户: {username}\n"
        message += f"• 扫描路径: {scan_path}\n"
        if target_path:
            message += f"• 整理路径: {target_path}\n"
        
        # 返回通用 JSON 格式
        return make_tool_response(message, {
            "storage_config": new_storage_config,
            "scanned_files": [],  # 清空之前的扫描结果
        })
        
    except Exception as e:
        return make_tool_response(
            f"❌ 连接失败: {str(e)}\n\n请检查：\n1. 服务器地址是否正确\n2. 用户名密码是否正确\n3. 服务器是否可访问",
            {"storage_config": {}}  # 清空配置
        )


@tool
def set_user_config(
    scan_delay: float = -1,
    upload_delay: float = -1,
    naming_language: str = "",
    use_copy: bool = None,
    state: Annotated[dict, InjectedState] = None
) -> str:
    """
    设置通用配置
    
    这些配置会被 scan_media_files、generate_strm、organize_files 等工具使用。
    只需要设置一次，后续工具会自动读取。
    
    注意：路径配置请在各自的连接工具中设置：
    - connect_webdav(target_path="..."): 传统整理的目标路径
    - connect_strm_target(target_path="..."): STRM 输出路径
    
    Args:
        scan_delay: 扫描延迟（秒），-1 表示不修改
        upload_delay: 上传延迟（秒），-1 表示不修改
        naming_language: 命名语言（zh/en），空字符串表示不修改
        use_copy: 整理时是否使用复制模式，None 表示不修改
    
    Returns:
        JSON: {"message": "...", "state_update": {"user_config": {...}}}
    """
    # 获取当前配置
    current_config = state.get("user_config", {}) if state else {}
    
    # 默认值
    new_config = {
        "scan_delay": current_config.get("scan_delay", 0.0),
        "upload_delay": current_config.get("upload_delay", 0.0),
        "naming_language": current_config.get("naming_language", "zh"),
        "use_copy": current_config.get("use_copy", True),
    }
    
    changes = []
    
    if scan_delay >= 0:
        new_config["scan_delay"] = scan_delay
        changes.append(f"• 扫描延迟: {scan_delay}s")
    
    if upload_delay >= 0:
        new_config["upload_delay"] = upload_delay
        changes.append(f"• 上传延迟: {upload_delay}s")
    
    if naming_language:
        new_config["naming_language"] = naming_language
        changes.append(f"• 命名语言: {naming_language}")
    
    if use_copy is not None:
        new_config["use_copy"] = use_copy
        changes.append(f"• 整理模式: {'复制' if use_copy else '移动'}")
    
    if changes:
        message = "✅ 用户配置已更新\n\n"
        message += "\n".join(changes)
    else:
        message = "⚠️ 未指定任何配置"
    
    return make_tool_response(message, {"user_config": new_config})


@tool
def get_connection_status(
    state: Annotated[dict, InjectedState] = None
) -> str:
    """
    获取当前存储服务连接状态
    
    Returns:
        JSON: {"message": "...", "state_update": {}}
    """
    message = ""
    
    # 从 State 获取配置
    storage_config = state.get("storage_config", {}) if state else {}
    strm_target_config = state.get("strm_target_config", {}) if state else {}
    user_config = state.get("user_config", {}) if state else {}
    scanned_files = state.get("scanned_files", []) if state else []
    
    # 源存储状态
    if storage_config.get("connected"):
        service_type = storage_config.get('type', 'unknown')
        service_name = "Alist API" if service_type == "alist" else "WebDAV"
        
        message += f"📁 源存储\n"
        message += f"• 服务器: {storage_config.get('url', '未知')}\n"
        message += f"• 连接方式: {service_name}\n"
        message += f"• 扫描路径: {storage_config.get('scan_path', '/')}\n"
        if storage_config.get('target_path'):
            message += f"• 整理路径: {storage_config.get('target_path')}\n"
        message += f"• 已扫描文件: {len(scanned_files)} 个\n"
    else:
        message += "📁 源存储: 未连接\n"
    
    message += "\n"
    
    # STRM 目标存储状态
    if strm_target_config.get("connected"):
        message += f"📤 STRM 目标\n"
        message += f"• 服务器: {strm_target_config.get('url', '未知')}\n"
        message += f"• 输出路径: {strm_target_config.get('target_path', '/')}\n"
    else:
        message += "📤 STRM 目标: 未连接\n"
    
    message += "\n"
    
    # 通用配置
    message += f"⚙️ 配置\n"
    message += f"• 命名语言: {user_config.get('naming_language', 'zh')}\n"
    message += f"• 整理模式: {'复制' if user_config.get('use_copy', True) else '移动'}\n"
    message += f"• 扫描延迟: {user_config.get('scan_delay', 0.0)}s\n"
    message += f"• 上传延迟: {user_config.get('upload_delay', 0.0)}s\n"
    
    # 返回只有消息，不更新 State
    return make_tool_response(message)
