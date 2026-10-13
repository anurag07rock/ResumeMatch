"use client";

import React, { useState } from "react";
import { usePathname } from "next/navigation";
import { MobileNav } from "./mobile-nav";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { useAuth } from "../../lib/auth-context";

const titles: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Dashboard",
    subtitle: "Overview of your resumes, job descriptions, and AI match scores",
  },
  "/resumes": {
    title: "Resume Library",
    subtitle: "Manage uploaded candidate resumes, parsed entities, and embeddings",
  },
  "/jobs": {
    title: "Job Requirements",
    subtitle: "Ingest and analyze job postings for taxonomy skill extraction",
  },
  "/matches": {
    title: "Match History & Analysis",
    subtitle: "Explainable multi-dimensional evaluations and attribution breakdown",
  },
  "/settings": {
    title: "Platform Settings",
    subtitle: "Configure scoring weights, privacy options, and API endpoints",
  },
};

export function Header() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const current = titles[pathname] || {
    title: "ResumeMatch",
    subtitle: "Explainable AI-Powered Resume Matching",
  };

  const handleLogout = async () => {
    setIsLoggingOut(true);
    await logout();
  };

  // Extract initials
  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : "RM";

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between border-b border-slate-800/80 bg-slate-950/80 px-4 sm:px-6 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <MobileNav />
        <div>
          <h1 className="text-base sm:text-lg font-bold tracking-tight text-white leading-tight">
            {current.title}
          </h1>
          <p className="text-xs text-slate-400 hidden sm:block leading-none mt-0.5">
            {current.subtitle}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* System API Indicator */}
        <div className="hidden lg:flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/60 px-3 py-1 text-xs text-slate-300">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true" />
          <span className="font-mono text-[11px] text-slate-400">API: /api/v1</span>
        </div>

        {/* Authenticated User Profile & Logout Action */}
        <div className="flex items-center gap-2.5 pl-2 border-l border-slate-800/80">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600/20 border border-indigo-500/30 text-indigo-300 text-xs font-semibold">
            {initials}
          </div>
          <div className="hidden sm:flex flex-col text-left max-w-[140px] truncate">
            <span className="text-xs font-medium text-slate-200 truncate">
              {user?.full_name || user?.email || "Authenticated User"}
            </span>
            <span className="text-[10px] text-slate-400 font-mono truncate">
              {user?.email || "Session Active"}
            </span>
          </div>

          <Badge variant="indigo" size="sm" className="hidden xl:inline-flex">
            Active
          </Badge>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            isLoading={isLoggingOut}
            className="text-xs text-slate-400 hover:text-rose-400 hover:bg-rose-950/20 ml-1"
          >
            Log Out
          </Button>
        </div>
      </div>
    </header>
  );
}
