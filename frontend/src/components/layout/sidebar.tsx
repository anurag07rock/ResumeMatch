"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  IconDashboard,
  IconFileText,
  IconBriefcase,
  IconSparkles,
  IconSettings,
  IconShieldCheck,
} from "../ui/icons";
import { Badge } from "../ui/badge";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

const navItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: IconDashboard },
  { label: "Resumes", href: "/resumes", icon: IconFileText },
  { label: "Jobs", href: "/jobs", icon: IconBriefcase },
  { label: "Matches", href: "/matches", icon: IconSparkles },
  { label: "Settings", href: "/settings", icon: IconSettings },
];

export function Sidebar({ className = "" }: { className?: string }) {
  const pathname = usePathname();

  return (
    <aside
      className={`w-64 shrink-0 flex-col border-r border-slate-800/80 bg-slate-950/80 backdrop-blur-md hidden md:flex ${className}`}
      aria-label="Primary Navigation"
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between px-6 border-b border-slate-800/60">
        <Link
          href="/dashboard"
          className="flex items-center gap-2.5 font-bold text-white text-base tracking-tight focus-ring rounded-md p-1"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white font-black text-sm shadow-sm border border-indigo-500/40">
            RM
          </div>
          <div className="flex flex-col">
            <span className="leading-none font-semibold text-slate-100">ResumeMatch</span>
            <span className="text-[10px] text-slate-400 font-mono mt-0.5">Explainable AI</span>
          </div>
        </Link>
        <Badge variant="indigo" size="sm">
          v1.0
        </Badge>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-4 py-5 space-y-1">
        <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Platform
        </div>
        <nav className="space-y-1" aria-label="Sidebar Sections">
          {navItems.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/dashboard" && pathname.startsWith(item.href));
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-ring ${
                  isActive
                    ? "bg-indigo-600/15 text-indigo-300 border border-indigo-500/25"
                    : "text-slate-400 hover:bg-slate-900 hover:text-slate-200 border border-transparent"
                }`}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon
                  size={18}
                  className={isActive ? "text-indigo-400" : "text-slate-400"}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Architecture Integrity Footer */}
      <div className="p-4 border-t border-slate-800/60">
        <div className="rounded-lg border border-slate-800/80 bg-slate-900/60 p-3 text-xs">
          <div className="flex items-center gap-2 text-slate-300 font-medium mb-1">
            <IconShieldCheck size={14} className="text-emerald-400 shrink-0" />
            <span>Explainable AI Engine</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-normal">
            Deterministic taxonomy extraction + 384-d dense embeddings. Zero hallucination.
          </p>
        </div>
      </div>
    </aside>
  );
}
