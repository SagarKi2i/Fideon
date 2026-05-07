import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import {
  Plus, Trash2, Loader2, Zap, ArrowDown, GripVertical,
  Repeat, Calendar, Clock, ChevronDown, ChevronUp, Save, Link2,
  Activity, TrendingUp, GitBranch, Play, SlidersHorizontal,
  Scale, AlertTriangle, FileText, ArrowRight, Sparkles,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { format } from "date-fns";
import AgentConfigForm, { AGENT_REGISTRY, type AgentConfig } from "@/components/pipeline/AgentConfigForm";

interface PipelineStep {
  id: string;
  agent_id: string;
  agent_name: string;
  config: AgentConfig;
  pass_output: boolean;
}

interface ScheduleConfig {
  enabled: boolean;
  type: "recurring" | "one_time";
  cron_expression?: string;
  scheduled_at?: string;
}

interface Pipeline {
  id: string;
  name: string;
  description: string | null;
  steps: PipelineStep[];
  schedule_config: ScheduleConfig | null;
  is_active: boolean;
  last_run_at: string | null;
  created_at: string;
}

const CRON_PRESETS = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every day at 9 AM", value: "0 9 * * *" },
  { label: "Every Monday at 9 AM", value: "0 9 * * 1" },
  { label: "Weekdays at 9 AM", value: "0 9 * * 1-5" },
  { label: "Monthly (1st)", value: "0 9 1 * *" },
];

const RECOMMENDED_TEMPLATES = [
  { icon: Scale, title: "Claims Processing", setup: "5 min setup", agents: "3 agents" },
  { icon: AlertTriangle, title: "Fraud Detection Pipeline", setup: "8 min setup", agents: "3 agents" },
  { icon: FileText, title: "Policy Document Validation", setup: "4 min setup", agents: "2 agents" },
];

function getCronLabel(cron: string): string {
  return CRON_PRESETS.find((p) => p.value === cron)?.label ?? cron;
}

