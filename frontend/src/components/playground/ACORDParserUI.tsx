import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Upload, FileText, Loader2, FileCheck } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { submitAcordRun } from "@/lib/acordWorkflowApi";
import { useNavigate } from "react-router-dom";

interface ACORDParserUIProps {
  modelId?: string;
  onRun: (data: any) => void;
  isRunning: boolean;
  result: string;
}

function stripJsonCodeFence(value: string): string {
  const trimmed = value.trim();
  // Supports:
  // ```json\n{...}\n```
  // ```\n{...}\n```
  if (trimmed.startsWith("```")) {
    const firstNewline = trimmed.indexOf("\n");
    const lastFence = trimmed.lastIndexOf("```");
    if (firstNewline !== -1 && lastFence > firstNewline) {
      return trimmed.slice(firstNewline + 1, lastFence).trim();
    }
  }
  return value;
}

function safeJsonParse(value: string): { ok: true; json: any } | { ok: false; error: string } {
  try {
    return { ok: true, json: JSON.parse(stripJsonCodeFence(value)) };
  } catch (e: any) {
    return { ok: false, error: e?.message || "Invalid JSON" };
  }
}

function flattenValues(input: any, prefix = "", out: Record<string, string> = {}): Record<string, string> {
  if (input === null) {
    out[prefix || "null"] = "null";
    return out;
  }

  const t = typeof input;
  if (t === "string" || t === "number" || t === "boolean") {
    out[prefix || "value"] = String(input);
    return out;
  }

  if (Array.isArray(input)) {
    input.forEach((v, i) => {
      const nextPrefix = prefix ? `${prefix}[${i}]` : `[${i}]`;
      flattenValues(v, nextPrefix, out);
    });
    return out;
  }

  if (t === "object") {
    Object.entries(input).forEach(([k, v]) => {
      const nextPrefix = prefix ? `${prefix}.${k}` : k;
      flattenValues(v, nextPrefix, out);
    });
    return out;
  }

  out[prefix || "value"] = String(input);
  return out;
}

type ChangeItem =
  | { type: "added"; path: string; after: string }
  | { type: "removed"; path: string; before: string }
  | { type: "changed"; path: string; before: string; after: string };

function computeChanges(original: any, edited: any, maxItems = 120): ChangeItem[] {
  const o = flattenValues(original);
  const e = flattenValues(edited);
  const keys = new Set([...Object.keys(o), ...Object.keys(e)]);
  const items: ChangeItem[] = [];

  for (const key of keys) {
    const before = o[key];
    const after = e[key];

    if (before === undefined && after !== undefined) {
      items.push({ type: "added", path: key, after });
    } else if (before !== undefined && after === undefined) {
      items.push({ type: "removed", path: key, before });
    } else if (before !== after) {
      items.push({ type: "changed", path: key, before: before ?? "", after: after ?? "" });
    }

    if (items.length >= maxItems) break;
  }

  // Deterministic ordering for UX.
  const rank = (t: ChangeItem["type"]) => (t === "added" ? 0 : t === "removed" ? 1 : 2);
  items.sort((a, b) => rank(a.type) - rank(b.type) || a.path.localeCompare(b.path));
  return items;
}

