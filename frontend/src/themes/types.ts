/**
 * 主题系统类型定义
 */

export interface ThemeColors {
  // 主色调
  primary: string;
  primaryLight: string;
  primaryDark: string;
  
  // 次要色
  secondary: string;
  secondaryLight: string;
  secondaryDark: string;
  
  // 强调色
  accent: string;
  accentLight: string;
  accentDark: string;
  
  // 状态色
  success: string;
  error: string;
  warning: string;
  
  // 背景
  background: string;
  backgroundGradient: string;
  surface: string;
  
  // 文字
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  
  // 边框
  border: string;
  borderHover: string;
}

export interface ThemeFonts {
  primary: string;
  secondary: string;
}

export interface ThemeRadius {
  sm: string;
  md: string;
  lg: string;
}

export interface ThemeShadows {
  sm: string;
  md: string;
  lg: string;
  glow: string;
}

export interface ThemeFeatures {
  showDecorations: boolean;
  showAnimations: boolean;
  showEmoji: boolean;
  showMascot: boolean;
}

export interface ThemeDecorations {
  mascot?: string;
  mascotName?: string;
  particles: 'sakura' | 'stars' | 'none';
}

export interface ThemePersona {
  name: string;
  fullName: string;           // 完整名称，用于系统提示词
  style: string;              // 说话风格描述
  roleDescription: string;    // 角色描述
  emoji: string;              // 使用的 emoji 集合
  greetings: string[];
  successPhrases: string[];
  errorPhrases: string[];
}

export interface ThemeUI {
  appTitle: string;
  appSubtitle: string;
  placeholder: string;
  initialMessage: string;
  tipText: string;
  notConfiguredText: string;
}

export interface ThemeMeta {
  title: string;           // 浏览器标签页标题
  favicon: string;         // favicon 路径
  mascotImage: string;     // 看板娘图片路径
}

export interface ThemeConfig {
  id: string;
  name: string;
  description: string;
  
  colors: ThemeColors;
  fonts: ThemeFonts;
  radius: ThemeRadius;
  shadows: ThemeShadows;
  
  features: ThemeFeatures;
  decorations: ThemeDecorations;
  persona: ThemePersona;
  ui: ThemeUI;
  meta: ThemeMeta;
}

export interface ThemeContextValue {
  theme: ThemeConfig;
  setTheme: (themeId: string) => void;
  availableThemes: ThemeConfig[];
}
