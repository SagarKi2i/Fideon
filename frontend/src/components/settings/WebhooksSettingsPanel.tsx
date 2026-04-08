import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { Webhook, Copy, Trash2, RotateCcw } from "lucide-react";
import {
  createWebhook,
  deleteWebhook,
  fetchWebhooks,
  rotateWebhookSecret,
  updateWebhook,
  type WebhookRow,
} from "@/lib/webhooksApi";

const CANONICAL_EVENTS = ["device.online", "model.deployed", "inference.complete"] as const;

function eventsPayload(selected: Set<string>): string[] {
  if (selected.size === 0 || selected.size === CANONICAL_EVENTS.length) {
    return [];
  }
  return CANONICAL_EVENTS.filter((e) => selected.has(e));
}

export function WebhooksSettingsPanel() {
  const { toast } = useToast();
  const [rows, setRows] = useState<WebhookRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [newUrl, setNewUrl] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newEvents, setNewEvents] = useState<Set<string>>(new Set(CANONICAL_EVENTS));
  const [creating, setCreating] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const list = await fetchWebhooks();
      setRows(list);
    } catch (e) {
      toast({
        title: "Could not load webhooks",
        description: e instanceof Error ? e.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggleNewEvent = (e: string) => {
    setNewEvents((prev) => {
      const next = new Set(prev);
      if (next.has(e)) next.delete(e);
      else next.add(e);
      return next;
    });
  };

  const handleCreate = async () => {
    const url = newUrl.trim();
    if (!url) {
      toast({ title: "URL required", variant: "destructive" });
      return;
    }
    try {
      setCreating(true);
      const res = await createWebhook({
        url,
        description: newDesc.trim(),
        events: eventsPayload(newEvents),
      });
      setRevealedSecret(res.secret);
      setNewUrl("");
      setNewDesc("");
      setNewEvents(new Set(CANONICAL_EVENTS));
      await load();
      toast({
        title: "Webhook created",
        description: "Copy the signing secret now — it is only shown once.",
      });
    } catch (e) {
      toast({
        title: "Create failed",
        description: e instanceof Error ? e.message : "Unknown error",
        variant: "destructive",
      });
    } finally {
      setCreating(false);
    }
  };

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast({ title: "Copied" });
    } catch {
      toast({ title: "Copy failed", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-4">
      {revealedSecret && (
        <Card className="border-primary/40 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">New signing secret</CardTitle>
            <CardDescription>Store this securely; it will not be shown again.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-2">
            <code className="text-xs break-all flex-1 min-w-0 bg-muted px-2 py-1 rounded">{revealedSecret}</code>
            <Button type="button" size="sm" variant="outline" onClick={() => copyText(revealedSecret)}>
              <Copy className="h-4 w-4 mr-1" />
              Copy
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setRevealedSecret(null)}>
              Dismiss
            </Button>
          </CardContent>
        </Card>
      )}

      <Card className="bg-card border-border shadow-card">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <Webhook className="h-5 w-5 text-primary" />
            Outbound webhooks
          </CardTitle>
          <CardDescription>
            Receive JSON payloads with HMAC-SHA256 signatures (
            <span className="font-mono text-xs">X-Fideon-Signature</span> and{" "}
            <span className="font-mono text-xs">X-NeuraPod-Signature</span>
            ). Leave all event types selected to subscribe to every event.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="wh-url">Endpoint URL</Label>
              <Input
                id="wh-url"
                placeholder="https://example.com/webhooks/fideon"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="wh-desc">Description (optional)</Label>
              <Input
                id="wh-desc"
                placeholder="Production listener"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>Events</Label>
              <div className="flex flex-wrap gap-4">
                {CANONICAL_EVENTS.map((ev) => (
                  <label key={ev} className="flex items-center gap-2 text-sm cursor-pointer">
                    <Switch checked={newEvents.has(ev)} onCheckedChange={() => toggleNewEvent(ev)} />
                    <span className="font-mono text-xs">{ev}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          <Button className="bg-gradient-primary" onClick={() => void handleCreate()} disabled={creating}>
            {creating ? "Creating…" : "Add webhook"}
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-card border-border shadow-card">
        <CardHeader>
          <CardTitle className="text-card-foreground text-base">Registered endpoints</CardTitle>
          <CardDescription>
            {loading ? "Loading…" : rows.length === 0 ? "No webhooks yet." : `${rows.length} configured`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {rows.map((w) => (
            <div
              key={w.id}
              className="rounded-lg border border-border p-3 space-y-2 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="min-w-0 flex-1 space-y-1">
                <p className="font-medium text-sm break-all">{w.url}</p>
                {w.description && <p className="text-xs text-muted-foreground">{w.description}</p>}
                <div className="flex flex-wrap gap-1">
                  {!w.events || w.events.length === 0 ? (
                    <Badge variant="secondary">all events</Badge>
                  ) : (
                    w.events.map((ev) => (
                      <Badge key={ev} variant="outline" className="font-mono text-[10px]">
                        {ev}
                      </Badge>
                    ))
                  )}
                  {!w.is_active && (
                    <Badge variant="destructive" className="text-[10px]">
                      inactive
                    </Badge>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 shrink-0">
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-muted-foreground">Active</span>
                  <Switch
                    checked={w.is_active}
                    onCheckedChange={async (on) => {
                      try {
                        await updateWebhook(w.id, { is_active: on });
                        await load();
                      } catch (e) {
                        toast({
                          title: "Update failed",
                          description: e instanceof Error ? e.message : "Unknown error",
                          variant: "destructive",
                        });
                      }
                    }}
                  />
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    try {
                      const r = await rotateWebhookSecret(w.id);
                      setRevealedSecret(r.secret);
                      toast({ title: "Secret rotated", description: "Copy the new secret now." });
                    } catch (e) {
                      toast({
                        title: "Rotate failed",
                        description: e instanceof Error ? e.message : "Unknown error",
                        variant: "destructive",
                      });
                    }
                  }}
                >
                  <RotateCcw className="h-3.5 w-3.5 mr-1" />
                  Rotate
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="destructive"
                  onClick={async () => {
                    if (!confirm("Delete this webhook? Deliveries in flight may fail.")) return;
                    try {
                      await deleteWebhook(w.id);
                      await load();
                      toast({ title: "Webhook removed" });
                    } catch (e) {
                      toast({
                        title: "Delete failed",
                        description: e instanceof Error ? e.message : "Unknown error",
                        variant: "destructive",
                      });
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1" />
                  Delete
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
