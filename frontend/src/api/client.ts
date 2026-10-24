export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public retryAfter: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : {};
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Chưa thể kết nối dịch vụ. Nội dung bạn nhập vẫn được giữ lại. Vui lòng thử lại.";
}

/** Same-origin BFF transport. Auth credentials are never kept in browser storage. */
export class ApiClient {
  private csrf = "";
  private intents = new Map<string, string>();
  onUnauthorized?: () => void;

  setCsrf(token: string) {
    this.csrf = token;
  }
  reset() {
    this.csrf = "";
    this.intents.clear();
  }

  async request<T>(
    path: string,
    options: {
      method?: string;
      body?: unknown;
      signal?: AbortSignal;
      publicWrite?: boolean;
    } = {},
  ): Promise<T> {
    const method = options.method || "GET";
    const writing = method !== "GET";
    const encoded =
      options.body === undefined ? undefined : JSON.stringify(options.body);
    const intent = `${method} ${path} ${encoded || ""}`;
    const headers: Record<string, string> = { Accept: "application/json" };
    if (encoded !== undefined) headers["Content-Type"] = "application/json";
    if (writing && !options.publicWrite) {
      if (!this.csrf)
        throw new ApiError(
          401,
          "SESSION_REQUIRED",
          "Phiên đã hết hạn. Vui lòng đăng nhập lại.",
        );
      headers["X-CSRF-Token"] = this.csrf;
      let key = this.intents.get(intent);
      if (!key) {
        if (this.intents.size >= 50)
          throw new ApiError(
            409,
            "PENDING_WRITES",
            "Còn thao tác chưa xác nhận. Vui lòng tải lại dữ liệu trước khi tiếp tục.",
          );
        key = crypto.randomUUID();
        this.intents.set(intent, key);
      }
      headers["Idempotency-Key"] = key;
    }
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (options.signal?.aborted) controller.abort();
    options.signal?.addEventListener("abort", abort, { once: true });
    const timeout = setTimeout(abort, 20_000);
    try {
      const response = await fetch(`/api/v1${path}`, {
        method,
        body: encoded,
        headers,
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error",
        signal: controller.signal,
      });
      if (!response.ok) {
        const payload = record(await response.json().catch(() => ({})));
        const detail = record(payload.error || payload.detail);
        if (
          response.status === 401 &&
          path !== "/session" &&
          path !== "/auth/login"
        )
          this.onUnauthorized?.();
        throw new ApiError(
          response.status,
          typeof detail.code === "string" ? detail.code : "API_ERROR",
          typeof detail.message === "string"
            ? detail.message
            : "Chưa hoàn tất thao tác. Vui lòng kiểm tra nội dung và thử lại.",
          response.headers.get("Retry-After"),
        );
      }
      const result =
        response.status === 204 ? undefined : await response.json();
      this.intents.delete(intent);
      return result as T;
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener("abort", abort);
    }
  }
}
