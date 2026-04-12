import { describe, it, expect } from "vitest";
import {
  formatDate,
  formatDateTime,
  formatBytes,
  formatLatency,
  formatStatus,
  formatJobStatus,
  formatAnswerMode,
  formatConfidence,
  mimeTypeLabel,
  truncate,
  cn,
  statusColor,
  answerModeColor,
} from "@/lib/utils";
import type { DocumentStatus, AnswerMode, IngestionJobStatus } from "@/lib/types";

describe("formatDate", () => {
  it("should format a valid ISO date string", () => {
    const result = formatDate("2026-04-12T10:30:00Z");
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });

  it("should return dash for null input", () => {
    expect(formatDate(null)).toBe("—");
  });

  it("should return dash for undefined input", () => {
    expect(formatDate(undefined)).toBe("—");
  });
});

describe("formatDateTime", () => {
  it("should format a valid ISO date string with time", () => {
    const result = formatDateTime("2026-04-12T10:30:00Z");
    expect(result).toBeTruthy();
    expect(typeof result).toBe("string");
  });

  it("should return dash for null input", () => {
    expect(formatDateTime(null)).toBe("—");
  });
});

describe("formatBytes", () => {
  it("should format 0 bytes", () => {
    expect(formatBytes(0)).toBe("0 B");
  });

  it("should format bytes", () => {
    expect(formatBytes(500)).toBe("500 B");
  });

  it("should format kilobytes", () => {
    expect(formatBytes(1024)).toBe("1.0 KB");
  });

  it("should format megabytes", () => {
    expect(formatBytes(1048576)).toBe("1.0 MB");
  });

  it("should return dash for null", () => {
    expect(formatBytes(null)).toBe("—");
  });

  it("should return dash for undefined", () => {
    expect(formatBytes(undefined)).toBe("—");
  });
});

describe("formatLatency", () => {
  it("should format milliseconds under 1000", () => {
    expect(formatLatency(500)).toBe("500ms");
  });

  it("should format seconds", () => {
    expect(formatLatency(2500)).toBe("2.5s");
  });

  it("should return dash for null", () => {
    expect(formatLatency(null)).toBe("—");
  });
});

describe("formatStatus", () => {
  it("should format pending status", () => {
    expect(formatStatus("pending")).toBe("Pending");
  });

  it("should format indexed status", () => {
    expect(formatStatus("indexed")).toBe("Indexed");
  });

  it("should format failed status", () => {
    expect(formatStatus("failed")).toBe("Failed");
  });

  it("should format superseded status", () => {
    expect(formatStatus("superseded")).toBe("Superseded");
  });

  it("should return unknown status as-is", () => {
    expect(formatStatus("unknown" as DocumentStatus)).toBe("unknown");
  });
});

describe("formatJobStatus", () => {
  it("should format all job statuses", () => {
    expect(formatJobStatus("queued")).toBe("Queued");
    expect(formatJobStatus("parsing")).toBe("Parsing");
    expect(formatJobStatus("chunking")).toBe("Chunking");
    expect(formatJobStatus("embedding")).toBe("Embedding");
    expect(formatJobStatus("indexing")).toBe("Indexing");
    expect(formatJobStatus("succeeded")).toBe("Succeeded");
    expect(formatJobStatus("failed")).toBe("Failed");
  });
});

describe("formatAnswerMode", () => {
  it("should format answer modes", () => {
    expect(formatAnswerMode("answered_with_evidence")).toBe(
      "Answered with evidence"
    );
    expect(formatAnswerMode("partially_answered_with_caveat")).toBe(
      "Partial answer (caveat)"
    );
    expect(formatAnswerMode("insufficient_evidence")).toBe(
      "Insufficient evidence"
    );
  });
});

describe("formatConfidence", () => {
  it("should format confidence as percentage", () => {
    expect(formatConfidence(0.85)).toBe("85%");
  });

  it("should format 0 confidence", () => {
    expect(formatConfidence(0)).toBe("0%");
  });

  it("should return dash for null", () => {
    expect(formatConfidence(null)).toBe("—");
  });
});

describe("mimeTypeLabel", () => {
  it("should map known MIME types to labels", () => {
    expect(mimeTypeLabel("text/markdown")).toBe("Markdown");
    expect(mimeTypeLabel("application/pdf")).toBe("PDF");
    expect(mimeTypeLabel("application/vnd.openxmlformats-officedocument.wordprocessingml.document")).toBe("DOCX");
    expect(mimeTypeLabel("text/plain")).toBe("TXT");
    expect(mimeTypeLabel("text/html")).toBe("HTML");
  });

  it("should return raw MIME type for unknown types", () => {
    expect(mimeTypeLabel("image/png")).toBe("image/png");
  });
});

describe("truncate", () => {
  it("should not truncate short text", () => {
    expect(truncate("hello", 10)).toBe("hello");
  });

  it("should truncate long text with ellipsis", () => {
    const result = truncate("hello world this is a long string", 10);
    expect(result.length).toBe(10);
    expect(result.endsWith("…")).toBe(true);
  });
});

describe("cn", () => {
  it("should merge class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("should handle empty inputs", () => {
    expect(cn()).toBe("");
  });
});

describe("statusColor", () => {
  it("should return color classes for each status", () => {
    for (const status of ["pending", "indexing", "indexed", "failed", "superseded"] as DocumentStatus[]) {
      const result = statusColor(status);
      expect(result).toBeTruthy();
      expect(typeof result).toBe("string");
    }
  });
});

describe("answerModeColor", () => {
  it("should return color classes for each mode", () => {
    for (const mode of ["answered_with_evidence", "partially_answered_with_caveat", "insufficient_evidence"] as AnswerMode[]) {
      const result = answerModeColor(mode);
      expect(result).toBeTruthy();
      expect(typeof result).toBe("string");
    }
  });
});