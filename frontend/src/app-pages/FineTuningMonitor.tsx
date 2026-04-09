import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { isElectron } from "@/lib/ollama";
import {
  fetchAcordJobLogTail,
  fetchAcordJobs,
  fetchPodJobLogTail,
  fetchPodJobs,
  type TrainingJobRow,
} from "@/lib/fineTuningMonitorApi";
import { Loader2, RefreshCw, ScrollText, Zap } from "lucide-react";

function badgeVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  const s = (status || "").toLowerCase();
  if (s === "completed") return "default";
  if (s === "running") return "secondary";
  if (s === "failed") return "destructive";
  return "outline";
}

export default function FineTuningMonitor() {
  const { toast } = useToast();
  const [electron, setElectron] = useState(false);
  const [loading, setLoading] = useState(true);
  const [acordJobs, setAcordJobs] = useState<TrainingJobRow[]>([]);
  const [podJobs, setPodJobs] = useState<TrainingJobRow[]>([]);
  const [selectedAcordJobId, setSelectedAcordJobId] = useState<string>("");
  const [selectedPodJobId, setSelectedPodJobId] = useState<string>("");
  const [podId, setPodId] = useState<string>("");
  const [logText, setLogText] = useState<string>("");
  const [progress, setProgress] = useState<number | null>(null);
  const [polling, setPolling] = useState(false);
  const [activeTab, setActiveTab] = useState<"acord" | "pod">("acord");

  useEffect(() => {
    void (async () => setElectron(await isElectron()))();
  }, []);

  const loadAcord = async () => {
    const jobs = await fetchAcordJobs({ limit: 25 });
    setAcordJobs(jobs);
    if (!selectedAcordJobId && jobs[0]?.id) setSelectedAcordJobId(String(jobs[0].id));
  };

  const loadPods = async (pid: string) => {
    if (!pid.trim()) {
      setPodJobs([]);
      return;
    }
    const jobs = await fetchPodJobs(pid.trim(), { limit: 25 });
    setPodJobs(jobs);
    if (!selectedPodJobId && jobs[0]?.id) setSelectedPodJobId(String(jobs[0].id));
  };

  const loadAll = async () => {
    setLoading(true);
    try {
      await loadAcord();
      if (podId.trim()) await loadPods(podId.trim());
    } catch (e) {
      toast({
        title: "Load failed",
        description: e instanceof Error ? e.message : String(e),
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!electron) return;
    void loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [electron]);

  const selectedJob = useMemo(() => {
    if (activeTab === "acord") return acordJobs.find((j) => j.id === selectedAcordJobId);
    return podJobs.find((j) => j.id === selectedPodJobId);
  }, [acordJobs, podJobs, selectedAcordJobId, selectedPodJobId, activeTab]);

  const refreshLog = async () => {
    const jobId = activeTab === "acord" ? selectedAcordJobId : selectedPodJobId;
    if (!jobId) return;
    try {
      if (activeTab === "acord") {
        const tail = await fetchAcordJobLogTail(jobId, 600);
        setLogText(tail.tail_text || "");
        setProgress(tail.progress_percent ?? null);
      } else {
        const pid = podId.trim();
        if (!pid) throw new Error("Pod id is required");
        const tail = await fetchPodJobLogTail(pid, jobId, 600);
        setLogText(tail.tail_text || "");
        setProgress(tail.progress_percent ?? null);
      }
    } catch (e) {
      toast({
        title: "Log fetch failed",
        description: e instanceof Error ? e.message : String(e),
        variant: "destructive",
      });
    }
  };

  useEffect(() => {
    if (!electron) return;
    setLogText("");
    setProgress(null);
    void refreshLog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAcordJobId, selectedPodJobId, activeTab, electron]);

  useEffect(() => {
    if (!electron) return;
    if (!polling) return;
    const id = window.setInterval(() => void refreshLog(), 2000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [polling, electron, selectedAcordJobId, selectedPodJobId, activeTab, podId]);

  if (!electron) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Fine-tuning Monitor</CardTitle>
            <CardDescription>This panel is only available in the Electron app.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Zap className="h-8 w-8 text-primary" />
            Fine-tuning Monitor
          </h1>
          <p className="text-muted-foreground mt-1">
            Live job status + log tail. Polls the API log-tail endpoints and shows best-effort progress percent.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => void loadAll()} disabled={loading} className="gap-2">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
          <Button variant={polling ? "default" : "outline"} onClick={() => setPolling(!polling)} className="gap-2">
            <ScrollText className="h-4 w-4" />
            {polling ? "Live: ON" : "Live: OFF"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Jobs</CardTitle>
          <CardDescription>Select a job and view logs below.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="space-y-4">
            <TabsList>
              <TabsTrigger value="acord">ACORD</TabsTrigger>
              <TabsTrigger value="pod">Pods</TabsTrigger>
            </TabsList>

            <TabsContent value="acord" className="space-y-3">
              {acordJobs.length === 0 ? (
                <p className="text-sm text-muted-foreground">No ACORD training jobs found yet.</p>
              ) : (
                <div className="grid gap-2">
                  {acordJobs.map((j) => (
                    <button
                      key={j.id}
                      className={`w-full text-left rounded-lg border p-3 hover:bg-muted/40 transition ${
                        j.id === selectedAcordJobId ? "border-primary/50 bg-primary/5" : "border-border"
                      }`}
                      onClick={() => setSelectedAcordJobId(j.id)}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <Badge variant={badgeVariant(j.status)} className="capitalize">
                            {j.status}
                          </Badge>
                          <span className="text-xs text-muted-foreground font-mono truncate">job {j.id}</span>
                          <span className="text-xs text-muted-foreground font-mono truncate">run {j.run_id}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {new Date(j.created_at).toLocaleString()}
                        </span>
                      </div>
                      {j.error ? <p className="mt-2 text-xs text-red-600 line-clamp-2">{j.error}</p> : null}
                    </button>
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="pod" className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="pod-id">Pod id</Label>
                <div className="flex gap-2">
                  <Input
                    id="pod-id"
                    placeholder="e.g. insurance"
                    value={podId}
                    onChange={(e) => setPodId(e.target.value)}
                    className="font-mono text-sm"
                  />
                  <Button variant="outline" onClick={() => void loadPods(podId)} disabled={!podId.trim()}>
                    Load
                  </Button>
                </div>
              </div>
              {podId.trim() && podJobs.length === 0 ? (
                <p className="text-sm text-muted-foreground">No pod training jobs found for this pod id.</p>
              ) : null}
              <div className="grid gap-2">
                {podJobs.map((j) => (
                  <button
                    key={j.id}
                    className={`w-full text-left rounded-lg border p-3 hover:bg-muted/40 transition ${
                      j.id === selectedPodJobId ? "border-primary/50 bg-primary/5" : "border-border"
                    }`}
                    onClick={() => setSelectedPodJobId(j.id)}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <Badge variant={badgeVariant(j.status)} className="capitalize">
                          {j.status}
                        </Badge>
                        <span className="text-xs text-muted-foreground font-mono truncate">job {j.id}</span>
                        <span className="text-xs text-muted-foreground font-mono truncate">run {j.run_id}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(j.created_at).toLocaleString()}
                      </span>
                    </div>
                    {j.error ? <p className="mt-2 text-xs text-red-600 line-clamp-2">{j.error}</p> : null}
                  </button>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <CardTitle className="text-base">Log tail</CardTitle>
              <CardDescription>
                {selectedJob ? (
                  <>
                    <span className="font-mono text-xs">job {selectedJob.id}</span>
                    {progress !== null ? <span className="ml-2 text-xs">progress ~{progress}%</span> : null}
                  </>
                ) : (
                  "Select a job above"
                )}
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => void refreshLog()} disabled={!selectedJob}>
              Refresh log
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <pre className="text-xs bg-muted/50 rounded p-3 overflow-x-auto whitespace-pre-wrap">
            {logText || (selectedJob ? "No log output yet." : "—")}
          </pre>
        </CardContent>
      </Card>
    </div>
  );
}

