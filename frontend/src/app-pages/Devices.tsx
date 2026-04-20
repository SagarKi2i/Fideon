import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { formatDistanceToNow } from "date-fns";
import { Loader2, Monitor, Search, Circle, ExternalLink } from "lucide-react";
import { apiUrl } from "@/lib/apiBaseUrl";

type DeviceStatus = "online" | "offline" | "never_checked_in";

type DeviceRow = {
  id: string;
  device_name: string | null;
  status: DeviceStatus;
  last_seen_at: string | null;
  os_type: string | null;
  app_version: string | null;
  registered_by: string | null;
  registered_by_email?: string | null;
  registered_by_name?: string | null;
  tenant_id: string | null;
  created_at?: string | null;
};

/** Label for breadcrumbs / device details header (same as Linked user column when possible). */
function linkedUserNavState(d: DeviceRow): { linkedUserLabel: string } | undefined {
  const name = d.registered_by_name || undefined;
  const email = d.registered_by_email || undefined;
  if (name && email) return { linkedUserLabel: `${name} (${email})` };
  if (name) return { linkedUserLabel: name };
  if (email) return { linkedUserLabel: email };
  return undefined;
}

export default function Devices() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState<DeviceRow[]>([]);
  const [search, setSearch] = useState("");
  const [tenantNameById, setTenantNameById] = useState<Record<string, string>>({});

  useEffect(() => {
    void checkAccessAndLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkAccessAndLoad = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const user = session?.user;
      if (!user) {
        navigate("/auth");
        return;
      }

      const profRes = await fetch(apiUrl("/api/settings/profile"), {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      const profData = profRes.ok ? await profRes.json() : null;
      const userRole = profData?.profile?.role;

      if (userRole !== "admin" && userRole !== "global_admin") {
        toast({ title: "Access Denied", description: "Admin only", variant: "destructive" });
        navigate("/");
        return;
      }

      await loadDevices();
    } catch {
      navigate("/auth");
    }
  };

  const loadDevices = async () => {
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        navigate("/auth");
        return;
      }

      const resp = await fetch(apiUrl("/api/v1/admin/devices"), {
        method: "GET",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
        },
      });
      const payload = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        const msg = (payload as any)?.error || (payload as any)?.detail || `HTTP ${resp.status}`;
        throw new Error(msg);
      }
      const devices = ((payload as any)?.devices || []) as DeviceRow[];
      setRows(devices);

      const tenantIds = Array.from(new Set((devices || []).map((d: any) => d.tenant_id).filter(Boolean))) as string[];

      if (tenantIds.length) {
        const tRes = await fetch(
          apiUrl(`/api/v1/admin/tenants?ids=${tenantIds.map(encodeURIComponent).join(",")}`),
          { headers: { Authorization: `Bearer ${session.access_token}` } },
        );
        const tData = tRes.ok ? await tRes.json() : null;
        const map: Record<string, string> = {};
        for (const t of (tData?.tenants || []) as any[]) map[t.id] = t.name;
        setTenantNameById(map);
      } else {
        setTenantNameById({});
      }
    } catch (e) {
      console.error("Failed to load devices:", e);
      toast({ title: "Error", description: "Failed to load devices", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((d: any) => {
      const email = String(d.registered_by_email || "");
      const fullName = String(d.registered_by_name || "");
      const tenant = d.tenant_id ? (tenantNameById[d.tenant_id] || "") : "";
      return (
        d.id.toLowerCase().includes(q) ||
        String(d.device_name || "").toLowerCase().includes(q) ||
        String(d.status || "").toLowerCase().includes(q) ||
        fullName.toLowerCase().includes(q) ||
        email.toLowerCase().includes(q) ||
        tenant.toLowerCase().includes(q)
      );
    });
  }, [rows, search, tenantNameById]);

  const statusBadge = (status: DeviceStatus) => {
    if (status === "online") {
      return (
        <Badge variant="outline" className="gap-1 bg-success/10 text-success border-success/20">
          <Circle className="h-2 w-2 fill-success" />
          Online
        </Badge>
      );
    }
    if (status === "offline") {
      return (
        <Badge variant="outline" className="gap-1 bg-muted text-muted-foreground">
          <Circle className="h-2 w-2 fill-muted-foreground" />
          Offline
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="gap-1">
        <Circle className="h-2 w-2" />
        Never Checked In
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Monitor className="h-6 w-6 text-primary" />
            Devices
          </h1>
          <p className="text-muted-foreground mt-1">All registered devices (admin view).</p>
        </div>
        <div className="flex gap-2 items-center">
          <div className="relative">
            <Search className="h-4 w-4 text-muted-foreground absolute left-2 top-1/2 -translate-y-1/2" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by device id, name, tenant, user..."
              className="pl-8 w-[360px] max-w-[80vw]"
            />
          </div>
          <Button variant="outline" onClick={() => void loadDevices()}>
            Refresh
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Registered devices</CardTitle>
          <CardDescription>
            Click a device to open details (requires admin/global admin).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {filtered.length === 0 ? (
            <div className="text-sm text-muted-foreground">No devices found.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Device</TableHead>
                  <TableHead>Tenant</TableHead>
                  <TableHead>Linked user</TableHead>
                  <TableHead>Last seen</TableHead>
                  <TableHead>OS / Version</TableHead>
                  <TableHead className="text-right">Open</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((d) => (
                  <TableRow
                    key={d.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/devices/${d.id}`, { state: linkedUserNavState(d) })}
                  >
                    <TableCell>{statusBadge(d.status)}</TableCell>
                    <TableCell className="min-w-[260px]">
                      <div className="font-medium">{d.device_name || "Unnamed device"}</div>
                      <div className="text-xs text-muted-foreground font-mono break-all">{d.id}</div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {d.tenant_id ? (tenantNameById[d.tenant_id] || d.tenant_id) : "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {d.registered_by
                        ? (() => {
                            const name = d.registered_by_name || undefined;
                            const email = d.registered_by_email || undefined;
                            if (name && email) return `${name} (${email})`;
                            if (name) return name;
                            if (email) return email;
                            return d.registered_by;
                          })()
                        : "—"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {d.last_seen_at ? formatDistanceToNow(new Date(d.last_seen_at), { addSuffix: true }) : "Never"}
                    </TableCell>
                    <TableCell className="text-sm">
                      {d.os_type || "—"} {d.app_version ? `• v${d.app_version}` : ""}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/devices/${d.id}`, { state: linkedUserNavState(d) });
                        }}
                      >
                        <ExternalLink className="h-4 w-4 mr-2" />
                        Details
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
