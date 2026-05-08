/**
 * Re-exports useUserRole from UserRoleContext.
 * The hook is now backed by a React Context (UserRoleProvider) so all
 * consumers share one fetch instead of each making their own.
 *
 * No changes needed in any consumer — the import path stays the same.
 */
export { useUserRole } from "@/contexts/UserRoleContext";
