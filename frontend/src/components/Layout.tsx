import { ReactNode, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { User, LogOut } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import type { User as SupabaseUser } from "@supabase/supabase-js";
import { useUserRole } from "@/hooks/useUserRole";
import { safeLog } from "@/logger";
import { computeAuditIntegrityHash } from "@/lib/auditHash";
import { useGlobalRealtimeSubscriptions } from "@/hooks/useGlobalRealtimeSubscriptions";
import { RealtimeNotificationBell } from "@/components/RealtimeNotificationBell";

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [user, setUser] = useState<SupabaseUser | null>(null);
  const navigate = useNavigate();
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
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        setUser(session?.user ?? null);
        if (!session?.user && event !== 'INITIAL_SESSION') {
          navigate("/auth");
        }
      }
    );

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        navigate("/auth");
      } else {
        setUser(session.user);
      }
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

  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex min-h-screen w-full bg-background">
        <AppSidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b border-border bg-card/80 backdrop-blur-sm px-3 md:px-4">
            <SidebarTrigger className="text-foreground" />
            <div className="flex-1" />
            <div className="flex items-center gap-2 md:gap-3">
              {/* Show email only on larger screens */}
              <div className="hidden sm:flex items-center gap-2 text-sm text-muted-foreground">
                <User className="h-4 w-4" />
                <span className="truncate max-w-[150px] md:max-w-none">{user.email}</span>
                {role && (
                  <span className="text-xs px-2 py-0.5 rounded-full border border-border bg-muted/60 text-foreground">
                    {roleLabelMap[role] || role}
                  </span>
                )}
              </div>
              <RealtimeNotificationBell />
              {/* Mobile: icon only, Desktop: icon + text */}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                className="gap-2 h-9 w-9 md:h-9 md:w-auto md:px-3"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden md:inline">Logout</span>
              </Button>
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
