import { useCallback, useEffect, useRef, useState } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Server, CheckCircle, XCircle, Clock, AlertTriangle, HardDrive, Activity, TrendingUp, QrCode, Link2 } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { ModelAllocationSection } from '@/components/admin/ModelAllocationSection';
import { PodActivationRequests } from '@/components/admin/PodActivationRequests';
import { useUserRole } from '@/hooks/useUserRole';
import { Badge } from '@/components/ui/badge';
import { REALTIME_DEVICE_EVENT } from '@/lib/realtimeEvents';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Link } from 'react-router-dom';
import { apiUrl } from '@/lib/apiBaseUrl';

interface DashboardStats {
  totalDevices: number;
  onlineDevices: number;
  offlineDevices: number;
  pendingApprovals: number;
  expiringSoon: number;
  syncFailures: number;
  totalModelsAssigned: number;
  totalUsageToday: number;
  deviceGrowthTrend: string | null;
  usageTrend: string | null;
  systemHealthText: string;
}

interface PairingSession {
  id: string;
  status: string;
  created_at: string;
  expires_at: string;
  consumed_at: string | null;
  linked_device_id: string | null;
  primary_device_label: string | null;
}

interface LinkedDevice {
  id: string;
  device_name: string;
  registered_at: string;
  status: string;
  os_type: string | null;
  app_version: string | null;
  metadata: any;
}

const STAT_CARDS_TEMPLATE: Record<string, {
  title: string;
  icon: any;
  description: string;
  color?: string;
  trend?: string;
  value?: number;
}> = {
  totalDevices: {
    title: 'Total Devices',
    icon: Server,
    description: 'Registered devices',
  },
  onlineDevices: {
    title: 'Online',
    icon: CheckCircle,
    description: 'Active right now',
    color: 'text-green-500',
  },
  offlineDevices: {
    title: 'Offline',
    icon: XCircle,
    description: 'Not connected',
    color: 'text-gray-500',
  },
  pendingApprovals: {
    title: 'Pending Approvals',
    icon: Clock,
    description: 'Pending pod requests',
    color: 'text-yellow-500',
  },
  expiringSoon: {
    title: 'License Expiring',
    icon: AlertTriangle,
    description: 'Within 30 days',
    color: 'text-orange-500',
  },
  syncFailures: {
    title: 'Sync Failures',
    icon: AlertTriangle,
    description: 'Last 24 hours',
    color: 'text-red-500',
  },
  totalModelsAssigned: {
    title: 'Models Assigned',
    icon: HardDrive,
    description: 'Total allocations',
  },
  totalUsageToday: {
    title: 'Usage Today',
    icon: Activity,
    description: 'Chat queries (24h)',
  },
};

const LOADING_SKELETON_IDS = [
  "stats-1", "stats-2", "stats-3", "stats-4",
  "stats-5", "stats-6", "stats-7", "stats-8",
];

function getUsageTrendText(usageToday: number, usageYesterday: number): string {
  if (usageYesterday > 0) {
    return `${Math.round(((usageToday - usageYesterday) / usageYesterday) * 100)}% vs yesterday`;
  }
  if (usageToday > 0) return "Active today";
  return "No usage yet";
}

function getSystemHealthText(syncFailures: number, onlineDevices: number): string {
  if (syncFailures > 0) return "Sync failures detected";
  if (onlineDevices > 0) return "Healthy and online";
  return "No online devices";
}

function toPercent(value: number, total: number): number {
  if (total <= 0) return 0;
  return (value / total) * 100;
}

