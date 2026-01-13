"""
LLM服务

封装LLM调用，支持OpenAI API兼容格式
"""

from typing import Optional, List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from backend.config import get_config, LLMConfig


class LLMService:
    """LLM服务封装"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        初始化LLM服务
        
        Args:
            config: LLM配置，None则从全局配置读取
        """
        self.config = config or get_config().llm
        self._client: Optional[ChatOpenAI] = None
    
    @property
    def client(self) -> ChatOpenAI:
        """获取LLM客户端（懒加载）"""
        if self._client is None:
            self._client = self._create_client()
        return self._client
    
    def _create_client(self) -> ChatOpenAI:
        """创建LLM客户端"""
        kwargs = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "openai_api_key": self.config.api_key,
            "openai_api_base": self.config.base_url,
        }
        
        # Azure特殊处理
        if self.config.provider == "azure" and self.config.api_version:
            kwargs["openai_api_version"] = self.config.api_version
        
        return ChatOpenAI(**kwargs)
    
    def get_chat_model(self) -> ChatOpenAI:
        """
        获取聊天模型实例
        
        Returns:
            ChatOpenAI: LangChain聊天模型
        """
        return self.client
    
    def bind_tools(self, tools: List[Any]) -> ChatOpenAI:
        """
        绑定工具到模型
        
        Args:
            tools: 工具列表
            
        Returns:
            ChatOpenAI: 绑定了工具的模型
        """
        return self.client.bind_tools(tools, parallel_tool_calls=False)
    
    async def ainvoke(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> BaseMessage:
        """
        异步调用LLM
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            BaseMessage: 响应消息
        """
        return await self.client.ainvoke(messages, **kwargs)
    
    def invoke(
        self,
        messages: List[BaseMessage],
        **kwargs
    ) -> BaseMessage:
        """
        同步调用LLM
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Returns:
            BaseMessage: 响应消息
        """
        return self.client.invoke(messages, **kwargs)


# 全局服务实例
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """获取全局LLM服务实例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

