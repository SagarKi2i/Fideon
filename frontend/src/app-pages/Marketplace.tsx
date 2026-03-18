import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Shield, 
  Heart, 
  Building2, 
  Scale, 
  Plane,
  CheckCircle2,
  ShieldCheck,
  FilePlus,
  AlertCircle,
  FileText,
  Search,
  RefreshCw,
  ClipboardCheck,
  Target,
  UserCheck,
  Layers,
  Mail,
  Flag,
  Calculator,
  Sparkles,
  Bot,
  Inbox,
  Filter,
  Activity,
  ShieldAlert,
  RotateCcw,
  FileCheck,
  Repeat,
  Download,
  Briefcase,
  Building,
  SendHorizontal,
  Clock as ClockIcon
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { brokerModels, mgaModels, carrierModels, InsuranceModel } from "@/lib/insuranceMocks";
import { useUserRole } from "@/hooks/useUserRole";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";
import { Skeleton } from "@/components/ui/skeleton";

interface ModelCard {
  id: string;
  name: string;
  domain: string;
  version: string;
  description: string;
  capabilities: string[];
  icon: any;
  segment?: string;
  category?: string;
}

function getModelVersion(modelId: string): string {
  const versionMap: Record<string, string> = {
    "quote-generation": "v2.1",
    "policy-comparison": "v2.0",
    "document-retrieval": "v2.3",
    "claims-fnol": "v1.9",
    "acord-parser": "v2.2",
    "carrier-submission-intake": "v1.7",
    "carrier-claims-adjudication": "v1.8",
  };
  return versionMap[modelId] ?? "v1.0";
}

const iconMap: Record<string, any> = {
  scale: Scale,
  "shield-check": ShieldCheck,
  "file-plus": FilePlus,
  "alert-circle": AlertCircle,
  "file-text": FileText,
  search: Search,
  "refresh-cw": RefreshCw,
  "clipboard-check": ClipboardCheck,
  target: Target,
  "user-check": UserCheck,
  layers: Layers,
  mail: Mail,
  flag: Flag,
  calculator: Calculator,
  bot: Bot,
  inbox: Inbox,
  filter: Filter,
  activity: Activity,
  "shield-alert": ShieldAlert,
  "rotate-ccw": RotateCcw,
  "file-check": FileCheck,
  repeat: Repeat,
  download: Download
};

// Insurance segment labels and icons
const insuranceSegments: Record<string, { label: string; icon: any; description: string }> = {
  broker: { label: "Brokers", icon: Briefcase, description: "Tools for insurance brokers and agents" },
  mga: { label: "MGA", icon: Building, description: "Managing General Agent operations" },
  carrier: { label: "Carriers", icon: Shield, description: "Insurance carrier underwriting & claims" }
};

// Convert insurance models to ModelCard format
const convertInsuranceModels = (models: InsuranceModel[]): ModelCard[] => 
  models.map(model => ({
    id: model.id,
    name: model.name,
    domain: model.domain,
    version: getModelVersion(model.id),
    description: model.description,
    capabilities: [model.category],
    icon: iconMap[model.icon] || Shield,
    segment: model.segment,
    category: model.category
  }));

const brokerModelCards = convertInsuranceModels(brokerModels);
const mgaModelCards = convertInsuranceModels(mgaModels);
const carrierModelCards = convertInsuranceModels(carrierModels);

