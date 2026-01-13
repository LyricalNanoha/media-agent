"use client";

import { CopilotChat } from "@copilotkit/react-ui";
import { 
  useCopilotReadable, 
  useCopilotAction, 
  useDefaultTool, 
  useRenderToolCall,
  useCoAgent,
  useCopilotChat
} from "@copilotkit/react-core";
import { useState, useEffect } from "react";
import { Film, Loader2, Check, Server, Search, FileEdit, FolderOpen, RefreshCw, Wifi, WifiOff, Zap, Sparkles, Heart, Star, Menu, X, Settings } from "lucide-react";
import { Mascot, MiniMascot } from "@/components/Mascot";
import { ToolCard } from "@/components/ToolCard";
import { useResponsive } from "@/hooks/useResponsive";
import { useTheme, themes, defaultTheme } from "@/themes";
import { useThemeConfig } from "@/hooks/useThemeConfig";

// Agent 状态类型定义（与后端 MediaAgentState 对应）
type MediaAgentState = {
  // ============ UI 状态 ============
  current_tool?: {
    name: string;
    status: string;  // "idle" | "executing" | "complete"
    description: string;
  };
  
  // ============ 进度状态 ============
  scan_progress?: {
    current: number;
    total: number;
    status: string;     // "idle" | "scanning" | "complete"
    videos: number;
    subtitles: number;
    dirs_scanned?: number;
  };
  analyze_progress?: {
    current: number;
    total: number;
    status: string;
  };
  organize_progress?: {
    current: number;
    total: number;
    status: string;
  };
  strm_progress?: {
    total_series?: number;
    completed_series?: number;
    current_series?: string;
    files_generated?: number;
  };
  
  // ============ 连接配置（核心数据）============
  storage_config?: {
    url?: string;
    username?: string;
    type?: string;          // "alist" | "webdav"
    scan_path?: string;     // 扫描路径
    target_path?: string;   // 传统整理目标路径
    connected?: boolean;    // 连接状态
  };
  strm_target_config?: {
    url?: string;
    username?: string;
    type?: string;          // "alist" | "webdav"
    target_path?: string;   // STRM 输出路径
    connected?: boolean;    // 连接状态
  };
  
  // ============ 摘要数据（由 get_state_summary 生成）============
  scan_result?: {
    total_files: number;
    video_count?: number;
    subtitle_count?: number;
    episode_range?: { min: number; max: number };
    sample_files?: string[];
  };
  classification_result?: {
    [tmdb_id: string]: {
      file_count: number;
      ep_range: string;
      name: string;
      type?: "tv" | "movie";
      seasons?: Array<{
        season: number;
        episode_count: number;
        ep_range: string;
      }>;
    };
  };
  
  // ============ 主题人设（同步到后端）============
  persona?: {
    name: string;
    fullName?: string;
    style: string;
    roleDescription?: string;
    emoji?: string;
    greetings: string[];
    successPhrases: string[];
    errorPhrases: string[];
  };
  
  // ============ 用户配置（对应 UserConfig 模型）============
  user_config?: {
    scan_delay?: number;      // 扫描延迟（目录间等待）
    upload_delay?: number;    // 上传延迟（文件间等待）
    naming_language?: string; // 命名语言: zh | en
    use_copy?: boolean;       // 整理模式: 复制 | 移动
  };
  
  // ============ 原始数据（可选，调试用）============
  scanned_files?: Array<{
    name: string;
    path: string;
    type: string;
    size: number;
    directory: string;
  }>;
  classifications?: Record<string, unknown>;
  analysis_result?: Record<string, unknown>;
};

// 工具名称映射（🌸 日系风格图标）
const TOOL_DISPLAY_NAMES: Record<string, { name: string; description: string; icon: string }> = {
  // 连接和扫描
  connect_webdav: { name: "连接存储", description: "正在连接到服务器~", icon: "🌸" },
  scan_media_files: { name: "扫描文件", description: "正在扫描媒体文件~", icon: "📂" },
  connect_strm_target: { name: "连接STRM目标", description: "正在连接 STRM 目标~", icon: "💫" },
  // TMDB 查询
  search_tmdb: { name: "搜索TMDB", description: "正在查询 TMDB~", icon: "🔮" },
  get_tmdb_details: { name: "获取详情", description: "正在获取详细信息~", icon: "✨" },
  // 分析和分类
  smart_analyze: { name: "智能分析", description: "正在分析文件~", icon: "🎀" },
  auto_classify: { name: "自动分类", description: "正在分类文件~", icon: "🎯" },
  analyze_and_classify: { name: "分析分类", description: "正在分析和分类文件~", icon: "🎀" },
  analyze_and_classify_v2: { name: "分析分类V2", description: "正在分析和分类文件（新架构）~", icon: "🎀" },
  prepare_llm_classification: { name: "准备LLM分类", description: "正在准备 LLM 分类数据~", icon: "🧠" },
  generate_classification: { name: "生成分类结果", description: "正在生成分类结果~", icon: "✨" },
  get_status: { name: "获取状态", description: "正在获取状态~", icon: "💝" },
  list_files: { name: "列出文件", description: "正在列出文件~", icon: "📋" },
  set_user_config: { name: "设置配置", description: "正在设置用户配置~", icon: "⚙️" },
  // 输出
  organize_files: { name: "整理文件", description: "正在整理文件~", icon: "🌷" },
  generate_strm: { name: "生成STRM", description: "正在生成 STRM~", icon: "📝" },
  retry_failed_uploads: { name: "重试上传", description: "正在重试失败的上传~", icon: "🔄" },
  // 测试
  test_card: { name: "测试卡片", description: "测试中~", icon: "🧪" },
};

