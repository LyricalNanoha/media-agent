import type { Metadata } from "next";
import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";
import { ThemeProvider } from "@/themes/ThemeProvider";

export const metadata: Metadata = {
  title: "奈叶的媒体整理助手",
  description: "AI驱动的影视资源管理工具 - 高町奈叶为你服务~ ✨",
  icons: {
    icon: "/mascot-1.jpg",  // 使用看板娘图片作为 favicon
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <ThemeProvider>
          <CopilotKit 
            runtimeUrl="/copilotkit"
            agent="media_agent"
            showDevConsole={false}
          >
            {children}
          </CopilotKit>
        </ThemeProvider>
      </body>
    </html>
  );
}

