import Link from "next/link";
import { getCollection } from "@/lib/api-client";
import { notFound } from "next/navigation";
import { Upload, MessageCircle, Activity, Settings, LayoutDashboard, FileText } from "lucide-react";

const TAB_ITEMS = [
  { label: "Overview", pathSegment: "", icon: LayoutDashboard },
  { label: "Documents", pathSegment: "/documents", icon: FileText },
  { label: "Ask", pathSegment: "/ask", icon: MessageCircle },
  { label: "Diagnostics", pathSegment: "/diagnostics", icon: Activity },
  { label: "Settings", pathSegment: "/settings", icon: Settings },
];

export default async function CollectionDetailLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ collectionId: string }>;
}) {
  const { collectionId } = await params;
  let collection;
  try {
    collection = await getCollection(collectionId);
  } catch {
    notFound();
  }

  const basePath = `/collections/${collectionId}`;

  return (
    <div className="flex flex-col h-full">
      {/* Collection header */}
      <header className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight">
            {collection.name}
          </h1>
          {collection.description && (
            <p className="text-sm text-muted-foreground mt-0.5">
              {collection.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Link href={`${basePath}/documents`}>
            <button className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-muted transition-colors">
              <Upload className="h-4 w-4" />
              Upload
            </button>
          </Link>
          <Link href={`${basePath}/ask`}>
            <button className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors">
              <MessageCircle className="h-4 w-4" />
              Ask
            </button>
          </Link>
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="border-b px-6" aria-label="Collection tabs">
        <ul className="flex gap-6">
          {TAB_ITEMS.map((tab) => {
            const href = `${basePath}${tab.pathSegment}`;
            return (
              <li key={tab.label}>
                <Link
                  href={href}
                  className="inline-flex items-center gap-1.5 border-b-2 border-transparent py-3 text-sm font-medium text-muted-foreground hover:border-foreground/30 hover:text-foreground transition-colors"
                >
                  <tab.icon className="h-3.5 w-3.5" />
                  {tab.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-6">
        {children}
      </div>
    </div>
  );
}