import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Loader2,
  ShieldAlert,
  Eye,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Filter,
  SortAsc,
  SortDesc,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  listPodAdminQueue,
  adminQueueStats,
  batchReviewPodRuns,
  getPodRunHealthCard,
  type PodAdminQueueFilters,
} from "@/lib/podWorkflowApi";

const STATE_META: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  open: { label: "Open", variant: "secondary" },
  in_progress: { label: "In Progress", variant: "default" },
  approved: { label: "Approved", variant: "default" },
  rework: { label: "Needs Rework", variant: "outline" },
  rejected: { label: "Rejected", variant: "destructive" },
};

const STATS_ORDER: { key: string; label: string; color: string }[] = [
  { key: "open", label: "Open", color: "text-amber-500" },
  { key: "in_progress", label: "In Progress", color: "text-blue-500" },
  { key: "approved", label: "Approved", color: "text-green-500" },
  { key: "rework", label: "Rework", color: "text-orange-500" },
  { key: "rejected", label: "Rejected", color: "text-red-500" },
];

const PAGE_SIZE = 25;

export default function AdminPodQueue() {
  const { podId } = useParams<{ podId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const [stats, setStats] = useState<Record<string, number>>({});
  const [statsLoading, setStatsLoading] = useState(true);

  const [filterStates, setFilterStates] = useState("open,in_progress");
  const [filterConfMin, setFilterConfMin] = useState("");
  const [filterConfMax, setFilterConfMax] = useState("");
  const [orderBy, setOrderBy] = useState<"priority" | "created_at" | "updated_at">("priority");
  const [orderDir, setOrderDir] = useState<"asc" | "desc">("desc");
  const [showFilters, setShowFilters] = useState(false);
  const [filterCalibMin, setFilterCalibMin] = useState("");
  const [filterCalibMax, setFilterCalibMax] = useState("");
  const [filterQg, setFilterQg] = useState<"any" | "pass" | "fail">("any");

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchLoading, setBatchLoading] = useState(false);
  const [healthByRunId, setHealthByRunId] = useState<Record<string, any>>({});

  const visibleItems = useMemo(() => {
    return items.filter((row: any) => {
      const runId = String(row.run_id || "");
      const run = row.pod_extraction_runs || {};
      const conf = Number(run.overall_confidence || 0);
      const health = healthByRunId[runId];
      const calibrated = Number(health?.confidence_evaluation?.calibrated_confidence ?? conf);
      const qg = health?.quality_gate_snapshot?.pass;

      if (filterCalibMin !== "" && calibrated < Number(filterCalibMin) / 100) return false;
      if (filterCalibMax !== "" && calibrated > Number(filterCalibMax) / 100) return false;
      if (filterQg === "pass" && qg !== true) return false;
      if (filterQg === "fail" && qg !== false) return false;
      return true;
    });
  }, [items, healthByRunId, filterCalibMin, filterCalibMax, filterQg]);

  const allVisibleIds = useMemo(() => visibleItems.map((r: any) => r.run_id as string), [visibleItems]);
  const allSelected = allVisibleIds.length > 0 && allVisibleIds.every((id: any) => selected.has(id));
  const someSelected = selected.size > 0;

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      if (!podId) return;
      const data = await adminQueueStats(podId);
      setStats(data);
    } catch {
      // Non-critical
    } finally {
      setStatsLoading(false);
    }
  }, [podId]);

  const buildFilters = useCallback(
    (p: number): PodAdminQueueFilters => {
      const f: PodAdminQueueFilters = {
        states: filterStates || "open,in_progress",
        order_by: orderBy,
        order_dir: orderDir,
        page: p,
        limit: PAGE_SIZE,
      };
      if (filterConfMin !== "") f.conf_min = Number(filterConfMin) / 100;
      if (filterConfMax !== "") f.conf_max = Number(filterConfMax) / 100;
      return f;
    },
    [filterStates, filterConfMin, filterConfMax, orderBy, orderDir]
  );

  const load = useCallback(
    async (p = 1) => {
      if (!podId) return;
      setLoading(true);
      setSelected(new Set());
      try {
        const data = await listPodAdminQueue(podId, buildFilters(p));
        setItems(data.queue);
        setPage(p);
        setHasMore(data.queue.length === PAGE_SIZE);
        setHealthByRunId({});
      } catch (e: any) {
        toast({ title: "Error", description: e.message || "Failed to load queue", variant: "destructive" });
      } finally {
        setLoading(false);
      }
    },
    [podId, buildFilters, toast]
  );

  useEffect(() => {
    if (!podId) return;
    load(1);
    loadStats();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [podId]);

  useEffect(() => {
    if (!podId || items.length === 0) return;
    let cancelled = false;
    const runIds = items.map((i: any) => String(i.run_id || "")).filter(Boolean);
    Promise.all(
      runIds.map(async runId => {
        try {
          const card = await getPodRunHealthCard(podId, runId);
          return [runId, card] as const;
        } catch {
          return [runId, null] as const;
        }
      })
    ).then(entries => {
      if (cancelled) return;
      const next: Record<string, any> = {};
      for (const [runId, card] of entries) {
        if (card) next[runId] = card;
      }
      setHealthByRunId(next);
    });
    return () => {
      cancelled = true;
    };
  }, [podId, items]);

  const toggleOne = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (allSelected) setSelected(new Set());
    else setSelected(new Set(allVisibleIds));
  };

  const handleBatch = async (decision: "approve" | "reject") => {
    if (!podId || selected.size === 0) return;
    setBatchLoading(true);
    try {
      const result = await batchReviewPodRuns(podId, [...selected], decision);
      toast({
        title: decision === "approve" ? "Batch Approved" : "Batch Rejected",
        description: `${result.succeeded} / ${result.total} runs processed.`,
        variant: result.succeeded < result.total ? "destructive" : "default",
      });
      await Promise.all([load(1), loadStats()]);
    } catch (e: any) {
      toast({ title: "Batch failed", description: e.message, variant: "destructive" });
    } finally {
      setBatchLoading(false);
    }
  };

  if (!podId) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Pod Admin Review Queue</h1>
          <p className="text-muted-foreground mt-1">Low-confidence and user-flagged extractions awaiting review</p>
        </div>
        <Button variant="outline" onClick={() => { load(1); loadStats(); }} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {STATS_ORDER.map(({ key, label, color }) => (
          <button
            key={key}
            onClick={() => { setFilterStates(key); load(1); }}
            className="rounded-lg border border-border/60 bg-card p-3 text-left hover:border-primary/40 hover:bg-muted/30 transition-colors"
          >
            <p className={`text-2xl font-bold ${color}`}>
              {statsLoading ? <Loader2 className="h-5 w-5 animate-spin inline" /> : (stats[key] ?? 0)}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
          </button>
        ))}
      </div>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              <ShieldAlert className="h-5 w-5 text-amber-500" />
              Queue Items
            </CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowFilters(v => !v)}
              className={showFilters ? "text-primary" : ""}
            >
              <Filter className="h-4 w-4 mr-1.5" />
              Filters
            </Button>
          </div>
        </CardHeader>

        {showFilters && (
          <CardContent className="border-b border-border/50 pb-4 pt-0">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">State(s)</Label>
                <Select value={filterStates} onValueChange={v => setFilterStates(v)}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open,in_progress">Open + In Progress</SelectItem>
                    <SelectItem value="open">Open only</SelectItem>
                    <SelectItem value="in_progress">In Progress only</SelectItem>
                    <SelectItem value="approved">Approved</SelectItem>
                    <SelectItem value="rework">Needs Rework</SelectItem>
                    <SelectItem value="rejected">Rejected</SelectItem>
                    <SelectItem value="open,in_progress,approved,rework,rejected">All</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Confidence %</Label>
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={filterConfMin}
                    onChange={e => setFilterConfMin(e.target.value)}
                    placeholder="Min"
                    className="h-8 text-xs w-full"
                  />
                  <span className="text-muted-foreground text-xs">–</span>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={filterConfMax}
                    onChange={e => setFilterConfMax(e.target.value)}
                    placeholder="Max"
                    className="h-8 text-xs w-full"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Sort</Label>
                <div className="flex items-center gap-1.5">
                  <Select value={orderBy} onValueChange={v => setOrderBy(v as any)}>
                    <SelectTrigger className="h-8 text-xs flex-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="priority">Priority</SelectItem>
                      <SelectItem value="created_at">Date</SelectItem>
                      <SelectItem value="updated_at">Updated</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 px-2"
                    onClick={() => setOrderDir(d => (d === "asc" ? "desc" : "asc"))}
                  >
                    {orderDir === "asc" ? <SortAsc className="h-3.5 w-3.5" /> : <SortDesc className="h-3.5 w-3.5" />}
                  </Button>
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Calibrated confidence %</Label>
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={filterCalibMin}
                    onChange={e => setFilterCalibMin(e.target.value)}
                    placeholder="Min"
                    className="h-8 text-xs w-full"
                  />
                  <span className="text-muted-foreground text-xs">–</span>
                  <Input
                    type="number"
                    min={0}
                    max={100}
                    value={filterCalibMax}
                    onChange={e => setFilterCalibMax(e.target.value)}
                    placeholder="Max"
                    className="h-8 text-xs w-full"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Quality gate</Label>
                <Select value={filterQg} onValueChange={v => setFilterQg(v as "any" | "pass" | "fail")}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="any">Any</SelectItem>
                    <SelectItem value="pass">Pass only</SelectItem>
                    <SelectItem value="fail">Fail only</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex items-center gap-2 mt-3">
              <Button size="sm" onClick={() => load(1)} disabled={loading}>
                {loading ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Filter className="h-3.5 w-3.5 mr-1.5" />}
                Apply
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFilterStates("open,in_progress");
                  setFilterConfMin("");
                  setFilterConfMax("");
                  setOrderBy("priority");
                  setOrderDir("desc");
                  setFilterCalibMin("");
                  setFilterCalibMax("");
                  setFilterQg("any");
                }}
              >
                Reset
              </Button>
            </div>
          </CardContent>
        )}

        <CardContent className={`space-y-3 ${showFilters ? "pt-4" : ""}`}>
          {someSelected && (
            <div className="flex items-center gap-3 rounded-lg bg-muted/40 border border-border px-3 py-2">
              <span className="text-sm font-medium">{selected.size} selected</span>
              <div className="flex items-center gap-2 ml-auto">
                <Button
                  size="sm"
                  variant="outline"
                  className="text-destructive hover:text-destructive h-7 text-xs"
                  disabled={batchLoading}
                  onClick={() => handleBatch("reject")}
                >
                  {batchLoading ? <Loader2 className="h-3 w-3 mr-1.5 animate-spin" /> : <XCircle className="h-3 w-3 mr-1.5" />}
                  Reject All
                </Button>
                <Button size="sm" className="h-7 text-xs" disabled={batchLoading} onClick={() => handleBatch("approve")}>
                  {batchLoading ? <Loader2 className="h-3 w-3 mr-1.5 animate-spin" /> : <CheckCircle2 className="h-3 w-3 mr-1.5" />}
                  Approve All
                </Button>
              </div>
            </div>
          )}

          {visibleItems.length > 0 && (
            <div className="flex items-center gap-2 px-1 pb-1 border-b border-border/30">
              <Checkbox id="select-all" checked={allSelected} onCheckedChange={toggleAll} />
              <label htmlFor="select-all" className="text-xs text-muted-foreground cursor-pointer select-none">
                Select all on this page
              </label>
              <span className="text-xs text-muted-foreground ml-auto">
                {visibleItems.length} item{visibleItems.length !== 1 ? "s" : ""}
              </span>
            </div>
          )}

          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-4 justify-center">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading…
            </div>
          )}

          {!loading && visibleItems.length === 0 && (
            <div className="text-sm text-muted-foreground text-center py-8">No items match the current filters.</div>
          )}

          {visibleItems.map((row: any) => {
            const run = row.pod_extraction_runs || {};
            const runId = row.run_id as string;
            const conf = Number(run.overall_confidence || 0);
            const pct = Math.round(conf * 100);
            const health = healthByRunId[runId];
            const calibratedPct = Math.round(
              Number(health?.confidence_evaluation?.calibrated_confidence ?? conf) * 100
            );
            const qualityGatePass = health?.quality_gate_snapshot?.pass;
            const stateMeta = STATE_META[row.state] ?? { label: row.state, variant: "outline" as const };
            const isChecked = selected.has(runId);

            return (
              <div
                key={runId}
                className={`border rounded-lg p-3 transition-colors ${
                  isChecked ? "border-primary/50 bg-primary/5" : "border-border/50 bg-card/50"
                }`}
              >
                <div className="flex items-start gap-3">
                  <Checkbox checked={isChecked} onCheckedChange={() => toggleOne(runId)} className="mt-0.5 shrink-0" />

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-sm font-medium">#{runId.slice(0, 8)}</span>
                      <Badge variant={stateMeta.variant} className="text-[10px] h-4">
                        {stateMeta.label}
                      </Badge>
                      <Badge
                        variant={pct >= 85 ? "default" : pct >= 60 ? "secondary" : "destructive"}
                        className="text-[10px] h-4"
                      >
                        {pct}% conf
                      </Badge>
                      <Badge
                        variant={calibratedPct >= 85 ? "default" : calibratedPct >= 60 ? "secondary" : "destructive"}
                        className="text-[10px] h-4"
                      >
                        {calibratedPct}% calibrated
                      </Badge>
                      <Badge
                        variant={qualityGatePass === true ? "default" : qualityGatePass === false ? "destructive" : "outline"}
                        className="text-[10px] h-4"
                      >
                        QG: {qualityGatePass === true ? "PASS" : qualityGatePass === false ? "FAIL" : "N/A"}
                      </Badge>
                      {row.priority != null && row.priority !== 0 && (
                        <Badge variant="outline" className="text-[10px] h-4">
                          P{row.priority}
                        </Badge>
                      )}
                    </div>

                    <p className="text-xs text-muted-foreground mt-1 truncate">
                      {run.source_filename || "Unknown file"} {" · "}
                      {new Date(run.created_at || row.created_at).toLocaleString()}
                    </p>

                    {row.reason && (
                      <p className="text-xs text-muted-foreground mt-0.5">Reason: {row.reason}</p>
                    )}
                  </div>

                  <Button
                    size="sm"
                    onClick={() => navigate(`/admin/pod/${encodeURIComponent(podId)}/${encodeURIComponent(runId)}`)}
                    className="shrink-0 h-7 text-xs"
                  >
                    <Eye className="h-3.5 w-3.5 mr-1.5" />
                    Review
                  </Button>
                </div>
              </div>
            );
          })}

          {(page > 1 || hasMore) && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button variant="outline" size="sm" disabled={page === 1 || loading} onClick={() => load(page - 1)}>
                <ChevronLeft className="h-3.5 w-3.5 mr-1" /> Previous
              </Button>
              <span className="text-xs text-muted-foreground">Page {page}</span>
              <Button
                variant="outline"
                size="sm"
                disabled={!hasMore || loading}
                onClick={() => load(page + 1)}
              >
                Next <ChevronRight className="h-3.5 w-3.5 ml-1" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

