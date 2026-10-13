/**
 * ResumeMatch — Typed API Client Foundation
 * Provides typed HTTP requests with centralized error parsing and config.
 */

import { ApiErrorEnvelope } from "./types";

export class ApiError extends Error {
  public code: string;
  public details?: { field?: string; issue: string }[];
  public status: number;
  public requestId?: string;

  constructor(status: number, envelope: ApiErrorEnvelope) {
    super(envelope.error?.message || "An unexpected API error occurred");
    this.name = "ApiError";
    this.status = status;
    this.code = envelope.error?.code || "UNKNOWN_ERROR";
    this.details = envelope.error?.details;
    this.requestId = envelope.request_id;
  }
}

export function getApiBaseUrl(): string {
  // Configurable base URL with sensible development default
  return process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
}

export interface RequestOptions extends RequestInit {
  token?: string;
  params?: Record<string, string | number | boolean | undefined>;
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;

  let url = `${baseUrl}${cleanEndpoint}`;

  if (options.params) {
    const searchParams = new URLSearchParams();
    for (const [key, val] of Object.entries(options.params)) {
      if (val !== undefined) {
        searchParams.append(key, String(val));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorEnvelope: ApiErrorEnvelope;
    try {
      errorEnvelope = await response.json();
    } catch {
      errorEnvelope = {
        error: {
          code: `HTTP_${response.status}`,
          message: response.statusText || `Request failed with status ${response.status}`,
        },
      };
    }
    throw new ApiError(response.status, errorEnvelope);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}
