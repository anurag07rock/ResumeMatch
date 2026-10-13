import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  getServerApiBaseUrl,
  AUTH_COOKIE_NAME,
  REFRESH_COOKIE_NAME,
  getCookieOptions,
} from "@/lib/server-api";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (!email || !password) {
      return NextResponse.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "Email and password are required.",
          },
        },
        { status: 400 }
      );
    }

    const backendUrl = `${getServerApiBaseUrl()}/auth/login`;
    const backendRes = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await backendRes.json();

    if (!backendRes.ok) {
      return NextResponse.json(data, { status: backendRes.status });
    }

    const { access_token, refresh_token, expires_in } = data;

    // Fetch user profile from /auth/me using the newly issued access token
    const meRes = await fetch(`${getServerApiBaseUrl()}/auth/me`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${access_token}`,
      },
    });

    let user = null;
    if (meRes.ok) {
      user = await meRes.json();
    }

    // Securely set HttpOnly cookies on the response
    const cookieStore = await cookies();
    cookieStore.set(AUTH_COOKIE_NAME, access_token, getCookieOptions(expires_in || 3600));

    if (refresh_token) {
      // 7 days refresh cookie
      cookieStore.set(REFRESH_COOKIE_NAME, refresh_token, getCookieOptions(7 * 24 * 3600));
    }

    // Return success without exposing the tokens in the response JSON
    return NextResponse.json({
      success: true,
      user,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal login proxy error";
    return NextResponse.json(
      {
        error: {
          code: "SERVER_ERROR",
          message,
        },
      },
      { status: 500 }
    );
  }
}
