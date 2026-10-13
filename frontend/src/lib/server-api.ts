/**
 * ResumeMatch — Server-side API Helper
 * Used exclusively by Next.js Route Handlers and Server Components.
 */

export function getServerApiBaseUrl(): string {
  const url =
    process.env.INTERNAL_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://localhost:8000/api/v1";
  return url.replace(/\/$/, "");
}

export const AUTH_COOKIE_NAME = "rm_access_token";
export const REFRESH_COOKIE_NAME = "rm_refresh_token";

export function getCookieOptions(maxAgeSeconds: number = 3600) {
  const isProduction = process.env.NODE_ENV === "production";
  return {
    httpOnly: true,
    secure: isProduction,
    sameSite: "lax" as const,
    path: "/",
    maxAge: maxAgeSeconds,
  };
}
