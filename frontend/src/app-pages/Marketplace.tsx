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
import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { brokerModels, mgaModels, carrierModels, InsuranceModel } from "@/lib/insuranceMocks";
import { useUserRole } from "@/hooks/useUserRole";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";
import { authHeadersJson } from "@/lib/authHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { modelIdsForAgentPacks } from "@/lib/agentPackModels";

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

const LOADING_SKELETON_IDS = ["mk-1", "mk-2", "mk-3", "mk-4", "mk-5", "mk-6", "mk-7", "mk-8"];

function getModelVersion(modelId: string): string {
  const versionMap: Record<string, string> = {
    "quote-generation": "v2.1",
    "policy-comparison": "v2.0",
    "document-retrieval": "v2.3",
    "claims-fnol": "v1.9",
    "acord_form_understanding": "v2.2",
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
  models.map((model: any) => ({
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

const LOCKED_MODEL_MESSAGE =
  "Upgrade your plan and agent pack to activate this model.";

const ACTIVE_MODEL_LIMIT_MESSAGE =
  "Please upgrade your plan to add more active models.";

export default function Marketplace() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { role, isViewer, isGuest, loading: roleLoading } = useUserRole();
  const [activatedModelIds, setActivatedModelIds] = useState<Set<string>>(new Set());
  const [pendingRequestIds, setPendingRequestIds] = useState<Set<string>>(new Set());
  const [tenantAgentPacks, setTenantAgentPacks] = useState<string[]>([]);
  const [tenantMaxActiveModels, setTenantMaxActiveModels] = useState<number | null>(null);
  const [tenantDistinctModelIds, setTenantDistinctModelIds] = useState<string[]>([]);
  const [marketplaceDataLoading, setMarketplaceDataLoading] = useState(true);
  const [selectedDomain, setSelectedDomain] = useState<string>("all");
  const [selectedInsuranceSegment, setSelectedInsuranceSegment] = useState<string>("all");

  const loading = marketplaceDataLoading || roleLoading;

  const allowedInsuranceModelIds = useMemo(
    () => modelIdsForAgentPacks(tenantAgentPacks),
    [tenantAgentPacks],
  );

  const tenantDistinctModelIdSet = useMemo(
    () => new Set(tenantDistinctModelIds),
    [tenantDistinctModelIds],
  );

  const isPackGatingActive = role === "global_admin" ? false : tenantAgentPacks.length > 0;

  const isBlockedByActiveModelPlanLimit = (model: ModelCard) => {
    if (tenantMaxActiveModels === null || tenantMaxActiveModels === undefined) return false;
    if (activatedModelIds.has(model.id)) return false;
    if (tenantDistinctModelIdSet.has(model.id)) return false;
    return tenantDistinctModelIdSet.size >= tenantMaxActiveModels;
  };

  const isMarketplaceModelUnlocked = (model: ModelCard) => {
    if (!isPackGatingActive) return true;
    if (activatedModelIds.has(model.id)) return true;
    if (model.domain === "insurance") return allowedInsuranceModelIds.has(model.id);
    return false;
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setMarketplaceDataLoading(true);
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          setActivatedModelIds(new Set());
          setPendingRequestIds(new Set());
          setTenantAgentPacks([]);
          setTenantMaxActiveModels(null);
          setTenantDistinctModelIds([]);
          return;
        }

        const headers = await authHeadersJson();
        const [actRes, profRes, pendRes] = await Promise.all([
          fetch(apiUrl("/api/pod-activation/my-activations"), { headers }),
          fetch(apiUrl("/api/settings/profile"), { headers }),
          fetch(apiUrl("/api/pod-activation/my-requests?status=pending"), { headers }),
        ]);

        const actPayload = await readJsonSafe(actRes);
        const profPayload = await readJsonSafe(profRes);
        const pendPayload = await readJsonSafe(pendRes);

        if (cancelled) return;

        if (actRes.ok) {
          setActivatedModelIds(new Set(actPayload.model_ids ?? []));
        } else {
          console.error("Failed to load activated models:", buildApiRequestError(actRes, actPayload, "Failed to load activated models"));
        }

        if (pendRes.ok) {
          setPendingRequestIds(new Set((pendPayload.requests ?? []).map((r: { model_id?: string }) => r.model_id).filter(Boolean)));
        } else {
          console.error("Failed to load pending requests:", buildApiRequestError(pendRes, pendPayload, "Failed to load pending requests"));
        }

        if (profRes.ok) {
          const packs = profPayload?.profile?.tenant_agent_packs;
          setTenantAgentPacks(Array.isArray(packs) ? packs : []);
          const maxM = profPayload?.profile?.tenant_max_active_models;
          setTenantMaxActiveModels(typeof maxM === "number" && Number.isFinite(maxM) ? maxM : null);
          const distinct = profPayload?.profile?.tenant_distinct_activated_model_ids;
          setTenantDistinctModelIds(Array.isArray(distinct) ? distinct.filter((x): x is string => typeof x === "string") : []);
        } else {
          setTenantAgentPacks([]);
          setTenantMaxActiveModels(null);
          setTenantDistinctModelIds([]);
        }
      } catch (error) {
        console.error("Error loading marketplace context:", error);
        if (!cancelled) {
          setTenantAgentPacks([]);
          setTenantMaxActiveModels(null);
          setTenantDistinctModelIds([]);
        }
      } finally {
        if (!cancelled) setMarketplaceDataLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshPendingRequests = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const headers = await authHeadersJson();
      const pendRes = await fetch(apiUrl("/api/pod-activation/my-requests?status=pending"), { headers });
      const pendPayload = await readJsonSafe(pendRes);
      if (!pendRes.ok) {
        console.error(
          "Failed to refresh pending requests:",
          buildApiRequestError(pendRes, pendPayload, "Failed to load pending requests"),
        );
        return;
      }
      setPendingRequestIds(
        new Set(
          (pendPayload.requests ?? [])
            .map((r: { model_id?: string }) => r.model_id)
            .filter(Boolean),
        ),
      );
    } catch (err) {
      console.error("Error refreshing pending requests:", err);
    }
  };

  const handleRequestActivation = async (model: ModelCard) => {
    if (!isMarketplaceModelUnlocked(model)) {
      toast({
        title: "Not included in your agent packs",
        description: LOCKED_MODEL_MESSAGE,
        variant: "destructive",
      });
      return;
    }
    if (isBlockedByActiveModelPlanLimit(model)) {
      toast({
        title: "Active model limit reached",
        description: ACTIVE_MODEL_LIMIT_MESSAGE,
        variant: "destructive",
      });
      return;
    }
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
          ...(await authHeadersJson()),
        },
        body: JSON.stringify({
          model_id: model.id,
          model_name: model.name,
          domain: model.domain,
        }),
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) {
        if (response.status === 401) {
          navigate("/auth");
          return;
        }
        if (response.status === 403) {
          const detail = payload?.detail;
          const msg =
            typeof detail === "string" && detail.trim()
              ? detail.trim()
              : ACTIVE_MODEL_LIMIT_MESSAGE;
          toast({
            title: "Active model limit reached",
            description: msg,
            variant: "destructive",
          });
          return;
        }
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

      await refreshPendingRequests();
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
    return allModels.filter((model: any) => model.domain === selectedDomain);
  };

  const filteredModels = getFilteredModels();

  const groupedModels = filteredModels.reduce((acc: any, model: any) => {
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
    healthcare: otherDomainModels.filter((m: any) => m.domain === "healthcare").length,
    banking: otherDomainModels.filter((m: any) => m.domain === "banking").length,
    legal: otherDomainModels.filter((m: any) => m.domain === "legal").length,
    travel: otherDomainModels.filter((m: any) => m.domain === "travel").length,
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
      return insuranceSegments[segment]?.label ?? segment;
    }
      return domainLabels[key] ?? key;
  };

  const getGroupIcon = (key: string) => {
    if (key.startsWith("insurance-")) {
      const segment = key.replace("insurance-", "");
      return insuranceSegments[segment]?.icon ?? Shield;
    }
    return domainIcons[key] ?? Shield;
  };

  const getModelCardClassName = (isActivated: boolean, isPending: boolean, isLocked: boolean): string => {
    if (isLocked) return "border-border/60 bg-card/80 border-border/50";
    if (isActivated) return "ring-2 ring-primary/50 shadow-elevated bg-card/90 border-primary/30";
    if (isPending) return "ring-2 ring-amber-500/30 shadow-elevated bg-card/90 border-amber-500/20";
    return "hover:border-primary/50 bg-card/80 border-border/50";
  };

  const getActivationButtonVariant = (
    isActivated: boolean,
    isPending: boolean,
  ): "outline" | "secondary" | "default" => {
    if (isActivated) return "outline";
    if (isPending) return "secondary";
    return "default";
  };

  const getActionButtonContent = (isActivated: boolean, isPending: boolean, actionBlockedByRole: boolean) => {
    if (isActivated) {
      return {
        icon: <CheckCircle2 className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />,
        label: "Activated",
      };
    }
    if (isPending) {
      return {
        icon: <ClockIcon className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />,
        label: "Request Pending",
      };
    }
    return {
      icon: <SendHorizontal className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />,
      label: actionBlockedByRole ? "View Only" : "Request Activation",
    };
  };

  const renderModelCard = (model: ModelCard, index: number) => {
    const actionBlockedByRole = role === "viewer" || role === "guest";

    const Icon = model.icon;
    const isActivated = activatedModelIds.has(model.id);
    const isPending = pendingRequestIds.has(model.id);
    const unlocked = isMarketplaceModelUnlocked(model);
    const isLocked = !unlocked;
    const isPlanLimitBlocked = isBlockedByActiveModelPlanLimit(model);
    const actionButtonContent = getActionButtonContent(isActivated, isPending, actionBlockedByRole);
    const showPlanLimitHint = !isLocked && isPlanLimitBlocked && !isActivated && !isPending;
    const buttonLabel =
      showPlanLimitHint && !actionBlockedByRole ? "Plan limit reached" : actionButtonContent.label;

    return (
      <Card
        key={model.id}
        style={{ animationDelay: `${index * 50}ms` }}
        className={cn(
          "group relative overflow-hidden flex flex-col h-full min-h-[280px] md:min-h-[340px] transition-all duration-500 border backdrop-blur-sm touch-manipulation animate-scale-in",
          !isLocked && "hover:shadow-premium hover:-translate-y-1 md:hover:-translate-y-2",
          getModelCardClassName(isActivated, isPending, isLocked),
        )}
      >
        {/* Enhanced Background Gradient Effect */}
        <div className="absolute inset-0 bg-gradient-primary opacity-0 group-hover:opacity-5 transition-opacity duration-300 pointer-events-none" />

        <div
          className={cn(
            "relative flex flex-col flex-1 min-h-0",
            isLocked && "blur-[3px] opacity-60 pointer-events-none select-none",
          )}
        >
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

          <div className="relative flex items-center justify-center pt-5 md:pt-8 pb-3 md:pb-5 bg-gradient-subtle">
            <div className="p-3 md:p-4 rounded-lg md:rounded-xl bg-gradient-to-br from-primary/15 to-primary/5 group-hover:from-primary/20 group-hover:to-primary/10 group-hover:scale-110 transition-all duration-500 shadow-card">
              <Icon className="h-8 w-8 md:h-11 md:w-11 text-primary group-hover:animate-float" />
            </div>
          </div>

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

          <div className="px-4 md:px-5 pb-2 md:pb-3">
            <div className="flex justify-center">
              <Badge variant="secondary" className="text-[10px] md:text-xs font-medium">
                {model.category ?? model.capabilities[0]}
              </Badge>
            </div>
          </div>

          <CardContent className="pt-0 pb-4 md:pb-6 px-4 md:px-6 mt-auto">
            {showPlanLimitHint && (
              <p className="text-[11px] md:text-xs text-center text-amber-700 dark:text-amber-500 font-medium leading-snug mb-2">
                {ACTIVE_MODEL_LIMIT_MESSAGE}
              </p>
            )}
            <Button
              onClick={() => handleRequestActivation(model)}
              disabled={
                isLocked || isPlanLimitBlocked || isActivated || isPending || loading || actionBlockedByRole
              }
              className="w-full font-semibold text-xs md:text-sm tracking-normal transition-all duration-500 h-10 md:h-11 group-hover:scale-105 touch-manipulation"
              size="default"
              variant={getActivationButtonVariant(isActivated, isPending)}
            >
              {actionButtonContent.icon}
              {buttonLabel}
            </Button>
          </CardContent>
        </div>

        {isLocked && (
          <div className="absolute inset-0 z-20 flex items-center justify-center p-4 bg-background/35 backdrop-blur-[2px]">
            <p className="text-center text-xs md:text-sm font-medium text-foreground leading-snug max-w-[16rem] md:max-w-xs">
              {LOCKED_MODEL_MESSAGE}
            </p>
          </div>
        )}
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
            {tenantMaxActiveModels !== null && (
              <p className="mt-3 text-xs md:text-sm font-medium text-amber-700 dark:text-amber-500">
                Active AI models for your organization: {tenantDistinctModelIds.length} of{" "}
                {tenantMaxActiveModels} included on your plan.
              </p>
            )}
          </div>
        </div>

        {/* Domain Filter Tabs */}
        <div className="mb-4 md:mb-8 sticky top-0 z-20 bg-background/95 backdrop-blur-xl py-2 md:py-4 -mx-2 px-2 md:-mx-4 md:px-4 border-b border-border/50 shadow-sm animate-scale-in">
          <Tabs value={selectedDomain} onValueChange={(v) => { setSelectedDomain(v); setSelectedInsuranceSegment("all"); }} className="w-full">
            <div className="w-full overflow-x-auto scrollbar-hide">
            <TabsList className="inline-flex h-10 md:h-12 w-max min-w-full flex-nowrap items-center justify-start rounded-lg md:rounded-xl bg-muted/50 backdrop-blur-sm p-1 gap-1">
              <TabsTrigger
                value="all"
                className="shrink-0 rounded-md md:rounded-lg px-3 md:px-4 text-xs md:text-sm data-[state=active]:bg-card data-[state=active]:shadow-card transition-all whitespace-nowrap touch-manipulation"
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
                    className="shrink-0 rounded-md md:rounded-lg px-3 md:px-4 text-xs md:text-sm data-[state=active]:bg-card data-[state=active]:shadow-card transition-all whitespace-nowrap touch-manipulation"
                  >
                    <Icon className="h-3.5 w-3.5 md:h-4 md:w-4 mr-1.5 md:mr-2" />
                    <span className="hidden md:inline">{label}</span>
                    <span className="md:hidden">{domain.charAt(0).toUpperCase() + domain.slice(1, 4)}</span>
                    <Badge variant="secondary" className="ml-1.5 md:ml-2 text-[10px] md:text-xs">{count}</Badge>
                  </TabsTrigger>
                );
              })}
            </TabsList>
            </div>
          </Tabs>

          {/* Insurance Sub-Segment Tabs */}
          {selectedDomain === "insurance" && (
            <div className="mt-3">
              <Tabs value={selectedInsuranceSegment} onValueChange={setSelectedInsuranceSegment} className="w-full">
                <div className="w-full overflow-x-auto scrollbar-hide">
                <TabsList className="inline-flex h-9 w-max min-w-full flex-nowrap items-center justify-start rounded-lg bg-primary/5 backdrop-blur-sm p-1 gap-1">
                  <TabsTrigger
                    value="all"
                    className="shrink-0 rounded-md px-4 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all whitespace-nowrap"
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
                        className="shrink-0 rounded-md px-4 text-xs data-[state=active]:bg-primary data-[state=active]:text-primary-foreground transition-all whitespace-nowrap"
                      >
                        <SegmentIcon className="h-3.5 w-3.5 mr-1.5" />
                        {label}
                        <Badge variant="secondary" className="ml-2 text-[10px] bg-background/50">{count}</Badge>
                      </TabsTrigger>
                    );
                  })}
                </TabsList>
                </div>
              </Tabs>
            </div>
          )}
        </div>

        <div className="space-y-6 md:space-y-12">
          {loading ? (
            <div className="grid gap-3 md:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {LOADING_SKELETON_IDS.map((id: any) => (
                <Skeleton key={id} className="h-[280px] md:h-[340px] w-full rounded-xl" />
              ))}
            </div>
          ) : Object.entries(groupedModels).map(([key, models]: [string, any]) => (
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
                {models.map((model: any, index: any) => renderModelCard(model, index))}
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