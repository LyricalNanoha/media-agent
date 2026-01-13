"""
配置加载模块

从config.yaml加载配置，支持环境变量覆盖
"""

import os
from pathlib import Path
from typing import Optional, List

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class TMDBConfig(BaseModel):
    """TMDB配置"""
    api_key: str = ""
    language: str = "zh-CN"
    include_adult: bool = False


class LLMConfig(BaseModel):
    """LLM配置 - 支持OpenAI API兼容格式"""
    provider: str = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 4096
    api_version: Optional[str] = None  # Azure专用


class DatabaseConfig(BaseModel):
    """数据库配置"""
    path: str = "./data/webdav_tools.db"


class StorageConfig(BaseModel):
    """存储服务配置（Alist/WebDAV）"""
    # 🔥 延迟配置已移到运行时 UserConfig：
    # - scan_delay: 扫描目录间等待
    # - upload_delay: 上传文件间等待
    rate_limit_delay: float = 5.0  # 遇到服务端限流时的等待时间（秒）
    
    # 缓存
    cache_enabled: bool = True
    cache_ttl: int = 300  # 缓存有效期（秒）
    cache_size: int = 100  # 最大缓存条目
    
    # 连接
    timeout: int = 30
    max_retries: int = 3


class ScanConfig(BaseModel):
    """扫描配置"""
    video_extensions: List[str] = Field(default_factory=lambda: [
        ".mkv", ".mp4", ".avi", ".mov", ".wmv", 
        ".flv", ".m4v", ".ts", ".rmvb", ".webm", ".iso"
    ])
    subtitle_extensions: List[str] = Field(default_factory=lambda: [
        ".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt",
        ".smi", ".sup", ".pgs", ".mks"
    ])
    exclude_patterns: List[str] = Field(default_factory=lambda: [
        ".*", "@eaDir", "#recycle", ".@__thumb", 
        "lost+found", "System Volume Information",
        "$RECYCLE.BIN", "Thumbs.db", ".DS_Store"
    ])
    batch_size: int = 100
    max_depth: Optional[int] = None


class ServerConfig(BaseModel):
    """服务器配置"""
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_port: int = 3000


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class AppConfig(BaseModel):
    """应用总配置"""
    tmdb: TMDBConfig = Field(default_factory=TMDBConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def find_config_file() -> Optional[Path]:
    """
    查找配置文件
    优先级: 环境变量 > 当前目录 > 项目根目录
    """
    # 1. 环境变量指定
    env_path = os.getenv("CONFIG_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
    
    # 2. 当前目录
    current_dir = Path.cwd()
    for name in ["config.yaml", "config.yml", "config/config.yaml", "config/config.yml"]:
        path = current_dir / name
        if path.exists():
            return path
    
    # 3. 项目根目录 (backend的父目录)
    project_root = Path(__file__).parent.parent
    for name in ["config.yaml", "config.yml", "config/config.yaml", "config/config.yml"]:
        path = project_root / name
        if path.exists():
            return path
    
    return None


def load_config() -> AppConfig:
    """
    加载配置文件
    
    配置优先级: 环境变量 > 配置文件 > 默认值
    
    Returns:
        AppConfig: 应用配置对象
    """
    config_path = find_config_file()
    
    if config_path is None:
        print("⚠️  未找到配置文件，尝试从环境变量加载配置...")
        raw_config = {}
    else:
        print(f"📄 加载配置文件: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}
    
    # 环境变量覆盖（优先级最高）
    if os.getenv("TMDB_API_KEY"):
        raw_config.setdefault("tmdb", {})["api_key"] = os.getenv("TMDB_API_KEY")
    
    if os.getenv("LLM_API_KEY"):
        raw_config.setdefault("llm", {})["api_key"] = os.getenv("LLM_API_KEY")
    
    if os.getenv("LLM_BASE_URL"):
        raw_config.setdefault("llm", {})["base_url"] = os.getenv("LLM_BASE_URL")
    
    if os.getenv("LLM_MODEL"):
        raw_config.setdefault("llm", {})["model"] = os.getenv("LLM_MODEL")
    
    # 检查必要的配置是否存在
    llm_config = raw_config.get("llm", {})
    tmdb_config = raw_config.get("tmdb", {})
    
    if llm_config.get("api_key"):
        print(f"✅ LLM API Key 已配置 (来源: {'环境变量' if os.getenv('LLM_API_KEY') else '配置文件'})")
    else:
        print("⚠️  LLM API Key 未配置！请设置 LLM_API_KEY 环境变量或在配置文件中配置")
    
    if tmdb_config.get("api_key"):
        print(f"✅ TMDB API Key 已配置 (来源: {'环境变量' if os.getenv('TMDB_API_KEY') else '配置文件'})")
    else:
        print("⚠️  TMDB API Key 未配置！请设置 TMDB_API_KEY 环境变量或在配置文件中配置")
    
    return AppConfig(**raw_config)


# 全局配置实例
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    获取全局配置实例（单例模式）
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> AppConfig:
    """
    重新加载配置
    """
    global _config
    _config = load_config()
    return _config

