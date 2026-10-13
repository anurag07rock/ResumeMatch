import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getServerApiBaseUrl, AUTH_COOKIE_NAME } from "@/lib/server-api";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

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

    const formData = await request.formData();
    const file = formData.get("file");

    if (!file || typeof file === "string") {
      return NextResponse.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "No file was provided in the upload request.",
          },
        },
        { status: 400 }
      );
    }

    const blob = file as File;

    if (!blob.name || !blob.name.toLowerCase().endsWith(".pdf")) {
      return NextResponse.json(
        {
          error: {
            code: "INVALID_FILE_TYPE",
            message: "Only PDF files (.pdf) are supported.",
          },
        },
        { status: 400 }
      );
    }

    if (blob.size === 0) {
      return NextResponse.json(
        {
          error: {
            code: "EMPTY_FILE",
            message: "The uploaded file is empty (0 bytes).",
          },
        },
        { status: 400 }
      );
    }

    if (blob.size > MAX_FILE_SIZE_BYTES) {
      return NextResponse.json(
        {
          error: {
            code: "PAYLOAD_TOO_LARGE",
            message: `File exceeds maximum allowed size of 5 MB (${MAX_FILE_SIZE_BYTES} bytes).`,
          },
        },
        { status: 413 }
      );
    }

    // Prepare multipart form data payload for FastAPI backend
    const backendFormData = new FormData();
    backendFormData.append("file", blob, blob.name);

    const backendUrl = `${getServerApiBaseUrl()}/resumes/upload`;
    const backendRes = await fetch(backendUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: backendFormData,
    });

    const data = await backendRes.json();

    if (!backendRes.ok) {
      return NextResponse.json(data, { status: backendRes.status });
    }

    return NextResponse.json(data, { status: 201 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Error proxying resume upload";
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
