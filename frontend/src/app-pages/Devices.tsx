import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Users,
  Plus,
  Trash2,
  Loader2,
  Package,
  UserCheck,
  Mail,
  ShieldCheck,
  User,
  X,
  Search,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { supabase } from "@/integrations/supabase/client";
import { apiUrl } from "@/lib/apiBaseUrl";
import { formatDistanceToNow } from "date-fns";
import { brokerModels, mgaModels, carrierModels } from "@/lib/insuranceMocks";

interface UserAccount {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

interface AllocatedModel {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
  activated_at: string | null;
}

type AppRole = "global_admin" | "admin" | "user" | "viewer" | "guest";

const roleDisplay: Record<AppRole, { label: string; badgeClass: string; privileged: boolean }> = {
  global_admin: {
    label: "Global Admin",
    badgeClass: "bg-purple-600/15 text-purple-700 border-purple-600/30 dark:text-purple-300",
    privileged: true,
  },
  admin: {
    label: "Admin",
    badgeClass: "bg-blue-600/15 text-blue-700 border-blue-600/30 dark:text-blue-300",
    privileged: true,
  },
  user: {
    label: "User",
    badgeClass: "bg-emerald-600/15 text-emerald-700 border-emerald-600/30 dark:text-emerald-300",
    privileged: false,
  },
  viewer: {
    label: "Viewer",
    badgeClass: "bg-amber-600/15 text-amber-700 border-amber-600/30 dark:text-amber-300",
    privileged: false,
  },
  guest: {
    label: "Guest",
    badgeClass: "bg-slate-600/15 text-slate-700 border-slate-600/30 dark:text-slate-300",
    privileged: false,
  },
};

function normalizeRole(role?: string): AppRole {
  const value = (role || "").toLowerCase();
  if (value === "global_admin" || value === "admin" || value === "user" || value === "viewer" || value === "guest") {
    return value;
  }
  return "user";
}

const allMarketplaceModels = [
  ...brokerModels.map(m => ({ id: m.id, name: m.name, domain: m.domain })),
  ...mgaModels.map(m => ({ id: m.id, name: m.name, domain: m.domain })),
  ...carrierModels.map(m => ({ id: m.id, name: m.name, domain: m.domain })),
];

export default function Devices() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [userModels, setUserModels] = useState<Record<string, AllocatedModel[]>>({});

  // Inline allocation state per user
  const [allocatingForUser, setAllocatingForUser] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [allocating, setAllocating] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const refreshTimerRef = useRef<number | null>(null);

  useEffect(() => {
    checkAccessAndLoad();

    const channel = supabase
      .channel("devices-page-live")
      .on("postgres_changes", { event: "*", schema: "public", table: "activated_models" }, () => {
        if (refreshTimerRef.current !== null) {
          window.clearTimeout(refreshTimerRef.current);
        }
        refreshTimerRef.current = window.setTimeout(() => {
          refreshTimerRef.current = null;
          void loadUsers();
        }, 400);
      })
      .subscribe();

    return () => {
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
      }
      supabase.removeChannel(channel);
    };
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setAllocatingForUser(null);
        setSearchTerm("");
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const checkAccessAndLoad = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) { navigate("/auth"); return; }

      const { data: roles } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", user.id);

      if (!roles?.some(r => r.role === "admin" || r.role === "global_admin")) {
        toast({ title: "Access Denied", description: "Admin only", variant: "destructive" });
        navigate("/"); return;
      }

