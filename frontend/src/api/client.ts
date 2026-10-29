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
    : "Chưa thể kết nối. Bạn hãy thử lại.";
}

/** Same-origin BFF transport. Auth credentials are never kept in browser storage. */
export class ApiClient {
  private csrf = "";
  private intents = new Map<string, string>();
  // Every in-flight request of the current lifecycle; reset() aborts them so a late response
  // can never restore private UI after the session or trial ended.
  private controllers = new Set<AbortController>();
  /** Bumped by reset(); callbacks capture it and drop results from an older lifecycle. */
  epoch = 0;
  onUnauthorized?: (error?: ApiError) => void;

  setCsrf(token: string) {
    this.csrf = token;
  }
  reset() {
    this.csrf = "";
    this.intents.clear();
    this.epoch += 1;
    for (const controller of this.controllers) controller.abort();
    this.controllers.clear();
  }

  async request<T>(
    path: string,
    options: {
      method?: string;
      body?: unknown;
      signal?: AbortSignal;
      publicWrite?: boolean;
      /** Stable key for a public write; kept across ambiguous retries instead of a fresh one. */
      idempotencyKey?: string;
      /** Marks the guest-intent/creation requests the backend requires a custom header for. */
      guestIntent?: boolean;
    } = {},
  ): Promise<T> {
    const method = options.method || "GET";
    const writing = method !== "GET";
    const encoded =
      options.body === undefined ? undefined : JSON.stringify(options.body);
    const intent = `${method} ${path} ${encoded || ""}`;
    const headers: Record<string, string> = { Accept: "application/json" };
    if (encoded !== undefined) headers["Content-Type"] = "application/json";
    if (options.guestIntent) headers["X-Guest-Intent"] = "1";
    if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
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
            "Một số thao tác chưa được xác nhận. Tải lại dữ liệu để kiểm tra trước khi tiếp tục.",
          );
        key = crypto.randomUUID();
        this.intents.set(intent, key);
      }
      headers["Idempotency-Key"] = key;
    }
    const controller = new AbortController();
    this.controllers.add(controller);
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
        // A 4xx means the server rolled the write back, so the key can never be
        // replayed usefully; only 5xx/network outcomes are ambiguous and keep it.
        if (response.status < 500) this.intents.delete(intent);
        const failure = new ApiError(
          response.status,
          typeof detail.code === "string" ? detail.code : "API_ERROR",
          // Without a server explanation the cause is unknown: never blame the input.
          typeof detail.message === "string"
            ? detail.message
            : "Chưa hoàn tất yêu cầu. Bạn hãy thử lại.",
          response.headers.get("Retry-After"),
        );
        // Step-up re-authentication and public auth endpoints are not session loss; an expired
        // guest trial (GUEST_EXPIRED) is session loss even on /session.
        if (
          response.status === 401 &&
          ((path !== "/session" &&
            !path.startsWith("/auth/") &&
            detail.code !== "REAUTH_REQUIRED") ||
            detail.code === "GUEST_EXPIRED")
        )
          this.onUnauthorized?.(failure);
        throw failure;
      }
      const result =
        response.status === 204 ? undefined : await response.json();
      this.intents.delete(intent);
      return result as T;
    } finally {
      clearTimeout(timeout);
      this.controllers.delete(controller);
      options.signal?.removeEventListener("abort", abort);
    }
  }
}
