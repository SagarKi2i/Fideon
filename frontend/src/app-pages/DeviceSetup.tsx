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
  Wifi,
  Copy
} from "lucide-react";
import {
  fetchDeviceModels,
  performDeviceCheckin,
  getStoredDeviceJwt,
  setStoredDeviceJwt,
  clearStoredDeviceJwt,
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
import { linkDeviceById } from "@/lib/deviceLinkApi";

export default function DeviceSetup() {
  const { toast } = useToast();
  const [isConnected, setIsConnected] = useState(false);
  const [allocatedModels, setAllocatedModels] = useState<DeviceModel[]>([]);
  const [localModels, setLocalModels] = useState<OllamaModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [ollamaRunning, setOllamaRunning] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<Record<string, PullProgress>>({});
  const [isElectronApp, setIsElectronApp] = useState(false);
  const [deviceJwt, setDeviceJwt] = useState("");
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [manualDisconnected, setManualDisconnected] = useState(false);

  useEffect(() => {
    void checkElectron();
    const storedJwt = getStoredDeviceJwt();
    if (storedJwt) {
      setDeviceJwt(storedJwt);
      setIsConnected(true);
      void loadDeviceModels(storedJwt);
    }
    void checkOllama();
  }, []);

  // Background heartbeat: every 60s, report device + local model status to cloud.
  useEffect(() => {
    if (!isElectronApp || !deviceJwt || !isConnected) {
      return;
    }

    const intervalId = window.setInterval(async () => {
      try {
        const localModelStatuses = allocatedModels.map((model: any) => ({
          model_id: model.model_id,
          is_downloaded: isModelInstalled(model.ollama_model_name),
        }));
        await performDeviceCheckin(deviceJwt, localModelStatuses);
      } catch {
        // Best-effort heartbeat; errors are intentionally swallowed to avoid UI noise.
      }
    }, 60000); // 60s

    return () => window.clearInterval(intervalId);
  }, [isElectronApp, deviceJwt, isConnected, allocatedModels, localModels]);

  const checkElectron = async () => {
    const result = await isElectron();
    setIsElectronApp(result);
    if (manualDisconnected) return;
    if (result && window.electron?.device?.getAuth) {
      try {
        const res = await window.electron.device.getAuth();
        if (res?.success) {
          setDeviceId(res.device_id ?? null);
          if (res.device_jwt) {
            setStoredDeviceJwt(res.device_jwt);
            setDeviceJwt(res.device_jwt);
            setIsConnected(true);
            await loadDeviceModels(res.device_jwt);
          }
        }
      } catch {
        // ignore
      }
    }
    if (result && window.electron?.device?.getDeviceId && !deviceId) {
      try {
        const res = await window.electron.device.getDeviceId();
        if (res?.success) setDeviceId(res.device_id ?? null);
      } catch {
        // ignore
      }
    }
  };

  const checkOllama = async () => {
    const status = await checkOllamaStatus();
    setOllamaRunning(status.running);
    if (status.running) {
      const models = await listOllamaModels();
      setLocalModels(models);
    }
  };

  const handleDisconnect = () => {
    clearStoredDeviceJwt();
    setDeviceJwt("");
    setIsConnected(false);
    setAllocatedModels([]);
    setManualDisconnected(true);
    if (window.electron?.device?.clearAuth) {
      void window.electron.device.clearAuth();
    }
    toast({
      title: "Disconnected",
      description: "Device auth cleared. Click Refresh to re-connect.",
    });
  };

  const loadDeviceModels = async (jwt: string) => {
    const response = await fetchDeviceModels(jwt);
    setAllocatedModels(response.models);
  };

  const handleRefresh = async () => {
    if (!deviceJwt) {
      setManualDisconnected(false);
      if (window.electron?.device?.ensureAuth) {
        try {
          setLoading(true);
          const res = await window.electron.device.ensureAuth();
          if (res?.success && res.device_jwt) {
            setStoredDeviceJwt(res.device_jwt);
            setDeviceJwt(res.device_jwt);
            setIsConnected(true);
            if (res.device_id) setDeviceId(res.device_id);
            await loadDeviceModels(res.device_jwt);
          } else {
            throw new Error(res?.error || "Could not register device");
          }
        } catch (e) {
          toast({
            title: "Reconnect failed",
            description: e instanceof Error ? e.message : "Unknown error",
            variant: "destructive",
          });
        } finally {
          setLoading(false);
        }
        return;
      }
      await checkElectron();
      return;
    }
    setLoading(true);
    try {
      await loadDeviceModels(deviceJwt);
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
    if (!deviceJwt) return;
    setLoading(true);
    try {
      const localModelStatuses = allocatedModels.map((model: any) => ({
        model_id: model.model_id,
        is_downloaded: isModelInstalled(model.ollama_model_name),
      }));
      
      await performDeviceCheckin(deviceJwt, localModelStatuses);
      await loadDeviceModels(deviceJwt);
      
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
    return localModels.some((m: any) => m.name === ollamaModelName);
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

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5" />
            Link this device to your account
          </CardTitle>
          <CardDescription>
            Link this device to your tenant using your current login session.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Label>Device ID</Label>
          <div className="flex flex-col sm:flex-row gap-2">
            <Input value={deviceId ?? "Not registered yet"} readOnly className="font-mono text-xs" />
            <Button
              type="button"
              variant="outline"
              disabled={!deviceId}
              onClick={async () => {
                if (!deviceId) return;
                try {
                  await navigator.clipboard.writeText(deviceId);
                  toast({ title: "Copied", description: "Device ID copied to clipboard." });
                } catch {
                  toast({ title: "Copy failed", description: "Please copy manually.", variant: "destructive" });
                }
              }}
            >
              <Copy className="h-4 w-4 mr-2" />
              Copy
            </Button>
            <Button
              type="button"
              className="bg-gradient-primary"
              disabled={!deviceId || loading}
              onClick={async () => {
                if (!deviceId) return;
                try {
                  setLoading(true);
                  await linkDeviceById(deviceId);
                  toast({ title: "Device linked", description: "This device is now connected to your tenant." });
                } catch (e) {
                  toast({
                    title: "Link failed",
                    description: e instanceof Error ? e.message : "Unknown error",
                    variant: "destructive",
                  });
                } finally {
                  setLoading(false);
                }
              }}
            >
              Link now
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            If this shows “Not registered yet”, click Refresh below to register/reconnect, then link.
          </p>
        </CardContent>
      </Card>

      {/* Connection Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Monitor className="h-5 w-5" />
            Device Connection
          </CardTitle>
          <CardDescription>
            This device auto-connects using its device JWT (no manual token needed).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {isConnected ? (
                  <Badge variant="default" className="bg-green-500">
                    <CheckCircle2 className="mr-1 h-3 w-3" />
                    Connected
                  </Badge>
                ) : (
                  <Badge variant="secondary">
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                    Connecting…
                  </Badge>
                )}
                <span className="text-sm text-muted-foreground">
                  {allocatedModels.length} model(s) allocated
                </span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
                <Button variant="outline" size="sm" onClick={handleSync} disabled={loading || !deviceJwt}>
                  Sync Status
                </Button>
                <Button variant="destructive" size="sm" onClick={handleDisconnect}>
                  Disconnect
                </Button>
              </div>
            </div>
          </div>
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
              {allocatedModels.map((model: any) => {
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
