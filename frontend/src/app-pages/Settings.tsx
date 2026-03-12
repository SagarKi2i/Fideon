import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { 
  Building2, 
  FolderOpen, 
  Settings as SettingsIcon, 
  Shield,
  CheckCircle2,
  AlertCircle,
  Key,
  Globe,
  Zap,
  Eye,
  EyeOff,
  Pencil,
  Sparkles,
  RotateCcw,
  DollarSign,
  Scale,
  Download,
  Code2,
  Monitor
} from "lucide-react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useToast } from "@/hooks/use-toast";
import { useWorkflowSettings } from "@/hooks/useWorkflowSettings";

// Import AMS logos
import appliedEpicLogo from "@/assets/logos/applied-epic-logo.png";
import hawksoftLogo from "@/assets/logos/hawksoft-logo.png";
import ams360Logo from "@/assets/logos/ams360-logo.png";
import qqCatalystLogo from "@/assets/logos/qq-catalyst-logo.png";
import ezlynxLogo from "@/assets/logos/ezlynx-logo.png";

interface CarrierCredentialData {
  username: string;
  password: string;
  enterpriseId: string;
}

interface CarrierCredential {
  id: string;
  name: string;
  logo: string;
  connected: boolean;
  lastSync?: string;
  credentials?: CarrierCredentialData;
}

interface AMSSystem {
  id: string;
  name: string;
  logo: string | { src: string };
  connected: boolean;
  description: string;
  connectionType?: "sdk" | "ui";
  sdkCredentials?: { clientId: string; clientKey: string };
  uiCredentials?: { username: string; password: string; enterpriseId: string };
}

const logoSrc = (logo: string | { src: string }) => (typeof logo === "string" ? logo : logo.src);

const carriers: CarrierCredential[] = [
  { id: "travelers", name: "Travelers", logo: "🏢", connected: false },
  { id: "hartford", name: "The Hartford", logo: "🦌", connected: false },
  { id: "chubb", name: "Chubb", logo: "🛡️", connected: true, lastSync: "2 hours ago", credentials: { username: "user@agency.com", password: "••••••••", enterpriseId: "ENT-12345" } },
  { id: "liberty-mutual", name: "Liberty Mutual", logo: "🗽", connected: false },
  { id: "nationwide", name: "Nationwide", logo: "🏠", connected: true, lastSync: "1 day ago", credentials: { username: "agent@nationwide.com", password: "••••••••", enterpriseId: "NW-67890" } },
  { id: "progressive", name: "Progressive Commercial", logo: "📊", connected: false },
  { id: "amtrust", name: "AmTrust", logo: "💼", connected: false },
  { id: "markel", name: "Markel", logo: "📈", connected: false },
  { id: "berkshire", name: "Berkshire Hathaway", logo: "🏛️", connected: false },
  { id: "zurich", name: "Zurich", logo: "🏔️", connected: false },
];

const amsSystemsList: AMSSystem[] = [
  { 
    id: "applied-epic", 
    name: "Applied Epic", 
    logo: appliedEpicLogo, 
    connected: true,
    description: "Enterprise agency management with integrated analytics"
  },
  { 
    id: "hawksoft", 
    name: "HawkSoft", 
    logo: hawksoftLogo, 
    connected: false,
    description: "Cloud-based agency management for P&C agencies"
  },
  { 
    id: "ams360", 
    name: "AMS 360", 
    logo: ams360Logo, 
    connected: false,
    description: "Vertafore's comprehensive agency management solution"
  },
  { 
    id: "qq-catalyst", 
    name: "QQ Catalyst", 
    logo: qqCatalystLogo, 
    connected: false,
    description: "Integrated management system for insurance professionals"
  },
  { 
    id: "ezlynx", 
    name: "EZLynx", 
    logo: ezlynxLogo, 
    connected: false,
    description: "Rating, management, and consumer engagement platform"
  },
];

