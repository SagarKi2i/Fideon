import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { safeLog } from "@/logger";

interface AuditRow {
  id: string;
  user_id: string;
  email: string;
  role: string;
  event: string;
  action_code?: string | null;
  outcome_code?: number | null;
  resource_type?: string | null;
  resource_id?: string | null;
  created_at: string;
}

export default function Activity() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const { data, error } = await (supabase as any)
          // Untyped access because auth_audit is not in generated Database types
          .from("auth_audit")
          .select("*")
          .order("created_at", { ascending: false });

        if (error) throw error;
        setRows((data || []) as AuditRow[]);
      } catch (e: any) {
        safeLog.error("activity_fetch_error", { error: e.message });
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>User Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading activity…</p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">No activity recorded yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Outcome</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-nowrap text-xs">
                      {new Date(row.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs">{row.email}</TableCell>
                    <TableCell>
                      <Badge variant={row.role.includes("admin") ? "default" : "outline"}>
                        {row.role}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">{row.event}</TableCell>
                    <TableCell className="text-xs">
                      {row.action_code || "-"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {row.resource_type
                        ? `${row.resource_type}${row.resource_id ? `:${row.resource_id}` : ""}`
                        : "-"}
                    </TableCell>
                    <TableCell className="text-xs">
                      {typeof row.outcome_code === "number" ? row.outcome_code : "-"}
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

