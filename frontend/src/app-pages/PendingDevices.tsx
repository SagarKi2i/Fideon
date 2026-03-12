import { useEffect, useState } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { CheckCircle, XCircle, Clock, Server } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface PendingDevice {
  id: string;
  device_name: string;
  device_token: string;
  os_type: string | null;
  registered_at: string;
  metadata: any;
}

export default function PendingDevices() {
  const [devices, setDevices] = useState<PendingDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    fetchPendingDevices();
  }, []);

  async function fetchPendingDevices() {
    try {
      const { data, error } = await supabase
        .from('devices')
        .select('*')
        .eq('status', 'never_checked_in')
        .order('registered_at', { ascending: false });

      if (error) throw error;
      setDevices(data || []);
    } catch (error) {
      console.error('Error fetching pending devices:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch pending devices',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove(deviceId: string) {
    try {
      const { error: deviceError } = await supabase
        .from('devices')
        .update({ status: 'offline', is_active: true })
        .eq('id', deviceId);

      if (deviceError) throw deviceError;

      // Create default license
      const { error: licenseError } = await supabase
        .from('device_licenses')
        .insert([
          {
            device_id: deviceId,
            license_type: 'standard',
            status: 'active',
          },
        ]);

      if (licenseError) throw licenseError;

      toast({
        title: 'Success',
        description: 'Device approved successfully',
      });

      fetchPendingDevices();
    } catch (error) {
      console.error('Error approving device:', error);
      toast({
        title: 'Error',
        description: 'Failed to approve device',
        variant: 'destructive',
      });
    }
  }

  async function handleReject(deviceId: string) {
    try {
      const { error } = await supabase
        .from('devices')
        .update({ is_active: false })
        .eq('id', deviceId);

      if (error) throw error;

      toast({
        title: 'Success',
        description: 'Device rejected',
      });

      fetchPendingDevices();
    } catch (error) {
      console.error('Error rejecting device:', error);
      toast({
        title: 'Error',
        description: 'Failed to reject device',
        variant: 'destructive',
      });
    }
  }

  return (
    <div className="min-h-screen p-8 relative overflow-hidden">
      {/* Animated background */}
      <div className="fixed inset-0 bg-gradient-subtle opacity-50 -z-10" />
      <div className="fixed top-20 right-20 w-96 h-96 bg-primary/5 rounded-full blur-3xl animate-float -z-10" />

      <div className="mb-8 animate-fade-in">
        <h1 className="text-4xl font-bold bg-gradient-hero bg-clip-text text-transparent mb-2">
          Pending Device Approvals
        </h1>
        <p className="text-muted-foreground">
          Review and approve device registration requests
        </p>
      </div>

      <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
        <CardHeader>
          <CardTitle className="flex items-center">
            <Clock className="h-5 w-5 mr-2" />
            Devices Awaiting Approval
          </CardTitle>
          <CardDescription>
            {devices.length} device{devices.length !== 1 ? 's' : ''} pending approval
          </CardDescription>
        </CardHeader>
        <CardContent>
          {devices.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Server className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No pending device approvals</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Device Name</TableHead>
                  <TableHead>OS Type</TableHead>
                  <TableHead>Registered At</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {devices.map((device) => (
                  <TableRow key={device.id}>
                    <TableCell className="font-medium">{device.device_name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{device.os_type || 'Unknown'}</Badge>
                    </TableCell>
                    <TableCell>
                      {new Date(device.registered_at).toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        <Clock className="h-3 w-3 mr-1" />
                        Pending
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleApprove(device.id)}
                          className="bg-green-500 hover:bg-green-600"
                        >
                          <CheckCircle className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleReject(device.id)}
                        >
                          <XCircle className="h-4 w-4 mr-1" />
                          Reject
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
