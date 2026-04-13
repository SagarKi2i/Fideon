import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { ClipboardCheck, Loader2, CheckCircle2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createDecisionReview } from "@/lib/reviewQueueApi";

interface SendToReviewProps {
  readonly podModelId: string;
  readonly podModelName: string;
  readonly domain: string;
  readonly result: string;
  readonly inputData?: Record<string, any>;
}

const DECISION_TYPES = [
  { value: "quote_approval", label: "Quote Approval" },
  { value: "claim_decision", label: "Claim Decision" },
  { value: "submission_triage", label: "Submission Triage" },
  { value: "policy_review", label: "Policy Review" },
  { value: "risk_assessment", label: "Risk Assessment" },
  { value: "document_validation", label: "Document Validation" },
  { value: "acord_parsing_review", label: "ACORD Parsing Review" },
  { value: "document_extraction_review", label: "Document Extraction Review" },
  { value: "endorsement_recommendation", label: "Endorsement Recommendation" },
  { value: "underwriting_recommendation", label: "Underwriting Recommendation" },
  { value: "fraud_flag_review", label: "Fraud Flag Review" },
  { value: "settlement_recommendation", label: "Settlement Recommendation" },
  { value: "compliance_exception", label: "Compliance Exception" },
  { value: "coverage_gap_review", label: "Coverage Gap Review" },
  { value: "renewal_strategy_review", label: "Renewal Strategy Review" },
  { value: "other", label: "Other" },
];

export function SendToReviewButton({ podModelId, podModelName, domain, result, inputData = {} }: SendToReviewProps) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [title, setTitle] = useState("");
  const [decisionType, setDecisionType] = useState("quote_approval");
  const [summary, setSummary] = useState("");

  const handleSend = async () => {
    if (!title.trim()) {
      toast({ title: "Title required", description: "Please provide a title for the review", variant: "destructive" });
      return;
    }

    setSending(true);
    try {
      await createDecisionReview({
        pod_model_id: podModelId,
        pod_model_name: podModelName,
        domain,
        decision_type: decisionType,
        title: title.trim(),
        summary: summary.trim() || null,
        ai_recommendation: result.substring(0, 2000),
        confidence_score: null,
        threshold_exceeded: false,
        input_data: inputData,
        output_data: { full_result: result.substring(0, 5000) },
      });

      toast({ title: "Sent to Review Queue", description: "Your decision has been submitted for human review" });
      setSent(true);
      setOpen(false);
    } catch (error) {
      console.error("Error sending to review:", error);
      toast({ title: "Error", description: "Failed to submit for review", variant: "destructive" });
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <Button variant="outline" size="sm" disabled className="gap-1.5 text-primary">
        <CheckCircle2 className="h-3.5 w-3.5" />
        Sent to Review
      </Button>
    );
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <ClipboardCheck className="h-3.5 w-3.5" />
          Send to Review
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Send to Review Queue</DialogTitle>
          <DialogDescription>Submit this AI output for human review and approval</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label>Title *</Label>
            <Input
              placeholder="e.g. Commercial Property Quote - ABC Corp"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Decision Type</Label>
            <Select value={decisionType} onValueChange={setDecisionType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DECISION_TYPES.map((t: any) => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Summary (optional)</Label>
            <Textarea
              placeholder="Brief context about what needs review..."
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={handleSend} disabled={sending}>
            {sending ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <ClipboardCheck className="h-4 w-4 mr-1" />}
            Submit for Review
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
