import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getServerApiBaseUrl, AUTH_COOKIE_NAME } from "@/lib/server-api";

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

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
    const { resume_id, job_id, job_text, job_title, save_result } = body;

    if (!resume_id || !UUID_REGEX.test(String(resume_id))) {
      return NextResponse.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "A valid resume_id UUID is required.",
          },
        },
        { status: 400 }
      );
    }

    if (!job_id && (!job_text || String(job_text).trim().length < 10)) {
      return NextResponse.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "Either a valid job_id UUID or job_text (at least 10 characters) must be supplied.",
          },
        },
        { status: 400 }
      );
    }

    if (job_id && !UUID_REGEX.test(String(job_id))) {
      return NextResponse.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "job_id must be a valid UUID format.",
          },
        },
        { status: 400 }
      );
    }

    const backendUrl = `${getServerApiBaseUrl()}/match`;
    const backendRes = await fetch(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        resume_id,
        job_id: job_id || undefined,
        job_text: job_text || undefined,
        job_title: job_title || undefined,
        save_result: save_result !== false,
      }),
    });

    const data = await backendRes.json();

    if (!backendRes.ok) {
      return NextResponse.json(data, { status: backendRes.status });
    }

    return NextResponse.json(data, { status: 200 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Error executing match evaluation";
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
