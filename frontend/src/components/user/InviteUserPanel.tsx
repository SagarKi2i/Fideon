/**
 * InviteUserPanel
 *
 * Shown to authenticated users with role === "user".
 * Lets them request the creation of a new user account.
 * The request is placed in a pending queue and must be approved
 * by an admin or global_admin before the account is created.
 *
 * Also shows the status of all requests the current user has submitted.
 */
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { UserPlus, Loader2, Clock, CheckCircle, XCircle, RefreshCw } from "lucide-react";

interface MyRequest {
  id: string;
  email: string;
  full_name: string | null;
  requested_role: string;
  status: "pending" | "approved" | "rejected";
  rejection_reason: string | null;
  created_at: string;
  reviewed_at: string | null;
}

const STATUS_CONFIG = {
  pending:  { label: "Pending",  color: "bg-amber-100 text-amber-700 border-amber-200",  icon: Clock },
  approved: { label: "Approved", color: "bg-green-100 text-green-700 border-green-200",  icon: CheckCircle },
  rejected: { label: "Rejected", color: "bg-red-100   text-red-700   border-red-200",    icon: XCircle },
};

export function InviteUserPanel() {
  const { toast } = useToast();

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [name, setName]   = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Past requests
  const [requests, setRequests] = useState<MyRequest[]>([]);
  const [loadingRequests, setLoadingRequests] = useState(true);

  const loadMyRequests = async () => {
    setLoadingRequests(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const res = await fetch(apiUrl("/api/my-user-creation-requests"), {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      const data = await readJsonSafe(res);
      if (!res.ok) throw buildApiRequestError(res, data, "Failed to load user-creation requests");
      setRequests(data.requests ?? []);
    } catch (err) {
      console.error("Failed to load my user-creation requests:", err);
    } finally {
      setLoadingRequests(false);
    }
  };

  useEffect(() => { loadMyRequests(); }, []);

  const handleSubmit = async () => {
    if (!email.trim()) {
      toast({ title: "Email required", description: "Please enter the email address.", variant: "destructive" });
      return;
    }

    setSubmitting(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Session expired");

      const res = await fetch(apiUrl("/api/admin-create-user"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          full_name: name.trim() || undefined,
          role: "user",
        }),
      });

      const data = await readJsonSafe(res);
      if (!res.ok) throw buildApiRequestError(res, data, "Request failed");

      toast({
        title: "Request submitted",
        description: data.message ?? "Your request has been sent for admin approval.",
      });

      setName("");
      setEmail("");
      setShowForm(false);
      await loadMyRequests();
    } catch (err: any) {
      toast({ title: "Failed", description: err.message, variant: "destructive" });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="bg-card border-border shadow-card">
      <CardHeader>
        <CardTitle className="text-card-foreground flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-primary" />
          Invite a New User
        </CardTitle>
        <CardDescription>
          Request creation of a new user account. An admin or global admin must approve
          before the account is activated. The new user will receive a password-setup
          email once approved.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* ── Toggle form ─────────────────────────────────────────────────── */}
        <Button
          variant={showForm ? "secondary" : "default"}
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? "Cancel" : "Request New User"}
        </Button>

        {/* ── Request form ─────────────────────────────────────────────────── */}
        {showForm && (
          <div className="p-4 rounded-md border border-border/60 bg-muted/30 space-y-3">
            <p className="text-sm font-medium flex items-center gap-2 text-amber-600">
              <Clock className="h-4 w-4" />
              This request will be sent for admin approval
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="invite-full-name" className="text-xs font-medium text-muted-foreground">Full Name (optional)</Label>
                <Input
                  id="invite-full-name"
                  type="text"
                  placeholder="Jane Smith"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="invite-email" className="text-xs font-medium text-muted-foreground">Email *</Label>
                <Input
                  id="invite-email"
                  type="email"
                  placeholder="jane@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              Role: <span className="font-medium text-foreground">user</span>
              {" · "}No password needed - the new user will receive a setup email on approval.
            </p>

            <Button onClick={handleSubmit} disabled={submitting}>
              {submitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              Submit Request
            </Button>
          </div>
        )}

        {/* ── My past requests ─────────────────────────────────────────────── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">My Submitted Requests</p>
            <Button variant="ghost" size="sm" onClick={loadMyRequests} disabled={loadingRequests}>
              <RefreshCw className="h-3 w-3" />
            </Button>
          </div>

          {loadingRequests ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : requests.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">No requests submitted yet.</p>
          ) : (
            <div className="space-y-2">
              {requests.map((r) => {
                const cfg = STATUS_CONFIG[r.status] ?? STATUS_CONFIG.pending;
                const Icon = cfg.icon;
                return (
                  <div
                    key={r.id}
                    className="flex items-start justify-between gap-3 p-3 rounded-md border border-border/60 bg-muted/10"
                  >
                    <div className="min-w-0 space-y-0.5">
                      <p className="text-sm font-medium truncate">{r.email}</p>
                      {r.full_name && (
                        <p className="text-xs text-muted-foreground">{r.full_name}</p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        Requested: {new Date(r.created_at).toLocaleString()}
                        {r.reviewed_at && ` · Reviewed: ${new Date(r.reviewed_at).toLocaleString()}`}
                      </p>
                      {r.status === "rejected" && r.rejection_reason && (
                        <p className="text-xs text-red-500 mt-1">
                          Reason: {r.rejection_reason}
                        </p>
                      )}
                    </div>
                    <span
                      className={`flex items-center gap-1 shrink-0 text-xs font-semibold px-2 py-1 rounded border ${cfg.color}`}
                    >
                      <Icon className="h-3 w-3" />
                      {cfg.label}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