export default function AdminDashboard() {
  const { isAdmin } = useUserRole();
  // Temporary product decision: keep QR pairing features implemented, but hide from admin/global_admin UI.
  const showQrPairingInsights = false;
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    totalDevices: 0,
    onlineDevices: 0,
    offlineDevices: 0,
    pendingApprovals: 0,
    expiringSoon: 0,
    syncFailures: 0,
    totalModelsAssigned: 0,
    totalUsageToday: 0,
    deviceGrowthTrend: null,
    usageTrend: null,
    systemHealthText: 'No active issues',
  });
  const [pairings, setPairings] = useState<PairingSession[]>([]);
  const [linkedDevices, setLinkedDevices] = useState<LinkedDevice[]>([]);
  const [pairingDbReady, setPairingDbReady] = useState(true);
  const refreshTimerRef = useRef<number | null>(null);

  const fetchDashboardStats = useCallback(async () => {
    try {
      const dayMs = 24 * 60 * 60 * 1000;
      const yesterdayIso = new Date(Date.now() - dayMs).toISOString();
      const weekAgoIso = new Date(Date.now() - (7 * dayMs)).toISOString();
      const thirtyDaysFromNowIso = new Date(Date.now() + (30 * dayMs)).toISOString();

      const [
        { count: totalDevicesCount, error: totalDevicesError },
        { count: onlineDevicesCount, error: onlineDevicesError },
        { count: offlineDevicesCount, error: offlineDevicesError },
        { count: expiringSoonCount, error: expiringSoonError },
        { count: syncFailuresCount, error: syncFailuresError },
        { count: assignedModelsCount, error: assignedModelsError },
        { count: pendingPodRequestsCount, error: pendingReqError },
        { count: usageTodayCount, error: usageTodayError },
        { count: usageYesterdayCount, error: usageYesterdayError },
        { count: devicesCreatedThisWeekCount, error: devicesWeekError },
        dashboardStatsResp,
      ] = await Promise.all([
        supabase.from('devices').select('*', { count: 'exact', head: true }),
        supabase.from('devices').select('*', { count: 'exact', head: true }).eq('status', 'online'),
        supabase.from('devices').select('*', { count: 'exact', head: true }).eq('status', 'offline'),
        supabase
          .from('device_licenses')
          .select('*', { count: 'exact', head: true })
          .lte('expires_at', thirtyDaysFromNowIso),
        supabase
          .from('device_sync_logs')
          .select('*', { count: 'exact', head: true })
          .eq('status', 'failed')
          .gte('created_at', yesterdayIso),
        supabase.from('activated_models').select('*', { count: 'exact', head: true }),
        supabase.from('pod_activation_requests').select('*', { count: 'exact', head: true }).eq('status', 'pending'),
        supabase.from('chat_messages').select('*', { count: 'exact', head: true }).gte('created_at', yesterdayIso),
        supabase
          .from('chat_messages')
          .select('*', { count: 'exact', head: true })
          .gte('created_at', new Date(Date.now() - (2 * dayMs)).toISOString())
          .lt('created_at', yesterdayIso),
        supabase.from('devices').select('*', { count: 'exact', head: true }).gte('registered_at', weekAgoIso),
        (async () => {
          const { data: { session } } = await supabase.auth.getSession();
          if (!session?.access_token) throw new Error('Missing auth session');
          const resp = await fetch(apiUrl('/api/admin/dashboard-stats'), {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${session.access_token}`,
            },
          });
          if (!resp.ok) {
            const msg = await resp.text();
            throw new Error(msg || 'Failed to fetch admin dashboard stats');
          }
          return resp.json() as Promise<{ total_devices?: number; total_models_assigned?: number }>;
        })(),
      ]);

      if (assignedModelsError) throw assignedModelsError;
      if (pendingReqError) throw pendingReqError;
      if (usageTodayError) throw usageTodayError;
      if (usageYesterdayError) throw usageYesterdayError;
      if (devicesWeekError) throw devicesWeekError;
      if (totalDevicesError) throw totalDevicesError;
      if (onlineDevicesError) throw onlineDevicesError;
      if (offlineDevicesError) throw offlineDevicesError;
      if (expiringSoonError) throw expiringSoonError;
      if (syncFailuresError) throw syncFailuresError;

      const usageToday = usageTodayCount ?? 0;
      const usageYesterday = usageYesterdayCount ?? 0;
      const onlineDevices = onlineDevicesCount ?? 0;
      const offlineDevices = offlineDevicesCount ?? 0;
      const usageTrend = getUsageTrendText(usageToday, usageYesterday);
      const syncFailures = syncFailuresCount ?? 0;
      const systemHealthText = getSystemHealthText(syncFailures, onlineDevices);

      setStats({
        totalDevices: Number(dashboardStatsResp?.total_devices ?? totalDevicesCount ?? 0),
        onlineDevices,
        offlineDevices,
        pendingApprovals: pendingPodRequestsCount ?? 0,
        expiringSoon: expiringSoonCount ?? 0,
        syncFailures,
        totalModelsAssigned: Number(dashboardStatsResp?.total_models_assigned ?? assignedModelsCount ?? 0),
        totalUsageToday: usageToday,
        deviceGrowthTrend: devicesCreatedThisWeekCount ? `+${devicesCreatedThisWeekCount} this week` : null,
        usageTrend,
        systemHealthText,
      });
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
    }
  }, []);

  const fetchPairingInsights = useCallback(async () => {
    try {
      const { data: pairingRows, error: pairingError } = await supabase
        .from('device_pairings')
        .select('id,status,created_at,expires_at,consumed_at,linked_device_id,primary_device_label')
        .order('created_at', { ascending: false })
        .limit(12);

      if (pairingError) {
        const missingTable = String(pairingError.message || '').toLowerCase().includes('device_pairings');
        if (missingTable) {
          setPairingDbReady(false);
          return;
        }
        throw pairingError;
      }

      setPairingDbReady(true);
      setPairings(pairingRows ?? []);

      const { data: allRecentDevices, error: devicesError } = await supabase
        .from('devices')
        .select('id,device_name,registered_at,status,os_type,app_version,metadata')
        .order('registered_at', { ascending: false })
        .limit(40);

      if (devicesError) throw devicesError;

      const linked = (allRecentDevices ?? []).filter((row: any) => row?.metadata?.linked_from_pairing === true);
      setLinkedDevices(linked.slice(0, 12));
    } catch (error) {
      console.error('Error fetching device pairing insights:', error);
    }
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      setIsLoading(true);
      if (showQrPairingInsights) {
        await Promise.all([fetchDashboardStats(), fetchPairingInsights()]);
      } else {
        await fetchDashboardStats();
      }
      setIsLoading(false);
    };
    void bootstrap();

    const handleDeviceRealtime = () => {
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
      refreshTimerRef.current = window.setTimeout(() => {
        refreshTimerRef.current = null;
        void fetchDashboardStats();
        if (showQrPairingInsights) {
          void fetchPairingInsights();
        }
      }, 500);
    };
    window.addEventListener(REALTIME_DEVICE_EVENT, handleDeviceRealtime);

    const pairingChannel = showQrPairingInsights
      ? supabase
          .channel('admin-device-pairings-live')
          .on('postgres_changes', { event: '*', schema: 'public', table: 'device_pairings' }, () => {
            fetchPairingInsights();
          })
          .subscribe()
      : null;

    const adminStatsChannel = supabase
      .channel('admin-dashboard-stats-live')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'devices' }, () => {
        void fetchDashboardStats();
        if (showQrPairingInsights) {
          void fetchPairingInsights();
        }
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'device_licenses' }, () => {
        void fetchDashboardStats();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'device_sync_logs' }, () => {
        void fetchDashboardStats();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'activated_models' }, () => {
        void fetchDashboardStats();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'pod_activation_requests' }, () => {
        void fetchDashboardStats();
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'chat_messages' }, () => {
        void fetchDashboardStats();
      })
      .subscribe();

    return () => {
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
      window.removeEventListener(REALTIME_DEVICE_EVENT, handleDeviceRealtime);
      if (pairingChannel) supabase.removeChannel(pairingChannel);
      supabase.removeChannel(adminStatsChannel);
    };
  }, [fetchDashboardStats, fetchPairingInsights, showQrPairingInsights]);

  const statCards = [
    { ...STAT_CARDS_TEMPLATE.totalDevices, value: stats.totalDevices, trend: stats.deviceGrowthTrend ?? undefined },
    { ...STAT_CARDS_TEMPLATE.onlineDevices, value: stats.onlineDevices },
    { ...STAT_CARDS_TEMPLATE.offlineDevices, value: stats.offlineDevices },
    { ...STAT_CARDS_TEMPLATE.pendingApprovals, value: stats.pendingApprovals },
    { ...STAT_CARDS_TEMPLATE.expiringSoon, value: stats.expiringSoon },
    { ...STAT_CARDS_TEMPLATE.syncFailures, value: stats.syncFailures },
    { ...STAT_CARDS_TEMPLATE.totalModelsAssigned, value: stats.totalModelsAssigned },
    { ...STAT_CARDS_TEMPLATE.totalUsageToday, value: stats.totalUsageToday, trend: stats.usageTrend ?? undefined },
  ];

  if (isLoading) {
    return (
      <div className="min-h-screen p-8 space-y-6">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-5 w-96" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {LOADING_SKELETON_IDS.map((id) => (
            <Skeleton key={id} className="h-36 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-72 w-full" />
          <Skeleton className="h-72 w-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8 relative overflow-hidden">
      {/* Animated background */}
      <div className="fixed inset-0 bg-gradient-subtle opacity-50 -z-10" />
      <div className="fixed top-20 right-20 w-96 h-96 bg-primary/5 rounded-full blur-3xl animate-float -z-10" />
      <div className="fixed bottom-20 left-20 w-96 h-96 bg-accent/5 rounded-full blur-3xl animate-float animation-delay-2000 -z-10" />

      {/* Header */}
      <div className="mb-8 animate-fade-in">
        <h1 className="text-4xl font-bold text-gray-900 dark:text-gray-100 mb-2">
          Admin Dashboard
        </h1>
        <p className="text-muted-foreground">
          Monitor and manage your private AI tenant infrastructure
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {statCards.map((stat, index) => (
          <Card
            key={stat.title}
            className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium hover:shadow-glow transition-all duration-300 animate-scale-in hover:-translate-y-1"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {stat.title}
                </CardTitle>
                <stat.icon className={`h-4 w-4 ${stat.color ?? 'text-primary'}`} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold mb-1">{stat.value}</div>
              <p className="text-xs text-muted-foreground">{stat.description}</p>
              {stat.trend && (
                <div className="flex items-center mt-2 text-xs text-green-500">
                  <TrendingUp className="h-3 w-3 mr-1" />
                  {stat.trend}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts and detailed views */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
          <CardHeader>
            <CardTitle>Device Status Distribution</CardTitle>
            <CardDescription>Current device connectivity</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Online</span>
                  <span className="text-sm text-muted-foreground">
                    {Math.round(toPercent(stats.onlineDevices, stats.totalDevices))}%
                  </span>
                </div>
                <Progress
                  value={toPercent(stats.onlineDevices, stats.totalDevices)}
                  className="h-2"
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Offline</span>
                  <span className="text-sm text-muted-foreground">
                    {Math.round(toPercent(stats.offlineDevices, stats.totalDevices))}%
                  </span>
                </div>
                <Progress
                  value={toPercent(stats.offlineDevices, stats.totalDevices)}
                  className="h-2"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
          <CardHeader>
            <CardTitle>Quick Actions Required</CardTitle>
            <CardDescription>Items needing attention</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {stats.pendingApprovals > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                  <div className="flex items-center">
                    <Clock className="h-5 w-5 text-yellow-500 mr-3" />
                    <span className="text-sm font-medium">Pending Device Approvals</span>
                  </div>
                  <span className="text-sm font-bold">{stats.pendingApprovals}</span>
                </div>
              )}
              {stats.expiringSoon > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-orange-500/10 border border-orange-500/20">
                  <div className="flex items-center">
                    <AlertTriangle className="h-5 w-5 text-orange-500 mr-3" />
                    <span className="text-sm font-medium">Licenses Expiring Soon</span>
                  </div>
                  <span className="text-sm font-bold">{stats.expiringSoon}</span>
                </div>
              )}
              {stats.syncFailures > 0 && (
                <div className="flex items-center justify-between p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="flex items-center">
                    <XCircle className="h-5 w-5 text-red-500 mr-3" />
                    <span className="text-sm font-medium">Recent Sync Failures</span>
                  </div>
                  <span className="text-sm font-bold">{stats.syncFailures}</span>
                </div>
              )}
              {stats.pendingApprovals === 0 && stats.expiringSoon === 0 && stats.syncFailures === 0 && (
                <div className="flex items-center justify-center p-8 text-muted-foreground">
                  <CheckCircle className="h-5 w-5 mr-2" />
                  <span>{stats.systemHealthText}</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Pod Activation Requests */}
      <div className="mt-6 animate-fade-in">
        <PodActivationRequests />
      </div>

      {/* Device Pairing Insights (hidden for admin/global_admin for now, feature kept in codebase) */}
      {showQrPairingInsights && (
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6 animate-fade-in">
          <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <QrCode className="h-5 w-5 text-primary" />
                Recent Pairing Sessions
              </CardTitle>
              <CardDescription>Live status for QR link sessions</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {!pairingDbReady && (
                <div className="text-sm text-muted-foreground">
                  `device_pairings` table not found yet. Apply latest Supabase migrations to enable this view.
                </div>
              )}
              {pairingDbReady && pairings.length === 0 && (
                <div className="text-sm text-muted-foreground">No pairing sessions yet.</div>
              )}
              {pairingDbReady && pairings.length > 0 && pairings.map((p) => (
                <div key={p.id} className="rounded-lg border border-border/60 p-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{p.primary_device_label ?? 'Primary session'}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(p.created_at).toLocaleString()} - expires {new Date(p.expires_at).toLocaleTimeString()}
                    </p>
                  </div>
                  <Badge variant={p.status === 'confirmed' ? 'default' : 'outline'}>{p.status}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Link2 className="h-5 w-5 text-primary" />
                Linked Devices (QR)
              </CardTitle>
              <CardDescription>Devices linked through pairing QR flow</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {linkedDevices.length === 0 ? (
                <div className="text-sm text-muted-foreground">No QR-linked devices found yet.</div>
              ) : (
                linkedDevices.map((d) => (
                  <div key={d.id} className="rounded-lg border border-border/60 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium truncate">{d.device_name}</p>
                      <Badge variant="outline">{d.status}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {d.os_type ?? 'Unknown OS'} | {d.app_version ?? 'Unknown app'} | {new Date(d.registered_at).toLocaleString()}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Model Allocation */}
      <div className="mt-6 animate-fade-in">
        <ModelAllocationSection />
      </div>
      {isAdmin && (
        <Card className="mt-6 border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
          <CardHeader>
            <CardTitle>User Management</CardTitle>
            <CardDescription>
              User creation requests and role controls are available on the dedicated Users page.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to="/users">Open Users Page</Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
