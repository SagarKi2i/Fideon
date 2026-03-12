import { useEffect, useState } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Server, CheckCircle, XCircle, Clock, AlertTriangle, HardDrive, Activity, TrendingUp } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { ModelAllocationSection } from '@/components/admin/ModelAllocationSection';
import { PodActivationRequests } from '@/components/admin/PodActivationRequests';
import { useUserRole } from '@/hooks/useUserRole';
import { GlobalAdminRoleManager } from '@/components/admin/GlobalAdminRoleManager';

interface DashboardStats {
  totalDevices: number;
  onlineDevices: number;
  offlineDevices: number;
  pendingApprovals: number;
  expiringSoon: number;
  syncFailures: number;
  totalModelsAssigned: number;
  totalUsageToday: number;
}

export default function AdminDashboard() {
  const { isGlobalAdmin } = useUserRole();
  const [stats, setStats] = useState<DashboardStats>({
    totalDevices: 0,
    onlineDevices: 0,
    offlineDevices: 0,
    pendingApprovals: 0,
    expiringSoon: 0,
    syncFailures: 0,
    totalModelsAssigned: 0,
    totalUsageToday: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  async function fetchDashboardStats() {
    try {
      const { data: devices } = await supabase.from('devices').select('*');
      const { data: licenses } = await supabase.from('device_licenses').select('*');
      const { data: deviceModels } = await supabase.from('device_models').select('*');
      const { data: syncLogs } = await supabase
        .from('device_sync_logs')
        .select('*')
        .eq('status', 'failed')
        .gte('created_at', new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString());

      const now = new Date();
      const thirtyDaysFromNow = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

      setStats({
        totalDevices: devices?.length || 0,
        onlineDevices: devices?.filter(d => d.status === 'online').length || 0,
        offlineDevices: devices?.filter(d => d.status === 'offline').length || 0,
        pendingApprovals: devices?.filter(d => d.status === 'never_checked_in').length || 0,
        expiringSoon: licenses?.filter(l => l.expires_at && new Date(l.expires_at) <= thirtyDaysFromNow).length || 0,
        syncFailures: syncLogs?.length || 0,
        totalModelsAssigned: deviceModels?.length || 0,
        totalUsageToday: 0,
      });
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  }

  const statCards = [
    {
      title: 'Total Devices',
      value: stats.totalDevices,
      icon: Server,
      description: 'Registered devices',
      trend: '+12%',
    },
    {
      title: 'Online',
      value: stats.onlineDevices,
      icon: CheckCircle,
      description: 'Active right now',
      color: 'text-green-500',
    },
    {
      title: 'Offline',
      value: stats.offlineDevices,
      icon: XCircle,
      description: 'Not connected',
      color: 'text-gray-500',
    },
    {
      title: 'Pending Approvals',
      value: stats.pendingApprovals,
      icon: Clock,
      description: 'Awaiting approval',
      color: 'text-yellow-500',
    },
    {
      title: 'License Expiring',
      value: stats.expiringSoon,
      icon: AlertTriangle,
      description: 'Within 30 days',
      color: 'text-orange-500',
    },
    {
      title: 'Sync Failures',
      value: stats.syncFailures,
      icon: AlertTriangle,
      description: 'Last 24 hours',
      color: 'text-red-500',
    },
    {
      title: 'Models Assigned',
      value: stats.totalModelsAssigned,
      icon: HardDrive,
      description: 'Total allocations',
    },
    {
      title: 'Usage Today',
      value: stats.totalUsageToday,
      icon: Activity,
      description: 'Model queries',
    },
  ];

  return (
    <div className="min-h-screen p-8 relative overflow-hidden">
      {/* Animated background */}
      <div className="fixed inset-0 bg-gradient-subtle opacity-50 -z-10" />
      <div className="fixed top-20 right-20 w-96 h-96 bg-primary/5 rounded-full blur-3xl animate-float -z-10" />
      <div className="fixed bottom-20 left-20 w-96 h-96 bg-accent/5 rounded-full blur-3xl animate-float animation-delay-2000 -z-10" />

      {/* Header */}
      <div className="mb-8 animate-fade-in">
        <h1 className="text-4xl font-bold bg-gradient-hero bg-clip-text text-transparent mb-2">
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
                <stat.icon className={`h-4 w-4 ${stat.color || 'text-primary'}`} />
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
                    {stats.totalDevices > 0
                      ? Math.round((stats.onlineDevices / stats.totalDevices) * 100)
                      : 0}
                    %
                  </span>
                </div>
                <Progress
                  value={
                    stats.totalDevices > 0
                      ? (stats.onlineDevices / stats.totalDevices) * 100
                      : 0
                  }
                  className="h-2"
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Offline</span>
                  <span className="text-sm text-muted-foreground">
                    {stats.totalDevices > 0
                      ? Math.round((stats.offlineDevices / stats.totalDevices) * 100)
                      : 0}
                    %
                  </span>
                </div>
                <Progress
                  value={
                    stats.totalDevices > 0
                      ? (stats.offlineDevices / stats.totalDevices) * 100
                      : 0
                  }
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
                  <span>All systems operational</span>
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

      {/* Model Allocation */}
      <div className="mt-6 animate-fade-in">
        <ModelAllocationSection />
      </div>

      {/* Global Admin extras */}
      {isGlobalAdmin && (
        <div className="mt-6 animate-fade-in">
          <GlobalAdminRoleManager />
        </div>
      )}
    </div>
  );
}
