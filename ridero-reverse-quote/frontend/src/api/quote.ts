import type { ReverseQuoteRequest, ReverseQuoteResponse } from "../types/quote";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ValidationErrorItem {
  msg?: string;
  loc?: (string | number)[];
}

function describeError(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = (detail as ValidationErrorItem[]).map((item) => {
      // Pydantic prefixes custom errors with "Value error, ".
      const msg = (item.msg ?? "Invalid value").replace(/^Value error, /, "");
      const field = item.loc?.filter((part) => part !== "body").join(".");
      return field ? `${field}: ${msg}` : msg;
    });
    if (messages.length > 0) return messages.join("\n");
  }
  return `Request failed with status ${status}`;
}

export async function requestReverseQuote(
  request: ReverseQuoteRequest,
  signal?: AbortSignal,
): Promise<ReverseQuoteResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}/quote/reverse`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(`Could not reach the quote API at ${API_URL}. Is the backend running?`);
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(describeError(body, response.status), response.status);
  }
  return body as ReverseQuoteResponse;
}
