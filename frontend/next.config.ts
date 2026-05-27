import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 将 /api/* 转发到后端，避免浏览器跨域配置复杂化
  async rewrites() {
    const backendBase = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