      await loadUsers();
    } catch {
      navigate("/auth");
    }
  };

  const loadUsersFromSupabaseFallback = async () => {
    const { data: appUsers, error: appUsersError } = await supabase
      .from("app_users")
      .select("user_id,email,created_at");
    if (appUsersError) throw appUsersError;

    const { data: roleRows, error: rolesError } = await supabase
      .from("user_roles")
      .select("user_id,role");
    if (rolesError) throw rolesError;

    const roleMap = new Map((roleRows || []).map(r => [r.user_id, r.role]));
    const fallbackUsers: UserAccount[] = (appUsers || []).map(u => ({
      id: u.user_id,
      email: u.email,
      role: roleMap.get(u.user_id) ?? "user",
      created_at: u.created_at,
    }));
    setUsers(fallbackUsers);
  };

  const loadUsers = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      let userList: UserAccount[] = [];

      try {
        const response = await fetch(
          apiUrl("/api/list-users"),
          { headers: { Authorization: `Bearer ${session.access_token}` } }
        );

        if (response.ok) {
          const data = await response.json();
          userList = data.users || [];
          setUsers(userList);
        } else {
          await loadUsersFromSupabaseFallback();
          return;
        }
      } catch (backendError) {
        console.warn("Primary /api/list-users failed, using fallback:", backendError);
        await loadUsersFromSupabaseFallback();
        return;
      }

      const userIds = userList.map((u) => u.id).filter(Boolean);
      if (!userIds.length) {
        setUserModels({});
        return;
      }

      const { data: allModels, error } = await supabase
        .from("activated_models")
        .select("id,user_id,model_id,model_name,domain,activated_at")
        .in("user_id", userIds);

      if (!error && allModels) {
        const grouped: Record<string, AllocatedModel[]> = {};
        for (const m of allModels) {
          if (!grouped[m.user_id]) grouped[m.user_id] = [];
          grouped[m.user_id].push(m);
        }
        setUserModels(grouped);
      }
    } catch (error) {
      console.error("Error loading users:", error);
      toast({ title: "Error", description: "Failed to load user accounts", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleAllocate = async (userId: string, userEmail: string, modelId: string) => {
    const model = allMarketplaceModels.find(m => m.id === modelId);
    if (!model) return;

    setAllocating(true);
    try {
      const { error } = await supabase.from("activated_models").insert({
        user_id: userId,
        model_id: model.id,
        model_name: model.name,
        domain: model.domain as any,
      });

      if (error) {
        if (error.code === "23505") {
          toast({ title: "Already Allocated", description: "Model already assigned to this user", variant: "destructive" });
        } else throw error;
        return;
      }

      toast({ title: "Model Allocated", description: `${model.name} allocated to ${userEmail}` });
      setAllocatingForUser(null);
      setSearchTerm("");
      loadUsers();
    } catch (error) {
      console.error("Error allocating:", error);
      toast({ title: "Error", description: "Failed to allocate model", variant: "destructive" });
    } finally {
      setAllocating(false);
    }
  };

  const handleDeallocate = async (allocationId: string, modelName: string) => {
    try {
      const { error } = await supabase.from("activated_models").delete().eq("id", allocationId);
      if (error) throw error;
      toast({ title: "Model Removed", description: `${modelName} deallocated` });
      loadUsers();
    } catch (error) {
      console.error("Error deallocating:", error);
      toast({ title: "Error", description: "Failed to remove model", variant: "destructive" });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen relative">
      {/* Animated Background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-1/4 w-96 h-96 bg-primary/10 rounded-full blur-3xl animate-glow-pulse" />
        <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-accent/10 rounded-full blur-3xl animate-glow-pulse" style={{ animationDelay: '2s' }} />
      </div>

      <div className="relative z-10 space-y-8 animate-fade-in">
        {/* Hero Header */}
        <div className="relative rounded-2xl bg-gradient-hero p-8 border border-border/50 backdrop-blur-sm shadow-premium">
          <div className="absolute inset-0 bg-gradient-subtle rounded-2xl opacity-50" />
          <div className="relative">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-3 rounded-xl bg-gradient-to-br from-primary/20 to-primary/10 shadow-card">
                <Users className="h-7 w-7 text-primary animate-float" />
              </div>
              <h1 className="text-4xl font-display font-bold tracking-tight bg-gradient-to-r from-primary via-primary to-accent bg-clip-text text-transparent">
                User Accounts
              </h1>
            </div>
            <p className="text-muted-foreground text-lg">
              Manage user accounts and allocate AI models
            </p>
          </div>
        </div>

        {/* User Cards */}
        {users.length === 0 ? (
          <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card">
            <CardContent className="text-center py-20">
              <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-hero mb-6">
                <Users className="h-10 w-10 text-primary" />
              </div>
              <h3 className="text-2xl font-display font-bold mb-3">No Users Found</h3>
              <p className="text-muted-foreground max-w-md mx-auto text-lg">
                Create user accounts from the Admin Dashboard
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {users.map((user, index) => {
              const models = userModels[user.id] || [];
              const normalizedRole = normalizeRole(user.role);
              const roleMeta = roleDisplay[normalizedRole];
              const isAdmin = roleMeta.privileged;
              const isPickerOpen = allocatingForUser === user.id;
              const availableModels = allMarketplaceModels.filter(
                m => !models.some(um => um.model_id === m.id)
              );
              const filteredModels = availableModels.filter(m =>
                m.name.toLowerCase().includes(searchTerm.toLowerCase())
              );

              return (
                <Card
                  key={user.id}
                  className="group relative overflow-hidden bg-card/90 backdrop-blur-sm border-border/50 shadow-card hover:shadow-premium hover:border-primary/30 transition-all duration-300 animate-scale-in"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="absolute inset-0 pointer-events-none bg-gradient-primary opacity-0 group-hover:opacity-5 transition-opacity duration-300" />

                  <CardHeader className="relative z-10 pb-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="p-3 rounded-xl bg-gradient-hero group-hover:scale-110 transition-transform duration-300">
                        {isAdmin ? (
                          <ShieldCheck className="h-6 w-6 text-primary" />
                        ) : (
                          <User className="h-6 w-6 text-primary" />
                        )}
                      </div>
                      <Badge variant="outline" className={roleMeta.badgeClass}>
                        {roleMeta.label}
                      </Badge>
                    </div>
                    <CardTitle className="text-lg font-display font-bold group-hover:text-primary transition-colors truncate">
                      {user.email}
                    </CardTitle>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Mail className="h-3 w-3" />
                      <span>Joined {formatDistanceToNow(new Date(user.created_at), { addSuffix: true })}</span>
                    </div>
                  </CardHeader>

                  <CardContent className="relative z-10 space-y-4">
                    {/* Allocated Models */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                          <Package className="h-3 w-3" />
                          Allocated Models
                        </span>
                        <Badge variant="outline" className="text-[10px]">{models.length}</Badge>
                      </div>

                      {models.length > 0 ? (
                        <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
                          {models.map(model => (
                            <div key={model.id} className="flex items-center justify-between gap-2 p-2 rounded-lg bg-muted/50 text-xs">
                              <div className="flex items-center gap-2 min-w-0">
                                <UserCheck className="h-3 w-3 text-primary shrink-0" />
                                <span className="truncate font-medium">{model.model_name}</span>
                              </div>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6 shrink-0 text-destructive hover:text-destructive"
                                onClick={() => handleDeallocate(model.id, model.model_name)}
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-muted-foreground italic py-2">No models allocated</p>
                      )}
                    </div>

                    {/* Inline Model Picker */}
                    <div className="relative" ref={isPickerOpen ? dropdownRef : undefined}>
                      {isPickerOpen ? (
                        <div className="border border-border rounded-lg bg-card shadow-lg">
                          {/* Search input */}
                          <div className="flex items-center gap-2 p-2 border-b border-border">
                            <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                            <input
                              type="text"
                              className="flex-1 text-sm bg-transparent outline-none placeholder:text-muted-foreground"
                              placeholder="Search models..."
                              value={searchTerm}
                              onChange={(e) => setSearchTerm(e.target.value)}
                              autoFocus
                            />
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-5 w-5 shrink-0"
                              onClick={() => { setAllocatingForUser(null); setSearchTerm(""); }}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </div>
                          {/* Model list */}
                          <div className="max-h-40 overflow-y-auto">
                            {filteredModels.length > 0 ? (
                              filteredModels.map(model => (
                                <button
                                  key={model.id}
                                  className="w-full flex items-center justify-between gap-2 px-3 py-2 text-xs hover:bg-muted/80 transition-colors text-left disabled:opacity-50"
                                  disabled={allocating}
                                  onClick={() => handleAllocate(user.id, user.email, model.id)}
                                >
                                  <span className="font-medium truncate">{model.name}</span>
                                  <Badge variant="secondary" className="text-[10px] shrink-0">{model.domain}</Badge>
                                </button>
                              ))
                            ) : (
                              <p className="text-xs text-muted-foreground text-center py-3">No models available</p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          className="w-full gap-1.5 hover:bg-primary hover:text-primary-foreground transition-colors"
                          onClick={() => { setAllocatingForUser(user.id); setSearchTerm(""); }}
                        >
                          <Plus className="h-3.5 w-3.5" />
                          Allocate Model
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
