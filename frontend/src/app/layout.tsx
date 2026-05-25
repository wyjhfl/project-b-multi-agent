import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { BarChart3, ClipboardCheck, LayoutDashboard, ListChecks } from "lucide-react";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Project B 运营台",
  description: "Project B v2.4.1 试点级运营台与任务中心",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="zh-CN" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <div className="app-shell">
          <aside className="sidebar">
            <div className="brand">
              <div className="brand-title">Project B</div>
              <div className="brand-subtitle">运营试点控制台</div>
            </div>
            <nav className="nav">
              <Link href="/" className="nav-link">
                <LayoutDashboard size={16} />
                <span>Dashboard</span>
              </Link>
              <Link href="/tasks" className="nav-link">
                <ListChecks size={16} />
                <span>任务中心</span>
              </Link>
              <Link href="/approvals" className="nav-link">
                <ClipboardCheck size={16} />
                <span>审批入口</span>
              </Link>
              <Link href="/metrics" className="nav-link">
                <BarChart3 size={16} />
                <span>指标入口</span>
              </Link>
            </nav>
          </aside>
          <main className="main-content">{children}</main>
        </div>
      </body>
    </html>
  );
}
