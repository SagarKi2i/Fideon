import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { ShieldPlus, Loader2 } from "lucide-react";
import type { Database } from "@/integrations/supabase/types";

type AppRole = Database["public"]["Enums"]["app_role"];

interface UserInfo {
  id: string;
  email: string;
  role: AppRole;
}

const roleOptions: AppRole[] = ["global_admin", "admin", "user", "viewer", "guest"];

export function GlobalAdminRoleManager() {
  const { toast } = useToast();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newUserName, setNewUserName] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserRole, setNewUserRole] = useState<AppRole>("user");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserConfirmPassword, setNewUserConfirmPassword] = useState("");

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsersFromSupabaseFallback = async () => {
    const { data: appUsers, error: appUsersError } = await supabase
      .from("app_users")
      .select("user_id,email")
      .order("email", { ascending: true });
    if (appUsersError) throw appUsersError;

    const { data: roleRows, error: roleRowsError } = await supabase
      .from("user_roles")
      .select("user_id,role");
    if (roleRowsError) throw roleRowsError;

    const roleMap = new Map((roleRows || []).map((r) => [r.user_id, r.role as AppRole]));
    const usersFromFallback: UserInfo[] = (appUsers || []).map((u) => ({
      id: u.user_id,
      email: u.email,
      role: roleMap.get(u.user_id) || "user",
    }));
    setUsers(usersFromFallback);
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/list-users`, {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
          const data = await response.json();
          setUsers((data.users || []).map((u: any) => ({ ...u, role: (u.role || "user") as AppRole })));
          return;
        }
      } catch (backendError) {
        console.warn("Primary /api/list-users failed, using fallback:", backendError);
      }

      await loadUsersFromSupabaseFallback();
    } catch (error) {
      console.error("Error loading users for global admin:", error);
      toast({
        title: "Error",
        description: "Failed to load users for role management",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const updateRole = async (userId: string, role: AppRole) => {
    setUpdatingUserId(userId);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      let updated = false;
      try {
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin-set-user-role`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ user_id: userId, role }),
        });
        if (response.ok) {
          updated = true;
        }
      } catch (backendError) {
        console.warn("Primary /api/admin-set-user-role failed, using fallback:", backendError);
      }

      if (!updated) {
        const { error } = await supabase
          .from("user_roles")
          .upsert({ user_id: userId, role }, { onConflict: "user_id" });
        if (error) throw error;
      }

      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role } : u)));
      toast({ title: "Role updated", description: "User role was updated successfully." });
    } catch (error: any) {
      console.error("Error updating role:", error);
      toast({
        title: "Update failed",
        description: error.message || "Could not update user role",
        variant: "destructive",
      });
    } finally {
      setUpdatingUserId(null);
    }
  };

  const createUser = async () => {
    if (!newUserName.trim() || !newUserEmail.trim() || !newUserPassword.trim()) {
      toast({
        title: "Missing details",
        description: "Name, email, and password are required.",
        variant: "destructive",
      });
      return;
    }
    if (newUserPassword.length < 8) {
      toast({
        title: "Weak password",
        description: "Password must be at least 8 characters.",
        variant: "destructive",
      });
      return;
    }
    if (newUserPassword !== newUserConfirmPassword) {
      toast({
        title: "Password mismatch",
        description: "Password and confirm password must match.",
        variant: "destructive",
      });
      return;
    }

    setCreating(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error("Session expired");
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/admin-create-user`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: newUserEmail.trim(),
          password: newUserPassword,
          role: newUserRole,
          full_name: newUserName.trim(),
        }),
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        throw new Error(errorPayload?.error || errorPayload?.detail || "Failed to create user");
      }

      toast({
        title: "User created",
        description: `Created ${newUserEmail} with role ${newUserRole}.`,
      });

      setNewUserName("");
      setNewUserEmail("");
      setNewUserRole("user");
      setNewUserPassword("");
      setNewUserConfirmPassword("");
      setShowCreateForm(false);
      await loadUsers();
    } catch (error: any) {
      console.error("Error creating user:", error);
      toast({
        title: "Create user failed",
        description: error.message || "Could not create new user.",
        variant: "destructive",
      });
    } finally {
      setCreating(false);
    }
  };

  return (
    <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldPlus className="h-5 w-5 text-primary" />
          Global Admin - Role Management
        </CardTitle>
        <CardDescription>Promote users, assign admin roles, and manage access levels.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-4">
          <Button
            onClick={() => setShowCreateForm((prev) => !prev)}
            variant={showCreateForm ? "secondary" : "default"}
          >
            {showCreateForm ? "Close Add User" : "Add New User"}
          </Button>
        </div>

        {showCreateForm && (
          <div className="mb-6 p-4 rounded-md border border-border/60 bg-muted/30">
            <p className="text-sm font-medium mb-3">Add New User</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                type="text"
                placeholder="Full name"
                value={newUserName}
                onChange={(e) => setNewUserName(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
              <input
                type="email"
                placeholder="Email"
                value={newUserEmail}
                onChange={(e) => setNewUserEmail(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
              <Select value={newUserRole} onValueChange={(value) => setNewUserRole(value as AppRole)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roleOptions.map((role) => (
                    <SelectItem key={role} value={role}>
                      {role}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <input
                type="password"
                placeholder="Password"
                value={newUserPassword}
                onChange={(e) => setNewUserPassword(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
              <input
                type="password"
                placeholder="Confirm password"
                value={newUserConfirmPassword}
                onChange={(e) => setNewUserConfirmPassword(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2"
              />
            </div>
            <div className="mt-3 flex gap-2">
              <Button onClick={createUser} disabled={creating}>
                {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Add User
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setShowCreateForm(false);
                  setNewUserName("");
                  setNewUserEmail("");
                  setNewUserRole("user");
                  setNewUserPassword("");
                  setNewUserConfirmPassword("");
                }}
                disabled={creating}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
          </div>
        ) : users.length === 0 ? (
          <p className="text-sm text-muted-foreground">No users available.</p>
        ) : (
          <div className="space-y-3">
            {users.map((u) => (
              <div key={u.id} className="flex items-center justify-between gap-3 p-3 rounded-md border border-border/60">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{u.email}</p>
                  <p className="text-xs text-muted-foreground">Current role: {u.role}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Select
                    value={u.role}
                    onValueChange={(value) => updateRole(u.id, value as AppRole)}
                    disabled={updatingUserId === u.id}
                  >
                    <SelectTrigger className="w-44">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {roleOptions.map((role) => (
                        <SelectItem key={role} value={role}>
                          {role}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {updatingUserId === u.id && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="mt-4">
          <Button variant="outline" onClick={loadUsers}>Refresh User List</Button>
        </div>
      </CardContent>
    </Card>
  );
}
