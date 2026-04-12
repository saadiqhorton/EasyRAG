"use client";

import { useState } from "react";
import type { EvidenceItem } from "@/lib/types";
import { formatConfidence, truncate } from "@/lib/utils";
import { ChevronDown, ChevronUp, FileText, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EvidenceDrawerProps {
  evidence: EvidenceItem[];
}

export function EvidenceDrawer({ evidence }: EvidenceDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border rounded-md">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between w-full px-3 py-2 text-sm font-medium hover:bg-muted transition-colors"
        aria-expanded={isOpen}
        aria-controls="evidence-drawer-content"
      >
        <span>
          Retrieved Evidence ({evidence.length}{" "}
          {evidence.length === 1 ? "chunk" : "chunks"})
        </span>
        {isOpen ? (
          <ChevronUp className="h-4 w-4" />
        ) : (
          <ChevronDown className="h-4 w-4" />
        )}
      </button>

      {isOpen && (
        <div
          id="evidence-drawer-content"
          className="border-t divide-y max-h-[400px] overflow-y-auto"
        >
          {evidence.map((item, index) => (
            <EvidenceChunkRow key={item.chunk_id} item={item} index={index} />
          ))}
        </div>
      )}
    </div>
  );
}

function EvidenceChunkRow({
  item,
  index,
}: {
  item: EvidenceItem;
  index: number;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="px-3 py-2">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-start gap-2 w-full text-left"
        aria-expanded={expanded}
      >
        <span className="flex items-center justify-center h-5 w-5 rounded bg-primary/10 text-xs font-medium text-primary shrink-0 mt-0.5">
          {index + 1}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium">{item.document_title}</span>
            {item.page_number != null && (
              <span className="text-xs text-muted-foreground">
                p.{item.page_number}
              </span>
            )}
            {item.section_path && (
              <span className="text-xs text-muted-foreground truncate">
                {item.section_path}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-muted-foreground">
              Confidence: {formatConfidence(item.confidence)}
            </span>
            {item.ocr_used && (
              <span className="inline-flex items-center rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                OCR
              </span>
            )}
            <span className="text-xs text-muted-foreground capitalize">
              {item.modality}
            </span>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            {expanded ? item.text : truncate(item.text, 150)}
          </p>
        </div>
      </button>
    </div>
  );
}