import type { FailureEvent } from "@/lib/types";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/utils";
import { RotateCcw, AlertCircle, AlertTriangle } from "lucide-react";

interface FailureListProps {
  failures: FailureEvent[];
  onRetry?: (failure: FailureEvent) => void;
}

const stageColor: Record<string, string> = {
  parsing: "bg-orange-50 text-orange-700 border-orange-200",
  chunking: "bg-yellow-50 text-yellow-700 border-yellow-200",
  embedding: "bg-blue-50 text-blue-700 border-blue-200",
  indexing: "bg-purple-50 text-purple-700 border-purple-200",
};

export function FailureList({ failures, onRetry }: FailureListProps) {
  if (failures.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
        No failures recorded.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Stage</TableHead>
          <TableHead>Error Type</TableHead>
          <TableHead>Message</TableHead>
          <TableHead>Retryable</TableHead>
          <TableHead>Suggested Action</TableHead>
          <TableHead>Time</TableHead>
          {onRetry && <TableHead className="text-right">Action</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {failures.map((failure) => (
          <TableRow key={failure.id}>
            <TableCell>
              <span
                className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium capitalize ${stageColor[failure.stage_name] ?? "bg-gray-50 text-gray-700 border-gray-200"}`}
              >
                {failure.stage_name}
              </span>
            </TableCell>
            <TableCell>
              <span className="text-sm font-medium text-destructive">
                {failure.error_type.replace(/_/g, " ")}
              </span>
            </TableCell>
            <TableCell className="max-w-[300px]">
              <p className="text-sm text-muted-foreground truncate">
                {failure.message}
              </p>
            </TableCell>
            <TableCell>
              {failure.is_retryable ? (
                <Badge variant="outline" className="border-green-200 text-green-700 bg-green-50">
                  Yes
                </Badge>
              ) : (
                <Badge variant="outline" className="border-red-200 text-red-700 bg-red-50">
                  No
                </Badge>
              )}
            </TableCell>
            <TableCell className="max-w-[200px]">
              <p className="text-sm text-muted-foreground truncate">
                {failure.suggested_action ?? "—"}
              </p>
            </TableCell>
            <TableCell className="text-muted-foreground text-sm whitespace-nowrap">
              {formatDateTime(failure.created_at)}
            </TableCell>
            {onRetry && (
              <TableCell className="text-right">
                {failure.is_retryable && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onRetry(failure)}
                    className="gap-1"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Retry
                  </Button>
                )}
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}