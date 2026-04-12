import { use } from "react";
import { getCollection, deleteCollection } from "@/lib/api-client";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import { Trash2 } from "lucide-react";
import { redirect } from "next/navigation";

export default async function SettingsPage({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = await params;
  let collection;
  try {
    collection = await getCollection(collectionId);
  } catch {
    return (
      <div className="text-sm text-muted-foreground">
        Could not load collection details.
      </div>
    );
  }

  async function handleDelete() {
    "use server";
    await deleteCollection(collectionId);
    redirect("/collections");
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-lg font-semibold">Settings</h2>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Collection Info</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>
            <span className="text-muted-foreground">Name</span>
            <p className="font-medium">{collection.name}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Description</span>
            <p className="font-medium">{collection.description ?? "—"}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Created</span>
            <p className="font-medium">{formatDate(collection.created_at)}</p>
          </div>
          <div>
            <span className="text-muted-foreground">Updated</span>
            <p className="font-medium">{formatDate(collection.updated_at)}</p>
          </div>
        </CardContent>
      </Card>

      <Card className="border-red-200">
        <CardHeader className="pb-3">
          <CardTitle className="text-base text-destructive">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground mb-4">
            Deleting this collection will remove all documents, versions, chunks,
            and indexed data. This action cannot be undone.
          </p>
          <form action={handleDelete}>
            <Button type="submit" variant="destructive" className="gap-2">
              <Trash2 className="h-4 w-4" />
              Delete Collection
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}