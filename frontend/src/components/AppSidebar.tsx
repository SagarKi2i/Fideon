import { FideonLogo } from "@/components/FideonLogo";
import { 
  LayoutDashboard, 
  ShoppingBag, 
  Box, 
  MessageSquare, 
  FileText,
  Mail,
  Settings,
  Brain,
  Monitor,
  Download,
  Presentation,
  Shield,
  Clock,
  ChevronDown,
  Activity,
  GraduationCap,
  Workflow,
  CalendarClock,
  Zap,
  ClipboardCheck,
  QrCode,
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import { useState, useEffect } from "react";
import { isElectron } from "@/lib/ollama";
import { useUserRole } from "@/hooks/useUserRole";
import { supabase } from "@/integrations/supabase/client";
import { Separator } from "@/components/ui/separator";
import { HelpAssistant } from "@/components/HelpAssistant";
import type { Database } from "@/integrations/supabase/types";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface ActivatedPod {
  id: string;
  model_id: string;
  model_name: string;
  domain: string;
}

type AppRole = Database["public"]["Enums"]["app_role"];

const items = [
  { title: "User Dashboard", url: "/", icon: LayoutDashboard, allowedRoles: ["global_admin", "admin", "user", "viewer", "guest"] as AppRole[] },
  { title: "Marketplace", url: "/marketplace", icon: ShoppingBag, allowedRoles: ["global_admin", "admin", "user", "viewer", "guest"] as AppRole[] },
  { title: "My Models", url: "/my-models", icon: Box, allowedRoles: ["global_admin", "admin", "user", "viewer"] as AppRole[] },
  { title: "Playground", url: "/playground", icon: MessageSquare, allowedRoles: ["global_admin", "admin", "user"] as AppRole[] },
  { title: "Model Training", url: "/training", icon: GraduationCap, allowedRoles: ["global_admin", "admin", "user"] as AppRole[] },
  { title: "Agent Workflows", url: "/agent-workflows", icon: Zap, allowedRoles: ["global_admin", "admin", "user"] as AppRole[] },
  { title: "Custom Workflows", url: "/workflows", icon: Workflow, allowedRoles: ["global_admin", "admin", "user"] as AppRole[] },
  { title: "Schedules", url: "/schedules", icon: CalendarClock, allowedRoles: ["global_admin", "admin", "user"] as AppRole[] },
  { title: "Review Queue", url: "/review-queue", icon: ClipboardCheck, allowedRoles: ["global_admin", "admin", "user"] as AppRole[] },
  
  { title: "Mailbox", url: "/mailbox", icon: Mail, allowedRoles: ["global_admin", "admin", "user"] as AppRole[] },
  { title: "Settings", url: "/settings", icon: Settings, allowedRoles: ["global_admin", "admin", "user", "viewer", "guest"] as AppRole[] },
  { title: "Link Devices", url: "/link-devices", icon: QrCode, allowedRoles: ["global_admin", "admin", "user", "viewer", "guest"] as AppRole[] },
];

const adminItems = [
  { title: "Admin Dashboard", url: "/admin", icon: Shield },
  { title: "Devices", url: "/devices", icon: Monitor },
  { title: "Pending Approvals", url: "/devices/pending", icon: Clock },
];

const electronItems = [
  { title: "Device Setup", url: "/device-setup", icon: Download },
];

export function AppSidebar() {
  const { state, isMobile, setOpenMobile } = useSidebar();
  const location = useLocation();
  const currentPath = location.pathname;
  const { isAdmin, role } = useUserRole();
  const visibleItems = items.filter((item) => {
    if (!role) return false;
    return item.allowedRoles.includes(role);
  });

  const [isElectronApp, setIsElectronApp] = useState(false);
  const [activatedPods, setActivatedPods] = useState<ActivatedPod[]>([]);
  const [podsOpen, setPodsOpen] = useState(true);

  // Check if sidebar is expanded (works for both mobile and desktop)
  const isExpanded = state === "expanded";

  useEffect(() => {
    const checkElectron = async () => {
      const result = await isElectron();
      setIsElectronApp(result);
    };
    checkElectron();
    loadActivatedPods();
  }, []);

  const loadActivatedPods = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;

      const { data, error } = await supabase
        .from("activated_models")
        .select("*")
        .eq("user_id", user.id);

      if (!error && data) {
        setActivatedPods(data);
      }
    } catch (error) {
      console.error("Error loading pods:", error);
    }
  };

  // Close sidebar on mobile when navigating
  const handleNavClick = () => {
    if (isMobile) {
      setOpenMobile(false);
    }
  };

  const isActive = (path: string) => {
    if (path === "/") {
      return currentPath === "/";
    }
    return currentPath.startsWith(path);
  };

  // Check if any pod dashboard is active
  const isPodDashboardActive = currentPath.startsWith("/pod/");

  return (
    <Sidebar collapsible="icon">
      <SidebarContent className="bg-sidebar border-r border-sidebar-border">
        <div className="px-3 py-4 flex items-center gap-2">
          <FideonLogo size={36} className="flex-shrink-0" />
          <div className="flex flex-col min-w-0 group-data-[collapsible=icon]:hidden">
            <span className="font-semibold text-sidebar-foreground truncate">Fideon OS</span>
            <span className="text-xs text-sidebar-foreground/70 truncate">AI for Insurance</span>
          </div>
        </div>
        
        <SidebarGroup>
          <SidebarGroupLabel className="text-sidebar-foreground/70">Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {visibleItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild tooltip={item.title}>
                    <NavLink 
                      to={item.url} 
                      end={item.url === "/"}
                      onClick={handleNavClick}
                      className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
                      activeClassName="bg-sidebar-primary text-sidebar-primary-foreground font-medium"
                    >
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Activated Pods Section */}
        {activatedPods.length > 0 && (
          <SidebarGroup>
            <Collapsible open={podsOpen} onOpenChange={setPodsOpen}>
              <CollapsibleTrigger className="w-full">
                <SidebarGroupLabel className="text-sidebar-foreground/70 flex items-center justify-between cursor-pointer hover:text-sidebar-foreground transition-colors">
                  <span className="flex items-center gap-2">
                    <Activity className="h-3.5 w-3.5" />
                    Active Pods
                  </span>
                  <ChevronDown className={`h-4 w-4 transition-transform ${podsOpen ? "" : "-rotate-90"}`} />
                </SidebarGroupLabel>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {activatedPods.map((pod) => (
                      <SidebarMenuItem key={pod.id}>
                        <SidebarMenuButton asChild tooltip={pod.model_name}>
                          <NavLink 
                            to={`/pod/${pod.model_id}`}
                            onClick={handleNavClick}
                            className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
                            activeClassName="bg-sidebar-primary text-sidebar-primary-foreground font-medium"
                          >
                            <div className="h-2 w-2 rounded-full bg-green-500 flex-shrink-0" />
                            <span className="truncate">{pod.model_name}</span>
                          </NavLink>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </CollapsibleContent>
            </Collapsible>
          </SidebarGroup>
        )}

        {isAdmin && (
          <SidebarGroup>
            <SidebarGroupLabel className="text-sidebar-foreground/70">Admin</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {adminItems.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild tooltip={item.title}>
                      <NavLink 
                        to={item.url}
                        onClick={handleNavClick}
                        className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
                        activeClassName="bg-sidebar-primary text-sidebar-primary-foreground font-medium"
                      >
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {isElectronApp && (
          <SidebarGroup>
            <SidebarGroupLabel className="text-sidebar-foreground/70">Device</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {electronItems.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild tooltip={item.title}>
                      <NavLink 
                        to={item.url}
                        onClick={handleNavClick}
                        className="hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
                        activeClassName="bg-sidebar-primary text-sidebar-primary-foreground font-medium"
                      >
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {/* Separator + Help Assistant */}
        <div className="mt-auto px-3 pb-4 group-data-[collapsible=icon]:hidden">
          <Separator className="mb-4" />
          <HelpAssistant />
        </div>
      </SidebarContent>
    </Sidebar>
  );
}
