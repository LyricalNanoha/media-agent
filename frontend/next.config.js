/** @type {import('next').NextConfig} */
const nextConfig = {
  // 🔥 启用 standalone 输出模式，大幅减少 Docker 镜像大小
  output: 'standalone',
  
  // 允许从后端API获取图片
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'image.tmdb.org',
        pathname: '/t/p/**',
      },
    ],
  },
  // 环境变量（通过环境变量或 Docker 配置覆盖）
  env: {
    BACKEND_URL: process.env.BACKEND_URL || 'http://localhost:8002',
  },
};

module.exports = nextConfig;

