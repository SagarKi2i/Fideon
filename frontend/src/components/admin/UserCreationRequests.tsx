import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { UserPlus, Loader2, CheckCircle, XCircle, RefreshCw } from "lucide-react";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";

interface UserCreationRequest {
  id: string;
  email: string;
  full_name: string | null;
  requested_role: string;
  requester_role: string;
  status: string;
  rejection_reason: string | null;
  created_at: string;
}

interface Props {
  /** "global_admin" sees all pending requests; "admin" sees only user→user requests */
  viewerRole: "global_admin" | "admin";
}

const ROLE_BADGE_COLORS: Record<string, string> = {
  global_admin: "bg-red-100 text-red-700 border-red-200",
  admin:        "bg-amber-100 text-amber-700 border-amber-200",
  user:         "bg-green-100 text-green-700 border-green-200",
  viewer:       "bg-blue-100 text-blue-700 border-blue-200",
  guest:        "bg-gray-100 text-gray-600 border-gray-200",
};

export function UserCreationRequests({ viewerRole }: Props) {
  const { toast } = useToast();
  const [requests, setRequests] = useState<UserCreationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const loadRequests = async () => {
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const res = await fetch(apiUrl("/api/user-creation-requests"), {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      const data = await readJsonSafe(res);
      if (!res.ok) throw buildApiRequestError(res, data, "Failed to load requests");
      setRequests(data.requests || []);
    } catch (err: any) {
      toast({ title: "Error", description: err.message || "Failed to load requests", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRequests(); }, []);

  const handleApprove = async (id: string) => {
    setActioningId(id);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Session expired");

      const res = await fetch(apiUrl(`/api/user-creation-requests/${id}/approve`), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      const data = await readJsonSafe(res);
      if (!res.ok) throw buildApiRequestError(res, data, "Approval failed");

      toast({ title: "Approved", description: data.message });
      await loadRequests();
    } catch (err: any) {
      toast({ title: "Approval failed", description: err.message, variant: "destructive" });
    } finally {
      setActioningId(null);
    }
  };

  const handleReject = async (id: string) => {
    setActioningId(id);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Session expired");

      const res = await fetch(apiUrl(`/api/user-creation-requests/${id}/reject`), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason: rejectReason }),
      });
      const data = await readJsonSafe(res);
      if (!res.ok) throw buildApiRequestError(res, data, "Rejection failed");

      toast({ title: "Rejected", description: data.message });
      setRejectingId(null);
      setRejectReason("");
      await loadRequests();
    } catch (err: any) {
      toast({ title: "Rejection failed", description: err.message, variant: "destructive" });
    } finally {
      setActioningId(null);
    }
  };

  const pendingRequests = requests.filter((r) => r.status === "pending");

  return (
    <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-primary" />
          Pending User Creation Requests
          {pendingRequests.length > 0 && (
            <Badge variant="destructive" className="ml-1">{pendingRequests.length}</Badge>
          )}
        </CardTitle>
        <CardDescription>
          {viewerRole === "global_admin"
            ? "Approve or reject requests from admins (creating admins) and users (creating users)."
            : "Approve or reject user-creation requests submitted by users."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          </div>
        ) : pendingRequests.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground gap-2">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm">No pending requests.</span>
          </div>
        ) : (
          <div className="space-y-3">
            {pendingRequests.map((r) => (
              <div
                key={r.id}
                className="rounded-md border border-border/60 p-4 bg-muted/20 space-y-3"
              >
                {/* Request header */}
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="min-w-0 space-y-1">
                    <p className="text-sm font-medium truncate">{r.email}</p>
                    {r.full_name && (
                      <p className="text-xs text-muted-foreground">{r.full_name}</p>
                    )}
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-muted-foreground">Requested role:</span>
                      <span
                        className={`text-xs font-semibold px-2 py-0.5 rounded border ${
                          ROLE_BADGE_COLORS[r.requested_role] || "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {r.requested_role}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        · Requested by: <span className="font-medium">{r.requester_role}</span>
                      </span>
                      <span className="text-xs text-muted-foreground">
                        · {new Date(r.created_at).toLocaleString()}
                      </span>
                    </div>
                  </div>

                  {/* Action buttons (only if not currently expanding reject form for this row) */}
                  {rejectingId !== r.id && (
                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        size="sm"
                        onClick={() => handleApprove(r.id)}
                        disabled={actioningId === r.id}
                        className="bg-green-600 hover:bg-green-700 text-white"
                      >
                        {actioningId === r.id ? (
                          <Loader2 className="h-3 w-3 animate-spin mr-1" />
                        ) : (
                          <CheckCircle className="h-3 w-3 mr-1" />
                        )}
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => { setRejectingId(r.id); setRejectReason(""); }}
                        disabled={actioningId === r.id}
                        className="border-red-300 text-red-600 hover:bg-red-50"
                      >
                        <XCircle className="h-3 w-3 mr-1" />
                        Reject
                      </Button>
                    </div>
                  )}
                </div>

                {/* Inline rejection reason form */}
                {rejectingId === r.id && (
                  <div className="space-y-2 pt-1 border-t border-border/40">
                    <p className="text-xs font-medium text-muted-foreground">Rejection reason (optional):</p>
                    <textarea
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      rows={2}
                      placeholder="Enter reason..."
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none"
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleReject(r.id)}
                        disabled={actioningId === r.id}
                      >
                        {actioningId === r.id ? (
                          <Loader2 className="h-3 w-3 animate-spin mr-1" />
                        ) : null}
                        Confirm Reject
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => { setRejectingId(null); setRejectReason(""); }}
                        disabled={actioningId === r.id}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="mt-4">
          <Button variant="outline" size="sm" onClick={loadRequests} disabled={loading}>
            <RefreshCw className="h-3 w-3 mr-2" />
            Refresh
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
