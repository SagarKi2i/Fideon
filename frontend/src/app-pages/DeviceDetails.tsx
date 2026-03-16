import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  Monitor,
  Circle,
  Loader2,
  RefreshCw,
  Plus,
  Trash2,
  Key,
  Activity,
  History,
  Package,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { formatDistanceToNow, format } from "date-fns";
import { performDeviceCheckin } from "@/lib/deviceApi";

interface Device {
  id: string;
  device_name: string;
  device_token: string;
  status: "online" | "offline" | "never_checked_in";
  os_type: string | null;
  app_version: string | null;
  last_seen_at: string | null;
  registered_at: string;
  is_active: boolean;
}

interface DeviceModel {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
  ollama_model_name: string | null;
  is_downloaded: boolean;
  allocated_at: string;
  last_synced_at: string | null;
}

interface SyncLog {
  id: string;
  sync_type: string;
  status: string;
  details: any;
  created_at: string;
}

interface UsageLog {
  id: string;
  model_id: string;
  prompt_count: number;
  tokens_used: number;
  duration_seconds: number;
  logged_at: string;
}

interface AvailableModel {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
}

export default function DeviceDetails() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { id } = useParams();
  const [device, setDevice] = useState<Device | null>(null);
  const [allocatedModels, setAllocatedModels] = useState<DeviceModel[]>([]);
  const [syncLogs, setSyncLogs] = useState<SyncLog[]>([]);
  const [usageLogs, setUsageLogs] = useState<UsageLog[]>([]);
  const [availableModels, setAvailableModels] = useState<AvailableModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [showToken, setShowToken] = useState(false);
  const [isAllocateOpen, setIsAllocateOpen] = useState(false);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [allocating, setAllocating] = useState(false);

  useEffect(() => {
    checkAccess();
  }, [id]);

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
      if (!isAdmin) {
        toast({
          title: "Access Denied",
          description: "Only administrators can access device details",
          variant: "destructive",
        });
        navigate("/devices");
        return;
      }

      loadDeviceData();
    } catch (error) {
      console.error("Error checking access:", error);
      navigate("/auth");
    }
  };

  const loadDeviceData = async () => {
    if (!id) return;

    try {
      const [deviceRes, modelsRes, syncLogsRes, usageLogsRes, availableModelsRes] =
        await Promise.all([
          supabase.from("devices").select("*").eq("id", id).maybeSingle(),
          supabase
            .from("device_models")
            .select("*")
            .eq("device_id", id)
            .order("allocated_at", { ascending: false }),
          supabase
            .from("device_sync_logs")
            .select("*")
            .eq("device_id", id)
            .order("created_at", { ascending: false })
            .limit(50),
          supabase
            .from("device_usage_logs")
            .select("*")
            .eq("device_id", id)
            .order("logged_at", { ascending: false })
            .limit(50),
          supabase
            .from("activated_models")
            .select("id, model_id, model_name, domain")
            .limit(100),
        ]);

      if (deviceRes.error) throw deviceRes.error;
      if (!deviceRes.data) {
        toast({
          title: "Not Found",
          description: "Device not found",
          variant: "destructive",
        });
        navigate("/devices");
        return;
      }

      setDevice(deviceRes.data as Device);
      setAllocatedModels((modelsRes.data as DeviceModel[]) || []);
      setSyncLogs((syncLogsRes.data as SyncLog[]) || []);
      setUsageLogs((usageLogsRes.data as UsageLog[]) || []);
      setAvailableModels((availableModelsRes.data as AvailableModel[]) || []);
    } catch (error: any) {
      console.error("Error loading device data:", error);
      toast({
        title: "Error",
        description: "Failed to load device details",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAllocateModels = async () => {
    if (!id) {
      toast({
        title: "Invalid Device",
        description: "Device ID is missing from route",
        variant: "destructive",
      });
      return;
    }

    if (selectedModels.length === 0) {
      toast({
        title: "No Models Selected",
        description: "Please select at least one model to allocate",
        variant: "destructive",
      });
      return;
    }

    setAllocating(true);
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) throw new Error("Not authenticated");

      const modelsToInsert = selectedModels.map((modelId) => {
        const model = availableModels.find((m) => m.model_id === modelId);
        return {
          device_id: id,
          model_id: modelId,
          model_name: model?.model_name || modelId,
          domain: model?.domain || "unknown",
          allocated_by: user.id,
        };
      });

      const { error } = await supabase.from("device_models").insert(modelsToInsert);

      if (error) throw error;

      toast({
        title: "Models Allocated",
        description: `${selectedModels.length} model(s) allocated successfully`,
      });

      setIsAllocateOpen(false);
      setSelectedModels([]);
      loadDeviceData();
    } catch (error: any) {
      console.error("Error allocating models:", error);
      toast({
        title: "Allocation Failed",
        description: error.message || "Failed to allocate models",
        variant: "destructive",
      });
    } finally {
      setAllocating(false);
    }
  };

  const handleRemoveModel = async (modelId: string, modelName: string) => {
    if (!confirm(`Remove ${modelName} from this device?`)) return;

    try {
      const { error } = await supabase.from("device_models").delete().eq("id", modelId);

      if (error) throw error;

      toast({
        title: "Model Removed",
        description: `${modelName} has been removed from this device`,
      });

      loadDeviceData();
    } catch (error: any) {
      console.error("Error removing model:", error);
      toast({
        title: "Remove Failed",
        description: error.message || "Failed to remove model",
        variant: "destructive",
      });
    }
  };

  const handleResetToken = async () => {
    if (!id) {
      toast({
        title: "Invalid Device",
        description: "Device ID is missing from route",
        variant: "destructive",
      });
      return;
    }

    if (!confirm("Are you sure you want to reset the device token? The device will need to re-register.")) return;

    try {
      const { data: tokenData, error: tokenError } = await supabase.rpc(
        "generate_device_token"
      );
      if (tokenError) throw tokenError;

      const { error } = await supabase
        .from("devices")
        .update({ device_token: tokenData, status: "never_checked_in" })
        .eq("id", id);

      if (error) throw error;

      toast({
        title: "Token Reset",
        description: "Device token has been regenerated",
      });

      loadDeviceData();
    } catch (error: any) {
      console.error("Error resetting token:", error);
      toast({
        title: "Reset Failed",
        description: error.message || "Failed to reset token",
        variant: "destructive",
      });
    }
  };

  const handleTriggerSync = async () => {
    if (!device) return;
    try {
      const localModels = allocatedModels.map((m) => ({
        model_id: m.model_id,
        is_downloaded: !!m.is_downloaded,
      }));
      await performDeviceCheckin(device.device_token, localModels);
      toast({
        title: "Sync requested",
        description: "The device will pull allocated models on next check-in.",
      });
      loadDeviceData();
    } catch (error: any) {
      console.error("Error triggering sync:", error);
      toast({
        title: "Sync failed",
        description: error.message || "Failed to trigger sync",
        variant: "destructive",
      });
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "online":
        return (
          <Badge variant="outline" className="gap-1 bg-success/10 text-success border-success/20">
            <Circle className="h-2 w-2 fill-success" />
            Online
          </Badge>
        );
      case "offline":
        return (
          <Badge variant="outline" className="gap-1 bg-muted text-muted-foreground">
            <Circle className="h-2 w-2 fill-muted-foreground" />
            Offline
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="gap-1">
            <Circle className="h-2 w-2" />
            Never Checked In
          </Badge>
        );
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!device) {
    return null;
  }

  const alreadyAllocated = allocatedModels.map((m) => m.model_id);
  const availableToAllocate = availableModels.filter(
    (m) => !alreadyAllocated.includes(m.model_id)
  );

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate("/devices")}
          className="gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            {device.device_name}
          </h1>
          <p className="text-muted-foreground mt-1">Device ID: {device.id}</p>
        </div>
        <div>{getStatusBadge(device.status)}</div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Last Seen
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {device.last_seen_at
                ? formatDistanceToNow(new Date(device.last_seen_at), { addSuffix: true })
                : "Never"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              OS / Version
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">
              {device.os_type && device.app_version
                ? `${device.os_type} • v${device.app_version}`
                : "—"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Allocated Models
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{allocatedModels.length}</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="models" className="space-y-4">
        <TabsList>
          <TabsTrigger value="models" className="gap-2">
            <Package className="h-4 w-4" />
            Allocated Models
          </TabsTrigger>
          <TabsTrigger value="token" className="gap-2">
            <Key className="h-4 w-4" />
            Token
          </TabsTrigger>
          <TabsTrigger value="sync" className="gap-2">
            <Activity className="h-4 w-4" />
            Sync Logs
          </TabsTrigger>
          <TabsTrigger value="usage" className="gap-2">
            <History className="h-4 w-4" />
            Usage Logs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="models" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Allocated Models ({allocatedModels.length})</CardTitle>
                <Dialog open={isAllocateOpen} onOpenChange={setIsAllocateOpen}>
                  <Button
                    onClick={() => setIsAllocateOpen(true)}
                    className="gap-2"
                    size="sm"
                  >
                    <Plus className="h-4 w-4" />
                    Allocate Models
                  </Button>
                  <DialogContent className="max-w-2xl">
                    <DialogHeader>
                      <DialogTitle>Allocate Models to Device</DialogTitle>
                      <DialogDescription>
                        Select models to allocate to {device.device_name}. The device will
                        receive these during the next sync.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      {availableToAllocate.length === 0 ? (
                        <p className="text-center text-muted-foreground py-8">
                          No more models available to allocate
                        </p>
                      ) : (
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                          {availableToAllocate.map((model) => (
                            <label
                              key={model.id}
                              className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 cursor-pointer"
                            >
                              <input
                                type="checkbox"
                                checked={selectedModels.includes(model.model_id)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setSelectedModels([...selectedModels, model.model_id]);
                                  } else {
                                    setSelectedModels(
                                      selectedModels.filter((id) => id !== model.model_id)
                                    );
                                  }
                                }}
                                className="h-4 w-4"
                              />
                              <div className="flex-1">
                                <p className="font-medium">{model.model_name}</p>
                                <p className="text-sm text-muted-foreground">
                                  {model.domain} • {model.model_id}
                                </p>
                              </div>
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                    <DialogFooter>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setIsAllocateOpen(false);
                          setSelectedModels([]);
                        }}
                        disabled={allocating}
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={handleAllocateModels}
                        disabled={allocating || selectedModels.length === 0}
                      >
                        {allocating ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Allocating...
                          </>
                        ) : (
                          `Allocate ${selectedModels.length} Model(s)`
                        )}
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>
            </CardHeader>
            <CardContent>
              {allocatedModels.length === 0 ? (
                <div className="text-center py-12">
                  <Package className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <h3 className="text-lg font-medium text-foreground mb-2">
                    No Models Allocated
                  </h3>
                  <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
                    Allocate models to this device to enable AI capabilities
                  </p>
                  <Button
                    onClick={() => setIsAllocateOpen(true)}
                    className="gap-2"
                  >
                    <Plus className="h-4 w-4" />
                    Allocate Models
                  </Button>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Model Name</TableHead>
                      <TableHead>Domain</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Allocated</TableHead>
                      <TableHead>Last Synced</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {allocatedModels.map((model) => (
                      <TableRow key={model.id}>
                        <TableCell className="font-medium">{model.model_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{model.domain}</Badge>
                        </TableCell>
                        <TableCell>
                          {model.is_downloaded ? (
                            <Badge variant="outline" className="bg-success/10 text-success">
                              Downloaded
                            </Badge>
                          ) : (
                            <Badge variant="outline">Pending</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDistanceToNow(new Date(model.allocated_at), {
                            addSuffix: true,
                          })}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {model.last_synced_at
                            ? formatDistanceToNow(new Date(model.last_synced_at), {
                                addSuffix: true,
                              })
                            : "Never"}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRemoveModel(model.id, model.model_name)}
                            className="gap-1 text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-3 w-3" />
                            Remove
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="token" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Device Token</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Registration Token</Label>
                <div className="flex gap-2">
                  <div className="flex-1 p-3 rounded-lg bg-muted font-mono text-sm">
                    {showToken ? device.device_token : "••••••••••••••••••••••••••"}
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => setShowToken(!showToken)}
                  >
                    {showToken ? "Hide" : "Show"}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      navigator.clipboard.writeText(device.device_token);
                      toast({
                        title: "Copied",
                        description: "Token copied to clipboard",
                      });
                    }}
                  >
                    Copy
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">
                  Use this token in the Electron app to authenticate with Fideon OS
                </p>
              </div>

              <div className="pt-4 border-t border-border">
                <Button
                  variant="destructive"
                  onClick={handleResetToken}
                  className="gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  Reset Token
                </Button>
                <p className="text-sm text-muted-foreground mt-2">
                  Resetting the token will invalidate the current token. The device will need
                  to re-register.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sync" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Sync History ({syncLogs.length})</CardTitle>
                <Button size="sm" className="gap-2" onClick={handleTriggerSync}>
                  <RefreshCw className="h-4 w-4" />
                  Sync Now
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {syncLogs.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  No sync logs available
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Details</TableHead>
                      <TableHead>Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {syncLogs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell>
                          <Badge variant="outline">{log.sync_type}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={log.status === "success" ? "outline" : "destructive"}
                            className={
                              log.status === "success" ? "bg-success/10 text-success" : ""
                            }
                          >
                            {log.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground max-w-md truncate">
                          {log.details ? JSON.stringify(log.details) : "—"}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {format(new Date(log.created_at), "MMM d, yyyy HH:mm:ss")}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="usage" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Usage Statistics ({usageLogs.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {usageLogs.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  No usage data available
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Model</TableHead>
                      <TableHead>Prompts</TableHead>
                      <TableHead>Tokens</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {usageLogs.map((log) => (
                      <TableRow key={log.id}>
                        <TableCell className="font-medium">{log.model_id}</TableCell>
                        <TableCell>{log.prompt_count}</TableCell>
                        <TableCell>{log.tokens_used.toLocaleString()}</TableCell>
                        <TableCell>{log.duration_seconds}s</TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {format(new Date(log.logged_at), "MMM d, yyyy HH:mm")}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
