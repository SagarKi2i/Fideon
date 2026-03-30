import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';
import { apiUrl } from '@/lib/apiBaseUrl';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';
import { Package, UserCheck, Trash2, Plus, Loader2 } from 'lucide-react';
import { brokerModels, mgaModels, carrierModels } from '@/lib/insuranceMocks';
import { buildApiRequestError, readJsonSafe } from '@/lib/httpErrors';

interface UserInfo {
  id: string;
  email: string;
  role: string;
}

interface AllocatedModel {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
  activated_at: string | null;
}

// All available models from marketplace
const allModels = [
  ...brokerModels.map(m => ({ id: m.id, name: m.name, domain: m.domain })),
  ...mgaModels.map(m => ({ id: m.id, name: m.name, domain: m.domain })),
  ...carrierModels.map(m => ({ id: m.id, name: m.name, domain: m.domain })),
];

export function ModelAllocationSection() {
  const getAllocationDateText = (activatedAt: string | null) => {
    if (!activatedAt) return '—';
    const date = new Date(activatedAt);
    if (!Number.isFinite(date.getTime())) return '—';
    return date.toLocaleDateString();
  };
  const { toast } = useToast();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [allocatedModels, setAllocatedModels] = useState<AllocatedModel[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>('');
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [loadingModels, setLoadingModels] = useState(false);
  const [allocating, setAllocating] = useState(false);

  useEffect(() => {
    fetchUsers();
  }, []);

  useEffect(() => {
    if (selectedUserId) {
      fetchAllocatedModels(selectedUserId);
    } else {
      setAllocatedModels([]);
    }
  }, [selectedUserId]);

  async function fetchUsersFromSupabaseFallback() {
    const { data: appUsers, error: appUsersError } = await supabase
      .from('app_users')
      .select('user_id,email')
      .order('email', { ascending: true });

    if (appUsersError) throw appUsersError;

    const { data: roleRows, error: rolesError } = await supabase
      .from('user_roles')
      .select('user_id,role');

    if (rolesError) throw rolesError;

    const roleMap = new Map((roleRows || []).map(r => [r.user_id, r.role]));
    const fallbackUsers: UserInfo[] = (appUsers || []).map(u => ({
      id: u.user_id,
      email: u.email,
      role: roleMap.get(u.user_id) || 'user',
    }));

    setUsers(fallbackUsers);
  }

  async function fetchUsers() {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      try {
        const response = await fetch(
          apiUrl('/api/list-users'),
          {
            headers: {
              Authorization: `Bearer ${session.access_token}`,
              'Content-Type': 'application/json',
            },
          }
        );

        if (response.ok) {
          const data = await response.json();
          setUsers(data.users || []);
          return;
        }
      } catch (backendError) {
        console.warn('Primary /api/list-users failed, using fallback:', backendError);
      }

      await fetchUsersFromSupabaseFallback();
    } catch (error) {
      console.error('Error fetching users:', error);
      toast({ title: 'Error', description: 'Failed to load users', variant: 'destructive' });
    } finally {
      setLoadingUsers(false);
    }
  }

  async function fetchAllocatedModels(userId: string) {
    setLoadingModels(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch(apiUrl(`/api/pod-activation/user/${userId}/activations`), {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, payload, "Failed to fetch allocations");
      setAllocatedModels(payload.allocations || []);
    } catch (error) {
      console.error('Error fetching allocated models:', error);
    } finally {
      setLoadingModels(false);
    }
  }

  async function handleAllocate() {
    if (!selectedUserId || !selectedModelId) return;

    const model = allModels.find(m => m.id === selectedModelId);
    if (!model) return;

    setAllocating(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch(apiUrl('/api/pod-activation/allocate'), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: selectedUserId,
          model_id: model.id,
          model_name: model.name,
          domain: model.domain,
        }),
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) {
        if (response.status === 409) {
          toast({ title: 'Already Allocated', description: 'This model is already allocated to this user', variant: 'destructive' });
        } else {
          throw buildApiRequestError(response, payload, "Failed to allocate model");
        }
        return;
      }

      toast({ title: 'Model Allocated', description: `${model.name} allocated successfully` });
      setSelectedModelId('');
      fetchAllocatedModels(selectedUserId);
      window.dispatchEvent(new CustomEvent("dashboard-stats-refresh"));
    } catch (error) {
      console.error('Error allocating model:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to allocate model',
        variant: 'destructive'
      });
    } finally {
      setAllocating(false);
    }
  }

  async function handleDeallocate(allocationId: string, modelName: string) {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const response = await fetch(apiUrl(`/api/pod-activation/allocations/${allocationId}`), {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
      });
      const payload = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, payload, "Failed to remove allocation");

      toast({ title: 'Model Removed', description: `${modelName} deallocated successfully` });
      fetchAllocatedModels(selectedUserId);
      window.dispatchEvent(new CustomEvent("dashboard-stats-refresh"));
    } catch (error) {
      console.error('Error deallocating model:', error);
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to remove model',
        variant: 'destructive'
      });
    }
  }

  const allocatedModelIds = new Set(allocatedModels.map(m => m.model_id));
  const availableModels = allModels.filter(m => !allocatedModelIds.has(m.id));
  const selectedUser = users.find(u => u.id === selectedUserId);

  return (
    <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="h-5 w-5 text-primary" />
          Model Allocation
        </CardTitle>
        <CardDescription>Allocate marketplace models to user accounts</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* User Selector */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <Label htmlFor="allocation-user-select" className="text-sm font-medium mb-2 block">Select User</Label>
            <Select value={selectedUserId} onValueChange={setSelectedUserId}>
              <SelectTrigger id="allocation-user-select">
                <SelectValue placeholder={loadingUsers ? "Loading users..." : "Choose a user"} />
              </SelectTrigger>
              <SelectContent>
                {users.map(user => (
                  <SelectItem key={user.id} value={user.id}>
                    <div className="flex items-center gap-2">
                      <span>{user.email}</span>
                      <Badge variant="outline" className="text-[10px]">{user.role}</Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedUserId && (
            <div className="flex-1">
              <Label htmlFor="allocation-model-select" className="text-sm font-medium mb-2 block">Allocate Model</Label>
              <div className="flex gap-2">
                <Select value={selectedModelId} onValueChange={setSelectedModelId}>
                  <SelectTrigger id="allocation-model-select" className="flex-1">
                    <SelectValue placeholder="Choose a model" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableModels.map(model => (
                      <SelectItem key={model.id} value={model.id}>
                        <div className="flex items-center gap-2">
                          <span>{model.name}</span>
                          <Badge variant="secondary" className="text-[10px]">{model.domain}</Badge>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  onClick={handleAllocate}
                  disabled={!selectedModelId || allocating}
                  size="icon"
                >
                  {allocating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Allocated Models Table */}
        {selectedUserId && (
          <div>
            <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
              <UserCheck className="h-4 w-4" />
              Models allocated to {selectedUser?.email}
              <Badge variant="secondary">{allocatedModels.length}</Badge>
            </h4>

            {loadingModels ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : allocatedModels.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground text-sm">
                No models allocated to this user yet
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Model</TableHead>
                    <TableHead>Domain</TableHead>
                    <TableHead>Allocated At</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allocatedModels.map(model => (
                    <TableRow key={model.id}>
                      <TableCell className="font-medium">{model.model_name}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{model.domain}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {getAllocationDateText(model.activated_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeallocate(model.id, model.model_name)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
