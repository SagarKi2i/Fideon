import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { 
  Brain, FileSearch, Scale, ClipboardList, FileText, 
  MessageSquare, Activity, Zap, Server, TrendingUp,
  ChevronRight, Sparkles, AlertCircle
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface ActivatedPod {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
  activated_at: string | null;
}

interface PodMetrics {
  totalQueries: number;
  successRate: number | null;
  lastActivity: string;
  trend: string;
}

const getPodIcon = (modelId: string) => {
  const icons: Record<string, typeof Brain> = {
    'document-retrieval': FileSearch,
    'quote-generation': FileText,
    'policy-comparison': Scale,
    'claims-fnol': ClipboardList,
    'generic-prompt': MessageSquare,
  };
  return icons[modelId] || Brain;
};

const getPodColor = (modelId: string) => {
  const colors: Record<string, string> = {
    'document-retrieval': 'text-blue-500',
    'quote-generation': 'text-emerald-500',
    'policy-comparison': 'text-purple-500',
    'claims-fnol': 'text-amber-500',
    'generic-prompt': 'text-pink-500',
  };
  return colors[modelId] || 'text-primary';
};

const getPodGradient = (modelId: string) => {
  const gradients: Record<string, string> = {
    'document-retrieval': 'from-blue-500/10 to-blue-600/5',
    'quote-generation': 'from-emerald-500/10 to-emerald-600/5',
    'policy-comparison': 'from-purple-500/10 to-purple-600/5',
    'claims-fnol': 'from-amber-500/10 to-amber-600/5',
    'generic-prompt': 'from-pink-500/10 to-pink-600/5',
  };
  return gradients[modelId] || 'from-primary/10 to-primary/5';
};

const toRelativeTime = (iso: string | null | undefined) => {
  if (!iso) return "No activity";
  const diffMs = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diffMs) || diffMs < 0) return "Just now";
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days > 1 ? "s" : ""} ago`;
};

const getTimeGreeting = () => {
  const hour = new Date().getHours();
  if (hour < 12) return "Good Morning";
  if (hour < 17) return "Good Afternoon";
  return "Good Evening";
};

const getPodSummaryText = (podCount: number): string =>
  podCount > 0
    ? `You have ${podCount} active pod${podCount > 1 ? "s" : ""} running`
    : "Get started by activating AI pods from the marketplace";

const getSystemsStatusText = (successRate: number | null): string => {
  if (successRate === null) return "No run data yet";
  if (successRate >= 99) return "All systems operational";
  if (successRate >= 95) return "Stable performance";
  return "Performance degraded";
};

const getSuccessPerformanceText = (successRate: number | null): string => {
  if (successRate === null) return "No run data yet";
  if (successRate >= 99) return "Excellent performance";
  if (successRate >= 95) return "Good performance";
  return "Needs attention";
};

const getSignedPercentText = (value: number | null, suffix: string): string =>
  value === null ? suffix : `${getSignedPrefix(value)}${value.toFixed(1)}${suffix}`;

const getResponseImprovementText = (value: number | null): string =>
  value === null
    ? "No baseline yet"
    : `${getInvertedSignedPrefix(value)}${Math.abs(value).toFixed(1)}% vs last month`;

const getSignedPrefix = (value: number): string => {
  if (value >= 0) return "+";
  return "";
};

const getInvertedSignedPrefix = (value: number): string => {
  if (value >= 0) return "-";
  return "+";
};

const calculateQueryTrend = (currentMonthQueries: number, previousMonthQueries: number): number => {
  if (previousMonthQueries > 0) {
    return ((currentMonthQueries - previousMonthQueries) / previousMonthQueries) * 100;
  }
  if (currentMonthQueries > 0) return 100;
  return 0;
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [pods, setPods] = useState<ActivatedPod[]>([]);
  const [loading, setLoading] = useState(true);
  const [displayName, setDisplayName] = useState("User");
  const [totalQueries, setTotalQueries] = useState(0);
  const [avgSuccessRate, setAvgSuccessRate] = useState<number | null>(null);
  const [queryTrendPct, setQueryTrendPct] = useState<number | null>(null);
  const [avgResponseSeconds, setAvgResponseSeconds] = useState<number | null>(null);
  const [responseImprovementPct, setResponseImprovementPct] = useState<number | null>(null);
  const [podQueryCounts, setPodQueryCounts] = useState<Record<string, number>>({});
  const [podLastActivity, setPodLastActivity] = useState<Record<string, string>>({});
  const [recentActivity, setRecentActivity] = useState<
    { id: string; action: string; time: string; status: "success" | "error"; podName: string }[]
  >([]);

  // Fetches profile once on mount — not re-fetched on realtime events.
  const loadProfile = useCallback(async (signal?: AbortSignal) => {
    try {
      const { data: { session: authSession } } = await supabase.auth.getSession();
      const token = authSession?.access_token;
      const fallbackName = authSession?.user?.email?.split("@")[0] ?? "User";

      // Show email immediately; update with full_name when profile arrives.
      setDisplayName(fallbackName);

      if (!token) return;
      const res = await fetch(apiUrl("/api/settings/profile"), {
        headers: { Authorization: `Bearer ${token}` },
        signal,
      });
      if (res.ok) {
        const data = await res.json();
        const p = data?.profile;
        setDisplayName(p?.full_name ?? p?.email?.split("@")[0] ?? fallbackName);
      }
    } catch (error: any) {
      if (error?.name !== "AbortError") console.error("Error loading profile:", error);
    }
  }, []);

  // Fetches live data — called on mount and on every realtime event.
  // Does NOT fetch profile (profile data doesn't change on these events).
  const loadActivatedPods = useCallback(async (_userId: string, signal?: AbortSignal) => {
    try {
      const { data: { session: authSession } } = await supabase.auth.getSession();
      const token = authSession?.access_token;
      const headers = { Authorization: `Bearer ${token}` };

      const [modelsRes, convsRes, runsRes] = await Promise.all([
        fetch(apiUrl("/api/v1/activated-models"), { headers, signal }),
        fetch(apiUrl("/api/v1/chat-conversations"), { headers, signal }),
        fetch(apiUrl("/api/v1/workflow-runs?limit=100"), { headers, signal }),
      ]);

      const podsData: ActivatedPod[] = modelsRes.ok ? (await modelsRes.json()).activated_models ?? [] : [];
      setPods(podsData);

      const conversations: any[] = convsRes.ok ? (await convsRes.json()).conversations ?? [] : [];

      const queryCountByModel: Record<string, number> = {};
      const lastActivityByModel: Record<string, string> = {};
      let conversationQueryTotal = 0;
      const now = new Date();
      const currentMonthStart = new Date(now.getFullYear(), now.getMonth(), 1);
      const previousMonthStart = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      let currentMonthQueries = 0;
      let previousMonthQueries = 0;
      const activityFeed: { id: string; action: string; time: string; status: "success" | "error"; podName: string }[] = [];

      for (const conv of conversations ?? []) {
        const modelId = conv.model_id ?? "generic-prompt";
        const messages = Array.isArray((conv as any).chat_messages) ? (conv as any).chat_messages : [];
        const queryCount = messages.length;
        queryCountByModel[modelId] = (queryCountByModel[modelId] ?? 0) + queryCount;
        conversationQueryTotal += queryCount;

        for (const msg of messages) {
          const createdAt = new Date(msg.created_at);
          if (Number.isNaN(createdAt.getTime())) continue;
          if (createdAt >= currentMonthStart) {
            currentMonthQueries += 1;
          } else if (createdAt >= previousMonthStart && createdAt < currentMonthStart) {
            previousMonthQueries += 1;
          }
        }

        const activityTime = conv.updated_at || null;
        if (!lastActivityByModel[modelId] || new Date(activityTime || 0).getTime() > new Date(lastActivityByModel[modelId]).getTime()) {
          lastActivityByModel[modelId] = activityTime || "";
        }

        activityFeed.push({
          id: conv.id,
          action: conv.title ? `Conversation: ${conv.title}` : "Conversation activity",
          time: toRelativeTime(activityTime),
          status: "success",
          podName: podsData.find((p: any) => p.model_id === modelId)?.model_name ?? modelId,
        });
      }

      setPodQueryCounts(queryCountByModel);
      setPodLastActivity(lastActivityByModel);
      setTotalQueries(conversationQueryTotal);
      setQueryTrendPct(calculateQueryTrend(currentMonthQueries, previousMonthQueries));

      const runRows: any[] = runsRes.ok ? (await runsRes.json()).workflow_runs ?? [] : [];
      const completedRuns = runRows.filter((r: any) => r.status === "completed");
      const failedRuns = runRows.filter((r: any) => r.status === "failed");
      const consideredRuns = completedRuns.length + failedRuns.length;
      const successRate = consideredRuns > 0 ? (completedRuns.length / consideredRuns) * 100 : null;
      setAvgSuccessRate(successRate);

      const completedDurations = completedRuns
        .map((run: any) => {
          if (!run.started_at || !run.completed_at) return null;
          const durationSec = (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000;
          return Number.isFinite(durationSec) && durationSec >= 0 ? durationSec : null;
        })
        .filter((v): v is number => v !== null);

      if (completedDurations.length > 0) {
        const avg = completedDurations.reduce((sum: any, value: any) => sum + value, 0) / completedDurations.length;
        setAvgResponseSeconds(avg);
      } else {
        setAvgResponseSeconds(null);
      }

      const currentMonthDurations = completedRuns
        .filter((run: any) => run.started_at && new Date(run.started_at) >= currentMonthStart)
        .map((run: any) => {
          if (!run.started_at || !run.completed_at) return null;
          const durationSec = (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000;
          return Number.isFinite(durationSec) && durationSec >= 0 ? durationSec : null;
        })
        .filter((v): v is number => v !== null);

      const previousMonthDurations = completedRuns
        .filter((run: any) => run.started_at && new Date(run.started_at) >= previousMonthStart && new Date(run.started_at) < currentMonthStart)
        .map((run: any) => {
          if (!run.started_at || !run.completed_at) return null;
          const durationSec = (new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000;
          return Number.isFinite(durationSec) && durationSec >= 0 ? durationSec : null;
        })
        .filter((v): v is number => v !== null);

      if (currentMonthDurations.length > 0 && previousMonthDurations.length > 0) {
        const currentAvg = currentMonthDurations.reduce((sum: any, value: any) => sum + value, 0) / currentMonthDurations.length;
        const previousAvg = previousMonthDurations.reduce((sum: any, value: any) => sum + value, 0) / previousMonthDurations.length;
        if (previousAvg > 0) {
          setResponseImprovementPct(((previousAvg - currentAvg) / previousAvg) * 100);
        } else {
          setResponseImprovementPct(null);
        }
      } else {
        setResponseImprovementPct(null);
      }

      const runActivities = runRows.slice(0, 5).map((r: any) => ({
        id: `run-${r.id}`,
        action: `Workflow run ${r.status}`,
        time: toRelativeTime(r.started_at),
        status: r.status === "failed" ? ("error" as const) : ("success" as const),
        podName: "Workflow",
      }));

      setRecentActivity([...activityFeed, ...runActivities].sort((a, b) => {
        const aTime = a.time === "Just now" ? 0 : 1;
        const bTime = b.time === "Just now" ? 0 : 1;
        return aTime - bTime;
      }).slice(0, 5));
    } catch (error: any) {
      if (error?.name !== "AbortError") console.error("Error loading pods:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let channel: RealtimeChannel | null = null;
    const controller = new AbortController();

    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      const user = session?.user;
      if (!user || controller.signal.aborted) {
        setLoading(false);
        return;
      }

      // Profile fetched once — independent of realtime data refreshes.
      void loadProfile(controller.signal);
      await loadActivatedPods(user.id, controller.signal);

      if (controller.signal.aborted) return;

      channel = supabase
        .channel(`dashboard-live-${user.id}`)
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "activated_models", filter: `user_id=eq.${user.id}` },
          () => void loadActivatedPods(user.id)
        )
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "chat_conversations", filter: `user_id=eq.${user.id}` },
          () => void loadActivatedPods(user.id)
        )
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "chat_messages" },
          () => void loadActivatedPods(user.id)
        )
        .on(
          "postgres_changes",
          { event: "*", schema: "public", table: "workflow_runs", filter: `user_id=eq.${user.id}` },
          () => void loadActivatedPods(user.id)
        )
        .subscribe();
    };

    void init();

    return () => {
      controller.abort();
      if (channel) supabase.removeChannel(channel);
    };
  }, [loadActivatedPods, loadProfile]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <Brain className="h-12 w-12 text-primary animate-float" />
          <p className="text-muted-foreground">Loading your workspace...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen relative">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-1/4 w-64 md:w-96 h-64 md:h-96 bg-primary/10 rounded-full blur-3xl animate-glow-pulse" />
        <div className="absolute bottom-20 right-1/4 w-64 md:w-96 h-64 md:h-96 bg-accent/10 rounded-full blur-3xl animate-glow-pulse" style={{ animationDelay: '1.5s' }} />
      </div>

      <div className="relative z-10 space-y-6 md:space-y-8 animate-fade-in">
        {/* Hero Header */}
        <div className="relative rounded-xl md:rounded-2xl bg-gradient-hero p-4 md:p-8 border border-border/50 backdrop-blur-sm shadow-premium">
          <div className="absolute inset-0 bg-gradient-subtle rounded-xl md:rounded-2xl opacity-50" />
          <div className="relative flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-4xl font-bold tracking-tight bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
                {getTimeGreeting()}, {displayName}
              </h1>
              <p className="text-muted-foreground mt-1 md:mt-2 text-sm md:text-lg">
                {getPodSummaryText(pods.length)}
              </p>
            </div>
            {pods.length === 0 && (
              <Button 
                onClick={() => navigate('/marketplace')}
                className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-premium w-full sm:w-auto"
                size="lg"
              >
                <Sparkles className="mr-2 h-4 w-4" />
                Browse Marketplace
              </Button>
            )}
          </div>
        </div>

        {pods.length === 0 ? (
          /* Empty State */
          <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <div className="p-4 rounded-full bg-primary/10 mb-6">
                <Brain className="h-12 w-12 text-primary" />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-2">No Active Pods</h3>
              <p className="text-muted-foreground text-center max-w-md mb-6">
                Activate AI pods from the marketplace to start processing documents, 
                generating quotes, and automating your insurance workflows.
              </p>
              <Button onClick={() => navigate('/marketplace')} size="lg">
                Explore AI Pods
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Aggregate Stats */}
            <div className="grid gap-3 md:gap-6 grid-cols-2 lg:grid-cols-4">
              <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card hover:shadow-premium transition-all duration-300">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 p-3 md:p-6 md:pb-2">
                  <CardTitle className="text-xs md:text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                    Active Pods
                    <InfoTooltip content="Number of AI pods currently activated and running in your workspace." side="top" />
                  </CardTitle>
                  <Server className="h-4 w-4 text-primary" />
                </CardHeader>
                <CardContent className="p-3 md:p-6 pt-0">
                  <div className="text-2xl md:text-3xl font-bold text-foreground">{pods.length}</div>
                  <p className="text-xs text-primary mt-1">
                    {getSystemsStatusText(avgSuccessRate)}
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card hover:shadow-premium transition-all duration-300">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 p-3 md:p-6 md:pb-2">
                  <CardTitle className="text-xs md:text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                    Total Queries
                    <InfoTooltip content="Total number of AI queries processed across all your active pods." side="top" />
                  </CardTitle>
                  <Activity className="h-4 w-4 text-blue-500" />
                </CardHeader>
                <CardContent className="p-3 md:p-6 pt-0">
                  <div className="text-2xl md:text-3xl font-bold text-foreground">{totalQueries.toLocaleString()}</div>
                  <p className="text-xs text-primary mt-1">
                    {getSignedPercentText(queryTrendPct, "% vs last month")}
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card hover:shadow-premium transition-all duration-300">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 p-3 md:p-6 md:pb-2">
                  <CardTitle className="text-xs md:text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                    Success Rate
                    <InfoTooltip content="Percentage of queries that completed successfully without errors." side="top" />
                  </CardTitle>
                  <TrendingUp className="h-4 w-4 text-emerald-500" />
                </CardHeader>
                <CardContent className="p-3 md:p-6 pt-0">
                  <div className="text-2xl md:text-3xl font-bold text-foreground">
                    {avgSuccessRate === null ? "--" : `${avgSuccessRate.toFixed(1)}%`}
                  </div>
                  <p className="text-xs text-primary mt-1">
                    {getSuccessPerformanceText(avgSuccessRate)}
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card hover:shadow-premium transition-all duration-300">
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2 p-3 md:p-6 md:pb-2">
                  <CardTitle className="text-xs md:text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                    Avg Response
                    <InfoTooltip content="Average time for pods to process and return results." side="top" />
                  </CardTitle>
                  <Zap className="h-4 w-4 text-amber-500" />
                </CardHeader>
                <CardContent className="p-3 md:p-6 pt-0">
                  <div className="text-2xl md:text-3xl font-bold text-foreground">
                    {avgResponseSeconds === null ? "--" : `${avgResponseSeconds.toFixed(1)}s`}
                  </div>
                  <p className="text-xs text-primary mt-1">
                    {getResponseImprovementText(responseImprovementPct)}
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Active Pods Grid */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg md:text-xl font-semibold text-foreground">Your Active Pods</h2>
                <Button variant="ghost" size="sm" onClick={() => navigate('/marketplace')}>
                  Add More <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
              <div className="grid gap-4 md:gap-6 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
                {pods.map((pod: any, index: any) => {
                  const Icon = getPodIcon(pod.model_id);
                  const podQueries = podQueryCounts[pod.model_id] ?? 0;
                  const metrics: PodMetrics = {
                    totalQueries: podQueries,
                    successRate: podQueries > 0 ? avgSuccessRate : null,
                    lastActivity: toRelativeTime(podLastActivity[pod.model_id]),
                    trend: podQueries > 0 ? "Live data" : "No data",
                  };
                  const colorClass = getPodColor(pod.model_id);
                  const gradient = getPodGradient(pod.model_id);
                  
                  return (
                    <Card 
                      key={pod.id}
                      className="group relative overflow-hidden bg-card/80 backdrop-blur-sm border-border/50 hover:border-primary/30 hover:shadow-premium transition-all duration-300 cursor-pointer animate-scale-in"
                      style={{ animationDelay: `${index * 100}ms` }}
                      onClick={() => navigate(`/pod/${pod.model_id}`)}
                    >
                      <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
                      <CardHeader className="relative pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-3">
                            <div className={`p-2.5 rounded-xl bg-gradient-to-br ${gradient} group-hover:scale-110 transition-transform duration-300`}>
                              <Icon className={`h-5 w-5 ${colorClass}`} />
                            </div>
                            <div>
                              <CardTitle className="text-base font-semibold text-foreground group-hover:text-primary transition-colors">
                                {pod.model_name}
                              </CardTitle>
                              <CardDescription className="text-xs capitalize mt-0.5">
                                {pod.domain} • {metrics.lastActivity}
                              </CardDescription>
                            </div>
                          </div>
                          <Badge variant="secondary" className="text-[10px] bg-emerald-500/10 text-emerald-500 border-emerald-500/20">
                            Active
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="relative pt-0 space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-xs text-muted-foreground">Queries</p>
                            <p className="text-lg font-semibold text-foreground">{metrics.totalQueries.toLocaleString()}</p>
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">Success Rate</p>
                            <p className="text-lg font-semibold text-foreground">
                              {metrics.successRate === null ? "--" : `${metrics.successRate.toFixed(1)}%`}
                            </p>
                          </div>
                        </div>
                        <div>
                          <div className="flex items-center justify-between text-xs mb-1.5">
                            <span className="text-muted-foreground">Performance</span>
                            <span className="text-primary font-medium">{metrics.trend}</span>
                          </div>
                          <Progress value={metrics.successRate ?? 0} className="h-1.5" />
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>

            {/* Recent Activity */}
            {recentActivity.length > 0 && (
              <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg font-semibold flex items-center gap-2">
                    Recent Activity
                    <InfoTooltip content="Real-time log of actions performed by your AI pods including document retrievals, quote generations, and more." side="right" />
                  </CardTitle>
                  <CardDescription>Latest actions across your active pods</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {recentActivity.map((activity: any) => {
                      const Icon = Activity;
                      const colorClass = "text-primary";
                      
                      return (
                        <div 
                          key={activity.id}
                          className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
                        >
                          <div className={`p-2 rounded-lg bg-background`}>
                            <Icon className={`h-4 w-4 ${colorClass}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-foreground truncate">
                              {activity.action}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {activity.podName} • {activity.time}
                            </p>
                          </div>
                          {activity.status === 'error' ? (
                            <Badge variant="destructive" className="text-[10px]">
                              <AlertCircle className="h-3 w-3 mr-1" />
                              Error
                            </Badge>
                          ) : (
                            <Badge variant="secondary" className="text-[10px] bg-emerald-500/10 text-emerald-500">
                              Success
                            </Badge>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

          </>
        )}
      </div>
    </div>
  );
}
