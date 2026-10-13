import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getServerApiBaseUrl, AUTH_COOKIE_NAME } from "@/lib/server-api";

export async function POST(request: NextRequest) {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get(AUTH_COOKIE_NAME)?.value;

    if (!token) {
      return NextResponse.json(
        {
          error: {
            code: "UNAUTHORIZED",
            message: "Authentication token missing or session expired.",
          },
        },
        { status: 401 }
      );
    }

    const body = await request.json();
    const { title, company, raw_text } = body;

    if (!title || typeof title !== "string" || !title.trim()) {
      return NextResponse.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "Job title is required and cannot be empty.",
          },
        },
        { status: 400 }
      );
    }

    if (!raw_text || typeof raw_text !== "string" || raw_text.trim().length < 10) {
      return NextResponse.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "Job description text must be at least 10 characters long.",
          },
        },
        { status: 400 }
      );
    }

    const backendUrl = `${getServerApiBaseUrl()}/jobs/analyze`;
    const backendRes = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        title: title.trim(),
        company: company ? String(company).trim() : undefined,
        raw_text: raw_text.trim(),
      }),
    });

    const data = await backendRes.json();

    if (!backendRes.ok) {
      return NextResponse.json(data, { status: backendRes.status });
    }

    return NextResponse.json(data, { status: 201 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Error proxying job analysis";
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
