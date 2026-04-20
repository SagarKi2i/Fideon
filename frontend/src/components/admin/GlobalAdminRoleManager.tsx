import { useCallback, useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { PasswordInput } from "@/components/ui/password-input";
import { useToast } from "@/hooks/use-toast";
import { ShieldPlus, Loader2, Clock } from "lucide-react";
import type { Database } from "@/integrations/supabase/types";
import { buildApiRequestError, readJsonSafe } from "@/lib/httpErrors";

type AppRole = Database["public"]["Enums"]["app_role"];

interface UserInfo {
  id: string;
  email: string;
  role: AppRole;
  tenant_name?: string;
}

interface Props {
  /**
   * The role of the currently logged-in user.
   * Controls which roles are available in the "Add User" form.
   */
  readonly currentUserRole: "global_admin" | "admin" | "user";
}

/**
 * Returns the role options available to the creator, along with a flag
 * indicating whether that role requires approval.
 *
 * Rules:
 *  global_admin → all roles, all instant
 *  admin        → user/viewer/guest instant; admin requires global_admin approval
 *  user         → only 'user', requires admin/global_admin approval
 */
function getRoleOptions(creatorRole: Props["currentUserRole"]): Array<{ role: AppRole; pending: boolean }> {
  if (creatorRole === "global_admin") {
    return [
      { role: "global_admin", pending: false },
      { role: "admin",        pending: false },
      { role: "user",         pending: false },
      { role: "viewer",       pending: false },
      { role: "guest",        pending: false },
    ];
  }
  if (creatorRole === "admin") {
    return [
      { role: "user",   pending: false },
      { role: "viewer", pending: false },
      { role: "guest",  pending: false },
      { role: "admin",  pending: true },   // needs global_admin approval
    ];
  }
  // user
  return [
    { role: "user", pending: true },        // needs admin/global_admin approval
  ];
}

function getCardCopy(currentUserRole: Props["currentUserRole"]): { title: string; description: string } {
  if (currentUserRole === "global_admin") {
    return {
      title: "Global Admin – Role Management",
      description: "Create users of any role, promote/demote existing users.",
    };
  }
  if (currentUserRole === "admin") {
    return {
      title: "Admin – User Management",
      description: "Create users, viewers, or guests instantly. Admin creation requires global admin approval.",
    };
  }
  return {
    title: "Invite a New User",
    description: "Request the creation of a new user account (requires admin or global admin approval).",
  };
}

function getCreateUserValidationError(
  email: string,
  password: string,
  confirmPassword: string,
  needsPassword: boolean
): { title: string; description: string } | null {
  if (!email.trim()) {
    return { title: "Missing email", description: "Email is required." };
  }
  if (!needsPassword) return null;
  if (!password.trim()) {
    return { title: "Missing password", description: "Password is required." };
  }
  if (password.length < 8) {
    return { title: "Weak password", description: "Password must be at least 8 characters." };
  }
  if (password !== confirmPassword) {
    return { title: "Password mismatch", description: "Passwords do not match." };
  }
  return null;
}

export function GlobalAdminRoleManager({ currentUserRole }: Props) {
  const { toast } = useToast();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newUserName, setNewUserName] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserConfirmPassword, setNewUserConfirmPassword] = useState("");

  const roleOptions = getRoleOptions(currentUserRole);
  const [newUserRole, setNewUserRole] = useState<AppRole>(roleOptions[0].role);

  // Reset selected role when creator role changes
  useEffect(() => {
    setNewUserRole(getRoleOptions(currentUserRole)[0].role);
  }, [currentUserRole]);

  const selectedRoleOption = roleOptions.find((o: any) => o.role === newUserRole) ?? roleOptions[0];

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch(apiUrl("/api/list-users"), {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });
      const data = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, data, "Failed to load users");
      setUsers((data.users || []).map((u: any) => ({ ...u, role: (u.role || "user") as AppRole })));
    } catch (error) {
      console.error("Error loading users:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to load users",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const updateRole = async (userId: string, role: AppRole) => {
    // Only global_admin can change existing roles
    if (currentUserRole !== "global_admin") return;
    setUpdatingUserId(userId);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;

      const response = await fetch(apiUrl("/api/admin-set-user-role"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_id: userId, role }),
      });
      if (!response.ok) {
        const payload = await readJsonSafe(response);
        throw buildApiRequestError(response, payload, "Could not update role");
      }

      setUsers((prev) => prev.map((u: any) => (u.id === userId ? { ...u, role } : u)));
      toast({ title: "Role updated", description: "User role was updated successfully." });
    } catch (error: any) {
      toast({ title: "Update failed", description: error.message || "Could not update role", variant: "destructive" });
    } finally {
      setUpdatingUserId(null);
    }
  };

  const createUser = async () => {
    // Password required only for instant creation (global_admin and admin creating non-admin roles)
    const needsPassword = !selectedRoleOption.pending;
    const validationError = getCreateUserValidationError(
      newUserEmail,
      newUserPassword,
      newUserConfirmPassword,
      needsPassword
    );
    if (validationError) {
      toast({ ...validationError, variant: "destructive" });
      return;
    }

    setCreating(true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) throw new Error("Session expired");

      const body: Record<string, string> = {
        email: newUserEmail.trim(),
        role: newUserRole,
        full_name: newUserName.trim(),
      };
      if (needsPassword) {
        body.password = newUserPassword;
      }

      const response = await fetch(apiUrl("/api/admin-create-user"), {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const result = await readJsonSafe(response);
      if (!response.ok) throw buildApiRequestError(response, result, "Failed to create user");

      if (result.pending) {
        toast({
          title: "Request submitted",
          description: result.message || "Your request has been sent for approval.",
        });
      } else {
        const inheritedModelsCount = Number(result.inherited_models_count ?? 0);
        toast({
          title: "User created",
          description: `Created ${newUserEmail} with role ${newUserRole}. Inherited ${inheritedModelsCount} tenant model${inheritedModelsCount === 1 ? "" : "s"}.`,
        });
        await loadUsers();
      }

      setNewUserName("");
      setNewUserEmail("");
      setNewUserRole(roleOptions[0].role);
      setNewUserPassword("");
      setNewUserConfirmPassword("");
      setShowCreateForm(false);
    } catch (error: any) {
      toast({ title: "Create user failed", description: error.message || "Could not create user.", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  const canSeeUserList = currentUserRole === "global_admin" || currentUserRole === "admin";
  const canChangeExistingRoles = currentUserRole === "global_admin";

  const { title: cardTitle, description: cardDescription } = getCardCopy(currentUserRole);

  return (
    <Card className="border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 shadow-premium">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldPlus className="h-5 w-5 text-primary" />
          {cardTitle}
        </CardTitle>
        <CardDescription>{cardDescription}</CardDescription>
      </CardHeader>
      <CardContent>
        {/* ── Add User Toggle ──────────────────────────────────────────────── */}
        <div className="mb-4">
          <Button
            onClick={() => setShowCreateForm((prev) => !prev)}
            variant={showCreateForm ? "secondary" : "default"}
          >
            {showCreateForm ? "Close Form" : "Add New User"}
          </Button>
        </div>

        {/* ── Create User Form ─────────────────────────────────────────────── */}
        {showCreateForm && (
          <div className="mb-6 p-4 rounded-md border border-border/60 bg-muted/30 space-y-3">
            <p className="text-sm font-medium">
              {selectedRoleOption.pending ? (
                <span className="flex items-center gap-1 text-amber-600">
                  <Clock className="h-4 w-4" />
                  This will be submitted for approval
                </span>
              ) : (
                "Add New User"
              )}
            </p>

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

              {/* Role selector */}
              <Select
                value={newUserRole}
                onValueChange={(value) => setNewUserRole(value as AppRole)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {roleOptions.map(({ role, pending }) => (
                    <SelectItem key={role} value={role}>
                      <span className="flex items-center gap-2">
                        {role}
                        {pending && (
                          <span className="text-xs text-amber-500 font-normal">(needs approval)</span>
                        )}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Password fields only when not a pending request */}
              {!selectedRoleOption.pending && (
                <>
                  <PasswordInput
                    placeholder="Password"
                    value={newUserPassword}
                    onChange={(e) => setNewUserPassword(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  />
                  <PasswordInput
                    placeholder="Confirm password"
                    value={newUserConfirmPassword}
                    onChange={(e) => setNewUserConfirmPassword(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2"
                  />
                </>
              )}

              {selectedRoleOption.pending && (
                <p className="text-xs text-muted-foreground md:col-span-2">
                  No password needed — a password-reset email will be sent to the user once approved.
                </p>
              )}
            </div>

            <div className="flex gap-2">
              <Button onClick={createUser} disabled={creating}>
                {creating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {selectedRoleOption.pending ? "Submit Request" : "Add User"}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setShowCreateForm(false);
                  setNewUserName("");
                  setNewUserEmail("");
                  setNewUserRole(roleOptions[0].role);
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

        {/* ── User List (admin + global_admin only) ────────────────────────── */}
        {canSeeUserList && (
          <>
            {loading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
              </div>
            ) : users.length === 0 ? (
              <p className="text-sm text-muted-foreground">No users available.</p>
            ) : (
              <div className="space-y-3">
                {users.map((u: any) => (
                  <div
                    key={u.id}
                    className="flex items-center justify-between gap-3 p-3 rounded-md border border-border/60"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{u.email}</p>
                      <p className="text-xs text-muted-foreground">Current role: {u.role}</p>
                      <p className="text-xs text-muted-foreground">Tenant: {u.tenant_name || "Unknown tenant"}</p>
                    </div>

                    {canChangeExistingRoles ? (
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
                            {(["global_admin", "admin", "user", "viewer", "guest"] as AppRole[]).map((role: any) => (
                              <SelectItem key={role} value={role}>
                                {role}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {updatingUserId === u.id && (
                          <Loader2 className="h-4 w-4 animate-spin text-primary" />
                        )}
                      </div>
                    ) : (
                      <span className="text-xs px-2 py-1 rounded bg-muted text-muted-foreground">
                        {u.role}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
            <div className="mt-4">
              <Button variant="outline" onClick={loadUsers}>Refresh User List</Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
