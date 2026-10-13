import { NextRequest, NextResponse } from "next/server";
import { AUTH_COOKIE_NAME } from "./lib/server-api";
import { sanitizeReturnUrl } from "./lib/auth-utils";

const protectedRoutes = ["/dashboard", "/resumes", "/jobs", "/matches", "/settings"];
const authRoutes = ["/login", "/register"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;

  const isProtected = protectedRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );
  const isAuthRoute = authRoutes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  );

  // 1. Unauthenticated access to protected portal routes
  if (isProtected && !token) {
    const returnUrl = sanitizeReturnUrl(
      `${pathname}${request.nextUrl.search}`,
      "/dashboard"
    );
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", returnUrl);
    return NextResponse.redirect(loginUrl);
  }

  // 2. Already authenticated user accessing /login or /register
  if (isAuthRoute && token) {
    const fromParam = request.nextUrl.searchParams.get("from");
    const targetUrl = sanitizeReturnUrl(fromParam, "/dashboard");
    return NextResponse.redirect(new URL(targetUrl, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/resumes/:path*",
    "/jobs/:path*",
    "/matches/:path*",
    "/settings/:path*",
    "/login",
    "/register",
  ],
};
