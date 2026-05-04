import { useState, useEffect, useCallback, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
  Copy,
  AlertCircle
} from "lucide-react";
import {
  fetchDeviceModels,
  performDeviceCheckin,
  getStoredDeviceJwt,
  setStoredDeviceJwt,
  clearStoredDeviceJwt,
  sendDeviceHeartbeat,
  type DeviceModel,
} from "@/lib/deviceApi";
import { ApiRequestError } from "@/lib/httpErrors";
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

function tryExtractDeviceIdFromJwt(token: string): string | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const payloadB64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = payloadB64 + "===".slice((payloadB64.length + 3) % 4);
    const json = atob(padded);
    const payload = JSON.parse(json) as any;
    const id = payload?.device_id ?? payload?.sub;
    return typeof id === "string" && id.trim() ? id.trim() : null;
  } catch {
    return null;
  }
}

export default function DeviceSetup() {
  const { toast } = useToast();
  const [isConnected, setIsConnected] = useState(false);
  const [allocatedModels, setAllocatedModels] = useState<DeviceModel[]>([]);
  const [localModels, setLocalModels] = useState<OllamaModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [ollamaRunning, setOllamaRunning] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState<Record<string, PullProgress>>({});
  const [isElectronApp, setIsElectronApp] = useState(false);
  const [deviceJwt, setDeviceJwt] = useState("");
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const [isDisabled, setIsDisabled] = useState(false);
  /** From Electron main: os.hostname + node-machine-id (registration fingerprint). */
  const [localMachine, setLocalMachine] = useState<{
    machineName: string;
    machineId: string;
    platform: string;
  } | null>(null);
  const authLossToastShown = useRef(false);

  const handleInvalidDeviceAuth = useCallback(
    (message?: string) => {
      clearStoredDeviceJwt();
      setDeviceJwt("");
      setDeviceId(null);
      setIsConnected(false);
      setAllocatedModels([]);
      if (message?.toLowerCase().includes("deactivated") || message?.toLowerCase().includes("disabled")) {
        setIsDisabled(true);
      }
      if (window.electron?.device?.clearAuth) {
        void window.electron.device.clearAuth();
      }
      if (!authLossToastShown.current) {
        authLossToastShown.current = true;
        toast({
          title: isDisabled ? "Device Disabled" : "Device no longer connected",
          description:
            message ||
            "This device was disabled or its token was revoked. Ask an admin to re-enable it if needed, then use Refresh to register again.",
          variant: "destructive",
        });
      }
    },
    [toast, isDisabled],
  );

  const verifyCloudSession = useCallback(
    async (jwt: string): Promise<boolean> => {
      try {
        await sendDeviceHeartbeat(jwt);
        authLossToastShown.current = false;
        setIsDisabled(false);
        return true;
      } catch (e) {
        if (e instanceof ApiRequestError && e.isAuthError) {
          handleInvalidDeviceAuth(e.message);
          return false;
        }
        throw e;
      }
    },
    [handleInvalidDeviceAuth],
  );

  useEffect(() => {
    void checkElectron();
    const storedJwt = getStoredDeviceJwt();
    if (storedJwt) {
      void (async () => {
        setConnecting(true);
        try {
          const ok = await verifyCloudSession(storedJwt);
          if (ok) {
            setDeviceJwt(storedJwt);
            setIsConnected(true);
            // Ensure Cloud device ID renders even if Electron store is slow/unavailable.
            const extractedId = tryExtractDeviceIdFromJwt(storedJwt);
            setDeviceId((prev) => prev ?? extractedId);
            
            let finalDeviceId = extractedId;
            if (window.electron?.device?.getDeviceId) {
              try {
                const res = await window.electron.device.getDeviceId();
                if (res?.success && res.device_id) {
                  setDeviceId(res.device_id);
                  finalDeviceId = res.device_id;
                }
              } catch {
                // ignore
              }
            }
            // Auto-link device to tenant
            if (finalDeviceId) {
              try { await linkDeviceById(finalDeviceId); } catch { /* silent fail if not logged in or already linked */ }
            }
            void loadDeviceModels(storedJwt);
          }
        } catch {
          // ignore network errors
        } finally {
          setConnecting(false);
        }
      })();
    }
    void checkOllama();
    // Intentionally mount-only: avoid re-running Electron bootstrap when callbacks change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isElectronApp || !window.electron?.device?.getDeviceInfo) return;
    void window.electron.device.getDeviceInfo().then((res) => {
      if (res?.success && "machineName" in res && "machineId" in res) {
        setLocalMachine({
          machineName: res.machineName,
          machineId: res.machineId,
          platform: res.platform ?? "",
        });
      }
    });
  }, [isElectronApp]);

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
      } catch (e) {
        if (e instanceof ApiRequestError && e.isAuthError) {
          handleInvalidDeviceAuth(e.message);
          return;
        }
        // Transient errors: keep UI connected; next Refresh/Sync will surface if persistent.
      }
    }, 60000); // 60s

    return () => window.clearInterval(intervalId);
  }, [isElectronApp, deviceJwt, isConnected, allocatedModels, localModels, handleInvalidDeviceAuth]);

  const checkElectron = async () => {
    const result = await isElectron();
    setIsElectronApp(result);
    if (result && window.electron?.device?.getAuth) {
      try {
        setConnecting(true);
        const res = await window.electron.device.getAuth();
        if (res?.success) {
          setDeviceId(res.device_id ?? null);
          if (res.device_jwt) {
            const ok = await verifyCloudSession(res.device_jwt);
            if (!ok) return;
            setStoredDeviceJwt(res.device_jwt);
            setDeviceJwt(res.device_jwt);
            setIsConnected(true);
            if (res.device_id) {
              try { await linkDeviceById(res.device_id); } catch { /* silent */ }
            }
            await loadDeviceModels(res.device_jwt);
          }
        }
      } catch {
        // ignore
      } finally {
        setConnecting(false);
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

  const loadDeviceModels = async (jwt: string) => {
    const response = await fetchDeviceModels(jwt);
    setAllocatedModels(response.models);
  };

  const handleRefresh = async () => {
    if (!deviceJwt) {
      if (window.electron?.device?.ensureAuth) {
        try {
          setConnecting(true);
          setLoading(true);
          toast({ title: "Refreshing…", description: "Registering/reconnecting this device." });
          const res = await window.electron.device.ensureAuth();
          if (res?.success && res.device_jwt) {
            const ok = await verifyCloudSession(res.device_jwt);
            if (!ok) return;
            setStoredDeviceJwt(res.device_jwt);
            setDeviceJwt(res.device_jwt);
            setIsConnected(true);
            const devId = res.device_id ?? tryExtractDeviceIdFromJwt(res.device_jwt);
            setDeviceId(devId);
            if (devId) {
              try { await linkDeviceById(devId); } catch { /* silent */ }
            }
            await loadDeviceModels(res.device_jwt);
          } else {
            throw new Error(res?.error || "Could not register device");
          }
        } catch (e) {
          const msg = e instanceof Error ? e.message : "Unknown error";
          const hint =
            typeof msg === "string" && msg.toLowerCase().includes("fetch failed")
              ? " Check the backend is running and Electron main uses the same API port as the app (electron/.env ELECTRON_API_BASE_URL, default 127.0.0.1:8080)."
              : "";
          toast({
            title: "Reconnect failed",
            description: msg + hint,
            variant: "destructive",
          });
        } finally {
          setLoading(false);
          setConnecting(false);
        }
        return;
      }
      await checkElectron();
      return;
    }
    setLoading(true);
    try {
      const ok = await verifyCloudSession(deviceJwt);
      if (!ok) {
        // Token was invalid/revoked. Auto re-register in Electron so Refresh is one-click recovery.
        if (window.electron?.device?.ensureAuth) {
          toast({ title: "Reconnecting…", description: "Device token was invalid. Re-registering now." });
          const res = await window.electron.device.ensureAuth();
          if (res?.success && res.device_jwt) {
            const ok2 = await verifyCloudSession(res.device_jwt);
            if (!ok2) return;
            setStoredDeviceJwt(res.device_jwt);
            setDeviceJwt(res.device_jwt);
            setIsConnected(true);
            const devId = res.device_id ?? tryExtractDeviceIdFromJwt(res.device_jwt);
            setDeviceId(devId);
            if (devId) {
              try { await linkDeviceById(devId); } catch { /* silent */ }
            }
            await loadDeviceModels(res.device_jwt);
          } else {
            throw new Error(res?.error || "Could not re-register device");
          }
        }
        return;
      }
      await loadDeviceModels(deviceJwt);
      await checkOllama();
      toast({
        title: "Refreshed",
        description: "Models list updated",
      });
    } catch (error: any) {
      if (error instanceof ApiRequestError && error.isAuthError) {
        handleInvalidDeviceAuth(error.message);
      } else {
        toast({
          title: "Error",
          description: error.message,
          variant: "destructive",
        });
      }
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
      if (error instanceof ApiRequestError && error.isAuthError) {
        handleInvalidDeviceAuth(error.message);
      } else {
        toast({
          title: "Sync Failed",
          description: error.message,
          variant: "destructive",
        });
      }
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
      
      {isDisabled && (
        <Alert variant="destructive" className="animate-in slide-in-from-top-2 duration-300">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Device Disabled</AlertTitle>
          <AlertDescription>
            This device has been disabled by an administrator. Please contact your administrator to re-enable it.
            Once re-enabled, click "Refresh" to reconnect.
          </AlertDescription>
        </Alert>
      )}

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
        <CardContent className="space-y-4">
          {localMachine ? (
            <div className="rounded-lg border border-border/60 bg-muted/30 p-3 space-y-2">
              <p className="text-xs font-medium text-muted-foreground">This computer</p>
              <div className="grid gap-2 text-sm">
                <div className="grid grid-cols-1 sm:grid-cols-[8rem_1fr] gap-1 sm:gap-3">
                  <span className="text-muted-foreground">Hostname</span>
                  <span className="font-mono text-foreground break-all">{localMachine.machineName}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-[8rem_1fr] gap-1 sm:gap-3">
                  <span className="text-muted-foreground">Machine ID</span>
                  <span className="font-mono text-xs break-all">{localMachine.machineId}</span>
                </div>
                {localMachine.platform ? (
                  <div className="grid grid-cols-1 sm:grid-cols-[8rem_1fr] gap-1 sm:gap-3">
                    <span className="text-muted-foreground">Platform</span>
                    <span className="font-mono">{localMachine.platform}</span>
                  </div>
                ) : null}
              </div>
              <p className="text-[11px] text-muted-foreground pt-1 border-t border-border/50">
                Stable hardware-derived ID used for registration. This is not the same as the cloud device ID below.
              </p>
            </div>
          ) : null}

          <div className="space-y-2">
          <Label>Cloud device ID</Label>
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
                  toast({ title: "Copied", description: "Cloud device ID copied to clipboard." });
                } catch {
                  toast({ title: "Copy failed", description: "Please copy manually.", variant: "destructive" });
                }
              }}
            >
              <Copy className="h-4 w-4 mr-2" />
              Copy
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            {deviceId 
              ? "This device is automatically registered and linked to your tenant." 
              : "If this shows “Not registered yet”, click Refresh below to register/reconnect."}
          </p>
          </div>
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
                {/* aria-live so screen readers announce connection changes without a page reload */}
                <div role="status" aria-live="polite" aria-atomic="true">
                  {isConnected ? (
                    <Badge variant="default" className="bg-green-500">
                      <CheckCircle2 className="mr-1 h-3 w-3" aria-hidden="true" />
                      Connected
                    </Badge>
                  ) : (loading || connecting) ? (
                    <Badge variant="secondary">
                      <Loader2 className="mr-1 h-3 w-3 animate-spin" aria-hidden="true" />
                      Connecting…
                    </Badge>
                  ) : (
                    <Badge variant="secondary">
                      <WifiOff className="mr-1 h-3 w-3" aria-hidden="true" />
                      Disconnected
                    </Badge>
                  )}
                </div>
                <span className="text-sm text-muted-foreground">
                  {allocatedModels.length} model(s) allocated
                </span>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading} aria-label="Refresh device connection">
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} aria-hidden="true" />
                </Button>
                <Button variant="outline" size="sm" onClick={handleSync} disabled={loading || !deviceJwt}>
                  Sync Status
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
              <Wifi className="h-5 w-5 text-green-500" aria-hidden="true" />
            ) : (
              <WifiOff className="h-5 w-5 text-red-500" aria-hidden="true" />
            )}
            Ollama Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <span role="status" aria-live="polite" className="text-sm text-muted-foreground">
              {ollamaRunning ? "Ollama is running" : "Ollama is not running"}
            </span>
            <Button variant="outline" size="sm" onClick={checkOllama} aria-label="Check Ollama status">
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
