import { Skeleton } from "@/components/ui/skeleton";
import { GlobalAdminRoleManager } from "@/components/admin/GlobalAdminRoleManager";
import { UserCreationRequests } from "@/components/admin/UserCreationRequests";
import { useUserRole } from "@/hooks/useUserRole";
import { Users as UsersIcon } from "lucide-react";

export default function Users() {
  const { isAdmin, isGlobalAdmin, loading } = useUserRole();

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-5 w-80" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight">Users</h1>
        <p className="text-muted-foreground">
          You do not have permission to view user management.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <UsersIcon className="h-7 w-7 text-primary" />
          Users
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage user creation requests and account roles.
        </p>
      </div>

      <UserCreationRequests viewerRole={isGlobalAdmin ? "global_admin" : "admin"} />

      <GlobalAdminRoleManager currentUserRole={isGlobalAdmin ? "global_admin" : "admin"} />
    </div>
  );
}

