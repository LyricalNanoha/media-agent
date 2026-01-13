"""
扫描相关工具

提供媒体文件扫描功能

🔥 新架构（2026-01-08）：
- 工具通过 InjectedState 直接访问 State
- 工具通过 get_storage_service(state) 获取服务实例
- 返回通用 JSON 格式：{"message": "...", "state_update": {...}}
"""

from typing import Dict, Any, List
from typing_extensions import Annotated
from collections import defaultdict
import re
import os
from langchain.tools import tool
from langgraph.prebuilt import InjectedState

from backend.agents.tool_response import make_tool_response
from backend.agents.services import get_storage_service
from backend.utils.file_filter import get_file_type

# 全局变量用于实时进度跟踪
_scan_progress = {
    "videos": 0,
    "subtitles": 0,
    "dirs_scanned": 0,
    "status": "idle"
}


def _extract_subtitle_language(filename: str) -> str:
    """从字幕文件名提取语言
    
    Examples:
        [001].chs.srt → chs
        [001].chi.srt → chs (转换为标准格式)
        [001].eng.srt → eng
        [001].jpn.ass → jpn
        [001].scjp.ass → scjp (复合语言保留)
        [001].tcjp.ass → tcjp (复合语言保留)
        [001].srt → und (未知)
    
    Returns:
        语言代码: chs, cht, eng, jpn, kor, scjp, tcjp, und 等
    """
    # 移除扩展名
    name = re.sub(r'\.(srt|ass|ssa|sub)$', '', filename, flags=re.IGNORECASE)
    
    # 🔥 复合语言直接保留（优先匹配）
    compound_langs = ['scjp', 'tcjp', 'chsjp', 'chtjp', 'chs_jp', 'cht_jp']
    
    # 常见语言代码映射
    lang_map = {
        # 简体中文
        'chs': 'chs', 'chi': 'chs', 'sc': 'chs', 'gb': 'chs', 'zh-cn': 'chs', 'zho': 'chs',
        # 繁体中文
        'cht': 'cht', 'tc': 'cht', 'big5': 'cht', 'zh-tw': 'cht',
        # 英文
        'eng': 'eng', 'en': 'eng',
        # 日文
        'jpn': 'jpn', 'jap': 'jpn', 'jp': 'jpn', 'ja': 'jpn',
        # 韩文
        'kor': 'kor', 'ko': 'kor',
    }
    
    # 尝试从文件名末尾提取语言
    parts = name.split('.')
    if len(parts) >= 2:
        last_part = parts[-1].lower()
        
        # 🔥 先检查复合语言
        if last_part in compound_langs:
            return last_part
        
        if last_part in lang_map:
            return lang_map[last_part]
    
    # 尝试匹配中间的语言标识
    for pattern in compound_langs:
        if f'.{pattern}.' in name.lower() or f'_{pattern}_' in name.lower():
            return pattern
    
    for pattern, lang in lang_map.items():
        if f'.{pattern}.' in name.lower() or f'_{pattern}_' in name.lower():
            return lang
    
    return 'und'  # 未知


def get_scan_progress() -> Dict[str, Any]:
    """获取当前扫描进度（用于状态同步）"""
    return _scan_progress.copy()


def reset_scan_progress():
    """重置扫描进度"""
    global _scan_progress
    _scan_progress = {
        "videos": 0,
        "subtitles": 0,
        "dirs_scanned": 0,
        "status": "idle"
    }


from backend.agents.state import MediaAgentState

