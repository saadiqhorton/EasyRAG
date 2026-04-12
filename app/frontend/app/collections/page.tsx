import { listCollections } from "@/lib/api-client";
import { CollectionsClient } from "./collections-client";

export default async function CollectionsPage() {
  let collections = [];
  let error: string | null = null;

  try {
    collections = await listCollections();
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load collections.";
  }

  return <CollectionsClient initialCollections={collections} initialError={error} />;
}