function JsonHighlight({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  const re =
    /("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (match.index > cursor) {
      parts.push(
        <span key={cursor} className="text-muted-foreground">
          {text.slice(cursor, match.index)}
        </span>
      );
    }
    const token = match[0];
    let cls = "";
    if (/^"/.test(token)) cls = token.endsWith(":") ? "text-blue-400 font-medium" : "text-green-400";
    else if (token === "true" || token === "false") cls = "text-yellow-400";
    else if (token === "null") cls = "text-red-400";
    else cls = "text-orange-400";
    parts.push(
      <span key={match.index} className={cls}>
        {token}
      </span>
    );
    cursor = match.index + token.length;
  }
  if (cursor < text.length) {
    parts.push(
      <span key={cursor} className="text-muted-foreground">
        {text.slice(cursor)}
      </span>
    );
  }
  return <>{parts}</>;
}

export default function ACORDParserUI({ modelId, onRun, isRunning, result }: ACORDParserUIProps) {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [formType, setFormType] = useState<string>("25");
  const [lastInput, setLastInput] = useState("");
  const { toast } = useToast();
  const [editText, setEditText] = useState<string>("");
  const [editError, setEditError] = useState<string | null>(null);
  const [trainSubmitted, setTrainSubmitted] = useState(false);
  const [activeTab, setActiveTab] = useState<"json" | "fields" | "edit" | "changes" | "split">("json");

  const handleRun = () => {
    if (!file) return;
    const inputDesc = `Parse ACORD ${formType}: ${file.name}`;
    setLastInput(inputDesc);
    onRun({
      type: "acord-parser",
      file,
      fileName: file.name,
      formType,
    });
  };

  const normalizedResult = useMemo(() => {
    if (!result) return "";
    const parsed = safeJsonParse(result);
    if (!parsed.ok) return stripJsonCodeFence(result);
    try {
      return JSON.stringify(parsed.json, null, 2);
    } catch {
      return stripJsonCodeFence(result);
    }
  }, [result]);

  const originalParsed = useMemo(() => {
    if (!normalizedResult) return null;
    const parsed = safeJsonParse(normalizedResult);
    return parsed.ok ? parsed.json : null;
  }, [normalizedResult]);

  useEffect(() => {
    if (!result) return;
    // Reset edit state when a new extraction result arrives.
    setEditText(normalizedResult);
    setEditError(null);
    setTrainSubmitted(false);
    setActiveTab("json");
  }, [result, normalizedResult]);

  const editedParsed = useMemo(() => {
    if (!editText) return null;
    const parsed = safeJsonParse(editText);
    return parsed.ok ? parsed.json : null;
  }, [editText]);

  const changes = useMemo(() => {
    if (!originalParsed || !editedParsed) return [];
    return computeChanges(originalParsed, editedParsed);
  }, [originalParsed, editedParsed]);

  const currentRunId = useMemo(() => {
    if (!originalParsed || typeof originalParsed !== "object") return "";
    const r = originalParsed as Record<string, unknown>;
    const runId = r.run_id ?? (r as any).runId ?? (r as any).run?.run_id ?? (r as any).run_id?.toString?.();
    return typeof runId === "string" ? runId : "";
  }, [originalParsed]);

  const handleTrain = async () => {
    if (!normalizedResult) return;
    if (!currentRunId) {
      toast({
        title: "Run ID missing",
        description: "This extraction result does not include a run_id.",
        variant: "destructive",
      });
      return;
    }
    try {
      const editedTrim = editText.trim();
      const parsed = safeJsonParse(editedTrim || normalizedResult);
      if (!parsed.ok) {
        setEditError(parsed.error);
        toast({
          title: "Invalid JSON",
          description: parsed.error,
          variant: "destructive",
        });
        return;
      }

      const submitResp = await submitAcordRun(currentRunId, {
        thumbs_up: true,
        notes: "Submitted from ACORD Form Understanding tab via Train",
        corrected_json: parsed.json,
        require_admin_approval_for_training: true,
      });
      setTrainSubmitted(true);
      toast({
        title: "Sent to Training Admin Review Queue",
        description: `Run submitted. Status: ${submitResp?.status || "submitted"}`,
      });

      // Force fresh queue load so user can immediately see it.
      navigate("/admin/acord-queue");
    } catch (e: any) {
      const msg = e?.message ? String(e.message) : "Could not submit run to ACORD queue";
      if (/not authenticated|session expired|unauthorized/i.test(msg)) {
        toast({
          title: "Session expired",
          description: "Please sign in again, then click Train to send it to Training Review.",
          variant: "destructive",
        });
        navigate("/auth");
        return;
      }
      toast({ title: "Training submit failed", description: msg, variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Upload ACORD Form
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="form-type">ACORD Form Type</Label>
            <Select value={formType} onValueChange={setFormType}>
              <SelectTrigger>
                <SelectValue placeholder="Select form type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="25">ACORD 25 - Certificate of Insurance</SelectItem>
                <SelectItem value="27">ACORD 27 - Evidence of Property Insurance</SelectItem>
                <SelectItem value="80">ACORD 80 - Garage Coverage Summary</SelectItem>
                <SelectItem value="85">ACORD 85 - General Liability Application</SelectItem>
                <SelectItem value="90">ACORD 90 - Automobile Application</SelectItem>
                <SelectItem value="125">ACORD 125 - Commercial Insurance Application</SelectItem>
                <SelectItem value="126">ACORD 126 - Commercial General Liability</SelectItem>
                <SelectItem value="140">ACORD 140 - Property Loss Notice</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="acord-file">Upload Document</Label>
            <Input
              id="acord-file"
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <FileText className="h-4 w-4" />
                {file.name}
              </div>
            )}
          </div>

          <Button
            onClick={handleRun}
            disabled={!file || isRunning}
            className="w-full bg-gradient-primary hover:opacity-90"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Parsing...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-2" />
                Parse ACORD Form
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <Card className="bg-card border-border animate-fade-in">
          <CardHeader className="bg-gradient-to-r from-primary/5 to-transparent">
            <CardTitle className="text-card-foreground flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-primary" />
              Parsed Data
            </CardTitle>
          </CardHeader>

          <CardContent className="pt-6 space-y-4">
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
              <TabsList>
                <TabsTrigger value="json">JSON</TabsTrigger>
                <TabsTrigger value="fields">Fields</TabsTrigger>
                <TabsTrigger value="edit">Edit</TabsTrigger>
                <TabsTrigger value="changes">Changes</TabsTrigger>
                <TabsTrigger value="split">Split View</TabsTrigger>
              </TabsList>

              <TabsContent value="json" className="mt-4">
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Extracted JSON</Label>
                  <pre className="rounded-lg border border-border/70 bg-[#0b1020] p-3 overflow-auto max-h-[320px] text-xs font-mono leading-5 whitespace-pre-wrap">
                    <JsonHighlight text={normalizedResult || "{}"} />
                  </pre>
                </div>
              </TabsContent>

              <TabsContent value="fields" className="mt-4">
                {originalParsed ? (
                  <div className="space-y-4">
                    <div className="rounded-lg border bg-muted/20 p-3">
                      <Label className="text-xs text-muted-foreground">Extracted fields</Label>
                      <div className="mt-2 grid gap-2 max-h-[260px] overflow-auto pr-1">
                        {Object.entries(flattenValues(originalParsed))
                          .slice(0, 80)
                          .map(([path, value]) => (
                            <div
                              key={path}
                              className="flex items-start justify-between gap-4 rounded border border-border/60 bg-card/70 p-2"
                            >
                              <span className="text-[11px] font-mono text-muted-foreground flex-1 min-w-0 break-words">
                                {path}
                              </span>
                              <span className="text-[11px] font-mono text-foreground max-w-[45%] whitespace-pre-wrap break-words text-right">
                                {value}
                              </span>
                            </div>
                          ))}
                      </div>
                      {Object.keys(flattenValues(originalParsed)).length > 80 && (
                        <p className="text-xs text-muted-foreground mt-2">
                          Showing first 80 fields. Refine edits using Edit tab.
                        </p>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-destructive">Could not parse extracted JSON.</p>
                )}
              </TabsContent>

              <TabsContent value="edit" className="mt-4">
                {originalParsed ? (
                  <div className="space-y-3">
                    <Label className="text-xs text-muted-foreground">Edit extracted JSON</Label>
                    {editError && <p className="text-sm text-destructive">{editError}</p>}
                    <Textarea
                      value={editText}
                      onChange={(e) => {
                        const next = e.target.value;
                        setEditText(next);
                        const parsed = safeJsonParse(next);
                        setEditError(parsed.ok ? null : parsed.error);
                      }}
                      className="min-h-[260px] font-mono text-xs"
                    />
                  </div>
                ) : (
                  <p className="text-sm text-destructive">
                    Cannot edit: extracted result is not valid JSON.
                  </p>
                )}
              </TabsContent>

              <TabsContent value="changes" className="mt-4">
                {originalParsed && editedParsed ? (
                  <div className="space-y-3">
                    {changes.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No changes detected.</p>
                    ) : (
                      <>
                        <p className="text-xs text-muted-foreground">
                          Showing up to {Math.min(changes.length, 120)} changed paths.
                        </p>
                        <div className="grid gap-2 max-h-[300px] overflow-auto pr-1">
                          {changes.map((c) => (
                            <div
                              key={c.path + c.type}
                              className="rounded-lg border border-border/60 bg-card/70 p-3"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <span className="text-[11px] font-mono text-muted-foreground break-words">
                                  {c.path}
                                </span>
                                {c.type === "added" && (
                                  <Badge className="bg-green-500/15 text-green-700 border border-green-500/30">
                                    Added
                                  </Badge>
                                )}
                                {c.type === "removed" && (
                                  <Badge
                                    variant="destructive"
                                    className="bg-red-500/10 text-red-700 border border-red-500/30"
                                  >
                                    Removed
                                  </Badge>
                                )}
                                {c.type === "changed" && (
                                  <Badge className="bg-amber-500/15 text-amber-700 border border-amber-500/30">
                                    Changed
                                  </Badge>
                                )}
                              </div>
                              {c.type === "added" && (
                                <div className="mt-2 text-[11px] font-mono whitespace-pre-wrap">
                                  After: {c.after}
                                </div>
                              )}
                              {c.type === "removed" && (
                                <div className="mt-2 text-[11px] font-mono whitespace-pre-wrap">
                                  Before: {c.before}
                                </div>
                              )}
                              {c.type === "changed" && (
                                <div className="mt-2 text-[11px] font-mono whitespace-pre-wrap">
                                  Before: {c.before}
                                  <br />
                                  After: {c.after}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Enter valid JSON in Edit tab to see changes.
                  </p>
                )}
              </TabsContent>

              <TabsContent value="split" className="mt-4">
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge className="bg-green-500/15 text-green-700 border border-green-500/30">
                        Added ({changes.filter((c) => c.type === "added").length})
                      </Badge>
                      <Badge
                        variant="destructive"
                        className="bg-red-500/10 text-red-700 border border-red-500/30"
                      >
                        Removed ({changes.filter((c) => c.type === "removed").length})
                      </Badge>
                      <Badge className="bg-amber-500/15 text-amber-700 border border-amber-500/30">
                        Changed ({changes.filter((c) => c.type === "changed").length})
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Split view renders Original vs Edited side-by-side with a legend.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">Original</Label>
                      <pre className="rounded-lg border border-border/70 bg-[#0b1020] p-3 overflow-auto max-h-[420px] text-xs font-mono leading-5 whitespace-pre-wrap">
                        <JsonHighlight text={normalizedResult || "{}"} />
                      </pre>
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs text-muted-foreground">Edited</Label>
                      <pre className="rounded-lg border border-border/70 bg-[#0b1020] p-3 overflow-auto max-h-[420px] text-xs font-mono leading-5 whitespace-pre-wrap">
                        <JsonHighlight text={editText || "{}"} />
                      </pre>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-border/50">
                    {originalParsed && editedParsed ? (
                      changes.length === 0 ? (
                        <p className="text-sm text-muted-foreground">No changes detected.</p>
                      ) : (
                        <div className="space-y-3">
                          <p className="text-xs text-muted-foreground">
                            Showing up to {Math.min(changes.length, 120)} changed paths.
                          </p>
                          <div className="grid gap-2 max-h-[300px] overflow-auto pr-1">
                            {changes.map((c) => (
                              <div
                                key={c.path + c.type}
                                className="rounded-lg border border-border/60 bg-card/70 p-3"
                              >
                                <div className="flex items-center justify-between gap-3">
                                  <span className="text-[11px] font-mono text-muted-foreground break-words">
                                    {c.path}
                                  </span>
                                  {c.type === "added" && (
                                    <Badge className="bg-green-500/15 text-green-700 border border-green-500/30">
                                      Added
                                    </Badge>
                                  )}
                                  {c.type === "removed" && (
                                    <Badge
                                      variant="destructive"
                                      className="bg-red-500/10 text-red-700 border border-red-500/30"
                                    >
                                      Removed
                                    </Badge>
                                  )}
                                  {c.type === "changed" && (
                                    <Badge className="bg-amber-500/15 text-amber-700 border border-amber-500/30">
                                      Changed
                                    </Badge>
                                  )}
                                </div>
                                {c.type === "added" && (
                                  <div className="mt-2 text-[11px] font-mono whitespace-pre-wrap">
                                    After: {c.after}
                                  </div>
                                )}
                                {c.type === "removed" && (
                                  <div className="mt-2 text-[11px] font-mono whitespace-pre-wrap">
                                    Before: {c.before}
                                  </div>
                                )}
                                {c.type === "changed" && (
                                  <div className="mt-2 text-[11px] font-mono whitespace-pre-wrap">
                                    Before: {c.before}
                                    <br />
                                    After: {c.after}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        Enter valid JSON in Edit tab to see split-view changes.
                      </p>
                    )}
                  </div>
                </div>
              </TabsContent>
            </Tabs>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/50">
              <Button
                variant="outline"
                disabled={isRunning || trainSubmitted}
                onClick={() => {
                  setEditText(normalizedResult);
                  setEditError(null);
                  setActiveTab("json");
                }}
              >
                Reset
              </Button>
              <Button
                disabled={isRunning || trainSubmitted}
                className="bg-gradient-primary hover:opacity-90"
                onClick={handleTrain}
              >
                Train
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
