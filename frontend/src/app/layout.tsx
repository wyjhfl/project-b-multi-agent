import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import {
  BarChart3,
  ClipboardCheck,
  LayoutDashboard,
  ListChecks,
  Radar,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
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
  description: "Project B v2.4 试点级运营台、审批台与观测台",
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
              <div className="brand-subtitle">企业试点运营控制台</div>
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
                <span>审批中心</span>
              </Link>
              <Link href="/observability" className="nav-link">
                <Radar size={16} />
                <span>追踪审计</span>
              </Link>
              <Link href="/audit" className="nav-link">
                <ScrollText size={16} />
                <span>审计列表</span>
              </Link>
              <Link href="/metrics" className="nav-link">
                <BarChart3 size={16} />
                <span>指标中心</span>
              </Link>
              <Link href="/rbac" className="nav-link">
                <ShieldCheck size={16} />
                <span>权限说明</span>
              </Link>
            </nav>
          </aside>
          <main className="main-content">{children}</main>
        </div>
      </body>
    </html>
  );
}
