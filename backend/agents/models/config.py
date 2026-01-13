"""
配置模型

包含：
- UserConfig: 用户配置
"""

from pydantic import BaseModel, Field


class UserConfig(BaseModel):
    """
    用户配置（Chat 过程中收集）
    
    注意：路径配置已移到各自的 storage_config/strm_target_config 中：
    - storage_config.target_path: 传统整理的目标路径
    - strm_target_config.target_path: STRM 输出路径
    """
    # 延迟
    scan_delay: float = Field(default=0.0, description="扫描延迟（秒）")
    upload_delay: float = Field(default=0.0, description="上传延迟（秒）")
    
    # 语言
    naming_language: str = Field(default="zh", description="命名语言: zh | en")
    
    # 整理模式
    use_copy: bool = Field(default=True, description="是否使用复制模式")

