import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { DocumentStatus, AnswerMode, IngestionJobStatus } from "./types";

/** Merge Tailwind classes with clsx */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format an ISO date string to a readable local date */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Format an ISO date string to a readable local date + time */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Format bytes to human-readable size */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  return `${value.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

/** Format milliseconds to human-readable duration */
export function formatLatency(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Human-readable label for document indexing status */
export function formatStatus(status: DocumentStatus): string {
  const labels: Record<DocumentStatus, string> = {
    pending: "Pending",
    indexing: "Indexing",
    indexed: "Indexed",
    failed: "Failed",
    superseded: "Superseded",
  };
  return labels[status] ?? status;
}

/** Human-readable label for ingestion job status */
export function formatJobStatus(status: IngestionJobStatus): string {
  const labels: Record<IngestionJobStatus, string> = {
    queued: "Queued",
    parsing: "Parsing",
    chunking: "Chunking",
    embedding: "Embedding",
    indexing: "Indexing",
    succeeded: "Succeeded",
    failed: "Failed",
  };
  return labels[status] ?? status;
}

/** Human-readable label for answer mode */
export function formatAnswerMode(mode: AnswerMode): string {
  const labels: Record<AnswerMode, string> = {
    answered_with_evidence: "Answered with evidence",
    partially_answered_with_caveat: "Partial answer (caveat)",
    insufficient_evidence: "Insufficient evidence",
  };
  return labels[mode] ?? mode;
}

/** Tailwind color classes for document status badges */
export function statusColor(status: DocumentStatus): string {
  const colors: Record<DocumentStatus, string> = {
    pending: "bg-gray-100 text-gray-700 border-gray-200",
    indexing: "bg-blue-50 text-blue-700 border-blue-200",
    indexed: "bg-green-50 text-green-700 border-green-200",
    failed: "bg-red-50 text-red-700 border-red-200",
    superseded: "bg-gray-50 text-gray-400 border-gray-200",
  };
  return colors[status] ?? "bg-gray-100 text-gray-700 border-gray-200";
}

/** Tailwind color classes for answer mode badges */
export function answerModeColor(mode: AnswerMode): string {
  const colors: Record<AnswerMode, string> = {
    answered_with_evidence: "bg-green-50 text-green-700 border-green-200",
    partially_answered_with_caveat:
      "bg-amber-50 text-amber-700 border-amber-200",
    insufficient_evidence: "bg-red-50 text-red-700 border-red-200",
  };
  return colors[mode] ?? "bg-gray-100 text-gray-700 border-gray-200";
}

/** Confidence value to human-readable label */
export function formatConfidence(confidence: number | null | undefined): string {
  if (confidence == null) return "—";
  return `${(confidence * 100).toFixed(0)}%`;
}

/** MIME type to short human label */
export function mimeTypeLabel(mime: string): string {
  const labels: Record<string, string> = {
    "text/markdown": "Markdown",
    "application/pdf": "PDF",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
      "DOCX",
    "text/plain": "TXT",
    "text/html": "HTML",
  };
  return labels[mime] ?? mime;
}

/** Truncate text to max length with ellipsis */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 1) + "…";
}