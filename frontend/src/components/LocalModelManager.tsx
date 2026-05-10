import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Download, Trash2, CheckCircle2, XCircle, Wifi, WifiOff, HardDrive } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  checkOllamaStatus,
  listOllamaModels,
  pullOllamaModel,
  deleteOllamaModel,
  checkNetworkStatus,
  getOllamaModelName,
  type OllamaModel,
  type PullProgress,
} from "@/lib/ollama";

interface LocalModelManagerProps {
  activatedModels: Array<{ id: string; model_id: string; model_name: string }>;
}

export default function LocalModelManager({ activatedModels }: LocalModelManagerProps) {
  const { toast } = useToast();
  const [ollamaStatus, setOllamaStatus] = useState({ installed: false, running: false });
  const [localModels, setLocalModels] = useState<OllamaModel[]>([]);
  const [isOnline, setIsOnline] = useState(true);
  const [downloading, setDownloading] = useState<Record<string, PullProgress>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const checkStatus = async () => {
    setLoading(true);
    const status = await checkOllamaStatus();
    setOllamaStatus(status);
    
    const online = await checkNetworkStatus();
    setIsOnline(online);

    if (status.running) {
      const models = await listOllamaModels();
      setLocalModels(models);
    }
    setLoading(false);
  };

  const handleDownloadModel = async (modelId: string, modelName: string) => {
    const ollamaModelName = getOllamaModelName(modelId);
    
    toast({
      title: "Downloading Model",
      description: `Starting download of ${modelName} (${ollamaModelName})...`,
    });

    const success = await pullOllamaModel(ollamaModelName, (progress) => {
      setDownloading(prev => ({ ...prev, [modelId]: progress }));
    });

    if (success) {
      toast({
        title: "Model Downloaded",
        description: `${modelName} is now available locally!`,
      });
      setDownloading(prev => {
        const newState = { ...prev };
        delete newState[modelId];
        return newState;
      });
      checkStatus(); // Refresh model list
    } else {
      toast({
        title: "Download Failed",
        description: "Failed to download model. Please try again.",
        variant: "destructive",
      });
      setDownloading(prev => {
        const newState = { ...prev };
        delete newState[modelId];
        return newState;
      });
    }
  };

  const handleDeleteModel = async (ollamaModelName: string, modelName: string) => {
    const success = await deleteOllamaModel(ollamaModelName);
    
    if (success) {
      toast({
        title: "Model Deleted",
        description: `${modelName} has been removed from local storage.`,
      });
      checkStatus(); // Refresh model list
    } else {
      toast({
        title: "Delete Failed",
        description: "Failed to delete model. Please try again.",
        variant: "destructive",
      });
    }
  };

  const isModelInstalled = (modelId: string): boolean => {
    const ollamaModelName = getOllamaModelName(modelId);
    return localModels.some((m: any) => m.name.startsWith(ollamaModelName.split(':')[0]));
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            Local Model Manager
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-4 text-muted-foreground">
            Checking Ollama status...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!ollamaStatus.installed || !ollamaStatus.running) {
    return (
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            Local Model Manager
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-2 text-destructive">
            <XCircle className="h-5 w-5" />
            <span>
              {!ollamaStatus.installed
                ? "Ollama is not installed"
                : "Ollama is not running"}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            To use local models, please install and run Ollama from{" "}
            <a
              href="https://ollama.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              ollama.ai
            </a>
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HardDrive className="h-5 w-5" />
            Local Model Manager
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={isOnline ? "default" : "secondary"} className="gap-1">
              {isOnline ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
              {isOnline ? "Online" : "Offline"}
            </Badge>
            <Badge variant="outline" className="gap-1">
              <CheckCircle2 className="h-3 w-3 text-success" />
              Ollama Running
            </Badge>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          {activatedModels.map((model: any) => {
            const ollamaModelName = getOllamaModelName(model.model_id);
            const installed = isModelInstalled(model.model_id);
            const isDownloading = downloading[model.model_id];
            const localModel = localModels.find((m: any) => 
              m.name.startsWith(ollamaModelName.split(':')[0])
            );

            return (
              <div
                key={model.id}
                className="flex items-center justify-between p-4 rounded-lg border border-border bg-muted/30"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{model.model_name}</p>
                    {installed && (
                      <Badge variant="outline" className="text-xs gap-1">
                        <CheckCircle2 className="h-3 w-3 text-success" />
                        Installed
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {ollamaModelName}
                    {localModel && ` • ${formatBytes(localModel.size)}`}
                  </p>
                  {isDownloading && (
                    <div className="space-y-1 mt-2">
                      <Progress
                        value={
                          isDownloading.total
                            ? (isDownloading.completed! / isDownloading.total) * 100
                            : 0
                        }
                      />
                      <p className="text-xs text-muted-foreground">
                        {isDownloading.status}
                        {isDownloading.total &&
                          ` • ${formatBytes(isDownloading.completed!)} / ${formatBytes(isDownloading.total)}`}
                      </p>
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  {!installed && !isDownloading && (
                    <Button
                      size="sm"
                      onClick={() => handleDownloadModel(model.model_id, model.model_name)}
                      className="gap-2"
                    >
                      <Download className="h-4 w-4" />
                      Download
                    </Button>
                  )}
                  {installed && (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() =>
                        handleDeleteModel(ollamaModelName, model.model_name)
                      }
                      className="gap-2"
                    >
                      <Trash2 className="h-4 w-4" />
                      Delete
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {activatedModels.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            No activated models to sync. Visit the Marketplace to activate models.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
