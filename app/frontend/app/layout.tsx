import type { Metadata } from "next";
import Link from "next/link";
import { Database, Clock, Settings } from "lucide-react";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAG Knowledge Base",
  description: "Upload, index, and query your documents with source transparency.",
};

const NAV_ITEMS = [
  { label: "Collections", href: "/collections", icon: Database },
  { label: "Recent", href: "/collections", icon: Clock },
  { label: "Settings", href: "#", icon: Settings },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <aside className="flex w-56 flex-col bg-sidebar text-sidebar-foreground shrink-0">
          <div className="flex h-14 items-center border-b border-sidebar-accent px-4">
            <span className="text-sm font-bold tracking-tight">
              RAG Knowledge Base
            </span>
          </div>
          <nav className="flex-1 space-y-1 px-2 py-4" aria-label="Main navigation">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.label}
                href={item.href}
                className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="border-t border-sidebar-accent px-4 py-3 text-xs text-sidebar-foreground/50">
            Phase 1 MVP
          </div>
        </aside>

        {/* Main content area */}
        <main className="flex-1 overflow-y-auto bg-background">
          {children}
        </main>
      </body>
    </html>
  );
}