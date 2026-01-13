"""
存储服务抽象基类

定义统一的存储操作接口，支持不同后端实现：
- Alist REST API
- 标准 WebDAV
"""

import os
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, AsyncGenerator, Tuple


@dataclass
class FileInfo:
    """文件/目录信息"""
    path: str           # 完整路径
    name: str           # 文件名
    is_dir: bool        # 是否为目录
    size: Optional[int] = None      # 文件大小（字节）
    modified: Optional[str] = None  # 修改时间
    content_type: Optional[str] = None  # MIME类型


class StorageService(ABC):
    """
    存储服务抽象基类
    
    所有存储后端（Alist、WebDAV等）都需要实现这个接口
    """
    
    @property
    @abstractmethod
    def service_type(self) -> str:
        """返回服务类型标识，如 'alist' 或 'webdav'"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        测试连接
        
        Returns:
            Dict包含:
            - success: bool
            - message: str
            - server_info: dict (可选)
        """
        pass
    
    @abstractmethod
    def list_directory(self, path: str = "/") -> List[FileInfo]:
        """
        列出目录内容（同步）
        
        Args:
            path: 目录路径
            
        Returns:
            文件信息列表
        """
        pass
    
    @abstractmethod
    async def list_directory_async(self, path: str = "/") -> List[FileInfo]:
        """
        列出目录内容（异步）
        
        Args:
            path: 目录路径
            
        Returns:
            文件信息列表
        """
        pass
    
    @abstractmethod
    def move_file(self, source: str, destination: str) -> bool:
        """
        移动/重命名文件
        
        Args:
            source: 源路径
            destination: 目标路径
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def create_directory(self, path: str) -> bool:
        """
        创建目录
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        检查路径是否存在
        
        Args:
            path: 路径
            
        Returns:
            是否存在
        """
        pass
    
    @abstractmethod
    async def close(self):
        """关闭连接"""
        pass
    
    @abstractmethod
    def get_file_content(self, path: str) -> Optional[str]:
        """
        读取文件内容（用于读取字幕等小文件）
        
        Args:
            path: 文件路径
            
        Returns:
            文件内容，如果失败返回 None
        """
        pass
    
    @abstractmethod
    def put_file_content(self, path: str, content: str) -> bool:
        """
        上传文本内容到文件（用于创建 STRM 等小文件）
        
        Args:
            path: 目标文件路径
            content: 文本内容
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def put_file_content_async(self, path: str, content: str) -> bool:
        """
        异步上传文本内容到文件
        
        Args:
            path: 目标文件路径
            content: 文本内容
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def create_directory_async(self, path: str) -> bool:
        """
        异步创建目录
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        pass
    
    async def upload_files_batch_async(
        self,
        files: List[Tuple[str, str]],
        concurrency: int = 16
    ) -> Tuple[int, int, List[str]]:
        """
        批量异步上传文件（默认实现）
        
        策略:
        1. 收集所有需要创建的目录
        2. 串行创建目录（避免竞争）
        3. 并行上传文件（使用 semaphore 控制并发）
        
        Args:
            files: [(路径, 内容), ...] 文件列表
            concurrency: 并发数，默认 16
            
        Returns:
            (success_count, error_count, failed_paths)
        """
        if not files:
            return 0, 0, []
        
        # 1. 收集所有需要创建的目录
        dirs_to_create = set()
        for path, _ in files:
            dir_path = os.path.dirname(path)
            if dir_path:
                # 添加所有层级的目录
                parts = dir_path.split('/')
                for i in range(1, len(parts) + 1):
                    dirs_to_create.add('/'.join(parts[:i]))
        
        # 2. 串行创建目录（按层级排序）
        sorted_dirs = sorted(dirs_to_create, key=lambda x: x.count('/'))
        for dir_path in sorted_dirs:
            await self.create_directory_async(dir_path)
        
        # 3. 并行上传文件
        semaphore = asyncio.Semaphore(concurrency)
        
        async def upload_one(path: str, content: str) -> Tuple[bool, str]:
            """返回 (成功与否, 路径)"""
            async with semaphore:
                result = await self.put_file_content_async(path, content)
                return result, path
        
        tasks = [upload_one(path, content) for path, content in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果并收集失败路径
        success_count = 0
        failed_paths = []
        for r in results:
            if isinstance(r, tuple) and r[0] is True:
                success_count += 1
            elif isinstance(r, tuple):
                failed_paths.append(r[1])
            else:
                # 异常情况，无法获取路径
                pass
        
        error_count = len(results) - success_count
        
        return success_count, error_count, failed_paths
    
    @abstractmethod
    def get_file_url(self, path: str) -> Optional[str]:
        """
        获取文件的直接访问 URL（用于 STRM 内容）
        
        Args:
            path: 文件路径
            
        Returns:
            文件的直接访问 URL，如果不支持则返回 None
        """
        pass
    
    def get_webdav_url(self, path: str) -> str:
        """
        获取文件的 WebDAV URL（通用方法）
        
        Args:
            path: 文件路径
            
        Returns:
            WebDAV 格式的 URL
        """
        # 子类需要提供 url 属性
        base_url = getattr(self, 'url', '')
        if self.service_type == 'alist':
            return f"{base_url}/dav{path}"
        else:
            return f"{base_url}{path}"


# 视频文件扩展名
VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', 
    '.webm', '.m4v', '.ts', '.rmvb', '.rm', '.3gp',
    '.m2ts', '.vob', '.mpg', '.mpeg'
}


def is_video_file(filename: str) -> bool:
    """检查是否为视频文件"""
    import os
    _, ext = os.path.splitext(filename.lower())
    return ext in VIDEO_EXTENSIONS