export default function AgentWorkflows() {
  const { toast } = useToast();
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingPipeline, setEditingPipeline] = useState<Pipeline | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [pipelineName, setPipelineName] = useState("");
  const [pipelineDesc, setPipelineDesc] = useState("");
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig>({ enabled: false, type: "recurring" });
  const [cronPreset, setCronPreset] = useState("0 9 * * *");
  const [scheduledDate, setScheduledDate] = useState("");
  const [scheduledTime, setScheduledTime] = useState("09:00");
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  useEffect(() => {
    void (async () => {
      const { data: { session } } = await supabase.auth.getSession();
      const user = session?.user;
      setCurrentUserId(user?.id ?? null);
      await loadData(user?.id ?? null);
    })();
  }, []);

  const loadData = async (forUserId?: string | null) => {
    try {
      const uid = forUserId ?? currentUserId;
      if (!uid) return;
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) return;
      const res = await fetch(apiUrl("/api/v1/agent-pipelines"), {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) {
        const payload = await res.json();
        setPipelines((payload.agent_pipelines || []).map((p: any) => ({
          ...p, steps: Array.isArray(p.steps) ? p.steps : [], schedule_config: p.schedule_config || null,
        })));
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const addStep = (agentId: string) => {
    const agent = AGENT_REGISTRY.find((a: any) => a.id === agentId);
    if (!agent) return;
    const newStep: PipelineStep = { id: crypto.randomUUID(), agent_id: agent.id, agent_name: agent.name, config: {}, pass_output: true };
    setSteps(prev => [...prev, newStep]);
    setExpandedStep(steps.length);
  };

  const updateStepConfig = (index: number, config: AgentConfig) => {
    setSteps(prev => prev.map((s: any, i: any) => i === index ? { ...s, config } : s));
  };

  const removeStep = (index: number) => {
    setSteps(prev => prev.filter((_: any, i: any) => i !== index));
    if (expandedStep === index) setExpandedStep(null);
  };

  const moveStep = (index: number, dir: "up" | "down") => {
    const ni = dir === "up" ? index - 1 : index + 1;
    if (ni < 0 || ni >= steps.length) return;
    const ns = [...steps];
    [ns[index], ns[ni]] = [ns[ni], ns[index]];
    setSteps(ns);
  };

  const getScheduleConfigPayload = (): ScheduleConfig | null => {
    if (!scheduleConfig.enabled) return null;
    if (scheduleConfig.type === "recurring") return { ...scheduleConfig, cron_expression: cronPreset, scheduled_at: undefined };
    return { ...scheduleConfig, cron_expression: undefined, scheduled_at: scheduledDate ? `${scheduledDate}T${scheduledTime}` : undefined };
  };

  const savePipeline = async () => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) throw new Error("Not authenticated");
    const token = session.access_token;
    const schedConfig = getScheduleConfigPayload();

    if (editingPipeline) {
      const res = await fetch(apiUrl(`/api/v1/agent-pipelines/${encodeURIComponent(editingPipeline.id)}`), {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ name: pipelineName, description: pipelineDesc || null, steps, schedule_config: schedConfig }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      toast({ title: "Workflow Updated" });
      return;
    }

    const res = await fetch(apiUrl("/api/v1/agent-pipelines"), {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ name: pipelineName, description: pipelineDesc || null, steps, schedule_config: schedConfig }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    toast({ title: "Workflow Created", description: `${steps.length} agent${steps.length > 1 ? "s" : ""} connected` });
  };

  const onStepPassOutputChange = (index: number, value: boolean) => {
    setSteps(prev => prev.map((s: any, i: any) => (i === index ? { ...s, pass_output: value } : s)));
  };

  const handleSave = async () => {
    if (!pipelineName.trim() || steps.length === 0) {
      toast({ title: "Missing fields", description: "Name and at least one agent required", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.user) throw new Error("Not authenticated");
      await savePipeline();
      resetForm();
      setCreateOpen(false);
      await loadData(session.user.id);
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    } finally { setSaving(false); }
  };

  const deletePipeline = async (id: string) => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) return;
    await fetch(apiUrl(`/api/v1/agent-pipelines/${encodeURIComponent(id)}`), {
      method: "DELETE",
      headers: { Authorization: `Bearer ${session.access_token}` },
    });
    await loadData();
  };

  const togglePipeline = async (id: string, current: boolean) => {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) return;
    const res = await fetch(apiUrl(`/api/v1/agent-pipelines/${encodeURIComponent(id)}`), {
      method: "PATCH",
      headers: { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: !current }),
    });
    if (res.ok) setPipelines(prev => prev.map((p: any) => p.id === id ? { ...p, is_active: !current } : p));
  };

  const openEdit = (pipeline: Pipeline) => {
    setEditingPipeline(pipeline);
    setPipelineName(pipeline.name);
    setPipelineDesc(pipeline.description ?? "");
    setSteps(pipeline.steps);
    setScheduleConfig(pipeline.schedule_config || { enabled: false, type: "recurring" });
    if (pipeline.schedule_config?.cron_expression) setCronPreset(pipeline.schedule_config.cron_expression);
    setCreateOpen(true);
  };

  const resetForm = () => {
    setPipelineName(""); setPipelineDesc(""); setSteps([]);
    setScheduleConfig({ enabled: false, type: "recurring" });
    setCronPreset("0 9 * * *"); setScheduledDate(""); setScheduledTime("09:00");
    setExpandedStep(null); setEditingPipeline(null);
  };

  // Computed stats
  const totalWorkflows = pipelines.length;
  const activeNow = pipelines.filter((p) => p.is_active).length;
  const scheduled = pipelines.filter((p) => p.schedule_config?.enabled).length;
  const automationRate = totalWorkflows > 0 ? Math.round((activeNow / totalWorkflows) * 100) : 0;

  const agentsByCategory = AGENT_REGISTRY.reduce((acc: any, a: any) => {
    if (!acc[a.category]) acc[a.category] = [];
    acc[a.category].push(a);
    return acc;
  }, {} as Record<string, typeof AGENT_REGISTRY>);

  if (loading) {
    return <div className="flex items-center justify-center h-[calc(100vh-4rem)]"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  return (
    <div className="space-y-6">

      {/* ── Hero Banner ── */}
      <div className="rounded-2xl bg-gradient-to-br from-slate-50 to-indigo-50/40 border border-slate-200/60 p-6 shadow-sm">
        {/* Top row */}
        <div className="flex items-start justify-between mb-5">
          <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-full px-3 py-1">
            <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
            <span className="text-[11px] font-semibold tracking-widest text-slate-600 uppercase">Agent Orchestration Engine</span>
          </div>
          <Button
            className="bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm"
            onClick={() => { resetForm(); setCreateOpen(true); }}
          >
            <Plus className="h-4 w-4 mr-1.5" /> New Workflow
          </Button>
        </div>

        {/* Title */}
        <div className="flex items-center gap-4 mb-2">
          <div className="p-3 rounded-xl bg-indigo-600 shadow-md">
            <Zap className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-slate-800">
            Agent <span className="text-indigo-500">Workflows</span>
          </h1>
        </div>
        <p className="text-slate-500 text-sm mb-6 ml-[72px]">
          Orchestrate intelligent agent pipelines that automate end-to-end insurance operations with surgical precision.
        </p>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <GitBranch className="h-4 w-4 text-slate-400" />
              <span className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase">Total Workflows</span>
            </div>
            <p className="text-3xl font-bold text-slate-800">{totalWorkflows}</p>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="h-4 w-4 text-slate-400" />
              <span className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase">Active Now</span>
              <span className="h-2 w-2 rounded-full bg-green-500 ml-auto" />
            </div>
            <p className="text-3xl font-bold text-slate-800">{activeNow}</p>
          </div>

          <div className="bg-amber-50 rounded-xl border border-amber-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="h-4 w-4 text-amber-500" />
              <span className="text-[11px] font-semibold tracking-widest text-amber-600 uppercase">Scheduled</span>
            </div>
            <p className="text-3xl font-bold text-slate-800">{scheduled}</p>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="h-4 w-4 text-slate-400" />
              <span className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase">Automation Rate</span>
            </div>
            <p className="text-3xl font-bold text-slate-800">{automationRate}%</p>
          </div>
        </div>
      </div>

      {/* ── Pipeline Builder Dialog ── */}
      <Dialog open={createOpen} onOpenChange={(v) => { if (!v) resetForm(); setCreateOpen(v); }}>
        <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingPipeline ? "Edit Workflow" : "Create Agent Workflow"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-5 pt-2">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Workflow Name</Label>
                <Input value={pipelineName} onChange={e => setPipelineName(e.target.value)} placeholder="e.g. Renewal Processing Pipeline" />
              </div>
              <div className="space-y-1.5">
                <Label>Description</Label>
                <Input value={pipelineDesc} onChange={e => setPipelineDesc(e.target.value)} placeholder="Optional description" />
              </div>
            </div>

            <Separator />

            <div className="space-y-3">
              <Label className="text-base font-semibold">Agent Pipeline</Label>
              {steps.length === 0 && (
                <div className="text-center py-6 border border-dashed border-border rounded-xl">
                  <Zap className="h-10 w-10 mx-auto mb-2 text-muted-foreground/50" />
                  <p className="text-sm text-muted-foreground mb-3">Select agents to build your pipeline</p>
                </div>
              )}
              {steps.map((step: any, idx: any) => {
                const agent = AGENT_REGISTRY.find((a: any) => a.id === step.agent_id);
                return (
                  <div key={step.id}>
                    {idx > 0 && (
                      <div className="flex items-center justify-center py-1 gap-2">
                        <ArrowDown className="h-5 w-5 text-primary/60" />
                        {steps[idx - 1].pass_output && (
                          <Badge variant="outline" className="text-[10px] text-primary border-primary/30">
                            <Link2 className="h-2.5 w-2.5 mr-0.5" /> output → input
                          </Badge>
                        )}
                      </div>
                    )}
                    <Card className={`border-border/60 ${expandedStep === idx ? "ring-1 ring-primary/30" : ""}`}>
                      <CardHeader className="py-3 px-4 cursor-pointer" onClick={() => setExpandedStep(expandedStep === idx ? null : idx)}>
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <GripVertical className="h-4 w-4 text-muted-foreground" />
                            <Badge variant="outline" className="text-xs">{idx + 1}</Badge>
                            <span className="font-semibold text-sm">{step.agent_name}</span>
                            {agent && <Badge variant="secondary" className="text-[10px]">{agent.category}</Badge>}
                          </div>
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={e => { e.stopPropagation(); moveStep(idx, "up"); }} disabled={idx === 0}><ChevronUp className="h-3 w-3" /></Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={e => { e.stopPropagation(); moveStep(idx, "down"); }} disabled={idx === steps.length - 1}><ChevronDown className="h-3 w-3" /></Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={e => { e.stopPropagation(); removeStep(idx); }}><Trash2 className="h-3 w-3 text-destructive" /></Button>
                            {expandedStep === idx ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </div>
                        </div>
                      </CardHeader>
                      {expandedStep === idx && (
                        <CardContent className="pt-0 px-4 pb-4 space-y-3">
                          {agent && <p className="text-xs text-muted-foreground">{agent.description}</p>}
                          <AgentConfigForm agentId={step.agent_id} config={step.config} onChange={c => updateStepConfig(idx, c)} />
                          {idx < steps.length - 1 && (
                            <div className="flex items-center justify-between pt-2 border-t border-border/50">
                              <Label className="text-xs flex items-center gap-1"><Link2 className="h-3 w-3" /> Pass output to next agent</Label>
                              <Switch checked={step.pass_output} onCheckedChange={(v) => onStepPassOutputChange(idx, v)} />
                            </div>
                          )}
                        </CardContent>
                      )}
                    </Card>
                  </div>
                );
              })}
              <div className="space-y-2 border border-dashed border-border rounded-xl p-3">
                <Label className="text-xs text-muted-foreground">Add Agent to Pipeline</Label>
                {Object.entries(agentsByCategory).map(([category, agents]: [string, any]) => (
                  <div key={category} className="space-y-1">
                    <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{category}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {agents.map((agent: any) => (
                        <Button key={agent.id} variant="outline" size="sm" className="h-7 text-xs" onClick={() => addStep(agent.id)}>
                          <Plus className="h-3 w-3 mr-1" /> {agent.name}
                        </Button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-base font-semibold">Schedule</Label>
                <Switch checked={scheduleConfig.enabled} onCheckedChange={v => setScheduleConfig(prev => ({ ...prev, enabled: v }))} />
              </div>
              {scheduleConfig.enabled && (
                <div className="space-y-3 pl-1">
                  <div className="flex gap-2">
                    <Button variant={scheduleConfig.type === "recurring" ? "default" : "outline"} size="sm"
                      onClick={() => setScheduleConfig(prev => ({ ...prev, type: "recurring" }))} className="flex-1">
                      <Repeat className="h-3.5 w-3.5 mr-1" /> Recurring
                    </Button>
                    <Button variant={scheduleConfig.type === "one_time" ? "default" : "outline"} size="sm"
                      onClick={() => setScheduleConfig(prev => ({ ...prev, type: "one_time" }))} className="flex-1">
                      <Calendar className="h-3.5 w-3.5 mr-1" /> One-Time
                    </Button>
                  </div>
                  {scheduleConfig.type === "recurring" ? (
                    <Select value={cronPreset} onValueChange={setCronPreset}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>{CRON_PRESETS.map((p: any) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
                    </Select>
                  ) : (
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1"><Label className="text-xs">Date</Label><Input type="date" value={scheduledDate} onChange={e => setScheduledDate(e.target.value)} /></div>
                      <div className="space-y-1"><Label className="text-xs">Time</Label><Input type="time" value={scheduledTime} onChange={e => setScheduledTime(e.target.value)} /></div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <Button onClick={handleSave} disabled={saving} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white">
              {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
              {editingPipeline ? "Update Workflow" : "Create Workflow"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ── Your Workflows ── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-800">Your Workflows</h2>
          <span className="text-sm text-slate-500">{totalWorkflows} total</span>
        </div>

        {pipelines.length === 0 ? (
          <Card className="border-slate-200">
            <CardContent className="py-14 text-center">
              <Zap className="h-14 w-14 mx-auto mb-4 text-slate-300" />
              <h3 className="text-base font-semibold text-slate-700 mb-1">No Workflows Yet</h3>
              <p className="text-sm text-slate-500 max-w-sm mx-auto mb-5">
                Build a workflow by chaining agents — Document Retrieval → Policy Comparison → Quote Generation.
              </p>
              <Button className="bg-indigo-600 hover:bg-indigo-700 text-white" onClick={() => { resetForm(); setCreateOpen(true); }}>
                <Plus className="h-4 w-4 mr-2" /> Create First Workflow
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {pipelines.map((pipeline: any) => (
              <Card key={pipeline.id} className="border-slate-200 shadow-sm hover:shadow-md transition-shadow bg-white overflow-hidden">
                {/* Top color bar */}
                <div className="h-1 bg-indigo-500" />
                <CardContent className="p-4">
                  {/* Title row */}
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2 rounded-xl bg-indigo-100 shrink-0">
                        <Zap className="h-5 w-5 text-indigo-600" />
                      </div>
                      <span className="font-semibold text-slate-800 truncate">{pipeline.name}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Button size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white h-8 px-3">
                        <Play className="h-3.5 w-3.5 mr-1.5 fill-white" /> Run
                      </Button>
                      <Switch
                        checked={pipeline.is_active}
                        onCheckedChange={() => togglePipeline(pipeline.id, pipeline.is_active)}
                      />
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-500" onClick={() => openEdit(pipeline)}>
                        <SlidersHorizontal className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-destructive" onClick={() => deletePipeline(pipeline.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {/* Step chain */}
                  {pipeline.steps.length > 0 && (
                    <div className="mt-3 flex items-center gap-1.5 flex-wrap">
                      {pipeline.steps.map((step: any, i: any) => (
                        <div key={step.id} className="flex items-center gap-1.5">
                          <div className="flex items-center gap-1.5 bg-slate-100 rounded-full px-3 py-1">
                            <span className="text-xs font-semibold text-slate-500">{i + 1}</span>
                            <span className="text-xs font-medium text-slate-700">{step.agent_name}</span>
                          </div>
                          {i < pipeline.steps.length - 1 && (
                            <ArrowRight className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Footer row */}
                  <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <span className={`h-2 w-2 rounded-full ${pipeline.is_active ? "bg-green-500" : "bg-slate-300"}`} />
                        {pipeline.is_active ? "Active" : "Inactive"}
                      </span>
                      {pipeline.schedule_config?.enabled && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {pipeline.schedule_config.type === "recurring"
                            ? getCronLabel(pipeline.schedule_config.cron_expression ?? "")
                            : pipeline.schedule_config.scheduled_at
                              ? format(new Date(pipeline.schedule_config.scheduled_at), "MMM d, yyyy h:mm a")
                              : "—"
                          }
                        </span>
                      )}
                      <span>{pipeline.steps.length} agent{pipeline.steps.length !== 1 ? "s" : ""}</span>
                    </div>
                    <span>{format(new Date(pipeline.created_at), "MMM d, yyyy")}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* ── Recommended Workflows ── */}
      <div>
        <h2 className="text-lg font-semibold text-slate-800 mb-1">Recommended Workflows</h2>
        <p className="text-sm text-slate-500 mb-3">Pre-built templates to get started faster</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {RECOMMENDED_TEMPLATES.map((t) => (
            <Card key={t.title} className="border-slate-200 bg-white hover:shadow-md transition-shadow cursor-pointer group">
              <CardContent className="p-4 flex items-center gap-3">
                <div className="p-2 rounded-lg bg-indigo-50 group-hover:bg-indigo-100 transition-colors shrink-0">
                  <t.icon className="h-5 w-5 text-indigo-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate">{t.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    <Clock className="h-3 w-3 inline mr-1" />
                    {t.setup} · {t.agents}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 shrink-0"
                  onClick={() => { resetForm(); setPipelineName(t.title); setCreateOpen(true); }}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

    </div>
  );
}
