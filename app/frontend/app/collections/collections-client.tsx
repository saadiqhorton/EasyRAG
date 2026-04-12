"use client";

import { useState } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CollectionCard } from "@/components/collections/collection-card";
import { CreateCollectionModal } from "@/components/collections/create-collection-modal";
import { listCollections } from "@/lib/api-client";
import type { Collection } from "@/lib/types";
import { Plus, AlertCircle, RefreshCw } from "lucide-react";

interface CollectionsClientProps {
  initialCollections: Collection[];
  initialError: string | null;
}

export function CollectionsClient({
  initialCollections,
  initialError,
}: CollectionsClientProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const { data, error, mutate } = useSWR<Collection[]>(
    "/collections",
    () => listCollections(),
    {
      fallbackData: initialCollections,
      revalidateOnFocus: false,
    }
  );

  const collections = data ?? [];
  const displayError = error
    ? error.message
    : initialError;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Collections</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your knowledge collections.
          </p>
        </div>
        <Button onClick={() => setModalOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Collection
        </Button>
      </div>

      {displayError && (
        <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 mb-6" role="alert">
          <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p>{displayError}</p>
            <button
              onClick={() => mutate()}
              className="mt-2 text-xs underline hover:no-underline"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {!displayError && collections.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-muted-foreground mb-4">
            No collections yet. Create one to get started.
          </p>
          <Button onClick={() => setModalOpen(true)} variant="outline" className="gap-2">
            <Plus className="h-4 w-4" />
            Create Collection
          </Button>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {collections.map((collection) => (
          <CollectionCard key={collection.id} collection={collection} />
        ))}
      </div>

      <CreateCollectionModal
        open={modalOpen}
        onOpenChange={setModalOpen}
        onCreated={() => mutate()}
      />
    </div>
  );
}