export default function Settings() {
  const { toast } = useToast();
  const { settings: workflowSettings, updateSettings: updateWorkflowSettings, resetToDefaults, DEFAULT_SETTINGS } = useWorkflowSettings();
  const [carrierCredentials, setCarrierCredentials] = useState(carriers);
  const [amsSystems, setAmsSystems] = useState(amsSystemsList);
  
  // Carrier credential modal state
  const [isCredentialModalOpen, setIsCredentialModalOpen] = useState(false);
  const [selectedCarrier, setSelectedCarrier] = useState<CarrierCredential | null>(null);
  const [credentialForm, setCredentialForm] = useState<CarrierCredentialData>({
    username: "",
    password: "",
    enterpriseId: ""
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  // AMS configuration modal state
  const [isAMSConfigOpen, setIsAMSConfigOpen] = useState(false);
  const [selectedAMS, setSelectedAMS] = useState<AMSSystem | null>(null);
  const [amsConnectionType, setAmsConnectionType] = useState<"sdk" | "ui">("sdk");
  const [amsSDKForm, setAmsSDKForm] = useState({ clientId: "", clientKey: "" });
  const [amsUIForm, setAmsUIForm] = useState({ username: "", password: "", enterpriseId: "" });
  const [showAMSPassword, setShowAMSPassword] = useState(false);
  const [showAMSKey, setShowAMSKey] = useState(false);

  const openCredentialModal = (carrier: CarrierCredential, editing: boolean = false) => {
    setSelectedCarrier(carrier);
    setIsEditing(editing);
    if (editing && carrier.credentials) {
      setCredentialForm({
        username: carrier.credentials.username,
        password: "",
        enterpriseId: carrier.credentials.enterpriseId
      });
    } else {
      setCredentialForm({ username: "", password: "", enterpriseId: "" });
    }
    setShowPassword(false);
    setIsCredentialModalOpen(true);
  };

  const handleCredentialSubmit = () => {
    if (!selectedCarrier) return;
    
    if (!credentialForm.username.trim() || !credentialForm.password.trim()) {
      toast({
        title: "Validation Error",
        description: "Username and password are required",
        variant: "destructive",
      });
      return;
    }

    setCarrierCredentials(prev => 
      prev.map(c => 
        c.id === selectedCarrier.id 
          ? { 
              ...c, 
              connected: true, 
              lastSync: "Just now",
              credentials: {
                username: credentialForm.username,
                password: "••••••••",
                enterpriseId: credentialForm.enterpriseId
              }
            }
          : c
      )
    );
    
    toast({
      title: isEditing ? "Credentials Updated" : "Connected",
      description: `${selectedCarrier.name} ${isEditing ? "credentials updated" : "connected"} successfully`,
    });
    
    setIsCredentialModalOpen(false);
    setSelectedCarrier(null);
    setCredentialForm({ username: "", password: "", enterpriseId: "" });
  };

  const handleCarrierDisconnect = (carrierId: string) => {
    const carrier = carrierCredentials.find(c => c.id === carrierId);
    setCarrierCredentials(prev => 
      prev.map(c => 
        c.id === carrierId 
          ? { ...c, connected: false, lastSync: undefined, credentials: undefined }
          : c
      )
    );
    toast({
      title: "Disconnected",
      description: `${carrier?.name} disconnected successfully`,
    });
  };

  const handleAMSConnect = (amsId: string) => {
    setAmsSystems(prev => 
      prev.map(a => 
        a.id === amsId 
          ? { ...a, connected: !a.connected }
          : a
      )
    );
    const ams = amsSystems.find(a => a.id === amsId);
    toast({
      title: ams?.connected ? "Disconnected" : "Connected",
      description: `${ams?.name} ${ams?.connected ? "disconnected" : "connected"} successfully`,
    });
  };

  const openAMSConfigModal = (ams: AMSSystem) => {
    setSelectedAMS(ams);
    setAmsConnectionType(ams.connectionType || "sdk");
    setAmsSDKForm(ams.sdkCredentials || { clientId: "", clientKey: "" });
    setAmsUIForm(ams.uiCredentials || { username: "", password: "", enterpriseId: "" });
    setShowAMSPassword(false);
    setShowAMSKey(false);
    setIsAMSConfigOpen(true);
  };

  const handleAMSConfigSubmit = () => {
    if (!selectedAMS) return;

    if (amsConnectionType === "sdk") {
      if (!amsSDKForm.clientId.trim() || !amsSDKForm.clientKey.trim()) {
        toast({ title: "Validation Error", description: "Client ID and Client Key are required", variant: "destructive" });
        return;
      }
    } else {
      if (!amsUIForm.username.trim() || !amsUIForm.password.trim() || !amsUIForm.enterpriseId.trim()) {
        toast({ title: "Validation Error", description: "Username, Password, and Enterprise ID are required", variant: "destructive" });
        return;
      }
    }

    setAmsSystems(prev =>
      prev.map(a =>
        a.id === selectedAMS.id
          ? {
              ...a,
              connected: true,
              connectionType: amsConnectionType,
              sdkCredentials: amsConnectionType === "sdk" ? amsSDKForm : undefined,
              uiCredentials: amsConnectionType === "ui" ? { ...amsUIForm, password: "••••••••" } : undefined,
            }
          : a
      )
    );

    toast({
      title: "AMS Configured",
      description: `${selectedAMS.name} connected via ${amsConnectionType === "sdk" ? "SDK" : "UI"} successfully`,
    });

    setIsAMSConfigOpen(false);
    setSelectedAMS(null);
  };

  const connectedCarriers = carrierCredentials.filter(c => c.connected).length;
  const connectedAMS = amsSystems.filter(a => a.connected).length;

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Settings</h1>
        <p className="text-muted-foreground mt-1">
          Configure your workspace, carrier credentials, and AMS integrations
        </p>
      </div>

      <Tabs defaultValue="carriers" className="space-y-4">
        <TabsList className="bg-muted flex-wrap h-auto gap-1">
          <TabsTrigger value="carriers" className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            <span className="hidden sm:inline">Carriers</span>
            <Badge variant="secondary" className="ml-1">{connectedCarriers}</Badge>
          </TabsTrigger>
          <TabsTrigger value="ams" className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4" />
            <span className="hidden sm:inline">AMS Systems</span>
            <Badge variant="secondary" className="ml-1">{connectedAMS}</Badge>
          </TabsTrigger>
          <TabsTrigger value="workflow" className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            <span className="hidden sm:inline">Workflow</span>
          </TabsTrigger>
          <TabsTrigger value="general" className="flex items-center gap-2">
            <SettingsIcon className="h-4 w-4" />
            <span className="hidden sm:inline">General</span>
          </TabsTrigger>
          <TabsTrigger value="system" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            <span className="hidden sm:inline">System</span>
          </TabsTrigger>
        </TabsList>

        {/* Carrier Credentials Tab */}
        <TabsContent value="carriers" className="space-y-4">
          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <Building2 className="h-5 w-5 text-primary" />
                Carrier Credentials
              </CardTitle>
              <CardDescription>
                Connect to carrier portals with your username, password, and enterprise ID
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {carrierCredentials.map((carrier) => (
                  <Card 
                    key={carrier.id} 
                    className={`border transition-all ${
                      carrier.connected 
                        ? "border-primary/50 bg-primary/5" 
                        : "border-border hover:border-primary/30"
                    }`}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-3xl">{carrier.logo}</div>
                          <div>
                            <p className="font-medium text-foreground">{carrier.name}</p>
                            {carrier.connected && carrier.credentials && (
                              <p className="text-xs text-muted-foreground">
                                {carrier.credentials.username}
                              </p>
                            )}
                            {carrier.connected && carrier.lastSync && (
                              <p className="text-xs text-muted-foreground flex items-center gap-1">
                                <CheckCircle2 className="h-3 w-3 text-green-500" />
                                Synced {carrier.lastSync}
                              </p>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {carrier.connected ? (
                            <>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => openCredentialModal(carrier, true)}
                                title="Edit credentials"
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleCarrierDisconnect(carrier.id)}
                              >
                                Disconnect
                              </Button>
                            </>
                          ) : (
                            <Button
                              size="sm"
                              onClick={() => openCredentialModal(carrier, false)}
                              className="bg-gradient-primary"
                            >
                              Connect
                            </Button>
                          )}
                        </div>
                      </div>
                      
                      {/* Show credential summary for connected carriers */}
                      {carrier.connected && carrier.credentials && (
                        <div className="mt-3 pt-3 border-t border-border">
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div>
                              <span className="text-muted-foreground">Enterprise ID:</span>
                              <span className="ml-1 font-medium">{carrier.credentials.enterpriseId || "N/A"}</span>
                            </div>
                            <div className="flex items-center justify-end">
                              <Badge variant="outline" className="text-green-600 border-green-600">
                                Active
                              </Badge>
                            </div>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <Key className="h-5 w-5 text-primary" />
                API Configuration
              </CardTitle>
              <CardDescription>
                Configure API access for carrier integrations
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                <div className="flex items-center gap-3">
                  <Shield className="h-5 w-5 text-primary" />
                  <div>
                    <p className="font-medium">OAuth 2.0 Authentication</p>
                    <p className="text-sm text-muted-foreground">Secure token-based authentication for all carriers</p>
                  </div>
                </div>
                <Switch defaultChecked />
              </div>
              <div className="flex items-center justify-between p-4 rounded-lg border border-border">
                <div className="flex items-center gap-3">
                  <Globe className="h-5 w-5 text-primary" />
                  <div>
                    <p className="font-medium">Auto-sync Documents</p>
                    <p className="text-sm text-muted-foreground">Automatically sync new documents daily</p>
                  </div>
                </div>
                <Switch defaultChecked />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* AMS Systems Tab */}
        <TabsContent value="ams" className="space-y-4">
          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <FolderOpen className="h-5 w-5 text-primary" />
                Agency Management Systems
              </CardTitle>
              <CardDescription>
                Connect your AMS to automatically attach retrieved documents
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {amsSystems.map((ams) => (
                  <Card 
                    key={ams.id} 
                    className={`border transition-all ${
                      ams.connected 
                        ? "border-primary/50 bg-primary/5" 
                        : "border-border hover:border-primary/30"
                    }`}
                  >
                    <CardContent className="p-4">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                          <img src={logoSrc(ams.logo)} alt={`${ams.name} logo`} className="h-12 w-12 object-contain" />
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="font-semibold text-lg text-foreground">{ams.name}</p>
                              {ams.connected && (
                                <Badge variant="outline" className="text-green-600 border-green-600">
                                  <CheckCircle2 className="h-3 w-3 mr-1" />
                                  Active
                                </Badge>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">{ams.description}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 sm:ml-auto">
                          {ams.connected ? (
                            <>
                              <Button variant="outline" size="sm" onClick={() => openAMSConfigModal(ams)}>
                                Configure
                              </Button>
                              <Button 
                                variant="outline" 
                                size="sm"
                                onClick={() => handleAMSConnect(ams.id)}
                              >
                                Disconnect
                              </Button>
                            </>
                          ) : (
                            <Button 
                              size="sm"
                              onClick={() => openAMSConfigModal(ams)}
                              className="bg-gradient-primary"
                            >
                              Connect AMS
                            </Button>
                          )}
                        </div>
                      </div>

                      {ams.connected && (
                        <div className="mt-4 pt-4 border-t border-border">
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                            <div>
                              <p className="text-muted-foreground">Connection</p>
                              <p className="font-medium flex items-center gap-1">
                                {ams.connectionType === "ui" ? <Monitor className="h-3 w-3" /> : <Code2 className="h-3 w-3" />}
                                {ams.connectionType === "ui" ? "UI Login" : "SDK"}
                              </p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Last Sync</p>
                              <p className="font-medium">2 hours ago</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Documents Synced</p>
                              <p className="font-medium">1,247</p>
                            </div>
                            <div>
                              <p className="text-muted-foreground">Status</p>
                              <p className="font-medium text-green-600 flex items-center gap-1">
                                <CheckCircle2 className="h-3 w-3" />
                                Healthy
                              </p>
                            </div>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-amber-500" />
                Integration Notes
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="text-primary">•</span>
                  Only one AMS can be active at a time for document attachment
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-primary">•</span>
                  Ensure your AMS account has API access enabled
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-primary">•</span>
                  Documents are attached to the client record matching the policy number
                </li>
              </ul>
            </CardContent>
          </Card>

          {/* AMS Configuration Dialog */}
          <Dialog open={isAMSConfigOpen} onOpenChange={setIsAMSConfigOpen}>
            <DialogContent className="sm:max-w-[500px]">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {selectedAMS && <img src={logoSrc(selectedAMS.logo)} alt="" className="h-8 w-8 object-contain" />}
                  Configure {selectedAMS?.name}
                </DialogTitle>
                <DialogDescription>
                  Choose how to connect to {selectedAMS?.name}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-5">
                <RadioGroup value={amsConnectionType} onValueChange={(v) => setAmsConnectionType(v as "sdk" | "ui")} className="grid grid-cols-2 gap-3">
                  <Label
                    htmlFor="ams-sdk"
                    className={`flex flex-col items-center gap-2 rounded-lg border-2 p-4 cursor-pointer transition-all ${
                      amsConnectionType === "sdk" ? "border-primary bg-primary/5" : "border-border hover:border-primary/30"
                    }`}
                  >
                    <RadioGroupItem value="sdk" id="ams-sdk" className="sr-only" />
                    <Code2 className="h-6 w-6 text-primary" />
                    <span className="font-medium text-sm">Via SDK</span>
                    <span className="text-xs text-muted-foreground text-center">Client ID & Key</span>
                  </Label>
                  <Label
                    htmlFor="ams-ui"
                    className={`flex flex-col items-center gap-2 rounded-lg border-2 p-4 cursor-pointer transition-all ${
                      amsConnectionType === "ui" ? "border-primary bg-primary/5" : "border-border hover:border-primary/30"
                    }`}
                  >
                    <RadioGroupItem value="ui" id="ams-ui" className="sr-only" />
                    <Monitor className="h-6 w-6 text-primary" />
                    <span className="font-medium text-sm">Via UI</span>
                    <span className="text-xs text-muted-foreground text-center">Username & Password</span>
                  </Label>
                </RadioGroup>

                {amsConnectionType === "sdk" ? (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="ams-client-id">Client ID</Label>
                      <Input
                        id="ams-client-id"
                        placeholder="Enter Client ID"
                        value={amsSDKForm.clientId}
                        onChange={(e) => setAmsSDKForm(prev => ({ ...prev, clientId: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="ams-client-key">Client Key</Label>
                      <div className="relative">
                        <Input
                          id="ams-client-key"
                          type={showAMSKey ? "text" : "password"}
                          placeholder="Enter Client Key"
                          value={amsSDKForm.clientKey}
                          onChange={(e) => setAmsSDKForm(prev => ({ ...prev, clientKey: e.target.value }))}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                          onClick={() => setShowAMSKey(!showAMSKey)}
                        >
                          {showAMSKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="ams-username">Username</Label>
                      <Input
                        id="ams-username"
                        placeholder="Enter username"
                        value={amsUIForm.username}
                        onChange={(e) => setAmsUIForm(prev => ({ ...prev, username: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="ams-password">Password</Label>
                      <div className="relative">
                        <Input
                          id="ams-password"
                          type={showAMSPassword ? "text" : "password"}
                          placeholder="Enter password"
                          value={amsUIForm.password}
                          onChange={(e) => setAmsUIForm(prev => ({ ...prev, password: e.target.value }))}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                          onClick={() => setShowAMSPassword(!showAMSPassword)}
                        >
                          {showAMSPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="ams-enterprise-id">Enterprise ID</Label>
                      <Input
                        id="ams-enterprise-id"
                        placeholder="Enter Enterprise ID"
                        value={amsUIForm.enterpriseId}
                        onChange={(e) => setAmsUIForm(prev => ({ ...prev, enterpriseId: e.target.value }))}
                      />
                    </div>
                  </div>
                )}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAMSConfigOpen(false)}>Cancel</Button>
                <Button onClick={handleAMSConfigSubmit} className="bg-gradient-primary">
                  {selectedAMS?.connected ? "Update" : "Connect"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        {/* General Tab */}
        <TabsContent value="general" className="space-y-4">
          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground">Workspace Settings</CardTitle>
              <CardDescription>Manage your workspace preferences</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="workspace">Workspace Name</Label>
                <Input id="workspace" placeholder="My Workspace" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="region">Region</Label>
                <Input id="region" placeholder="Local" disabled />
              </div>
              <Button>Save Changes</Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Workflow Intelligence Tab */}
        <TabsContent value="workflow" className="space-y-4">
          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-card-foreground flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-primary" />
                    Workflow Intelligence
                  </CardTitle>
                  <CardDescription>
                    Configure smart recommendations and cross-pod suggestions
                  </CardDescription>
                </div>
                <Button 
                  variant="outline" 
                  size="sm"
                  onClick={() => {
                    resetToDefaults();
                    toast({
                      title: "Settings Reset",
                      description: "Workflow settings have been reset to defaults",
                    });
                  }}
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Reset to Defaults
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Master Toggle */}
              <div className="flex items-center justify-between p-4 rounded-lg border border-border bg-muted/30">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <Sparkles className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium text-foreground">Enable Smart Recommendations</p>
                    <p className="text-sm text-muted-foreground">
                      Show contextual suggestions based on workflow activity
                    </p>
                  </div>
                </div>
                <Switch 
                  checked={workflowSettings.enableSmartRecommendations}
                  onCheckedChange={(checked) => updateWorkflowSettings({ enableSmartRecommendations: checked })}
                />
              </div>

              {/* Document Retrieval Threshold */}
              <div className={`space-y-4 p-4 rounded-lg border border-border ${!workflowSettings.enableSmartRecommendations ? 'opacity-50 pointer-events-none' : ''}`}>
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-blue-500/10 flex items-center justify-center">
                    <Download className="h-5 w-5 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-foreground">Document Retrieval - Quote Recommendation</p>
                    <p className="text-sm text-muted-foreground">
                      Suggest Quote Generation when invoice premium exceeds this threshold
                    </p>
                  </div>
                </div>
                
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-2">
                      <DollarSign className="h-4 w-4 text-muted-foreground" />
                      Premium Threshold
                    </Label>
                    <div className="flex items-center gap-2">
                      <span className="text-xl font-bold text-primary">
                        ${workflowSettings.documentRetrievalPremiumThreshold.toLocaleString()}
                      </span>
                      {workflowSettings.documentRetrievalPremiumThreshold !== DEFAULT_SETTINGS.documentRetrievalPremiumThreshold && (
                        <Badge variant="secondary" className="text-xs">Modified</Badge>
                      )}
                    </div>
                  </div>
                  <Slider
                    value={[workflowSettings.documentRetrievalPremiumThreshold]}
                    onValueChange={([value]) => updateWorkflowSettings({ documentRetrievalPremiumThreshold: value })}
                    min={1000}
                    max={50000}
                    step={500}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>$1,000</span>
                    <span>$50,000</span>
                  </div>
                </div>
              </div>

              {/* Policy Comparison Threshold */}
              <div className={`space-y-4 p-4 rounded-lg border border-border ${!workflowSettings.enableSmartRecommendations ? 'opacity-50 pointer-events-none' : ''}`}>
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-green-500/10 flex items-center justify-center">
                    <Scale className="h-5 w-5 text-green-600" />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-foreground">Policy Comparison - Quote Recommendation</p>
                    <p className="text-sm text-muted-foreground">
                      Suggest Quote Generation when compared policy premium exceeds this threshold
                    </p>
                  </div>
                </div>
                
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label className="flex items-center gap-2">
                      <DollarSign className="h-4 w-4 text-muted-foreground" />
                      Premium Threshold
                    </Label>
                    <div className="flex items-center gap-2">
                      <span className="text-xl font-bold text-primary">
                        ${workflowSettings.policyComparisonPremiumThreshold.toLocaleString()}
                      </span>
                      {workflowSettings.policyComparisonPremiumThreshold !== DEFAULT_SETTINGS.policyComparisonPremiumThreshold && (
                        <Badge variant="secondary" className="text-xs">Modified</Badge>
                      )}
                    </div>
                  </div>
                  <Slider
                    value={[workflowSettings.policyComparisonPremiumThreshold]}
                    onValueChange={([value]) => updateWorkflowSettings({ policyComparisonPremiumThreshold: value })}
                    min={1000}
                    max={50000}
                    step={500}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>$1,000</span>
                    <span>$50,000</span>
                  </div>
                </div>
              </div>

              {/* Info Card */}
              <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-foreground">How it works</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      When premiums exceed your configured thresholds, the system will display recommendations 
                      to use the Quote Generation pod to find potentially better rates from competitive carriers.
                      This helps identify savings opportunities across your workflow.
                    </p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* System Tab */}
        <TabsContent value="system" className="space-y-4">
          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground">System Diagnostics</CardTitle>
              <CardDescription>View system information and connected endpoints</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm text-muted-foreground">Status</Label>
                  <p className="text-foreground font-medium flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    Connected
                  </p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">Active Carriers</Label>
                  <p className="text-foreground font-medium">{connectedCarriers} Connected</p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">Active AMS</Label>
                  <p className="text-foreground font-medium">{connectedAMS} Connected</p>
                </div>
                <div>
                  <Label className="text-sm text-muted-foreground">API Health</Label>
                  <p className="text-foreground font-medium text-green-600">All Systems Operational</p>
                </div>
              </div>
              <Button variant="secondary" className="w-full">
                Run Diagnostics
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Carrier Credential Modal */}
      <Dialog open={isCredentialModalOpen} onOpenChange={setIsCredentialModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3">
              <span className="text-3xl">{selectedCarrier?.logo}</span>
              {isEditing ? "Edit" : "Connect to"} {selectedCarrier?.name}
            </DialogTitle>
            <DialogDescription>
              Enter your carrier portal credentials to enable document retrieval and quoting.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="carrier-username">Username / Email</Label>
              <Input
                id="carrier-username"
                type="email"
                placeholder="agent@agency.com"
                value={credentialForm.username}
                onChange={(e) => setCredentialForm(prev => ({ ...prev, username: e.target.value }))}
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="carrier-password">Password</Label>
              <div className="relative">
                <Input
                  id="carrier-password"
                  type={showPassword ? "text" : "password"}
                  placeholder={isEditing ? "Enter new password" : "••••••••"}
                  value={credentialForm.password}
                  onChange={(e) => setCredentialForm(prev => ({ ...prev, password: e.target.value }))}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="carrier-enterprise-id">Enterprise ID (Optional)</Label>
              <Input
                id="carrier-enterprise-id"
                placeholder="ENT-12345"
                value={credentialForm.enterpriseId}
                onChange={(e) => setCredentialForm(prev => ({ ...prev, enterpriseId: e.target.value }))}
              />
              <p className="text-xs text-muted-foreground">
                Some carriers require an enterprise or agency ID for API access
              </p>
            </div>
          </div>
          
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setIsCredentialModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCredentialSubmit} className="bg-gradient-primary">
              <Key className="h-4 w-4 mr-2" />
              {isEditing ? "Update Credentials" : "Connect"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
