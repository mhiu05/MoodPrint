export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
    public requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export interface ClientOptions {
  baseUrl: string;
  getIdentity?(): string | null;
  getToken(): Promise<string | null>;
  refreshToken(): Promise<string | null>;
  onUnauthenticated(): void;
  fetch?: typeof globalThis.fetch;
}
export type ApiClient = <T = unknown>(
  path: string,
  init?: RequestInit,
) => Promise<T>;
export type StreamClient = ApiClient & {
  stream(path: string, init?: RequestInit): Promise<Response>;
};
export function createApiClient(options: ClientOptions): StreamClient {
  let refreshing: Promise<string | null> | undefined;
  const stream = async (
    path: string,
    init: RequestInit = {},
  ): Promise<Response> => {
    const identity = options.getIdentity?.();
    const checkIdentity = () => {
      if (options.getIdentity && options.getIdentity() !== identity)
        throw new ApiError(
          401,
          "session_changed",
          "Phiên làm việc đã thay đổi. Hãy mở lại nội dung trong tài khoản hiện tại.",
        );
    };
    if (
      !path.startsWith("/v1/") ||
      path.startsWith("//") ||
      /[\\\r\n]/.test(path)
    )
      throw new Error("Đường dẫn API không hợp lệ.");
    const request = async (token: string | null) => {
      init.signal?.throwIfAborted();
      checkIdentity();
      const headers = new Headers(init.headers);
      if (token) headers.set("Authorization", `Bearer ${token}`);
      if (init.body != null) headers.set("Content-Type", "application/json");
      return (options.fetch ?? globalThis.fetch)(
        `${options.baseUrl.replace(/\/$/, "")}${path}`,
        { ...init, headers, credentials: "omit", cache: "no-store" },
      );
    };
    let response: Response;
    try {
      response = await request(await options.getToken());
      init.signal?.throwIfAborted();
      if (response.status === 401) {
        checkIdentity();
        refreshing ??= options
          .refreshToken()
          .catch(() => null)
          .finally(() => {
            refreshing = undefined;
          });
        const token = await refreshing;
        init.signal?.throwIfAborted();
        if (token) response = await request(token);
      }
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (init.signal?.aborted) throw init.signal.reason;
      if (error instanceof DOMException && error.name === "AbortError")
        throw error;
      throw new ApiError(
        0,
        "network_error",
        "Không thể kết nối. Nội dung nhập vẫn được giữ; hãy thử lại.",
      );
    }
    init.signal?.throwIfAborted();
    checkIdentity();
    if (response.status === 401) options.onUnauthenticated();
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      init.signal?.throwIfAborted();
      checkIdentity();
      const error = payload?.error;
      throw new ApiError(
        response.status,
        error?.code ?? "upstream_error",
        error?.message ?? "Chưa thể hoàn tất. Hãy thử lại.",
        error?.details ?? {},
        error?.requestId ?? response.headers.get("X-Request-ID") ?? undefined,
      );
    }
    return response;
  };
  const api: ApiClient = async <T>(path: string, init?: RequestInit) => {
    const response = await stream(path, init);
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  };
  return Object.assign(api, { stream });
}

export async function readAllPages<T>(
  api: ApiClient,
  path: string,
): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  const visited = new Set<string>();
  do {
    const page: { items: T[]; nextCursor: string | null } = await api(
      `${path}${path.includes("?") ? "&" : "?"}limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    );
    items.push(...page.items);
    cursor = page.nextCursor;
    if (cursor && visited.has(cursor))
      throw new Error("Phản hồi phân trang không hợp lệ.");
    if (cursor) visited.add(cursor);
  } while (cursor);
  return items;
}
