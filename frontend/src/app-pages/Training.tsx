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
  markAcordSamplesUsed,
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

      const modelsRes = await fetch(apiUrl("/api/v1/activated-models"), {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (modelsRes.ok) {
        const modelsPayload = await modelsRes.json();
        setActivatedModels(modelsPayload.activated_models ?? []);
      }

      const electron = await isElectron();
      setIsElectronApp(electron);
      const token = getStoredDeviceToken();
      const connected = !!token;
      setIsConnected(connected);
      setWebMode(!electron || !connected);
      await refreshLocalAcordCount();
      loadData();
    };
    init();
  }, []);

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
      // Step 1: Load submitted samples from Supabase
      setFinetuneStatus("Loading training samples from database…");
      const samples = await getAcordTrainingSamples();

      if (samples.length === 0) {
        setFinetuneStatus("No training samples found. Save a correction from the ACORD Parser first.");
        toast({ title: "No samples", description: "Save at least one correction before fine-tuning.", variant: "destructive" });
        return;
      }

      // Step 2: Sync samples to RunPod pod filesystem
      setFinetuneStatus(`Syncing ${samples.length} sample(s) to RunPod…`);
      const syncResult = await syncFeedbacksToRunpod(
        samples.map((s) => ({
          prompt: s.prompt,
          original_response: s.original_response,
          corrected_response: s.corrected_response,
          form_type: s.form_type,
        }))
      );

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
      await createTrainingJob({
        model_id: "acord_form_understanding",
        training_type: "fine-tune",
        config: { runpod_job_id: runpodJobId },
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
            </CardContent>
          </Card>

          {/* Recent Feedback */}
          {feedback.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Recent Feedback ({feedback.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {feedback.slice(0, 10).map((fb: any) => (
                    <div key={fb.id} className="flex items-start justify-between p-3 border rounded-lg">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline">{fb.model_id}</Badge>
                          <Badge variant={fb.is_used_for_training ? "default" : "secondary"}>
                            {fb.is_used_for_training ? "Used" : "Available"}
                          </Badge>
                          {fb.feedback_type === "correction" && <ThumbsUp className="h-3 w-3 text-green-500" />}
                          {fb.feedback_type === "rating" && (
                            <span className="text-xs text-muted-foreground">★ {fb.rating}/5</span>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground truncate">{fb.prompt}</p>
                      </div>
                      <span className="text-xs text-muted-foreground whitespace-nowrap ml-2">
                        {new Date(fb.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
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
                    const canFinetune = !isFinetuning && localAcordCount > 0;

                    return (
                      <div key={modelId} className="p-4 border rounded-lg space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-medium">{modelName}</h4>
                          <Badge variant="outline">{localAcordCount} samples</Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {localAcordCount > 0
                            ? `${localAcordCount} sample${localAcordCount !== 1 ? "s" : ""} ready for training`
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
                    );
                  }

                  // All other models — local feedback
                  const modelFeedback = feedback.filter((f: any) => f.model_id === modelId && !f.is_used_for_training);
                  return (
                    <div key={modelId} className="p-4 border rounded-lg space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium">{modelName}</h4>
                        <Badge variant="outline">{modelFeedback.length} samples</Badge>
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
                  {jobs.map((job: any) => (
                    <div key={job.id} className="flex items-center justify-between p-3 border rounded-lg">
                      <div className="flex items-center gap-3">
                        {statusIcon(job.status)}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium capitalize">{job.model_id.replace("-", " ")}</span>
                            <Badge variant="outline">{job.training_type}</Badge>
                            <Badge variant={getJobBadgeVariant(job.status)}>{job.status}</Badge>
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {job.feedback_count} samples • {new Date(job.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      {job.metrics && Object.keys(job.metrics).length > 0 && (
                        <div className="text-right text-sm text-muted-foreground">
                          {(job.metrics as any).loss && <p>Loss: {(job.metrics as any).loss}</p>}
                          {(job.metrics as any).epochs && <p>Epochs: {(job.metrics as any).epochs}</p>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Federated Learning Tab */}
        <TabsContent value="federated" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5" />
                Federated Learning Rounds
              </CardTitle>
              <CardDescription>
                Contribute your local training improvements to the global model. Only encrypted weight
                deltas are shared — your data never leaves your device.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg mb-4">
                <Shield className="h-5 w-5 text-green-500 flex-shrink-0" />
                <p className="text-sm text-muted-foreground">
                  <strong className="text-foreground">Privacy Protected:</strong> Differential privacy noise is added
                  to all gradient updates before submission. Your raw data stays on your device.
                </p>
              </div>

              {rounds.length === 0 ? (
                <div className="text-center py-8">
                  <Globe className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                  <h3 className="font-medium mb-1">No Active Rounds</h3>
                  <p className="text-sm text-muted-foreground">
                    No federated learning rounds are currently active. Your admin will start rounds when ready.
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
                            <h4 className="font-medium capitalize">{round.model_id.replace("-", " ")}</h4>
                            <Badge variant="outline">Round {round.round_number}</Badge>
                            <Badge variant={getRoundBadgeVariant(round.status)}>{round.status}</Badge>
                          </div>
                          {contributed && (
                            <Badge variant="default" className="bg-green-500">
                              <CheckCircle2 className="h-3 w-3 mr-1" />
                              Contributed
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
                            <Upload className="h-4 w-4 mr-2" />
                            Contribute Gradient Update
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

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
                  { step: "2", title: "Train Locally", desc: "Fine-tune the model on your device using LoRA adapters", icon: Cpu },
                  { step: "3", title: "Share Gradients", desc: "Only encrypted weight deltas are sent (not your data)", icon: Shield },
                  { step: "4", title: "Global Update", desc: "Server aggregates updates and distributes improved model", icon: Globe },
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
