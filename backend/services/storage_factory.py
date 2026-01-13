"""
存储服务工厂

自动检测服务器类型并创建合适的存储服务实例。
"""

import asyncio
from typing import Optional
from urllib.parse import urlparse, unquote

import httpx

from backend.config import get_config
from backend.services.storage_base import StorageService
from backend.services.alist_service import AlistService, detect_alist_server
from backend.services.webdav_service import WebDAVService


async def detect_server_type(url: str) -> str:
    """
    检测服务器类型
    
    Args:
        url: 服务器地址
        
    Returns:
        'alist' 或 'webdav'
    """
    base_url = url.rstrip('/')
    
    # 先检测是否是Alist
    if await detect_alist_server(base_url):
        return "alist"
    
    # 检测是否支持WebDAV
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 尝试OPTIONS请求检测WebDAV支持
            response = await client.request("OPTIONS", f"{base_url}/dav/")
            
            # 检查DAV头
            dav_header = response.headers.get("DAV", "")
            if "1" in dav_header or "2" in dav_header:
                return "webdav"
                
            # 即使没有DAV头，如果返回200也可能支持
            if response.status_code == 200:
                return "webdav"
    except Exception:
        pass
    
    # 默认尝试WebDAV
    return "webdav"


async def create_storage_service(
    url: str,
    username: str,
    password: str,
    base_path: str = "/",
    force_type: Optional[str] = None
) -> StorageService:
    """
    创建存储服务实例
    
    会自动检测服务器类型并选择合适的实现。
    
    Args:
        url: 服务器地址
        username: 用户名
        password: 密码
        base_path: 基础路径
        force_type: 强制指定类型 ('alist' 或 'webdav')
        
    Returns:
        StorageService实例
    """
    # 解析URL
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # 如果URL包含路径，将其作为base_path
    if parsed.path and parsed.path != "/":
        url_path = unquote(parsed.path)
        if base_path == "/":
            base_path = url_path
        else:
            # 合并路径
            base_path = f"{url_path.rstrip('/')}/{base_path.lstrip('/')}"
    
    # 确定服务类型
    if force_type:
        server_type = force_type
    else:
        server_type = await detect_server_type(base_url)
    
    # 创建服务实例
    if server_type == "alist":
        return AlistService(
            url=base_url,
            username=username,
            password=password,
            base_path=base_path,
        )
    else:
        return WebDAVService(
            url=base_url,
            username=username,
            password=password,
            base_path=base_path,
        )


def create_storage_service_sync(
    url: str,
    username: str,
    password: str,
    base_path: str = "/",
    force_type: Optional[str] = None,
) -> StorageService:
    """
    同步版本的创建存储服务
    
    用于无法使用async的场景
    
    Args:
        url: 存储服务地址
        username: 用户名
        password: 密码
        base_path: 基础路径
        force_type: 强制指定类型 ("alist" 或 "webdav")
    
    🔥 注意：底层不再使用 request_delay 参数
    扫描延迟由 scan_delay 控制，上传延迟由 upload_delay 控制
    """
    # 获取配置
    config = get_config()
    storage_config = config.storage
    
    # 解析URL
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    
    # 如果URL包含路径，将其作为base_path
    if parsed.path and parsed.path != "/":
        url_path = unquote(parsed.path)
        if base_path == "/":
            base_path = url_path
        else:
            base_path = f"{url_path.rstrip('/')}/{base_path.lstrip('/')}"
    
    # 同步检测服务器类型
    server_type = force_type
    if not server_type:
        try:
            # 简单同步检测
            with httpx.Client(timeout=10.0) as client:
                # 检测Alist
                try:
                    response = client.get(f"{base_url}/api/public/settings")
                    if response.status_code == 200 and "code" in response.json():
                        server_type = "alist"
                except Exception:
                    pass
                
                if not server_type:
                    server_type = "webdav"
        except Exception:
            server_type = "webdav"
    
    # 创建服务实例
    if server_type == "alist":
        return AlistService(
            url=base_url,
            username=username,
            password=password,
            base_path=base_path,
            cache_ttl=storage_config.cache_ttl if storage_config.cache_enabled else 0,
            cache_size=storage_config.cache_size,
        )
    else:
        return WebDAVService(
            url=base_url,
            username=username,
            password=password,
            base_path=base_path,
        )

