import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  getServerApiBaseUrl,
  AUTH_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
} from "@/lib/server-api";

export async function GET() {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;

    if (!token) {
      return NextResponse.json(
        {
          authenticated: false,
          user: null,
          message: "No active authentication token.",
        },
        { status: 401 }
      );
    }

    const backendRes = await fetch(`${getServerApiBaseUrl()}/auth/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!backendRes.ok) {
      // Clear invalid/expired cookie
      cookieStore.delete(AUTH_COOKIE_NAME);
      cookieStore.delete(REFRESH_COOKIE_NAME);
      return NextResponse.json(
        {
          authenticated: false,
          user: null,
          message: "Session expired or invalid.",
        },
        { status: 401 }
      );
    }

    const user = await backendRes.json();
    return NextResponse.json({
      authenticated: true,
      user,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal session check error";
    return NextResponse.json(
      {
        authenticated: false,
        user: null,
        error: message,
      },
      { status: 500 }
    );
  }
}
