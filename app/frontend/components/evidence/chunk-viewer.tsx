"use client";

import { useRef } from "react";

interface ChunkViewerProps {
  text: string;
  highlightText?: string;
}

export function ChunkViewer({ text, highlightText }: ChunkViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // If highlight text provided, bold the matching segments
  const renderedText = highlightText
    ? renderHighlighted(text, highlightText)
    : text;

  return (
    <div
      ref={containerRef}
      className="max-h-[300px] overflow-y-auto rounded-md border bg-muted/30 p-4 text-sm leading-relaxed whitespace-pre-wrap"
      role="region"
      aria-label="Chunk text content"
    >
      {renderedText}
    </div>
  );
}

function renderHighlighted(text: string, query: string): React.ReactNode {
  // Simple case-insensitive substring highlight
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase().trim();
  if (!lowerQuery) return text;

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let searchFrom = 0;

  while (searchFrom < lowerText.length) {
    const idx = lowerText.indexOf(lowerQuery, searchFrom);
    if (idx === -1) break;

    if (idx > lastIndex) {
      parts.push(text.slice(lastIndex, idx));
    }
    parts.push(
      <mark key={idx} className="bg-yellow-200 rounded-sm px-0.5">
        {text.slice(idx, idx + query.length)}
      </mark>
    );
    lastIndex = idx + query.length;
    searchFrom = lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}