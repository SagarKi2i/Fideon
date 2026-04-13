import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2, XCircle, Clock, Package } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { useUserRole } from "@/hooks/useUserRole";
import { safeLog } from "@/logger";
import { computeAuditIntegrityHash } from "@/lib/auditHash";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ActivationRequest {
  id: string;
  user_id: string;
  model_id: string;
  model_name: string;
  domain: string;
  status: string;
  requested_at: string;
  reviewed_at: string | null;
  rejection_reason: string | null;
  requested_by_full_name?: string | null;
  requested_by_email?: string | null;
  requested_by_tenant_name?: string | null;
  requested_by_tenant_id?: string | null;
}

interface RequestUserContext {
  fullName: string | null;
  email: string | null;
  tenantId: string | null;
  tenantName: string | null;
}

export function PodActivationRequests() {
  const { toast } = useToast();
  const [requests, setRequests] = useState<ActivationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [reviewRequest, setReviewRequest] = useState<ActivationRequest | null>(null);
  const [reviewContext, setReviewContext] = useState<RequestUserContext | null>(null);
  const [loadingReviewContext, setLoadingReviewContext] = useState(false);
  const [reviewRejectionReason, setReviewRejectionReason] = useState("");
  const { role } = useUserRole();

  useEffect(() => {
    loadRequests();
  }, []);

  const loadRequests = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch(apiUrl("/api/pod-activation/requests"), {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, payload, "Failed to load activation requests");
      setRequests(payload.requests ?? []);
    } catch (error) {
      console.error("Error loading requests:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (request: ActivationRequest) => {
    setProcessingId(request.id);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch(apiUrl(`/api/pod-activation/${request.id}/approve`), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, payload, "Failed to approve request");

      // Close modal quickly. Remaining work (audit + refresh) happens in the background.
      setReviewRequest(null);
      setReviewRejectionReason("");

      toast({
        title: "Request Approved",
        description: `${request.model_name} has been activated for the user`,
      });

      void loadRequests();
      window.dispatchEvent(new CustomEvent("dashboard-stats-refresh"));

      // Audit: admin/global_admin approving a pod request (best-effort, non-blocking).
      void (async () => {
        try {
          const { data: { user } } = await supabase.auth.getUser();
          if (!user) return;

          const createdAt = new Date().toISOString();
          const integrity_hash = await computeAuditIntegrityHash({
            user_id: user.id,
            role: role ?? "admin",
            event: `approve_pod:${request.model_id}`,
            action_code: "U",
            outcome_code: 0,
            resource_type: "pod_activation",
            resource_id: request.id,
            created_at: createdAt,
          });

          await (supabase as any).from("auth_audit").insert({
            user_id: user.id,
            email: user.email,
            role: role ?? "admin",
            event: `approve_pod:${request.model_id}`,
            action_code: "U",
            outcome_code: 0,
            resource_type: "pod_activation",
            resource_id: request.id,
            created_at: createdAt,
            integrity_hash,
          });
        } catch (auditError) {
          safeLog.error("auth_audit_pod_approve_error", {
            error: auditError instanceof Error ? auditError.message : String(auditError),
          });
        }
      })();
    } catch (error) {
      console.error("Error approving request:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to approve request",
        variant: "destructive",
      });
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (request: ActivationRequest, rejectionReasonText?: string) => {
    setProcessingId(request.id);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch(apiUrl(`/api/pod-activation/${request.id}/reject`), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          rejection_reason: rejectionReasonText?.trim() || null,
        }),
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, payload, "Failed to reject request");

      // Close modal quickly. Remaining work (audit + refresh) happens in the background.
      toast({
        title: "Request Rejected",
        description: `Activation request for ${request.model_name} has been rejected`,
      });

      setReviewRequest(null);
      setReviewRejectionReason("");

      void loadRequests();
      window.dispatchEvent(new CustomEvent("dashboard-stats-refresh"));

      // Audit: admin/global_admin rejecting a pod request (best-effort, non-blocking).
      void (async () => {
        try {
          const { data: { user } } = await supabase.auth.getUser();
          if (!user) return;

          const createdAt = new Date().toISOString();
          const integrity_hash = await computeAuditIntegrityHash({
            user_id: user.id,
            role: role ?? "admin",
            event: `reject_pod:${request.model_id}`,
            action_code: "U",
            outcome_code: 0,
            resource_type: "pod_activation",
            resource_id: request.id,
            created_at: createdAt,
          });

          await (supabase as any).from("auth_audit").insert({
            user_id: user.id,
            email: user.email,
            role: role ?? "admin",
            event: `reject_pod:${request.model_id}`,
            action_code: "U",
            outcome_code: 0,
            resource_type: "pod_activation",
            resource_id: request.id,
            created_at: createdAt,
            integrity_hash,
          });
        } catch (auditError) {
          safeLog.error("auth_audit_pod_reject_error", {
            error: auditError instanceof Error ? auditError.message : String(auditError),
          });
        }
      })();
    } catch (error) {
      console.error("Error rejecting request:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to reject request",
        variant: "destructive",
      });
    } finally {
      setProcessingId(null);
    }
  };

  const openReviewModal = async (request: ActivationRequest) => {
    setReviewRequest(request);
    setReviewContext(null);
    setReviewRejectionReason("");
    setLoadingReviewContext(true);

    try {
      // Prefer backend-enriched requester context (production-safe; avoids client-side RLS joins).
      if (
        request.requested_by_email !== undefined ||
        request.requested_by_full_name !== undefined ||
        request.requested_by_tenant_name !== undefined
      ) {
        setReviewContext({
          fullName: request.requested_by_full_name ?? null,
          email: request.requested_by_email ?? null,
          tenantId: request.requested_by_tenant_id ?? null,
          tenantName: request.requested_by_tenant_name ?? null,
        });
        return;
      }

      const { data: appUser, error } = await (supabase as any)
        .from("app_users")
        .select("full_name,email,tenant_id")
        .eq("user_id", request.user_id)
        .maybeSingle();

      if (error) throw error;

      let tenantName: string | null = null;
      if (appUser?.tenant_id) {
        const { data: tenant, error: tenantError } = await (supabase as any)
          .from("tenants")
          .select("name")
          .eq("id", appUser.tenant_id)
          .maybeSingle();
        if (tenantError) throw tenantError;
        tenantName = tenant?.name ?? null;
      }

      setReviewContext({
        fullName: appUser?.full_name ?? null,
        email: appUser?.email ?? null,
        tenantId: appUser?.tenant_id ?? null,
        tenantName,
      });
    } catch (error) {
      console.error("Error loading request context:", error);
      setReviewContext(null);
    } finally {
      setLoadingReviewContext(false);
    }
  };

  const pendingRequests = requests.filter((r: any) => r.status === "pending");
  const processedRequests = requests.filter((r: any) => r.status !== "pending");

  if (loading) {
    return (
      <Card className="border-border/50 bg-background/95 backdrop-blur">
        <CardContent className="flex items-center justify-center py-8">
          <p className="text-muted-foreground">Loading requests...</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Pending Requests */}
      <Card className="border-border/50 bg-background/95 backdrop-blur shadow-premium">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-amber-500" />
                Pending Pod Activation Requests
              </CardTitle>
              <CardDescription>Approve or reject user requests to activate AI pods</CardDescription>
            </div>
            {pendingRequests.length > 0 && (
              <Badge className="bg-amber-500/90 text-white">{pendingRequests.length} pending</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {pendingRequests.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <CheckCircle2 className="h-8 w-8 mb-2 text-primary/50" />
              <p>No pending requests</p>
            </div>
          ) : (
            <div className="space-y-4">
              {pendingRequests.map((request: any) => (
                <div
                  key={request.id}
                  className="flex flex-col gap-3 p-4 rounded-lg border border-border/50 bg-card/50 hover:bg-card/80 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <Package className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <p className="font-medium text-sm">{request.model_name}</p>
                        <p className="text-xs text-muted-foreground capitalize">
                          {request.domain} • Requested {new Date(request.requested_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => openReviewModal(request)}
                        disabled={processingId === request.id}
                      >
                        Review Request
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Processed Requests */}
      {processedRequests.length > 0 && (
        <Card className="border-border/50 bg-background/95 backdrop-blur">
          <CardHeader>
            <CardTitle className="text-base">Recent Decisions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {processedRequests.slice(0, 10).map((request: any) => (
                <div
                  key={request.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-muted/30"
                >
                  <div className="flex items-center gap-3">
                    <Package className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{request.model_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {request.reviewed_at && new Date(request.reviewed_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <Badge
                    variant={request.status === "approved" ? "default" : "destructive"}
                    className="text-xs"
                  >
                    {request.status === "approved" ? "Approved" : "Rejected"}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={!!reviewRequest} onOpenChange={(open) => !open && setReviewRequest(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Review Pod Activation Request</DialogTitle>
            <DialogDescription>
              Validate tenant context and approve in one click, or reject with a reason.
            </DialogDescription>
          </DialogHeader>
          {reviewRequest ? (
            <div className="space-y-3 py-2">
              <div className="rounded-md border p-3 text-sm space-y-1">
                <p className="font-medium">{reviewRequest.model_name}</p>
                <p className="text-muted-foreground capitalize">{reviewRequest.domain}</p>
                <p className="text-xs text-muted-foreground">
                  Requested {new Date(reviewRequest.requested_at).toLocaleString()}
                </p>
              </div>

              <div className="rounded-md border p-3 text-sm space-y-1">
                {loadingReviewContext ? (
                  <p className="text-muted-foreground">Loading tenant context...</p>
                ) : (
                  <>
                    <p>
                      <span className="text-muted-foreground">Requested by:</span>{" "}
                      {reviewContext?.fullName ?? reviewContext?.email ?? "Unknown user"}
                    </p>
                    <p><span className="text-muted-foreground">Email:</span> {reviewContext?.email ?? "Not available"}</p>
                    <p><span className="text-muted-foreground">Tenant:</span> {reviewContext?.tenantName ?? (reviewContext?.tenantId ? "Tenant (ID available)" : "Unassigned tenant")}</p>
                    <p className="text-xs text-muted-foreground">Tenant ID: {reviewContext?.tenantId ?? "N/A"}</p>
                    <p className="text-xs text-muted-foreground">User ID: {reviewRequest.user_id}</p>
                  </>
                )}
              </div>

              <Textarea
                placeholder="Reason for rejection (optional)"
                value={reviewRejectionReason}
                onChange={(e) => setReviewRejectionReason(e.target.value)}
                rows={3}
              />
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setReviewRequest(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={!reviewRequest || processingId === reviewRequest?.id}
              onClick={() => reviewRequest && handleReject(reviewRequest, reviewRejectionReason)}
            >
              <XCircle className="h-4 w-4 mr-1.5" />
              Decline
            </Button>
            <Button
              disabled={!reviewRequest || processingId === reviewRequest?.id}
              onClick={() => reviewRequest && handleApprove(reviewRequest)}
            >
              <CheckCircle2 className="h-4 w-4 mr-1.5" />
              One-click Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
