'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { ThemeContext, themes, defaultTheme, applyTheme } from './';
import type { ThemeConfig } from './types';

// 导入主题样式
import './base/variables.css';
import './base/components.css';
import './base/animations.css';
import './nanoha/overrides.css';
import './minimal/overrides.css';
import './cyberpunk/overrides.css';
import './silverwolf/overrides.css';

const THEME_STORAGE_KEY = 'media-assistant-theme';

/**
 * 应用主题的元数据（title、favicon）
 */
function applyThemeMeta(theme: ThemeConfig): void {
  if (typeof document === 'undefined') return;
  
  // 更新页面标题
  document.title = theme.meta.title;
  
  // 更新 favicon
  const faviconLink = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (faviconLink && theme.meta.favicon) {
    faviconLink.href = theme.meta.favicon;
  } else if (theme.meta.favicon) {
    const newFavicon = document.createElement('link');
    newFavicon.rel = 'icon';
    newFavicon.href = theme.meta.favicon;
    document.head.appendChild(newFavicon);
  }
  
  console.log('📄 Applied theme meta:', theme.meta.title);
}

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<ThemeConfig>(defaultTheme);
  const [mounted, setMounted] = useState(false);

  // 从 localStorage 加载主题
  useEffect(() => {
    setMounted(true);
    
    const savedThemeId = localStorage.getItem(THEME_STORAGE_KEY);
    if (savedThemeId && themes[savedThemeId]) {
      const savedTheme = themes[savedThemeId];
      setThemeState(savedTheme);
      applyTheme(savedTheme);
      applyThemeMeta(savedTheme);
    } else {
      applyTheme(defaultTheme);
      applyThemeMeta(defaultTheme);
    }
  }, []);

  // 切换主题
  const setTheme = useCallback((themeId: string) => {
    const newTheme = themes[themeId];
    if (!newTheme) {
      console.warn(`Theme "${themeId}" not found`);
      return;
    }
    
    console.log('🎨 Switching theme to:', themeId);
    
    setThemeState(newTheme);
    applyTheme(newTheme);
    applyThemeMeta(newTheme);
    localStorage.setItem(THEME_STORAGE_KEY, themeId);
    
    // 添加过渡动画
    document.body.classList.add('theme-transitioning');
    setTimeout(() => {
      document.body.classList.remove('theme-transitioning');
    }, 300);
  }, []);

  // 防止 SSR 闪烁
  if (!mounted) {
    return null;
  }

  return (
    <ThemeContext.Provider 
      value={{ 
        theme, 
        setTheme, 
        availableThemes: Object.values(themes) 
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export default ThemeProvider;
