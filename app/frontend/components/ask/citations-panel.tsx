"use client";

import type { Citation } from "@/lib/types";
import { FileText, Hash } from "lucide-react";

interface CitationsPanelProps {
  citations: Citation[];
  onCitationClick?: (citation: Citation) => void;
}

export function CitationsPanel({
  citations,
  onCitationClick,
}: CitationsPanelProps) {
  return (
    <ul className="space-y-1.5" aria-label="Citations">
      {citations.map((citation) => (
        <li key={citation.source_number}>
          <button
            type="button"
            onClick={() => onCitationClick?.(citation)}
            className="flex items-start gap-2 w-full rounded-md p-2 text-left text-sm hover:bg-muted transition-colors"
            aria-label={`Citation ${citation.source_number}: ${citation.document_title}`}
          >
            <span className="flex items-center justify-center h-5 w-5 rounded bg-primary/10 text-xs font-medium text-primary shrink-0">
              {citation.source_number}
            </span>
            <div className="min-w-0">
              <span className="font-medium">
                {citation.document_title}
              </span>
              <span className="text-muted-foreground">
                {citation.page_number != null && (
                  <span className="ml-1.5 flex items-center gap-0.5 inline">
                    <Hash className="h-3 w-3" />
                    p.{citation.page_number}
                  </span>
                )}
                {citation.section_path && (
                  <span className="ml-1.5">
                    {citation.section_path}
                  </span>
                )}
              </span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}