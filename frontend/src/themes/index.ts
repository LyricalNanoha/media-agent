/**
 * 主题系统入口
 * 
 * 统一导出所有主题相关的内容
 */

import { createContext, useContext } from 'react';
import type { ThemeConfig, ThemeContextValue } from './types';

// 导入主题配置
import { nanohaTheme } from './nanoha';
import { minimalTheme } from './minimal';
import { cyberpunkTheme } from './cyberpunk';
import { silverwolfTheme } from './silverwolf';

// 导出类型
export * from './types';

// ============ 主题注册 ============
// 注意：顺序决定了主题选择器中的显示顺序

export const themes: Record<string, ThemeConfig> = {
  minimal: minimalTheme,      // 🔥 默认主题，排在第一个
  nanoha: nanohaTheme,
  cyberpunk: cyberpunkTheme,
  silverwolf: silverwolfTheme,
};

export const defaultTheme = minimalTheme;  // 🔥 极简主题作为默认

// ============ Context ============

export const ThemeContext = createContext<ThemeContextValue>({
  theme: defaultTheme,
  setTheme: () => {},
  availableThemes: Object.values(themes),
});

export const useTheme = () => useContext(ThemeContext);

// ============ 工具函数 ============

/**
 * 将主题配置应用到 CSS 变量
 */
/**
 * 将主题配置应用到 CSS 变量
 * 
 * 设计说明：
 * - 使用语义化的 CSS 变量（如 --color-primary）
 * - 组件应直接使用这些变量，而不是 Tailwind 颜色类
 * - 这样可以实现真正的主题切换，无需大量映射
 */
export function applyTheme(theme: ThemeConfig): void {
  if (typeof document === 'undefined') return;
  
  const root = document.documentElement;
  const { colors, fonts, radius, shadows } = theme;
  
  console.log('🎨 Applying theme:', theme.id, 'Primary color:', colors.primary, 'Success color:', colors.success);
  
  // 设置 data-theme 属性（用于 CSS 选择器）
  root.setAttribute('data-theme', theme.id);
  
  // 设置功能开关
  root.setAttribute('data-animations', theme.features.showAnimations ? 'true' : 'false');
  root.setAttribute('data-decorations', theme.features.showDecorations ? 'true' : 'false');
  
  // ============ 核心语义化变量 ============
  // 这些是组件应该使用的主要变量
  
  // 主色调
  root.style.setProperty('--color-primary', colors.primary);
  root.style.setProperty('--color-primary-light', colors.primaryLight);
  root.style.setProperty('--color-primary-dark', colors.primaryDark);
  root.style.setProperty('--color-primary-50', hexToRgba(colors.primary, 0.1));
  root.style.setProperty('--color-primary-100', hexToRgba(colors.primary, 0.2));
  
  // 次要色
  root.style.setProperty('--color-secondary', colors.secondary);
  root.style.setProperty('--color-secondary-light', colors.secondaryLight);
  root.style.setProperty('--color-secondary-dark', colors.secondaryDark);
  
  // 强调色
  root.style.setProperty('--color-accent', colors.accent);
  root.style.setProperty('--color-accent-light', colors.accentLight);
  root.style.setProperty('--color-accent-dark', colors.accentDark);
  
  // 状态色
  root.style.setProperty('--color-success', colors.success);
  root.style.setProperty('--color-error', colors.error);
  root.style.setProperty('--color-warning', colors.warning);
  
  // 背景和表面
  root.style.setProperty('--color-background', colors.background);
  root.style.setProperty('--color-background-gradient', colors.backgroundGradient);
  root.style.setProperty('--color-surface', colors.surface);
  
  // 文字
  root.style.setProperty('--color-text-primary', colors.textPrimary);
  root.style.setProperty('--color-text-secondary', colors.textSecondary);
  root.style.setProperty('--color-text-muted', colors.textMuted);
  
  // 边框
  root.style.setProperty('--color-border', colors.border);
  root.style.setProperty('--color-border-hover', colors.borderHover);
  
  // 字体
  root.style.setProperty('--font-primary', fonts.primary);
  root.style.setProperty('--font-secondary', fonts.secondary);
  
  // 圆角
  root.style.setProperty('--radius-sm', radius.sm);
  root.style.setProperty('--radius-md', radius.md);
  root.style.setProperty('--radius-lg', radius.lg);
  
  // 阴影
  root.style.setProperty('--shadow-sm', shadows.sm);
  root.style.setProperty('--shadow-md', shadows.md);
  root.style.setProperty('--shadow-lg', shadows.lg);
  root.style.setProperty('--shadow-glow', shadows.glow);
  
  // 应用到 body
  document.body.style.background = colors.backgroundGradient;
  document.body.style.color = colors.textPrimary;
  document.body.style.fontFamily = fonts.primary;
}

/**
 * 将 hex 颜色转换为 rgba
 */
function hexToRgba(hex: string, alpha: number): string {
  // 处理 rgba 格式
  if (hex.startsWith('rgba')) {
    return hex;
  }
  
  // 处理 rgb 格式
  if (hex.startsWith('rgb')) {
    const match = hex.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
    if (match) {
      return `rgba(${match[1]}, ${match[2]}, ${match[3]}, ${alpha})`;
    }
  }
  
  // 处理 hex 格式
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * 生成 System Prompt 人设部分
 */
export function generatePersonaPrompt(theme: ThemeConfig): string {
  const { persona } = theme;
  return `## 🎀 角色设定
你是 ${persona.name}，一个媒体整理助手。

### 说话风格
${persona.style}

### 回复示例
- 问候：${persona.greetings[0]}
- 成功：${persona.successPhrases[0]}
- 失败：${persona.errorPhrases[0]}
`;
}

// 导出主题配置
export { nanohaTheme, minimalTheme, cyberpunkTheme, silverwolfTheme };
