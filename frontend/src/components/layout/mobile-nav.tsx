"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  IconDashboard,
  IconFileText,
  IconBriefcase,
  IconSparkles,
  IconSettings,
  IconMenu,
  IconX,
  IconShieldCheck,
} from "../ui/icons";
import { Badge } from "../ui/badge";

const navItems = [
  { label: "Dashboard", href: "/dashboard", icon: IconDashboard },
  { label: "Resumes", href: "/resumes", icon: IconFileText },
  { label: "Jobs", href: "/jobs", icon: IconBriefcase },
  { label: "Matches", href: "/matches", icon: IconSparkles },
  { label: "Settings", href: "/settings", icon: IconSettings },
];

export function MobileNav() {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();

  // Handle ESC key to close
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Prevent background scrolling when open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="inline-flex items-center justify-center rounded-lg p-2 text-slate-400 hover:bg-slate-900 hover:text-slate-100 focus-ring"
        aria-label="Open mobile navigation menu"
        aria-expanded={isOpen}
      >
        <IconMenu size={22} />
      </button>

      {isOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Mobile Navigation"
          className="fixed inset-0 z-50 flex"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-xs transition-opacity"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />

          {/* Drawer Menu */}
          <div className="relative flex w-full max-w-xs flex-1 flex-col bg-slate-950 border-r border-slate-800 p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-6 border-b border-slate-800/80">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white font-black text-sm">
                  RM
                </div>
                <div>
                  <span className="font-bold text-white text-base">ResumeMatch</span>
                  <p className="text-[10px] text-slate-500 font-mono">Explainable AI</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-900 hover:text-slate-200 focus-ring"
                aria-label="Close navigation menu"
              >
                <IconX size={20} />
              </button>
            </div>

            <nav className="mt-6 space-y-1.5 flex-1 overflow-y-auto" aria-label="Mobile Routes">
              {navItems.map((item) => {
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/dashboard" && pathname.startsWith(item.href));
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setIsOpen(false)}
                    className={`flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-sm font-medium transition-colors focus-ring ${
                      isActive
                        ? "bg-indigo-600/15 text-indigo-300 border border-indigo-500/25"
                        : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
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

            <div className="pt-6 border-t border-slate-800/80 mt-auto">
              <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-slate-300">FastAPI Backend</span>
                  <Badge variant="success" size="sm">
                    Online
                  </Badge>
                </div>
                <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mt-2">
                  <IconShieldCheck size={13} className="text-emerald-400" />
                  <span>Strict Zero-Fabrication</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
