"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Loader2 } from "lucide-react";

interface QueryInputProps {
  onSubmit: (query: string) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function QueryInput({
  onSubmit,
  isLoading = false,
  placeholder = "Ask a question about your documents...",
}: QueryInputProps) {
  const [query, setQuery] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || isLoading) return;
    onSubmit(trimmed);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const trimmed = query.trim();
      if (!trimmed || isLoading) return;
      onSubmit(trimmed);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <div className="flex-1">
        <Textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isLoading}
          rows={2}
          className="resize-none"
          aria-label="Enter your question"
        />
      </div>
      <Button
        type="submit"
        disabled={isLoading || !query.trim()}
        className="self-end"
        aria-label="Submit question"
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
      </Button>
    </form>
  );
}