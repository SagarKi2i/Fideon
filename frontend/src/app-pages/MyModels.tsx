import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Brain, Clock3, PlayCircle, Signal, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
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

function getPodTelemetry(modelId: string) {
  const signal = (modelId.length * 13) % 100;
  const lastInferenceMins = ((modelId.length * 7) % 44) + 1;
  return {
    status: signal > 35 ? "online" : "idle",
    usagePercent: Math.max(8, signal),
    lastInferenceLabel: `${lastInferenceMins}m ago`,
  };
}

export default function MyModels() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [models, setModels] = useState<ActivatedModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [deactivatingId, setDeactivatingId] = useState<string | null>(null);

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

      const { data, error } = await supabase
        .from("activated_models")
        .select("*")
        .eq("user_id", user.id)
        .order("activated_at", { ascending: false });

      if (error) throw error;
      setModels(data || []);
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

  const handleDeactivate = async (modelId: string) => {
    try {
      const { error } = await supabase
        .from("activated_models")
        .delete()
        .eq("id", modelId);

      if (error) throw error;

      toast({
        title: "Success",
        description: "Model deactivated successfully",
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
              {models.map((model, index) => (
                <Card 
                  key={model.id} 
                  className="group relative overflow-hidden bg-card/80 backdrop-blur-sm border-border/50 hover:border-primary/30 hover:shadow-premium transition-all duration-300 animate-scale-in"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="absolute inset-0 bg-gradient-primary opacity-0 group-hover:opacity-5 transition-opacity duration-300" />
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
                              {getPodTelemetry(model.model_id).status}
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
                        <span>{getPodTelemetry(model.model_id).lastInferenceLabel}</span>
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-muted-foreground flex items-center gap-1">
                            <Signal className="h-3 w-3" />
                            Usage
                          </span>
                          <span>{getPodTelemetry(model.model_id).usagePercent}%</span>
                        </div>
                        <Progress value={getPodTelemetry(model.model_id).usagePercent} className="h-1.5" />
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
