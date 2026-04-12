import { getAnswer } from "@/lib/api-client";
import { notFound } from "next/navigation";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { EvidenceInspector } from "@/components/evidence/evidence-inspector";
import { CitationsPanel } from "@/components/ask/citations-panel";
import {
  formatAnswerMode,
  answerModeColor,
  formatLatency,
  formatDateTime,
  formatConfidence,
} from "@/lib/utils";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Cpu,
} from "lucide-react";

const modeIcon = {
  answered_with_evidence: <CheckCircle2 className="h-4 w-4" />,
  partially_answered_with_caveat: <AlertTriangle className="h-4 w-4" />,
  insufficient_evidence: <XCircle className="h-4 w-4" />,
};

export default async function AnswerDetailPage({
  params,
}: {
  params: Promise<{ answerId: string }>;
}) {
  const { answerId } = await params;
  let answer;
  try {
    answer = await getAnswer(answerId);
  } catch {
    notFound();
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-tight">Answer Detail</h1>
        <span
          className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium ${answerModeColor(answer.answer_mode)}`}
          role="status"
        >
          {modeIcon[answer.answer_mode]}
          {formatAnswerMode(answer.answer_mode)}
        </span>
      </div>

      {/* Answer metadata */}
      <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
        <span className="flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" />
          {formatLatency(answer.latency_ms)}
        </span>
        <span className="flex items-center gap-1">
          <Cpu className="h-3.5 w-3.5" />
          {answer.llm_model}
        </span>
        <span>Reranker: {answer.reranker_used ? "Yes" : "No"}</span>
        <span>{formatDateTime(answer.created_at)}</span>
      </div>

      <Separator />

      {/* Answer text */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Answer</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {answer.answer_text}
          </div>
        </CardContent>
      </Card>

      {/* Citations */}
      {answer.citations.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              Citations ({answer.citations.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CitationsPanel citations={answer.citations} />
          </CardContent>
        </Card>
      )}

      {/* Full evidence */}
      {answer.evidence.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              Evidence ({answer.evidence.length} chunks)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {answer.evidence.map((item) => (
              <div
                key={item.chunk_id}
                className="rounded-md border p-4"
              >
                <EvidenceInspector item={item} />
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}