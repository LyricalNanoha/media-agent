"use client";

import { useState, useEffect } from "react";
import Image from "next/image";

type MascotMood = "idle" | "happy" | "thinking" | "excited" | "sleepy";

interface MascotProps {
  mood?: MascotMood;
  message?: string;
  className?: string;
  /** 自定义图片URL，如果提供则使用图片替代CSS绘制的角色 */
  imageUrl?: string;
}

// 🌟 看板娘组件 - 支持自定义图片
export function Mascot({ mood = "idle", message, className = "", imageUrl }: MascotProps) {
  const [currentMood, setCurrentMood] = useState<MascotMood>(mood);
  const [showBubble, setShowBubble] = useState(!!message);

  useEffect(() => {
    setCurrentMood(mood);
  }, [mood]);

  useEffect(() => {
    setShowBubble(!!message);
  }, [message]);

  // 根据心情获取动画类
  const getMoodAnimation = () => {
    switch (currentMood) {
      case "happy":
        return "animate-bounce-soft";
      case "excited":
        return "animate-wiggle";
      case "thinking":
        return "animate-tilt";
      case "sleepy":
        return "animate-sway";
      default:
        return "animate-float-gentle";
    }
  };

  // 根据心情获取表情 emoji
  const getMoodEmoji = () => {
    switch (currentMood) {
      case "happy":
        return "😊";
      case "thinking":
        return "🤔";
      case "excited":
        return "✨";
      case "sleepy":
        return "😴";
      default:
        return "💫";
    }
  };

  return (
    <div className={`relative ${className}`}>
      {/* 对话气泡 */}
      {showBubble && message && (
        <div 
          className="absolute -top-14 left-1/2 -translate-x-1/2 bg-white rounded-2xl px-3 py-1.5 shadow-lg min-w-max z-10" 
          style={{ 
            animation: "pop-in 0.3s ease-out",
            border: "2px solid #B8D4FF"
          }}
        >
          <p className="text-xs text-gray-700 font-medium whitespace-nowrap">{message}</p>
          {/* 气泡尾巴 */}
          <div 
            className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-white rotate-45" 
            style={{ borderRight: "2px solid #B8D4FF", borderBottom: "2px solid #B8D4FF" }}
          />
        </div>
      )}

      {/* 看板娘主体 */}
      <div className={`relative ${getMoodAnimation()}`}>
        {/* 魔法光环效果 */}
        {currentMood === "excited" && (
          <div 
            className="absolute -inset-4 rounded-full opacity-40"
            style={{ 
              background: "radial-gradient(circle, #FFD70050 0%, transparent 70%)",
              animation: "soft-pulse 2s ease-in-out infinite"
            }}
          />
        )}

        {imageUrl ? (
          // 使用自定义图片/SVG
          <div className="relative w-28 h-32">
            <Image
              src={imageUrl}
              alt="Mascot"
              fill
              className="object-contain"
              unoptimized
            />
            {/* 心情指示器 */}
            <div className="absolute -top-2 -right-2 text-xl bg-white/80 rounded-full p-1 shadow-sm">
              {getMoodEmoji()}
            </div>
          </div>
        ) : (
          // 默认的简洁魔法少女风格
          <div className="relative">
            {/* 简洁的魔法少女图标 */}
            <div className="w-20 h-20 relative">
              {/* 魔法阵背景 */}
              <div 
                className="absolute inset-0 rounded-full opacity-20"
                style={{ 
                  background: "conic-gradient(from 0deg, #5BA3FF, #FFD700, #E63946, #6B5BCD, #5BA3FF)",
                  animation: "spin 10s linear infinite"
                }}
              />
              
              {/* 主体圆形 */}
              <div 
                className="absolute inset-1 rounded-full bg-gradient-to-br from-white to-blue-50 shadow-lg flex items-center justify-center"
                style={{ border: "3px solid #5BA3FF" }}
              >
                {/* 魔法杖图标 */}
                <svg 
                  viewBox="0 0 24 24" 
                  className="w-10 h-10"
                  fill="none"
                  stroke="#5BA3FF"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  {/* 杖身 */}
                  <line x1="4" y1="20" x2="20" y2="4" />
                  {/* 星星顶部 */}
                  <polygon 
                    points="20,4 17,7 20,10 23,7" 
                    fill="#FFD700" 
                    stroke="#FFD700"
                  />
                  {/* 小星星装饰 */}
                  <circle cx="8" cy="16" r="1" fill="#E63946" />
                  <circle cx="12" cy="12" r="1" fill="#6B5BCD" />
                </svg>
              </div>
              
              {/* 闪烁星星 */}
              <div className="absolute -top-1 -right-1 text-sm" style={{ animation: "twinkle 2s ease-in-out infinite" }}>✦</div>
              <div className="absolute -bottom-1 -left-1 text-xs" style={{ animation: "twinkle 2s ease-in-out infinite 0.5s" }}>✦</div>
            </div>
            
            {/* 心情指示器 */}
            <div className="absolute -top-2 left-1/2 -translate-x-1/2 text-lg">
              {getMoodEmoji()}
            </div>
          </div>
        )}

        {/* 发光效果 */}
        {currentMood === "excited" && (
          <>
            <div className="absolute -top-3 -left-3 text-base text-yellow-400" style={{ animation: "twinkle 2s ease-in-out infinite" }}>✦</div>
            <div className="absolute -top-2 -right-4 text-sm text-yellow-400" style={{ animation: "twinkle 2s ease-in-out infinite 0.3s" }}>✦</div>
          </>
        )}
      </div>
    </div>
  );
}

// 🌸 迷你看板娘（用于角落装饰）
export function MiniMascot({ className = "" }: { className?: string }) {
  return (
    <div className={`text-4xl animate-float-gentle cursor-pointer hover:scale-110 transition-transform ${className}`}>
      <span className="inline-block hover:animate-wiggle">🐱</span>
    </div>
  );
}

// 🌸 看板娘对话气泡
export function MascotBubble({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`relative bg-white/90 backdrop-blur-sm rounded-2xl px-4 py-3 shadow-lg border-2 border-sakura-200 ${className}`}>
      {children}
      <div className="absolute -bottom-2 left-6 w-4 h-4 bg-white border-r-2 border-b-2 border-sakura-200 rotate-45" />
    </div>
  );
}

