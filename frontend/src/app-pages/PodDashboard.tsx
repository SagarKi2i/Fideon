import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { 
  Brain, 
  Activity, 
  MessageSquare, 
  Clock, 
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  FileDown,
  FileText,
  Scale,
  ClipboardList,
  Search,
  Power,
  Building2,
  RefreshCw,
  XCircle,
  Inbox,
  Gavel,
  DollarSign,
  AlertTriangle,
  User
} from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { useToast } from "@/hooks/use-toast";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface ActivatedPod {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
  activated_at: string | null;
}

// Pod-specific mock data
const documentRetrievalLogs = [
  { date: "2026-02-08", carrier: "Travelers", documents: 12, synced: 12, errors: 0, status: "success" },
  { date: "2026-02-07", carrier: "Chubb", documents: 8, synced: 8, errors: 0, status: "success" },
  { date: "2026-02-07", carrier: "Hartford", documents: 15, synced: 14, errors: 1, status: "warning" },
  { date: "2026-02-06", carrier: "Liberty Mutual", documents: 6, synced: 6, errors: 0, status: "success" },
  { date: "2026-02-06", carrier: "Progressive", documents: 10, synced: 8, errors: 2, status: "error" },
  { date: "2026-02-05", carrier: "Nationwide", documents: 4, synced: 4, errors: 0, status: "success" },
];

const quoteGenerationLogs = [
  { date: "2026-02-08", type: "Commercial Auto", carrier: "Travelers", premium: "$12,450", status: "completed" },
  { date: "2026-02-08", type: "BOP", carrier: "Hartford", premium: "$8,200", status: "completed" },
  { date: "2026-02-07", type: "Workers Comp", carrier: "Liberty Mutual", premium: "$15,800", status: "pending" },
  { date: "2026-02-07", type: "General Liability", carrier: "Chubb", premium: "$6,500", status: "completed" },
  { date: "2026-02-06", type: "Property", carrier: "Nationwide", premium: "$22,100", status: "completed" },
];

const policyComparisonLogs = [
  { date: "2026-02-08", policies: "Travelers vs Chubb", coverage: "Commercial Auto", differences: 12, recommendation: "Travelers" },
  { date: "2026-02-07", policies: "Hartford vs Liberty", coverage: "BOP", differences: 8, recommendation: "Hartford" },
  { date: "2026-02-07", policies: "Progressive vs Nationwide", coverage: "Property", differences: 15, recommendation: "Nationwide" },
  { date: "2026-02-06", policies: "Chubb vs AIG", coverage: "Umbrella", differences: 5, recommendation: "AIG" },
];

const claimsFnolLogs = [
  { date: "2026-02-08", claimId: "CLM-2026-1234", type: "Auto Collision", carrier: "Travelers", status: "submitted" },
  { date: "2026-02-07", claimId: "CLM-2026-1233", type: "Property Damage", carrier: "Hartford", status: "processing" },
  { date: "2026-02-07", claimId: "CLM-2026-1232", type: "Liability", carrier: "Chubb", status: "submitted" },
  { date: "2026-02-06", claimId: "CLM-2026-1231", type: "Workers Comp", carrier: "Liberty Mutual", status: "completed" },
];

const multiDocumentLogs = [
  { date: "2026-02-08", documents: 5, analysis: "Coverage Gap Analysis", findings: 8, status: "completed" },
  { date: "2026-02-07", documents: 3, analysis: "Policy Consolidation", findings: 4, status: "completed" },
  { date: "2026-02-06", documents: 8, analysis: "Risk Assessment", findings: 12, status: "completed" },
  { date: "2026-02-05", documents: 2, analysis: "Renewal Comparison", findings: 6, status: "completed" },
];

// Carrier-specific mock data
const submissionIntakeLogs = [
  { date: "2026-02-08", submissionId: "SUB-2026-0045", insured: "Tech Solutions Corp", lob: "Commercial Package", appetiteMatch: 87, status: "triaged", underwriter: "Sarah Chen" },
  { date: "2026-02-08", submissionId: "SUB-2026-0044", insured: "Metro Retail Group", lob: "Property", appetiteMatch: 92, status: "assigned", underwriter: "Mike Johnson" },
  { date: "2026-02-07", submissionId: "SUB-2026-0043", insured: "Coastal Dining LLC", lob: "General Liability", appetiteMatch: 45, status: "declined", underwriter: null },
  { date: "2026-02-07", submissionId: "SUB-2026-0042", insured: "Summit Construction", lob: "Workers Comp", appetiteMatch: 78, status: "quoted", underwriter: "Lisa Park" },
  { date: "2026-02-06", submissionId: "SUB-2026-0041", insured: "DataFlow Systems", lob: "Cyber", appetiteMatch: 95, status: "quoted", underwriter: "Sarah Chen" },
];

