import type { EvidenceItem } from "@/lib/types";
import {
  formatConfidence,
  formatDate,
  formatBytes,
} from "@/lib/utils";
import { FileText, Hash, BookOpen, Eye } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { ChunkViewer } from "./chunk-viewer";

interface EvidenceInspectorProps {
  item: EvidenceItem;
  onClose?: () => void;
}

export function EvidenceInspector({ item, onClose }: EvidenceInspectorProps) {
  return (
    <div className="space-y-4">
      {/* Header with source metadata */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <FileText className="h-4 w-4" />
            {item.document_title}
          </h3>
          {onClose && (
            <button
              onClick={onClose}
              className="text-sm text-muted-foreground hover:text-foreground"
              aria-label="Close inspector"
            >
              Close
            </button>
          )}
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          {item.page_number != null && (
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Hash className="h-3.5 w-3.5" />
              <span>Page {item.page_number}</span>
            </div>
          )}
          {item.section_path && (
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <BookOpen className="h-3.5 w-3.5" />
              <span>{item.section_path}</span>
            </div>
          )}
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Eye className="h-3.5 w-3.5" />
            <span>
              Confidence: {formatConfidence(item.confidence)}
            </span>
          </div>
        </div>

        {/* Modality and OCR badges */}
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium capitalize bg-muted">
            {item.modality}
          </span>
          {item.ocr_used && (
            <span className="inline-flex items-center rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
              OCR extracted
            </span>
          )}
        </div>
      </div>

      <Separator />

      {/* Chunk text viewer */}
      <ChunkViewer text={item.text} />

      {/* Confidence bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Parse confidence</span>
          <span>{formatConfidence(item.confidence)}</span>
        </div>
        <div className="h-2 rounded-full bg-muted overflow-hidden">
          <div
            className={`h-full rounded-full ${
              item.confidence >= 0.8
                ? "bg-green-500"
                : item.confidence >= 0.5
                  ? "bg-amber-500"
                  : "bg-red-500"
            }`}
            style={{ width: `${item.confidence * 100}%` }}
            role="progressbar"
            aria-valuenow={Math.round(item.confidence * 100)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Parse confidence"
          />
        </div>
      </div>

      {/* Link to original document */}
      <div className="pt-2">
        <a
          href={`/collections/${item.document_id}`}
          className="text-sm text-primary hover:underline"
        >
          View original document
        </a>
      </div>
    </div>
  );
}