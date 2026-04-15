import { listFailures, reindexCollection } from "@/lib/api-client";
import { FailureList } from "@/components/diagnostics/failure-list";
import { Button } from "@/components/ui/button";
import { RotateCcw, AlertTriangle } from "lucide-react";
import type { FailureEvent } from "@/lib/types";

export default async function DiagnosticsPage({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = await params;

  let failures: FailureEvent[] = [];
  let error: string | null = null;

  try {
    failures = await listFailures(collectionId);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load failures.";
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Diagnostics</h2>
        <form
          action={async () => {
            "use server";
            await reindexCollection(collectionId);
          }}
        >
          <Button type="submit" variant="outline" size="sm" className="gap-1.5">
            <RotateCcw className="h-3.5 w-3.5" />
            Reindex Failed
          </Button>
        </form>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {!error && (
        <>
          <div>
            <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Failure Events
            </h3>
            <FailureList failures={failures} />
          </div>
        </>
      )}
    </div>
  );
}