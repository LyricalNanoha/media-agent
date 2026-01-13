import type { Config } from "tailwindcss";

/**
 * Tailwind CSS 配置
 * 
 * 注意：主题颜色已迁移到 CSS 变量系统 (src/themes/)
 * 组件应直接使用 style={{ color: `var(--color-primary)` }} 等方式
 * 而不是 Tailwind 颜色类
 */
const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"M PLUS Rounded 1c"', '"Noto Sans SC"', '-apple-system', 'sans-serif'],
        display: ['"M PLUS Rounded 1c"', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'float': 'float 4s ease-in-out infinite',
        'float-delay': 'float-delay 5s ease-in-out infinite 1s',
        'twinkle': 'twinkle 2s ease-in-out infinite',
        'soft-pulse': 'soft-pulse 3s ease-in-out infinite',
        'sakura-fall': 'sakura-fall 10s linear infinite',
        'gradient': 'gradient-shift 3s ease infinite',
        'bounce-soft': 'bounce-soft 1s ease-in-out infinite',
        'wiggle': 'wiggle 0.5s ease-in-out infinite',
        'tilt': 'tilt 2s ease-in-out infinite',
        'sway': 'sway 3s ease-in-out infinite',
        'float-gentle': 'float-gentle 3s ease-in-out infinite',
        'pop-in': 'pop-in 0.3s ease-out forwards',
        'sparkle': 'sparkle 1.5s ease-in-out infinite',
        'heart-beat': 'heart-beat 1s ease-in-out infinite',
        'rainbow': 'rainbow-shift 5s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
          '50%': { transform: 'translateY(-10px) rotate(5deg)' },
        },
        'float-delay': {
          '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
          '50%': { transform: 'translateY(-8px) rotate(-5deg)' },
        },
        twinkle: {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.5', transform: 'scale(0.9)' },
        },
        'soft-pulse': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.85', transform: 'scale(0.98)' },
        },
        'sakura-fall': {
          '0%': { transform: 'translateY(-10px) translateX(0) rotate(0deg)', opacity: '0' },
          '10%': { opacity: '0.8' },
          '100%': { transform: 'translateY(100vh) translateX(50px) rotate(360deg)', opacity: '0' },
        },
        'gradient-shift': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        'bounce-soft': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        wiggle: {
          '0%, 100%': { transform: 'rotate(0deg)' },
          '25%': { transform: 'rotate(-5deg)' },
          '75%': { transform: 'rotate(5deg)' },
        },
        tilt: {
          '0%, 100%': { transform: 'rotate(0deg)' },
          '50%': { transform: 'rotate(5deg)' },
        },
        sway: {
          '0%, 100%': { transform: 'translateX(0)' },
          '50%': { transform: 'translateX(3px)' },
        },
        'float-gentle': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-5px)' },
        },
        'pop-in': {
          '0%': { transform: 'translateX(-50%) scale(0.8)', opacity: '0' },
          '50%': { transform: 'translateX(-50%) scale(1.05)' },
          '100%': { transform: 'translateX(-50%) scale(1)', opacity: '1' },
        },
        sparkle: {
          '0%, 100%': { opacity: '1', transform: 'scale(1) rotate(0deg)' },
          '50%': { opacity: '0.6', transform: 'scale(0.8) rotate(180deg)' },
        },
        'heart-beat': {
          '0%, 100%': { transform: 'scale(1)' },
          '25%': { transform: 'scale(1.1)' },
          '50%': { transform: 'scale(1)' },
          '75%': { transform: 'scale(1.1)' },
        },
        'rainbow-shift': {
          '0%': { filter: 'hue-rotate(0deg)' },
          '100%': { filter: 'hue-rotate(360deg)' },
        },
      },
      borderRadius: {
        '4xl': '2rem',
        '5xl': '2.5rem',
      },
    },
  },
  plugins: [],
};

export default config;
