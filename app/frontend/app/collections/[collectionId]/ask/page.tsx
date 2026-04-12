"use client";

import { useState, use } from "react";
import useSWR from "swr";
import { QueryInput } from "@/components/ask/query-input";
import { AnswerCard } from "@/components/ask/answer-card";
import { askCollection } from "@/lib/api-client";
import type { AskResponse } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { MessageCircle } from "lucide-react";

export default function AskPage({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = use(params);
  const [query, setQuery] = useState<string | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | undefined>();

  async function handleSubmit(queryText: string) {
    setQuery(queryText);
    setResponse(null);
    setError(null);
    setIsLoading(true);
    const start = performance.now();

    try {
      const result = await askCollection(collectionId, { query: queryText });
      setResponse(result);
      setLatency(Math.round(performance.now() - start));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to get an answer."
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <h2 className="text-lg font-semibold">Ask</h2>

      <QueryInput
        onSubmit={handleSubmit}
        isLoading={isLoading}
        placeholder="Ask a question about your documents..."
      />

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700" role="alert">
          {error}
        </div>
      )}

      {/* Answer display */}
      {response && (
        <AnswerCard response={response} latency={latency} />
      )}

      {/* Empty state */}
      {!query && !isLoading && (
        <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
          <MessageCircle className="h-10 w-10 mb-3" />
          <p className="text-sm">
            Type a question above to query your knowledge base.
          </p>
          <p className="text-xs mt-1">
            Answers will include citations and source evidence.
          </p>
        </div>
      )}
    </div>
  );
}