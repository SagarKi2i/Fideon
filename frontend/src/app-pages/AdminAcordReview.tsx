import { getFormPresentation } from "@/lib/acordFormPresentation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Loader2, ArrowLeft, CheckCircle2, XCircle, ShieldAlert,
  Copy, Check, Pencil, Eye, RefreshCw, FileText, Cpu, BarChart3,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  adminReviewAcordRun,
  getAcordRun,
  previewTrainingJsonl,
  getJobByRunId,
  getJobEvalResults,
  getJobHistoryByRunId,
  getJobLogTail,
  getRunHealthCard,
} from "@/lib/acordWorkflowApi";

// ── Syntax highlighter (same as ACORDParserUI) ───────────────────────────────
function JsonHighlight({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  const re =
    /("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (match.index > cursor)
      parts.push(<span key={cursor} className="text-muted-foreground">{text.slice(cursor, match.index)}</span>);
    const token = match[0];
    let cls = "";
    if (/^"/.test(token)) cls = token.endsWith(":") ? "text-blue-400 font-medium" : "text-green-400";
    else if (token === "true" || token === "false") cls = "text-yellow-400";
    else if (token === "null") cls = "text-red-400";
    else cls = "text-orange-400";
    parts.push(<span key={match.index} className={cls}>{token}</span>);
    cursor = match.index + token.length;
  }
  if (cursor < text.length)
    parts.push(<span key={cursor} className="text-muted-foreground">{text.slice(cursor)}</span>);
  return <>{parts}</>;
}

// ── Training job status badge ────────────────────────────────────────────────
const JOB_STATUS_META: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline"; spin?: boolean }> = {
  queued:    { label: "Queued",    variant: "secondary" },
  running:   { label: "Running",   variant: "default",      spin: true },
  completed: { label: "Completed", variant: "default" },
  failed:    { label: "Failed",    variant: "destructive" },
};

export default function AdminAcordReview() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [run, setRun] = useState<any>(null);
  const [originalJsonText, setOriginalJsonText] = useState("");
  const [editedJsonText, setEditedJsonText] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [copied, setCopied] = useState(false);
  const [notes, setNotes] = useState("");

  // Training job state for this run
  const [trainingJob, setTrainingJob] = useState<any>(null);
  const [trainingHistory, setTrainingHistory] = useState<any[]>([]);
  const [jobLoading, setJobLoading] = useState(false);
  const [evalResults, setEvalResults] = useState<any[]>([]);
  const [jobLogTail, setJobLogTail] = useState<string>("");
  const [jobProgressPercent, setJobProgressPercent] = useState<number | null>(null);
  const [jobLogError, setJobLogError] = useState<string | null>(null);
  const [copiedTrainingLine, setCopiedTrainingLine] = useState(false);
  const [healthCard, setHealthCard] = useState<any | null>(null);

  const confidence = useMemo(() => {
    return Math.round(Number(run?.overall_confidence || 0) * 100);
  }, [run]);

  /** Canonical JSONL line from backend (`build_sft_label_json` + export metadata). */
  const [trainingPreview, setTrainingPreview] = useState<
    | { status: "idle" }
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ok"; pretty: string; jsonlLine: string }
  >({ status: "idle" });

  useEffect(() => {
    if (!runId || !run) {
      setTrainingPreview({ status: "idle" });
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(editedJsonText);
    } catch {
      setTrainingPreview({
        status: "error",
        message: "Invalid extracted JSON — fix it above to preview the training record.",
      });
      return;
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      setTrainingPreview({ status: "error", message: "Extracted JSON must be an object." });
      return;
    }
    setTrainingPreview({ status: "loading" });
    const t = window.setTimeout(() => {
      previewTrainingJsonl(runId, {
        extracted_json: parsed as Record<string, unknown>,
        raw_text: String(run.raw_text ?? ""),
        source_filename: run.source_filename ?? null,
      })
        .then((res) => {
          const rec = res.record as Record<string, unknown>;
          const pretty = JSON.stringify(rec, null, 2);
          const jsonlLine = JSON.stringify(rec);
          setTrainingPreview({ status: "ok", pretty, jsonlLine });
        })
        .catch((e: Error) => {
          setTrainingPreview({
            status: "error",
            message: e?.message || "Could not load training preview from server.",
          });
        });
    }, 400);
    return () => window.clearTimeout(t);
  }, [runId, run, editedJsonText]);

  const handleCopyTrainingJsonl = useCallback(() => {
    if (trainingPreview.status !== "ok") return;
    navigator.clipboard.writeText(trainingPreview.jsonlLine).then(() => {
      setCopiedTrainingLine(true);
      setTimeout(() => setCopiedTrainingLine(false), 2000);
    });
  }, [trainingPreview]);

  const load = async () => {
    if (!runId) return;
    setLoading(true);
    try {
      const data = await getAcordRun(runId);
      const r = data.run;
      setRun(r);
      const original = r?.original_extracted_json ?? r?.extracted_json ?? {};
      const edited = r?.edited_extracted_json ?? r?.extracted_json ?? {};
      setOriginalJsonText(JSON.stringify(original, null, 2));
      setEditedJsonText(JSON.stringify(edited, null, 2));
    } catch (e: any) {
      toast({ title: "Error", description: e.message || "Failed to load run", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const loadJob = async (opts?: { silent?: boolean; selectedJobId?: string | null }) => {
    if (!runId) return;
    const silent = opts?.silent ?? false;
    const selectedJobId = opts?.selectedJobId ?? null;
    if (!silent) setJobLoading(true);
    setEvalResults([]);
    try {
      const [latestResp, historyResp, healthResp] = await Promise.all([
        getJobByRunId(runId),
        getJobHistoryByRunId(runId, 50),
        getRunHealthCard(runId),
      ]);
      setHealthCard(healthResp ?? null);
      setTrainingHistory(historyResp.jobs || []);
      const latest = latestResp.job || null;

      const selectedFromHistory = selectedJobId
        ? (historyResp.jobs || []).find((j: any) => String(j.id) === String(selectedJobId)) || null
        : null;
      const job = selectedFromHistory || latest;
      setTrainingJob(job || null);

      // Do not clear log/progress before fetch — that caused flicker on each poll (empty → refilled).
      if (!job?.id) {
        setJobLogTail("");
        setJobProgressPercent(null);
        setJobLogError(null);
      } else {
        setJobLogError(null);
        try {
          const logData = await getJobLogTail(job.id, 250);
          setJobLogTail(logData.tail_text || "");
          setJobProgressPercent(logData.progress_percent ?? null);
        } catch (e: any) {
          setJobLogError(e?.message || "Failed to fetch job log tail.");
          // Keep previous tail / progress on transient errors
        }
      }

      if (job?.id && job?.status === "completed") {
        try {
          const evalData = await getJobEvalResults(job.id);
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
  };

  useEffect(() => { load(); loadJob(); }, [runId]);

  // While running, poll status+log periodically.
  useEffect(() => {
    if (!trainingJob || (trainingJob.status !== "running" && trainingJob.status !== "queued")) return;
    const id = window.setInterval(() => {
      loadJob({ silent: true, selectedJobId: trainingJob?.id || null });
    }, 5000);
    return () => window.clearInterval(id);
  }, [trainingJob?.status, trainingJob?.id, runId]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(editedJsonText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [editedJsonText]);

  const handleToggleEdit = () => {
    if (editMode) {
      try {
        JSON.parse(editedJsonText);
        setJsonError(null);
      } catch {
        setJsonError("Invalid JSON — fix syntax before switching to preview.");
        return;
      }
    }
    setEditMode(v => !v);
  };

  const act = async (decision: "approve" | "rework" | "reject") => {
    if (!runId) return;
    let corrected: any;
    try {
      corrected = JSON.parse(editedJsonText);
      setJsonError(null);
    } catch {
      setJsonError("Invalid JSON — fix before submitting.");
      return;
    }
    setSaving(true);
    try {
      const resp = await adminReviewAcordRun(runId, {
        decision,
        notes: notes || undefined,
        corrected_json: corrected,
      });
      toast({ title: "Saved", description: `Status: ${resp.status}` });
      if (decision === "approve") {
        // Give the job a moment to be created then refresh
        setTimeout(() => loadJob(), 1500);
      } else {
        navigate("/admin/acord-queue");
      }
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

  if (!runId || !run) {
    return (
      <div className="space-y-4 p-6">
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back
        </Button>
        <div className="text-sm text-muted-foreground">Run not found.</div>
      </div>
    );
  }

  const jobMeta = trainingJob ? (JOB_STATUS_META[trainingJob.status] ?? JOB_STATUS_META.queued) : null;
  const hasPersistedEdits = Boolean(run?.has_edits);
  const showDualJson = hasPersistedEdits || editMode;

  const selectHistoryJob = (jobId: string) => {
    loadJob({ selectedJobId: jobId });
  };

  const calibratedConfidencePct = Math.round(
    Number(healthCard?.confidence_evaluation?.calibrated_confidence ?? run?.overall_confidence ?? 0) * 100,
  );
  const confidenceReasons: string[] = Array.isArray(healthCard?.confidence_evaluation?.reasons)
    ? healthCard.confidence_evaluation.reasons
    : [];
  const qualityGatePass = healthCard?.quality_gate_snapshot?.pass;
  const qualityGateChecks: any[] = Array.isArray(healthCard?.quality_gate_snapshot?.checks)
    ? healthCard.quality_gate_snapshot.checks
    : [];
  const trainingJobStatus = String(trainingJob?.status || "").toLowerCase();
  const isGateFinal = trainingJobStatus === "completed" || trainingJobStatus === "failed";
  const effectiveQualityGatePass = isGateFinal ? qualityGatePass : null;

  return (
    <div className="space-y-6 p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Button variant="outline" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeft className="h-4 w-4 mr-2" /> Back to Queue
        </Button>
        <div className="flex flex-col items-end gap-0.5">
          <div className="flex items-center gap-2">
          {run.form_type_detected && (
            <Badge variant="outline" className="text-primary border-primary/40">
              {getFormPresentation(run.form_type_detected).title}
            </Badge>
          )}
          <Badge variant={confidence >= 85 ? "default" : confidence >= 60 ? "secondary" : "destructive"}>
            {confidence}% confidence
          </Badge>
          <Badge variant="outline">Run {runId.slice(0, 8)}</Badge>
          </div>
          {run.form_type_detected && (
            <span className="text-[10px] text-muted-foreground max-w-[240px] text-right">
              {getFormPresentation(run.form_type_detected).subtitle}
            </span>
          )}
        </div>
      </div>

      {/* File metadata */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldAlert className="h-4 w-4 text-amber-500" />
            Admin Review
          </CardTitle>
          <CardDescription className="flex items-center gap-2">
            <FileText className="h-3.5 w-3.5" />
            {run.source_filename || "Unknown file"}
            <span className="text-muted-foreground/50">·</span>
            Status: <span className="font-medium capitalize">{run.status}</span>
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Training Job Status */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Cpu className="h-4 w-4 text-primary" />
            Fine-Tuning Job
            <Button variant="ghost" size="sm" className="h-6 w-6 p-0 ml-auto" onClick={() => loadJob()} disabled={jobLoading}>
              <RefreshCw className={`h-3 w-3 ${jobLoading ? "animate-spin" : ""}`} />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {trainingJob ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-sm flex-wrap">
                <Badge variant={jobMeta!.variant} className="gap-1">
                  {jobMeta!.spin && <Loader2 className="h-3 w-3 animate-spin" />}
                  {jobMeta!.label}
                </Badge>
                <span className="text-muted-foreground font-mono text-xs">{trainingJob.id?.slice(0, 8)}</span>

                {trainingJob.started_at && (
                  <span className="text-muted-foreground text-xs">
                    Started {new Date(trainingJob.started_at).toLocaleString()}
                  </span>
                )}
                {trainingJob.finished_at && (
                  <span className="text-muted-foreground text-xs">
                    · Finished {new Date(trainingJob.finished_at).toLocaleString()}
                  </span>
                )}

                {trainingJob.status === "queued" && trainingJob.created_at && (
                  <span className="text-muted-foreground text-xs">
                    Queued {new Date(trainingJob.created_at).toLocaleString()}
                  </span>
                )}
                {trainingJob.updated_at && (
                  <span className="text-muted-foreground text-xs">
                    · Updated {new Date(trainingJob.updated_at).toLocaleString()}
                  </span>
                )}

                {trainingJob.status === "running" && (
                  <Badge variant="outline" className="font-mono text-xs">
                    {jobProgressPercent == null ? "Progress: N/A" : `Progress: ${jobProgressPercent}%`}
                  </Badge>
                )}

                {trainingJob.error && (
                  <span className="text-destructive text-xs truncate max-w-xs" title={trainingJob.error}>
                    Error: {trainingJob.error}
                  </span>
                )}
              </div>

              {trainingJob.status === "running" && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Live progress</span>
                    <span className="font-mono">{jobProgressPercent == null ? "—" : `${jobProgressPercent}%`}</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all"
                      style={{ width: `${jobProgressPercent == null ? 0 : jobProgressPercent}%` }}
                    />
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-medium text-primary">Fine-tuning logs</p>
                  <p className="text-xs text-muted-foreground">
                    {jobLogTail ? "Latest tail:" : "No logs yet."}
                  </p>
                </div>
                {jobLogError && (
                  <p className="text-xs text-destructive">{jobLogError}</p>
                )}
                {jobLogTail ? (
                  <pre className="overflow-auto rounded-lg bg-[#0b1020] text-slate-100 border border-slate-700/60 p-3 text-xs leading-relaxed font-mono max-h-[260px] whitespace-pre-wrap">
                    {jobLogTail}
                  </pre>
                ) : (
                  <p className="text-xs text-muted-foreground">{trainingJob.status === "queued" ? "Waiting for job to start…" : "Log tail unavailable."}</p>
                )}
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              No training job yet — job is created automatically after approval.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Fine-Tuning History */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Fine-Tuning History</CardTitle>
          <CardDescription>
            Full run history for this ACORD file with status, logs, outputs, and eval metrics.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {trainingHistory.length === 0 ? (
            <p className="text-xs text-muted-foreground">No history yet. First approval will create the initial job.</p>
          ) : (
            <div className="space-y-2">
              {trainingHistory.map((j: any) => {
                const meta = JOB_STATUS_META[j.status] ?? JOB_STATUS_META.queued;
                const isSelected = String(trainingJob?.id || "") === String(j.id || "");
                return (
                  <button
                    key={j.id}
                    type="button"
                    onClick={() => selectHistoryJob(j.id)}
                    className={`w-full text-left rounded-lg border p-3 transition-colors ${isSelected ? "border-primary bg-primary/5" : "border-border/60 hover:bg-muted/40"}`}
                  >
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                      <div className="flex items-center gap-2">
                        <Badge variant={meta.variant} className="gap-1">
                          {meta.spin && <Loader2 className="h-3 w-3 animate-spin" />}
                          {meta.label}
                        </Badge>
                        <span className="font-mono text-xs text-muted-foreground">{String(j.id).slice(0, 8)}</span>
                        {isSelected && <Badge variant="outline" className="text-[10px]">Selected</Badge>}
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {j.created_at ? new Date(j.created_at).toLocaleString() : "—"}
                      </span>
                    </div>
                    <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-muted-foreground">
                      <span>Dataset: <span className="font-mono">{j.dataset_path || "—"}</span></span>
                      <span>Output: <span className="font-mono">{j.output_dir || "—"}</span></span>
                      <span>Log: <span className="font-mono">{j.log_path || "—"}</span></span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Confidence + Quality Gate Health Card */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Run Health Card</CardTitle>
          <CardDescription>
            Combined confidence signal and latest quality gate checks for this run.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={calibratedConfidencePct >= 85 ? "default" : calibratedConfidencePct >= 60 ? "secondary" : "destructive"}>
              Calibrated confidence: {calibratedConfidencePct}%
            </Badge>
            <Badge variant={effectiveQualityGatePass === true ? "default" : effectiveQualityGatePass === false ? "destructive" : "outline"}>
              Quality gate: {effectiveQualityGatePass === true ? "PASS" : effectiveQualityGatePass === false ? "FAIL" : "Pending"}
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
                const metricVerdict = isGateFinal ? (c?.ok ? "OK" : "NOT OK") : "PENDING";
                return (
                  <div key={`${c?.metric || "metric"}-${idx}`} className="rounded border border-border/60 p-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium">{String(c?.metric || "metric").replace(/_/g, " ")}</span>
                      <Badge variant={isGateFinal ? (c?.ok ? "default" : "destructive") : "outline"}>{metricVerdict}</Badge>
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
              Quality gate metrics will appear after a completed or failed training job with eval results.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Evaluation Metrics (visible when job completed and eval results exist) */}
      {evalResults.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary" />
              Evaluation Metrics
            </CardTitle>
            <CardDescription>Post-training eval: seen / paraphrased / out-of-scope</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
              {evalResults.map((er: any) => (
                <div key={er.eval_set} className="rounded-lg border border-border/60 p-3 space-y-1">
                  <div className="font-medium text-primary capitalize">{er.eval_set.replace(/_/g, " ")}</div>
                  {er.exact_match != null && (
                    <div className="flex justify-between text-muted-foreground">
                      <span>Exact Match</span>
                      <span className="font-mono">{(Number(er.exact_match) * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {er.soft_accuracy != null && (
                    <div className="flex justify-between text-muted-foreground">
                      <span>Soft Acc</span>
                      <span className="font-mono">{(Number(er.soft_accuracy) * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {er.semantic_sim != null && (
                    <div className="flex justify-between text-muted-foreground">
                      <span>Semantic Sim</span>
                      <span className="font-mono">{Number(er.semantic_sim).toFixed(2)}</span>
                    </div>
                  )}
                  {er.hallucination_rate != null && (
                    <div className="flex justify-between text-muted-foreground">
                      <span>Halluc Rate</span>
                      <span className="font-mono">{(Number(er.hallucination_rate) * 100).toFixed(1)}%</span>
                    </div>
                  )}
                  {er.refusal_rate != null && (
                    <div className="flex justify-between text-muted-foreground">
                      <span>Refusal</span>
                      <span className="font-mono">{(Number(er.refusal_rate) * 100).toFixed(1)}%</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Full JSON Editor */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center justify-between">
            <span>{showDualJson ? "Edited JSON" : "Extracted JSON"}</span>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={handleCopy} className="h-7 px-2 gap-1 text-xs">
                {copied ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copied" : "Copy"}
              </Button>
              <Button variant="ghost" size="sm" onClick={handleToggleEdit} className="h-7 px-2 gap-1 text-xs">
                {editMode ? <Eye className="h-3.5 w-3.5" /> : <Pencil className="h-3.5 w-3.5" />}
                {editMode ? "Preview" : "Edit"}
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {showDualJson ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-[11px] text-muted-foreground">Original Extracted JSON</Label>
                <pre className="overflow-auto rounded-lg bg-[#0d1117] border border-border p-4 text-xs leading-relaxed font-mono max-h-[520px]">
                  <code><JsonHighlight text={originalJsonText} /></code>
                </pre>
              </div>
              <div className="space-y-1">
                <Label className="text-[11px] text-muted-foreground">New Editable JSON</Label>
                {editMode ? (
                  <Textarea
                    value={editedJsonText}
                    onChange={e => setEditedJsonText(e.target.value)}
                    rows={24}
                    className="font-mono text-xs bg-[#0d1117] text-[#c9d1d9] border-border rounded-lg resize-y"
                    spellCheck={false}
                  />
                ) : (
                  <pre className="overflow-auto rounded-lg bg-[#0d1117] border border-border p-4 text-xs leading-relaxed font-mono max-h-[520px]">
                    <code><JsonHighlight text={editedJsonText} /></code>
                  </pre>
                )}
              </div>
            </div>
          ) : (
            <pre className="overflow-auto rounded-lg bg-[#0d1117] border border-border p-4 text-xs leading-relaxed font-mono max-h-[520px]">
              <code><JsonHighlight text={editedJsonText} /></code>
            </pre>
          )}
          {jsonError && (
            <div className="text-xs text-destructive flex items-center gap-1">
              <XCircle className="h-3.5 w-3.5 flex-shrink-0" /> {jsonError}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Fine-tuning JSONL preview (same schema as export_approved_acord_dataset before Approve & Train) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center justify-between gap-2">
            <span className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              Fine-tuning record preview
            </span>
            {trainingPreview.status === "ok" && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopyTrainingJsonl}
                className="h-7 px-2 gap-1 text-xs shrink-0"
              >
                {copiedTrainingLine ? (
                  <Check className="h-3.5 w-3.5 text-green-500" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                {copiedTrainingLine ? "Copied JSONL" : "Copy JSONL line"}
              </Button>
            )}
          </CardTitle>
          <CardDescription>
            Built on the server with{" "}
            <span className="font-mono text-xs">build_sft_label_json</span> — same JSONL row as{" "}
            <span className="font-mono text-xs">fine_tuning/export_approved_acord_dataset.py</span>{" "}
            (six-field output, no confidence in metadata).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!run || !runId ? (
            <p className="text-sm text-muted-foreground">Open a run to see the training JSONL preview.</p>
          ) : trainingPreview.status === "error" ? (
            <p className="text-sm text-muted-foreground flex items-start gap-2">
              <XCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              {trainingPreview.message}
            </p>
          ) : trainingPreview.status === "ok" ? (
            <pre className="overflow-auto rounded-lg bg-[#0d1117] border border-border p-4 text-xs leading-relaxed font-mono max-h-[420px]">
              <code><JsonHighlight text={trainingPreview.pretty} /></code>
            </pre>
          ) : (
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin shrink-0" />
              Loading preview…
            </p>
          )}
        </CardContent>
      </Card>

      {/* Notes + Actions */}
      <Card>
        <CardContent className="pt-4 space-y-4">
          <div className="space-y-2">
            <Label className="text-sm">Admin Notes (optional)</Label>
            <Textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={3}
              placeholder="Reason for decision, corrections made, etc."
            />
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button
              variant="outline"
              className="text-destructive hover:text-destructive"
              disabled={saving}
              onClick={() => act("reject")}
            >
              <XCircle className="h-4 w-4 mr-2" /> Reject
            </Button>
            <Button variant="outline" disabled={saving} onClick={() => act("rework")}>
              Needs Rework
            </Button>
            <Button disabled={saving} onClick={() => act("approve")}>
              {saving
                ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                : <CheckCircle2 className="h-4 w-4 mr-2" />}
              Approve & Train
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
