import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { parsePolicyClauseDiff, type PolicyClauseDiff } from "@/lib/policyClauseDiff";

type ClauseStatus = PolicyClauseDiff["clauses"][number]["status"];

function statusBadge(status: ClauseStatus): { variant: "added" | "removed" | "changed" } {
  if (status === "added") return { variant: "added" };
  if (status === "removed") return { variant: "removed" };
  return { variant: "changed" };
}

function StatusBadge({ status }: { status: ClauseStatus }) {
  const b = statusBadge(status);
  if (b.variant === "added") {
    return (
      <Badge className="bg-green-500/15 text-green-700 border border-green-500/30">
        Added
      </Badge>
    );
  }
  if (b.variant === "removed") {
    return (
      <Badge variant="destructive" className="bg-red-500/10 text-red-700 border border-red-500/30">
        Removed
      </Badge>
    );
  }
  return (
    <Badge className="bg-amber-500/15 text-amber-700 border border-amber-500/30">
      Changed
    </Badge>
  );
}

export default function PolicyClauseRedlineUI({ result }: { result: string }) {
  const diff = useMemo(() => parsePolicyClauseDiff(result), [result]);
  const clauses = useMemo(() => diff?.clauses ?? [], [diff]);

  const [selectedIdx, setSelectedIdx] = useState(0);
  useEffect(() => {
    setSelectedIdx(0);
  }, [result, clauses.length]);

  const selected = clauses[selectedIdx] ?? null;

  const counts = useMemo(() => {
    const added = clauses.filter((c: any) => c.status === "added").length;
    const removed = clauses.filter((c: any) => c.status === "removed").length;
    const changed = clauses.filter((c: any) => c.status === "changed").length;
    return { added, removed, changed };
  }, [clauses]);

  if (!diff) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            Clause diff not available; showing coverage comparison instead.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            Clause Redline
          </CardTitle>
          <div className="flex flex-wrap gap-2 mt-2">
            <Badge className="bg-green-500/15 text-green-700 border border-green-500/30">
              Added ({counts.added})
            </Badge>
            <Badge variant="destructive" className="bg-red-500/10 text-red-700 border border-red-500/30">
              Removed ({counts.removed})
            </Badge>
            <Badge className="bg-amber-500/15 text-amber-700 border border-amber-500/30">
              Changed ({counts.changed})
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-1 space-y-2">
              {clauses.length === 0 ? (
                <p className="text-sm text-muted-foreground">No clause changes detected.</p>
              ) : (
                <div className="space-y-2 max-h-[520px] overflow-auto pr-1">
                  {clauses.map((c: any, idx: any) => (
                    <button
                      key={`${c.id}-${c.status}-${idx}`}
                      type="button"
                      onClick={() => setSelectedIdx(idx)}
                      className={[
                        "w-full text-left rounded-lg border p-3 transition-colors",
                        selectedIdx === idx ? "border-primary bg-primary/5" : "border-border/60 hover:bg-muted/30",
                      ].join(" ")}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-[12px] font-medium text-foreground truncate">
                            {c.title || c.id}
                          </div>
                          {c.path && <div className="text-[11px] text-muted-foreground mt-1 truncate">{c.path}</div>}
                        </div>
                        <StatusBadge status={c.status} />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="lg:col-span-2">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Selected clause</Label>
                    <div className="text-sm font-medium text-foreground">
                      {selected ? selected.title || selected.id : "—"}
                    </div>
                    {selected && (
                      <div className="text-xs text-muted-foreground">
                        Status: <span className="font-medium">{selected.status}</span>
                      </div>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!selected || selectedIdx === 0}
                    onClick={() => setSelectedIdx((i) => Math.max(0, i - 1))}
                  >
                    Previous
                  </Button>
                </div>

                {selected ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">Before</Label>
                      <pre className="rounded-lg border border-border/70 bg-[#0b1020] p-3 overflow-auto max-h-[420px] text-xs font-mono leading-5 whitespace-pre-wrap">
                        {selected.before?.trim() ? selected.before : "—"}
                      </pre>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">After</Label>
                      <pre className="rounded-lg border border-border/70 bg-[#0b1020] p-3 overflow-auto max-h-[420px] text-xs font-mono leading-5 whitespace-pre-wrap">
                        {selected.after?.trim() ? selected.after : "—"}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Select a clause to view before/after.</p>
                )}
              </div>

              {selected && selectedIdx < clauses.length - 1 && (
                <div className="mt-4 flex justify-end">
                  <Button variant="outline" size="sm" onClick={() => setSelectedIdx((i) => Math.min(clauses.length - 1, i + 1))}>
                    Next
                  </Button>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

