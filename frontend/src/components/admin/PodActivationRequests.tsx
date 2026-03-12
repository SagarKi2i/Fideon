import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { CheckCircle2, XCircle, Clock, Package, User } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";

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
}

export function PodActivationRequests() {
  const { toast } = useToast();
  const [requests, setRequests] = useState<ActivationRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState<Record<string, string>>({});
  const [showRejectInput, setShowRejectInput] = useState<string | null>(null);

  useEffect(() => {
    loadRequests();
  }, []);

  const loadRequests = async () => {
    try {
      const { data, error } = await supabase
        .from("pod_activation_requests")
        .select("*")
        .order("requested_at", { ascending: false });

      if (error) throw error;
      setRequests(data || []);
    } catch (error) {
      console.error("Error loading requests:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (request: ActivationRequest) => {
    setProcessingId(request.id);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      // Insert into activated_models
      const { error: insertError } = await supabase
        .from("activated_models")
        .insert([{
          user_id: request.user_id,
          model_id: request.model_id,
          model_name: request.model_name,
          domain: request.domain as "banking" | "healthcare" | "insurance" | "legal" | "travel",
        }]);

      if (insertError) {
        if (insertError.code === "23505") {
          // Already activated, just update request status
        } else {
          throw insertError;
        }
      }

      // Update request status
      const { error: updateError } = await supabase
        .from("pod_activation_requests")
        .update({
          status: "approved",
          reviewed_at: new Date().toISOString(),
          reviewed_by: user.id,
        })
        .eq("id", request.id);

      if (updateError) throw updateError;

      toast({
        title: "Request Approved",
        description: `${request.model_name} has been activated for the user`,
      });

      loadRequests();
    } catch (error) {
      console.error("Error approving request:", error);
      toast({
        title: "Error",
        description: "Failed to approve request",
        variant: "destructive",
      });
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (request: ActivationRequest) => {
    setProcessingId(request.id);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { error } = await supabase
        .from("pod_activation_requests")
        .update({
          status: "rejected",
          reviewed_at: new Date().toISOString(),
          reviewed_by: user.id,
          rejection_reason: rejectionReason[request.id] || null,
        })
        .eq("id", request.id);

      if (error) throw error;

      toast({
        title: "Request Rejected",
        description: `Activation request for ${request.model_name} has been rejected`,
      });

      setShowRejectInput(null);
      loadRequests();
    } catch (error) {
      console.error("Error rejecting request:", error);
      toast({
        title: "Error",
        description: "Failed to reject request",
        variant: "destructive",
      });
    } finally {
      setProcessingId(null);
    }
  };

  const pendingRequests = requests.filter(r => r.status === "pending");
  const processedRequests = requests.filter(r => r.status !== "pending");

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
              {pendingRequests.map((request) => (
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
                      {showRejectInput === request.id ? (
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setShowRejectInput(null)}
                          >
                            Cancel
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleReject(request)}
                            disabled={processingId === request.id}
                          >
                            <XCircle className="h-3.5 w-3.5 mr-1" />
                            Confirm Reject
                          </Button>
                        </div>
                      ) : (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setShowRejectInput(request.id)}
                            disabled={processingId === request.id}
                            className="text-destructive hover:text-destructive"
                          >
                            <XCircle className="h-3.5 w-3.5 mr-1" />
                            Reject
                          </Button>
                          <Button
                            size="sm"
                            onClick={() => handleApprove(request)}
                            disabled={processingId === request.id}
                          >
                            <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                            Approve
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  {showRejectInput === request.id && (
                    <Textarea
                      placeholder="Reason for rejection (optional)"
                      value={rejectionReason[request.id] || ""}
                      onChange={(e) =>
                        setRejectionReason((prev) => ({
                          ...prev,
                          [request.id]: e.target.value,
                        }))
                      }
                      className="text-sm"
                      rows={2}
                    />
                  )}
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
              {processedRequests.slice(0, 10).map((request) => (
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
    </div>
  );
}