const claimsAdjudicationLogs = [
  { date: "2026-02-08", claimId: "ADJ-2026-0089", claimant: "Johnson Manufacturing", type: "Property Damage", reserve: "$125,000", fraudScore: "Low", status: "investigating" },
  { date: "2026-02-08", claimId: "ADJ-2026-0088", claimant: "City Transport Inc", type: "Auto Liability", reserve: "$45,000", fraudScore: "Medium", status: "approved" },
  { date: "2026-02-07", claimId: "ADJ-2026-0087", claimant: "Retail Holdings", type: "Slip & Fall", reserve: "$78,000", fraudScore: "Low", status: "approved" },
  { date: "2026-02-07", claimId: "ADJ-2026-0086", claimant: "Quick Delivery LLC", type: "Workers Comp", reserve: "$32,000", fraudScore: "High", status: "investigating" },
  { date: "2026-02-06", claimId: "ADJ-2026-0085", claimant: "Harbor Logistics", type: "Cargo Damage", reserve: "$156,000", fraudScore: "Low", status: "paid" },
];

const getPodIcon = (modelId: string) => {
  switch (modelId) {
    case "document-retrieval":
    case "document-search":
      return FileDown;
    case "quote-generation":
      return FileText;
    case "policy-comparison":
      return Scale;
    case "claims-fnol":
      return ClipboardList;
    case "multi-document":
      return Search;
    case "carrier-submission-intake":
      return Inbox;
    case "carrier-claims-adjudication":
      return Gavel;
    default:
      return Brain;
  }
};

const getPodStats = (modelId: string) => {
  switch (modelId) {
    case "document-retrieval":
    case "document-search":
      return { total: 55, success: 52, errors: 3, label: "Documents Retrieved" };
    case "quote-generation":
      return { total: 156, success: 142, errors: 14, label: "Quotes Generated" };
    case "policy-comparison":
      return { total: 89, success: 89, errors: 0, label: "Comparisons Made" };
    case "claims-fnol":
      return { total: 234, success: 228, errors: 6, label: "Claims Processed" };
    case "multi-document":
      return { total: 67, success: 65, errors: 2, label: "Analyses Completed" };
    case "carrier-submission-intake":
      return { total: 127, success: 98, errors: 5, label: "Submissions Triaged" };
    case "carrier-claims-adjudication":
      return { total: 89, success: 82, errors: 3, label: "Claims Adjudicated" };
    default:
      return { total: 0, success: 0, errors: 0, label: "Operations" };
  }
};

