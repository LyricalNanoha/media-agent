"""
Alist REST API 服务

使用Alist的REST API进行文件操作，避免WebDAV被WAF拦截的问题。

Alist API文档: https://alist.nn.ci/guide/api/

风控策略：
- 请求间隔限制（避免115等网盘风控）
- 目录缓存（减少重复请求）
- 智能重试（遇到限流时自动等待）
"""

import os
import time
import logging
import asyncio
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from collections import OrderedDict
from threading import Lock

import httpx

logger = logging.getLogger(__name__)

from backend.services.storage_base import StorageService, FileInfo, is_video_file

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# 🔥 默认请求限速配置
# 注意：delay 逻辑已简化，底层不再使用 request_delay
# 扫描/上传的延迟由 user_config 中的 scan_delay/upload_delay 控制
DEFAULT_REQUEST_DELAY = 0.0  # 底层不等待，延迟由上层工具控制
DEFAULT_RATE_LIMIT_DELAY = 5.0  # 遇到限流时的等待时间（秒）

# 缓存配置
DEFAULT_CACHE_TTL = 300  # 缓存有效期（秒）
DEFAULT_CACHE_SIZE = 100  # 最大缓存条目数

# 🔥 HTTP 超时配置
HTTP_TIMEOUT = 30.0  # 单个请求超时时间（秒）


class LRUCache:
    """简单的LRU缓存实现"""
    
    def __init__(self, max_size: int = DEFAULT_CACHE_SIZE, ttl: int = DEFAULT_CACHE_TTL):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            if key not in self.cache:
                return None
            
            value, timestamp = self.cache[key]
            
            # 检查是否过期
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                return None
            
            # 移动到末尾（最近使用）
            self.cache.move_to_end(key)
            return value
    
    def set(self, key: str, value: Any):
        """设置缓存值"""
        with self.lock:
            # 如果已存在，先删除
            if key in self.cache:
                del self.cache[key]
            
            # 如果缓存已满，删除最旧的
            while len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
            
            self.cache[key] = (value, time.time())
    
    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
    
    def invalidate(self, key: str):
        """使某个缓存失效"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]


class RateLimiter:
    """简单的请求限速器"""
    
    def __init__(self, min_interval: float = DEFAULT_REQUEST_DELAY):
        self.min_interval = min_interval
        self.last_request_time = 0.0
        self.lock = Lock()
    
    def wait(self):
        """同步等待，确保请求间隔"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
    
    async def wait_async(self):
        """异步等待，确保请求间隔"""
        now = time.time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()


