const DEFAULT_BASE_URL = "http://localhost:8000";
const API_TIMEOUT_MS = 10000;

export class ApiError extends Error {
  status: number;
  payload?: unknown;

  constructor(message: string, status = 500, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_BASE_URL;
  return raw.replace(/\/+$/, "");
}

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  // 浏览器端优先使用 Next.js 本地代理，避免额外 CORS 配置
  if (typeof window !== "undefined") {
    return `/api${normalizedPath}`;
  }
  return `${getApiBaseUrl()}${normalizedPath}`;
}

async function parseJsonSafe(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    throw new ApiError(`接口返回非 JSON 响应：${response.url}`, response.status, text);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    const response = await fetch(buildUrl(path), {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {}),
      },
      signal: controller.signal,
    });

    const payload = await parseJsonSafe(response);

    if (!response.ok) {
      const message =
        typeof payload === "object" && payload && "error" in payload
          ? String((payload as Record<string, unknown>).error)
          : `接口请求失败：${response.status}`;
      throw new ApiError(message, response.status, payload);
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    if (error instanceof Error && error.name === "AbortError") {
      throw new ApiError(`接口请求超时：${path}`, 408);
    }
    throw new ApiError(`接口请求异常：${path}`, 500, error);
  } finally {
    clearTimeout(timeoutId);
  }
}
