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

/** Map job status to a progress stage label and percentage */
function jobToProgress(job: IngestionJob): {
  stage: string;
  percent: number;
  isComplete: boolean;
  isFailed: boolean;
} {
  switch (job.status) {
    case "queued":
      return { stage: "Queued", percent: 10, isComplete: false, isFailed: false };
    case "parsing":
      return { stage: "Parsing", percent: 30, isComplete: false, isFailed: false };
    case "chunking":
      return { stage: "Chunking", percent: 50, isComplete: false, isFailed: false };
    case "embedding":
      return { stage: "Embedding", percent: 70, isComplete: false, isFailed: false };
    case "indexing":
      return { stage: "Indexing", percent: 90, isComplete: false, isFailed: false };
    case "succeeded":
      return { stage: "Complete", percent: 100, isComplete: true, isFailed: false };
    case "failed":
      return {
        stage: job.failure_events?.[0]?.stage_name ?? "Failed",
        percent: 0,
        isComplete: true,
        isFailed: true,
      };
    default:
      return { stage: "Unknown", percent: 0, isComplete: false, isFailed: false };
  }
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
                {progress.isFailed ? "Failed" : progress.stage}
              </span>
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