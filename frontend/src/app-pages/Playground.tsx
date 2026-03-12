import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Loader2, ShoppingCart, Cloud, HardDrive, Brain } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { useNavigate } from "react-router-dom";
import { streamChat } from "@/lib/aiChat";
import { getMockInsuranceResponse } from "@/lib/insuranceMocks";
import PolicyComparisonUI from "@/components/playground/PolicyComparisonUI";
import ACORDParserUI from "@/components/playground/ACORDParserUI";
import ClaimsFNOLUI from "@/components/playground/ClaimsFNOLUI";
import DocumentRetrievalUI from "@/components/playground/DocumentRetrievalUI";
import GenericPromptUI from "@/components/playground/GenericPromptUI";
import QuoteGenerationUI from "@/components/playground/QuoteGenerationUI";
import SubmissionIntakeUI from "@/components/playground/SubmissionIntakeUI";
import ClaimsAdjudicationUI from "@/components/playground/ClaimsAdjudicationUI";
import { SendToReviewButton } from "@/components/playground/SendToReviewButton";
import LocalModelManager from "@/components/LocalModelManager";
import {
  isElectron,
  checkOllamaStatus,
  checkNetworkStatus,
  generateWithOllama,
  getOllamaModelName,
  listOllamaModels,
} from "@/lib/ollama";

interface ActivatedModel {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
}