function relativeTime(isoDate: string | null): string {
  if (!isoDate) return "Never";
  const diff = Date.now() - new Date(isoDate).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function PodSpecificTable({ modelId, acordRuns }: Readonly<{ modelId: string; acordRuns?: any[] }>) {
  const statusClassForDocRetrieval = (status: string): string => {
    if (status === "success") return "text-green-600 border-green-600";
    if (status === "warning") return "text-amber-600 border-amber-600";
    return "text-destructive border-destructive";
  };

  const statusClassForQuote = (status: string): string =>
    status === "completed" ? "text-green-600 border-green-600" : "text-amber-600 border-amber-600";

  const statusClassForClaims = (status: string): string => {
    if (status === "completed") return "text-green-600 border-green-600";
    if (status === "submitted") return "text-blue-600 border-blue-600";
    return "text-amber-600 border-amber-600";
  };

  const appetiteClass = (score: number): string => {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-amber-500";
    return "bg-red-500";
  };

  const appetiteTextClass = (score: number): string => {
    if (score >= 80) return "text-green-600";
    if (score >= 60) return "text-amber-600";
    return "text-red-600";
  };

  const submissionStatusClass = (status: string): string => {
    if (status === "quoted") return "text-green-600 border-green-600";
    if (status === "assigned") return "text-blue-600 border-blue-600";
    if (status === "triaged") return "text-amber-600 border-amber-600";
    return "text-destructive border-destructive";
  };

  const fraudBadgeClass = (score: string): string => {
    if (score === "Low") return "text-green-600 border-green-600 bg-green-500/10";
    if (score === "Medium") return "text-amber-600 border-amber-600 bg-amber-500/10";
    return "text-red-600 border-red-600 bg-red-500/10";
  };

  const adjudicationStatusClass = (status: string): string => {
    if (status === "paid") return "text-green-600 border-green-600";
    if (status === "approved") return "text-blue-600 border-blue-600";
    return "text-amber-600 border-amber-600";
  };

  switch (modelId) {
    case "document-retrieval":
    case "document-search":
      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Carrier</TableHead>
              <TableHead>Documents</TableHead>
              <TableHead>Synced</TableHead>
              <TableHead>Errors</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {documentRetrievalLogs.map((log: any) => (
              <TableRow key={`${log.date}-${log.carrier}-${log.documents}`}>
                <TableCell className="font-medium">{log.date}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    {log.carrier}
                  </div>
                </TableCell>
                <TableCell>{log.documents}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <RefreshCw className="h-3 w-3 text-muted-foreground" />
                    {log.synced}
                  </div>
                </TableCell>
                <TableCell>{log.errors}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={statusClassForDocRetrieval(log.status)}>
                    {log.status === "success" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                    {log.status === "warning" && <AlertCircle className="h-3 w-3 mr-1" />}
                    {log.status === "error" && <XCircle className="h-3 w-3 mr-1" />}
                    {log.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );

    case "quote-generation":
      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Coverage Type</TableHead>
              <TableHead>Carrier</TableHead>
              <TableHead>Premium</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {quoteGenerationLogs.map((log: any) => (
              <TableRow key={`${log.date}-${log.type}-${log.carrier}`}>
                <TableCell className="font-medium">{log.date}</TableCell>
                <TableCell>{log.type}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    {log.carrier}
                  </div>
                </TableCell>
                <TableCell className="font-semibold">{log.premium}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={statusClassForQuote(log.status)}>
                    {log.status === "completed" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                    {log.status === "pending" && <Clock className="h-3 w-3 mr-1" />}
                    {log.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );

    case "policy-comparison":
      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Policies Compared</TableHead>
              <TableHead>Coverage</TableHead>
              <TableHead>Differences</TableHead>
              <TableHead>Recommendation</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {policyComparisonLogs.map((log: any) => (
              <TableRow key={`${log.date}-${log.policies}`}>
                <TableCell className="font-medium">{log.date}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Scale className="h-4 w-4 text-muted-foreground" />
                    {log.policies}
                  </div>
                </TableCell>
                <TableCell>{log.coverage}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{log.differences} items</Badge>
                </TableCell>
                <TableCell className="font-semibold text-primary">{log.recommendation}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );

    case "claims-fnol":
      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Claim ID</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Carrier</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {claimsFnolLogs.map((log: any) => (
              <TableRow key={`${log.date}-${log.claimId}`}>
                <TableCell className="font-medium">{log.date}</TableCell>
                <TableCell>
                  <code className="bg-muted px-2 py-1 rounded text-sm">{log.claimId}</code>
                </TableCell>
                <TableCell>{log.type}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    {log.carrier}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={statusClassForClaims(log.status)}>
                    {log.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );

    case "multi-document":
      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Documents</TableHead>
              <TableHead>Analysis Type</TableHead>
              <TableHead>Findings</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {multiDocumentLogs.map((log: any) => (
              <TableRow key={`${log.date}-${log.analysis}`}>
                <TableCell className="font-medium">{log.date}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    {log.documents} files
                  </div>
                </TableCell>
                <TableCell>{log.analysis}</TableCell>
                <TableCell>
                  <Badge variant="secondary">{log.findings} findings</Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-green-600 border-green-600">
                    <CheckCircle2 className="h-3 w-3 mr-1" />
                    {log.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );

    case "carrier-submission-intake":
      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Submission ID</TableHead>
              <TableHead>Insured</TableHead>
              <TableHead>Line of Business</TableHead>
              <TableHead>Appetite Match</TableHead>
              <TableHead>Underwriter</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {submissionIntakeLogs.map((log: any) => (
              <TableRow key={`${log.date}-${log.submissionId}`}>
                <TableCell className="font-medium">{log.date}</TableCell>
                <TableCell>
                  <code className="bg-muted px-2 py-1 rounded text-sm">{log.submissionId}</code>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    {log.insured}
                  </div>
                </TableCell>
                <TableCell>{log.lob}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${appetiteClass(log.appetiteMatch)}`} />
                    <span className={appetiteTextClass(log.appetiteMatch)}>{log.appetiteMatch}%</span>
                  </div>
                </TableCell>
                <TableCell>
                  {log.underwriter ? (
                    <div className="flex items-center gap-2">
                      <User className="h-3 w-3 text-muted-foreground" />
                      {log.underwriter}
                    </div>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={submissionStatusClass(log.status)}>
                    {log.status === "quoted" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                    {log.status === "declined" && <XCircle className="h-3 w-3 mr-1" />}
                    {log.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );

    case "carrier-claims-adjudication":
      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Claim ID</TableHead>
              <TableHead>Claimant</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Reserve</TableHead>
              <TableHead>Fraud Risk</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {claimsAdjudicationLogs.map((log: any) => (
              <TableRow key={`${log.date}-${log.claimId}`}>
                <TableCell className="font-medium">{log.date}</TableCell>
                <TableCell>
                  <code className="bg-muted px-2 py-1 rounded text-sm">{log.claimId}</code>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                    {log.claimant}
                  </div>
                </TableCell>
                <TableCell>{log.type}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <DollarSign className="h-3 w-3 text-muted-foreground" />
                    <span className="font-semibold">{log.reserve}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={fraudBadgeClass(log.fraudScore)}>
                    {log.fraudScore === "High" && <AlertTriangle className="h-3 w-3 mr-1" />}
                    {log.fraudScore}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={adjudicationStatusClass(log.status)}>
                    {log.status === "paid" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                    {log.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );

    case "acord-parser": {
      const runs = acordRuns ?? [];
      if (runs.length === 0) {
        return (
          <div className="text-center py-8 text-muted-foreground">
            <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No extractions yet — upload a PDF in the Playground to get started.</p>
          </div>
        );
      }
      const statusClass = (s: string) => {
        if (s === "approved") return "text-green-600 border-green-600";
        if (s === "submitted") return "text-blue-600 border-blue-600";
        if (s === "needs_admin_review") return "text-amber-600 border-amber-600";
        return "text-muted-foreground border-border";
      };
      const statusLabel: Record<string, string> = {
        draft: "Extracted",
        submitted: "Correction Saved",
        needs_admin_review: "Admin Review",
        approved: "Trained",
      };
      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Filename</TableHead>
              <TableHead>Form Type</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run: any) => (
              <TableRow key={run.id}>
                <TableCell className="font-medium text-muted-foreground">
                  {new Date(run.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="truncate max-w-[220px]">{run.source_filename || "—"}</span>
                  </div>
                </TableCell>
                <TableCell>ACORD {run.form_type_detected || "—"}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={statusClass(run.status)}>
                    {run.status === "approved" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                    {run.status === "submitted" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                    {run.status === "needs_admin_review" && <AlertCircle className="h-3 w-3 mr-1" />}
                    {statusLabel[run.status] ?? run.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );
    }

    default:
      return (
        <div className="text-center py-8 text-muted-foreground">
          <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p>No activity data available for this pod</p>
        </div>
      );
  }
}

export default function PodDashboard() {
  const { podId } = useParams<{ podId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [pod, setPod] = useState<ActivatedPod | null>(null);
  const [loading, setLoading] = useState(true);
  const [deactivating, setDeactivating] = useState(false);
  const [acordRuns, setAcordRuns] = useState<any[]>([]);
  const [acordStats, setAcordStats] = useState<{ total: number; lastActivity: string | null } | null>(null);

  useEffect(() => {
    loadPodData();
  }, [podId]);

  const loadAcordStats = async () => {
    const db = supabase as any;
    const { data } = await db
      .from("acord_extraction_runs")
      .select("id, source_filename, form_type_detected, status, created_at")
      .order("created_at", { ascending: false })
      .limit(100);
    if (data) {
      setAcordRuns(data);
      setAcordStats({ total: data.length, lastActivity: data[0]?.created_at ?? null });
    }
  };

  const loadPodData = async () => {
    if (!podId) {
      navigate("/my-models");
      return;
    }

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const user = session?.user;
      if (!user) {
        navigate("/auth");
        return;
      }

      const res = await fetch(
        apiUrl(`/api/v1/activated-models?model_id=${encodeURIComponent(podId)}`),
        { headers: { Authorization: `Bearer ${session.access_token}` } },
      );
      const payload = res.ok ? await res.json() : null;
      const rows: ActivatedPod[] = payload?.activated_models ?? [];
      const data = rows[0] ?? null;

      if (!data) {
        toast({
          title: "Pod not found",
          description: "This pod may have been deactivated",
          variant: "destructive"
        });
        navigate("/my-models");
        return;
      }

      setPod(data);
      if (data.model_id === "acord-parser") {
        loadAcordStats();
      }
    } catch (error) {
      console.error("Error loading pod:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeactivate = async () => {
    if (!pod) return;

    setDeactivating(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) throw new Error("Not authenticated");
      const res = await fetch(apiUrl(`/api/v1/activated-models/${encodeURIComponent(pod.id)}`), {
        method: "DELETE",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast({
        title: "Pod deactivated",
        description: `${pod.model_name} has been deactivated successfully`,
      });
      navigate("/my-models");
    } catch (error) {
      console.error("Error deactivating pod:", error);
      toast({
        title: "Error",
        description: "Failed to deactivate pod",
        variant: "destructive"
      });
    } finally {
      setDeactivating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Brain className="h-8 w-8 animate-pulse text-primary" />
      </div>
    );
  }

  if (!pod) {
    return null;
  }

  const PodIcon = getPodIcon(pod.model_id);
  const stats = getPodStats(pod.model_id);
  const isAcord = pod.model_id === "acord-parser";
  const displayTotal   = isAcord ? (acordStats?.total ?? 0) : stats.total;
  const displayErrors  = isAcord ? acordRuns.filter((r) => r.status === "draft").length : stats.errors;
  const displaySuccess = displayTotal > 0
    ? (((displayTotal - displayErrors) / displayTotal) * 100).toFixed(1) + "%"
    : "—";
  const displayLabel   = isAcord ? "PDFs Extracted" : stats.label;
  const displayLastActivity = isAcord
    ? relativeTime(acordStats?.lastActivity ?? null)
    : "—";

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate("/my-models")}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center">
            <PodIcon className="h-6 w-6 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
                {pod.model_name}
              </h1>
              <Badge variant="outline" className="text-green-600 border-green-600">
                <CheckCircle2 className="h-3 w-3 mr-1" />
                Active
              </Badge>
            </div>
            <p className="text-muted-foreground mt-1">
              {pod.domain.charAt(0).toUpperCase() + pod.domain.slice(1)} • Activated {new Date(pod.activated_at || "").toLocaleDateString()}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button 
            onClick={() => navigate(`/playground?model=${encodeURIComponent(pod.model_id)}`)}
            className="bg-gradient-primary"
          >
            <MessageSquare className="h-4 w-4 mr-2" />
            Open in Playground
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" className="text-destructive border-destructive hover:bg-destructive/10">
                <Power className="h-4 w-4 mr-2" />
                Deactivate
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Deactivate Pod?</AlertDialogTitle>
                <AlertDialogDescription>
                  This will deactivate {pod.model_name}. You can reactivate it from the Marketplace at any time.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction 
                  onClick={handleDeactivate}
                  disabled={deactivating}
                  className="bg-destructive hover:bg-destructive/90"
                >
                  {deactivating ? "Deactivating..." : "Deactivate"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Key Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-card border-border">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{displayLabel}</p>
                <p className="text-2xl font-bold text-foreground">{displayTotal}</p>
              </div>
              <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                <PodIcon className="h-5 w-5 text-primary" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Success Rate</p>
                <p className="text-2xl font-bold text-foreground">{displaySuccess}</p>
              </div>
              <div className="h-10 w-10 rounded-full bg-green-500/10 flex items-center justify-center">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Corrections Pending</p>
                <p className="text-2xl font-bold text-foreground">{displayErrors}</p>
              </div>
              <div className="h-10 w-10 rounded-full bg-destructive/10 flex items-center justify-center">
                <XCircle className="h-5 w-5 text-destructive" />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Last Activity</p>
                <p className="text-2xl font-bold text-foreground">{displayLastActivity}</p>
              </div>
              <div className="h-10 w-10 rounded-full bg-accent/10 flex items-center justify-center">
                <Clock className="h-5 w-5 text-accent" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pod-Specific Activity Log */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-lg">Activity Log</CardTitle>
          <CardDescription>Recent operations for this pod</CardDescription>
        </CardHeader>
        <CardContent>
          <PodSpecificTable modelId={pod.model_id} acordRuns={acordRuns} />
        </CardContent>
      </Card>
    </div>
  );
}
