import { cn, formatStatus, statusColor } from "@/lib/utils";
import type { DocumentStatus } from "@/lib/types";
import { AlertCircle, Loader2, CheckCircle2, Clock, Archive } from "lucide-react";

interface DocumentStatusBadgeProps {
  status: DocumentStatus;
  className?: string;
}

export function DocumentStatusBadge({
  status,
  className,
}: DocumentStatusBadgeProps) {
  const icon = {
    pending: <Clock className="h-3 w-3" />,
    indexing: <Loader2 className="h-3 w-3 animate-spin" />,
    indexed: <CheckCircle2 className="h-3 w-3" />,
    failed: <AlertCircle className="h-3 w-3" />,
    superseded: <Archive className="h-3 w-3" />,
  }[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium",
        statusColor(status),
        className
      )}
      role="status"
      aria-label={`Document status: ${formatStatus(status)}`}
    >
      {icon}
      {formatStatus(status)}
    </span>
  );
}