// Non-insurance domain models
const otherDomainModels: ModelCard[] = [
  {
    id: "healthcare-basic",
    name: "Healthcare Assistant",
    domain: "healthcare",
    version: "v1.0",
    description: "Basic medical assistance and pre-authorization support",
    capabilities: ["Pre-Auth Support", "Basic Medical Q&A", "Document Review"],
    icon: Heart,
  },
  {
    id: "healthcare-clinical",
    name: "Clinical Intelligence Pro",
    domain: "healthcare",
    version: "v1.3",
    description: "Advanced clinical summaries and diagnosis support",
    capabilities: ["Clinical Summary", "Diagnosis Support", "Advanced Medical Q&A", "Treatment Plans"],
    icon: Heart,
  },
  {
    id: "banking-basic",
    name: "Banking Compliance Assistant",
    domain: "banking",
    version: "v1.0",
    description: "Basic KYC and compliance checking for financial institutions",
    capabilities: ["KYC Analysis", "Basic Compliance", "Document Verification"],
    icon: Building2,
  },
  {
    id: "banking-advanced",
    name: "Financial Intelligence Pro",
    domain: "banking",
    version: "v1.2",
    description: "Advanced risk assessment and fraud detection",
    capabilities: ["Advanced Risk Assessment", "Fraud Detection", "Compliance Monitoring", "AML Screening"],
    icon: Building2,
  },
  {
    id: "legal-basic",
    name: "Legal Document Analyzer",
    domain: "legal",
    version: "v1.0",
    description: "Basic contract review and clause identification",
    capabilities: ["Contract Review", "Clause Finder", "Basic Legal Q&A"],
    icon: Scale,
  },
  {
    id: "legal-advanced",
    name: "Legal Intelligence Pro",
    domain: "legal",
    version: "v1.1",
    description: "Advanced risk identification and compliance checking",
    capabilities: ["Risk Identification", "Compliance Review", "Advanced Analysis", "Legal Research"],
    icon: Scale,
  },
  {
    id: "travel-basic",
    name: "Travel Assistant",
    domain: "travel",
    version: "v1.0",
    description: "Basic travel information and recommendations",
    capabilities: ["Destination Info", "Travel Q&A", "Basic Planning"],
    icon: Plane,
  },
  {
    id: "travel-advanced",
    name: "Travel Intelligence Pro",
    domain: "travel",
    version: "v1.1",
    description: "Advanced itinerary planning and personalized recommendations",
    capabilities: ["Smart Itinerary", "Personalized Recommendations", "Advanced Planning", "Real-time Updates"],
    icon: Plane,
  },
];

// Combined models for counting
const allInsuranceModels = [...brokerModelCards, ...mgaModelCards, ...carrierModelCards];
const allModels: ModelCard[] = [...allInsuranceModels, ...otherDomainModels];

const domainLabels: Record<string, string> = {
  insurance: "Insurance",
  healthcare: "Healthcare",
  banking: "Banking & Finance",
  legal: "Legal",
  travel: "Travel & Tourism",
};