@tool
def scan_media_files(
    path: str = "", 
    recursive: bool = True, 
    max_files: int = 0, 
    max_depth: int = 10,
    scan_delay: float = -1.0,
    state: Annotated[dict, InjectedState] = None
) -> str:
    """
    扫描存储服务器上的媒体文件
    
    Args:
        path: 扫描路径，留空则从连接时的基础路径开始，或指定相对/绝对路径
        recursive: 是否递归扫描子目录，默认True
        max_files: 最大返回文件数，0表示不限制（默认不限制）
        max_depth: 最大递归深度，默认10层
        scan_delay: 扫描每个目录之间的间隔（秒）。
                    -1 表示使用 user_config 中的值（默认）
                    0 表示不等待
                    >0 表示等待指定秒数
    
    Returns:
        JSON: {"message": "...", "state_update": {"scanned_files": [...], "scan_progress": {...}}}
    """
    # 从 State 获取服务
    service = get_storage_service(state)
    if not service:
        return make_tool_response("❌ 请先使用 connect_webdav 连接到存储服务器")
    
    # 从 State 获取配置
    storage_config = state.get("storage_config", {})
    user_config = state.get("user_config", {})
    
    try:
        global _scan_progress
        reset_scan_progress()
        _scan_progress["status"] = "scanning"
        
        config_scan_path = storage_config.get("scan_path", "/")
        service_type = storage_config.get("type", "unknown")
        scanned_dirs = 0
        
        # 使用 user_config 中的 scan_delay（如果未指定）
        effective_scan_delay = scan_delay if scan_delay >= 0 else user_config.get("scan_delay", 0.0)
        
        # 确定扫描起始路径
        if path:
            if path.startswith('/'):
                scan_path = path  # 绝对路径
            else:
                scan_path = f"{config_scan_path.rstrip('/')}/{path}"  # 相对路径
        else:
            scan_path = config_scan_path  # 使用连接时的扫描路径
        
        # 分别存储视频和字幕（使用 Dict 格式）
        video_files: List[Dict[str, Any]] = []
        subtitle_files: List[Dict[str, Any]] = []
        
        def scan_directory(dir_path: str, depth: int):
            """递归扫描目录"""
            global _scan_progress
            nonlocal video_files, subtitle_files, scanned_dirs
            
            if depth > max_depth:
                return
            # max_files=0 表示不限制
            total_files = len(video_files) + len(subtitle_files)
            if max_files > 0 and total_files >= max_files:
                return
            
            try:
                # 应用用户指定的扫描延迟（首个目录不等待）
                if effective_scan_delay > 0 and scanned_dirs > 0:
                    import time
                    time.sleep(effective_scan_delay)
                
                items = service.list_directory(dir_path)
                scanned_dirs += 1
                
                # 更新全局进度（用于状态同步）
                _scan_progress["dirs_scanned"] = scanned_dirs
                _scan_progress["videos"] = len(video_files)
                _scan_progress["subtitles"] = len(subtitle_files)
                
                # 打印扫描进度（每5个目录打印一次）
                if scanned_dirs % 5 == 0:
                    print(f"📂 已扫描 {scanned_dirs} 个目录 | 视频: {len(video_files)} | 字幕: {len(subtitle_files)}")
                
                for item in items:
                    # max_files=0 表示不限制
                    total_files = len(video_files) + len(subtitle_files)
                    if max_files > 0 and total_files >= max_files:
                        return
                    
                    if item.is_dir and recursive:
                        # 递归扫描子目录
                        scan_directory(item.path, depth + 1)
                    elif not item.is_dir:
                        file_type = get_file_type(item.name)
                        # 获取目录名
                        directory = os.path.dirname(item.path)
                        
                        if file_type == 'video':
                            video_files.append({
                                "path": item.path,
                                "name": item.name,
                                "size": item.size,
                                "type": "video",
                                "directory": directory,
                            })
                            # 每发现一个视频更新进度
                            _scan_progress["videos"] = len(video_files)
                        elif file_type == 'subtitle':
                            # 提取字幕语言
                            language = _extract_subtitle_language(item.name)
                            subtitle_files.append({
                                "path": item.path,
                                "name": item.name,
                                "size": item.size,
                                "type": "subtitle",
                                "directory": directory,
                                "language": language,
                            })
                            _scan_progress["subtitles"] = len(subtitle_files)
            except Exception as e:
                # 跳过无法访问的目录
                print(f"跳过目录 {dir_path}: {e}")
        
        # 开始扫描
        print(f"开始扫描 ({service_type}): {scan_path}")
        scan_directory(scan_path, 0)
        
        # 标记扫描完成
        _scan_progress["status"] = "connected"
        
        # 合并所有文件
        files = video_files + subtitle_files
        
        if not files:
            return make_tool_response(
                f"📂 在 {scan_path} 中没有找到媒体文件（扫描了 {scanned_dirs} 个目录，使用 {service_type}）\n\n提示：\n• 确保路径正确\n• 检查文件扩展名是否为常见视频格式\n• 尝试指定子目录",
                {
                    "scanned_files": [],
                    "scan_progress": {
                        "videos": 0,
                        "subtitles": 0,
                        "dirs_scanned": scanned_dirs,
                        "status": "connected",
                    }
                }
            )
        
        # 格式化输出消息
        message = f"## 📂 扫描结果\n\n"
        message += f"在 `{scan_path}` 找到 **{len(video_files)}** 个视频 + **{len(subtitle_files)}** 个字幕\n\n"
        
        # 显示剧集分组（只统计视频文件）
        video_series = defaultdict(list)
        video_movies = []
        for f in video_files:
            name = f["name"]
            tv_pattern = r'^(.+?)\s*[\(\[]?(?:TV\s*)?S?(\d+).*?[\)\]]?\s*\.?\s*(\d+)'
            movie_pattern = r'^(.+?)\s*[\(\[]?(\d{4})[\)\]]?'
            
            tv_match = re.match(tv_pattern, name, re.IGNORECASE)
            if tv_match:
                series_name = tv_match.group(1).strip()
                video_series[series_name].append(f)
            else:
                movie_match = re.match(movie_pattern, name)
                if movie_match:
                    video_movies.append({
                        **f,
                        'title': movie_match.group(1).strip(),
                        'year': movie_match.group(2)
                    })
                else:
                    parent_dir = os.path.basename(f["directory"]) or 'Other'
                    video_series[parent_dir].append(f)
        
        if video_series:
            message += "### 📺 剧集系列\n\n"
            message += "| 系列名称 | 视频 | 字幕 | 文件示例 |\n"
            message += "|---------|------|------|----------|\n"
            for series_name, episodes in sorted(video_series.items()):
                # 计算匹配的字幕数量
                subtitle_count = sum(1 for s in subtitle_files if series_name.lower() in s["name"].lower())
                first_ep_name = episodes[0]["name"]
                first_ep = first_ep_name[:35] + '...' if len(first_ep_name) > 35 else first_ep_name
                message += f"| **{series_name}** | {len(episodes)} | {subtitle_count} | {first_ep} |\n"
            message += "\n"
        
        # 显示电影
        if video_movies:
            message += "### 🎬 电影\n\n"
            for m in video_movies[:10]:
                message += f"- {m['title']} ({m['year']})\n"
            if len(video_movies) > 10:
                message += f"- ... 还有 {len(video_movies) - 10} 部电影\n"
            message += "\n"
        
        message += "---\n\n"
        message += "**接下来，告诉我你要处理哪些文件：**\n"
        message += "- 「重命名全部文件」\n"
        message += "- 「只处理第一季」\n"
        message += "- 「重命名所有电影」\n"
        
        # 返回通用 JSON 格式
        return make_tool_response(message, {
            "scanned_files": files,
            "scan_progress": {
                "videos": len(video_files),
                "subtitles": len(subtitle_files),
                "dirs_scanned": scanned_dirs,
                "status": "connected",
            },
            "scan_result": {
                "total_files": len(files),
                "video_count": len(video_files),
                "subtitle_count": len(subtitle_files),
            }
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return make_tool_response(f"❌ 扫描失败: {str(e)}")
