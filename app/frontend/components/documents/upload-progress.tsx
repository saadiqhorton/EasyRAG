"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { getIngestionJob } from "@/lib/api-client";
import type { DocumentUploadResponse, IngestionJob } from "@/lib/types";
import { formatJobStatus } from "@/lib/utils";
import {
  CheckCircle2,
  Loader2,
  AlertCircle,
  FileText,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface UploadItem {
  file: File;
  uploadResponse?: DocumentUploadResponse;
  error?: string;
}

interface UploadProgressProps {
  uploads: UploadItem[];
  onRemove: (index: number) => void;
}

/** Format elapsed seconds into human-readable duration */
function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

/** Map job status to a progress stage label and percentage */
function jobToProgress(job: IngestionJob): {
  stage: string;
  percent: number;
  isComplete: boolean;
  isFailed: boolean;
  chunkText: string | null;
  elapsedText: string | null;
} {
  // Use real progress from backend if available, otherwise fall back to stage-based estimation
  const percent =
    job.progress_percent !== null && job.progress_percent !== undefined
      ? job.progress_percent
      : estimatePercentFromStatus(job.status);

  const chunkText =
    job.chunks_processed !== null &&
    job.chunks_total !== null &&
    job.chunks_total > 0
      ? `${job.chunks_processed} / ${job.chunks_total} chunks`
      : null;

  const elapsedText =
    job.elapsed_seconds !== null && job.elapsed_seconds !== undefined
      ? formatElapsed(job.elapsed_seconds)
      : null;

  switch (job.status) {
    case "succeeded":
      return {
        stage: "Complete",
        percent: 100,
        isComplete: true,
        isFailed: false,
        chunkText,
        elapsedText,
      };
    case "failed":
      return {
        stage: job.failures?.[0]?.stage_name ?? "Failed",
        percent: 0,
        isComplete: true,
        isFailed: true,
        chunkText,
        elapsedText,
      };
    default:
      return {
        stage: capitalizeFirst(job.status),
        percent,
        isComplete: false,
        isFailed: false,
        chunkText,
        elapsedText,
      };
  }
}

/** Estimate progress percentage based on job status (fallback) */
function estimatePercentFromStatus(status: IngestionJob["status"]): number {
  switch (status) {
    case "queued":
      return 5;
    case "parsing":
      return 20;
    case "chunking":
      return 40;
    case "embedding":
      return 70;
    case "indexing":
      return 90;
    default:
      return 0;
  }
}

/** Capitalize first letter of a string */
function capitalizeFirst(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function UploadItemRow({
  item,
  index,
  onRemove,
}: {
  item: UploadItem;
  index: number;
  onRemove: (index: number) => void;
}) {
  const jobId = item.uploadResponse?.job_id;
  const { data: job } = useSWR(
    jobId ? `/ingestion-jobs/${jobId}` : null,
    () => (jobId ? getIngestionJob(jobId) : null),
    {
      refreshInterval: (data) => {
        if (!data) return 2000;
        if (data.status === "succeeded" || data.status === "failed") return 0;
        return 2000;
      },
    }
  );

  const progress = job ? jobToProgress(job) : null;
  const failureMessage =
    job?.status === "failed" && job.failures.length > 0
      ? job.failures[0].message
      : null;

  return (
    <div className="flex items-center gap-3 rounded-md border p-3">
      <FileText className="h-4 w-4 text-muted-foreground shrink-0" />

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{item.file.name}</p>

        {item.error && (
          <p className="text-xs text-destructive mt-0.5">{item.error}</p>
        )}

        {progress && (
          <>
            <div className="flex items-center gap-2 mt-1">
              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500",
                    progress.isFailed
                      ? "bg-destructive"
                      : progress.isComplete
                        ? "bg-green-500"
                        : "bg-primary"
                  )}
                  style={{ width: `${progress.percent}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground shrink-0">
                {progress.isFailed ? "Failed" : `${progress.percent}%`}
              </span>
            </div>

            {/* Progress details: stage, chunks, elapsed time */}
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-muted-foreground">
                {progress.stage}
              </span>
              {progress.chunkText && (
                <>
                  <span className="text-xs text-muted-foreground">•</span>
                  <span className="text-xs text-muted-foreground">
                    {progress.chunkText}
                  </span>
                </>
              )}
              {progress.elapsedText && (
                <>
                  <span className="text-xs text-muted-foreground">•</span>
                  <span className="text-xs text-muted-foreground">
                    {progress.elapsedText}
                  </span>
                </>
              )}
            </div>

            {failureMessage && (
              <p className="text-xs text-destructive mt-1">{failureMessage}</p>
            )}
          </>
        )}

        {!progress && !item.error && (
          <p className="text-xs text-muted-foreground mt-0.5">Uploading...</p>
        )}
      </div>

      <button
        onClick={() => onRemove(index)}
        className="shrink-0 text-muted-foreground hover:text-foreground"
        aria-label={`Remove ${item.file.name}`}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function UploadProgress({
  uploads,
  onRemove,
}: UploadProgressProps) {
  if (uploads.length === 0) return null;

  return (
    <div className="space-y-2">
      {uploads.map((item, index) => (
        <UploadItemRow
          key={`${item.file.name}-${index}`}
          item={item}
          index={index}
          onRemove={onRemove}
        />
      ))}
    </div>
  );
}