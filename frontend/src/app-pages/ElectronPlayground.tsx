import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Download, Trash2, Play, AlertCircle, CheckCircle, HardDrive } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  checkOllamaStatus,
  listOllamaModels,
  pullOllamaModel,
  generateWithOllama,
  deleteOllamaModel,
  OllamaModel,
} from "@/lib/ollama";
import { Progress } from "@/components/ui/progress";

export default function ElectronPlayground() {
  const { toast } = useToast();
  const [ollamaStatus, setOllamaStatus] = useState({ installed: false, running: false });
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [pullProgress, setPullProgress] = useState<{ [key: string]: number }>({});
  const [pullingModels, setPullingModels] = useState<Set<string>>(new Set());

  useEffect(() => {
    initializeOllama();
  }, []);

  const initializeOllama = async () => {
    setLoading(true);
    const status = await checkOllamaStatus();
    setOllamaStatus(status);

    if (status.running) {
      await refreshModels();
    }
    setLoading(false);
  };

  const refreshModels = async () => {
    const modelList = await listOllamaModels();
    setModels(modelList);
    if (modelList.length > 0 && !selectedModel) {
      setSelectedModel(modelList[0].name);
    }
  };

  const handlePullModel = async (modelName: string) => {
    setPullingModels(prev => new Set(prev).add(modelName));
    setPullProgress(prev => ({ ...prev, [modelName]: 0 }));

    const success = await pullOllamaModel(modelName, (progress) => {
      if (progress.total && progress.completed) {
        const percent = (progress.completed / progress.total) * 100;
        setPullProgress(prev => ({ ...prev, [modelName]: percent }));
      }
    });

    setPullingModels(prev => {
      const next = new Set(prev);
      next.delete(modelName);
      return next;
    });

    if (success) {
      toast({
        title: "Success",
        description: `Model ${modelName} downloaded successfully`,
      });
      await refreshModels();
    } else {
      toast({
        title: "Error",
        description: `Failed to download model ${modelName}`,
        variant: "destructive",
      });
    }
  };

  const handleDeleteModel = async (modelName: string) => {
    const success = await deleteOllamaModel(modelName);
    if (success) {
      toast({
        title: "Success",
        description: `Model ${modelName} deleted successfully`,
      });
      await refreshModels();
    } else {
      toast({
        title: "Error",
        description: `Failed to delete model ${modelName}`,
        variant: "destructive",
      });
    }
  };

  const handleRun = async () => {
    if (!prompt.trim() || !selectedModel) {
      toast({
        title: "Missing Information",
        description: "Please enter a prompt and select a model",
        variant: "destructive",
      });
      return;
    }

    setIsRunning(true);
    setResult("");

    try {
      await generateWithOllama(
        selectedModel,
        prompt,
        "You are a helpful AI assistant running locally.",
        (chunk) => {
          setResult(prev => prev + chunk);
        }
      );
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate response",
        variant: "destructive",
      });
    } finally {
      setIsRunning(false);
    }
  };

  const popularModels = [
    { name: "llama3.2:latest", description: "Meta's latest Llama model - Fast and efficient" },
    { name: "mistral:latest", description: "Mistral 7B - Excellent performance" },
    { name: "phi3:latest", description: "Microsoft Phi-3 - Compact and powerful" },
    { name: "gemma2:latest", description: "Google Gemma 2 - Strong reasoning" },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!ollamaStatus.running) {
    return (
      <div className="flex items-center justify-center h-screen bg-background p-8">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              Ollama Not Running
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground">
              Ollama needs to be installed and running to use local AI models.
            </p>
            <div className="space-y-2 text-sm">
              <p className="font-medium">To get started:</p>
              <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                <li>Download Ollama from <a href="https://ollama.ai" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">ollama.ai</a></li>
                <li>Install and run Ollama</li>
                <li>Restart this app</li>
              </ol>
            </div>
            <Button onClick={initializeOllama} className="w-full">
              Check Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="h-screen bg-background flex flex-col">
      {/* Header */}
      <div className="border-b border-border bg-primary px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <HardDrive className="h-5 w-5 text-primary-foreground" />
          <h1 className="text-lg font-semibold text-primary-foreground">Local Fideon Playground</h1>
        </div>
        <div className="flex items-center gap-2">
          <CheckCircle className="h-4 w-4 text-green-500" />
          <span className="text-sm text-primary-foreground">Ollama Connected</span>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-64 border-r border-border bg-muted/30 flex flex-col">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold text-sm text-foreground mb-2">Installed Models</h2>
            <p className="text-xs text-muted-foreground">
              {models.length} {models.length === 1 ? 'model' : 'models'} available
            </p>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {models.map((model: any) => (
              <div
                key={model.name}
                className={`p-3 rounded-lg cursor-pointer transition-colors ${
                  selectedModel === model.name
                    ? 'bg-primary/10 border border-primary/20'
                    : 'hover:bg-muted'
                }`}
                onClick={() => setSelectedModel(model.name)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedModel(model.name);
                  }
                }}
                role="button"
                tabIndex={0}
                aria-pressed={selectedModel === model.name}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {model.name.split(':')[0]}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {(model.size / 1024 / 1024 / 1024).toFixed(1)} GB
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteModel(model.name);
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 border-t border-border">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                const section = document.getElementById('download-section');
                section?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              <Download className="h-4 w-4 mr-2" />
              Download Models
            </Button>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Prompt Section */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Play className="h-5 w-5" />
                  Run Prompt
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>Model</Label>
                  <Select value={selectedModel} onValueChange={setSelectedModel}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a model" />
                    </SelectTrigger>
                    <SelectContent>
                      {models.map((model: any) => (
                        <SelectItem key={model.name} value={model.name}>
                          {model.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Prompt</Label>
                  <Textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Enter your prompt here..."
                    className="min-h-[100px]"
                  />
                </div>

                <Button
                  onClick={handleRun}
                  disabled={isRunning || !selectedModel}
                  className="w-full"
                >
                  {isRunning ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Run Prompt
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Result Section */}
            {result && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Response</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="bg-muted/50 rounded-lg p-4 font-mono text-sm whitespace-pre-wrap">
                    {result}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Download Section */}
            <Card id="download-section">
              <CardHeader>
                <CardTitle className="text-lg">Download New Models</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {popularModels.map((model: any) => {
                    const isPulling = pullingModels.has(model.name);
                    const progress = pullProgress[model.name] ?? 0;
                    const isInstalled = models.some((m: any) => m.name === model.name);

                    return (
                      <div key={model.name} className="border border-border rounded-lg p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <h3 className="font-medium text-foreground">{model.name}</h3>
                            <p className="text-sm text-muted-foreground mt-1">
                              {model.description}
                            </p>
                          </div>
                          <Button
                            size="sm"
                            onClick={() => handlePullModel(model.name)}
                            disabled={isPulling || isInstalled}
                            variant={isInstalled ? "outline" : "default"}
                          >
                            {isPulling ? (
                              <>
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                Downloading
                              </>
                            ) : isInstalled ? (
                              <>
                                <CheckCircle className="h-4 w-4 mr-2" />
                                Installed
                              </>
                            ) : (
                              <>
                                <Download className="h-4 w-4 mr-2" />
                                Download
                              </>
                            )}
                          </Button>
                        </div>
                        {isPulling && (
                          <Progress value={progress} className="mt-3" />
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
