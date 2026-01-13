"""
服务管理模块

🔥 新架构（2026-01-08）：
- 提供从 State 配置获取服务实例的函数
- 使用简单的全局缓存避免重复创建
- 工具通过此模块获取服务，不再依赖 SessionContext

使用方式：
    from backend.agents.services import get_storage_service, get_strm_target_service
    
    @tool
    def my_tool(state: Annotated[dict, InjectedState]) -> str:
        service = get_storage_service(state)
        if not service:
            return make_tool_response("❌ 请先连接存储服务器")
        # ... 使用 service ...
"""

import hashlib
import logging
from typing import Dict, Any, Optional

from backend.services.storage_base import StorageService
from backend.services.storage_factory import create_storage_service_sync

_logger = logging.getLogger(__name__)

# 全局服务缓存：{config_hash: StorageService}
_storage_cache: Dict[str, StorageService] = {}
_strm_cache: Dict[str, StorageService] = {}


def _config_hash(config: Dict[str, Any]) -> str:
    """计算配置的哈希值（用于缓存键）"""
    # 只使用关键字段计算哈希
    key_fields = ["url", "username", "password"]
    key_str = "|".join(str(config.get(k, "")) for k in key_fields)
    return hashlib.md5(key_str.encode()).hexdigest()[:16]


def get_storage_service(state: Dict[str, Any]) -> Optional[StorageService]:
    """
    从 State 获取存储服务实例
    
    会自动缓存服务实例，配置相同时复用。
    
    Args:
        state: LangGraph State（包含 storage_config）
    
    Returns:
        StorageService 实例，如果配置无效则返回 None
    """
    config = state.get("storage_config", {})
    if not config or not config.get("url"):
        return None
    
    # 检查缓存
    cache_key = _config_hash(config)
    if cache_key in _storage_cache:
        return _storage_cache[cache_key]
    
    # 创建新服务
    try:
        service = create_storage_service_sync(
            url=config.get("url", ""),
            username=config.get("username", ""),
            password=config.get("password", ""),
            base_path="/",  # 固定为根目录，实际路径由工具控制
        )
        _storage_cache[cache_key] = service
        _logger.info(f"📦 创建存储服务: {config.get('url')}")
        return service
    except Exception as e:
        _logger.warning(f"创建存储服务失败: {e}")
        return None


def get_strm_target_service(state: Dict[str, Any]) -> Optional[StorageService]:
    """
    从 State 获取 STRM 目标存储服务实例
    
    会自动缓存服务实例，配置相同时复用。
    
    Args:
        state: LangGraph State（包含 strm_target_config）
    
    Returns:
        StorageService 实例，如果配置无效则返回 None
    """
    config = state.get("strm_target_config", {})
    if not config or not config.get("url"):
        return None
    
    # 检查缓存
    cache_key = _config_hash(config)
    if cache_key in _strm_cache:
        return _strm_cache[cache_key]
    
    # 创建新服务
    try:
        service = create_storage_service_sync(
            url=config.get("url", ""),
            username=config.get("username", ""),
            password=config.get("password", ""),
            base_path="/",
        )
        _strm_cache[cache_key] = service
        _logger.info(f"📦 创建 STRM 目标服务: {config.get('url')}")
        return service
    except Exception as e:
        _logger.warning(f"创建 STRM 目标服务失败: {e}")
        return None


def cache_storage_service(config: Dict[str, Any], service: StorageService):
    """
    缓存存储服务实例
    
    在 connect_webdav 中使用，确保创建的服务被缓存。
    
    Args:
        config: 存储配置（包含 url, username, password）
        service: 已创建的服务实例
    """
    cache_key = _config_hash(config)
    _storage_cache[cache_key] = service
    _logger.info(f"📦 缓存存储服务: {config.get('url')} (key={cache_key})")


def cache_strm_service(config: Dict[str, Any], service: StorageService):
    """
    缓存 STRM 目标存储服务实例
    
    在 connect_strm_target 中使用，确保创建的服务被缓存。
    
    Args:
        config: 存储配置（包含 url, username, password）
        service: 已创建的服务实例
    """
    cache_key = _config_hash(config)
    _strm_cache[cache_key] = service
    _logger.info(f"📦 缓存 STRM 目标服务: {config.get('url')} (key={cache_key})")


def clear_service_cache():
    """清除所有服务缓存（用于测试）"""
    global _storage_cache, _strm_cache
    _storage_cache = {}
    _strm_cache = {}
    _logger.info("🧹 清除服务缓存")
