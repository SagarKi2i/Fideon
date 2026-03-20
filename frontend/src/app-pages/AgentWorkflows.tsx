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
  Repeat, Calendar, Clock, ChevronDown, ChevronUp, Save, Settings2, Link2
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { format } from "date-fns";
import AgentConfigForm, { AGENT_REGISTRY, type AgentConfig } from "@/components/pipeline/AgentConfigForm";

interface PipelineStep {
  id: string;
  agent_id: string;
  agent_name: string;
  config: AgentConfig;
  pass_output: boolean; // pass output to next step
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

export default function AgentWorkflows() {
  const { toast } = useToast();
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingPipeline, setEditingPipeline] = useState<Pipeline | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form
  const [pipelineName, setPipelineName] = useState("");
  const [pipelineDesc, setPipelineDesc] = useState("");
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [scheduleConfig, setScheduleConfig] = useState<ScheduleConfig>({ enabled: false, type: "recurring" });
  const [cronPreset, setCronPreset] = useState("0 9 * * *");
  const [scheduledDate, setScheduledDate] = useState("");
  const [scheduledTime, setScheduledTime] = useState("09:00");
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    try {
      const { data } = await supabase.from("agent_pipelines").select("*").order("created_at", { ascending: false });
      if (data) setPipelines(data.map((p: any) => ({
        ...p, steps: Array.isArray(p.steps) ? p.steps : [], schedule_config: p.schedule_config || null,
      })));
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const addStep = (agentId: string) => {
    const agent = AGENT_REGISTRY.find(a => a.id === agentId);
    if (!agent) return;
    const newStep: PipelineStep = {
      id: crypto.randomUUID(),
      agent_id: agent.id,
      agent_name: agent.name,
      config: {},
      pass_output: true,
    };
    setSteps(prev => [...prev, newStep]);
    setExpandedStep(steps.length);
  };

  const updateStepConfig = (index: number, config: AgentConfig) => {
    setSteps(prev => prev.map((s, i) => i === index ? { ...s, config } : s));
  };

  const removeStep = (index: number) => {
    setSteps(prev => prev.filter((_, i) => i !== index));
    if (expandedStep === index) setExpandedStep(null);
  };

  const moveStep = (index: number, dir: "up" | "down") => {
    const ni = dir === "up" ? index - 1 : index + 1;
    if (ni < 0 || ni >= steps.length) return;
    const ns = [...steps];
    [ns[index], ns[ni]] = [ns[ni], ns[index]];
    setSteps(ns);
  };

  const handleSave = async () => {
    if (!pipelineName.trim() || steps.length === 0) {
      toast({ title: "Missing fields", description: "Name and at least one agent required", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const schedConfig: ScheduleConfig | null = scheduleConfig.enabled ? {
        ...scheduleConfig,
        cron_expression: scheduleConfig.type === "recurring" ? cronPreset : undefined,
        scheduled_at: scheduleConfig.type === "one_time" && scheduledDate ? `${scheduledDate}T${scheduledTime}` : undefined,
      } : null;

      if (editingPipeline) {
        const { error } = await supabase.from("agent_pipelines")
          .update({ name: pipelineName, description: pipelineDesc || null, steps: steps as any, schedule_config: schedConfig as any } as any)
          .eq("id", editingPipeline.id);
        if (error) throw error;
        toast({ title: "Pipeline Updated" });
      } else {
        const { error } = await supabase.from("agent_pipelines").insert({
          user_id: user.id, name: pipelineName, description: pipelineDesc || null,
          steps: steps as any, schedule_config: schedConfig as any,
        } as any);
        if (error) throw error;
        toast({ title: "Pipeline Created", description: `${steps.length} agent${steps.length > 1 ? "s" : ""} connected` });
      }
      resetForm(); setCreateOpen(false); loadData();
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    } finally { setSaving(false); }
  };

  const deletePipeline = async (id: string) => {
    await supabase.from("agent_pipelines").delete().eq("id", id);
    loadData();
  };

  const togglePipeline = async (id: string, current: boolean) => {
    await supabase.from("agent_pipelines").update({ is_active: !current } as any).eq("id", id);
    setPipelines(prev => prev.map(p => p.id === id ? { ...p, is_active: !current } : p));
  };

  const openEdit = (pipeline: Pipeline) => {
    setEditingPipeline(pipeline);
    setPipelineName(pipeline.name);
    setPipelineDesc(pipeline.description || "");
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

  if (loading) {
    return <div className="flex items-center justify-center h-[calc(100vh-4rem)]"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>;
  }

  // Group agents by category
  const agentsByCategory = AGENT_REGISTRY.reduce((acc, a) => {
    if (!acc[a.category]) {
      acc[a.category] = [];
    }
    acc[a.category].push(a);
    return acc;
  }, {} as Record<string, typeof AGENT_REGISTRY>);

  return (
    <div className="min-h-screen relative">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-1/3 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-glow-pulse" />
      </div>

      <div className="relative z-10 space-y-6 animate-fade-in">
        {/* Header */}
        <div className="relative rounded-2xl bg-gradient-hero p-6 border border-border/50 backdrop-blur-sm shadow-premium">
          <div className="absolute inset-0 bg-gradient-subtle rounded-2xl opacity-50" />
          <div className="relative flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg bg-primary/10"><Zap className="h-7 w-7 text-primary" /></div>
                <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
                  Agent Workflows
                </h1>
              </div>
              <p className="text-muted-foreground">Configure and chain your playground agents into automated pipelines</p>
            </div>
            <Button className="shadow-elevated" onClick={() => { resetForm(); setCreateOpen(true); }}>
              <Plus className="h-4 w-4 mr-2" /> New Pipeline
            </Button>
          </div>
        </div>

        {/* Pipeline Builder Dialog */}
        <Dialog open={createOpen} onOpenChange={(v) => { if (!v) resetForm(); setCreateOpen(v); }}>
          <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{editingPipeline ? "Edit Pipeline" : "Create Agent Pipeline"}</DialogTitle>
            </DialogHeader>
            <div className="space-y-5 pt-2">
              {/* Name & Description */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Pipeline Name</Label>
                  <Input value={pipelineName} onChange={e => setPipelineName(e.target.value)} placeholder="e.g. Renewal Processing Pipeline" />
                </div>
                <div className="space-y-1.5">
                  <Label>Description</Label>
                  <Input value={pipelineDesc} onChange={e => setPipelineDesc(e.target.value)} placeholder="Optional description" />
                </div>
              </div>

              <Separator />

              {/* Agent Chain */}
              <div className="space-y-3">
                <Label className="text-base font-semibold">Agent Pipeline</Label>

                {steps.length === 0 && (
                  <div className="text-center py-6 border border-dashed border-border rounded-xl">
                    <Zap className="h-10 w-10 mx-auto mb-2 text-muted-foreground/50" />
                    <p className="text-sm text-muted-foreground mb-3">Select agents to build your pipeline</p>
                  </div>
                )}

                {steps.map((step, idx) => {
                  const agent = AGENT_REGISTRY.find(a => a.id === step.agent_id);
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
                                <Switch checked={step.pass_output} onCheckedChange={v => setSteps(prev => prev.map((s, i) => i === idx ? { ...s, pass_output: v } : s))} />
                              </div>
                            )}
                          </CardContent>
                        )}
                      </Card>
                    </div>
                  );
                })}

                {/* Agent Selector */}
                <div className="space-y-2 border border-dashed border-border rounded-xl p-3">
                  <Label className="text-xs text-muted-foreground">Add Agent to Pipeline</Label>
                  {Object.entries(agentsByCategory).map(([category, agents]) => (
                    <div key={category} className="space-y-1">
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">{category}</p>
                      <div className="flex flex-wrap gap-1.5">
                        {agents.map(agent => (
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

              {/* Schedule */}
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
                        <SelectContent>{CRON_PRESETS.map(p => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}</SelectContent>
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

              <Button onClick={handleSave} disabled={saving} className="w-full">
                {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                {editingPipeline ? "Update Pipeline" : "Create Pipeline"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Pipelines List */}
        {pipelines.length === 0 ? (
          <Card className="bg-card/80 backdrop-blur-sm border-border/50">
            <CardContent className="pt-6">
              <div className="text-center py-12">
                <Zap className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                <h3 className="text-lg font-medium text-foreground mb-2">No Agent Pipelines</h3>
                <p className="text-muted-foreground mb-6 max-w-md mx-auto">
                  Build a pipeline by chaining playground agents — configure Document Retrieval → Policy Comparison → Quote Generation and more
                </p>
                <Button onClick={() => { resetForm(); setCreateOpen(true); }}>
                  <Plus className="h-4 w-4 mr-2" /> Create First Pipeline
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4">
            {pipelines.map(pipeline => (
              <Card key={pipeline.id} className="bg-card/80 backdrop-blur-sm border-border/50 hover:shadow-elevated transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10"><Zap className="h-5 w-5 text-primary" /></div>
                      <div>
                        <CardTitle className="text-lg">{pipeline.name}</CardTitle>
                        {pipeline.description && <CardDescription>{pipeline.description}</CardDescription>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch checked={pipeline.is_active} onCheckedChange={() => togglePipeline(pipeline.id, pipeline.is_active)} />
                      <Button variant="ghost" size="icon" onClick={() => openEdit(pipeline)}><Settings2 className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" onClick={() => deletePipeline(pipeline.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Step chain visualization */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {pipeline.steps.map((step, i) => (
                      <div key={step.id} className="flex items-center gap-2">
                        <Badge variant="secondary" className="py-1.5 px-3">
                          <span className="text-xs text-muted-foreground mr-1.5">{i + 1}.</span>
                          {step.agent_name}
                        </Badge>
                        {i < pipeline.steps.length - 1 && (
                          <div className="flex items-center gap-1">
                            <ArrowDown className="h-4 w-4 text-primary/50 rotate-[-90deg]" />
                            {step.pass_output && <Link2 className="h-3 w-3 text-primary/40" />}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                    {pipeline.schedule_config?.enabled && (
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {pipeline.schedule_config.type === "recurring"
                          ? CRON_PRESETS.find(p => p.value === pipeline.schedule_config?.cron_expression)?.label || pipeline.schedule_config.cron_expression
                          : pipeline.schedule_config.scheduled_at ? format(new Date(pipeline.schedule_config.scheduled_at), "MMM d, yyyy h:mm a") : "—"
                        }
                      </span>
                    )}
                    <span>{pipeline.steps.length} agent{pipeline.steps.length !== 1 ? "s" : ""} chained</span>
                    <span>Created {format(new Date(pipeline.created_at), "MMM d, yyyy")}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
