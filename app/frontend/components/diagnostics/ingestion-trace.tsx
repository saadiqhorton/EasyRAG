import type { IngestionJob } from "@/lib/types";
import { formatJobStatus, formatDateTime } from "@/lib/utils";
import {
  CheckCircle2,
  Loader2,
  AlertCircle,
  Circle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface IngestionTraceProps {
  job: IngestionJob;
}

const STAGES = ["queued", "parsing", "chunking", "embedding", "indexing", "succeeded"] as const;

function stageIcon(stage: string, jobStatus: string, currentStage: string | null) {
  const stageIdx = STAGES.indexOf(stage as typeof STAGES[number]);
  const currentIdx = currentStage ? STAGES.indexOf(currentStage as typeof STAGES[number]) : -1;

  if (jobStatus === "succeeded") {
    return <CheckCircle2 className="h-5 w-5 text-green-500" />;
  }
  if (jobStatus === "failed" && stageIdx >= currentIdx) {
    if (stage === currentStage) {
      return <AlertCircle className="h-5 w-5 text-destructive" />;
    }
    return <Circle className="h-5 w-5 text-muted-foreground/30" />;
  }
  if (stage === currentStage) {
    return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
  }
  if (stageIdx < (currentIdx >= 0 ? currentIdx : 0)) {
    return <CheckCircle2 className="h-5 w-5 text-green-500" />;
  }
  return <Circle className="h-5 w-5 text-muted-foreground/30" />;
}

export function IngestionTrace({ job }: IngestionTraceProps) {
  const currentStage = job.current_stage ?? job.status;

  return (
    <div className="space-y-3" role="list" aria-label="Ingestion trace">
      <div className="text-sm font-medium">
        Job {job.id.slice(0, 8)}... — {formatJobStatus(job.status)}
      </div>

      <ol className="flex items-center gap-0">
        {STAGES.map((stage, idx) => (
          <li
            key={stage}
            className="flex items-center"
            role="listitem"
            aria-current={stage === currentStage ? "step" : undefined}
          >
            <div className="flex flex-col items-center">
              {stageIcon(stage, job.status, currentStage)}
              <span
                className={cn(
                  "text-[10px] mt-1 capitalize",
                  stage === currentStage
                    ? "font-semibold text-foreground"
                    : "text-muted-foreground"
                )}
              >
                {stage}
              </span>
            </div>
            {idx < STAGES.length - 1 && (
              <div
                className={cn(
                  "h-0.5 w-8 mx-1",
                  STAGES.indexOf(currentStage as typeof STAGES[number]) > idx ||
                    job.status === "succeeded"
                    ? "bg-green-300"
                    : "bg-border"
                )}
              />
            )}
          </li>
        ))}
      </ol>

      {job.started_at && (
        <div className="text-xs text-muted-foreground">
          Started: {formatDateTime(job.started_at)}
          {job.completed_at && (
            <> — Completed: {formatDateTime(job.completed_at)}</>
          )}
        </div>
      )}

      {job.failures.length > 0 && (
        <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <p className="font-medium">
            {job.failures.length}{" "}
            {job.failures.length === 1 ? "failure" : "failures"} recorded
          </p>
          <p className="mt-1 text-xs">{job.failures[0].message}</p>
        </div>
      )}
    </div>
  );
}