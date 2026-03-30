import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Loader2,
  Eye,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ShieldAlert,
  FileText,
  Pencil,
  Check,
  X,
  Clock,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  adminReviewPodRun,
  getJobByRunId,
  getJobEvalResults,
  getJobHistoryByRunId,
  getJobLogTail,
  getPodRunHealthCard,
  getPodRun,
} from "@/lib/podWorkflowApi";

const JOB_STATUS_META: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline"; spin?: boolean }> = {
  queued: { label: "Queued", variant: "secondary" },
  running: { label: "Running", variant: "default", spin: true },
  completed: { label: "Completed", variant: "default" },
  failed: { label: "Failed", variant: "destructive" },
};

export default function AdminPodReview() {
  const { podId, runId } = useParams<{ podId: string; runId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [run, setRun] = useState<any>(null);
  const [originalJsonText, setOriginalJsonText] = useState("");
  const [editedJsonText, setEditedJsonText] = useState("");
  const [notes, setNotes] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);

  const confidencePct = useMemo(() => {
    const c = Number(run?.overall_confidence ?? 0);
    return Math.round(c * 100);
  }, [run]);

  // Training job state
  const [trainingJob, setTrainingJob] = useState<any>(null);
  const [trainingHistory, setTrainingHistory] = useState<any[]>([]);
  const [evalResults, setEvalResults] = useState<any[]>([]);

  const [jobLogTail, setJobLogTail] = useState("");
  const [jobProgressPercent, setJobProgressPercent] = useState<number | null>(null);
  const [jobLogError, setJobLogError] = useState<string | null>(null);
  const [jobLoading, setJobLoading] = useState(false);
  const [healthCard, setHealthCard] = useState<any | null>(null);

  const load = useCallback(async () => {
    if (!podId || !runId) return;
    setLoading(true);
    try {
      const data = await getPodRun(podId, runId);
      setRun(data.run);
      const original = data.run?.original_extracted_json ?? data.run?.extracted_json ?? {};
      const edited = data.run?.edited_extracted_json ?? data.run?.extracted_json ?? {};
      setOriginalJsonText(JSON.stringify(original, null, 2));
      setEditedJsonText(JSON.stringify(edited, null, 2));
      setJsonError(null);
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "Failed to load run", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [podId, runId, toast]);

  const loadJob = useCallback(
    async (opts?: { silent?: boolean; selectedJobId?: string | null }) => {
      if (!podId || !runId) return;
      const silent = opts?.silent ?? false;
      if (!silent) setJobLoading(true);

      setEvalResults([]);
      try {
        const [latestResp, historyResp, healthResp] = await Promise.all([
          getJobByRunId(podId, runId),
          getJobHistoryByRunId(podId, runId, 50),
          getPodRunHealthCard(podId, runId),
        ]);
        setHealthCard(healthResp ?? null);

        const latest = latestResp.job || null;
        const historyJobs = historyResp.jobs || [];
        setTrainingHistory(historyJobs);

        const selectedFromHistory = opts?.selectedJobId
          ? (historyJobs || []).find(j => String(j.id) === String(opts?.selectedJobId)) || null
          : null;

        const job = selectedFromHistory || latest;
        setTrainingJob(job || null);

        if (!job?.id) {
          setJobLogTail("");
          setJobProgressPercent(null);
          setJobLogError(null);
          return;
        }

        setJobLogError(null);
        try {
          const logData = await getJobLogTail(podId, job.id, 250);
          setJobLogTail(logData.tail_text || "");
          setJobProgressPercent(logData.progress_percent ?? null);
        } catch (e: any) {
          setJobLogError(e?.message || "Failed to fetch job log tail.");
        }

        if (job?.status === "completed") {
          try {
            const evalData = await getJobEvalResults(podId, job.id);
            setEvalResults(evalData.eval_results || []);
          } catch {
            // Eval may not exist yet
          }
        }
      } catch {
        setTrainingJob(null);
        setHealthCard(null);
        setJobLogTail("");
        setJobProgressPercent(null);
        setJobLogError(null);
      } finally {
        if (!silent) setJobLoading(false);
      }
    },
    [podId, runId]
  );

  useEffect(() => {
    load();
    loadJob();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [podId, runId]);

  // Poll job log while running/queued
  useEffect(() => {
    if (!trainingJob || !podId) return;
    if (trainingJob.status !== "running" && trainingJob.status !== "queued") return;
    const id = window.setInterval(() => loadJob({ silent: true }), 5000);
    return () => window.clearInterval(id);
  }, [trainingJob?.status, trainingJob?.id, podId, loadJob]);

  const handleToggleEdit = () => {
    if (editMode) {
      setJsonError(null);
      setEditMode(false);
      return;
    }
    try {
      JSON.parse(editedJsonText);
      setJsonError(null);
      setEditMode(true);
    } catch {
      setJsonError("Invalid JSON — fix syntax before editing.");
    }
  };

  const act = async (decision: "approve" | "rework" | "reject") => {
    if (!podId || !runId) return;
    let corrected: any;
    try {
      corrected = JSON.parse(editedJsonText);
      setJsonError(null);
    } catch {
      setJsonError("Invalid JSON — fix before submitting.");
      toast({ title: "Invalid JSON", description: "Fix JSON syntax before submitting.", variant: "destructive" });
      return;
    }

    setSaving(true);
    try {
      const resp = await adminReviewPodRun(podId, runId, {
        decision,
        notes: notes || undefined,
        corrected_json: corrected,
      });
      toast({ title: "Saved", description: `Status: ${resp.status}` });
      navigate(`/admin/pod/${encodeURIComponent(podId)}/queue`);
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "Failed", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground p-6">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading run…
      </div>
    );
  }

  if (!podId || !runId || !run) return null;

  const state = run?.status || "draft";
  const hasPersistedEdits = Boolean(run?.has_edits);
  const showDualJson = hasPersistedEdits || editMode;
  const jobMeta = trainingJob ? JOB_STATUS_META[trainingJob.status] : null;
  const calibratedConfidencePct = Math.round(
    Number(healthCard?.confidence_evaluation?.calibrated_confidence ?? run?.overall_confidence ?? 0) * 100
  );
  const confidenceReasons: string[] = Array.isArray(healthCard?.confidence_evaluation?.reasons)
    ? healthCard.confidence_evaluation.reasons
    : [];
  const qualityGatePass = healthCard?.quality_gate_snapshot?.pass;
  const qualityGateChecks: any[] = Array.isArray(healthCard?.quality_gate_snapshot?.checks)
    ? healthCard.quality_gate_snapshot.checks
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Pod Admin Review</h1>
          <p className="text-muted-foreground mt-1">
            Pod: <span className="font-mono">{podId}</span> · Run #{runId.slice(0, 8)}
          </p>
        </div>
        <Button variant="outline" onClick={() => navigate(`/admin/pod/${encodeURIComponent(podId)}/queue`)}>
          Back to Queue
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldAlert className="h-5 w-5 text-amber-500" />
            Review Extracted JSON
          </CardTitle>
          <CardDescription className="mt-1">
            Confidence: <span className="font-semibold">{confidencePct}%</span> · Current status:{" "}
            <span className="font-semibold">{state}</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-xs">Notes (optional)</Label>
            <Input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Add admin notes…" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">{showDualJson ? "Edited JSON" : "Extracted JSON"}</Label>
              <Button size="sm" variant="outline" onClick={handleToggleEdit}>
                <Pencil className="h-3.5 w-3.5 mr-1.5" />
                {editMode ? "Done" : "Edit"}
              </Button>
            </div>
            {jsonError && <p className="text-sm text-destructive">{jsonError}</p>}
            {showDualJson ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-[11px] text-muted-foreground">Original Extracted JSON</Label>
                  <Textarea
                    value={originalJsonText}
                    className="min-h-[220px] font-mono text-xs"
                    disabled
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[11px] text-muted-foreground">New Editable JSON</Label>
                  <Textarea
                    value={editedJsonText}
                    onChange={e => setEditedJsonText(e.target.value)}
                    className="min-h-[220px] font-mono text-xs"
                    disabled={!editMode || saving}
                  />
                </div>
              </div>
            ) : (
              <Textarea
                value={editedJsonText}
                onChange={e => setEditedJsonText(e.target.value)}
                className="min-h-[220px] font-mono text-xs"
                disabled={!editMode || saving}
              />
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              onClick={() => act("approve")}
              disabled={saving}
              className="gap-1"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              Approve
            </Button>
            <Button
              onClick={() => act("rework")}
              disabled={saving}
              variant="secondary"
              className="gap-1"
            >
              <RefreshCw className="h-4 w-4" />
              Rework
            </Button>
            <Button
              onClick={() => act("reject")}
              disabled={saving}
              variant="destructive"
              className="gap-1"
            >
              <XCircle className="h-4 w-4" />
              Reject
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Run Health Card</CardTitle>
          <CardDescription>
            Combined confidence signal and quality gate snapshot for this run.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={calibratedConfidencePct >= 85 ? "default" : calibratedConfidencePct >= 60 ? "secondary" : "destructive"}>
              Calibrated confidence: {calibratedConfidencePct}%
            </Badge>
            <Badge variant={qualityGatePass === true ? "default" : qualityGatePass === false ? "destructive" : "outline"}>
              Quality gate: {qualityGatePass === true ? "PASS" : qualityGatePass === false ? "FAIL" : "N/A"}
            </Badge>
          </div>

          {confidenceReasons.length > 0 && (
            <div className="text-xs text-muted-foreground">
              Confidence reasons: {confidenceReasons.join(", ")}
            </div>
          )}

          {qualityGateChecks.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {qualityGateChecks.map((c: any, idx: number) => {
                const val = c?.value == null ? "N/A" : `${(Number(c.value) * 100).toFixed(1)}%`;
                const th = c?.threshold == null ? "N/A" : `${(Number(c.threshold) * 100).toFixed(1)}%`;
                return (
                  <div key={`${c?.metric || "metric"}-${idx}`} className="rounded border border-border/60 p-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(c?.metric || "metric").replace(/_/g, " ")}</span>
                      <Badge variant={c?.ok ? "default" : "destructive"}>{c?.ok ? "OK" : "NOT OK"}</Badge>
                    </div>
                    <div className="mt-1 text-muted-foreground font-mono">
                      {val} {c?.operator || ""} {th}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Quality gate metrics will appear after a completed training job with eval results.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <FileText className="h-5 w-5 text-primary" />
            Training Job
          </CardTitle>
          <CardDescription>
            {trainingJob ? (
              <>
                Job status:{" "}
                <Badge variant={jobMeta?.variant || "outline"} className="ml-2 text-xs">
                  {jobMeta?.spin ? <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin inline" /> : null}
                  {jobMeta?.label || trainingJob.status}
                </Badge>
              </>
            ) : (
              "No training job found for this run yet."
            )}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-3">
          {jobLoading && <p className="text-sm text-muted-foreground">Loading job details…</p>}
          {jobLogError && <p className="text-sm text-destructive">{jobLogError}</p>}
          {jobProgressPercent != null && (
            <Badge variant="outline" className="text-xs">
              {jobProgressPercent}% progress
            </Badge>
          )}
          <div className="rounded-lg border bg-muted/20 p-3">
            <pre className="text-xs whitespace-pre-wrap font-mono max-h-[260px] overflow-auto">
              {jobLogTail || "[No log tail yet]"}
            </pre>
          </div>

          {evalResults.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs">Eval Results</Label>
              <div className="rounded-lg border bg-card p-3">
                <pre className="text-xs whitespace-pre-wrap font-mono max-h-[220px] overflow-auto">
                  {JSON.stringify(evalResults, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

