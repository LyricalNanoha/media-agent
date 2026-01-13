"""
简化的聊天API端点

直接调用LangGraph Agent处理用户消息，
返回流式响应。
"""

import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agents.media_agent import graph
from backend.config import get_config

router = APIRouter()


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    thread_id: str = "default"


async def stream_agent_response(messages: List[ChatMessage], thread_id: str) -> AsyncGenerator[str, None]:
    """
    流式调用Agent并返回响应
    """
    # 转换消息格式
    from langchain_core.messages import HumanMessage, AIMessage
    
    langchain_messages = []
    for msg in messages:
        if msg.role == "user":
            langchain_messages.append(HumanMessage(content=msg.content))
        else:
            langchain_messages.append(AIMessage(content=msg.content))
    
    # 调用Agent
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # 使用stream获取流式响应
        async for event in graph.astream(
            {"messages": langchain_messages},
            config,
            stream_mode="values"
        ):
            messages = event.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if hasattr(last_msg, 'content') and last_msg.content:
                    # 发送消息内容
                    yield f"data: {json.dumps({'type': 'message', 'content': last_msg.content}, ensure_ascii=False)}\n\n"
                
                # 检查是否有工具调用
                if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                    for tool_call in last_msg.tool_calls:
                        yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_call.get('name', ''), 'args': tool_call.get('args', {})}, ensure_ascii=False)}\n\n"
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    处理聊天请求，返回SSE流
    """
    return StreamingResponse(
        stream_agent_response(request.messages, request.thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/chat/simple")
async def chat_simple(request: ChatRequest):
    """
    简单版本：等待完整响应后返回
    """
    from langchain_core.messages import HumanMessage, AIMessage
    
    langchain_messages = []
    for msg in request.messages:
        if msg.role == "user":
            langchain_messages.append(HumanMessage(content=msg.content))
        else:
            langchain_messages.append(AIMessage(content=msg.content))
    
    config = {"configurable": {"thread_id": request.thread_id}}
    
    try:
        result = await graph.ainvoke(
            {"messages": langchain_messages},
            config,
        )
        
        messages = result.get("messages", [])
        response_content = ""
        tool_calls = []
        
        for msg in messages:
            if hasattr(msg, 'content') and msg.content:
                response_content = msg.content
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                tool_calls.extend(msg.tool_calls)
        
        return {
            "response": response_content,
            "tool_calls": tool_calls,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





