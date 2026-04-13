import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Calendar, Clock, Plus, Trash2, Loader2, CalendarClock, Repeat } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { format } from "date-fns";

interface ActivatedModel {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
}

interface AgentSchedule {
  id: string;
  model_id: string;
  model_name: string;
  schedule_type: string;
  cron_expression: string | null;
  scheduled_at: string | null;
  prompt: string;
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

const CRON_PRESETS = [
  { label: "Every hour", value: "0 * * * *" },
  { label: "Every day at 9 AM", value: "0 9 * * *" },
  { label: "Every Monday at 9 AM", value: "0 9 * * 1" },
  { label: "Every weekday at 9 AM", value: "0 9 * * 1-5" },
  { label: "Every 1st of month", value: "0 9 1 * *" },
  { label: "Custom", value: "custom" },
];

export default function AgentSchedules() {
  const { toast } = useToast();
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [schedules, setSchedules] = useState<AgentSchedule[]>([]);
  const [models, setModels] = useState<ActivatedModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // Form state
  const [selectedModel, setSelectedModel] = useState("");
  const [scheduleType, setScheduleType] = useState<"one_time" | "recurring">("recurring");
  const [cronPreset, setCronPreset] = useState("0 9 * * *");
  const [customCron, setCustomCron] = useState("");
  const [scheduledDate, setScheduledDate] = useState("");
  const [scheduledTime, setScheduledTime] = useState("09:00");
  const [prompt, setPrompt] = useState("");

  useEffect(() => {
    void (async () => {
      const { data: { user } } = await supabase.auth.getUser();
      setCurrentUserId(user?.id ?? null);
      await loadData(user?.id ?? null);
    })();
  }, []);

  const loadData = async (userId?: string | null) => {
    try {
      const uid = userId ?? currentUserId;
      if (!uid) return;

      const [modelsRes, schedulesRes] = await Promise.all([
        (supabase as any).from("activated_models").select("*").eq("user_id", uid),
        (supabase as any).from("agent_schedules").select("*").eq("user_id", uid).order("created_at", { ascending: false }),
      ]);

      if (modelsRes.data) {
        setModels(modelsRes.data);
        if (modelsRes.data.length > 0) setSelectedModel(modelsRes.data[0].model_id);
      }
      if (schedulesRes.data) setSchedules(schedulesRes.data as AgentSchedule[]);
    } catch (e) {
      console.error("Error loading data:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!selectedModel || !prompt.trim()) {
      toast({ title: "Missing fields", description: "Please select a model and enter a prompt", variant: "destructive" });
      return;
    }

    const model = models.find((m: any) => m.model_id === selectedModel);
    if (!model) return;

    setSaving(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const cronValue = cronPreset === "custom" ? customCron : cronPreset;
      let scheduledAt: string | null = null;
      let nextRunAt: string | null = null;

      if (scheduleType === "one_time" && scheduledDate && scheduledTime) {
        scheduledAt = new Date(`${scheduledDate}T${scheduledTime}`).toISOString();
        nextRunAt = scheduledAt;
      }

      const { error } = await (supabase as any).from("agent_schedules").insert({
        user_id: user.id,
        model_id: model.model_id,
        model_name: model.model_name,
        schedule_type: scheduleType,
        cron_expression: scheduleType === "recurring" ? cronValue : null,
        scheduled_at: scheduledAt,
        prompt: prompt.trim(),
        next_run_at: nextRunAt,
      } as any);

      if (error) throw error;

      toast({ title: "Schedule Created", description: `Agent "${model.model_name}" has been scheduled` });
      setCreateOpen(false);
      resetForm();
      await loadData(user.id);
    } catch (e: any) {
      toast({ title: "Error", description: e.message, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const toggleSchedule = async (id: string, currentState: boolean) => {
    const { error } = await (supabase as any)
      .from("agent_schedules")
      .update({ is_active: !currentState })
      .eq("id", id)
      .eq("user_id", currentUserId ?? "");
    if (!error) {
      setSchedules(prev => prev.map((s: any) => s.id === id ? { ...s, is_active: !currentState } : s));
    }
  };

  const deleteSchedule = async (id: string) => {
    const { error } = await (supabase as any)
      .from("agent_schedules")
      .delete()
      .eq("id", id)
      .eq("user_id", currentUserId ?? "");
    if (!error) {
      setSchedules(prev => prev.filter((s: any) => s.id !== id));
      toast({ title: "Deleted", description: "Schedule removed" });
    }
  };

  const resetForm = () => {
    setPrompt("");
    setScheduleType("recurring");
    setCronPreset("0 9 * * *");
    setCustomCron("");
    setScheduledDate("");
    setScheduledTime("09:00");
  };

  const getCronLabel = (cron: string | null) => {
    if (!cron) return "—";
    const preset = CRON_PRESETS.find((p: any) => p.value === cron);
    return preset ? preset.label : cron;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

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
                <div className="p-2 rounded-lg bg-primary/10">
                  <CalendarClock className="h-7 w-7 text-primary" />
                </div>
                <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
                  Agent Schedules
                </h1>
              </div>
              <p className="text-muted-foreground">Schedule your playground agents to run automatically</p>
            </div>
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button className="shadow-elevated">
                  <Plus className="h-4 w-4 mr-2" /> New Schedule
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                  <DialogTitle>Create Agent Schedule</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  {/* Model */}
                  <div className="space-y-2">
                    <Label>Agent / Model</Label>
                    <Select value={selectedModel} onValueChange={setSelectedModel}>
                      <SelectTrigger><SelectValue placeholder="Select agent" /></SelectTrigger>
                      <SelectContent>
                        {models.map((m: any) => (
                          <SelectItem key={m.id} value={m.model_id}>{m.model_name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Schedule Type */}
                  <div className="space-y-2">
                    <Label>Schedule Type</Label>
                    <div className="flex gap-2">
                      <Button
                        variant={scheduleType === "recurring" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setScheduleType("recurring")}
                        className="flex-1"
                      >
                        <Repeat className="h-4 w-4 mr-1" /> Recurring
                      </Button>
                      <Button
                        variant={scheduleType === "one_time" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setScheduleType("one_time")}
                        className="flex-1"
                      >
                        <Calendar className="h-4 w-4 mr-1" /> One-Time
                      </Button>
                    </div>
                  </div>

                  {/* Recurring Options */}
                  {scheduleType === "recurring" && (
                    <div className="space-y-2">
                      <Label>Frequency</Label>
                      <Select value={cronPreset} onValueChange={setCronPreset}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {CRON_PRESETS.map((p: any) => (
                            <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {cronPreset === "custom" && (
                        <Input
                          placeholder="e.g. 0 9 * * 1-5"
                          value={customCron}
                          onChange={e => setCustomCron(e.target.value)}
                        />
                      )}
                    </div>
                  )}

                  {/* One-time Options */}
                  {scheduleType === "one_time" && (
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <Label>Date</Label>
                        <Input type="date" value={scheduledDate} onChange={e => setScheduledDate(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label>Time</Label>
                        <Input type="time" value={scheduledTime} onChange={e => setScheduledTime(e.target.value)} />
                      </div>
                    </div>
                  )}

                  {/* Prompt */}
                  <div className="space-y-2">
                    <Label>Prompt</Label>
                    <Textarea
                      value={prompt}
                      onChange={e => setPrompt(e.target.value)}
                      placeholder="Enter the prompt to run on this schedule..."
                      rows={3}
                    />
                  </div>

                  <Button onClick={handleCreate} disabled={saving} className="w-full">
                    {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                    Create Schedule
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Schedules List */}
        {schedules.length === 0 ? (
          <Card className="bg-card/80 backdrop-blur-sm border-border/50">
            <CardContent className="pt-6">
              <div className="text-center py-12">
                <CalendarClock className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                <h3 className="text-lg font-medium text-foreground mb-2">No Scheduled Agents</h3>
                <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                  Create a schedule to run your agents automatically at set times
                </p>
                <Button onClick={() => setCreateOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" /> Create First Schedule
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="bg-card/80 backdrop-blur-sm border-border/50">
            <CardHeader>
              <CardTitle>Active Schedules</CardTitle>
              <CardDescription>{schedules.length} schedule{schedules.length !== 1 ? "s" : ""} configured</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Schedule</TableHead>
                    <TableHead>Prompt</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {schedules.map((schedule: any) => (
                    <TableRow key={schedule.id}>
                      <TableCell className="font-medium">{schedule.model_name}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {schedule.schedule_type === "recurring" ? (
                            <><Repeat className="h-3 w-3 mr-1" /> Recurring</>
                          ) : (
                            <><Clock className="h-3 w-3 mr-1" /> One-Time</>
                          )}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {schedule.schedule_type === "recurring"
                          ? getCronLabel(schedule.cron_expression)
                          : schedule.scheduled_at
                            ? format(new Date(schedule.scheduled_at), "MMM d, yyyy h:mm a")
                            : "—"
                        }
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate text-sm">{schedule.prompt}</TableCell>
                      <TableCell>
                        <Switch
                          checked={schedule.is_active}
                          onCheckedChange={() => toggleSchedule(schedule.id, schedule.is_active)}
                        />
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" onClick={() => deleteSchedule(schedule.id)}>
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
