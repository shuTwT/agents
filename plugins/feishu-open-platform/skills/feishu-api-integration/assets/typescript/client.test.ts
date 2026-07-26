import { describe, expect, it, vi } from "vitest";
import { callFeishu, FeishuApiError, type HttpClient } from "./client";

describe("callFeishu", () => {
  it("adds the bearer token and returns successful data", async () => {
    const request = vi.fn().mockResolvedValue({ status: 200, data: { ok: true } });
    const client: HttpClient = { request };

    await expect(
      callFeishu(client, "test-token", { method: "GET", url: "/open-apis/example" }),
    ).resolves.toEqual({ ok: true });

    expect(request).toHaveBeenCalledWith({
      method: "GET",
      url: "/open-apis/example",
      headers: { Authorization: "Bearer test-token" },
    });
  });

  it("raises a typed error for non-success responses", async () => {
    const client: HttpClient = {
      request: vi.fn().mockResolvedValue({ status: 403, data: {} }),
    };

    await expect(
      callFeishu(client, "test-token", { method: "GET", url: "/open-apis/example" }),
    ).rejects.toBeInstanceOf(FeishuApiError);
  });
});
