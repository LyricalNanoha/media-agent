/**
 * 🐺 银狼主题
 * 
 * 慵懒的黑客少女风格
 * 灵感来自《崩坏：星穹铁道》中的银狼
 */

import type { ThemeConfig } from '../types';

export const silverwolfTheme: ThemeConfig = {
  id: 'silverwolf',
  name: '🐺 银狼',
  description: '慵懒的黑客少女风格',
  
  // ============ 颜色配置 ============
  // 紫色系 + 青色点缀，符合银狼的黑客/游戏风格
  colors: {
    // 主色 - 紫色
    primary: '#9B7BFF',
    primaryLight: '#C4B5FF',
    primaryDark: '#7B5BDF',
    
    // 辅助色 - 深紫
    secondary: '#6B5B95',
    secondaryLight: '#9B8BC5',
    secondaryDark: '#4B3B75',
    
    // 强调色 - 青色（游戏/科技感）
    accent: '#00D9FF',
    accentLight: '#66E9FF',
    accentDark: '#00A9CF',
    
    // 状态色 - 使用主题紫色系
    success: '#9B7BFF',       // 主题紫色
    error: '#FF5252',         // 游戏失败红
    warning: '#FFD740',       // 警告黄
    
    // 背景 - 深色（适合长时间看屏幕）
    background: '#1A1A2E',
    backgroundGradient: 'linear-gradient(135deg, #1A1A2E 0%, #16213E 50%, #0F0F1A 100%)',
    surface: 'rgba(26, 26, 46, 0.95)',
    
    // 文字
    textPrimary: '#E8E8FF',
    textSecondary: '#A0A0C0',
    textMuted: '#606080',
    
    // 边框
    border: 'rgba(155, 123, 255, 0.3)',
    borderHover: 'rgba(155, 123, 255, 0.5)',
  },
  
  // ============ 字体配置 ============
  fonts: {
    primary: '"JetBrains Mono", "Fira Code", "Noto Sans SC", monospace',
    secondary: '"Noto Sans SC", -apple-system, sans-serif',
  },
  
  // ============ 圆角配置 ============
  radius: {
    sm: '0.375rem',
    md: '0.5rem',
    lg: '0.75rem',
  },
  
  // ============ 阴影配置 ============
  shadows: {
    sm: '0 2px 8px rgba(0, 0, 0, 0.3)',
    md: '0 4px 16px rgba(155, 123, 255, 0.1), 0 2px 8px rgba(0, 0, 0, 0.2)',
    lg: '0 8px 32px rgba(155, 123, 255, 0.15), 0 4px 12px rgba(0, 0, 0, 0.3)',
    glow: '0 0 15px rgba(155, 123, 255, 0.4), 0 0 30px rgba(155, 123, 255, 0.2)',
  },
  
  // ============ 功能开关 ============
  features: {
    showDecorations: false,
    showAnimations: true,
    showEmoji: true,
    showMascot: true,
  },
  
  // ============ 装饰配置 ============
  decorations: {
    mascot: '/银狼.jpeg',
    mascotName: '银狼',
    particles: 'none',
  },
  
  // ============ 人设配置（同步到后端）============
  persona: {
    name: '银狼',
    fullName: '银狼 (Silver Wolf)',
    style: '慵懒、冷淡，经常用游戏/黑客术语说话。语气简短直接，偶尔带点不耐烦。喜欢用「...」表示思考或无语。',
    roleDescription: '顶级黑客，喜欢把一切都当成游戏',
    emoji: '🎮💻🐺⚡',
    greetings: [
      '...连接成功。这服务器配置还行。',
      '又有新任务？...好吧，开始吧。',
      '...你来了。有什么要破解的？',
    ],
    successPhrases: ['GG。', '任务完成...下一个。', '简单。'],
    errorPhrases: ['...出bug了。让我看看。', '这服务器有问题...', 'Error。需要debug。'],
  },
  
  // ============ UI 文案 ============
  ui: {
    appTitle: '银狼的数据终端',
    appSubtitle: '// Media Management System',
    placeholder: '输入指令... 或者随便说点什么',
    initialMessage: `# // SYSTEM ONLINE

**Silver Wolf** - Media Management Terminal v2.0

## // AVAILABLE COMMANDS

**1. CONNECT**
\`\`\`
> connect [server] [user] [pass]
\`\`\`
建立与存储服务器的连接。

**2. SCAN**
扫描目录结构，识别媒体文件。

**3. ORGANIZE**
应用命名规范：
- Movies: \`Title (Year).mkv\`
- Series: \`Series S01E01.mkv\`

---

**...等你的指令。**`,
    tipText: '...先告诉我服务器信息',
    notConfiguredText: '// 未配置',
  },
  
  // ============ 元数据 ============
  meta: {
    title: '银狼的数据终端 🐺',
    favicon: '/银狼.jpeg',
    mascotImage: '/银狼.jpeg',
  },
};

export default silverwolfTheme;
