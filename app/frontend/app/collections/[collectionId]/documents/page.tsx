"use client";

import { use, useState, useCallback } from "react";
import useSWR from "swr";
import { DocumentTable } from "@/components/documents/document-table";
import { UploadDropzone } from "@/components/documents/upload-dropzone";
import { UploadProgress } from "@/components/documents/upload-progress";
import { listDocuments, uploadDocument, deleteDocument, reindexCollection } from "@/lib/api-client";
import type { DocumentUploadResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Upload, RefreshCw } from "lucide-react";

interface UploadItem {
  file: File;
  uploadResponse?: DocumentUploadResponse;
  error?: string;
}

export default function DocumentsPage({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = use(params);
  const [showUpload, setShowUpload] = useState(false);
  const [uploads, setUploads] = useState<UploadItem[]>([]);

  const { data: documents, mutate, error } = useSWR(
    collectionId ? `/collections/${collectionId}/documents` : null,
    () => listDocuments(collectionId),
    { revalidateOnFocus: false }
  );

  const handleFilesSelected = useCallback(
    async (files: File[]) => {
      const newUploads: UploadItem[] = files.map((file) => ({ file }));
      setUploads((prev) => [...prev, ...newUploads]);

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        try {
          const response = await uploadDocument(collectionId, file);
          setUploads((prev) => {
            const targetIdx = prev.length - files.length + i;
            return prev.map((item, idx) =>
              idx === targetIdx ? { ...item, uploadResponse: response } : item
            );
          });
          mutate();
        } catch (err) {
          setUploads((prev) => {
            const targetIdx = prev.length - files.length + i;
            return prev.map((item, idx) =>
              idx === targetIdx
                ? {
                    ...item,
                    error: err instanceof Error ? err.message : "Upload failed",
                  }
                : item
            );
          });
        }
      }
    },
    [collectionId, mutate]
  );

  const handleRemoveUpload = useCallback((index: number) => {
    setUploads((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleReplace = useCallback(
    (documentId: string) => {
      // Open the upload dropzone for replacement
      setShowUpload(true);
    },
    []
  );

  const handleReindex = useCallback(
    async (documentId: string) => {
      try {
        await reindexCollection(collectionId, { document_id: documentId });
        mutate();
      } catch {
        // Error handled silently; UI can add toast notification later
      }
    },
    [collectionId, mutate]
  );

  const handleDelete = useCallback(
    async (documentId: string) => {
      if (!confirm("Are you sure you want to delete this document?")) return;
      try {
        await deleteDocument(documentId);
        mutate();
      } catch {
        // Error handled silently
      }
    },
    [mutate]
  );

  return (
    <div className="space-y-4 max-w-5xl">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Documents</h2>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => mutate()}
            className="gap-1.5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={() => setShowUpload(!showUpload)}
            className="gap-1.5"
          >
            <Upload className="h-3.5 w-3.5" />
            Upload
          </Button>
        </div>
      </div>

      {showUpload && (
        <div className="space-y-3">
          <UploadDropzone onFilesSelected={handleFilesSelected} />
          <UploadProgress uploads={uploads} onRemove={handleRemoveUpload} />
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load documents: {error.message}
        </div>
      )}

      {!error && (
        <DocumentTable
          documents={documents?.items ?? []}
          onReplace={handleReplace}
          onReindex={handleReindex}
          onDelete={handleDelete}
        />
      )}
    </div>
  );
}