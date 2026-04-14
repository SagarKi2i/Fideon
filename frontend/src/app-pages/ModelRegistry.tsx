import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Loader2, RefreshCw, Sparkles, CloudDownload, Scale } from "lucide-react";
import {
  fetchModelRegistry,
  recomputeModelRegistryBest,
  syncModelRegistryFromMlflow,
  type ModelRegistryRow,
} from "@/lib/modelRegistryApi";

function fmtMetric(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  return Number(v).toFixed(digits);
}

function fmtLatency(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  return `${Math.round(Number(v))} ms`;
}

export default function ModelRegistry() {
  const { toast } = useToast();
  const [rows, setRows] = useState<ModelRegistryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [taskFilter, setTaskFilter] = useState<string>("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [syncing, setSyncing] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchModelRegistry();
      setRows(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load";
      toast({ title: "Error", description: msg, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const taskKeys = useMemo(() => {
    const s = new Set<string>();
    rows.forEach((r: any) => s.add(r.task_key));
    return Array.from(s).sort();
  }, [rows]);

  const displayedRows = useMemo(
    () => (taskFilter === "all" ? rows : rows.filter((r: any) => r.task_key === taskFilter)),
    [rows, taskFilter],
  );

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const compared = useMemo(
    () => displayedRows.filter((r: any) => selected.has(r.id)),
    [displayedRows, selected],
  );

  const handleSyncMlflow = async () => {
    setSyncing(true);
    try {
      const out = await syncModelRegistryFromMlflow();
      toast({
        title: "MLflow sync complete",
        description: `Inserted ${out.inserted ?? 0}, updated ${out.updated ?? 0} (${out.runs_fetched ?? 0} runs).`,
      });
      await load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Sync failed";
      toast({ title: "MLflow sync", description: msg, variant: "destructive" });
    } finally {
      setSyncing(false);
    }
  };

  const handleRecompute = async () => {
    setRecomputing(true);
    try {
      await recomputeModelRegistryBest();
      toast({ title: "Best models updated", description: "Per-task winners recalculated." });
      await load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Recompute failed";
      toast({ title: "Recompute", description: msg, variant: "destructive" });
    } finally {
      setRecomputing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Sparkles className="h-8 w-8 text-primary" />
            Model registry
          </h1>
          <p className="text-muted-foreground mt-1">
            Insurance-task benchmarks (BLEU, F1, latency). Global catalog plus your tenant after MLflow sync.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading} className="gap-2">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleRecompute()}
            disabled={recomputing || loading}
            className="gap-2"
          >
            {recomputing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scale className="h-4 w-4" />}
            Recompute best
          </Button>
          <Button size="sm" onClick={() => void handleSyncMlflow()} disabled={syncing || loading} className="gap-2">
            {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <CloudDownload className="h-4 w-4" />}
            Sync from MLflow
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Benchmarked models</CardTitle>
              <CardDescription>
                Select rows below to compare metrics side by side. “Best” is highest average of BLEU and F1 (latency as
                tie-breaker).
              </CardDescription>
            </div>
            <div className="w-full sm:w-56">
              <Select value={taskFilter} onValueChange={setTaskFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by task" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All tasks</SelectItem>
                  {taskKeys.map((k: any) => (
                    <SelectItem key={k} value={k}>
                      {k}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-16 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin" />
            </div>
          ) : rows.length === 0 ? (
            <p className="text-center text-muted-foreground py-12">No registry rows yet. Apply the Supabase migration and refresh.</p>
          ) : displayedRows.length === 0 ? (
            <p className="text-center text-muted-foreground py-12">No models for this task filter.</p>
          ) : (
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10" />
                    <TableHead>Task</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead className="text-right">BLEU</TableHead>
                    <TableHead className="text-right">F1</TableHead>
                    <TableHead className="text-right">Latency</TableHead>
                    <TableHead>Scope</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {displayedRows.map((r: any) => (
                    <TableRow key={r.id} className={selected.has(r.id) ? "bg-muted/50" : undefined}>
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={selected.has(r.id)}
                          onChange={() => toggle(r.id)}
                          className="h-4 w-4 rounded border-input"
                          aria-label={`Select ${r.display_name || r.base_model}`}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <span className="font-medium">{r.task_label}</span>
                          <span className="text-xs text-muted-foreground font-mono">{r.task_key}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <span className="font-medium">{r.display_name || r.base_model}</span>
                          <div className="flex flex-wrap gap-1">
                            {r.is_best_for_task && (
                              <Badge className="text-xs bg-emerald-600 hover:bg-emerald-600">Best</Badge>
                            )}
                            <Badge variant="outline" className="text-xs font-mono">
                              {r.base_model}
                            </Badge>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{r.source}</Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono">{fmtMetric(r.bleu_score)}</TableCell>
                      <TableCell className="text-right font-mono">{fmtMetric(r.f1_score)}</TableCell>
                      <TableCell className="text-right font-mono">{fmtLatency(r.latency_ms)}</TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {r.tenant_id ? "Tenant" : "Global"}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {compared.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Comparison</CardTitle>
            <CardDescription>{compared.length} models selected</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead>Task</TableHead>
                  <TableHead className="text-right">BLEU</TableHead>
                  <TableHead className="text-right">F1</TableHead>
                  <TableHead className="text-right">Latency</TableHead>
                  <TableHead>Best</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {compared.map((r: any) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.display_name || r.base_model}</TableCell>
                    <TableCell>{r.task_label}</TableCell>
                    <TableCell className="text-right font-mono">{fmtMetric(r.bleu_score)}</TableCell>
                    <TableCell className="text-right font-mono">{fmtMetric(r.f1_score)}</TableCell>
                    <TableCell className="text-right font-mono">{fmtLatency(r.latency_ms)}</TableCell>
                    <TableCell>{r.is_best_for_task ? "Yes" : "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
