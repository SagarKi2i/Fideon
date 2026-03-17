import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { 
  Monitor, 
  Download, 
  CheckCircle2, 
  Loader2, 
  RefreshCw,
  Trash2,
  WifiOff,
  Wifi
} from "lucide-react";
import {
  fetchDeviceModels,
  performDeviceCheckin,
  getStoredDeviceToken,
  setStoredDeviceToken,
  clearStoredDeviceToken,
  type DeviceModel,
} from "@/lib/deviceApi";
import {
  checkOllamaStatus,
  listOllamaModels,
  pullOllamaModel,
  deleteOllamaModel,
  isElectron,
  type OllamaModel,
  type PullProgress,
} from "@/lib/ollama";

export default function DeviceSetup() {
  const { toast } = useToast();
  const [deviceToken, setDeviceToken] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [allocatedModels, setAllocatedModels] = useState<DeviceModel[]>([]);
  const [localModels, setLocalModels] = useState<OllamaModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [ollamaRunning, setOllamaRunning] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<Record<string, PullProgress>>({});
  const [isElectronApp, setIsElectronApp] = useState(false);

  useEffect(() => {
    checkElectron();
    const stored = getStoredDeviceToken();
    if (stored) {
      setDeviceToken(stored);
      setIsConnected(true);
      loadDeviceModels(stored);
    }
    checkOllama();
  }, []);

  // Background heartbeat: every 60s, report device + local model status to cloud.
  useEffect(() => {
    if (!isElectronApp || !deviceToken || !isConnected) {
      return;
    }

    const intervalId = window.setInterval(async () => {
      try {
        if (!deviceToken) return;
        const localModelStatuses = allocatedModels.map(model => ({
          model_id: model.model_id,
          is_downloaded: isModelInstalled(model.ollama_model_name),
        }));
        await performDeviceCheckin(deviceToken, localModelStatuses);
      } catch {
        // Best-effort heartbeat; errors are intentionally swallowed to avoid UI noise.
      }
    }, 60000); // 60s

    return () => window.clearInterval(intervalId);
  }, [isElectronApp, deviceToken, isConnected, allocatedModels, localModels]);

  const checkElectron = async () => {
    const result = await isElectron();
    setIsElectronApp(result);
  };

  const checkOllama = async () => {
    const status = await checkOllamaStatus();
    setOllamaRunning(status.running);
    if (status.running) {
      const models = await listOllamaModels();
      setLocalModels(models);
    }
  };

  const handleConnect = async () => {
    if (!deviceToken.trim()) {
      toast({
        title: "Error",
        description: "Please enter a device token",
        variant: "destructive",
      });
      return;
    }

    setLoading(true);
    try {
      await loadDeviceModels(deviceToken);
      setStoredDeviceToken(deviceToken);
      setIsConnected(true);
      toast({
        title: "Connected",
        description: "Successfully connected to Fideon OS",
      });
    } catch (error: any) {
      toast({
        title: "Connection Failed",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = () => {
    clearStoredDeviceToken();
    setDeviceToken("");
    setIsConnected(false);
    setAllocatedModels([]);
    toast({
      title: "Disconnected",
      description: "Device token cleared",
    });
  };

  const loadDeviceModels = async (token: string) => {
    const response = await fetchDeviceModels(token);
    setAllocatedModels(response.models);
  };

  const handleRefresh = async () => {
    if (!deviceToken) return;
    setLoading(true);
    try {
      await loadDeviceModels(deviceToken);
      await checkOllama();
      toast({
        title: "Refreshed",
        description: "Models list updated",
      });
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    if (!deviceToken) return;
    setLoading(true);
    try {
      const localModelStatuses = allocatedModels.map(model => ({
        model_id: model.model_id,
        is_downloaded: isModelInstalled(model.ollama_model_name),
      }));
      
      await performDeviceCheckin(deviceToken, localModelStatuses);
      await loadDeviceModels(deviceToken);
      
      toast({
        title: "Synced",
        description: "Device status synchronized with cloud",
      });
    } catch (error: any) {
      toast({
        title: "Sync Failed",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadModel = async (model: DeviceModel) => {
    try {
      const success = await pullOllamaModel(
        model.ollama_model_name,
        (progress) => {
          setDownloadProgress(prev => ({
            ...prev,
            [model.model_id]: progress,
          }));
        }
      );

      if (success) {
        await checkOllama();
        await handleSync();
        toast({
          title: "Success",
          description: `${model.model_name} downloaded successfully`,
        });
      }
    } catch (error: any) {
      toast({
        title: "Download Failed",
        description: error.message,
        variant: "destructive",
      });
    } finally {
      setDownloadProgress(prev => {
        const updated = { ...prev };
        delete updated[model.model_id];
        return updated;
      });
    }
  };

  const handleDeleteModel = async (model: DeviceModel) => {
    try {
      const success = await deleteOllamaModel(model.ollama_model_name);
      if (success) {
        await checkOllama();
        await handleSync();
        toast({
          title: "Deleted",
          description: `${model.model_name} removed`,
        });
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    }
  };

  const isModelInstalled = (ollamaModelName: string): boolean => {
    return localModels.some(m => m.name === ollamaModelName);
  };

  if (!isElectronApp) {
    return (
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Device Setup</CardTitle>
            <CardDescription>
              This feature is only available in the Electron desktop app
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Device Setup</h1>
        <p className="text-muted-foreground mt-1">
          Connect your device to sync and download AI models locally
        </p>
      </div>

      {/* Connection Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5" />
            Device Connection
          </CardTitle>
          <CardDescription>
            Enter the device token from your admin dashboard to connect
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!isConnected ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="token">Device Token</Label>
                <Input
                  id="token"
                  type="password"
                  value={deviceToken}
                  onChange={(e) => setDeviceToken(e.target.value)}
                  placeholder="Enter your device token"
                />
              </div>
              <Button onClick={handleConnect} disabled={loading}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Connect Device
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="default" className="bg-green-500">
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    Connected
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    {allocatedModels.length} model(s) allocated
                  </span>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleSync} disabled={loading}>
                    Sync Status
                  </Button>
                  <Button variant="destructive" size="sm" onClick={handleDisconnect}>
                    Disconnect
                  </Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Ollama Status Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {ollamaRunning ? (
              <Wifi className="h-5 w-5 text-green-500" />
            ) : (
              <WifiOff className="h-5 w-5 text-red-500" />
            )}
            Ollama Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">
              {ollamaRunning ? "Ollama is running" : "Ollama is not running"}
            </span>
            <Button variant="outline" size="sm" onClick={checkOllama}>
              Check Status
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Allocated Models */}
      {isConnected && allocatedModels.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Allocated Models</CardTitle>
            <CardDescription>
              Models assigned to this device. Download them to use locally.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {allocatedModels.map((model) => {
                const installed = isModelInstalled(model.ollama_model_name);
                const progress = downloadProgress[model.model_id];
                
                return (
                  <div
                    key={model.model_id}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium">{model.model_name}</h3>
                        <Badge variant="outline">{model.domain}</Badge>
                        {installed && (
                          <Badge variant="default" className="bg-green-500">
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            Installed
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {model.ollama_model_name}
                      </p>
                      {progress && (
                        <div className="mt-2">
                          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                            <span>{progress.status}</span>
                            {progress.completed && progress.total && (
                              <span>
                                {Math.round((progress.completed / progress.total) * 100)}%
                              </span>
                            )}
                          </div>
                          <div className="h-1.5 bg-secondary rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary transition-all duration-300"
                              style={{
                                width: progress.completed && progress.total
                                  ? `${(progress.completed / progress.total) * 100}%`
                                  : '0%',
                              }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-2">
                      {!installed && !progress && ollamaRunning && (
                        <Button
                          size="sm"
                          onClick={() => handleDownloadModel(model)}
                        >
                          <Download className="mr-2 h-4 w-4" />
                          Download
                        </Button>
                      )}
                      {installed && (
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDeleteModel(model)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                      {progress && (
                        <Button size="sm" disabled>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Downloading
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {isConnected && allocatedModels.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="text-center">
              <Monitor className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-medium mb-2">No Models Allocated</h3>
              <p className="text-muted-foreground max-w-sm mx-auto">
                No models have been allocated to this device yet. Contact your admin to allocate models.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
