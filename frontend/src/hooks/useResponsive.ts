/**
 * 响应式布局 Hook
 * 
 * 断点设计：
 * - mobile: < 768px
 * - tablet: 768px - 1024px
 * - desktop: > 1024px
 */

import { useState, useEffect } from 'react';

export type ScreenSize = 'mobile' | 'tablet' | 'desktop';

interface ResponsiveState {
  screenSize: ScreenSize;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  width: number;
  height: number;
}

const BREAKPOINTS = {
  mobile: 768,
  tablet: 1024,
} as const;

function getScreenSize(width: number): ScreenSize {
  if (width < BREAKPOINTS.mobile) return 'mobile';
  if (width < BREAKPOINTS.tablet) return 'tablet';
  return 'desktop';
}

export function useResponsive(): ResponsiveState {
  const [state, setState] = useState<ResponsiveState>(() => {
    // SSR 安全的初始值
    if (typeof window === 'undefined') {
      return {
        screenSize: 'desktop',
        isMobile: false,
        isTablet: false,
        isDesktop: true,
        width: 1200,
        height: 800,
      };
    }
    
    const width = window.innerWidth;
    const height = window.innerHeight;
    const screenSize = getScreenSize(width);
    
    return {
      screenSize,
      isMobile: screenSize === 'mobile',
      isTablet: screenSize === 'tablet',
      isDesktop: screenSize === 'desktop',
      width,
      height,
    };
  });

  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const screenSize = getScreenSize(width);
      
      setState({
        screenSize,
        isMobile: screenSize === 'mobile',
        isTablet: screenSize === 'tablet',
        isDesktop: screenSize === 'desktop',
        width,
        height,
      });
    };

    // 初始化
    handleResize();

    // 监听 resize 事件
    window.addEventListener('resize', handleResize);
    
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return state;
}

export default useResponsive;
