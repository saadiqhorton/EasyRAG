import { describe, it, expect } from "vitest";
import type {
  DocumentListItem,
  Citation,
  EvidenceItem,
  DocumentStatus,
  AnswerMode,
  IngestionJobStatus,
} from "@/lib/types";

describe("Type alignment with backend", () => {
  it("DocumentListItem should use backend field names", () => {
    const doc: DocumentListItem = {
      id: "uuid-1",
      title: "Test Doc",
      mime_type: "application/pdf",
      index_status: "indexed",
      version_number: 1,
      original_filename: "test.pdf",
      updated_at: "2026-04-12T10:00:00Z",
      parse_confidence: 0.85,
    };
    expect(doc.mime_type).toBe("application/pdf");
    expect(doc.index_status).toBe("indexed");
    expect(doc.version_number).toBe(1);
    expect(doc.original_filename).toBe("test.pdf");
    expect(doc.updated_at).toBe("2026-04-12T10:00:00Z");
  });

  it("Citation should use source_number not index", () => {
    const citation: Citation = {
      source_number: 1,
      document_title: "Test Document",
      page_number: 5,
      section_path: "Chapter 1",
      chunk_id: "uuid-chunk",
    };
    expect(citation.source_number).toBe(1);
    expect(citation.document_title).toBe("Test Document");
  });

  it("EvidenceItem should have ocr_used and citation_anchor", () => {
    const evidence: EvidenceItem = {
      chunk_id: "uuid-chunk",
      text: "sample text",
      document_id: "uuid-doc",
      document_title: "Test Doc",
      page_number: null,
      section_path: null,
      modality: "text",
      confidence: 0.9,
      ocr_used: false,
      citation_anchor: "Test Doc - Page 5",
    };
    expect(evidence.ocr_used).toBe(false);
    expect(evidence.citation_anchor).toBe("Test Doc - Page 5");
  });

  it("DocumentStatus should cover all backend states", () => {
    const statuses: DocumentStatus[] = [
      "pending",
      "indexing",
      "indexed",
      "failed",
      "superseded",
    ];
    expect(statuses).toHaveLength(5);
  });

  it("AnswerMode should cover all backend modes", () => {
    const modes: AnswerMode[] = [
      "answered_with_evidence",
      "partially_answered_with_caveat",
      "insufficient_evidence",
    ];
    expect(modes).toHaveLength(3);
  });

  it("IngestionJobStatus should cover all backend states", () => {
    const statuses: IngestionJobStatus[] = [
      "queued",
      "parsing",
      "chunking",
      "embedding",
      "indexing",
      "succeeded",
      "failed",
    ];
    expect(statuses).toHaveLength(7);
  });
});