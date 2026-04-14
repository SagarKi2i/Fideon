import { ReactNode, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { ChevronDown, LogOut, Moon, Settings, Sun } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import type { User as SupabaseUser } from "@supabase/supabase-js";
import { useUserRole } from "@/hooks/useUserRole";
import { safeLog } from "@/logger";
import { computeAuditIntegrityHash } from "@/lib/auditHash";
import { useGlobalRealtimeSubscriptions } from "@/hooks/useGlobalRealtimeSubscriptions";
import { RealtimeNotificationBell } from "@/components/RealtimeNotificationBell";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Skeleton } from "@/components/ui/skeleton";
import { IdleSessionWatcher } from "@/components/IdleSessionWatcher";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [user, setUser] = useState<SupabaseUser | null>(null);
  const [tenantName, setTenantName] = useState<string>("");
  const [displayName, setDisplayName] = useState<string>("");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [headerReady, setHeaderReady] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const { role } = useUserRole();

  const roleLabelMap: Record<string, string> = {
    global_admin: "Global Admin",
    admin: "Admin",
    user: "User",
    viewer: "Viewer",
    guest: "Guest",
  };

  useGlobalRealtimeSubscriptions();

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem("theme") : null;
    const prefersDark =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialTheme: "light" | "dark" = saved === "dark" || (!saved && prefersDark) ? "dark" : "light";
    setTheme(initialTheme);
    document.documentElement.classList.toggle("dark", initialTheme === "dark");
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
    localStorage.setItem("theme", nextTheme);
  };

  useEffect(() => {
    const loadHeaderProfile = async () => {
      if (!user) return;
      setHeaderReady(false);
      try {
        const { data: profile } = await (supabase as any)
          .from("app_users")
          .select("full_name,tenant_id")
          .eq("user_id", user.id)
          .maybeSingle();

        const resolvedName = profile?.full_name || user.user_metadata?.full_name || "";
        setDisplayName(resolvedName);

        if (profile?.tenant_id) {
          const { data: tenant } = await (supabase as any)
            .from("tenants")
            .select("name")
            .eq("id", profile.tenant_id)
            .maybeSingle();
          setTenantName(tenant?.name || "");
        } else {
          setTenantName("");
        }
      } catch {
        setTenantName("");
      } finally {
        setHeaderReady(true);
      }
    };
    void loadHeaderProfile();
  }, [user]);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        setUser(session?.user ?? null);
        // Avoid forcing logout on TOKEN_REFRESH_FAILED during brief network/proxy blips.
        // Signed-out is the real terminal state.
        // USER_DELETED exists at runtime but may be missing from AuthChangeEvent typings in some @supabase/supabase-js versions.
        if (
          !session?.user &&
          (event === "SIGNED_OUT" || (event as string) === "USER_DELETED")
        ) {
          navigate("/auth");
        }
      }
    );

    supabase.auth
      .getSession()
      .then(({ data: { session } }) => {
        if (!session) {
          // If session isn't available immediately (e.g. refresh in-flight),
          // don't hard-redirect; allow ProtectedRoute/useUserRole to decide.
          // This prevents a "logout after 4-5 seconds" UX regression.
          setUser(null);
          return;
        }
        setUser(session.user);
      })
      .catch(() => {
        // Rare: auth storage / lock races; avoid crashing the layout.
        setUser(null);
      });

    return () => subscription.unsubscribe();
  }, [navigate]);

  const handleLogout = async () => {
    const currentUser = user;
    const currentRole = role;

    try {
      // Attempt to write a logout audit entry before signing out
      if (currentUser) {
        try {
          const createdAt = new Date().toISOString();
          const integrity_hash = await computeAuditIntegrityHash({
            user_id: currentUser.id,
            role: currentRole || "user",
            event: "logout",
            action_code: "E",
            outcome_code: 0,
            resource_type: "auth_session",
            resource_id: null,
            created_at: createdAt,
          });

          await (supabase as any).from("auth_audit").insert({
            user_id: currentUser.id,
            email: currentUser.email,
            role: currentRole || "user",
            event: "logout",
            action_code: "E",           // Execute (end auth session)
            outcome_code: 0,
            resource_type: "auth_session",
            resource_id: null,          // null for auth_session events (no specific resource)
            created_at: createdAt,
            integrity_hash,
          });
        } catch (auditError) {
          safeLog.error("auth_audit_logout_error", {
            error:
              auditError instanceof Error ? auditError.message : String(auditError),
          });
        }
      }
    } finally {
      await supabase.auth.signOut();
    }
    toast({
      title: "Signed out",
      description: "You have been signed out successfully.",
    });
    navigate("/auth");
  };

  if (!user) {
    return null;
  }

  const pathSegments = location.pathname.split("/").filter(Boolean);
  const deviceDetailLinkedUser =
    pathSegments.length === 2 &&
    pathSegments[0] === "devices" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(pathSegments[1])
      ? (location.state as { linkedUserLabel?: string } | null)?.linkedUserLabel
      : undefined;
  const routeLabelMap: Record<string, string> = {
    admin: "Admin Dashboard",
    "acord-queue": "Training Review",
    users: "Users",
    "model-registry": "Model Registry",
    devices: "Devices",
    pending: "Pending Approvals",
    marketplace: "Marketplace",
    "my-models": "My Models",
    playground: "Playground",
    training: "Model Training",
    workflows: "Custom Workflows",
    schedules: "Schedules",
    "agent-workflows": "Agent Workflows",
    "review-queue": "Review Queue",
    activity: "Activity",
    settings: "Settings",
    "link-devices": "Link Devices",
    "device-setup": "Device Setup",
    "fine-tuning-monitor": "Fine-tuning Monitor",
    mailbox: "Mailbox",
    documents: "Documents",
  };

  const initialsSource = displayName || user.email || "U";
  const initials = initialsSource
    .split(" ")
    .map((p: any) => p[0]?.toUpperCase())
    .filter(Boolean)
    .slice(0, 2)
    .join("");

  return (
    <SidebarProvider defaultOpen={true}>
      <IdleSessionWatcher />
      <div className="flex min-h-screen w-full bg-background">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b border-border bg-card/80 backdrop-blur-sm px-3 md:px-4">
            <SidebarTrigger className="text-foreground" />
            <div className="min-w-0">
              <Breadcrumb>
                <BreadcrumbList>
                  <BreadcrumbItem>
                    <BreadcrumbLink asChild>
                      <Link to="/">Home</Link>
                    </BreadcrumbLink>
                  </BreadcrumbItem>
                  {pathSegments.map((segment: any, index: any) => {
                    const to = `/${pathSegments.slice(0, index + 1).join("/")}`;
                    const isLast = index === pathSegments.length - 1;
                    const isDeviceDetailCrumb =
                      index === 1 &&
                      pathSegments[0] === "devices" &&
                      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment);
                    const label =
                      isDeviceDetailCrumb && deviceDetailLinkedUser
                        ? deviceDetailLinkedUser
                        : routeLabelMap[segment] || segment.replace(/-/g, " ");
                    const crumbNaturalCase = Boolean(isDeviceDetailCrumb && deviceDetailLinkedUser);
                    return [
                      <BreadcrumbSeparator key={`${to}-sep`} />,
                      <BreadcrumbItem key={to}>
                        {isLast ? (
                          <BreadcrumbPage
                            className={
                              crumbNaturalCase
                                ? "truncate max-w-[min(100vw-8rem,28rem)]"
                                : "capitalize"
                            }
                          >
                            {label}
                          </BreadcrumbPage>
                        ) : (
                          <BreadcrumbLink asChild>
                            <Link
                              to={to}
                              className={crumbNaturalCase ? "truncate max-w-[min(100vw-8rem,28rem)]" : "capitalize"}
                            >
                              {label}
                            </Link>
                          </BreadcrumbLink>
                        )}
                      </BreadcrumbItem>,
                    ];
                  })}
                </BreadcrumbList>
              </Breadcrumb>
            </div>
            <div className="flex-1" />
            <div className="flex items-center gap-2 md:gap-3">
              <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle dark mode">
                {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <RealtimeNotificationBell />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="h-9 px-2 gap-2 hover:bg-muted/60 hover:text-foreground">
                    <Avatar className="h-7 w-7">
                      <AvatarFallback className="text-xs">{initials || "U"}</AvatarFallback>
                    </Avatar>
                    <div className="hidden md:flex flex-col items-start leading-tight">
                      <span className="text-xs font-medium truncate max-w-[170px]">
                        {displayName || user.email}
                      </span>
                      {headerReady ? (
                        <span className="text-[11px] text-muted-foreground truncate max-w-[170px]">
                          {tenantName ? `${tenantName} • ` : ""}
                          {role ? (roleLabelMap[role] || role) : "User"}
                        </span>
                      ) : (
                        <Skeleton className="h-3 w-24" />
                      )}
                    </div>
                    <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-64">
                  <DropdownMenuLabel className="space-y-0.5">
                    <p className="text-sm font-medium truncate">{displayName || user.email}</p>
                    <p className="text-xs text-muted-foreground truncate">{user.email}</p>
                    <p className="text-xs text-muted-foreground">
                      {tenantName ? `${tenantName} • ` : ""}
                      {role ? (roleLabelMap[role] || role) : "User"}
                    </p>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => navigate("/settings")}>
                    <Settings className="h-4 w-4 mr-2" />
                    Settings
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleLogout}>
                    <LogOut className="h-4 w-4 mr-2" />
                    Logout
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </header>
          <main className="flex-1 p-3 md:p-6 overflow-auto">
            {children}
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
