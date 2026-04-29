import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import {
  Brain,
  MessageSquare,
  Cpu,
  Globe,
  ThumbsUp,
  Star,
  Play,
  RefreshCw,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Upload,
  Shield,
  Users,
  BarChart3,
  ChevronDown,
  ChevronUp,
  FileText,
} from "lucide-react";
import { isElectron } from "@/lib/ollama";
import { getStoredDeviceToken } from "@/lib/deviceApi";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { useNavigate } from "react-router-dom";
import {
  submitFeedback,
  getFeedback,
  getLocalFeedback,
  getLocalJobs,
  createTrainingJob,
  getTrainingJobs,
  getActiveRounds,
  getTrainingStats,
  submitGradient,
  type TrainingFeedback,
  type TrainingJob,
  type FederatedRound,
  type DeviceContribution,
  type TrainingStats,
} from "@/lib/trainingApi";
import { syncFeedbacksToRunpod, startRunpodFinetune, getRunpodJobStatus } from "@/lib/pdfUploadApi";
import {
  getAcordTrainingCount,
  getAcordTrainingSamples,
  getAcordSamplesForDisplay,
  markAcordSamplesUsed,
  type AcordSampleDisplay,
} from "@/lib/acordSupabaseApi";

export default function Training() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [isElectronApp, setIsElectronApp] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [webMode, setWebMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<TrainingStats | null>(null);
  const [feedback, setFeedback] = useState<TrainingFeedback[]>([]);
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [rounds, setRounds] = useState<FederatedRound[]>([]);
  const [contributions, setContributions] = useState<DeviceContribution[]>([]);
  const [activatedModels, setActivatedModels] = useState<{ model_id: string; model_name: string }[]>([]);

  // RunPod ACORD fine-tuning
  const [isFinetuning, setIsFinetuning] = useState(false);
  const [finetuneStatus, setFinetuneStatus] = useState<string | null>(null);

  // ACORD training sample count — read from Supabase (status='submitted' runs)
  const [localAcordCount, setLocalAcordCount] = useState<number>(0);

  // Expanded feedback item (click to view full details) — Recent Feedback tab
  const [expandedFeedbackId, setExpandedFeedbackId] = useState<string | null>(null);

  // ACORD sample list (shown when user clicks the sample count badge)
  const [showAcordSamples, setShowAcordSamples] = useState(false);
  const [acordSampleList, setAcordSampleList] = useState<AcordSampleDisplay[]>([]);
  const [acordSamplesLoading, setAcordSamplesLoading] = useState(false);
  const [expandedSampleId, setExpandedSampleId] = useState<string | null>(null);

  // Local Training tab — expanded item across all model lists (shared)
  const [expandedLocalItemId, setExpandedLocalItemId] = useState<string | null>(null);
  // Which non-ACORD model's feedback list is open (map modelId -> bool)
  const [showModelFeedback, setShowModelFeedback] = useState<Record<string, boolean>>({});

  // Live RunPod job polling
  const [activeRunpodJobId, setActiveRunpodJobId] = useState<string | null>(null);
  const [runpodJobStatus, setRunpodJobStatus] = useState<{
    status: string; phase?: string; version?: number; error?: string; eval_scores?: Record<string, any>;
  } | null>(null);

  // Mark training_feedback rows for ACORD model as used after a completed training run.
  // Also updates local-storage feedback so the badge reflects the new state without a reload.
  const markAcordFeedbackAsUsed = async () => {
    try {
      await supabase
        .from("training_feedback")
        .update({ is_used_for_training: true })
        .eq("model_id", "acord_form_understanding")
        .eq("is_used_for_training", false);
    } catch {
      // Supabase unavailable — update localStorage fallback
    }
    // Update localStorage items too so the badge flips instantly
    const local = JSON.parse(localStorage.getItem("local_training_feedback") || "[]");
    const updated = local.map((f: any) =>
      (f.model_id === "acord_form_understanding" && !f.is_used_for_training)
        ? { ...f, is_used_for_training: true }
        : f
    );
    localStorage.setItem("local_training_feedback", JSON.stringify(updated));
  };

  const refreshLocalAcordCount = async () => {
    try {
      const count = await getAcordTrainingCount();
      setLocalAcordCount(count);
    } catch {
      // Supabase unavailable — fall back to localStorage for legacy samples
      const count = getLocalFeedback().filter(
        (f) => f.model_id === "acord_form_understanding" && !f.is_used_for_training
      ).length;
      setLocalAcordCount(count);
    }
  };

  const handleToggleAcordSamples = async () => {
    if (showAcordSamples) {
      setShowAcordSamples(false);
      return;
    }
    setShowAcordSamples(true);
    setAcordSamplesLoading(true);
    try {
      const samples = await getAcordSamplesForDisplay();
      setAcordSampleList(samples);
    } catch {
      setAcordSampleList([]);
    } finally {
      setAcordSamplesLoading(false);
    }
  };

  // Feedback form
  const [feedbackModelId, setFeedbackModelId] = useState("");
  const [feedbackPrompt, setFeedbackPrompt] = useState("");
  const [feedbackOriginal, setFeedbackOriginal] = useState("");
  const [feedbackCorrected, setFeedbackCorrected] = useState("");
  const [feedbackRating, setFeedbackRating] = useState<number>(0);

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      const user = session?.user;
      if (!user) { navigate("/auth"); return; }

      try {
        const modelsRes = await fetch(apiUrl("/api/v1/activated-models"), {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });
        if (modelsRes.ok) {
          const modelsPayload = await modelsRes.json();
          setActivatedModels(modelsPayload.activated_models ?? []);
        }
      } catch {
        // Backend unreachable — continue with empty model list
      }

      const electron = await isElectron();
      setIsElectronApp(electron);
      const token = getStoredDeviceToken();
      const connected = !!token;
      setIsConnected(connected);
      setWebMode(!electron || !connected);
      await refreshLocalAcordCount();
      loadData();
      // Restore live polling for any job still marked running
      const savedJobs = getLocalJobs();
      const runningJob = savedJobs.find((j: any) => j.status === "running" && (j.config as any)?.runpod_job_id);
      if (runningJob) setActiveRunpodJobId((runningJob.config as any).runpod_job_id);
    };
    init();
  }, []);

  // Poll RunPod job every 5 s while a job is active
  useEffect(() => {
    if (!activeRunpodJobId) return;
    let alive = true;
    let failCount = 0;
    const MAX_FAILURES = 3;
    const jobIdSnapshot = activeRunpodJobId;
    const poll = async () => {
      try {
        const rpStatus = await getRunpodJobStatus(jobIdSnapshot);
        if (!alive) return;
        failCount = 0;
        setRunpodJobStatus(rpStatus);
        const terminal = ["completed", "failed", "gate_failed"].includes(rpStatus.status);
        if (terminal) {
          // Mark ACORD feedback as used so the badge flips to "Fine-tune Completed"
          if (rpStatus.status === "completed") await markAcordFeedbackAsUsed();
          // Persist final status into localStorage
          const allJobs = getLocalJobs();
          const updated = allJobs.map((j: any) =>
            (j.config as any)?.runpod_job_id === jobIdSnapshot
              ? {
                  ...j,
                  status: rpStatus.status === "completed" ? "completed" : "failed",
                  completed_at: new Date().toISOString(),
                  metrics: rpStatus.eval_scores
                    ? { ...rpStatus.eval_scores, version: rpStatus.version }
                    : { version: rpStatus.version },
                  error_message: rpStatus.error ?? null,
                }
              : j
          );
          localStorage.setItem("local_training_jobs", JSON.stringify(updated));
          setActiveRunpodJobId(null);
          loadData();
        }
      } catch {
        if (!alive) return;
        failCount++;
        if (failCount >= MAX_FAILURES) {
          // RunPod unreachable after 3 attempts — stop spinner, mark job as failed
          const allJobs = getLocalJobs();
          const updated = allJobs.map((j: any) =>
            (j.config as any)?.runpod_job_id === jobIdSnapshot
              ? {
                  ...j,
                  status: "failed",
                  error_message: "RunPod unreachable",
                  completed_at: new Date().toISOString(),
                }
              : j
          );
          localStorage.setItem("local_training_jobs", JSON.stringify(updated));
          setActiveRunpodJobId(null);
          setRunpodJobStatus(null);
          loadData();
        }
      }
    };
    poll();
    const interval = window.setInterval(poll, 5000);
    return () => { alive = false; clearInterval(interval); };
  }, [activeRunpodJobId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadData = async () => {
    setLoading(true);
    try {
      const token = getStoredDeviceToken();
      if (token) {
        const [statsRes, feedbackRes, jobsRes, roundsRes] = await Promise.all([
          getTrainingStats(),
          getFeedback(),
          getTrainingJobs(),
          getActiveRounds(),
        ]);
        setStats(statsRes.stats);
        setFeedback(feedbackRes.feedback);
        setJobs(jobsRes.jobs);
        setRounds(roundsRes.rounds);
        setContributions(roundsRes.contributions);
      } else {
        // Web-only: load from local storage
        const localFb = getLocalFeedback();
        let localJb = getLocalJobs();

        // Poll RunPod for real status on any running jobs that have a runpod_job_id
        const runningJobs = localJb.filter((j: any) => j.status === 'running' && (j.config as any)?.runpod_job_id);
        for (const job of runningJobs) {
          try {
            const rpStatus = await getRunpodJobStatus((job.config as any).runpod_job_id);
            if (rpStatus.status === 'completed' || rpStatus.status === 'gate_failed' || rpStatus.status === 'failed') {
              const updatedJobs = localJb.map((j: any) =>
                j.id === job.id
                  ? {
                      ...j,
                      status: rpStatus.status === 'completed' ? 'completed' : 'failed',
                      completed_at: new Date().toISOString(),
                      metrics: rpStatus.eval_scores
                        ? { ...rpStatus.eval_scores, version: rpStatus.version }
                        : { version: rpStatus.version },
                      error_message: rpStatus.error ?? null,
                    }
                  : j
              );
              localStorage.setItem('local_training_jobs', JSON.stringify(updatedJobs));
              localJb = updatedJobs;
            }
          } catch {
            // RunPod unreachable — keep showing "running"
          }
        }

        setFeedback(localFb);
        setJobs(localJb);
        setStats({
          total_feedback: localFb.length,
          total_training_jobs: localJb.length,
          total_contributions: 0,
        });
      }
    } catch (error: any) {
      // On error, still try local feedback
      const localFb = getLocalFeedback();
      if (localFb.length > 0) {
        setFeedback(localFb);
        setStats({ total_feedback: localFb.length, total_training_jobs: 0, total_contributions: 0 });
      } else {
        toast({ title: "Error", description: error.message, variant: "destructive" });
      }
    } finally {
      setLoading(false);
      await refreshLocalAcordCount();
    }
  };

  const handleRunpodFinetune = async () => {
    setIsFinetuning(true);
    setFinetuneStatus(null);

    try {
      // Step 1: Load submitted samples from Supabase (ACORD Parser corrections)
      setFinetuneStatus("Loading training samples from database…");
      const samples = await getAcordTrainingSamples();

      // Step 1b: Also include any ACORD feedback submitted via the Feedback form
      // (training_feedback table, model_id = acord_form_understanding, not yet used)
      const acordFormFeedback = feedback.filter(
        (f: any) =>
          (f.model_id === "acord_form_understanding" ||
            f.model_id?.toLowerCase().includes("acord")) &&
          !f.is_used_for_training &&
          f.corrected_response
      );

      const totalSamples = samples.length + acordFormFeedback.length;
      if (totalSamples === 0) {
        setFinetuneStatus("No training samples found. Save a correction from the ACORD Parser first.");
        toast({ title: "No samples", description: "Save at least one correction before fine-tuning.", variant: "destructive" });
        return;
      }

      // Step 2: Sync samples to RunPod pod filesystem
      setFinetuneStatus(`Syncing ${totalSamples} sample(s) to RunPod…`);
      const syncResult = await syncFeedbacksToRunpod([
        ...samples.map((s) => ({
          prompt: s.prompt,
          original_response: s.original_response,
          corrected_response: s.corrected_response,
          form_type: s.form_type,
        })),
        ...acordFormFeedback.map((f: any) => ({
          prompt: f.prompt,
          original_response: f.original_response,
          corrected_response: f.corrected_response,
          form_type: "25",
        })),
      ]);

      if (syncResult.failed > 0 && syncResult.synced === 0) {
        const msg = "Could not reach RunPod. Start the server on the pod:\ncd /workspace/ai-ml && python -m uvicorn server:app --host 0.0.0.0 --port 8000";
        setFinetuneStatus(msg);
        toast({ title: "RunPod unreachable", description: "Start the RunPod server first.", variant: "destructive" });
        return;
      }

      // Step 3: Trigger fine-tuning on RunPod
      setFinetuneStatus("Starting fine-tuning job…");
      const result = await startRunpodFinetune();
      setFinetuneStatus(
        result.status === "queued"
          ? `Fine-tuning queued with ${result.total_samples} sample(s). Running on RunPod GPU…`
          : result.message || result.status
      );
      toast({
        title: "Fine-tuning started on RunPod",
        description: `${result.total_samples ?? samples.length} sample(s) sent for LoRA training.`,
      });

      // Step 4: Mark samples as used in Supabase so they don't re-appear in count
      const runIds = samples.map((s) => s.run_id);
      await markAcordSamplesUsed(runIds).catch(() => {});

      // Step 5: Record training job locally for history polling
      const runpodJobId = (result as any).job_id ?? null;
      if (runpodJobId) {
        setActiveRunpodJobId(runpodJobId);
        setRunpodJobStatus({ status: "running", phase: "starting" });
      }
      await createTrainingJob({
        model_id: "acord_form_understanding",
        training_type: "fine-tune",
        config: { runpod_job_id: runpodJobId, sample_count: samples.length },
      }).catch(() => {});

      loadData();
    } catch (e: any) {
      const msg = e?.message || "Fine-tune failed";
      setFinetuneStatus(msg);
      toast({ title: "Fine-tune failed", description: msg, variant: "destructive" });
    } finally {
      setIsFinetuning(false);
      await refreshLocalAcordCount();
    }
  };

  const handleSubmitFeedback = async () => {
    if (!feedbackModelId || !feedbackPrompt || !feedbackOriginal) {
      toast({ title: "Missing fields", description: "Model, prompt, and original response are required", variant: "destructive" });
      return;
    }
    try {
      await submitFeedback({
        model_id: feedbackModelId,
        prompt: feedbackPrompt,
        original_response: feedbackOriginal,
        corrected_response: feedbackCorrected ?? undefined,
        rating: feedbackRating ?? undefined,
        feedback_type: feedbackCorrected ? "correction" : "rating",
      });
      toast({ title: "Feedback submitted", description: "Your feedback will be used for local training" });
      setFeedbackPrompt("");
      setFeedbackOriginal("");
      setFeedbackCorrected("");
      setFeedbackRating(0);
      loadData();
    } catch (error: any) {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  };

  const handleStartTraining = async (modelId: string, trainingType: string) => {
    try {
      const result = await createTrainingJob({ model_id: modelId, training_type: trainingType });
      toast({ title: "Training started", description: `Job ${result.job.id.slice(0, 8)} created with ${result.job.feedback_count} feedback samples` });
      loadData();
    } catch (error: any) {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  };

  const handleContribute = async (round: FederatedRound) => {
    try {
      // Simulate gradient generation (in real scenario, this comes from local training)
      const gradientHash = crypto.randomUUID();
      await submitGradient({
        model_id: round.model_id,
        round_number: round.round_number,
        gradient_hash: gradientHash,
        gradient_size_bytes: 1024 * 1024,
        metrics: { local_loss: 0.05, epochs: 3 },
        privacy_noise_added: true,
      });
      toast({ title: "Contribution submitted", description: `Gradient submitted for round ${round.round_number}` });
      loadData();
    } catch (error: any) {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  };

  const statusIcon = (status: string) => {
    switch (status) {
      case "completed": return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "failed": return <XCircle className="h-4 w-4 text-red-500" />;
      case "running": return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      default: return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const hasContributed = (round: FederatedRound) =>
    contributions.some((c: any) => c.model_id === round.model_id && c.round_number === round.round_number);
  const getJobBadgeVariant = (status: string): "default" | "destructive" | "secondary" => {
    if (status === "completed") return "default";
    if (status === "failed") return "destructive";
    return "secondary";
  };
  const getRoundBadgeVariant = (status: string): "default" | "secondary" | "outline" => {
    if (status === "completed") return "default";
    if (status === "aggregating") return "secondary";
    return "outline";
  };

  // ── Pipeline helpers ─────────────────────────────────────────────────────────
  const getPhaseLabel = (phase: string | undefined): string => {
    switch (phase) {
      case "starting":            return "Initialising job…";
      case "loading_config":      return "Loading configuration…";
      case "building_dataset":    return "Building training dataset…";
      case "resolving_base_model":return "Loading base model weights…";
      case "pending_registered":  return "Registering pending version…";
      case "training":            return "Training on GPU…";
      case "evaluating":          return "Evaluating model quality…";
      case "gate_checked":        return "Quality gate passed ✓";
      case "merging":             return "Merging LoRA adapter…";
      case "promoting":           return "Uploading to SeaweedFS & registering…";
      case "done":                return "Complete — model registered";
      default:                    return phase ? `${phase}…` : "Processing…";
    }
  };

  // 0=idle 1=local-training 2=uploading 3=aggregating 4=done
  const getPipelineStep = (phase: string | undefined, status: string): number => {
    if (status === "completed") return 4;
    if (!phase) return 0;
    if (["promoting"].includes(phase)) return 3;
    if (["merging"].includes(phase)) return 2;
    if (["starting", "loading_config", "building_dataset", "resolving_base_model",
         "pending_registered", "training", "evaluating", "gate_checked"].includes(phase)) return 1;
    return 0;
  };

  if (!isElectronApp && !webMode) {
    return null;
  }

  // Show a connect prompt only for Electron users without a token
  if (isElectronApp && !isConnected) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Model Training</CardTitle>
            <CardDescription>Connect your device first in Device Setup to use training features</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  // Note: no early return for activatedModels.length === 0 —
  // the ACORD RunPod fine-tuning card must always be visible.

  // Derived pipeline state — placed after early returns so TS sees them as read
  const pipelineStep = getPipelineStep(runpodJobStatus?.phase, runpodJobStatus?.status ?? "");
  const isJobRunning = !!activeRunpodJobId || runpodJobStatus?.status === "running";
  const isJobDone = runpodJobStatus?.status === "completed";
  const isJobFailed = runpodJobStatus?.status === "failed" || runpodJobStatus?.status === "gate_failed";

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Model Training</h1>
          <p className="text-muted-foreground mt-1">
            Train models locally and contribute to federated learning
          </p>
        </div>
        <Button variant="outline" onClick={loadData} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-500/10 rounded-lg">
                  <MessageSquare className="h-5 w-5 text-blue-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total_feedback}</p>
                  <p className="text-sm text-muted-foreground">Feedback Collected</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-500/10 rounded-lg">
                  <Cpu className="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total_training_jobs}</p>
                  <p className="text-sm text-muted-foreground">Training Jobs</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-500/10 rounded-lg">
                  <Globe className="h-5 w-5 text-purple-500" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total_contributions}</p>
                  <p className="text-sm text-muted-foreground">Federated Contributions</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="feedback" className="space-y-4">
        <TabsList>
          <TabsTrigger value="feedback">
            <MessageSquare className="h-4 w-4 mr-2" />
            Feedback
          </TabsTrigger>
          <TabsTrigger value="local-training">
            <Cpu className="h-4 w-4 mr-2" />
            Local Training
          </TabsTrigger>
          <TabsTrigger value="federated">
            <Globe className="h-4 w-4 mr-2" />
            Federated Learning
          </TabsTrigger>
        </TabsList>

        {/* Feedback Tab */}
        <TabsContent value="feedback" className="space-y-4">
          {/* Fine-tune completion banner — shown when the latest job finished successfully */}
          {isJobDone && (
            <div className="flex items-center gap-3 p-4 rounded-lg bg-green-500/10 border border-green-500/30">
              <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-green-600 dark:text-green-400">
                  Fine-tune Completed
                  {runpodJobStatus?.version != null && ` — Model v${runpodJobStatus.version} promoted`}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Your ACORD Form Understanding feedback has been used to train the model. All used samples are now marked below.
                </p>
              </div>
            </div>
          )}
          {isJobFailed && (
            <div className="flex items-center gap-3 p-4 rounded-lg bg-red-500/10 border border-red-500/30">
              <XCircle className="h-5 w-5 text-red-500 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-red-600 dark:text-red-400">Fine-tune Failed</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {runpodJobStatus?.error ?? "The training job did not complete. Check the Local Training tab for details."}
                </p>
              </div>
            </div>
          )}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Star className="h-5 w-5" />
                Submit Training Feedback
              </CardTitle>
              <CardDescription>
                Correct AI outputs or rate responses to build local training data
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Model</Label>
                <Select value={feedbackModelId} onValueChange={setFeedbackModelId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {activatedModels.map((m: any) => (
                      <SelectItem key={m.model_id} value={m.model_id}>{m.model_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Prompt</Label>
                <Textarea value={feedbackPrompt} onChange={e => setFeedbackPrompt(e.target.value)} placeholder="The prompt that was sent to the model" />
              </div>
              <div className="space-y-2">
                <Label>Original Response</Label>
                <Textarea value={feedbackOriginal} onChange={e => setFeedbackOriginal(e.target.value)} placeholder="The model's original response" />
              </div>
              <div className="space-y-2">
                <Label>Corrected Response (optional)</Label>
                <Textarea value={feedbackCorrected} onChange={e => setFeedbackCorrected(e.target.value)} placeholder="What the correct response should have been" />
              </div>
              <div className="space-y-2">
                <Label>Rating</Label>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map((star: any) => (
                    <Button
                      key={star}
                      variant={feedbackRating >= star ? "default" : "outline"}
                      size="sm"
                      onClick={() => setFeedbackRating(star)}
                    >
                      <Star className={`h-4 w-4 ${feedbackRating >= star ? "fill-current" : ""}`} />
                    </Button>
                  ))}
                </div>
              </div>
              <Button onClick={handleSubmitFeedback}>
                <Upload className="h-4 w-4 mr-2" />
                Submit Feedback
              </Button>
              {(feedbackModelId === "acord_form_understanding" ||
                activatedModels.find((m) => m.model_id === feedbackModelId)
                  ?.model_name?.toLowerCase().includes("acord")) && (
                <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                  This feedback will be included in your next Local Training run for ACORD Form Understanding.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Recent Feedback */}
          {feedback.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Recent Feedback ({feedback.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {feedback.slice(0, 10).map((fb: any) => {
                    const isExpanded = expandedFeedbackId === fb.id;
                    const createdAt = new Date(fb.created_at);
                    const dateStr = createdAt.toLocaleDateString(undefined, {
                      year: "numeric", month: "short", day: "numeric",
                    });
                    const timeStr = createdAt.toLocaleTimeString(undefined, {
                      hour: "2-digit", minute: "2-digit",
                    });
                    return (
                      <div key={fb.id} className="border rounded-lg overflow-hidden">
                        {/* Clickable header row */}
                        <button
                          className="w-full flex items-start justify-between p-3 hover:bg-muted/40 transition-colors text-left"
                          onClick={() => setExpandedFeedbackId(isExpanded ? null : fb.id)}
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <Badge variant="outline">{fb.model_id}</Badge>
                              <Badge
                                variant={fb.is_used_for_training ? "default" : "secondary"}
                                className={fb.is_used_for_training ? "bg-green-600/90 text-white border-0" : ""}
                              >
                                {fb.is_used_for_training ? (
                                  <><CheckCircle2 className="h-3 w-3 mr-1" />Fine-tune Completed</>
                                ) : "Available"}
                              </Badge>
                              {fb.feedback_type === "correction" && (
                                <ThumbsUp className="h-3 w-3 text-green-500" />
                              )}
                              {fb.feedback_type === "rating" && fb.rating > 0 && (
                                <span className="text-xs text-muted-foreground">★ {fb.rating}/5</span>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground truncate">{fb.prompt}</p>
                          </div>
                          <div className="flex items-center gap-2 ml-3 shrink-0">
                            <div className="text-right">
                              <p className="text-xs font-medium text-muted-foreground">{dateStr}</p>
                              <p className="text-xs text-muted-foreground">{timeStr}</p>
                            </div>
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            )}
                          </div>
                        </button>

                        {/* Expanded detail panel */}
                        {isExpanded && (
                          <div className="border-t bg-muted/20 px-4 py-3 space-y-3">
                            <div>
                              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                                Prompt
                              </p>
                              <p className="text-sm whitespace-pre-wrap break-words">{fb.prompt}</p>
                            </div>
                            {fb.original_response && (
                              <div>
                                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                                  Original Response
                                </p>
                                <p className="text-sm whitespace-pre-wrap break-words text-muted-foreground">
                                  {fb.original_response}
                                </p>
                              </div>
                            )}
                            {fb.corrected_response && (
                              <div>
                                <p className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-1">
                                  Corrected Response
                                </p>
                                <p className="text-sm whitespace-pre-wrap break-words text-green-700 dark:text-green-400">
                                  {fb.corrected_response}
                                </p>
                              </div>
                            )}
                            <div className="flex items-center gap-4 pt-1 border-t text-xs text-muted-foreground">
                              <span>Type: <span className="font-medium capitalize">{fb.feedback_type ?? "—"}</span></span>
                              {fb.rating > 0 && (
                                <span>Rating: <span className="font-medium">{"★".repeat(fb.rating)}{"☆".repeat(5 - fb.rating)}</span></span>
                              )}
                              <span className="ml-auto">{dateStr} · {timeStr}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Local Training Tab */}
        <TabsContent value="local-training" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Cpu className="h-5 w-5" />
                Start Local Training
              </CardTitle>
              <CardDescription>
                Fine-tune models on your device using collected feedback
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {activatedModels.map(({ model_id: modelId, model_name: modelName }) => {
                  const isAcord =
                    modelId === "acord_form_understanding" ||
                    modelName?.toLowerCase().includes("acord");

                  // ACORD model — count read from Supabase via refreshLocalAcordCount
                  if (isAcord) {
                    const acordFormFeedback = [...feedback.filter((f: any) => f.model_id === modelId && !f.is_used_for_training)]
                      .sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
                    const totalAcordSamples = localAcordCount + acordFormFeedback.length;
                    const canFinetune = !isFinetuning && totalAcordSamples > 0;

                    return (
                      <div key={modelId} className="col-span-full space-y-2">
                        <div className="p-4 border rounded-lg space-y-3">
                          <div className="flex items-center justify-between">
                            <h4 className="font-medium">{modelName}</h4>
                            {totalAcordSamples > 0 ? (
                              <button
                                onClick={handleToggleAcordSamples}
                                className="flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-xs font-semibold hover:bg-muted transition-colors"
                              >
                                {totalAcordSamples} samples
                                {showAcordSamples ? (
                                  <ChevronUp className="h-3 w-3" />
                                ) : (
                                  <ChevronDown className="h-3 w-3" />
                                )}
                              </button>
                            ) : (
                              <Badge variant="outline">0 samples</Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {totalAcordSamples > 0
                              ? `${totalAcordSamples} sample${totalAcordSamples !== 1 ? "s" : ""} ready for training`
                              : "No feedback samples yet — save a sample from the ACORD Parser"}
                          </p>
                          {finetuneStatus && (
                            <p className="text-xs text-muted-foreground whitespace-pre-line">{finetuneStatus}</p>
                          )}
                          <Button
                            size="sm"
                            disabled={!canFinetune}
                            onClick={handleRunpodFinetune}
                          >
                            {isFinetuning ? (
                              <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Starting…</>
                            ) : (
                              <><Play className="h-4 w-4 mr-1" />Fine-tune</>
                            )}
                          </Button>
                        </div>

                        {/* Expandable sample list — ACORD runs + form feedback, sorted latest first */}
                        {showAcordSamples && (
                          <div className="border rounded-lg overflow-hidden">
                            <div className="px-4 py-2 bg-muted/50 border-b flex items-center justify-between">
                              <span className="text-sm font-medium">Training Samples</span>
                              <span className="text-xs text-muted-foreground">
                                {acordSampleList.length} sample{acordSampleList.length !== 1 ? "s" : ""} · latest first
                              </span>
                            </div>
                            {acordSamplesLoading ? (
                              <div className="flex items-center justify-center py-6 gap-2 text-muted-foreground">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span className="text-sm">Loading samples…</span>
                              </div>
                            ) : acordSampleList.length === 0 ? (
                              <div className="py-6 text-center text-sm text-muted-foreground">
                                No samples found
                              </div>
                            ) : (
                              <div className="divide-y">
                                {acordSampleList.map((s, idx) => {
                                  const date = new Date(s.created_at);
                                  const dateStr = date.toLocaleDateString(undefined, {
                                    year: "numeric", month: "short", day: "numeric",
                                  });
                                  const timeStr = date.toLocaleTimeString(undefined, {
                                    hour: "2-digit", minute: "2-digit",
                                  });
                                  const isSampleExpanded = expandedSampleId === s.run_id;
                                  return (
                                    <div key={s.run_id} className="overflow-hidden">
                                      {/* Clickable summary row */}
                                      <button
                                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/40 transition-colors text-left"
                                        onClick={() => setExpandedSampleId(isSampleExpanded ? null : s.run_id)}
                                      >
                                        <span className="text-xs text-muted-foreground w-5 shrink-0">
                                          {idx + 1}
                                        </span>
                                        <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                                        <div className="flex-1 min-w-0">
                                          <p className="text-sm font-medium truncate">
                                            {s.source_filename}
                                          </p>
                                          <p className="text-xs text-muted-foreground">
                                            Form {s.form_type}
                                          </p>
                                        </div>
                                        <div className="text-right shrink-0">
                                          <p className="text-xs font-medium">{dateStr}</p>
                                          <p className="text-xs text-muted-foreground">{timeStr}</p>
                                        </div>
                                        <Badge
                                          variant={s.status === "needs_admin_review" ? "secondary" : "outline"}
                                          className="text-xs shrink-0"
                                        >
                                          {s.status === "needs_admin_review" ? "review" : "ready"}
                                        </Badge>
                                        {isSampleExpanded ? (
                                          <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
                                        ) : (
                                          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                                        )}
                                      </button>

                                      {/* Expanded detail panel */}
                                      {isSampleExpanded && (
                                        <div className="border-t bg-muted/20 px-5 py-4 space-y-4">
                                          <div>
                                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                                              Prompt / Raw Text
                                            </p>
                                            <p className="text-sm whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
                                              {s.prompt || "—"}
                                            </p>
                                          </div>
                                          <div>
                                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                                              Original Extracted JSON
                                            </p>
                                            <pre className="text-xs bg-muted rounded p-3 overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap break-words">
                                              {s.original_response || "—"}
                                            </pre>
                                          </div>
                                          {s.corrected_response && (
                                            <div>
                                              <p className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-1">
                                                Corrected JSON
                                              </p>
                                              <pre className="text-xs bg-green-50 dark:bg-green-950/30 text-green-800 dark:text-green-300 rounded p-3 overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap break-words">
                                                {s.corrected_response}
                                              </pre>
                                            </div>
                                          )}
                                          <div className="flex items-center gap-3 pt-1 border-t text-xs text-muted-foreground">
                                            <span>File: <span className="font-medium">{s.source_filename}</span></span>
                                            <span>·</span>
                                            <span>Form: <span className="font-medium">{s.form_type}</span></span>
                                            <span className="ml-auto">{dateStr} · {timeStr}</span>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Form-submitted feedback for ACORD — from training_feedback table */}
                        {(() => {
                          if (acordFormFeedback.length === 0) return null;
                          return (
                            <div className="border rounded-lg overflow-hidden">
                              <div className="px-4 py-2 bg-muted/50 border-b flex items-center justify-between">
                                <span className="text-sm font-medium">Form Feedback</span>
                                <span className="text-xs text-muted-foreground">
                                  {acordFormFeedback.length} item{acordFormFeedback.length !== 1 ? "s" : ""} · latest first
                                </span>
                              </div>
                              <div className="divide-y">
                                {acordFormFeedback.map((fb: any, idx: number) => {
                                  const isItemExpanded = expandedLocalItemId === fb.id;
                                  const date = new Date(fb.created_at);
                                  const dateStr = date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
                                  const timeStr = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
                                  return (
                                    <div key={fb.id} className="overflow-hidden">
                                      <button
                                        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/40 transition-colors text-left"
                                        onClick={() => setExpandedLocalItemId(isItemExpanded ? null : fb.id)}
                                      >
                                        <span className="text-xs text-muted-foreground w-5 shrink-0">{idx + 1}</span>
                                        <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />
                                        <div className="flex-1 min-w-0">
                                          <p className="text-sm font-medium truncate">{fb.prompt}</p>
                                          <p className="text-xs text-muted-foreground capitalize">{fb.feedback_type || "feedback"}</p>
                                        </div>
                                        <div className="text-right shrink-0">
                                          <p className="text-xs font-medium">{dateStr}</p>
                                          <p className="text-xs text-muted-foreground">{timeStr}</p>
                                        </div>
                                        <Badge variant="outline" className="text-xs shrink-0">ready</Badge>
                                        {isItemExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />}
                                      </button>
                                      {isItemExpanded && (
                                        <div className="border-t bg-muted/20 px-5 py-4 space-y-4">
                                          <div>
                                            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Prompt</p>
                                            <p className="text-sm whitespace-pre-wrap break-words max-h-40 overflow-y-auto">{fb.prompt || "—"}</p>
                                          </div>
                                          {fb.original_response && (
                                            <div>
                                              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Original Response</p>
                                              <p className="text-sm whitespace-pre-wrap break-words text-muted-foreground max-h-40 overflow-y-auto">{fb.original_response}</p>
                                            </div>
                                          )}
                                          {fb.corrected_response && (
                                            <div>
                                              <p className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-1">Corrected Response</p>
                                              <p className="text-sm whitespace-pre-wrap break-words text-green-700 dark:text-green-400 max-h-40 overflow-y-auto">{fb.corrected_response}</p>
                                            </div>
                                          )}
                                          <div className="flex items-center gap-4 pt-1 border-t text-xs text-muted-foreground">
                                            <span>Type: <span className="font-medium capitalize">{fb.feedback_type || "feedback"}</span></span>
                                            {fb.rating > 0 && <span>Rating: <span className="font-medium">{"★".repeat(fb.rating)}{"☆".repeat(5 - fb.rating)}</span></span>}
                                            <span className="ml-auto">{dateStr} · {timeStr}</span>
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })()}
                      </div>
                    );
                  }

                  // All other models — local feedback from training_feedback table
                  const modelFeedback = [...feedback.filter((f: any) => f.model_id === modelId && !f.is_used_for_training)]
                    .sort((a: any, b: any) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
                  const isShowingFeedback = showModelFeedback[modelId] ?? false;

                  return (
                    <div key={modelId} className="col-span-full space-y-2">
                      <div className="p-4 border rounded-lg space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-medium">{modelName}</h4>
                          {modelFeedback.length > 0 ? (
                            <button
                              onClick={() => setShowModelFeedback(prev => ({ ...prev, [modelId]: !isShowingFeedback }))}
                              className="flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-xs font-semibold hover:bg-muted transition-colors"
                            >
                              {modelFeedback.length} samples
                              {isShowingFeedback ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                            </button>
                          ) : (
                            <Badge variant="outline">0 samples</Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {modelFeedback.length >= 1
                            ? `${modelFeedback.length} sample${modelFeedback.length > 1 ? "s" : ""} ready for training`
                            : "No feedback samples yet"}
                        </p>
                        <Button
                          size="sm"
                          disabled={modelFeedback.length < 1}
                          onClick={() => handleStartTraining(modelId, "fine-tune")}
                        >
                          <Play className="h-4 w-4 mr-1" />
                          Fine-tune
                        </Button>
                      </div>

                      {/* Expandable feedback list */}
                      {isShowingFeedback && modelFeedback.length > 0 && (
                        <div className="border rounded-lg overflow-hidden">
                          <div className="px-4 py-2 bg-muted/50 border-b flex items-center justify-between">
                            <span className="text-sm font-medium">Training Samples</span>
                            <span className="text-xs text-muted-foreground">
                              {modelFeedback.length} sample{modelFeedback.length !== 1 ? "s" : ""} · latest first
                            </span>
                          </div>
                          <div className="divide-y">
                            {modelFeedback.map((fb: any, idx: number) => {
                              const isItemExpanded = expandedLocalItemId === fb.id;
                              const date = new Date(fb.created_at);
                              const dateStr = date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
                              const timeStr = date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
                              return (
                                <div key={fb.id} className="overflow-hidden">
                                  <button
                                    className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/40 transition-colors text-left"
                                    onClick={() => setExpandedLocalItemId(isItemExpanded ? null : fb.id)}
                                  >
                                    <span className="text-xs text-muted-foreground w-5 shrink-0">{idx + 1}</span>
                                    <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm font-medium truncate">{fb.prompt}</p>
                                      <p className="text-xs text-muted-foreground capitalize">{fb.feedback_type || "feedback"}</p>
                                    </div>
                                    <div className="text-right shrink-0">
                                      <p className="text-xs font-medium">{dateStr}</p>
                                      <p className="text-xs text-muted-foreground">{timeStr}</p>
                                    </div>
                                    <Badge variant="outline" className="text-xs shrink-0">ready</Badge>
                                    {isItemExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />}
                                  </button>
                                  {isItemExpanded && (
                                    <div className="border-t bg-muted/20 px-5 py-4 space-y-4">
                                      <div>
                                        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Prompt</p>
                                        <p className="text-sm whitespace-pre-wrap break-words max-h-40 overflow-y-auto">{fb.prompt || "—"}</p>
                                      </div>
                                      {fb.original_response && (
                                        <div>
                                          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1">Original Response</p>
                                          <p className="text-sm whitespace-pre-wrap break-words text-muted-foreground max-h-40 overflow-y-auto">{fb.original_response}</p>
                                        </div>
                                      )}
                                      {fb.corrected_response && (
                                        <div>
                                          <p className="text-xs font-semibold text-green-600 uppercase tracking-wide mb-1">Corrected Response</p>
                                          <p className="text-sm whitespace-pre-wrap break-words text-green-700 dark:text-green-400 max-h-40 overflow-y-auto">{fb.corrected_response}</p>
                                        </div>
                                      )}
                                      <div className="flex items-center gap-4 pt-1 border-t text-xs text-muted-foreground">
                                        <span>Type: <span className="font-medium capitalize">{fb.feedback_type || "feedback"}</span></span>
                                        {fb.rating > 0 && <span>Rating: <span className="font-medium">{"★".repeat(fb.rating)}{"☆".repeat(5 - fb.rating)}</span></span>}
                                        <span className="ml-auto">{dateStr} · {timeStr}</span>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Training Jobs History */}
          {jobs.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Training History
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {jobs.map((job: any) => {
                    const isActiveJob = (job.config as any)?.runpod_job_id === activeRunpodJobId;
                    const livePhase = isActiveJob ? runpodJobStatus?.phase : undefined;
                    const displayStatus = isActiveJob && runpodJobStatus ? runpodJobStatus.status : job.status;
                    return (
                      <div key={job.id} className="flex items-center justify-between p-3 border rounded-lg">
                        <div className="flex items-center gap-3">
                          {statusIcon(displayStatus)}
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-medium capitalize">{job.model_id.replace(/_/g, " ")}</span>
                              <Badge variant="outline">{job.training_type}</Badge>
                              <Badge variant={getJobBadgeVariant(displayStatus)}>{displayStatus}</Badge>
                              {livePhase && displayStatus === "running" && (
                                <Badge variant="secondary" className="text-[10px]">
                                  {getPhaseLabel(livePhase)}
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {(job.config as any)?.sample_count ?? job.feedback_count} samples • {new Date(job.created_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <div className="text-right text-sm text-muted-foreground">
                          {job.metrics && (job.metrics as any).version && (
                            <p className="text-xs font-medium">v{(job.metrics as any).version}</p>
                          )}
                          {job.metrics && (job.metrics as any).loss && (
                            <p>Loss: {(job.metrics as any).loss}</p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Federated Learning Tab */}
        <TabsContent value="federated" className="space-y-4">

          {/* Privacy banner */}
          <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg border">
            <Shield className="h-5 w-5 text-green-500 flex-shrink-0" />
            <p className="text-sm text-muted-foreground">
              <strong className="text-foreground">Privacy Protected:</strong> Differential privacy noise is added
              to all gradient updates before submission. Your raw data stays on your device.
            </p>
          </div>

          {/* Live Pipeline Status */}
          {(isJobRunning || isJobDone || isJobFailed) && (() => {
            const steps = [
              { label: "Local Training",      desc: "QLoRA fine-tuning on GPU",                  icon: Cpu },
              { label: "Upload Weights",       desc: "Merge adapter & push to SeaweedFS",         icon: Upload },
              { label: "Global Aggregation",   desc: "FedAvg across participants",                icon: Globe },
              { label: "Model Ready",          desc: "New version available for Electron download", icon: CheckCircle2 },
            ];
            return (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Globe className="h-5 w-5" />
                    Federated Learning — Pipeline Status
                    {isJobRunning && <Loader2 className="h-4 w-4 ml-1 animate-spin text-blue-500" />}
                    {isJobDone && <CheckCircle2 className="h-4 w-4 ml-1 text-green-500" />}
                    {isJobFailed && <XCircle className="h-4 w-4 ml-1 text-red-500" />}
                  </CardTitle>
                  {runpodJobStatus?.phase && (
                    <CardDescription className="flex items-center gap-1.5">
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                      {getPhaseLabel(runpodJobStatus.phase)}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent>
                  {/* Step indicators */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                    {steps.map((s, i) => {
                      const stepNum = i + 1;
                      const done = isJobDone ? true : pipelineStep > stepNum;
                      const active = !isJobFailed && pipelineStep === stepNum;
                      const failed = isJobFailed && pipelineStep === stepNum;
                      return (
                        <div
                          key={s.label}
                          className={`relative flex flex-col items-center text-center p-3 rounded-lg border transition-colors ${
                            done ? "border-green-500/40 bg-green-500/5" :
                            active ? "border-blue-500/40 bg-blue-500/5" :
                            failed ? "border-red-500/40 bg-red-500/5" :
                            "border-border/40 bg-muted/20 opacity-50"
                          }`}
                        >
                          <div className={`mb-2 h-9 w-9 rounded-full flex items-center justify-center ${
                            done ? "bg-green-500/15" : active ? "bg-blue-500/15" : failed ? "bg-red-500/15" : "bg-muted"
                          }`}>
                            {done ? (
                              <CheckCircle2 className="h-5 w-5 text-green-500" />
                            ) : active ? (
                              <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
                            ) : failed ? (
                              <XCircle className="h-5 w-5 text-red-500" />
                            ) : (
                              <s.icon className="h-5 w-5 text-muted-foreground" />
                            )}
                          </div>
                          <span className={`text-[10px] font-bold uppercase tracking-wide mb-0.5 ${
                            done ? "text-green-500" : active ? "text-blue-500" : failed ? "text-red-500" : "text-muted-foreground"
                          }`}>Step {stepNum}</span>
                          <p className="text-xs font-medium leading-tight">{s.label}</p>
                          <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">{s.desc}</p>
                        </div>
                      );
                    })}
                  </div>

                  {/* Overall progress bar */}
                  <Progress value={isJobDone ? 100 : isJobFailed ? (pipelineStep / 4) * 100 : ((pipelineStep - 0.5) / 4) * 100} className="h-1.5 mb-3" />

                  {/* Terminal state messages */}
                  {isJobDone && (
                    <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-sm text-green-600 dark:text-green-400">
                      <CheckCircle2 className="h-4 w-4 shrink-0" />
                      Model {runpodJobStatus?.version ? `v${runpodJobStatus.version}` : ""} registered successfully — available for Electron download.
                    </div>
                  )}
                  {isJobFailed && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-600 dark:text-red-400">
                      <XCircle className="h-4 w-4 shrink-0 mt-0.5" />
                      <span>{runpodJobStatus?.error || "Training failed. Check RunPod logs for details."}</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })()}

          {/* No job running and no recent result — show idle state with existing rounds or info */}
          {!isJobRunning && !isJobDone && !isJobFailed && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Globe className="h-5 w-5" />
                  Federated Learning Rounds
                </CardTitle>
              </CardHeader>
              <CardContent>
                {rounds.length === 0 ? (
                  <div className="text-center py-8">
                    <Globe className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-40" />
                    <h3 className="font-medium mb-1">No Active Rounds</h3>
                    <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                      Start local training above to kick off the pipeline. After weights are uploaded
                      to SeaweedFS the global aggregation runs automatically.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {rounds.map((round: any) => {
                      const contributed = hasContributed(round);
                      const progress = (round.current_participants / round.min_participants) * 100;
                      return (
                        <div key={round.id} className="p-4 border rounded-lg space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <h4 className="font-medium capitalize">{round.model_id.replace(/_/g, " ")}</h4>
                              <Badge variant="outline">Round {round.round_number}</Badge>
                              <Badge variant={getRoundBadgeVariant(round.status)}>{round.status}</Badge>
                            </div>
                            {contributed && (
                              <Badge className="bg-green-500 text-white">
                                <CheckCircle2 className="h-3 w-3 mr-1" />Contributed
                              </Badge>
                            )}
                          </div>
                          <div className="space-y-1">
                            <div className="flex justify-between text-sm">
                              <span className="text-muted-foreground flex items-center gap-1">
                                <Users className="h-3 w-3" />
                                {round.current_participants}/{round.min_participants} participants
                              </span>
                              <span className="text-muted-foreground">{round.aggregation_method}</span>
                            </div>
                            <Progress value={Math.min(progress, 100)} />
                          </div>
                          {!contributed && round.status === "collecting" && (
                            <Button size="sm" onClick={() => handleContribute(round)}>
                              <Upload className="h-4 w-4 mr-2" />Contribute Gradient Update
                            </Button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* How It Works */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5" />
                How Federated Learning Works
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[
                  { step: "1", title: "Collect Feedback", desc: "Rate and correct AI outputs during normal use", icon: MessageSquare },
                  { step: "2", title: "Train Locally", desc: "Fine-tune the model on RunPod GPU using LoRA adapters", icon: Cpu },
                  { step: "3", title: "Upload & Aggregate", desc: "Weights pushed to SeaweedFS; FedAvg runs automatically", icon: Globe },
                  { step: "4", title: "Model Updated", desc: "New version registered and distributed to Electron devices", icon: CheckCircle2 },
                ].map((item: any) => (
                  <div key={item.step} className="text-center p-4 border rounded-lg">
                    <div className="mx-auto mb-2 h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                      <item.icon className="h-5 w-5 text-primary" />
                    </div>
                    <div className="text-xs font-semibold text-primary mb-1">Step {item.step}</div>
                    <h4 className="font-medium text-sm">{item.title}</h4>
                    <p className="text-xs text-muted-foreground mt-1">{item.desc}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