// 当前正在执行的工具状态
type ActiveToolState = {
  name: string;
  displayName: string;
  description: string;
  icon: string;
  startTime: number;
  videos?: number;
  subtitles?: number;
  dirs?: number;
} | null;

export default function Home() {
  const [activeTool, setActiveTool] = useState<ActiveToolState>(null);
  
  // 🔥 获取 LLM 生成状态（用于显示"思考中"loading）
  const { isLoading: isLLMThinking } = useCopilotChat();
  
  // 🔥 从 localStorage 读取当前主题，获取初始 persona
  const getInitialPersona = () => {
    if (typeof window !== 'undefined') {
      const savedThemeId = localStorage.getItem('media-assistant-theme');
      const savedTheme = savedThemeId ? themes[savedThemeId] : defaultTheme;
      return savedTheme?.persona || defaultTheme.persona;
    }
    return defaultTheme.persona;
  };

  // 订阅 Agent 状态（包含 setState 用于同步 persona）
  const { state: agentState, setState: setAgentState } = useCoAgent<MediaAgentState>({
    name: "media_agent",
    initialState: {
      scan_progress: { current: 0, total: 0, status: "disconnected", videos: 0, subtitles: 0 },
      analyze_progress: { current: 0, total: 0, status: "idle" },
      organize_progress: { current: 0, total: 0, status: "idle" },
      persona: getInitialPersona(),
    },
  });

  // 响应式状态和主题（必须在组件顶部声明）
  const { isMobile, isTablet, isDesktop } = useResponsive();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme, setTheme, availableThemes } = useTheme();
  const [showThemeMenu, setShowThemeMenu] = useState(false);
  const themeConfig = useThemeConfig();
  
  // 🔥 当主题切换时，同步 persona 到后端 Agent 状态
  // 使用 theme.id 作为依赖，避免因 theme 对象引用变化导致的无限循环
  const themeId = theme?.id;
  useEffect(() => {
    if (theme && theme.persona && themeId && setAgentState) {
      console.log("🎭 [persona-sync] 准备同步 persona:", {
        themeId,
        personaName: theme.persona.name,
        currentAgentPersona: agentState?.persona?.name,
      });
      // 使用 setTimeout 确保在 useCoAgent 完全初始化后再同步
      const timer = setTimeout(() => {
        console.log("🎭 [persona-sync] 执行同步...");
        setAgentState((prev) => {
          console.log("🎭 [persona-sync] prev state persona:", prev?.persona?.name);
          return {
            ...prev,
            persona: theme.persona,
          };
        });
      }, 100);
      return () => clearTimeout(timer);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [themeId]); // 只依赖 themeId，不依赖整个 theme 对象

  // 监听 Agent 状态更新
  useEffect(() => {
    console.log("🌸 Agent State Updated:", agentState);
    
    const currentTool = agentState?.current_tool;
    const scanProgress = agentState?.scan_progress;
    
    if (currentTool && currentTool.status === "executing" && currentTool.name) {
      const toolInfo = TOOL_DISPLAY_NAMES[currentTool.name] || {
        name: currentTool.name,
        description: currentTool.description || `正在执行 ${currentTool.name}~`,
        icon: "✨",
      };
      
      setActiveTool(prev => ({
        name: currentTool.name,
        displayName: toolInfo.name,
        description: currentTool.description || toolInfo.description,
        icon: toolInfo.icon,
        startTime: prev?.name === currentTool.name ? (prev.startTime || Date.now()) : Date.now(),
        videos: scanProgress?.videos || 0,
        subtitles: scanProgress?.subtitles || 0,
        dirs: scanProgress?.dirs_scanned || 0,
      }));
    } else if (currentTool && currentTool.status === "idle" && activeTool) {
      setTimeout(() => setActiveTool(null), 300);
    }
    
    if (scanProgress?.status === "scanning" && activeTool?.name === "scan_media_files") {
      setActiveTool(prev => prev ? {
        ...prev,
        videos: scanProgress.videos || 0,
        subtitles: scanProgress.subtitles || 0,
        dirs: scanProgress.dirs_scanned || 0,
      } : null);
    }
  }, [agentState]);

  useCopilotReadable({
    description: "当前扫描统计",
    value: agentState?.scan_progress || {},
  });

  // 将当前主题人设传递给后端
  useCopilotReadable({
    description: "当前助手人设风格",
    value: {
      name: theme.persona.name,
      style: theme.persona.style,
      useEmoji: theme.features.showEmoji,
    },
  });

  // 🌸 连接WebDAV工具
  useRenderToolCall({
    name: "connect_webdav",
    render: ({ status, args }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "已连接成功" : "正在连接..."}
        subtitle={args.url}
        emoji={themeConfig.showEmoji ? "🌸" : undefined}
      />
    ),
  });

  // 🌸 扫描文件工具
  useRenderToolCall({
    name: "scan_media_files",
    render: ({ status, args }) => {
      const scanResult = agentState?.scan_result;
      const progress = agentState?.scan_progress;
      const isScanning = status !== "complete" && progress?.status === "scanning";
      
      const videoCount = scanResult?.video_count || scanResult?.total_files || progress?.videos || 0;
      const subtitleCount = scanResult?.subtitle_count || progress?.subtitles || 0;
      const dirCount = progress?.dirs_scanned || 0;
      
      return (
        <ToolCard
          status={status}
          title={status === "complete" ? "扫描完成" : "正在扫描..."}
          subtitle={`路径: ${args.path || "/"} ${args.recursive ? "(递归)" : ""}`}
          emoji={themeConfig.showEmoji ? "✨" : undefined}
        >
          {(isScanning || status === "complete") && (
            <div className="flex items-center justify-between text-xs" style={{ color: `var(--color-text-secondary)` }}>
              <span>📹 视频: <span className="font-semibold" style={{ color: `var(--color-secondary)` }}>{videoCount}</span></span>
              <span>📝 字幕: <span className="font-semibold" style={{ color: `var(--color-primary)` }}>{subtitleCount}</span></span>
              <span>📁 目录: <span className="font-semibold">{dirCount}</span></span>
            </div>
          )}
        </ToolCard>
      );
    },
  });

  // 🌸 搜索 TMDB 工具
  useRenderToolCall({
    name: "search_tmdb",
    render: ({ status, args }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "搜索完成" : "正在搜索 TMDB..."}
        subtitle={`搜索: ${args?.query || "未知"} (${args?.media_type === "movie" ? "电影" : "TV系列"})`}
        emoji={themeConfig.showEmoji ? "🔮" : undefined}
      />
    ),
  });

  // 🌸 获取 TMDB 详情工具
  useRenderToolCall({
    name: "get_tmdb_details",
    render: ({ status, args }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "详情获取完成" : "正在获取详情..."}
        subtitle={`TMDB ID: ${args?.tmdb_id || "未知"} (${args?.media_type === "movie" ? "电影" : "TV系列"})`}
        icon={<Film className="w-5 h-5" style={{ color: `var(--color-secondary)` }} />}
      />
    ),
  });

  // 🌸 智能分析工具
  useRenderToolCall({
    name: "smart_analyze",
    render: ({ status }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "分析完成" : "正在智能分析..."}
        subtitle={status === "complete" ? "已完成文件分析和 TMDB 匹配" : "正在分析文件结构并搜索 TMDB 信息..."}
        emoji={themeConfig.showEmoji ? "🎀" : undefined}
      />
    ),
  });

  // 🌸 自动分类工具
  useRenderToolCall({
    name: "auto_classify",
    render: ({ status }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "分类完成" : "正在自动分类..."}
        subtitle="根据 TMDB 季信息将文件分类到正确的系列和季"
        icon={<FolderOpen className="w-5 h-5" style={{ color: `var(--color-success)` }} />}
      />
    ),
  });

  // 🌸 获取状态工具
  useRenderToolCall({
    name: "get_status",
    render: ({ status }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "状态已获取" : "正在获取状态..."}
        icon={<Heart className="w-5 h-5" style={{ color: `var(--color-primary)` }} />}
      />
    ),
  });

  // 🌸 整理文件工具
  useRenderToolCall({
    name: "organize_files",
    render: ({ status, args }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "整理完成" : "正在整理文件..."}
        subtitle={`目标: ${args?.target_path || "未设置"} | 模式: ${args?.use_copy ? "复制" : "移动"}`}
        emoji={themeConfig.showEmoji ? "🌷" : undefined}
      />
    ),
  });

  // 🌸 连接 STRM 目标存储
  useRenderToolCall({
    name: "connect_strm_target",
    render: ({ status, args }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "STRM 目标已连接" : "正在连接..."}
        subtitle={args?.url || "目标存储"}
        emoji={themeConfig.showEmoji ? "💫" : undefined}
      />
    ),
  });

  // 🌸 生成 STRM 工具
  useRenderToolCall({
    name: "generate_strm",
    render: ({ status, args }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "STRM 生成完成" : "正在生成 STRM..."}
        subtitle={`输出: ${args?.output_format === "webdav" ? "上传到目标存储" : (args?.output_format === "zip" ? "ZIP 打包" : "预览")}`}
        icon={<FileEdit className="w-5 h-5" style={{ color: `var(--color-success)` }} />}
      />
    ),
  });

  // 🌸 准备 LLM 分类
  useRenderToolCall({
    name: "prepare_llm_classification",
    render: ({ status }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "LLM 分类数据已准备" : "正在准备 LLM 分类数据..."}
        subtitle="收集文件信息和 TMDB 数据"
        emoji={themeConfig.showEmoji ? "🧠" : undefined}
      />
    ),
  });

  // 🌸 生成分类结果
  useRenderToolCall({
    name: "generate_classification",
    render: ({ status }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "分类结果已生成" : "正在生成分类结果..."}
        subtitle="解析并保存分类结果"
        emoji={themeConfig.showEmoji ? "✨" : undefined}
      />
    ),
  });

  // 🌸 分析和分类（合并版）
  useRenderToolCall({
    name: "analyze_and_classify",
    render: ({ status }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "分析分类完成" : "正在分析和分类文件..."}
        emoji={themeConfig.showEmoji ? "🎀" : undefined}
      />
    ),
  });

  // 🌸 分析和分类 V2
  useRenderToolCall({
    name: "analyze_and_classify_v2",
    render: ({ status }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "分析分类完成" : "正在分析和分类文件（新架构）..."}
        emoji={themeConfig.showEmoji ? "🎀" : undefined}
      />
    ),
  });

  // 🌸 重试失败的上传
  useRenderToolCall({
    name: "retry_failed_uploads",
    render: ({ status }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "重试完成" : "正在重试失败的上传..."}
        emoji={themeConfig.showEmoji ? "🔄" : undefined}
      />
    ),
  });

  // 🌸 测试工具
  useRenderToolCall({
    name: "test_card",
    render: ({ status, args }) => (
      <ToolCard
        status={status}
        title={status === "complete" ? "测试完成" : "测试中..."}
        subtitle={`等待 ${args?.wait_seconds || 3} 秒 | ${args?.message || "测试消息"}`}
        icon={<RefreshCw className={`w-5 h-5 ${status !== "complete" ? "animate-spin" : ""}`} style={{ color: `var(--color-primary)` }} />}
      />
    ),
  });

  // 🌸 默认工具渲染
  useDefaultTool({
    render: ({ name, args, status }) => {
      const internalTools = ['_classify_directories', '_fetch_metadata', 'emit_state'];
      if (internalTools.some(t => name.includes(t))) {
        return <></>;
      }
      
      const toolInfo = TOOL_DISPLAY_NAMES[name] || { 
        name, 
        description: `正在执行 ${name}`, 
        icon: "✨" 
      };
      
      const formatArgs = (toolArgs: Record<string, unknown>) => {
        if (!toolArgs || Object.keys(toolArgs).length === 0) return null;
        const simplified = Object.entries(toolArgs)
          .filter(([, v]) => typeof v !== 'object')
          .slice(0, 3)
          .map(([k, v]) => `${k}: ${v}`)
          .join(' | ');
        return simplified || null;
      };

      return (
        <ToolCard
          status={status}
          title={status === "complete" ? `✓ ${toolInfo.name}` : `${themeConfig.showEmoji ? toolInfo.icon + ' ' : ''}${toolInfo.name}`}
          subtitle={args && formatArgs(args) ? formatArgs(args) || undefined : undefined}
        />
      );
    },
  });

  // 根据状态获取看板娘心情
  const getMascotMood = () => {
    if (activeTool) return "excited";
    if (agentState?.scan_progress?.status === "scanning") return "thinking";
    if (agentState?.storage_config?.connected) return "happy";
    return "idle";
  };

  const getMascotMessage = () => {
    if (activeTool?.name === "scan_media_files") return "正在努力扫描中~";
    if (activeTool?.name === "connect_webdav") return "连接中...请稍等~";
    if (activeTool) return "处理中~";
    if (agentState?.storage_config?.connected) return "已连接！可以开始了~";
    return undefined;
  };

  // 移动端关闭侧边栏
  const closeSidebar = () => setSidebarOpen(false);

  return (
    <div className="h-screen flex flex-col bg-gradient-main relative overflow-hidden">
      
      {/* 🎀 头部 - 响应式 */}
      <header 
        className="glass py-1.5 flex-shrink-0 relative z-20"
        style={{ borderBottom: `2px solid var(--color-border)` }}
      >
        <div className="flex items-center justify-between px-3">
          {/* 左侧区域 */}
          <div className="flex items-center gap-2">
            {/* 移动端菜单按钮 */}
            {isMobile && (
              <button 
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 rounded-lg transition-colors"
                style={{ 
                  background: `var(--color-primary-50)`,
                  color: `var(--color-primary)`
                }}
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            )}
            
            {/* 标题区域 - 使用主题配置 */}
            <div>
              <h1 className="text-base font-bold flex items-center gap-1.5">
                <span style={{ color: `var(--color-primary)` }}>{themeConfig.appTitle}</span>
                <span 
                  className="text-[10px] text-white px-1.5 py-0.5 rounded-full font-medium"
                  style={{ background: `linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%)` }}
                >
                  v2.0
                </span>
              </h1>
              <p className="text-[10px]" style={{ color: `var(--color-text-secondary)` }}>{themeConfig.appSubtitle}</p>
            </div>
          </div>
          
          {/* 右侧区域 */}
          <div className="flex items-center gap-2">
            {/* 主题切换按钮 */}
            <div className="relative">
              <button 
                onClick={() => setShowThemeMenu(!showThemeMenu)}
                className="p-2 rounded-lg transition-colors"
                style={{ 
                  background: `var(--color-primary-50)`,
                  color: `var(--color-primary)`
                }}
                title="切换主题"
              >
                <Settings className="w-4 h-4" />
              </button>
              
              {/* 主题菜单 */}
              {showThemeMenu && (
                <div 
                  className="absolute right-0 top-full mt-2 w-48 rounded-xl shadow-lg overflow-hidden z-50"
                  style={{ 
                    background: `var(--color-surface)`,
                    border: `1px solid var(--color-border)`
                  }}
                >
                  <div 
                    className="p-2 text-xs font-medium"
                    style={{ 
                      borderBottom: `1px solid var(--color-border)`,
                      color: `var(--color-text-secondary)`
                    }}
                  >
                    选择主题
                  </div>
                  {availableThemes.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => {
                        setTheme(t.id);
                        setShowThemeMenu(false);
                      }}
                      className="w-full px-3 py-2 text-left text-sm transition-colors flex items-center gap-2"
                      style={{ 
                        background: theme.id === t.id ? `var(--color-primary-50)` : 'transparent',
                        color: theme.id === t.id ? `var(--color-primary)` : `var(--color-text-primary)`
                      }}
                    >
                      <span>{t.name}</span>
                      {theme.id === t.id && <Check className="w-4 h-4 ml-auto" />}
                    </button>
                  ))}
                </div>
              )}
            </div>
            
          </div>
        </div>
      </header>

      {/* 🎀 移动端侧边栏遮罩 */}
      {isMobile && sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/30 z-30 backdrop-blur-sm"
          onClick={closeSidebar}
        />
      )}

      {/* 🎀 主内容区 */}
      <main className="flex-1 flex overflow-hidden relative z-10">
        {/* 🎀 左侧状态面板 - 响应式 */}
        <aside className={`
          ${isMobile 
            ? `fixed left-0 top-0 h-full z-40 transform transition-transform duration-300 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}` 
            : 'relative'
          }
          ${isTablet ? 'w-64' : 'w-72'}
          glass flex-shrink-0 flex flex-col
        `}
        style={{ borderRight: `2px solid var(--color-border)` }}
        >
          {/* 🎀 可滚动的内容区域 */}
          <div className="flex-1 overflow-y-auto p-3">
          {/* 看板娘区域 - 根据主题显示 */}
          {theme.decorations.mascot && (
            <div className="mb-4 flex flex-col items-center">
              <Mascot 
                mood={getMascotMood()} 
                message={getMascotMessage()}
                imageUrl={theme.decorations.mascot}
              />
              <p className="text-xs mt-1" style={{ color: `var(--color-text-muted)` }}>
                {themeConfig.mascotName}{themeConfig.showEmoji ? '~ ✨' : ''}
              </p>
            </div>
          )}
          
          <h2 className="text-sm font-bold mb-3 flex items-center gap-2" style={{ color: `var(--color-text-primary)` }}>
            <Star className={`w-4 h-4 ${themeConfig.showAnimations ? 'animate-sparkle' : ''}`} style={{ color: `var(--color-accent)` }} />
            <span style={{ color: `var(--color-primary)` }}>工具执行状态</span>
            {themeConfig.showEmoji && <span className={`text-lg ${themeConfig.showAnimations ? 'animate-twinkle' : ''}`}>✨</span>}
          </h2>
          
          {/* 源存储配置 */}
          {(() => {
            const isConnected = agentState?.storage_config?.url && agentState?.storage_config?.connected !== false;
            return (
              <div 
                className="card-anime p-3 mb-3 transition-all duration-300"
                style={{
                  borderColor: isConnected ? `var(--color-success)` : undefined,
                  boxShadow: isConnected ? `var(--shadow-glow)` : undefined
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <div className={`status-dot ${isConnected ? 'status-connected' : 'status-disconnected'}`} />
                  <span className="text-sm font-semibold" style={{ color: `var(--color-text-primary)` }}>{themeConfig.showEmoji ? '💾 ' : ''}源存储</span>
                  {isConnected && themeConfig.showEmoji && <span className={`text-xs ${themeConfig.animationClasses.sparkle}`}>✦</span>}
                </div>
                {agentState?.storage_config?.url ? (
                  <div className="text-xs space-y-1.5" style={{ color: `var(--color-text-secondary)` }}>
                    <p 
                      className="truncate flex items-center gap-1.5 rounded-lg px-2 py-1"
                      style={{ background: `var(--color-primary-50)` }}
                    >
                      {themeConfig.showEmoji && <span>🔗</span>} {agentState.storage_config.url}
                    </p>
                    <p 
                      className="truncate flex items-center gap-1.5 rounded-lg px-2 py-1"
                      style={{ background: `var(--color-primary-100)` }}
                    >
                      {themeConfig.showEmoji && <span>📂</span>} 扫描: {agentState.storage_config.scan_path || "/"}
                    </p>
                    {agentState.storage_config.target_path && (
                      <p 
                        className="truncate flex items-center gap-1.5 rounded-lg px-2 py-1"
                        style={{ background: `var(--color-primary-50)` }}
                      >
                        {themeConfig.showEmoji && <span>📁</span>} 整理: {agentState.storage_config.target_path}
                      </p>
                    )}
                    <p className="mt-1 text-center" style={{ color: `var(--color-text-muted)` }}>
                      <span 
                        className="px-2 py-0.5 rounded-full"
                        style={{ background: `var(--color-primary-light)`, color: `var(--color-primary-dark)` }}
                      >
                        {themeConfig.showEmoji ? (agentState.storage_config.type === 'alist' ? '✨ Alist' : '🌐 WebDAV') : (agentState.storage_config.type === 'alist' ? 'Alist' : 'WebDAV')}
                      </span>
                    </p>
                  </div>
                ) : (
                  <p className="text-xs text-center py-2" style={{ color: `var(--color-text-muted)` }}>
                    {themeConfig.showEmoji ? '未配置~ 告诉我服务器地址吧 💭' : '未配置'}
                  </p>
                )}
              </div>
            );
          })()}

          {/* STRM 目标配置 */}
          {(() => {
            const isConnected = agentState?.strm_target_config?.url && agentState?.strm_target_config?.connected !== false;
            return (
              <div 
                className="card-anime p-3 mb-3 transition-all duration-300"
                style={{
                  borderColor: isConnected ? `var(--color-secondary)` : undefined,
                  boxShadow: isConnected ? `var(--shadow-glow)` : undefined
                }}
              >
                <div className="flex items-center gap-2 mb-2">
                  <div className={`status-dot ${isConnected ? 'status-connected' : 'status-disconnected'}`} />
                  <span className="text-sm font-semibold" style={{ color: `var(--color-text-primary)` }}>{themeConfig.showEmoji ? '📺 ' : ''}STRM 目标</span>
                  {isConnected && themeConfig.showEmoji && <span className={`text-xs ${themeConfig.animationClasses.sparkle}`}>💫</span>}
                </div>
                {agentState?.strm_target_config?.url ? (
                  <div className="text-xs space-y-1.5" style={{ color: `var(--color-text-secondary)` }}>
                    <p 
                      className="truncate flex items-center gap-1.5 rounded-lg px-2 py-1"
                      style={{ background: `var(--color-primary-50)` }}
                    >
                      {themeConfig.showEmoji && <span>🔗</span>} {agentState.strm_target_config.url}
                    </p>
                    <p 
                      className="truncate flex items-center gap-1.5 rounded-lg px-2 py-1"
                      style={{ background: `var(--color-primary-100)` }}
                    >
                      {themeConfig.showEmoji && <span>📝</span>} 输出: {agentState.strm_target_config.target_path || "/"}
                    </p>
                    {agentState.strm_target_config.type && (
                      <p className="mt-1 text-center" style={{ color: `var(--color-text-muted)` }}>
                        <span 
                          className="px-2 py-0.5 rounded-full"
                          style={{ background: `var(--color-primary-light)`, color: `var(--color-primary-dark)` }}
                        >
                          {themeConfig.showEmoji ? (agentState.strm_target_config.type === 'alist' ? '✨ Alist' : '🌐 WebDAV') : (agentState.strm_target_config.type === 'alist' ? 'Alist' : 'WebDAV')}
                        </span>
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-center py-2" style={{ color: `var(--color-text-muted)` }}>
                    {themeConfig.showEmoji ? '未配置~ (可选) 💭' : '未配置 (可选)'}
                  </p>
                )}
              </div>
            );
          })()}
          
          {/* 🎀 用户配置 */}
          {agentState?.user_config && Object.keys(agentState.user_config).length > 0 && (
            <div className="card-anime p-3 mb-3">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-semibold" style={{ color: `var(--color-text-primary)` }}>⚙️ 配置</span>
                {themeConfig.showAnimations && <span className="text-xs animate-sparkle">✦</span>}
              </div>
              <div className="text-xs grid grid-cols-2 gap-2" style={{ color: `var(--color-text-secondary)` }}>
                {agentState.user_config.scan_delay !== undefined && (
                  <div className="rounded-lg px-2 py-1.5 text-center" style={{ background: `var(--color-surface)` }}>
                    <div className="font-semibold" style={{ color: `var(--color-secondary)` }}>{agentState.user_config.scan_delay}s</div>
                    <div style={{ color: `var(--color-text-muted)` }}>扫描延迟</div>
                  </div>
                )}
                {agentState.user_config.upload_delay !== undefined && (
                  <div className="rounded-lg px-2 py-1.5 text-center" style={{ background: `var(--color-surface)` }}>
                    <div className="font-semibold" style={{ color: `var(--color-primary)` }}>{agentState.user_config.upload_delay}s</div>
                    <div style={{ color: `var(--color-text-muted)` }}>上传延迟</div>
                  </div>
                )}
                {agentState.user_config.naming_language && (
                  <div className="rounded-lg px-2 py-1.5 text-center" style={{ background: `var(--color-surface)` }}>
                    <div className="font-semibold" style={{ color: `var(--color-primary)` }}>{agentState.user_config.naming_language === 'zh' ? '中文' : '英文'}</div>
                    <div style={{ color: `var(--color-text-muted)` }}>命名语言</div>
                  </div>
                )}
                {agentState.user_config.use_copy !== undefined && (
                  <div className="rounded-lg px-2 py-1.5 text-center" style={{ background: `var(--color-surface)` }}>
                    <div className="font-semibold" style={{ color: `var(--color-success)` }}>{agentState.user_config.use_copy ? '复制' : '移动'}</div>
                    <div style={{ color: `var(--color-text-muted)` }}>整理模式</div>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* 🎀 扫描结果摘要 */}
          {agentState?.scan_result && agentState.scan_result.total_files > 0 && (
            <div 
              className="card-anime p-3 mb-3"
              style={{ borderColor: `var(--color-secondary)` }}
            >
              <div className="flex items-center gap-2 mb-3">
                <FolderOpen className="w-4 h-4" style={{ color: `var(--color-secondary)` }} />
                <span className="text-sm font-semibold" style={{ color: `var(--color-text-primary)` }}>📂 扫描结果</span>
                {themeConfig.showAnimations && <span className="text-xs animate-sparkle">✨</span>}
              </div>
              <div className="grid grid-cols-2 gap-3 text-center">
                <div 
                  className="rounded-xl p-3"
                  style={{ 
                    background: `linear-gradient(135deg, var(--color-secondary-light) 0%, var(--color-secondary) 100%)`,
                    border: `1px solid var(--color-secondary)`
                  }}
                >
                  <div 
                    className={`text-2xl font-bold ${themeConfig.showAnimations ? 'animate-soft-pulse' : ''}`}
                    style={{ color: 'white' }}
                  >
                    {agentState.scan_result.video_count || agentState.scan_result.total_files}
                  </div>
                  <div className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.8)' }}>🎬 视频文件</div>
                </div>
                {agentState.scan_result.subtitle_count !== undefined && agentState.scan_result.subtitle_count > 0 && (
                  <div 
                    className="rounded-xl p-3"
                    style={{ 
                      background: `linear-gradient(135deg, var(--color-primary-light) 0%, var(--color-primary) 100%)`,
                      border: `1px solid var(--color-primary)`
                    }}
                  >
                    <div 
                      className={`text-2xl font-bold ${themeConfig.showAnimations ? 'animate-soft-pulse' : ''}`}
                      style={{ color: 'white' }}
                    >
                      {agentState.scan_result.subtitle_count}
                    </div>
                    <div className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.8)' }}>📝 字幕文件</div>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* 🎀 分类结果 */}
          {agentState?.classification_result && Object.keys(agentState.classification_result).length > 0 && (
            <div 
              className="card-anime p-3 mb-3"
              style={{ borderColor: `var(--color-primary)` }}
            >
              <div className="flex items-center gap-2 mb-3">
                <Film className="w-4 h-4" style={{ color: `var(--color-primary)` }} />
                <span className="text-sm font-semibold" style={{ color: `var(--color-text-primary)` }}>🎬 分类结果</span>
                {themeConfig.showAnimations && <span className="text-xs animate-heart-beat">💖</span>}
              </div>
              <div className="space-y-2">
                {Object.entries(agentState.classification_result).map(([tmdbId, info]) => (
                  <div 
                    key={tmdbId} 
                    className="rounded-xl p-3 border-l-4 transition-all hover:scale-[1.02] hover:shadow-md"
                    style={{ 
                      background: `var(--color-surface)`,
                      borderColor: info.type === 'movie' ? `var(--color-accent)` : `var(--color-primary)`
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{info.type === 'movie' ? '🎬' : '📺'}</span>
                      <span className="text-sm font-semibold truncate flex-1" style={{ color: `var(--color-text-primary)` }}>
                        {info.name || `TMDB:${tmdbId}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs mt-2" style={{ color: `var(--color-text-secondary)` }}>
                      <span 
                        className="px-2 py-0.5 rounded-full"
                        style={{ background: `var(--color-primary-50)` }}
                      >
                        {info.file_count} 文件
                      </span>
                    </div>
                    {/* 🆕 按季显示详情 */}
                    {info.seasons && info.seasons.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {info.seasons.map((season) => (
                          <div key={season.season} className="flex items-center gap-2 text-xs" style={{ color: `var(--color-text-muted)` }}>
                            <span 
                              className="px-1.5 py-0.5 rounded"
                              style={{ background: `var(--color-secondary-light)` }}
                            >
                              S{String(season.season).padStart(2, '0')}
                            </span>
                            <span>{season.episode_count} 集</span>
                            <span>{season.ep_range}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {/* 电影或无季信息时显示旧版 ep_range */}
                    {(!info.seasons || info.seasons.length === 0) && info.ep_range !== '-' && (
                      <div className="mt-2 text-xs" style={{ color: `var(--color-text-muted)` }}>
                        <span 
                          className="px-2 py-0.5 rounded-full"
                          style={{ background: `var(--color-secondary-light)` }}
                        >
                          {info.ep_range}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* 🎀 提示信息 */}
          <div 
            className="mt-4 p-3 rounded-xl"
            style={{ 
              background: `linear-gradient(135deg, var(--color-primary-50) 0%, var(--color-primary-100) 100%)`,
              border: `1px solid var(--color-primary-light)`
            }}
          >
            <div className="flex items-start gap-2">
              {themeConfig.showEmoji && <span className={`text-lg ${themeConfig.showAnimations ? 'animate-bounce-soft' : ''}`}>💡</span>}
              <p className="text-xs" style={{ color: `var(--color-text-secondary)` }}>
                {themeConfig.tipText}
              </p>
            </div>
          </div>
          </div>
          
          {/* 🎀 固定在底部的状态栏 - 统一样式 */}
          <div 
            className="flex-shrink-0 p-3"
            style={{ 
              borderTop: `1px solid var(--color-border)`,
              background: `var(--color-surface)`
            }}
          >
            <div 
              className="card-anime p-3"
              style={{ 
                borderColor: (activeTool || isLLMThinking) ? `var(--color-primary)` : undefined,
                boxShadow: (activeTool || isLLMThinking) ? `var(--shadow-glow)` : undefined
              }}
            >
              <div className="flex items-center gap-3">
                {/* 状态图标 */}
                {(activeTool || isLLMThinking) ? (
                  <Loader2 className="w-5 h-5 animate-spin flex-shrink-0" style={{ color: `var(--color-primary)` }} />
                ) : (
                  <div className={`w-5 h-5 flex items-center justify-center flex-shrink-0 ${themeConfig.showAnimations ? 'animate-float-gentle' : ''}`}>
                    💭
                  </div>
                )}
                
                {/* 状态文本 */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold truncate" style={{ color: (activeTool || isLLMThinking) ? `var(--color-primary)` : `var(--color-text-secondary)` }}>
                    {activeTool 
                      ? `${themeConfig.showEmoji ? activeTool.icon + ' ' : ''}${activeTool.displayName}`
                      : isLLMThinking 
                        ? `${themeConfig.showEmoji ? '🧠 ' : ''}分析中...`
                        : '等待任务...'
                    }
                  </div>
                  <div className="text-xs truncate" style={{ color: `var(--color-text-muted)` }}>
                    {activeTool 
                      ? activeTool.description
                      : isLLMThinking 
                        ? '正在分析文件并生成分类结果'
                        : themeConfig.showEmoji ? '在聊天中发送指令开始吧~' : '在聊天中发送指令'
                    }
                  </div>
                </div>
                
                {/* 动画装饰 */}
                {themeConfig.showAnimations && (activeTool || isLLMThinking) && (
                  <span className="text-lg animate-sparkle flex-shrink-0">✨</span>
                )}
              </div>
            </div>
          </div>
        </aside>
        
        {/* 🎀 右侧Chat */}
        <div className="flex-1 overflow-hidden relative">
          
          <CopilotChat
          className="h-full"
          labels={{
            title: themeConfig.appTitle,
            initial: themeConfig.initialMessage,
            placeholder: themeConfig.placeholder,
          }}
        />
        </div>
      </main>
      
      {/* 🎀 移动端底部状态栏 */}
      {isMobile && (
        <div 
          className="glass px-3 py-2 flex-shrink-0 z-20"
          style={{ borderTop: `2px solid var(--color-border)` }}
        >
          <div className="flex items-center justify-between">
            {/* 连接状态 */}
            <div className="flex items-center gap-2">
              <div className={`status-dot ${agentState?.storage_config?.connected ? 'status-connected' : 'status-disconnected'}`} />
              <span className="text-xs" style={{ color: `var(--color-text-secondary)` }}>
                {agentState?.storage_config?.connected 
                  ? (agentState?.storage_config?.type === 'alist' ? 'Alist' : 'WebDAV')
                  : '未连接'}
              </span>
            </div>
            
            {/* 当前任务 */}
            {activeTool && (
              <div className="flex items-center gap-2 text-xs">
                <Loader2 className="w-3 h-3 animate-spin" style={{ color: `var(--color-primary)` }} />
                <span className="truncate max-w-[120px]" style={{ color: `var(--color-text-secondary)` }}>
                  {TOOL_DISPLAY_NAMES[activeTool.name]?.name || activeTool.name}
                </span>
              </div>
            )}
            
            {/* 扫描统计 */}
            {agentState?.scan_result && (
              <div className="flex items-center gap-2 text-xs" style={{ color: `var(--color-text-secondary)` }}>
                <span>🎬 {agentState.scan_result.video_count || agentState.scan_result.total_files || 0}</span>
                <span>📝 {agentState.scan_result.subtitle_count || 0}</span>
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
}
