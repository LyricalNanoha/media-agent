/**
 * 主题配置 Hook
 * 
 * 返回当前主题的 UI 配置
 */

import { useTheme } from '@/themes';
import type { ThemeConfig } from '@/themes/types';

export interface ThemeUIConfig {
  // 文本内容
  appTitle: string;
  appSubtitle: string;
  mascotName?: string;
  
  // 初始消息
  initialMessage: string;
  placeholder: string;
  tipText: string;
  notConfiguredText: string;
  
  // 装饰元素
  showDecorations: boolean;
  showAnimations: boolean;
  showEmoji: boolean;
  showMascot: boolean;
  mascotUrl?: string;
  
  // 头部装饰 emoji
  headerEmoji: string[];
  
  // 动画类名
  animationClasses: {
    float: string;
    pulse: string;
    sparkle: string;
  };
}

export function useThemeConfig(): ThemeUIConfig {
  const { theme } = useTheme();
  
  // 根据主题生成头部装饰 emoji
  const getHeaderEmoji = (): string[] => {
    if (!theme.features.showEmoji) return [];
    
    // 根据主题 ID 返回不同的 emoji
    switch (theme.id) {
      case 'nanoha':
        return ['✨', '💖'];
      case 'cyberpunk':
        return ['⚡', '🔥'];
      default:
        return [];
    }
  };
  
  return {
    appTitle: theme.ui.appTitle,
    appSubtitle: theme.ui.appSubtitle,
    mascotName: theme.decorations.mascotName,
    
    initialMessage: theme.ui.initialMessage,
    placeholder: theme.ui.placeholder,
    tipText: theme.ui.tipText,
    notConfiguredText: theme.ui.notConfiguredText,
    
    showDecorations: theme.features.showDecorations,
    showAnimations: theme.features.showAnimations,
    showEmoji: theme.features.showEmoji,
    showMascot: theme.features.showMascot,
    mascotUrl: theme.decorations.mascot,
    
    headerEmoji: getHeaderEmoji(),
    
    animationClasses: {
      float: theme.features.showAnimations ? 'animate-float' : '',
      pulse: theme.features.showAnimations ? 'animate-soft-pulse' : '',
      sparkle: theme.features.showAnimations ? 'animate-sparkle' : '',
    },
  };
}

export default useThemeConfig;
