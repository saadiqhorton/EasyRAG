"use client";

import { useState } from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { DocumentStatusBadge } from "./document-status-badge";
import type { DocumentListItem } from "@/lib/types";
import {
  formatStatus,
  mimeTypeLabel,
  formatDate,
  formatConfidence,
} from "@/lib/utils";
import { ArrowUpDown, RotateCcw, Trash2, Upload } from "lucide-react";

interface DocumentTableProps {
  documents: DocumentListItem[];
  onReplace?: (documentId: string) => void;
  onReindex?: (documentId: string) => void;
  onDelete?: (documentId: string) => void;
}

type SortKey = "title" | "index_status" | "updated_at" | "parse_confidence";

export function DocumentTable({
  documents,
  onReplace,
  onReindex,
  onDelete,
}: DocumentTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("updated_at");
  const [sortAsc, setSortAsc] = useState(false);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  const sorted = [...documents].sort((a, b) => {
    const dir = sortAsc ? 1 : -1;
    switch (sortKey) {
      case "title":
        return dir * a.title.localeCompare(b.title);
      case "index_status":
        return dir * a.index_status.localeCompare(b.index_status);
      case "updated_at":
        return dir * (new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime());
      case "parse_confidence": {
        const aConf = a.parse_confidence ?? -1;
        const bConf = b.parse_confidence ?? -1;
        return dir * (aConf - bConf);
      }
      default:
        return 0;
    }
  });

  if (documents.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground">
        No documents uploaded yet.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <SortableHead
            label="Title"
            sortKey="title"
            currentKey={sortKey}
            asc={sortAsc}
            onSort={toggleSort}
          />
          <TableHead>Type</TableHead>
          <SortableHead
            label="Status"
            sortKey="index_status"
            currentKey={sortKey}
            asc={sortAsc}
            onSort={toggleSort}
          />
          <TableHead>Version</TableHead>
          <TableHead>Source</TableHead>
          <SortableHead
            label="Updated"
            sortKey="updated_at"
            currentKey={sortKey}
            asc={sortAsc}
            onSort={toggleSort}
          />
          <SortableHead
            label="Confidence"
            sortKey="parse_confidence"
            currentKey={sortKey}
            asc={sortAsc}
            onSort={toggleSort}
          />
          <TableHead className="text-right">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((doc) => (
          <TableRow key={doc.id}>
            <TableCell className="font-medium max-w-[200px] truncate">
              {doc.title}
            </TableCell>
            <TableCell>{mimeTypeLabel(doc.mime_type)}</TableCell>
            <TableCell>
              <DocumentStatusBadge status={doc.index_status} />
            </TableCell>
            <TableCell>v{doc.version_number}</TableCell>
            <TableCell className="max-w-[150px] truncate text-muted-foreground">
              {doc.original_filename}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatDate(doc.updated_at)}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatConfidence(doc.parse_confidence)}
            </TableCell>
            <TableCell className="text-right">
              <div className="flex items-center justify-end gap-1">
                {doc.index_status === "failed" && onReindex && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onReindex(doc.id)}
                    title="Reindex document"
                    aria-label={`Reindex ${doc.title}`}
                  >
                    <RotateCcw className="h-4 w-4" />
                  </Button>
                )}
                {onReplace && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onReplace(doc.id)}
                    title="Replace document"
                    aria-label={`Replace ${doc.title}`}
                  >
                    <Upload className="h-4 w-4" />
                  </Button>
                )}
                {onDelete && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(doc.id)}
                    title="Delete document"
                    aria-label={`Delete ${doc.title}`}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function SortableHead({
  label,
  sortKey,
  currentKey,
  asc,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  currentKey: SortKey;
  asc: boolean;
  onSort: (key: SortKey) => void;
}) {
  const isActive = sortKey === currentKey;
  return (
    <TableHead
      className="cursor-pointer select-none"
      onClick={() => onSort(sortKey)}
      aria-sort={isActive ? (asc ? "ascending" : "descending") : "none"}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <ArrowUpDown
          className={`h-3 w-3 ${isActive ? "text-foreground" : "text-muted-foreground/40"}`}
        />
      </span>
    </TableHead>
  );
}