import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { 
  CheckCircle2, XCircle, Clock, Eye, Brain, 
  AlertTriangle, ChevronDown, ChevronUp, Filter
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { useUserRole } from "@/hooks/useUserRole";
import {
  approveDecisionReview,
  listAllDecisionReviews,
  listMyDecisionReviews,
  rejectDecisionReview,
} from "@/lib/reviewQueueApi";

interface DecisionReview {
  id: string;
  user_id: string;
  pod_model_id: string;
  pod_model_name: string;
  domain: string;
  decision_type: string;
  title: string;
  summary: string | null;
  ai_recommendation: string | null;
  confidence_score: number | null;
  threshold_exceeded: boolean;
  input_data: Record<string, any>;
  output_data: Record<string, any>;
  status: string;
  reviewer_id: string | null;
  reviewer_notes: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

const DECISION_TYPE_LABELS: Record<string, string> = {
  quote_approval: "Quote Approval",
  claim_decision: "Claim Decision",
  submission_triage: "Submission Triage",
  policy_review: "Policy Review",
  risk_assessment: "Risk Assessment",
  document_validation: "Document Validation",
  acord_parsing_review: "ACORD Parsing Review",
  document_extraction_review: "Document Extraction Review",
  endorsement_recommendation: "Endorsement Recommendation",
  underwriting_recommendation: "Underwriting Recommendation",
  fraud_flag_review: "Fraud Flag Review",
  settlement_recommendation: "Settlement Recommendation",
  compliance_exception: "Compliance Exception",
  coverage_gap_review: "Coverage Gap Review",
  renewal_strategy_review: "Renewal Strategy Review",
  other: "Other",
};

const STATUS_CONFIG: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline"; icon: typeof Clock }> = {
  pending: { label: "Pending Review", variant: "secondary", icon: Clock },
  approved: { label: "Approved", variant: "default", icon: CheckCircle2 },
  rejected: { label: "Rejected", variant: "destructive", icon: XCircle },
};

export default function ReviewQueue() {
  const { toast } = useToast();
  const { isAdmin, loading: roleLoading } = useUserRole();
  const [searchParams] = useSearchParams();
  const [reviews, setReviews] = useState<DecisionReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [reviewerNotes, setReviewerNotes] = useState<Record<string, string>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [domainFilter, setDomainFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const requestedTab = searchParams.get("tab") === "completed" ? "completed" : "pending";
  const requestedReviewId = searchParams.get("reviewId");
  const [activeTab, setActiveTab] = useState<"pending" | "completed">(requestedTab);

  useEffect(() => {
    if (roleLoading) return;
    loadReviews();
  }, [roleLoading, isAdmin]);

  useEffect(() => {
    setActiveTab(requestedTab);
  }, [requestedTab]);

  const loadReviews = async () => {
    try {
      const rows = isAdmin ? await listAllDecisionReviews() : await listMyDecisionReviews();
      setReviews((rows as DecisionReview[]) ?? []);
    } catch (error) {
      console.error("Error loading reviews:", error);
      toast({ title: "Error", description: "Failed to load review queue", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (review: DecisionReview, action: "approved" | "rejected") => {
    setProcessingId(review.id);
    try {
      if (action === "approved") {
        await approveDecisionReview(review.id, reviewerNotes[review.id] ?? "");
      } else {
        await rejectDecisionReview(review.id, reviewerNotes[review.id] ?? "");
      }

      toast({
        title: action === "approved" ? "Decision Approved" : "Decision Rejected",
        description: `"${review.title}" has been ${action}`,
      });

      setExpandedId(null);
      loadReviews();
    } catch (error) {
      console.error("Error processing review:", error);
      toast({ title: "Error", description: "Failed to process review", variant: "destructive" });
    } finally {
      setProcessingId(null);
    }
  };

  const filteredReviews = reviews.filter((r) => {
    if (domainFilter !== "all" && r.domain !== domainFilter) return false;
    if (typeFilter !== "all" && r.decision_type !== typeFilter) return false;
    return true;
  });

  const pendingReviews = filteredReviews.filter((r) => r.status === "pending");
  const completedReviews = filteredReviews.filter((r) => r.status !== "pending");
  const reviewIds = useMemo(() => new Set(reviews.map((r) => r.id)), [reviews]);

  useEffect(() => {
    if (!requestedReviewId) return;
    if (!reviewIds.has(requestedReviewId)) return;
    setExpandedId(requestedReviewId);
  }, [requestedReviewId, reviewIds]);
  const domains = [...new Set(reviews.map((r) => r.domain))];
  const types = [...new Set(reviews.map((r) => r.decision_type))];

  const renderConfidenceBar = (score: number | null) => {
    if (score === null) return null;
    const pct = Math.round(score * 100);
    const color = pct >= 80 ? "text-green-500" : pct >= 50 ? "text-amber-500" : "text-red-500";
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className={`font-medium ${color}`}>{pct}%</span>
        <Progress value={pct} className="h-1.5 w-20" />
        <span className="text-muted-foreground">confidence</span>
      </div>
    );
  };

  const renderReviewCard = (review: DecisionReview, showActions: boolean) => {
    const isExpanded = expandedId === review.id;
    const statusCfg = STATUS_CONFIG[review.status] ?? STATUS_CONFIG.pending;
    const StatusIcon = statusCfg.icon;

    return (
      <div
        key={review.id}
        className="border border-border/50 rounded-lg bg-card/50 hover:bg-card/80 transition-colors"
      >
        <div
          className="flex items-start justify-between p-4 cursor-pointer"
          onClick={() => setExpandedId(isExpanded ? null : review.id)}
        >
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className="p-2 rounded-lg bg-primary/10 mt-0.5">
              <Brain className="h-4 w-4 text-primary" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-medium text-sm truncate">{review.title}</p>
                <Badge variant="outline" className="text-[10px] capitalize">{review.domain}</Badge>
                <Badge variant="outline" className="text-[10px]">
                  {DECISION_TYPE_LABELS[review.decision_type] ?? review.decision_type}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                {review.pod_model_name} • {new Date(review.created_at).toLocaleDateString()}
              </p>
              {review.confidence_score !== null && renderConfidenceBar(review.confidence_score)}
            </div>
          </div>
          <div className="flex items-center gap-2 ml-2">
            <Badge variant={statusCfg.variant} className="text-xs gap-1">
              <StatusIcon className="h-3 w-3" />
              {statusCfg.label}
            </Badge>
            {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
          </div>
        </div>

        {isExpanded && (
          <div className="px-4 pb-4 space-y-3 border-t border-border/30 pt-3">
            {review.summary && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Summary</p>
                <p className="text-sm">{review.summary}</p>
              </div>
            )}
            {review.ai_recommendation && (
              <div className="p-3 rounded-lg bg-primary/5 border border-primary/10">
                <p className="text-xs font-medium text-primary mb-1 flex items-center gap-1">
                  <Brain className="h-3 w-3" /> AI Recommendation
                </p>
                <p className="text-sm">{review.ai_recommendation}</p>
              </div>
            )}
            {review.threshold_exceeded && (
              <div className="flex items-center gap-1.5 text-xs text-amber-600">
                <AlertTriangle className="h-3.5 w-3.5" />
                <span>Confidence threshold exceeded — manual review required</span>
              </div>
            )}

            {review.reviewer_notes && review.status !== "pending" && (
              <div>
                <p className="text-xs font-medium text-muted-foreground mb-1">Reviewer Notes</p>
                <p className="text-sm">{review.reviewer_notes}</p>
              </div>
            )}

            {showActions && isAdmin && review.status === "pending" && (
              <div className="space-y-3 pt-2">
                <Textarea
                  placeholder="Add reviewer notes (optional)..."
                  value={reviewerNotes[review.id] ?? ""}
                  onChange={(e) =>
                    setReviewerNotes((prev) => ({ ...prev, [review.id]: e.target.value }))
                  }
                  className="text-sm"
                  rows={2}
                />
                <div className="flex items-center gap-2 justify-end">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => { e.stopPropagation(); handleAction(review, "rejected"); }}
                    disabled={processingId === review.id}
                    className="text-destructive hover:text-destructive"
                  >
                    <XCircle className="h-3.5 w-3.5 mr-1" />
                    Reject
                  </Button>
                  <Button
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); handleAction(review, "approved"); }}
                    disabled={processingId === review.id}
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                    Approve
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="p-6">
        <Card className="border-border/50 bg-background/95 backdrop-blur">
          <CardContent className="flex items-center justify-center py-12">
            <p className="text-muted-foreground">Loading review queue...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Decision Review Queue</h1>
        <p className="text-muted-foreground mt-1">
          Human-in-the-loop review for AI-generated decisions across all pods
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Filter className="h-4 w-4" />
          <span>Filter:</span>
        </div>
        <Select value={domainFilter} onValueChange={setDomainFilter}>
          <SelectTrigger className="w-[140px] h-8 text-xs">
            <SelectValue placeholder="Domain" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Domains</SelectItem>
            {domains.map((d) => (
              <SelectItem key={d} value={d} className="capitalize">{d}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[180px] h-8 text-xs">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {types.map((t) => (
              <SelectItem key={t} value={t}>{DECISION_TYPE_LABELS[t] ?? t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {pendingReviews.length > 0 && (
          <Badge className="bg-amber-500/90 text-white ml-auto">
            {pendingReviews.length} pending
          </Badge>
        )}
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "pending" | "completed")}>
        <TabsList>
          <TabsTrigger value="pending" className="gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            Pending ({pendingReviews.length})
          </TabsTrigger>
          <TabsTrigger value="completed" className="gap-1.5">
            <Eye className="h-3.5 w-3.5" />
            Completed ({completedReviews.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pending" className="mt-4">
          {pendingReviews.length === 0 ? (
            <Card className="border-border/50 bg-background/95 backdrop-blur">
              <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <CheckCircle2 className="h-10 w-10 mb-3 text-primary/40" />
                <p className="font-medium">All caught up!</p>
                <p className="text-sm">No pending decisions to review</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {pendingReviews.map((review) => renderReviewCard(review, isAdmin))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="completed" className="mt-4">
          {completedReviews.length === 0 ? (
            <Card className="border-border/50 bg-background/95 backdrop-blur">
              <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Eye className="h-10 w-10 mb-3 text-primary/40" />
                <p className="text-sm">No completed reviews yet</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {completedReviews.map((review) => renderReviewCard(review, false))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
