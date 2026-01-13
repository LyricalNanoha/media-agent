'use client';

import React from 'react';
import { Check, Loader2 } from 'lucide-react';

interface ToolCardProps {
  status: 'idle' | 'executing' | 'complete' | 'error' | 'inProgress';
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  emoji?: string;
  children?: React.ReactNode;
}

/**
 * 通用工具卡片组件
 * 
 * 使用 CSS 变量实现主题化
 */
export function ToolCard({ 
  status, 
  title, 
  subtitle, 
  icon,
  emoji,
  children 
}: ToolCardProps) {
  const isComplete = status === 'complete';
  
  return (
    <div 
      className="flex flex-col gap-2 p-4 rounded-2xl my-3 transition-all"
      style={{
        background: `linear-gradient(135deg, var(--color-surface) 0%, var(--color-primary-50) 100%)`,
        border: `1px solid var(--color-border)`,
        boxShadow: `var(--shadow-md)`,
      }}
    >
      <div className="flex items-center gap-3">
        {/* 状态图标 */}
        <div 
          className="p-2.5 rounded-full transition-colors"
          style={{
            background: isComplete 
              ? `var(--color-success)` 
              : `var(--color-primary-50)`,
          }}
        >
          {isComplete ? (
            <Check className="w-5 h-5 text-white" />
          ) : (
            <Loader2 
              className="w-5 h-5 animate-spin" 
              style={{ color: `var(--color-primary)` }}
            />
          )}
        </div>
        
        {/* 内容 */}
        <div className="flex-1 min-w-0">
          <p 
            className="text-sm font-medium"
            style={{ color: `var(--color-text-primary)` }}
          >
            {title}
          </p>
          {subtitle && (
            <p 
              className="text-xs mt-0.5 truncate"
              style={{ color: `var(--color-text-secondary)` }}
            >
              {subtitle}
            </p>
          )}
        </div>
        
        {/* 右侧图标或 emoji */}
        {icon && <div className="flex-shrink-0">{icon}</div>}
        {emoji && <span className="text-2xl flex-shrink-0">{emoji}</span>}
      </div>
      
      {/* 额外内容 */}
      {children && (
        <div 
          className="mt-2 p-3 rounded-xl backdrop-blur-sm"
          style={{
            background: `var(--color-surface)`,
            border: `1px solid var(--color-border)`,
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export default ToolCard;
