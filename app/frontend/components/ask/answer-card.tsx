"use client";

import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { CitationsPanel } from "./citations-panel";
import { EvidenceDrawer } from "./evidence-drawer";
import type { AskResponse } from "@/lib/types";
import {
  formatAnswerMode,
  answerModeColor,
  formatLatency,
  formatConfidence,
} from "@/lib/utils";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
} from "lucide-react";

interface AnswerCardProps {
  response: AskResponse;
  latency?: number;
}

const modeIcon = {
  answered_with_evidence: <CheckCircle2 className="h-4 w-4" />,
  partially_answered_with_caveat: <AlertTriangle className="h-4 w-4" />,
  insufficient_evidence: <XCircle className="h-4 w-4" />,
};

export function AnswerCard({ response, latency }: AnswerCardProps) {
  const { answer_text, answer_mode, citations, evidence } = response;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Answer</CardTitle>
          <div className="flex items-center gap-2">
            {latency != null && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {formatLatency(latency)}
              </span>
            )}
            <span
              className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium ${answerModeColor(answer_mode)}`}
              role="status"
            >
              {modeIcon[answer_mode]}
              {formatAnswerMode(answer_mode)}
            </span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Answer text with inline citation markers */}
        <div className="text-sm leading-relaxed whitespace-pre-wrap">
          {answer_text}
        </div>

        <Separator />

        {/* Citations always visible alongside the answer (UX rule: never show polished answer without sources nearby) */}
        {citations.length > 0 && (
          <div>
            <h3 className="text-sm font-medium mb-2">Sources</h3>
            <CitationsPanel citations={citations} />
          </div>
        )}

        {/* Evidence drawer for detailed inspection */}
        {evidence.length > 0 && (
          <div>
            <EvidenceDrawer evidence={evidence} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}