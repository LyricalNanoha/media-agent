/**
 * ⚪ 极简主题
 * 
 * 简约专业风格
 */

import type { ThemeConfig } from '../types';

export const minimalTheme: ThemeConfig = {
  id: 'minimal',
  name: '⚪ 极简',
  description: '简约专业风格',
  
  // ============ 颜色配置 ============
  colors: {
    primary: '#3B82F6',       // 蓝色
    primaryLight: '#DBEAFE',
    primaryDark: '#1D4ED8',
    
    secondary: '#64748B',     // 灰蓝
    secondaryLight: '#E2E8F0',
    secondaryDark: '#475569',
    
    accent: '#059669',        // 绿色
    accentLight: '#D1FAE5',
    accentDark: '#047857',
    
    success: '#059669',
    error: '#DC2626',
    warning: '#D97706',
    
    background: '#FFFFFF',
    backgroundGradient: 'linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%)',
    surface: 'rgba(255, 255, 255, 0.95)',
    
    textPrimary: '#1E293B',
    textSecondary: '#475569',
    textMuted: '#94A3B8',
    
    border: '#E2E8F0',
    borderHover: '#CBD5E1',
  },
  
  // ============ 字体配置 ============
  fonts: {
    primary: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    secondary: '-apple-system, BlinkMacSystemFont, sans-serif',
  },
  
  // ============ 圆角配置 ============
  radius: {
    sm: '0.375rem',
    md: '0.5rem',
    lg: '0.75rem',
  },
  
  // ============ 阴影配置 ============
  shadows: {
    sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
    md: '0 4px 16px rgba(0, 0, 0, 0.05), 0 1px 4px rgba(0, 0, 0, 0.03)',
    lg: '0 8px 24px rgba(0, 0, 0, 0.08), 0 2px 8px rgba(0, 0, 0, 0.05)',
    glow: 'none',
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
    name: '助手',
    fullName: '智能助手',
    style: '简洁专业，直接高效',
    roleDescription: '专业的影视资源管理助手',
    emoji: '',
    greetings: [
      '已连接到服务器。',
      '你好，我是媒体整理助手。请告诉我需要处理的任务。',
    ],
    successPhrases: ['完成。', '操作成功。'],
    errorPhrases: ['操作失败，请检查配置。', '出现错误。'],
  },
  
  // ============ UI 文案 ============
  ui: {
    appTitle: '媒体整理助手',
    appSubtitle: 'AI 驱动的影视资源管理',
    placeholder: '输入指令，例如：连接到 Alist 服务器',
    initialMessage: `# 媒体整理助手

欢迎使用媒体整理工具。

## 快速开始

**1. 连接服务器**
提供服务器地址、用户名和密码。

**2. 扫描文件**
扫描目录，识别媒体文件。

**3. 整理文件**
按照标准命名规范重命名：
- 电影: \`标题 (年份).mkv\`
- 电视剧: \`剧名 S01E01.mkv\`

---

请告诉我你需要执行的操作。`,
    tipText: '请提供服务器地址、用户名和密码以开始。',
    notConfiguredText: '未配置',
  },
  
  // ============ 元数据 ============
  meta: {
    title: '媒体整理助手',
    favicon: '/favicon.ico',
    mascotImage: '',
  },
};

export default minimalTheme;