export default function Playground() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [models, setModels] = useState<ActivatedModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState("");
  const [isElectronApp, setIsElectronApp] = useState(false);
  const [useLocalModel, setUseLocalModel] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [ollamaReady, setOllamaReady] = useState(false);

  useEffect(() => {
    checkAccess();
    checkElectronAndOllama();
    
    // Check online status periodically
    const interval = setInterval(async () => {
      const online = await checkNetworkStatus();
      setIsOnline(online);
    }, 10000);
    
    return () => clearInterval(interval);
  }, []);

  const checkElectronAndOllama = async () => {
    const electron = await isElectron();
    setIsElectronApp(electron);
    
    if (electron) {
      const status = await checkOllamaStatus();
      setOllamaReady(status.running);
      
      // Auto-enable local models if offline
      const online = await checkNetworkStatus();
      setIsOnline(online);
      if (!online && status.running) {
        setUseLocalModel(true);
      }
    }
  };

  const checkAccess = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        navigate("/auth");
        return;
      }

      const { data: roles } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", user.id);

      const isAdmin = roles?.some(r => r.role === "admin");
      if (isAdmin) {
        toast({
          title: "Access Denied",
          description: "Playground is only available for user accounts",
          variant: "destructive",
        });
        navigate("/dashboard");
        return;
      }

      loadActivatedModels(user.id);
    } catch (error) {
      console.error("Error checking access:", error);
      navigate("/auth");
    }
  };

  const loadActivatedModels = async (userId: string) => {
    try {
      const { data, error } = await supabase
        .from("activated_models")
        .select("*")
        .eq("user_id", userId);

      if (error) throw error;
      setModels(data || []);
      if (data && data.length > 0) {
        setSelectedModel(data[0].model_id);
      }
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

  const handleRun = async (data: any) => {
    if (!selectedModel) {
      toast({
        title: "Missing Information",
        description: "Please select a model",
        variant: "destructive",
      });
      return;
    }

    const selectedModelData = models.find(m => m.model_id === selectedModel);
    const isInsuranceModel = selectedModelData?.domain === "insurance";

    setIsRunning(true);
    setResult("");

    try {
      // Check if we should use local model
      if (useLocalModel && isElectronApp) {
        if (!ollamaReady) {
          toast({
            title: "Ollama Not Ready",
            description: "Please ensure Ollama is running to use local models",
            variant: "destructive",
          });
          setIsRunning(false);
          return;
        }

        // Check if model is installed
        const ollamaModels = await listOllamaModels();
        const ollamaModelName = getOllamaModelName(selectedModel);
        const modelInstalled = ollamaModels.some(m => 
          m.name.startsWith(ollamaModelName.split(':')[0])
        );

        if (!modelInstalled) {
          toast({
            title: "Model Not Installed",
            description: "Please download the model first from the Local Model Manager",
            variant: "destructive",
          });
          setIsRunning(false);
          return;
        }

        // Generate with local Ollama model
        const prompt = data.type === "generic" ? data.prompt : JSON.stringify(data, null, 2);
        const systemPrompt = `You are an AI assistant specialized in ${selectedModelData?.model_name}. Provide detailed and helpful responses.`;
        
        await generateWithOllama(
          ollamaModelName,
          prompt,
          systemPrompt,
          (chunk) => {
            setResult(prev => prev + chunk);
          }
        );
        
        setIsRunning(false);
      } else if (isInsuranceModel) {
        // Use mock responses for Insurance models with data context
        const contextPrompt = data.type === "generic" 
          ? data.prompt 
          : JSON.stringify(data, null, 2);
        const mockResponse = getMockInsuranceResponse(selectedModel, contextPrompt);
        let currentIndex = 0;
        
        const streamInterval = setInterval(() => {
          if (currentIndex < mockResponse.length) {
            const chunk = mockResponse.slice(currentIndex, currentIndex + 5);
            setResult((prev) => prev + chunk);
            currentIndex += 5;
          } else {
            clearInterval(streamInterval);
            setIsRunning(false);
          }
        }, 20);
      } else {
        // Use real AI for other models
        const messages = [
          {
            role: "user" as const,
            content: data.type === "generic" ? data.prompt : JSON.stringify(data, null, 2)
          }
        ];

        await streamChat({
          messages,
          onDelta: (delta) => {
            setResult((prev) => prev + delta);
          },
          onDone: () => {
            setIsRunning(false);
          },
          onError: (error) => {
            console.error("Streaming error:", error);
            toast({
              title: "Error",
              description: typeof error === "string" ? error : "Failed to run prompt",
              variant: "destructive",
            });
            setIsRunning(false);
          },
        });
      }
    } catch (error: any) {
      console.error("Error running prompt:", error);
      toast({
        title: "Error",
        description: "An unexpected error occurred",
        variant: "destructive",
      });
      setIsRunning(false);
    }
  };

  const selectedModelData = models.find(m => m.model_id === selectedModel);
  const modelName = selectedModelData?.model_name || "";

  const renderModelUI = () => {
    if (!selectedModel) return null;

    switch (selectedModel) {
      case "policy-comparison":
        return <PolicyComparisonUI modelId={selectedModel} onRun={handleRun} isRunning={isRunning} result={result} />;
      case "acord-parser":
        return <ACORDParserUI modelId={selectedModel} onRun={handleRun} isRunning={isRunning} result={result} />;
      case "claims-fnol":
        return <ClaimsFNOLUI onRun={handleRun} isRunning={isRunning} result={result} />;
      case "document-retrieval":
        return <DocumentRetrievalUI onRun={handleRun} isRunning={isRunning} result={result} />;
      case "quote-generation":
        return <QuoteGenerationUI onRun={handleRun} isRunning={isRunning} result={result} />;
      // Carrier models
      case "carrier-submission-intake":
      case "carrier-submission-triage":
        return <SubmissionIntakeUI onRun={handleRun} isRunning={isRunning} result={result} />;
      case "carrier-claims-intake":
      case "carrier-claims-adjudication":
      case "carrier-fraud-detection":
      case "carrier-subrogation":
        return <ClaimsAdjudicationUI onRun={handleRun} isRunning={isRunning} result={result} />;
      default:
        return <GenericPromptUI modelName={modelName} modelId={selectedModel} onRun={handleRun} isRunning={isRunning} result={result} />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (models.length === 0) {
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
                  Fideon Playground
                </h1>
              </div>
              <p className="text-muted-foreground text-lg">
                Test and experiment with your activated AI models
              </p>
            </div>
          </div>

          <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card animate-scale-in">
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <ShoppingCart className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-medium text-foreground mb-2">No Models Activated</h3>
              <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                Activate models from the marketplace to start using the playground
              </p>
              <Button
                onClick={() => navigate("/marketplace")}
                className="bg-gradient-to-r from-primary to-primary/80 hover:opacity-90 transition-opacity shadow-elevated"
              >
                Browse Marketplace
              </Button>
            </div>
          </CardContent>
        </Card>
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

      <div className="relative z-10 space-y-6 animate-fade-in">
        {/* Hero Header */}
        <div className="relative rounded-2xl bg-gradient-hero p-8 border border-border/50 backdrop-blur-sm shadow-premium">
          <div className="absolute inset-0 bg-gradient-subtle rounded-2xl opacity-50" />
          <div className="relative">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-lg bg-primary/10">
                <Brain className="h-8 w-8 text-primary animate-float" />
              </div>
              <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
                Fideon Playground
              </h1>
            </div>
            <p className="text-muted-foreground text-lg">
              Test and experiment with your activated AI models
            </p>
          </div>
        </div>

        {/* Model Selection - Top */}
        <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card hover:shadow-elevated transition-shadow animate-scale-in">
          <CardContent className="pt-6 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="model" className="text-foreground">Select Model</Label>
              <Select value={selectedModel} onValueChange={setSelectedModel}>
                <SelectTrigger id="model" className="bg-background border-input text-foreground">
                  <SelectValue placeholder="Choose a model" />
                </SelectTrigger>
                <SelectContent>
                  {models.map((model) => (
                    <SelectItem key={model.id} value={model.model_id}>
                      {model.model_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {selectedModelData && (
              <div className="pt-4 border-t border-border">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                  {selectedModelData.domain}
                </span>
              </div>
            )}

            {isElectronApp && ollamaReady && (
              <div className="space-y-2 pt-4 border-t border-border">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {useLocalModel ? (
                      <HardDrive className="h-4 w-4 text-primary" />
                    ) : (
                      <Cloud className="h-4 w-4 text-muted-foreground" />
                    )}
                    <Label htmlFor="local-toggle" className="cursor-pointer">
                      {useLocalModel ? "Local Model" : "Cloud Model"}
                    </Label>
                  </div>
                  <Switch
                    id="local-toggle"
                    checked={useLocalModel}
                    onCheckedChange={setUseLocalModel}
                  />
                </div>
                {!isOnline && (
                  <p className="text-xs text-muted-foreground">
                    You're offline. Using local models automatically.
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Model-specific UI */}
        {renderModelUI()}

        {/* Send to Review button - shown when there's output */}
        {result && !isRunning && selectedModelData && (
          <div className="flex justify-end">
            <SendToReviewButton
              podModelId={selectedModel}
              podModelName={selectedModelData.model_name}
              domain={selectedModelData.domain}
              result={result}
            />
          </div>
        )}

        {isElectronApp && (
          <LocalModelManager activatedModels={models} />
        )}
      </div>
    </div>
  );
}
