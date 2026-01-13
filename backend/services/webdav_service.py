"""
WebDAV服务

连接和操作标准WebDAV服务器
"""

import os
import time
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
from urllib.parse import urljoin, quote

import httpx
from webdav3.client import Client as WebDAVClient
from webdav3.exceptions import WebDavException

from backend.config import get_config
from backend.services.storage_base import StorageService, FileInfo

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # 秒


class WebDAVService(StorageService):
    """标准WebDAV服务"""
    
    @property
    def service_type(self) -> str:
        return "webdav"
    
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        base_path: str = "/"
    ):
        """
        初始化WebDAV服务
        
        Args:
            url: WebDAV服务器地址
            username: 用户名
            password: 密码
            base_path: 基础路径
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip('/') or '/'
        
        self._client: Optional[WebDAVClient] = None
        self._http_client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> WebDAVClient:
        """获取WebDAV客户端"""
        if self._client is None:
            # 构建WebDAV URL - Alist的WebDAV路径是 /dav
            # 如果URL已经包含/dav，不要重复添加
            webdav_url = self.url
            if not webdav_url.endswith('/dav'):
                webdav_url = f"{webdav_url}/dav"
            
            options = {
                'webdav_hostname': webdav_url,
                'webdav_login': self.username,
                'webdav_password': self.password,
                'webdav_timeout': 30,
            }
            self._client = WebDAVClient(options)
        return self._client
    
    @property
    def http_client(self) -> httpx.AsyncClient:
        """获取异步HTTP客户端"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                auth=(self.username, self.password),
                timeout=30.0,
                follow_redirects=True,
            )
        return self._http_client
    
    async def close(self):
        """关闭客户端连接"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    def _full_path(self, path: str) -> str:
        """获取完整路径"""
        if path.startswith('/'):
            return path
        return f"{self.base_path}/{path}".replace('//', '/')
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接
        
        Returns:
            Dict: 包含success和message的字典
        """
        try:
            # 尝试列出根目录
            webdav_url = f"{self.url}/dav/"
            response = await self.http_client.request(
                "PROPFIND",
                webdav_url,
                headers={"Depth": "0"},
            )
            
            if response.status_code in (200, 207):
                return {
                    "success": True,
                    "message": "连接成功",
                    "server_info": {
                        "url": self.url,
                        "status_code": response.status_code,
                    }
                }
            else:
                return {
                    "success": False,
                    "message": f"连接失败: HTTP {response.status_code}",
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接失败: {str(e)}",
            }
    
    def list_directory(self, path: str = "/") -> List[FileInfo]:
        """
        列出目录内容（同步，使用httpx，带重试）
        
        Args:
            path: 目录路径
            
        Returns:
            List[FileInfo]: 文件信息列表
        """
        import httpx
        
        full_path = self._full_path(path)
        
        # 构建WebDAV URL
        # Alist WebDAV 格式: http://host:port/dav/路径
        webdav_path = full_path
        if not webdav_path.startswith('/'):
            webdav_path = '/' + webdav_path
        
        webdav_url = f"{self.url}/dav{quote(webdav_path)}"
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                # 使用同步HTTP请求
                with httpx.Client(
                    auth=(self.username, self.password),
                    timeout=30.0,
                    follow_redirects=True,
                ) as client:
                    response = client.request(
                        "PROPFIND",
                        webdav_url,
                        headers={"Depth": "1"},
                    )
                    
                    if response.status_code in (200, 207):
                        return self._parse_propfind_response(response.text, full_path)
                    elif response.status_code == 404:
                        # 404可能是临时问题，重试
                        last_error = f"HTTP 404: Not Found"
                    else:
                        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")
                    
            except Exception as e:
                last_error = str(e)
            
            # 等待后重试
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        
        raise Exception(f"列出目录失败（重试{MAX_RETRIES}次后）: {last_error}")
    
    async def list_directory_async(self, path: str = "/") -> List[FileInfo]:
        """
        列出目录内容（异步，带重试）
        
        Args:
            path: 目录路径
            
        Returns:
            List[FileInfo]: 文件信息列表
        """
        import asyncio
        
        full_path = self._full_path(path)
        webdav_url = f"{self.url}/dav{quote(full_path)}"
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.http_client.request(
                    "PROPFIND",
                    webdav_url,
                    headers={"Depth": "1"},
                )
                
                if response.status_code in (200, 207):
                    return self._parse_propfind_response(response.text, full_path)
                elif response.status_code == 404:
                    # 404可能是临时问题，重试
                    last_error = f"HTTP 404: Not Found"
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except Exception as e:
                last_error = str(e)
            
            # 等待后重试
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        
        raise Exception(f"列出目录失败（重试{MAX_RETRIES}次后）: {last_error}")
    
    def _parse_propfind_response(self, xml_text: str, base_path: str) -> List[FileInfo]:
        """解析PROPFIND响应"""
        import xml.etree.ElementTree as ET
        
        result = []
        
        try:
            root = ET.fromstring(xml_text)
            
            # WebDAV命名空间
            ns = {'d': 'DAV:'}
            
            for response in root.findall('.//d:response', ns):
                href = response.find('d:href', ns)
                if href is None:
                    continue
                
                path = href.text or ''
                # 解码URL
                from urllib.parse import unquote
                path = unquote(path)
                
                # 移除/dav前缀
                if '/dav' in path:
                    path = path.split('/dav', 1)[-1]
                
                # 跳过基础路径本身
                if path.rstrip('/') == base_path.rstrip('/'):
                    continue
                
                # 检查是否为目录
                resourcetype = response.find('.//d:resourcetype', ns)
                is_dir = resourcetype is not None and resourcetype.find('d:collection', ns) is not None
                
                # 获取文件大小
                size_elem = response.find('.//d:getcontentlength', ns)
                size = int(size_elem.text) if size_elem is not None and size_elem.text else None
                
                # 获取修改时间
                modified_elem = response.find('.//d:getlastmodified', ns)
                modified = modified_elem.text if modified_elem is not None else None
                
                info = FileInfo(
                    path=path,
                    name=os.path.basename(path.rstrip('/')),
                    is_dir=is_dir,
                    size=size,
                    modified=modified,
                )
                result.append(info)
            
        except ET.ParseError:
            pass
        
        return result
    
    async def scan_recursive(
        self,
        path: str = "/",
        max_depth: Optional[int] = None,
        callback: Optional[callable] = None
    ) -> AsyncGenerator[FileInfo, None]:
        """
        递归扫描目录
        
        Args:
            path: 起始路径
            max_depth: 最大深度
            callback: 进度回调函数
            
        Yields:
            FileInfo: 文件信息
        """
        from backend.utils.file_filter import get_file_filter
        
        file_filter = get_file_filter()
        
        async def scan(current_path: str, depth: int):
            if max_depth is not None and depth > max_depth:
                return
            
            try:
                items = await self.list_directory_async(current_path)
                
                for item in items:
                    # 检查是否应该排除
                    if file_filter.should_exclude(item.path):
                        continue
                    
                    if item.is_dir:
                        # 递归扫描子目录
                        async for sub_item in scan(item.path, depth + 1):
                            yield sub_item
                    else:
                        # 检查是否为视频文件
                        if file_filter.is_video_file(item.name):
                            if callback:
                                callback(item)
                            yield item
            except Exception as e:
                print(f"扫描 {current_path} 失败: {e}")
        
        async for item in scan(path, 0):
            yield item
    
    def move_file(self, source: str, destination: str) -> bool:
        """
        移动/重命名文件
        
        Args:
            source: 源路径
            destination: 目标路径
            
        Returns:
            bool: 是否成功
        """
        src_path = self._full_path(source)
        dst_path = self._full_path(destination)
        
        try:
            self.client.move(src_path, dst_path, overwrite=False)
            return True
        except WebDavException as e:
            raise Exception(f"移动文件失败: {str(e)}")
    
    def create_directory(self, path: str) -> bool:
        """
        创建目录
        
        Args:
            path: 目录路径
            
        Returns:
            bool: 是否成功
        """
        full_path = self._full_path(path)
        
        try:
            self.client.mkdir(full_path)
            return True
        except WebDavException as e:
            # 目录已存在不算错误
            if "405" in str(e):
                return True
            raise Exception(f"创建目录失败: {str(e)}")
    
    def exists(self, path: str) -> bool:
        """
        检查路径是否存在
        
        Args:
            path: 路径
            
        Returns:
            bool: 是否存在
        """
        full_path = self._full_path(path)
        
        try:
            return self.client.check(full_path)
        except WebDavException:
            return False
    
    def get_file_content(self, path: str) -> Optional[str]:
        """
        读取文件内容（用于读取字幕等小文件）
        
        Args:
            path: 文件路径
            
        Returns:
            文件内容，如果失败返回 None
        """
        full_path = self._full_path(path)
        webdav_url = f"{self.url}/dav{quote(full_path)}"
        
        try:
            with httpx.Client(
                auth=(self.username, self.password),
                timeout=30.0,
            ) as client:
                response = client.get(webdav_url)
                if response.status_code == 200:
                    try:
                        return response.text
                    except UnicodeDecodeError:
                        return response.content.decode('gbk', errors='replace')
                return None
        except Exception as e:
            logger.error(f"读取文件内容失败 {path}: {e}")
            return None
    
    def put_file_content(self, path: str, content: str) -> bool:
        """
        上传文本内容到文件（用于创建 STRM 等小文件）
        
        Args:
            path: 目标文件路径
            content: 文本内容
            
        Returns:
            是否成功
        """
        full_path = self._full_path(path)
        webdav_url = f"{self.url}/dav{quote(full_path)}"
        
        try:
            with httpx.Client(
                auth=(self.username, self.password),
                timeout=30.0,
            ) as client:
                response = client.put(
                    webdav_url,
                    content=content.encode('utf-8'),
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                )
                return response.status_code in (200, 201, 204)
        except Exception as e:
            raise Exception(f"上传文件失败: {str(e)}")
    
    async def put_file_content_async(self, path: str, content: str) -> bool:
        """
        异步上传文本内容到文件
        
        Args:
            path: 目标文件路径
            content: 文本内容
            
        Returns:
            是否成功
        """
        full_path = self._full_path(path)
        webdav_url = f"{self.url}/dav{quote(full_path)}"
        
        try:
            response = await self.http_client.put(
                webdav_url,
                content=content.encode('utf-8'),
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
            return response.status_code in (200, 201, 204)
        except Exception as e:
            return False
    
    async def create_directory_async(self, path: str) -> bool:
        """
        异步创建目录（使用 WebDAV MKCOL）
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        full_path = self._full_path(path)
        webdav_url = f"{self.url}/dav{quote(full_path)}"
        
        try:
            response = await self.http_client.request(
                "MKCOL",
                webdav_url,
            )
            # 201 Created, 405 Already exists
            return response.status_code in (200, 201, 405)
        except Exception as e:
            return False  # 目录可能已存在
    
    def get_file_url(self, path: str) -> Optional[str]:
        """
        获取文件的直接访问 URL
        
        对于标准 WebDAV，返回 WebDAV URL（可能需要认证）
        
        Args:
            path: 文件路径
            
        Returns:
            文件的 WebDAV URL
        """
        full_path = self._full_path(path)
        # 标准 WebDAV 没有无需认证的直接 URL，返回 WebDAV 路径
        return f"{self.url}/dav{full_path}"


# 从数据库模型创建服务实例
def create_webdav_service_from_connection(connection) -> WebDAVService:
    """
    从数据库连接模型创建WebDAV服务
    
    Args:
        connection: WebDAVConnection数据库模型实例
        
    Returns:
        WebDAVService: WebDAV服务实例
    """
    return WebDAVService(
        url=connection.url,
        username=connection.username,
        password=connection.password,
        base_path=connection.base_path,
    )