export default function Marketplace() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { role, isViewer, isGuest } = useUserRole();
  const [activatedModelIds, setActivatedModelIds] = useState<Set<string>>(new Set());
  const [pendingRequestIds, setPendingRequestIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [selectedDomain, setSelectedDomain] = useState<string>("all");
  const [selectedInsuranceSegment, setSelectedInsuranceSegment] = useState<string>("all");

  useEffect(() => {
    loadActivatedModels();
    loadPendingRequests();
  }, []);

  const loadActivatedModels = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        setLoading(false);
        return;
      }

      const response = await fetch(apiUrl("/api/pod-activation/my-activations"), {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, payload, "Failed to load activated models");
      setActivatedModelIds(new Set(payload.model_ids ?? []));
    } catch (error) {
      console.error("Error loading activated models:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadPendingRequests = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch(apiUrl("/api/pod-activation/my-requests?status=pending"), {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, payload, "Failed to load pending requests");
      setPendingRequestIds(new Set((payload.requests ?? []).map((r: any) => r.model_id)));
    } catch (error) {
      console.error("Error loading pending requests:", error);
    }
  };

  const handleRequestActivation = async (model: ModelCard) => {
    if (isViewer) {
      toast({
        title: "Viewer mode",
        description: "Viewer role is read-only. You can view models but cannot request activation.",
        variant: "destructive",
      });
      return;
    }
    if (isGuest) {
      toast({
        title: "Guest access is limited",
        description: "Guest role cannot request model activation.",
        variant: "destructive",
      });
      return;
    }

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        navigate("/auth");
        return;
      }

      const response = await fetch(apiUrl("/api/pod-activation/request"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model_id: model.id,
          model_name: model.name,
          domain: model.domain,
        }),
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) {
        if (response.status === 409) {
          toast({
            title: "Already Requested",
            description: "You already have a pending request for this pod",
            variant: "destructive",
          });
        } else {
          const apiError = buildApiRequestError(response, payload, "Failed to send request");
          toast({
            title: "Request Error",
            description: apiError.message,
            variant: "destructive",
          });
        }
        return;
      }

      toast({
        title: "Request Sent!",
        description: `Activation request for ${model.name} has been sent to your admin for approval`,
      });

      loadPendingRequests();
    } catch (error) {
      console.error("Error requesting activation:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to send request",
        variant: "destructive",
      });
    }
  };

  // Get filtered models based on domain and insurance segment
  const getFilteredModels = () => {
    if (selectedDomain === "all") {
      return allModels;
    }
    if (selectedDomain === "insurance") {
      if (selectedInsuranceSegment === "all") {
        return allInsuranceModels;
      }
      if (selectedInsuranceSegment === "broker") return brokerModelCards;
      if (selectedInsuranceSegment === "mga") return mgaModelCards;
      if (selectedInsuranceSegment === "carrier") return carrierModelCards;
      return allInsuranceModels;
    }
    return allModels.filter(model => model.domain === selectedDomain);
  };

  const filteredModels = getFilteredModels();

  const groupedModels = filteredModels.reduce((acc, model) => {
    const key = model.domain === "insurance" && model.segment 
      ? `insurance-${model.segment}` 
      : model.domain;
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(model);
    return acc;
  }, {} as Record<string, ModelCard[]>);

  const domainCounts = {
    insurance: allInsuranceModels.length,
    healthcare: otherDomainModels.filter(m => m.domain === "healthcare").length,
    banking: otherDomainModels.filter(m => m.domain === "banking").length,
    legal: otherDomainModels.filter(m => m.domain === "legal").length,
    travel: otherDomainModels.filter(m => m.domain === "travel").length,
  };

  const domainIcons: Record<string, any> = {
    insurance: Shield,
    healthcare: Heart,
    banking: Building2,
    legal: Scale,
    travel: Plane
  };

  const getGroupLabel = (key: string) => {
    if (key.startsWith("insurance-")) {
      const segment = key.replace("insurance-", "");
      return insuranceSegments[segment]?.label || segment;
    }
      return domainLabels[key] ?? key;
  };

  const getGroupIcon = (key: string) => {
    if (key.startsWith("insurance-")) {
      const segment = key.replace("insurance-", "");
      return insuranceSegments[segment]?.icon || Shield;
    }
    return domainIcons[key] || Shield;
  };

  const renderModelCard = (model: ModelCard, index: number) => {
    const actionBlockedByRole = role === "viewer" || role === "guest";

    const Icon = model.icon;
    const isActivated = activatedModelIds.has(model.id);
    const isPending = pendingRequestIds.has(model.id);

    return (
      <Card 
        key={model.id} 
        style={{ animationDelay: `${index * 50}ms` }}
        className={`group relative overflow-hidden flex flex-col h-full min-h-[280px] md:min-h-[340px] transition-all duration-500 hover:shadow-premium hover:-translate-y-1 md:hover:-translate-y-2 animate-scale-in border backdrop-blur-sm touch-manipulation ${
          isActivated 
            ? "ring-2 ring-primary/50 shadow-elevated bg-card/90 border-primary/30" 
            : isPending
            ? "ring-2 ring-amber-500/30 shadow-elevated bg-card/90 border-amber-500/20"
            : "hover:border-primary/50 bg-card/80 border-border/50"
        }`}
      >
        {/* Enhanced Background Gradient Effect */}
        <div className="absolute inset-0 bg-gradient-primary opacity-0 group-hover:opacity-5 transition-opacity duration-300 pointer-events-none" />
        
        {isActivated && (
          <div className="absolute top-2 md:top-3 right-2 md:right-3 z-10">
            <Badge className="bg-primary text-primary-foreground shadow-lg animate-in zoom-in duration-300 text-[10px] md:text-xs">
              <CheckCircle2 className="h-2.5 w-2.5 md:h-3 md:w-3 mr-1" />
              Active
            </Badge>
          </div>
        )}

        {isPending && !isActivated && (
          <div className="absolute top-2 md:top-3 right-2 md:right-3 z-10">
            <Badge className="bg-amber-500/90 text-white shadow-lg animate-in zoom-in duration-300 text-[10px] md:text-xs">
              <ClockIcon className="h-2.5 w-2.5 md:h-3 md:w-3 mr-1" />
              Pending
            </Badge>
          </div>
        )}
        
        {/* Enhanced Icon Header */}
        <div className="relative flex items-center justify-center pt-5 md:pt-8 pb-3 md:pb-5 bg-gradient-subtle">
          <div className="p-3 md:p-4 rounded-lg md:rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 group-hover:from-primary/20 group-hover:to-primary/10 group-hover:scale-110 transition-all duration-500 shadow-card">
            <Icon className="h-8 w-8 md:h-11 md:w-11 text-primary group-hover:animate-float" />
          </div>
        </div>

        {/* Content - Flexible */}
        <CardHeader className="flex-1 pb-2 px-4 md:px-6">
          <CardTitle className="text-sm md:text-base font-semibold line-clamp-2 text-center leading-snug mb-1.5 md:mb-2 tracking-tight">
            {model.name}
          </CardTitle>
          <div className="flex justify-center mb-1.5">
            <Badge variant="outline" className="text-[10px] md:text-xs">
              {model.version}
            </Badge>
          </div>
          <CardDescription className="text-xs md:text-sm line-clamp-3 text-center leading-relaxed font-normal">
            {model.description}
          </CardDescription>
        </CardHeader>

        {/* Category Badge - Fixed position */}
        <div className="px-4 md:px-5 pb-2 md:pb-3">
          <div className="flex justify-center">
            <Badge variant="secondary" className="text-[10px] md:text-xs font-medium">
              {model.category ?? model.capabilities[0]}
            </Badge>
          </div>
        </div>

        {/* Action Button - Enhanced */}
        <CardContent className="pt-0 pb-4 md:pb-6 px-4 md:px-6 mt-auto">
          <Button
            onClick={() => handleRequestActivation(model)}
            disabled={isActivated || isPending || loading || actionBlockedByRole}
            className="w-full font-semibold text-xs md:text-sm tracking-normal transition-all duration-500 h-10 md:h-11 group-hover:scale-105 touch-manipulation"
            size="default"
            variant={isActivated ? "outline" : isPending ? "secondary" : "default"}
          >
            {isActivated ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />
                Activated
              </>
            ) : isPending ? (
              <>
                <ClockIcon className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />
                Request Pending
              </>
            ) : (
              <>
                <SendHorizontal className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />
                {actionBlockedByRole ? "View Only" : "Request Activation"}
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="min-h-screen relative">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-40 left-1/3 w-64 md:w-96 h-64 md:h-96 bg-primary/10 rounded-full blur-3xl animate-glow-pulse" />
        <div className="absolute bottom-40 right-1/3 w-64 md:w-96 h-64 md:h-96 bg-accent/10 rounded-full blur-3xl animate-glow-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto py-4 md:py-12 px-2 sm:px-4 lg:px-8">
        {/* Hero Header */}
        <div className="relative mb-6 md:mb-12 rounded-xl md:rounded-2xl bg-gradient-hero p-4 md:p-8 border border-border/50 backdrop-blur-sm shadow-premium animate-fade-in">
          <div className="absolute inset-0 bg-gradient-subtle rounded-xl md:rounded-2xl opacity-50" />
          <div className="relative">
            <div className="flex items-center gap-3 md:gap-4 mb-2 md:mb-3">
              <div className="p-2 md:p-3 rounded-lg md:rounded-xl bg-primary/10 backdrop-blur-sm">
                <Sparkles className="h-6 w-6 md:h-8 md:w-8 text-primary animate-float" />
              </div>
              <h1 className="text-2xl md:text-5xl font-bold tracking-tight bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
                Model Marketplace
              </h1>
            </div>
            <p className="text-muted-foreground text-sm md:text-lg">
              Discover and activate domain-specific AI models for your business
            </p>
          </div>
        </div>

        {/* Domain Filter Tabs */}
        <div className="mb-4 md:mb-8 sticky top-0 z-20 bg-background/95 backdrop-blur-xl py-2 md:py-4 -mx-2 px-2 md:-mx-4 md:px-4 border-b border-border/50 shadow-sm animate-scale-in">
          <Tabs value={selectedDomain} onValueChange={(v) => { setSelectedDomain(v); setSelectedInsuranceSegment("all"); }} className="w-full">
            <TabsList className="inline-flex h-10 md:h-12 items-center justify-start rounded-lg md:rounded-xl bg-muted/50 backdrop-blur-sm p-1 w-full overflow-x-auto scrollbar-hide">
              <TabsTrigger 
                value="all" 
                className="rounded-md md:rounded-lg px-3 md:px-6 text-xs md:text-sm data-[state=active]:bg-card data-[state=active]:shadow-card transition-all whitespace-nowrap touch-manipulation"
              >
                <Sparkles className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />
                <span className="hidden sm:inline">All Models</span>
                <span className="sm:hidden">All</span>
                <Badge variant="secondary" className="ml-1.5 md:ml-2 bg-primary/10 text-primary text-[10px] md:text-xs">{allModels.length}</Badge>
              </TabsTrigger>
              {Object.entries(domainLabels).map(([domain, label]) => {
                const Icon = domainIcons[domain];
                const count = domainCounts[domain as keyof typeof domainCounts] ?? 0;
                return (
                  <TabsTrigger 
                    key={domain} 
                    value={domain}
                    className="rounded-md md:rounded-lg px-3 md:px-6 text-xs md:text-sm data-[state=active]:bg-card data-[state=active]:shadow-card transition-all whitespace-nowrap touch-manipulation"
                  >
                    <Icon className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />
                    <span className="hidden md:inline">{label}</span>
                    <span className="md:hidden">{domain.charAt(0).toUpperCase() + domain.slice(1, 4)}</span>
                    <Badge variant="secondary" className="ml-1.5 md:ml-2 text-[10px] md:text-xs">{count}</Badge>
                  </TabsTrigger>
                );
              })}
            </TabsList>
          </Tabs>

          {/* Insurance Sub-Segment Tabs */}
          {selectedDomain === "insurance" && (
            <div className="mt-3">
              <Tabs value={selectedInsuranceSegment} onValueChange={setSelectedInsuranceSegment} className="w-full">
                <TabsList className="inline-flex h-9 items-center justify-start rounded-lg bg-primary/5 backdrop-blur-sm p-1 overflow-x-auto scrollbar-hide">
                  <TabsTrigger 
                    value="all" 
                    className="rounded-md px-4 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all whitespace-nowrap"
                  >
                    All Insurance
                    <Badge variant="secondary" className="ml-2 text-[10px] bg-background/50">{allInsuranceModels.length}</Badge>
                  </TabsTrigger>
                  {Object.entries(insuranceSegments).map(([segment, { label, icon: SegmentIcon }]) => {
                    const count = segment === "broker" ? brokerModelCards.length 
                      : segment === "mga" ? mgaModelCards.length 
                      : carrierModelCards.length;
                    return (
                      <TabsTrigger 
                        key={segment} 
                        value={segment}
                        className="rounded-md px-4 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all whitespace-nowrap"
                      >
                        <SegmentIcon className="h-3.5 w-3.5 mr-1.5" />
                        {label}
                        <Badge variant="secondary" className="ml-2 text-[10px] bg-background/50">{count}</Badge>
                      </TabsTrigger>
                    );
                  })}
                </TabsList>
              </Tabs>
            </div>
          )}
        </div>

        <div className="space-y-6 md:space-y-12">
          {loading ? (
            <div className="grid gap-3 md:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => (
                <Skeleton key={i} className="h-[280px] md:h-[340px] w-full rounded-xl" />
              ))}
            </div>
          ) : Object.entries(groupedModels).map(([key, models]) => (
            <div key={key} className="animate-fade-in">
              <div className="flex items-center gap-2 md:gap-3 mb-3 md:mb-6 p-3 md:p-4 rounded-lg md:rounded-xl bg-gradient-hero border border-border/50 backdrop-blur-sm">
                {(() => {
                  const Icon = getGroupIcon(key);
                  return (
                    <div className="p-1.5 md:p-2 rounded-md md:rounded-lg bg-primary/10 flex-shrink-0">
                      <Icon className="h-5 w-5 md:h-6 md:w-6 text-primary" />
                    </div>
                  );
                })()}
                <div className="flex-1 min-w-0">
                  <h2 className="text-lg md:text-2xl font-bold capitalize text-foreground truncate">{getGroupLabel(key)}</h2>
                  {key.startsWith("insurance-") && (
                    <p className="text-xs text-muted-foreground hidden md:block">
                      {insuranceSegments[key.replace("insurance-", "")]?.description}
                    </p>
                  )}
                </div>
                <Badge variant="outline" className="ml-auto border-primary/30 text-primary text-[10px] md:text-xs whitespace-nowrap">{models.length} models</Badge>
              </div>
              <div className="grid gap-3 md:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 auto-rows-fr items-stretch">
                {models.map((model, index) => renderModelCard(model, index))}
              </div>
            </div>
          ))}
          
          {!loading && filteredModels.length === 0 && (
            <div className="text-center py-12 md:py-20">
              <div className="inline-flex items-center justify-center w-12 h-12 md:w-16 md:h-16 rounded-full bg-muted mb-3 md:mb-4">
                <Search className="h-6 w-6 md:h-8 md:w-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg md:text-xl font-semibold mb-2">No models found</h3>
              <p className="text-sm md:text-base text-muted-foreground">Try selecting a different domain</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