class AlistService(StorageService):
    """
    Alist REST API 服务
    
    使用Alist的REST API而不是WebDAV，避免WAF拦截问题。
    """
    
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        base_path: str = "/",
        cache_ttl: int = DEFAULT_CACHE_TTL,
        cache_size: int = DEFAULT_CACHE_SIZE,
    ):
        """
        初始化Alist服务
        
        Args:
            url: Alist服务器地址，如 http://192.168.1.1:5244
            username: 用户名
            password: 密码
            base_path: 基础路径，如 /115/剧集/动漫
            cache_ttl: 缓存有效期（秒）
            cache_size: 最大缓存条目数
        
        🔥 注意：底层不再使用 request_delay 参数
        扫描延迟由 scan_delay 控制，上传延迟由 upload_delay 控制
        """
        self.url = url.rstrip('/')
        self.username = username
        self.password = password
        self.base_path = base_path.rstrip('/') or '/'
        if not self.base_path.startswith('/'):
            self.base_path = '/' + self.base_path
        
        self._token: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None
        
        # 限速器（默认不等待）和缓存
        self._rate_limiter = RateLimiter(min_interval=0.0)
        self._cache = LRUCache(max_size=cache_size, ttl=cache_ttl)
    
    @property
    def service_type(self) -> str:
        return "alist"
    
    def _get_sync_client(self) -> httpx.Client:
        """获取同步HTTP客户端"""
        if self._sync_client is None:
            # 🔥 详细的超时配置，避免无限等待
            timeout = httpx.Timeout(
                connect=10.0,   # 连接超时
                read=30.0,      # 读取超时
                write=30.0,     # 写入超时
                pool=10.0,      # 连接池超时
            )
            self._sync_client = httpx.Client(
                timeout=timeout,
                follow_redirects=True,
            )
        return self._sync_client
    
    @property
    def http_client(self) -> httpx.AsyncClient:
        """获取异步HTTP客户端"""
        if self._http_client is None:
            # 🔥 详细的超时配置，避免无限等待
            # 字幕文件可能较大，需要更长的超时时间
            timeout = httpx.Timeout(
                connect=10.0,   # 连接超时
                read=60.0,      # 读取超时（增加到 60 秒）
                write=60.0,     # 写入超时（增加到 60 秒）
                pool=10.0,      # 连接池超时
            )
            self._http_client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
            )
        return self._http_client
    
    async def close(self):
        """关闭客户端连接"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None
    
    def put_file_content(self, path: str, content: str) -> bool:
        """
        上传文本内容到文件（用于创建 STRM 等小文件）
        
        Args:
            path: 目标文件路径
            content: 文本内容
            
        Returns:
            是否成功
        """
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        full_path = self._full_path(path)
        client = self._get_sync_client()
        
        self._rate_limiter.wait()
        
        try:
            from urllib.parse import quote
            
            response = client.put(
                f"{self.url}/api/fs/put",
                headers={
                    "Authorization": self._token,
                    "File-Path": quote(full_path, safe=''),
                    "Content-Type": "application/octet-stream",
                },
                content=content.encode('utf-8'),
                timeout=30.0,  # 🔥 显式设置超时
            )
            
            if response.status_code == 200:
                data = response.json()
                code = data.get("code")
                if code == 200:
                    return True
                else:
                    logger.warning(f"上传文件返回非200状态码 {path}: code={code}, message={data.get('message')}")
                    return False
            else:
                logger.warning(f"上传文件 HTTP 错误 {path}: status={response.status_code}")
                return False
        except Exception as e:
            logger.error(f"上传文件失败 {path}: {e}")
            return False
    
    async def put_file_content_async(self, path: str, content: str) -> bool:
        """
        异步上传文本内容到文件
        
        Args:
            path: 目标文件路径
            content: 文本内容
            
        Returns:
            是否成功
        """
        # 确保已登录
        if not self._token:
            if not await self._login_async():
                raise Exception("登录失败")
        
        full_path = self._full_path(path)
        
        # 异步限速等待
        await self._rate_limiter.wait_async()
        
        try:
            from urllib.parse import quote
            
            response = await self.http_client.put(
                f"{self.url}/api/fs/put",
                headers={
                    "Authorization": self._token,
                    "File-Path": quote(full_path, safe=''),
                    "Content-Type": "application/octet-stream",
                },
                content=content.encode('utf-8'),
            )
            
            if response.status_code == 200:
                data = response.json()
                code = data.get("code")
                if code == 200:
                    return True
                else:
                    logger.warning(f"异步上传文件返回非200状态码 {path}: code={code}, message={data.get('message')}")
                    return False
            else:
                logger.warning(f"异步上传文件 HTTP 错误 {path}: status={response.status_code}")
                return False
        except Exception as e:
            logger.error(f"异步上传文件失败 {path}: {e}")
            return False
    
    async def create_directory_async(self, path: str) -> bool:
        """
        异步创建目录
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        # 确保已登录
        if not self._token:
            if not await self._login_async():
                raise Exception("登录失败")
        
        full_path = self._full_path(path)
        
        # 异步限速等待
        await self._rate_limiter.wait_async()
        
        try:
            response = await self.http_client.post(
                f"{self.url}/api/fs/mkdir",
                json={"path": full_path},
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                # code 200 成功，500 可能是目录已存在
                return data.get("code") in (200, 500)
            
            return False
        except Exception as e:
            logger.debug(f"异步创建目录失败 {path}: {e}")
            return False  # 目录可能已存在，不抛异常
    
    async def upload_files_batch_async(
        self,
        files: List[Tuple[str, str]],
        concurrency: int = 16
    ) -> Tuple[int, int, List[str]]:
        """
        批量异步上传文件（优化版，跳过限速）
        
        专为批量上传设计，跳过单文件限速（通过 semaphore 控制并发）。
        比基类默认实现更快。
        
        Args:
            files: [(路径, 内容), ...] 文件列表
            concurrency: 并发数，默认 16
            
        Returns:
            (success_count, error_count, failed_paths)
        """
        if not files:
            return 0, 0, []
        
        # 确保已登录
        if not self._token:
            if not await self._login_async():
                raise Exception("登录失败")
        
        from urllib.parse import quote as url_quote
        import os
        
        # 1. 收集所有需要创建的目录
        dirs_to_create = set()
        for path, _ in files:
            full_path = self._full_path(path)
            dir_path = os.path.dirname(full_path)
            if dir_path:
                parts = dir_path.split('/')
                for i in range(1, len(parts) + 1):
                    dirs_to_create.add('/'.join(parts[:i]))
        
        # 2. 串行创建目录（使用限速，避免风控）
        sorted_dirs = sorted(dirs_to_create, key=lambda x: x.count('/'))
        for dir_path in sorted_dirs:
            await self._rate_limiter.wait_async()
            try:
                await self.http_client.post(
                    f"{self.url}/api/fs/mkdir",
                    json={"path": dir_path},
                    headers=self._get_headers(),
                )
            except Exception:
                pass  # 目录可能已存在
        
        # 3. 并行上传文件（不使用限速，通过 semaphore 控制并发）
        semaphore = asyncio.Semaphore(concurrency)
        
        async def upload_one(path: str, content: str) -> Tuple[bool, str]:
            """返回 (成功与否, 原始路径)"""
            async with semaphore:
                full_path = self._full_path(path)
                try:
                    # 🔥 检查 content 是否为空
                    if content is None:
                        logger.warning(f"上传失败 {path}: content 为 None")
                        return False, path
                    
                    # 🔥 处理字符串编码
                    if isinstance(content, str):
                        content_bytes = content.encode('utf-8')
                    else:
                        content_bytes = content
                    
                    response = await self.http_client.put(
                        f"{self.url}/api/fs/put",
                        headers={
                            "Authorization": self._token,
                            "File-Path": url_quote(full_path, safe=''),
                            "Content-Type": "application/octet-stream",
                        },
                        content=content_bytes,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        api_code = data.get("code")
                        if api_code == 200:
                            return True, path
                        else:
                            # API 内部错误 - 提升日志级别以便调试
                            error_msg = data.get('message', 'unknown')
                            logger.warning(f"上传失败 {path}: API code={api_code}, msg={error_msg}")
                    else:
                        logger.warning(f"上传失败 {path}: HTTP {response.status_code}")
                    return False, path
                except Exception as e:
                    import traceback
                    logger.warning(f"批量上传文件失败 {path}: {e}\n{traceback.format_exc()}")
                    return False, path
        
        tasks = [upload_one(path, content) for path, content in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果并收集失败路径
        success_count = 0
        failed_paths = []
        for r in results:
            if isinstance(r, tuple):
                success, path = r
                if success:
                    success_count += 1
                else:
                    failed_paths.append(path)
            else:
                # 异常情况
                logger.warning(f"上传任务异常: {r}")
        
        error_count = len(results) - success_count
        
        return success_count, error_count, failed_paths
    
    def get_file_url(self, path: str) -> Optional[str]:
        """
        获取文件的直接访问 URL
        
        Args:
            path: 文件路径
            
        Returns:
            文件的直接访问 URL（raw_url），如果无法获取则返回 None
        """
        if not self._token:
            if not self._login_sync():
                return None
        
        full_path = self._full_path(path)
        client = self._get_sync_client()
        
        self._rate_limiter.wait()
        
        try:
            response = client.post(
                f"{self.url}/api/fs/get",
                json={"path": full_path},
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return data.get("data", {}).get("raw_url")
            return None
        except Exception as e:
            logger.error(f"获取文件URL失败 {path}: {e}")
            return None
    
    def get_file_content(self, path: str) -> Optional[str]:
        """
        读取文件内容（用于读取字幕等小文件）
        
        通过 raw_url 下载文件内容
        
        Args:
            path: 文件路径
            
        Returns:
            文件内容，如果失败返回 None
        """
        # 1. 获取文件的直接访问 URL
        raw_url = self.get_file_url(path)
        if not raw_url:
            logger.warning(f"无法获取文件URL: {path}")
            return None
        
        # 2. 下载文件内容
        client = self._get_sync_client()
        self._rate_limiter.wait()
        
        try:
            response = client.get(raw_url)
            if response.status_code == 200:
                # 尝试以 UTF-8 解码，如果失败则尝试其他编码
                try:
                    return response.text
                except UnicodeDecodeError:
                    # 尝试 GBK 编码（常见于中文字幕）
                    return response.content.decode('gbk', errors='replace')
            else:
                logger.warning(f"下载文件失败 {path}: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"读取文件内容失败 {path}: {e}")
            return None
    
    async def get_file_url_async(self, path: str) -> Optional[str]:
        """
        异步获取文件的直接访问 URL
        
        Args:
            path: 文件路径
            
        Returns:
            文件的直接访问 URL（raw_url），如果无法获取则返回 None
        """
        if not self._token:
            if not await self._login_async():
                return None
        
        full_path = self._full_path(path)
        await self._rate_limiter.wait_async()
        
        try:
            response = await self.http_client.post(
                f"{self.url}/api/fs/get",
                json={"path": full_path},
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return data.get("data", {}).get("raw_url")
            return None
        except Exception as e:
            logger.error(f"异步获取文件URL失败 {path}: {e}")
            return None
    
    async def get_file_content_async(self, path: str) -> Optional[str]:
        """
        异步读取文件内容（用于读取字幕等小文件）
        
        Args:
            path: 文件路径
            
        Returns:
            文件内容，如果失败返回 None
        """
        # 1. 获取文件的直接访问 URL
        raw_url = await self.get_file_url_async(path)
        if not raw_url:
            logger.warning(f"无法获取文件URL: {path}")
            return None
        
        # 2. 下载文件内容
        await self._rate_limiter.wait_async()
        
        try:
            response = await self.http_client.get(raw_url)
            if response.status_code == 200:
                try:
                    return response.text
                except UnicodeDecodeError:
                    return response.content.decode('gbk', errors='replace')
            else:
                logger.warning(f"异步下载文件失败 {path}: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"异步读取文件内容失败 {path}: {e}")
            return None
    
    def _full_path(self, path: str) -> str:
        """获取完整路径"""
        if not path or path == "/":
            return self.base_path
        if path.startswith('/'):
            # 绝对路径
            return path
        # 相对路径，拼接到base_path
        return f"{self.base_path}/{path}".replace('//', '/')
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "Content-Type": "application/json",
        }
        if self._token:
            headers["Authorization"] = self._token
        return headers
    
    def _login_sync(self) -> bool:
        """同步登录获取token"""
        client = self._get_sync_client()
        
        try:
            response = client.post(
                f"{self.url}/api/auth/login",
                json={
                    "username": self.username,
                    "password": self.password,
                },
                headers={"Content-Type": "application/json"},
                timeout=30.0,  # 🔥 显式设置超时
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    self._token = data.get("data", {}).get("token")
                    logger.info(f"✅ Alist 登录成功: {self.url}")
                    return True
                else:
                    logger.warning(f"❌ Alist 登录失败: code={data.get('code')}, message={data.get('message')}")
            else:
                logger.warning(f"❌ Alist 登录 HTTP 错误: status={response.status_code}")
                    
            return False
        except Exception as e:
            logger.error(f"❌ Alist 登录异常: {e}")
            return False
    
    async def _login_async(self) -> bool:
        """异步登录获取token"""
        try:
            response = await self.http_client.post(
                f"{self.url}/api/auth/login",
                json={
                    "username": self.username,
                    "password": self.password,
                },
                headers={"Content-Type": "application/json"},
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    self._token = data.get("data", {}).get("token")
                    return True
                    
            return False
        except Exception:
            return False
    
    async def test_connection(self) -> Dict[str, Any]:
        """测试连接"""
        try:
            # 先尝试登录
            if not await self._login_async():
                return {
                    "success": False,
                    "message": "登录失败，请检查用户名密码",
                }
            
            # 测试列出根目录
            response = await self.http_client.post(
                f"{self.url}/api/fs/list",
                json={"path": "/", "refresh": False},
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return {
                        "success": True,
                        "message": "连接成功 (Alist API)",
                        "server_info": {
                            "url": self.url,
                            "type": "alist",
                            "base_path": self.base_path,
                        }
                    }
            
            return {
                "success": False,
                "message": f"API调用失败: {response.text[:200]}",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接失败: {str(e)}",
            }
    
    def list_directory(self, path: str = "/") -> List[FileInfo]:
        """列出目录内容（同步，带缓存和限速）"""
        # 确保已登录
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        full_path = self._full_path(path)
        
        # 检查缓存
        cache_key = f"list:{full_path}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        client = self._get_sync_client()
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                # 限速等待
                self._rate_limiter.wait()
                
                response = client.post(
                    f"{self.url}/api/fs/list",
                    json={
                        "path": full_path,
                        "refresh": False,
                        "page": 1,
                        "per_page": 0,  # 0表示全部
                    },
                    headers=self._get_headers(),
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 200:
                        result = self._parse_list_response(data, full_path)
                        # 缓存结果
                        self._cache.set(cache_key, result)
                        return result
                    elif data.get("code") == 401:
                        # token过期，重新登录
                        self._token = None
                        if self._login_sync():
                            continue
                    elif data.get("code") == 429 or "too many" in data.get("message", "").lower():
                        # 遇到限流，等待更长时间
                        print(f"⚠️ 遇到限流，等待 {DEFAULT_RATE_LIMIT_DELAY} 秒...")
                        time.sleep(DEFAULT_RATE_LIMIT_DELAY)
                        continue
                    last_error = data.get("message", "未知错误")
                elif response.status_code == 429:
                    # HTTP层面的限流
                    print(f"⚠️ HTTP 429限流，等待 {DEFAULT_RATE_LIMIT_DELAY} 秒...")
                    time.sleep(DEFAULT_RATE_LIMIT_DELAY)
                    continue
                else:
                    last_error = f"HTTP {response.status_code}"
                    
            except Exception as e:
                last_error = str(e)
            
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        
        raise Exception(f"列出目录失败（重试{MAX_RETRIES}次后）: {last_error}")
    
    async def list_directory_async(self, path: str = "/") -> List[FileInfo]:
        """列出目录内容（异步，带缓存和限速）"""
        # 确保已登录
        if not self._token:
            if not await self._login_async():
                raise Exception("登录失败")
        
        full_path = self._full_path(path)
        
        # 检查缓存
        cache_key = f"list:{full_path}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                # 限速等待
                await self._rate_limiter.wait_async()
                
                response = await self.http_client.post(
                    f"{self.url}/api/fs/list",
                    json={
                        "path": full_path,
                        "refresh": False,
                        "page": 1,
                        "per_page": 0,
                    },
                    headers=self._get_headers(),
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 200:
                        result = self._parse_list_response(data, full_path)
                        # 缓存结果
                        self._cache.set(cache_key, result)
                        return result
                    elif data.get("code") == 401:
                        # token过期，重新登录
                        self._token = None
                        if await self._login_async():
                            continue
                    elif data.get("code") == 429 or "too many" in data.get("message", "").lower():
                        # 遇到限流，等待更长时间
                        print(f"⚠️ 遇到限流，等待 {DEFAULT_RATE_LIMIT_DELAY} 秒...")
                        await asyncio.sleep(DEFAULT_RATE_LIMIT_DELAY)
                        continue
                    last_error = data.get("message", "未知错误")
                elif response.status_code == 429:
                    # HTTP层面的限流
                    print(f"⚠️ HTTP 429限流，等待 {DEFAULT_RATE_LIMIT_DELAY} 秒...")
                    await asyncio.sleep(DEFAULT_RATE_LIMIT_DELAY)
                    continue
                else:
                    last_error = f"HTTP {response.status_code}"
                    
            except Exception as e:
                last_error = str(e)
            
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        
        raise Exception(f"列出目录失败（重试{MAX_RETRIES}次后）: {last_error}")
    
    def _parse_list_response(self, data: Dict[str, Any], parent_path: str) -> List[FileInfo]:
        """解析列表响应"""
        result = []
        
        content = data.get("data", {}).get("content") or []
        
        for item in content:
            name = item.get("name", "")
            is_dir = item.get("is_dir", False)
            
            # 构建完整路径
            item_path = f"{parent_path.rstrip('/')}/{name}"
            
            info = FileInfo(
                path=item_path,
                name=name,
                is_dir=is_dir,
                size=item.get("size"),
                modified=item.get("modified"),
                content_type=item.get("type"),
            )
            result.append(info)
        
        return result
    
    def move_file(self, source: str, destination: str) -> bool:
        """移动/重命名文件"""
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        src_full = self._full_path(source)
        dst_full = self._full_path(destination)
        
        # 获取源文件名和目录
        src_dir = os.path.dirname(src_full)
        src_name = os.path.basename(src_full)
        dst_dir = os.path.dirname(dst_full)
        dst_name = os.path.basename(dst_full)
        
        client = self._get_sync_client()
        
        # 限速等待
        self._rate_limiter.wait()
        
        try:
            # 如果只是重命名（同目录）
            if src_dir == dst_dir:
                response = client.post(
                    f"{self.url}/api/fs/rename",
                    json={
                        "path": src_full,
                        "name": dst_name,
                    },
                    headers=self._get_headers(),
                )
            else:
                # 跨目录移动
                response = client.post(
                    f"{self.url}/api/fs/move",
                    json={
                        "src_dir": src_dir,
                        "dst_dir": dst_dir,
                        "names": [src_name],
                    },
                    headers=self._get_headers(),
                )
                
                # 如果目标文件名不同，还需要重命名
                if src_name != dst_name:
                    new_path = f"{dst_dir}/{src_name}"
                    response = client.post(
                        f"{self.url}/api/fs/rename",
                        json={
                            "path": new_path,
                            "name": dst_name,
                        },
                        headers=self._get_headers(),
                    )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("code") == 200
                
            return False
        except Exception as e:
            raise Exception(f"移动文件失败: {str(e)}")
    
    def copy_file(self, source: str, destination: str) -> bool:
        """复制文件"""
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        src_full = self._full_path(source)
        dst_full = self._full_path(destination)
        
        src_dir = os.path.dirname(src_full)
        src_name = os.path.basename(src_full)
        dst_dir = os.path.dirname(dst_full)
        dst_name = os.path.basename(dst_full)
        
        client = self._get_sync_client()
        
        # 限速等待
        self._rate_limiter.wait()
        
        try:
            # 复制文件
            response = client.post(
                f"{self.url}/api/fs/copy",
                json={
                    "src_dir": src_dir,
                    "dst_dir": dst_dir,
                    "names": [src_name],
                },
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") != 200:
                    logger.error(f"复制文件API返回错误: {data}")
                    return False
                
                # 🔥 Alist 复制是异步的，需要等待复制完成
                # 轮询检查目标文件是否存在
                import time
                copied_path = f"{dst_dir}/{src_name}"
                max_wait = 30  # 最多等待 30 秒
                wait_interval = 0.5  # 每 0.5 秒检查一次
                waited = 0
                
                while waited < max_wait:
                    time.sleep(wait_interval)
                    waited += wait_interval
                    
                    # 检查文件是否存在
                    check_response = client.post(
                        f"{self.url}/api/fs/get",
                        json={"path": copied_path},
                        headers=self._get_headers(),
                    )
                    if check_response.status_code == 200:
                        check_data = check_response.json()
                        if check_data.get("code") == 200:
                            # 文件已存在，复制完成
                            break
                else:
                    logger.warning(f"等待复制完成超时: {copied_path}")
                    # 继续尝试重命名，可能已经完成了
                
                # 如果目标文件名不同，需要重命名
                if src_name != dst_name:
                    new_path = f"{dst_dir}/{src_name}"
                    response = client.post(
                        f"{self.url}/api/fs/rename",
                        json={
                            "path": new_path,
                            "name": dst_name,
                        },
                        headers=self._get_headers(),
                    )
                    rename_data = response.json()
                    if response.status_code != 200 or rename_data.get("code") != 200:
                        logger.error(f"重命名文件API返回错误: {rename_data}")
                        return False
                    return True
                return True
            return False
        except Exception as e:
            raise Exception(f"复制文件失败: {str(e)}")
    
    def delete_file(self, path: str) -> bool:
        """删除文件"""
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        full_path = self._full_path(path)
        dir_path = os.path.dirname(full_path)
        file_name = os.path.basename(full_path)
        
        client = self._get_sync_client()
        
        # 限速等待
        self._rate_limiter.wait()
        
        try:
            response = client.post(
                f"{self.url}/api/fs/remove",
                json={
                    "dir": dir_path,
                    "names": [file_name],
                },
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                return response.json().get("code") == 200
            return False
        except Exception as e:
            raise Exception(f"删除文件失败: {str(e)}")
    
    def batch_copy(self, src_dir: str, dst_dir: str, names: List[str]) -> Dict[str, bool]:
        """
        批量复制文件
        
        Args:
            src_dir: 源目录路径
            dst_dir: 目标目录路径
            names: 文件名列表
            
        Returns:
            Dict[文件名, 是否成功]
        """
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        src_full = self._full_path(src_dir)
        dst_full = self._full_path(dst_dir)
        
        client = self._get_sync_client()
        
        # 限速等待
        self._rate_limiter.wait()
        
        try:
            response = client.post(
                f"{self.url}/api/fs/copy",
                json={
                    "src_dir": src_full,
                    "dst_dir": dst_full,
                    "names": names,
                },
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return {name: True for name in names}
            
            return {name: False for name in names}
        except Exception as e:
            print(f"批量复制失败: {e}")
            return {name: False for name in names}
    
    def batch_move(self, src_dir: str, dst_dir: str, names: List[str]) -> Dict[str, bool]:
        """
        批量移动文件
        
        Args:
            src_dir: 源目录路径
            dst_dir: 目标目录路径
            names: 文件名列表
            
        Returns:
            Dict[文件名, 是否成功]
        """
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        src_full = self._full_path(src_dir)
        dst_full = self._full_path(dst_dir)
        
        client = self._get_sync_client()
        
        # 限速等待
        self._rate_limiter.wait()
        
        try:
            response = client.post(
                f"{self.url}/api/fs/move",
                json={
                    "src_dir": src_full,
                    "dst_dir": dst_full,
                    "names": names,
                },
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return {name: True for name in names}
            
            return {name: False for name in names}
        except Exception as e:
            print(f"批量移动失败: {e}")
            return {name: False for name in names}
    
    def batch_delete(self, dir_path: str, names: List[str]) -> Dict[str, bool]:
        """
        批量删除文件
        
        Args:
            dir_path: 目录路径
            names: 文件名列表
            
        Returns:
            Dict[文件名, 是否成功]
        """
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        full_path = self._full_path(dir_path)
        
        client = self._get_sync_client()
        
        # 限速等待
        self._rate_limiter.wait()
        
        try:
            response = client.post(
                f"{self.url}/api/fs/remove",
                json={
                    "dir": full_path,
                    "names": names,
                },
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    return {name: True for name in names}
            
            return {name: False for name in names}
        except Exception as e:
            print(f"批量删除失败: {e}")
            return {name: False for name in names}
    
    async def refresh_directory_async(self, path: str) -> bool:
        """
        刷新目录缓存（异步）
        
        Alist 会缓存目录列表，上传文件后需要刷新才能看到新文件。
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        if not self._token:
            if not await self._login_async():
                return False
        
        full_path = self._full_path(path)
        
        try:
            # 使用 list API 并设置 refresh=True 来刷新缓存
            response = await self.http_client.post(
                f"{self.url}/api/fs/list",
                json={
                    "path": full_path,
                    "refresh": True,  # 🔥 关键：设置 refresh=True
                    "page": 1,
                    "per_page": 1,  # 只需要触发刷新，不需要返回全部内容
                },
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    # 清除本地缓存
                    cache_key = f"list:{full_path}"
                    self._cache.invalidate(cache_key)
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"刷新目录失败 {path}: {e}")
            return False
    
    async def refresh_directories_batch_async(self, paths: List[str], concurrency: int = 4) -> Dict[str, bool]:
        """
        批量刷新目录缓存（异步并发）
        
        Args:
            paths: 目录路径列表
            concurrency: 并发数
            
        Returns:
            Dict[路径, 是否成功]
        """
        semaphore = asyncio.Semaphore(concurrency)
        results = {}
        
        async def refresh_one(path: str):
            async with semaphore:
                success = await self.refresh_directory_async(path)
                results[path] = success
        
        await asyncio.gather(*[refresh_one(p) for p in paths])
        return results
    
    def batch_rename(self, renames: List[Dict[str, str]]) -> Dict[str, bool]:
        """
        批量重命名文件
        
        注意：Alist的rename API不支持真正的批量，这里循环调用但使用限速
        
        Args:
            renames: [{"old_path": "/path/to/old", "new_name": "new_name"}, ...]
            
        Returns:
            Dict[old_path, 是否成功]
        """
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        client = self._get_sync_client()
        results = {}
        
        for item in renames:
            old_path = self._full_path(item["old_path"])
            new_name = item["new_name"]
            
            # 限速等待
            self._rate_limiter.wait()
            
            try:
                response = client.post(
                    f"{self.url}/api/fs/rename",
                    json={
                        "path": old_path,
                        "name": new_name,
                    },
                    headers=self._get_headers(),
                )
                
                success = response.status_code == 200 and response.json().get("code") == 200
                results[item["old_path"]] = success
            except Exception as e:
                print(f"重命名失败 {old_path}: {e}")
                results[item["old_path"]] = False
        
        return results
    
    def create_directory(self, path: str) -> bool:
        """创建目录"""
        if not self._token:
            if not self._login_sync():
                raise Exception("登录失败")
        
        full_path = self._full_path(path)
        client = self._get_sync_client()
        
        # 限速等待
        self._rate_limiter.wait()
        
        try:
            response = client.post(
                f"{self.url}/api/fs/mkdir",
                json={"path": full_path},
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                # code 200 成功，500 可能是目录已存在
                return data.get("code") in (200, 500)
                
            return False
        except Exception as e:
            raise Exception(f"创建目录失败: {str(e)}")
    
    def exists(self, path: str) -> bool:
        """检查路径是否存在"""
        if not self._token:
            if not self._login_sync():
                return False
        
        full_path = self._full_path(path)
        client = self._get_sync_client()
        
        try:
            response = client.post(
                f"{self.url}/api/fs/get",
                json={"path": full_path},
                headers=self._get_headers(),
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("code") == 200
                
            return False
        except Exception:
            return False


async def detect_alist_server(url: str) -> bool:
    """
    检测是否是Alist服务器
    
    通过访问 /api/public/settings 端点来判断
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Alist的公开设置API
            response = await client.get(f"{url.rstrip('/')}/api/public/settings")
            
            if response.status_code == 200:
                data = response.json()
                # Alist会返回code字段
                if "code" in data:
                    return True
            
            # 也可以检查根路径返回的HTML中是否包含Alist特征
            response = await client.get(url)
            if "alist" in response.text.lower():
                return True
                
    except Exception:
        pass
    
    return False

