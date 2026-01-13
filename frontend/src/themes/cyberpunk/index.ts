/**
 * 🌆 赛博朋克主题
 * 
 * 科技感霓虹风格
 */

import type { ThemeConfig } from '../types';

export const cyberpunkTheme: ThemeConfig = {
  id: 'cyberpunk',
  name: '🌆 赛博朋克',
  description: '科技感霓虹风格',
  
  // ============ 颜色配置 ============
  // 统一使用青色系，通过深浅区分
  colors: {
    // 主色 - 霓虹青
    primary: '#00D4E4',
    primaryLight: '#4DE8F4',
    primaryDark: '#00A3B3',
    
    // 辅助色 - 深青
    secondary: '#00B4C4',
    secondaryLight: '#33C9D6',
    secondaryDark: '#008A98',
    
    // 强调色 - 亮青
    accent: '#00F0FF',
    accentLight: '#66F5FF',
    accentDark: '#00C4D4',
    
    // 状态色 - 使用主题青色系
    success: '#00E6FF',       // 主题青色
    error: '#FF6B8A',         // 柔和红
    warning: '#FFD166',       // 柔和黄
    
    // 背景 - 深色
    background: '#0D1117',
    backgroundGradient: 'linear-gradient(135deg, #0D1117 0%, #161B22 50%, #0D1117 100%)',
    surface: 'rgba(22, 27, 34, 0.95)',
    
    // 文字
    textPrimary: '#E6EDF3',
    textSecondary: '#8B949E',
    textMuted: '#484F58',
    
    // 边框
    border: 'rgba(0, 212, 228, 0.25)',
    borderHover: 'rgba(0, 212, 228, 0.45)',
  },
  
  // ============ 字体配置 ============
  fonts: {
    primary: '"Orbitron", "Noto Sans SC", -apple-system, sans-serif',
    secondary: '"Noto Sans SC", -apple-system, sans-serif',
  },
  
  // ============ 圆角配置 ============
  radius: {
    sm: '0.25rem',
    md: '0.375rem',
    lg: '0.5rem',
  },
  
  // ============ 阴影配置 ============
  shadows: {
    sm: '0 2px 8px rgba(0, 0, 0, 0.4)',
    md: '0 4px 16px rgba(0, 212, 228, 0.08), 0 2px 8px rgba(0, 0, 0, 0.3)',
    lg: '0 8px 32px rgba(0, 212, 228, 0.12), 0 4px 12px rgba(0, 0, 0, 0.4)',
    glow: '0 0 15px rgba(0, 212, 228, 0.3), 0 0 30px rgba(0, 212, 228, 0.15)',
  },
  
  // ============ 功能开关 ============
  features: {
    showDecorations: false,
    showAnimations: false,
    showEmoji: false,
    showMascot: false,
  },
  
  // ============ 装饰配置 ============
  decorations: {
    mascot: undefined,
    mascotName: undefined,
    particles: 'none',
  },
  
  // ============ 人设配置（同步到后端）============
  persona: {
    name: 'NEXUS-7',
    fullName: 'NEXUS-7 AI Unit',
    style: '科技感强，使用技术术语，偶尔有机械感',
    roleDescription: '高级人工智能数据处理单元',
    emoji: '⚡🔧💻🌐',
    greetings: [
      '[CONNECTED] 数据链路已建立...',
      '系统在线。准备执行媒体整理任务。',
      '连接已建立。等待指令。',
    ],
    successPhrases: ['[SUCCESS] 任务完成。', '[DONE] 进程终止。', '执行成功。'],
    errorPhrases: ['[ERROR] 检测到异常。正在诊断...', '[WARNING] 系统故障。'],
  },
  
  // ============ UI 文案 ============
  ui: {
    appTitle: 'Media Agent',
    appSubtitle: 'AI-Powered Media Management',
    placeholder: 'Enter command...',
    initialMessage: `# SYSTEM ONLINE

**Nova v2.0** - Media Management AI

## AVAILABLE COMMANDS

**1. CONNECT**
Establish connection to storage server.
> connect http://server:port user password

**2. SCAN**
Analyze directory structure and detect media files.

**3. ORGANIZE**
Apply naming conventions:
- Movies: \`Title (Year).mkv\`
- Series: \`Series S01E01.mkv\`

---

**AWAITING INSTRUCTIONS...**`,
    tipText: 'Provide server credentials to initialize.',
    notConfiguredText: 'Not configured',
  },
  
  // ============ 元数据 ============
  meta: {
    title: 'NEXUS-7 // Media Agent',
    favicon: '/favicon.ico',
    mascotImage: '',
  },
};

export default cyberpunkTheme;
