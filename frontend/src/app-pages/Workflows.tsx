import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import {
  Brain, Plus, Play, Loader2, CheckCircle2, Circle, ArrowRight,
  Sparkles, FileText, Trash2, MessageSquare, Send, Pencil, History, RotateCcw,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { streamFromEdgeFunction } from "@/lib/streamHelper";
import { streamChat } from "@/lib/aiChat";

interface WorkflowStep {
  step_number: number;
  title: string;
  description: string;
  action_type: string;
  ai_can_assist: boolean;
  estimated_minutes: number;
}

interface Workflow {
  id: string;
  title: string;
  description: string | null;
  sop_text: string;
  category: string;
  parsed_steps: WorkflowStep[];
  created_at: string;
}

interface WorkflowVersion {
  id: string;
  version_number: number;
  title: string;
  description: string | null;
  sop_text: string;
  category: string;
  parsed_steps: WorkflowStep[];
  created_at: string;
}

interface WorkflowRun {
  id: string;
  workflow_id: string;
  status: string;
  current_step: number;
  step_results: { step: number; notes: string; completed_at: string }[];
  started_at: string;
  completed_at: string | null;
}

interface StepResult {
  step: number;
  notes: string;
  completed_at: string;
}

interface ActivatedModel {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
}

interface StepResultCandidate {
  step?: unknown;
  notes?: unknown;
  completed_at?: unknown;
}

function getStepTimelineClass(index: number, currentStep: number): string {
  if (index < currentStep) return "bg-green-500/10 text-green-500";
  if (index === currentStep) return "bg-primary/10 text-primary ring-2 ring-primary";
  return "bg-muted text-muted-foreground";
}

async function getToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

export default function Workflows() {
  const { toast } = useToast();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newSopText, setNewSopText] = useState("");
  const [newCategory, setNewCategory] = useState("general");
  const [parsing, setParsing] = useState(false);

  // Edit state
  const [editOpen, setEditOpen] = useState(false);
  const [editWorkflow, setEditWorkflow] = useState<Workflow | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editSopText, setEditSopText] = useState("");
  const [editCategory, setEditCategory] = useState("general");
  const [editSaving, setEditSaving] = useState(false);
  const [editReparsing, setEditReparsing] = useState(false);

  // Version history state
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyWorkflow, setHistoryWorkflow] = useState<Workflow | null>(null);
  const [versions, setVersions] = useState<WorkflowVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [restoringVersion, setRestoringVersion] = useState<number | null>(null);

  // Runner state
  const [activeRun, setActiveRun] = useState<{ workflow: Workflow; run: WorkflowRun } | null>(null);
  const [aiGuidance, setAiGuidance] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [stepNotes, setStepNotes] = useState("");

  // Model chat state
  const [models, setModels] = useState<ActivatedModel[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [modelPrompt, setModelPrompt] = useState("");
  const [modelResponse, setModelResponse] = useState("");
  const [modelLoading, setModelLoading] = useState(false);
  const [showModelChat, setShowModelChat] = useState(false);

  const parseStepResults = (value: unknown): StepResult[] => {
    if (!Array.isArray(value)) return [];
    return value
      .filter((item): item is StepResult => {
        if (!item || typeof item !== "object") return false;
        const candidate = item as StepResultCandidate;
        return (
          typeof candidate.step === "number" &&
          typeof candidate.notes === "string" &&
          typeof candidate.completed_at === "string"
        );
      })
      .map((item: any) => ({ step: item.step, notes: item.notes, completed_at: item.completed_at }));
  };

  useEffect(() => {
    void (async () => {
      const token = await getToken();
      await Promise.all([loadWorkflows(token), loadModels(token)]);
    })();
  }, []);

  const loadModels = async (token: string | null) => {
    if (!token) return;
    try {
      const res = await fetch(apiUrl("/api/v1/activated-models"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const payload = await res.json();
      const data: ActivatedModel[] = payload.activated_models ?? [];
      if (data.length > 0) {
        setModels(data);
        setSelectedModel(data[0].model_id);
      }
    } catch (e) {
      console.error("Error loading models:", e);
    }
  };

  const loadWorkflows = async (token: string | null) => {
    if (!token) return;
    try {
      const res = await fetch(apiUrl("/api/v1/workflows"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      setWorkflows((payload.workflows ?? []).map((w: any) => ({
        ...w,
        parsed_steps: Array.isArray(w.parsed_steps) ? w.parsed_steps : [],
      })));
    } catch (e) {
      console.error("Error loading workflows:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newTitle || !newSopText) {
      toast({ title: "Missing fields", description: "Title and SOP text are required", variant: "destructive" });
      return;
    }
    setParsing(true);
    try {
      let parsedSteps: WorkflowStep[] = [];
      let fullResponse = "";
      await streamFromEdgeFunction("workflow-ai", { sop_text: newSopText, action: "parse" }, {
        onDelta: (delta) => { fullResponse += delta; },
        onDone: () => {},
        onError: (err) => { throw new Error(err); },
      });
      const jsonMatch = fullResponse.match(/\[[\s\S]*\]/);
      if (jsonMatch) parsedSteps = JSON.parse(jsonMatch[0]);

      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const res = await fetch(apiUrl("/api/v1/workflows"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle, description: newDescription || null, sop_text: newSopText, category: newCategory, parsed_steps: parsedSteps }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast({ title: "Workflow Created", description: `${parsedSteps.length} steps parsed from your SOP` });
      setCreateOpen(false);
      setNewTitle(""); setNewDescription(""); setNewSopText(""); setNewCategory("general");
      await loadWorkflows(token);
    } catch (e: any) {
      toast({ title: "Error", description: e.message ?? "Failed to create workflow", variant: "destructive" });
    } finally {
      setParsing(false);
    }
  };

  // ─── Edit workflow ────────────────────────────────────────────────────────

  const openEdit = (w: Workflow) => {
    setEditWorkflow(w);
    setEditTitle(w.title);
    setEditDescription(w.description ?? "");
    setEditSopText(w.sop_text);
    setEditCategory(w.category ?? "general");
    setEditOpen(true);
  };

  const handleEditSave = async (reparse = false) => {
    if (!editWorkflow) return;
    if (!editTitle.trim()) {
      toast({ title: "Title required", variant: "destructive" });
      return;
    }
    if (reparse) setEditReparsing(true);
    else setEditSaving(true);

    try {
      let parsedSteps = editWorkflow.parsed_steps;
      if (reparse) {
        let fullResponse = "";
        await streamFromEdgeFunction("workflow-ai", { sop_text: editSopText, action: "parse" }, {
          onDelta: (delta) => { fullResponse += delta; },
          onDone: () => {},
          onError: (err) => { throw new Error(err); },
        });
        const jsonMatch = fullResponse.match(/\[[\s\S]*\]/);
        if (jsonMatch) parsedSteps = JSON.parse(jsonMatch[0]);
      }

      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const res = await fetch(apiUrl(`/api/v1/workflows/${editWorkflow.id}`), {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          title: editTitle.trim(),
          description: editDescription.trim() || null,
          sop_text: editSopText,
          category: editCategory,
          parsed_steps: parsedSteps,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast({ title: "Workflow Updated" });
      setEditOpen(false);
      await loadWorkflows(token);
    } catch (e: any) {
      toast({ title: "Error", description: e.message ?? "Failed to save", variant: "destructive" });
    } finally {
      setEditSaving(false);
      setEditReparsing(false);
    }
  };

  // ─── Version history ──────────────────────────────────────────────────────

  const openHistory = async (w: Workflow) => {
    setHistoryWorkflow(w);
    setHistoryOpen(true);
    setVersionsLoading(true);
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl(`/api/v1/workflows/${w.id}/versions`), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      setVersions(payload.versions ?? []);
    } catch (e: any) {
      toast({ title: "Error loading history", description: e.message, variant: "destructive" });
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleRestore = async (versionNumber: number) => {
    if (!historyWorkflow) return;
    setRestoringVersion(versionNumber);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const res = await fetch(apiUrl(`/api/v1/workflows/${historyWorkflow.id}/restore/${versionNumber}`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast({ title: "Restored", description: `Workflow restored to version ${versionNumber}` });
      setHistoryOpen(false);
      await loadWorkflows(token);
    } catch (e: any) {
      toast({ title: "Error", description: e.message ?? "Restore failed", variant: "destructive" });
    } finally {
      setRestoringVersion(null);
    }
  };

  // ─── Run ──────────────────────────────────────────────────────────────────

  const startRun = async (workflow: Workflow) => {
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(apiUrl("/api/v1/workflow-runs"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ workflow_id: workflow.id, status: "in_progress", current_step: 0, step_results: [] }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      const data = payload.workflow_run;
      setActiveRun({ workflow, run: { ...data, current_step: data.current_step ?? 0, step_results: parseStepResults(data.step_results) } });
      setAiGuidance("");
      setStepNotes("");
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    }
  };

  const getAiAssistance = async () => {
    if (!activeRun) return;
    const step = activeRun.workflow.parsed_steps[activeRun.run.current_step];
    if (!step) return;
    setAiLoading(true);
    setAiGuidance("");
    try {
      const previousNotes = activeRun.run.step_results.map((r: any) => `Step ${r.step + 1}: ${r.notes}`).join("\n");
      await streamFromEdgeFunction("workflow-ai", {
        sop_text: activeRun.workflow.sop_text,
        action: "assist",
        current_step: step,
        step_context: previousNotes,
      }, {
        onDelta: (delta) => { setAiGuidance(prev => prev + delta); },
        onDone: () => { setAiLoading(false); },
        onError: (err) => { console.error(err); setAiLoading(false); },
      });
    } catch (e) {
      setAiLoading(false);
    }
  };

  const completeStep = async () => {
    if (!activeRun) return;
    const newResults = [
      ...activeRun.run.step_results,
      { step: activeRun.run.current_step, notes: stepNotes, completed_at: new Date().toISOString() },
    ];
    const nextStep = activeRun.run.current_step + 1;
    const isComplete = nextStep >= activeRun.workflow.parsed_steps.length;

    const token = await getToken();
    if (!token) return;
    await fetch(apiUrl(`/api/v1/workflow-runs/${activeRun.run.id}`), {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        current_step: nextStep,
        step_results: newResults,
        status: isComplete ? "completed" : "in_progress",
        completed_at: isComplete ? new Date().toISOString() : null,
      }),
    });

    if (isComplete) {
      toast({ title: "Workflow Complete!", description: `All ${activeRun.workflow.parsed_steps.length} steps finished` });
      setActiveRun(null);
    } else {
      setActiveRun({ ...activeRun, run: { ...activeRun.run, current_step: nextStep, step_results: newResults } });
      setStepNotes("");
      setAiGuidance("");
    }
  };

  const deleteWorkflow = async (id: string) => {
    const token = await getToken();
    if (!token) return;
    await fetch(apiUrl(`/api/v1/workflows/${id}`), {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    await loadWorkflows(token);
  };

  const runModelPrompt = async () => {
    if (!modelPrompt.trim() || !selectedModel) return;
    setModelLoading(true);
    setModelResponse("");
    const currentStep = activeRun?.workflow.parsed_steps[activeRun.run.current_step];
    const contextPrefix = currentStep
      ? `[Workflow: ${activeRun.workflow.title} | Step ${activeRun.run.current_step + 1}: ${currentStep.title}]\n\n`
      : "";
    const messages: { role: "user" | "assistant"; content: string }[] = [
      { role: "user", content: contextPrefix + modelPrompt },
    ];
    try {
      await streamChat({
        messages,
        modelId: selectedModel,
        onDelta: (delta) => { setModelResponse(prev => prev + delta); },
        onDone: () => { setModelLoading(false); },
        onError: (err) => {
          console.error(err);
          toast({ title: "Error", description: typeof err === "string" ? err : "Model request failed", variant: "destructive" });
          setModelLoading(false);
        },
      });
    } catch (e) {
      setModelLoading(false);
    }
  };

  const actionTypeColors: Record<string, string> = {
    review: "bg-blue-500/10 text-blue-500",
    analyze: "bg-purple-500/10 text-purple-500",
    verify: "bg-green-500/10 text-green-500",
    input: "bg-orange-500/10 text-orange-500",
    decision: "bg-red-500/10 text-red-500",
    communicate: "bg-cyan-500/10 text-cyan-500",
    document: "bg-yellow-500/10 text-yellow-500",
    calculate: "bg-pink-500/10 text-pink-500",
  };

  const categoryOptions = [
    { value: "general", label: "General" },
    { value: "underwriting", label: "Underwriting" },
    { value: "claims", label: "Claims" },
    { value: "policy-admin", label: "Policy Admin" },
    { value: "compliance", label: "Compliance" },
    { value: "billing", label: "Billing" },
  ];

  // ─── Runner view ──────────────────────────────────────────────────────────
  if (activeRun) {
    const currentStep = activeRun.workflow.parsed_steps[activeRun.run.current_step];
    const progress = (activeRun.run.current_step / activeRun.workflow.parsed_steps.length) * 100;
    return (
      <div className="min-h-screen relative">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          <div className="absolute top-20 left-1/3 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-glow-pulse" />
        </div>
        <div className="relative z-10 space-y-6 animate-fade-in">
          <div className="relative rounded-2xl bg-gradient-hero p-6 border border-border/50 backdrop-blur-sm shadow-premium">
            <div className="absolute inset-0 bg-gradient-subtle rounded-2xl opacity-50" />
            <div className="relative flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-foreground">{activeRun.workflow.title}</h1>
                <p className="text-muted-foreground">Step {activeRun.run.current_step + 1} of {activeRun.workflow.parsed_steps.length}</p>
              </div>
              <Button variant="outline" onClick={() => setActiveRun(null)}>Exit</Button>
            </div>
            <div className="mt-4 h-2 bg-muted rounded-full overflow-hidden">
              <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>

          <div className="flex gap-2 overflow-x-auto pb-2">
            {activeRun.workflow.parsed_steps.map((s: any, i: any) => (
              <div key={`${s.title}-${i}`} className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium shrink-0 ${getStepTimelineClass(i, activeRun.run.current_step)}`}>
                {i < activeRun.run.current_step ? <CheckCircle2 className="h-3 w-3" /> : <Circle className="h-3 w-3" />}
                {s.title}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="bg-card/80 backdrop-blur-sm border-border/50">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Badge className={actionTypeColors[currentStep?.action_type] || "bg-muted text-muted-foreground"}>{currentStep?.action_type}</Badge>
                  <span className="text-xs text-muted-foreground">~{currentStep?.estimated_minutes} min</span>
                </div>
                <CardTitle className="text-lg">{currentStep?.title}</CardTitle>
                <CardDescription>{currentStep?.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Your Notes / Actions Taken</Label>
                  <Textarea value={stepNotes} onChange={(e) => setStepNotes(e.target.value)} placeholder="Document what you did for this step..." rows={4} />
                </div>
                <Button onClick={completeStep} className="w-full">
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  Complete Step
                  {activeRun.run.current_step < activeRun.workflow.parsed_steps.length - 1 && <ArrowRight className="h-4 w-4 ml-2" />}
                </Button>
              </CardContent>
            </Card>

            <Card className="bg-card/80 backdrop-blur-sm border-border/50">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2"><Sparkles className="h-5 w-5 text-primary" />AI Guidance</CardTitle>
                <CardDescription>Get AI suggestions for this step</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {currentStep?.ai_can_assist && (
                  <Button variant="outline" onClick={getAiAssistance} disabled={aiLoading} className="w-full">
                    {aiLoading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Brain className="h-4 w-4 mr-2" />}
                    {aiLoading ? "Generating guidance..." : "Get AI Suggestions"}
                  </Button>
                )}
                {aiGuidance && (
                  <div className="prose prose-sm max-w-none text-foreground bg-muted/50 rounded-lg p-4 max-h-96 overflow-y-auto whitespace-pre-wrap">{aiGuidance}</div>
                )}
                {!currentStep?.ai_can_assist && !aiGuidance && (
                  <p className="text-sm text-muted-foreground italic">This step requires manual action without AI assistance.</p>
                )}
              </CardContent>
            </Card>
          </div>

          {models.length > 0 && (
            <Card className="bg-card/80 backdrop-blur-sm border-border/50">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2"><MessageSquare className="h-5 w-5 text-primary" />Use Model</CardTitle>
                  <Button variant="ghost" size="sm" onClick={() => { setShowModelChat(!showModelChat); setModelResponse(""); setModelPrompt(""); }}>
                    {showModelChat ? "Hide" : "Open"}
                  </Button>
                </div>
                <CardDescription>Query your activated models in context of this workflow step</CardDescription>
              </CardHeader>
              {showModelChat && (
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label>Model</Label>
                    <Select value={selectedModel} onValueChange={setSelectedModel}>
                      <SelectTrigger className="bg-background"><SelectValue placeholder="Select model" /></SelectTrigger>
                      <SelectContent>
                        {models.map((m: any) => <SelectItem key={m.id} value={m.model_id}>{m.model_name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex gap-2">
                    <Textarea
                      value={modelPrompt}
                      onChange={(e) => setModelPrompt(e.target.value)}
                      placeholder="Ask the model anything related to this step..."
                      rows={2}
                      className="flex-1"
                      onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runModelPrompt(); } }}
                    />
                    <Button onClick={runModelPrompt} disabled={modelLoading || !modelPrompt.trim()} size="icon" className="shrink-0 self-end">
                      {modelLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    </Button>
                  </div>
                  {modelResponse && (
                    <div className="prose prose-sm max-w-none text-foreground bg-muted/50 rounded-lg p-4 max-h-80 overflow-y-auto whitespace-pre-wrap">{modelResponse}</div>
                  )}
                </CardContent>
              )}
            </Card>
          )}

          {activeRun.run.step_results.length > 0 && (
            <Card className="bg-card/80 backdrop-blur-sm border-border/50">
              <CardHeader><CardTitle className="text-sm">Completed Steps</CardTitle></CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {activeRun.run.step_results.map((r: any) => (
                    <div key={`${r.step}-${r.completed_at}`} className="flex items-start gap-2 text-sm">
                      <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                      <div>
                        <span className="font-medium">{activeRun.workflow.parsed_steps[r.step]?.title}</span>
                        {r.notes && <p className="text-muted-foreground">{r.notes}</p>}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    );
  }

  // ─── Main list view ───────────────────────────────────────────────────────
  return (
    <div className="min-h-screen relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-1/3 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-glow-pulse" />
        <div className="absolute bottom-20 right-1/3 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-glow-pulse" style={{ animationDelay: "2s" }} />
      </div>

      <div className="relative z-10 space-y-6 animate-fade-in">
        {/* Header */}
        <div className="relative rounded-2xl bg-gradient-hero p-8 border border-border/50 backdrop-blur-sm shadow-premium">
          <div className="absolute inset-0 bg-gradient-subtle rounded-2xl opacity-50" />
          <div className="relative flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg bg-primary/10">
                  <FileText className="h-8 w-8 text-primary animate-float" />
                </div>
                <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">Workflows</h1>
              </div>
              <p className="text-muted-foreground text-lg">Create SOPs in natural language and let AI guide you step-by-step</p>
            </div>
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button className="bg-gradient-to-r from-primary to-primary/80 hover:opacity-90">
                  <Plus className="h-4 w-4 mr-2" /> New Workflow
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader><DialogTitle>Create Workflow from SOP</DialogTitle></DialogHeader>
                <div className="space-y-4 mt-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Title</Label>
                      <Input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="e.g. New Policy Issuance" />
                    </div>
                    <div className="space-y-2">
                      <Label>Category</Label>
                      <Select value={newCategory} onValueChange={setNewCategory}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>{categoryOptions.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Description (optional)</Label>
                    <Input value={newDescription} onChange={(e) => setNewDescription(e.target.value)} placeholder="Brief description" />
                  </div>
                  <div className="space-y-2">
                    <Label>SOP / Procedure (natural language)</Label>
                    <Textarea
                      value={newSopText}
                      onChange={(e) => setNewSopText(e.target.value)}
                      placeholder={`Write your procedure here. Example:\n\n1. Receive submission from broker via email\n2. Log submission in AMS and assign submission ID\n3. Check if the line of business is within our appetite`}
                      rows={10}
                    />
                  </div>
                  <Button onClick={handleCreate} disabled={parsing} className="w-full">
                    {parsing ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> AI is parsing your SOP...</> : <><Sparkles className="h-4 w-4 mr-2" /> Create & Parse with AI</>}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Workflow grid */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : workflows.length === 0 ? (
          <Card className="bg-card/80 backdrop-blur-sm border-border/50">
            <CardContent className="pt-6 text-center py-16">
              <FileText className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-medium mb-2">No Workflows Yet</h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">Write a procedure in plain language and AI will parse it into actionable steps</p>
              <Button onClick={() => setCreateOpen(true)}><Plus className="h-4 w-4 mr-2" /> Create Your First Workflow</Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {workflows.map((w: any) => (
              <Card key={w.id} className="bg-card/80 backdrop-blur-sm border-border/50 hover:shadow-elevated transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <Badge variant="outline" className="mb-2">{w.category}</Badge>
                      <CardTitle className="text-base">{w.title}</CardTitle>
                      {w.description && <CardDescription className="mt-1">{w.description}</CardDescription>}
                    </div>
                    <div className="flex items-center gap-1 ml-2 shrink-0">
                      <Button variant="ghost" size="icon" onClick={() => openEdit(w)} className="text-muted-foreground hover:text-foreground h-8 w-8">
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => openHistory(w)} className="text-muted-foreground hover:text-foreground h-8 w-8">
                        <History className="h-3.5 w-3.5" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => deleteWorkflow(w.id)} className="text-muted-foreground hover:text-destructive h-8 w-8">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 mb-4">
                    {w.parsed_steps.slice(0, 3).map((s: any, i: any) => (
                      <div key={`${w.id}-${s.title}-${i}`} className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Circle className="h-3 w-3 shrink-0" />
                        <span className="truncate">{s.title}</span>
                      </div>
                    ))}
                    {w.parsed_steps.length > 3 && <p className="text-xs text-muted-foreground pl-5">+{w.parsed_steps.length - 3} more steps</p>}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">{w.parsed_steps.length} steps</span>
                    <Button size="sm" onClick={() => startRun(w)}><Play className="h-3 w-3 mr-1" /> Run</Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* ─── Edit Dialog ─────────────────────────────────────────────────── */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader><DialogTitle>Edit Workflow</DialogTitle></DialogHeader>
          <div className="space-y-4 mt-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Category</Label>
                <Select value={editCategory} onValueChange={setEditCategory}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{categoryOptions.map(o => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description (optional)</Label>
              <Input value={editDescription} onChange={(e) => setEditDescription(e.target.value)} placeholder="Brief description" />
            </div>
            <div className="space-y-2">
              <Label>SOP / Procedure</Label>
              <Textarea value={editSopText} onChange={(e) => setEditSopText(e.target.value)} rows={10} />
            </div>
            <div className="flex gap-2">
              <Button onClick={() => handleEditSave(false)} disabled={editSaving || editReparsing} className="flex-1">
                {editSaving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Save Changes
              </Button>
              <Button onClick={() => handleEditSave(true)} disabled={editSaving || editReparsing} variant="outline" className="flex-1">
                {editReparsing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
                Save & Re-parse Steps
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ─── Version History Sheet ────────────────────────────────────────── */}
      <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
        <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <History className="h-5 w-5" />
              Version History
            </SheetTitle>
            {historyWorkflow && <p className="text-sm text-muted-foreground">{historyWorkflow.title}</p>}
          </SheetHeader>

          <div className="mt-6 space-y-3">
            {versionsLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : versions.length === 0 ? (
              <div className="text-center py-12">
                <History className="h-10 w-10 mx-auto mb-3 text-muted-foreground opacity-40" />
                <p className="text-sm text-muted-foreground">No previous versions yet.</p>
                <p className="text-xs text-muted-foreground mt-1">Versions are saved automatically when you edit this workflow.</p>
              </div>
            ) : (
              versions.map((v) => (
                <Card key={v.id} className="bg-card/80 border-border/50">
                  <CardContent className="pt-4 pb-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="text-xs shrink-0">v{v.version_number}</Badge>
                          <span className="text-xs text-muted-foreground truncate">
                            {new Date(v.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-sm font-medium truncate">{v.title}</p>
                        {v.description && <p className="text-xs text-muted-foreground truncate">{v.description}</p>}
                        <p className="text-xs text-muted-foreground mt-1">{(v.parsed_steps ?? []).length} steps · {v.category}</p>
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRestore(v.version_number)}
                        disabled={restoringVersion !== null}
                        className="shrink-0"
                      >
                        {restoringVersion === v.version_number
                          ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          : <RotateCcw className="h-3.5 w-3.5 mr-1" />}
                        Restore
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}