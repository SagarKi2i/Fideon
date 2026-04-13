import ModelUpdateBanner from "@/components/ModelUpdateBanner";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Brain, Clock3, PlayCircle, Signal, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { apiUrl } from "@/lib/apiBaseUrl";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface ActivatedModel {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
  activated_at: string | null;
}

interface ModelTelemetry {
  status: "online" | "idle";
  usagePercent: number;
  lastInferenceLabel: string;
}

const DEFAULT_TELEMETRY: ModelTelemetry = {
  status: "idle",
  usagePercent: 0,
  lastInferenceLabel: "No inferences yet",
};

function formatRelativeTime(isoTs: string | null): string {
  if (!isoTs) return "No inferences yet";
  const diffMs = Date.now() - new Date(isoTs).getTime();
  if (!Number.isFinite(diffMs) || diffMs < 0) return "Just now";
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function MyModels() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [models, setModels] = useState<ActivatedModel[]>([]);
  const [telemetryByModelId, setTelemetryByModelId] = useState<Record<string, ModelTelemetry>>({});
  const [loading, setLoading] = useState(true);
  const [deactivatingId, setDeactivatingId] = useState<string | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  useEffect(() => {
    loadActivatedModels();
  }, []);

  const loadActivatedModels = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        navigate("/auth");
        return;
      }
      setCurrentUserId(user.id);

      const { data, error } = await (supabase as any)
        .from("activated_models")
        .select("*")
        .eq("user_id", user.id)
        .order("activated_at", { ascending: false });

      if (error) throw error;
      const nextModels = data || [];
      setModels(nextModels);
      void loadModelTelemetry(user.id, nextModels.map((m: any) => m.model_id));
    } catch (error) {
      console.error("Error loading models:", error);
      toast({
        title: "Error",
        description: "Failed to load activated models",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadModelTelemetry = async (userId: string, modelIds: string[]) => {
    if (!modelIds.length) {
      setTelemetryByModelId({});
      return;
    }

    const { data, error } = await (supabase as any)
      .from("chat_conversations")
      .select("model_id,updated_at")
      .eq("user_id", userId)
      .in("model_id", modelIds);

    if (error) {
      console.error("Error loading model telemetry:", error);
      return;
    }

    const modelStats: Record<string, { count: number; lastUpdatedAt: string | null }> = {};
    for (const row of data || []) {
      const modelId = row.model_id;
      if (!modelId) continue;
      if (!modelStats[modelId]) {
        modelStats[modelId] = { count: 0, lastUpdatedAt: null };
      }
      modelStats[modelId].count += 1;
      if (!modelStats[modelId].lastUpdatedAt || (row.updated_at && row.updated_at > modelStats[modelId].lastUpdatedAt!)) {
        modelStats[modelId].lastUpdatedAt = row.updated_at;
      }
    }

    const maxCount = Math.max(
      1,
      ...Object.values(modelStats).map((s: any) => s.count),
    );

    const nextTelemetry: Record<string, ModelTelemetry> = {};
    for (const modelId of modelIds) {
      const stats = modelStats[modelId];
      if (!stats) {
        nextTelemetry[modelId] = DEFAULT_TELEMETRY;
        continue;
      }

      const usagePercent = Math.min(100, Math.round((stats.count / maxCount) * 100));
      const lastTs = stats.lastUpdatedAt;
      const minsSinceLast =
        lastTs ? Math.floor((Date.now() - new Date(lastTs).getTime()) / 60000) : Number.POSITIVE_INFINITY;
      nextTelemetry[modelId] = {
        status: minsSinceLast <= 15 ? "online" : "idle",
        usagePercent,
        lastInferenceLabel: formatRelativeTime(lastTs),
      };
    }
    setTelemetryByModelId(nextTelemetry);
  };

  useEffect(() => {
    if (!currentUserId) return;
    const channel = supabase
      .channel(`my-models-realtime-${currentUserId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "activated_models", filter: `user_id=eq.${currentUserId}` },
        () => {
          void loadActivatedModels();
        },
      )
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "chat_conversations", filter: `user_id=eq.${currentUserId}` },
        () => {
          void loadActivatedModels();
        },
      )
      .subscribe();

    return () => {
      void supabase.removeChannel(channel);
    };
  }, [currentUserId]);

  const handleDeactivate = async (modelId: string) => {
    try {
      const modelToDelete = models.find((m: any) => m.id === modelId);
      if (!modelToDelete) {
        throw new Error("Selected model not found.");
      }
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        navigate("/auth");
        return;
      }
      const response = await fetch(
        apiUrl(`/api/pod-activation/my-models/${encodeURIComponent(modelToDelete.model_id)}`),
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
          },
        },
      );
      if (!response.ok) {
        const payload = await response.json().catch(() => null);
        throw new Error(payload?.error || "Failed to delete model data.");
      }

      toast({
        title: "Success",
        description: "Model and related data deleted for your account.",
      });

      setDeactivatingId(null);
      loadActivatedModels();
    } catch (error) {
      console.error("Error deactivating model:", error);
      toast({
        title: "Error",
        description: "Failed to deactivate model",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">My Models</h1>
          <p className="text-muted-foreground mt-1">Loading your activated models...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen relative">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-1/3 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-glow-pulse" />
        <div className="absolute bottom-20 right-1/3 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-glow-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <div className="relative z-10 space-y-8 animate-fade-in">
        {/* Model update banner — only visible in Electron when an update is available */}
        <ModelUpdateBanner domain="broker" />

        {/* Hero Header */}
        <div className="relative rounded-2xl bg-gradient-hero p-8 border border-border/50 backdrop-blur-sm shadow-premium">
          <div className="absolute inset-0 bg-gradient-subtle rounded-2xl opacity-50" />
          <div className="relative">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-primary/10">
                <Brain className="h-8 w-8 text-primary animate-float" />
              </div>
              <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
                My Models
              </h1>
            </div>
            <p className="text-muted-foreground text-lg">
              Manage your activated AI models and view their details
            </p>
          </div>
        </div>

        <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card hover:shadow-elevated transition-shadow animate-scale-in">
        <CardHeader>
          <CardTitle className="text-card-foreground">Activated Models</CardTitle>
          <CardDescription>Models ready for use in your workspace</CardDescription>
        </CardHeader>
        <CardContent>
          {models.length === 0 ? (
            <div className="text-center py-12">
              <Brain className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-medium text-foreground mb-2">No Models Activated</h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                Start by browsing the marketplace and activating domain-specific AI models
              </p>
              <Button 
                onClick={() => navigate("/marketplace")}
                className="bg-gradient-to-r from-primary to-primary/80 hover:opacity-90 transition-opacity shadow-elevated"
              >
                Browse Marketplace
              </Button>
            </div>
          ) : (
            <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
              {models.map((model: any, index: any) => (
                (() => {
                  const telemetry = telemetryByModelId[model.model_id] || DEFAULT_TELEMETRY;
                  return (
                <Card 
                  key={model.id} 
                  className="group relative overflow-hidden bg-card/80 backdrop-blur-sm border-border/50 hover:border-primary/30 hover:shadow-premium transition-all duration-300 animate-scale-in"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="absolute inset-0 pointer-events-none bg-gradient-primary opacity-0 group-hover:opacity-5 transition-opacity duration-300" />
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="p-2 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
                          <Brain className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <CardTitle className="text-base text-foreground">{model.model_name}</CardTitle>
                          <div className="text-xs mt-1 capitalize flex items-center gap-2 text-muted-foreground">
                            <span>{model.domain}</span>
                            <Badge variant="outline" className="text-[10px]">
                              {telemetry.status}
                            </Badge>
                          </div>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeactivatingId(model.id)}
                        className="h-8 w-8 p-0 text-destructive hover:text-destructive hover:bg-destructive/10 transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-muted-foreground mb-2">
                      Activated: {model.activated_at ? new Date(model.activated_at).toLocaleDateString() : "N/A"}
                    </p>
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground flex items-center gap-1">
                          <Clock3 className="h-3 w-3" />
                          Last inference
                        </span>
                        <span>{telemetry.lastInferenceLabel}</span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground flex items-center gap-1">
                            <Signal className="h-3 w-3" />
                            Usage
                          </span>
                          <span>{telemetry.usagePercent}%</span>
                        </div>
                        <Progress value={telemetry.usagePercent} className="h-1.5" />
                      </div>
                    </div>
                    <Button
                      variant="secondary"
                      size="sm"
                      className="w-full mt-3"
                      onClick={() => navigate(`/playground?model=${encodeURIComponent(model.model_id)}`)}
                    >
                      <PlayCircle className="h-3.5 w-3.5 mr-1.5" />
                      Open Playground
                    </Button>
                  </CardContent>
                </Card>
                  );
                })()
              ))}
            </div>
          )}
        </CardContent>
       </Card>
      </div>

      <AlertDialog open={deactivatingId !== null} onOpenChange={(open) => !open && setDeactivatingId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deactivate Model</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to deactivate this model? You'll no longer have access to it in your workspace until you reactivate it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deactivatingId && handleDeactivate(deactivatingId)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Deactivate
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
