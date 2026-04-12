import { getCollection, getCollectionHealth } from "@/lib/api-client";
import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate, formatBytes } from "@/lib/utils";
import {
  Database,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
  Archive,
} from "lucide-react";

export default async function CollectionOverviewPage({
  params,
}: {
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = await params;
  let collection;
  let health;

  try {
    collection = await getCollection(collectionId);
  } catch {
    notFound();
  }

  try {
    health = await getCollectionHealth(collectionId);
  } catch {
    health = null;
  }

  const summary = collection.index_status_summary;

  return (
    <div className="space-y-6 max-w-3xl">
      <h2 className="text-lg font-semibold">Overview</h2>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Database className="h-4 w-4" />
              Documents
            </div>
            <p className="text-2xl font-bold mt-1">{collection.document_count}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-sm text-green-600">
              <CheckCircle2 className="h-4 w-4" />
              Indexed
            </div>
            <p className="text-2xl font-bold mt-1">{summary.indexed}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-sm text-blue-600">
              <Loader2 className="h-4 w-4" />
              Indexing
            </div>
            <p className="text-2xl font-bold mt-1">
              {summary.indexing + summary.pending}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4 pb-4">
            <div className="flex items-center gap-2 text-sm text-red-600">
              <AlertCircle className="h-4 w-4" />
              Failed
            </div>
            <p className="text-2xl font-bold mt-1">{summary.failed}</p>
          </CardContent>
        </Card>
      </div>

      {/* Health summary */}
      {health && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Health</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Total documents</span>
                <p className="font-medium">{health.total_documents}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Indexed</span>
                <p className="font-medium">{health.indexed_count}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Failed</span>
                <p className="font-medium text-destructive">{health.failed_count}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Storage used</span>
                <p className="font-medium">{formatBytes(health.storage_bytes)}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Last ingestion</span>
                <p className="font-medium">{formatDate(health.last_ingestion_at)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Index status breakdown */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Index Status Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            {summary.pending > 0 && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" /> Pending
                </span>
                <Badge variant="outline">{summary.pending}</Badge>
              </div>
            )}
            {summary.indexing > 0 && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-blue-600">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Indexing
                </span>
                <Badge variant="outline">{summary.indexing}</Badge>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-green-600">
                <CheckCircle2 className="h-3.5 w-3.5" /> Indexed
              </span>
              <Badge variant="outline">{summary.indexed}</Badge>
            </div>
            {summary.failed > 0 && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-red-600">
                  <AlertCircle className="h-3.5 w-3.5" /> Failed
                </span>
                <Badge variant="destructive">{summary.failed}</Badge>
              </div>
            )}
            {summary.superseded > 0 && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Archive className="h-3.5 w-3.5" /> Superseded
                </span>
                <Badge variant="outline" className="text-muted-foreground">
                  {summary.superseded}
                </Badge>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Recent failures */}
      {collection.recent_failures.length > 0 && (
        <Card className="border-red-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-destructive flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              Recent Failures
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {collection.recent_failures.slice(0, 5).map((failure) => (
                <li
                  key={failure.id}
                  className="flex items-start justify-between gap-4"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-destructive">
                      {failure.error_type.replace(/_/g, " ")}
                    </p>
                    <p className="text-muted-foreground truncate">
                      {failure.message}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {formatDate(failure.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}