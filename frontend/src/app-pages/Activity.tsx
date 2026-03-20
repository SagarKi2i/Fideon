import { useCallback, useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { safeLog } from "@/logger";
import { ChevronLeft, ChevronRight, Download, RefreshCw } from "lucide-react";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";
import { Skeleton } from "@/components/ui/skeleton";

const PAGE_SIZE = 25;

interface AuditRow {
  id: string;
  user_id: string;
  email: string;
  role: string;
  event: string;
  action_code?: string | null;
  outcome_code?: number | null;
  resource_type?: string | null;
  resource_id?: string | null;
  created_at: string;
}

interface SystemLogRow {
  id: string;
  user_id: string;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  details?: Record<string, unknown> | null;
  ip_address?: string | null;
  user_agent?: string | null;
  previous_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  /** AI decision fields */
  model_id?: string | null;
  prediction?: Record<string, unknown> | null;
  shap_values?: Record<string, number> | null;
  reasoning?: string | null;
  /** Ledger integrity fields */
  integrity_hash?: string | null;
  chain_hash?: string | null;
  sequence_num?: number | null;
  created_at: string;
}

function exportCsv(filename: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return;
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => JSON.stringify(v ?? "");
  const csv = [headers.join(","), ...rows.map((r) => headers.map((h) => escape(r[h])).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function RoleBadge({ role }: Readonly<{ role: string }>) {
  return (
    <Badge variant={role.includes("admin") ? "default" : "outline"} className="text-xs">
      {role}
    </Badge>
  );
}

function ModelBadge({ modelId }: Readonly<{ modelId?: string | null }>) {
  if (!modelId) return <span className="text-xs text-muted-foreground">-</span>;
  return (
    <Badge variant="secondary" className="text-xs font-mono">
      {modelId}
    </Badge>
  );
}

/** Shows top SHAP factors inline next to the reasoning text. */
function ShapFactors({ shapValues }: { shapValues?: Record<string, number> | null }) {
  if (!shapValues) return null;
  const top = Object.entries(shapValues)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 3);
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {top.map(([feat, val]) => (
        <span
          key={feat}
          className={`text-[10px] px-1 rounded border font-mono ${
            val >= 0
              ? "border-emerald-400 text-emerald-700 bg-emerald-50"
              : "border-rose-400 text-rose-700 bg-rose-50"
          }`}
          title={`${feat}: ${val >= 0 ? "+" : ""}${val.toFixed(4)}`}
        >
          {feat} {val >= 0 ? "↑" : "↓"}
        </span>
      ))}
    </div>
  );
}

function OutcomeBadge({ code }: { code?: number | null }) {
  if (typeof code !== "number") return <span className="text-xs text-muted-foreground">-</span>;
  const label = code === 0 ? "Success" : code === 4 ? "Minor" : code === 8 ? "Serious" : code === 12 ? "Major" : String(code);
  return (
    <Badge variant={code === 0 ? "default" : "destructive"} className="text-xs">
      {label}
    </Badge>
  );
}

function Pagination({
  page,
  hasMore,
  onPrev,
  onNext,
}: {
  page: number;
  hasMore: boolean;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="flex items-center justify-between pt-2">
      <Button variant="outline" size="sm" disabled={page === 0} onClick={onPrev}>
        <ChevronLeft className="h-4 w-4 mr-1" />
        Prev
      </Button>
      <span className="text-xs text-muted-foreground">Page {page + 1}</span>
      <Button variant="outline" size="sm" disabled={!hasMore} onClick={onNext}>
        Next
        <ChevronRight className="h-4 w-4 ml-1" />
      </Button>
    </div>
  );
}

// ── Auth Events Tab ───────────────────────────────────────────────────────────

function AuthEventsTab() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [filterEvent, setFilterEvent] = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [pendingEvent, setPendingEvent] = useState("");
  const [pendingFrom, setPendingFrom] = useState("");
  const [pendingTo, setPendingTo] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch PAGE_SIZE + 1 to detect next page
      let q = (supabase as any)
        .from("auth_audit")
        .select("*")
        .order("created_at", { ascending: false })
        .range(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);

      if (filterEvent) q = q.ilike("event", `%${filterEvent}%`);
      if (filterDateFrom) q = q.gte("created_at", filterDateFrom);
      if (filterDateTo) q = q.lte("created_at", filterDateTo + "T23:59:59Z");

      const { data, error } = await q;
      if (error) throw error;
      const fetched = (data || []) as AuditRow[];
      setHasMore(fetched.length > PAGE_SIZE);
      setRows(fetched.slice(0, PAGE_SIZE));
    } catch (e: any) {
      safeLog.error("activity_auth_fetch_error", { error: e.message });
    } finally {
      setLoading(false);
    }
  }, [page, filterEvent, filterDateFrom, filterDateTo]);

  useEffect(() => { load(); }, [load]);

  const applyFilter = () => {
    setFilterEvent(pendingEvent);
    setFilterDateFrom(pendingFrom);
    setFilterDateTo(pendingTo);
    setPage(0);
  };

  const clearFilter = () => {
    setPendingEvent("");
    setPendingFrom("");
    setPendingTo("");
    setFilterEvent("");
    setFilterDateFrom("");
    setFilterDateTo("");
    setPage(0);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4 flex-wrap pb-3">
        <CardTitle className="text-base">Auth Events</CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={() => exportCsv("auth-events.csv", rows as unknown as Record<string, unknown>[])}
          disabled={!rows.length}
        >
          <Download className="h-4 w-4 mr-1" />
          Export CSV
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Filters */}
        <div className="flex flex-wrap gap-3 items-end">
          <div className="space-y-1">
            <Label className="text-xs">Event</Label>
            <Input
              className="h-8 w-36 text-xs"
              placeholder="e.g. login"
              value={pendingEvent}
              onChange={(e) => setPendingEvent(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyFilter()}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">From</Label>
            <Input
              className="h-8 w-36 text-xs"
              type="date"
              value={pendingFrom}
              onChange={(e) => setPendingFrom(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">To</Label>
            <Input
              className="h-8 w-36 text-xs"
              type="date"
              value={pendingTo}
              onChange={(e) => setPendingTo(e.target.value)}
            />
          </div>
          <Button size="sm" className="h-8" onClick={applyFilter}>
            Apply
          </Button>
          <Button size="sm" variant="ghost" className="h-8" onClick={clearFilter}>
            Clear
          </Button>
          <Button size="sm" variant="outline" className="h-8 ml-auto" onClick={load}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* Table */}
        {loading ? (
          <div className="space-y-2 py-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">No auth events found.</p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Outcome</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-nowrap text-xs">
                      {new Date(row.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs">{row.email}</TableCell>
                    <TableCell>
                      <RoleBadge role={row.role} />
                    </TableCell>
                    <TableCell className="text-xs">{row.event}</TableCell>
                    <TableCell className="text-xs">{row.action_code || "-"}</TableCell>
                    <TableCell className="text-xs">
                      {row.resource_type
                        ? `${row.resource_type}${row.resource_id ? `:${row.resource_id}` : ""}`
                        : "-"}
                    </TableCell>
                    <TableCell>
                      <OutcomeBadge code={row.outcome_code} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <Pagination
          page={page}
          hasMore={hasMore}
          onPrev={() => setPage((p) => Math.max(0, p - 1))}
          onNext={() => setPage((p) => p + 1)}
        />
      </CardContent>
    </Card>
  );
}

// ── System Events Tab ─────────────────────────────────────────────────────────

function SystemEventsTab() {
  const [rows, setRows] = useState<SystemLogRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [filterAction, setFilterAction] = useState("");
  const [filterResource, setFilterResource] = useState("");
  const [filterDateFrom, setFilterDateFrom] = useState("");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [pendingAction, setPendingAction] = useState("");
  const [pendingResource, setPendingResource] = useState("");
  const [pendingFrom, setPendingFrom] = useState("");
  const [pendingTo, setPendingTo] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const params = new URLSearchParams({ page: String(page) });
      if (filterAction) params.set("action", filterAction);
      if (filterResource) params.set("resource_type", filterResource);
      if (filterDateFrom) params.set("date_from", filterDateFrom);
      if (filterDateTo) params.set("date_to", filterDateTo + "T23:59:59Z");

      const resp = await fetch(apiUrl(`/api/activity/system?${params}`), {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      const payload = await readJsonSafe(resp);
      if (!resp.ok) throw buildApiRequestError(resp, payload, "Failed to load system logs");
      setRows((payload.logs || []) as SystemLogRow[]);
      setHasMore(!!payload.has_more);
    } catch (e: any) {
      safeLog.error("activity_sys_fetch_error", { error: e.message });
    } finally {
      setLoading(false);
    }
  }, [page, filterAction, filterResource, filterDateFrom, filterDateTo]);

  useEffect(() => { load(); }, [load]);

  const applyFilter = () => {
    setFilterAction(pendingAction);
    setFilterResource(pendingResource);
    setFilterDateFrom(pendingFrom);
    setFilterDateTo(pendingTo);
    setPage(0);
  };

  const clearFilter = () => {
    setPendingAction("");
    setPendingResource("");
    setPendingFrom("");
    setPendingTo("");
    setFilterAction("");
    setFilterResource("");
    setFilterDateFrom("");
    setFilterDateTo("");
    setPage(0);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4 flex-wrap pb-3">
        <CardTitle className="text-base">System Events</CardTitle>
        <Button
          variant="outline"
          size="sm"
          onClick={() => exportCsv("system-events.csv", rows as unknown as Record<string, unknown>[])}
          disabled={!rows.length}
        >
          <Download className="h-4 w-4 mr-1" />
          Export CSV
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Filters */}
        <div className="flex flex-wrap gap-3 items-end">
          <div className="space-y-1">
            <Label className="text-xs">Action</Label>
            <Input
              className="h-8 w-40 text-xs"
              placeholder="e.g. approve_pod"
              value={pendingAction}
              onChange={(e) => setPendingAction(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyFilter()}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Resource Type</Label>
            <Input
              className="h-8 w-40 text-xs"
              placeholder="e.g. user"
              value={pendingResource}
              onChange={(e) => setPendingResource(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && applyFilter()}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">From</Label>
            <Input
              className="h-8 w-36 text-xs"
              type="date"
              value={pendingFrom}
              onChange={(e) => setPendingFrom(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">To</Label>
            <Input
              className="h-8 w-36 text-xs"
              type="date"
              value={pendingTo}
              onChange={(e) => setPendingTo(e.target.value)}
            />
          </div>
          <Button size="sm" className="h-8" onClick={applyFilter}>
            Apply
          </Button>
          <Button size="sm" variant="ghost" className="h-8" onClick={clearFilter}>
            Clear
          </Button>
          <Button size="sm" variant="outline" className="h-8 ml-auto" onClick={load}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* Table */}
        {loading ? (
          <div className="space-y-2 py-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : rows.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">No system events found.</p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-36">When</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Model</TableHead>
                  <TableHead className="min-w-[220px]">AI Reasoning</TableHead>
                  <TableHead>Details</TableHead>
                  <TableHead>IP</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-nowrap text-xs">
                      {new Date(row.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs font-medium">{row.action}</TableCell>
                    <TableCell className="text-xs">
                      {row.resource_type}
                      {row.resource_id ? `:${row.resource_id.slice(0, 8)}…` : ""}
                    </TableCell>
                    <TableCell>
                      <ModelBadge modelId={row.model_id} />
                    </TableCell>
                    <TableCell className="text-xs max-w-sm">
                      {row.reasoning ? (
                        <>
                          <p className="line-clamp-2 text-muted-foreground" title={row.reasoning}>
                            {row.reasoning}
                          </p>
                          <ShapFactors shapValues={row.shap_values} />
                        </>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs max-w-xs truncate">
                      {row.details ? JSON.stringify(row.details) : "-"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {row.ip_address || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <Pagination
          page={page}
          hasMore={hasMore}
          onPrev={() => setPage((p) => Math.max(0, p - 1))}
          onNext={() => setPage((p) => p + 1)}
        />
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Activity() {
  return (
    <div className="space-y-4">
      <Tabs defaultValue="auth">
        <TabsList>
          <TabsTrigger value="auth">Auth Events</TabsTrigger>
          <TabsTrigger value="system">System Events</TabsTrigger>
        </TabsList>
        <TabsContent value="auth" className="mt-4">
          <AuthEventsTab />
        </TabsContent>
        <TabsContent value="system" className="mt-4">
          <SystemEventsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
