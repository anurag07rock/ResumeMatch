"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { AppShell } from "../../components/layout/app-shell";
import { useAuth } from "../../lib/auth-context";
import { LoadingSpinner } from "../../components/ui/loading-spinner";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    }
  }, [isLoading, isAuthenticated, router, pathname]);

  return (
    <AppShell>
      {isLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm">
          <LoadingSpinner size="lg" label="Verifying authenticated session..." />
        </div>
      )}
      {children}
    </AppShell>
  );
}
