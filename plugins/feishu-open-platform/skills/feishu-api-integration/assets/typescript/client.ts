export interface HttpClient {
  request<T>(options: {
    method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
    url: string;
    headers?: Record<string, string>;
    query?: Record<string, string | number | boolean | undefined>;
    body?: unknown;
    signal?: AbortSignal;
  }): Promise<{ status: number; data: T }>;
}

export class FeishuApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "FeishuApiError";
  }
}

export async function callFeishu<T>(
  client: HttpClient,
  accessToken: string,
  options: Parameters<HttpClient["request"]>[0],
): Promise<T> {
  const response = await client.request<T>({
    ...options,
    headers: {
      ...options.headers,
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (response.status < 200 || response.status >= 300) {
    throw new FeishuApiError(
      `Feishu API request failed with status ${response.status}`,
      response.status,
    );
  }

  return response.data;
}
