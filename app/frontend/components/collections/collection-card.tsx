import Link from "next/link";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Collection } from "@/lib/types";
import { cn, formatStatus, statusColor } from "@/lib/utils";
import { FileText, AlertTriangle, Database } from "lucide-react";

interface CollectionCardProps {
  collection: Collection;
}

export function CollectionCard({ collection }: CollectionCardProps) {
  const { index_status_summary } = collection;
  const hasFailures = index_status_summary.failed > 0;
  const hasPending =
    index_status_summary.pending > 0 || index_status_summary.indexing > 0;

  return (
    <Link href={`/collections/${collection.id}`}>
      <Card className="hover:border-ring transition-colors cursor-pointer">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <CardTitle className="text-base">{collection.name}</CardTitle>
            {hasFailures && (
              <Badge
                variant="destructive"
                className="gap-1"
              >
                <AlertTriangle className="h-3 w-3" />
                {index_status_summary.failed} failed
              </Badge>
            )}
          </div>
          {collection.description && (
            <CardDescription className="line-clamp-2">
              {collection.description}
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <Database className="h-3.5 w-3.5" />
              {collection.document_count}{" "}
              {collection.document_count === 1 ? "doc" : "docs"}
            </span>
            <span className="flex items-center gap-1">
              <FileText className="h-3.5 w-3.5" />
              {index_status_summary.indexed} indexed
            </span>
          </div>

          {/* Status summary row */}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {hasPending && (
              <span
                className={cn(
                  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
                  statusColor("indexing")
                )}
              >
                {index_status_summary.indexing > 0
                  ? `${index_status_summary.indexing} indexing`
                  : `${index_status_summary.pending} pending`}
              </span>
            )}
            {index_status_summary.failed > 0 && (
              <span
                className={cn(
                  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
                  statusColor("failed")
                )}
              >
                {index_status_summary.failed} failed
              </span>
            )}
            {index_status_summary.superseded > 0 && (
              <span
                className={cn(
                  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
                  statusColor("superseded")
                )}
              >
                {index_status_summary.superseded} superseded
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}