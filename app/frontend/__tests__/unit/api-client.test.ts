import { describe, it, expect, vi, beforeEach } from "vitest";
import { ApiError } from "@/lib/api-client";

describe("ApiError", () => {
  it("should create an error with status and body", () => {
    const error = new ApiError(404, { detail: "Not found" });
    expect(error.status).toBe(404);
    expect(error.body).toEqual({ detail: "Not found" });
    expect(error.message).toBe("API error 404");
    expect(error.name).toBe("ApiError");
  });

  it("should use custom message when provided", () => {
    const error = new ApiError(400, {}, "Bad request");
    expect(error.message).toBe("Bad request");
  });

  it("should be an instance of Error", () => {
    const error = new ApiError(500, null);
    expect(error).toBeInstanceOf(Error);
  });
});

describe("API client request function", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("should handle 204 No Content", async () => {
    const mockResponse = new Response(null, { status: 204 });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(mockResponse);

    const { swrFetcher } = await import("@/lib/api-client");
    const result = await swrFetcher("/api/test");
    expect(result).toBeUndefined();
  });

  it("should throw ApiError on non-2xx response", async () => {
    const errorBody = { detail: "Not found" };
    const mockResponse = new Response(JSON.stringify(errorBody), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(mockResponse);

    const { listCollections } = await import("@/lib/api-client");
    await expect(listCollections()).rejects.toThrow();
  });

  it("should set JSON content-type for non-multipart requests", async () => {
    let capturedInit: RequestInit | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementationOnce(
      async (_url: string, init?: RequestInit) => {
        capturedInit = init;
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
    );

    const { createCollection } = await import("@/lib/api-client");
    try {
      await createCollection({ name: "Test" });
    } catch {
      // May fail due to response parsing, but we just want to check the init
    }

    const headers = capturedInit?.headers as Record<string, string>;
    expect(headers?.["Content-Type"]).toBe("application/json");
  });
});