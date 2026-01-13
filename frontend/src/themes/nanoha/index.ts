/**
 * 🌸 Nanoha 主题
 * 
 * 温柔可爱的魔法少女风格
 */

import type { ThemeConfig } from '../types';

export const nanohaTheme: ThemeConfig = {
  id: 'nanoha',
  name: '🌸 奈叶',
  description: '温柔可爱的魔法少女风格',
  
  // ============ 颜色配置 ============
  // 🌸 全部统一为粉色系，通过深浅区分
  colors: {
    // 主色 - 标准粉色
    primary: '#FF6B9D',
    primaryLight: '#FFB3C6',
    primaryDark: '#E84A7D',
    
    // 辅助色 - 淡粉/玫瑰粉
    secondary: '#FF8FAB',
    secondaryLight: '#FFCCD5',
    secondaryDark: '#FF5A7D',
    
    // 强调色 - 珊瑚粉
    accent: '#FF7A85',
    accentLight: '#FFD1D4',
    accentDark: '#FF4D5A',
    
    // 状态色 - 全部粉色系
    success: '#FF8FAB',      // 成功 - 淡粉色（柔和的成功感）
    error: '#FF4D6D',        // 错误 - 深粉/玫红（警示但不刺眼）
    warning: '#FF9E9E',      // 警告 - 桃粉色
    
    // 背景 - 粉色渐变
    background: '#FFFFFF',
    backgroundGradient: 'linear-gradient(135deg, #FFFFFF 0%, #FFF0F3 30%, #FFE4EA 70%, #FFF5F7 100%)',
    surface: 'rgba(255, 255, 255, 0.92)',
    
    // 文字
    textPrimary: '#4A2C3D',   // 深粉棕色
    textSecondary: '#7D5A6A', // 中粉棕色
    textMuted: '#B8949F',     // 淡粉灰色
    
    // 边框
    border: 'rgba(255, 107, 157, 0.25)',
    borderHover: 'rgba(255, 107, 157, 0.45)',
  },
  
  // ============ 字体配置 ============
  fonts: {
    primary: '"M PLUS Rounded 1c", "Noto Sans SC", -apple-system, sans-serif',
    secondary: '"Noto Sans SC", -apple-system, sans-serif',
  },
  
  // ============ 圆角配置 ============
  radius: {
    sm: '0.5rem',
    md: '1rem',
    lg: '1.5rem',
  },
  
  // ============ 阴影配置 ============
  shadows: {
    sm: '0 2px 8px rgba(0, 0, 0, 0.05)',
    md: '0 4px 16px rgba(255, 107, 157, 0.1), 0 2px 8px rgba(0, 0, 0, 0.05)',
    lg: '0 8px 32px rgba(255, 107, 157, 0.15), 0 4px 12px rgba(0, 0, 0, 0.08)',
    glow: '0 0 20px rgba(255, 107, 157, 0.3)',
  },
  
  // ============ 功能开关 ============
  features: {
    showDecorations: true,
    showAnimations: true,
    showEmoji: true,
    showMascot: true,
  },
  
  // ============ 装饰配置 ============
  decorations: {
    mascot: '/mascot-1.jpg',
    mascotName: '高町奈叶',
    particles: 'sakura',
  },
  
  // ============ 人设配置（同步到后端）============
  persona: {
    name: '奈叶',
    fullName: '高町奈叶 (Nanoha Takamachi)',
    style: '温柔亲切，常用「呢」「哦」「~」等语气词',
    roleDescription: '一位温柔但坚定的魔法少女',
    emoji: '✨💫🎬💖',
    greetings: [
      '太好了，成功连接到服务器了呢~ ✨',
      '你好呀~ ✨ 我是奈叶，今天要整理什么资源呢？',
      '欢迎回来~ 💖 有什么可以帮你的吗？',
    ],
    successPhrases: ['太好了！✨', '完成啦~！💖', '成功了呢~ 💫'],
    errorPhrases: ['唔...好像出了点问题呢，让我帮你检查一下~', '没关系，让我来帮你解决~'],
  },
  
  // ============ UI 文案 ============
  ui: {
    appTitle: '奈叶的媒体整理助手',
    appSubtitle: 'AI驱动的影视资源管理 🎬',
    placeholder: '告诉奈叶你想做什么~ 例如：连接到我的Alist服务器 💫',
    initialMessage: `# ✨ 你好呀~！我是奈叶！

欢迎~！我是高町奈叶，你的影视资源管理小助手哦~ 💖
让我用魔法帮你管理 WebDAV/Alist 上的影视文件吧！✨

## 🎀 快速开始

**1. 💾 连接服务器**
告诉我你的服务器地址、用户名和密码呢~
> 连接 http://example.com:5244/path 用户名xxx 密码xxx

**2. 📂 扫描文件**
连接成功后，我会帮你扫描目录，找出所有媒体文件哦~

**3. 🎬 整理文件**
我会按 Infuse 命名规范帮你重命名：
- 电影: \`标题 (年份).mkv\`
- 电视剧: \`剧名 S01E01.mkv\`

---

**💖 直接告诉我你想做什么吧~ 我会努力帮你完成的！✨**`,
    tipText: '告诉我服务器地址、用户名和密码来开始吧~ ✨',
    notConfiguredText: '未配置~ 告诉我服务器地址吧 💭',
  },
  
  // ============ 元数据（浏览器标题、favicon 等）============
  meta: {
    title: '奈叶的媒体整理助手 ✨',
    favicon: '/mascot-1.jpg',
    mascotImage: '/mascot-1.jpg',
  },
};

export default nanohaTheme;
