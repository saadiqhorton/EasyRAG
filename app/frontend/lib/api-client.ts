/**
 * Typed API client for the RAG Knowledge Base backend.
 * All endpoints proxy through Next.js rewrites: /api/* -> http://localhost:8000/api/*
 */

import type {
  Collection,
  CollectionCreate,
  CollectionDetail,
  CollectionHealth,
  DocumentListItem,
  DocumentDetail,
  DocumentUploadResponse,
  IngestionJob,
  FailureEvent,
  SearchRequest,
  SearchResponse,
  AskRequest,
  AskResponse,
  AnswerDetail,
  ReindexRequest,
  ReindexResponse,
} from "./types";

const API_BASE = "/api";

class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  // Set JSON content-type for non-multipart requests
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text();
    }
    throw new ApiError(
      res.status,
      body,
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : undefined
    );
  }

  // Handle 204 No Content
  if (res.status === 204) {
    return undefined as T;
  }

  return res.json();
}

// ─── Collection CRUD ──────────────────────────────────────────────

export async function listCollections(
  skip = 0,
  limit = 20
): Promise<Collection[]> {
  return request<Collection[]>(
    `/collections?skip=${skip}&limit=${limit}`
  );
}

export async function getCollection(
  collectionId: string
): Promise<CollectionDetail> {
  return request<CollectionDetail>(`/collections/${collectionId}`);
}

export async function createCollection(
  data: CollectionCreate
): Promise<Collection> {
  return request<Collection>("/collections", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteCollection(
  collectionId: string
): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/collections/${collectionId}`, {
    method: "DELETE",
  });
}

// ─── Documents ────────────────────────────────────────────────────

export async function listDocuments(
  collectionId: string,
  skip = 0,
  limit = 50
): Promise<{ items: DocumentListItem[]; total: number; skip: number; limit: number }> {
  return request<{ items: DocumentListItem[]; total: number; skip: number; limit: number }>(
    `/collections/${collectionId}/documents?skip=${skip}&limit=${limit}`
  );
}

export async function uploadDocument(
  collectionId: string,
  file: File
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<DocumentUploadResponse>(
    `/collections/${collectionId}/documents`,
    {
      method: "POST",
      body: formData,
    }
  );
}

export async function getDocument(
  documentId: string
): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/documents/${documentId}`);
}

export async function replaceDocument(
  documentId: string,
  file: File
): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return request<DocumentUploadResponse>(
    `/documents/${documentId}/replace`,
    {
      method: "POST",
      body: formData,
    }
  );
}

export async function deleteDocument(
  documentId: string
): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/documents/${documentId}`, {
    method: "DELETE",
  });
}

// ─── Ingestion ────────────────────────────────────────────────────

export async function getIngestionJob(jobId: string): Promise<IngestionJob> {
  return request<IngestionJob>(`/ingestion-jobs/${jobId}`);
}

export async function listFailures(
  collectionId: string,
  skip = 0,
  limit = 50
): Promise<FailureEvent[]> {
  return request<FailureEvent[]>(
    `/collections/${collectionId}/failures?skip=${skip}&limit=${limit}`
  );
}

export async function reindexCollection(
  collectionId: string,
  data?: ReindexRequest
): Promise<ReindexResponse> {
  return request<ReindexResponse>(
    `/collections/${collectionId}/reindex`,
    {
      method: "POST",
      body: JSON.stringify(data ?? {}),
    }
  );
}

// ─── Search / Ask ─────────────────────────────────────────────────

export async function searchCollection(
  collectionId: string,
  data: SearchRequest
): Promise<SearchResponse> {
  return request<SearchResponse>(
    `/collections/${collectionId}/search`,
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export async function askCollection(
  collectionId: string,
  data: AskRequest
): Promise<AskResponse> {
  return request<AskResponse>(
    `/collections/${collectionId}/ask`,
    {
      method: "POST",
      body: JSON.stringify(data),
    }
  );
}

export async function getAnswer(answerId: string): Promise<AnswerDetail> {
  return request<AnswerDetail>(`/answers/${answerId}`);
}

// ─── Health ───────────────────────────────────────────────────────

export async function getCollectionHealth(
  collectionId: string
): Promise<CollectionHealth> {
  return request<CollectionHealth>(
    `/collections/${collectionId}/health`
  );
}

// ─── SWR fetcher ──────────────────────────────────────────────────

/** Generic SWR fetcher that uses the API client request function */
export const swrFetcher = <T>(url: string) => request<T>(url);

export { ApiError };