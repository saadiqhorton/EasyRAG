"use client";

import { useCallback, useState, useRef } from "react";
import { Upload, FileText, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const ACCEPTED_TYPES = [
  "text/markdown",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/html",
];

const ACCEPTED_EXTENSIONS = ".md,.pdf,.docx,.txt,.html";
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

interface UploadDropzoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled?: boolean;
}

export function UploadDropzone({
  onFilesSelected,
  disabled = false,
}: UploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFiles = useCallback(
    (fileList: FileList | File[]): { valid: File[]; errors: string[] } => {
      const files = Array.from(fileList);
      const valid: File[] = [];
      const errors: string[] = [];

      for (const file of files) {
        // Check MIME type
        if (
          !ACCEPTED_TYPES.includes(file.type) &&
          !file.name.match(/\.(md|pdf|docx|txt|html)$/i)
        ) {
          errors.push(
            `"${file.name}" is not a supported file type. Accepted: .md, .pdf, .docx, .txt, .html`
          );
          continue;
        }
        // Check file size
        if (file.size > MAX_FILE_SIZE) {
          errors.push(
            `"${file.name}" exceeds the 50MB size limit.`
          );
          continue;
        }
        valid.push(file);
      }

      return { valid, errors };
    },
    []
  );

  const handleFiles = useCallback(
    (fileList: FileList | File[]) => {
      setValidationError(null);
      const { valid, errors } = validateFiles(fileList);
      if (errors.length > 0) {
        setValidationError(errors.join(" "));
      }
      if (valid.length > 0) {
        onFilesSelected(valid);
      }
    },
    [validateFiles, onFilesSelected]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) setIsDragOver(true);
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      if (disabled) return;
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles, disabled]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        handleFiles(e.target.files);
      }
      // Reset input so the same file can be re-selected
      e.target.value = "";
    },
    [handleFiles]
  );

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label="Upload files by dropping them here or clicking to browse"
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors cursor-pointer",
          isDragOver
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-muted/50",
          disabled && "opacity-50 cursor-not-allowed"
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && !disabled) {
            inputRef.current?.click();
          }
        }}
      >
        <Upload className="h-8 w-8 text-muted-foreground mb-3" />
        <p className="text-sm font-medium">
          Drop files here, or click to browse
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Supports .md, .pdf, .docx, .txt, .html (max 50MB each)
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          multiple
          className="hidden"
          onChange={handleInputChange}
          disabled={disabled}
          aria-hidden="true"
        />
      </div>

      {validationError && (
        <div
          className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          role="alert"
        >
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <span>{validationError}</span>
        </div>
      )}
    </div>
  );
}