import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Upload, FileText, Loader2, FileCheck, CheckCircle2, AlertCircle, RefreshCw, Scan, FileDigit } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/hooks/use-toast";
import { submitAcordRun } from "@/lib/acordWorkflowApi";
import {
  smartExtractPdf,
  triggerFullExtraction,
  submitRunpodForTraining,
  type AcordExtractionResult,
} from "@/lib/pdfUploadApi";
import {
  createAcordRun,
  saveAcordFeedback,
} from "@/lib/acordSupabaseApi";
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
    input.forEach((v: any, i: any) => {
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

// Unified processing pipeline state
type ProcessingPhase =
  | "idle"
  | "processing"         // smart-extract in flight (detect + digital Claude OR detect + RunPod upload)
  | "extracting_scanned" // RunPod Surya+Qwen running (scanned path only)
  | "done"
  | "failed";

type ExtractionState =
  | { phase: "idle" }
  | { phase: "extracting" }
  | { phase: "completed"; result: AcordExtractionResult }
  | { phase: "failed"; message: string };

function serializeFieldValue(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v)) {
    return v
      .map((item) =>
        item === null || item === undefined
          ? ""
          : typeof item === "object"
          ? JSON.stringify(item)
          : String(item)
      )
      .filter(Boolean)
      .join(", ");
  }
  if (typeof v === "object") {
    if ("value" in (v as any)) return String((v as any).value ?? "");
    return JSON.stringify(v);
  }
  return String(v);
}

function flattenAcordFields(result: AcordExtractionResult): Array<{ key: string; value: string }> {
  const raw = result.extracted_json ?? result.extracted_fields ?? result.fields ?? {};
  return Object.entries(raw)
    .map(([key, v]) => {
      if (v === null || v === undefined) return null;
      const val = serializeFieldValue(v);
      return val !== null && val !== undefined ? { key, value: val } : null;
    })
    .filter(Boolean) as Array<{ key: string; value: string }>;
}

function fieldsToMarkdown(
  fields: Array<{ key: string; value: string }>,
  formType: string,
  pdfType: string,
): string {
  const formLabel = formType.replace(/^acord/i, "");
  const pdfLabel = pdfType === "scanned" ? "Scanned PDF" : pdfType === "digital" ? "Digital PDF" : pdfType || "Unknown";
  const rows = fields.map(
    (f) => `| ${f.key.replace(/\|/g, "\\|")} | ${String(f.value).replace(/\|/g, "\\|")} |`
  );
  return [
    `## ACORD ${formLabel} — Extracted Fields`,
    ``,
    `**PDF Type:** ${pdfLabel}  `,
    `**Total Fields:** ${fields.length}`,
    ``,
    `| Field | Value |`,
    `|-------|-------|`,
    ...rows,
  ].join("\n");
}

function parseMarkdownTableToJson(markdown: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of markdown.split("\n")) {
    if (!line.trimStart().startsWith("|")) continue;
    const cells = line.split("|").map((c) => c.trim()).filter(Boolean);
    if (cells.length < 2) continue;
    const [key, value] = cells;
    if (!key || key === "Field" || /^-+$/.test(key)) continue;
    result[key.replace(/\\\|/g, "|")] = (value ?? "").replace(/\\\|/g, "|");
  }
  return result;
}

/** snake_case / camelCase → Title Case label */
function toLabel(key: string): string {
  return key
    .replace(/([A-Z])/g, " $1")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/**
 * Build display sections purely from the extracted JSON — no hardcoded fields.
 * - Top-level plain objects   → one section with flattened field rows
 * - Top-level arrays of objects → one numbered section per item
 * - Top-level arrays of primitives / primitives → flat field row
 * - Null / empty / "_"-prefixed keys are skipped everywhere
 */
function buildDynamicSections(extracted: any): {
  flatFields: Array<{ key: string; label: string; value: string }>;
  sections: Array<{ key: string; title: string; fields: Array<{ key: string; label: string; value: string }> }>;
} {
  const flatFields: Array<{ key: string; label: string; value: string }> = [];
  const sections: Array<{ key: string; title: string; fields: Array<{ key: string; label: string; value: string }> }> = [];

  if (!extracted || typeof extracted !== "object") return { flatFields, sections };

  // Recursively collect {label, value} rows from a plain object, flattening one level of nesting
  function collectFields(obj: Record<string, any>): Array<{ key: string; label: string; value: string }> {
    const rows: Array<{ key: string; label: string; value: string }> = [];
    for (const [k, v] of Object.entries(obj)) {
      if (k.startsWith("_") || v === null || v === undefined) continue;
      if (typeof v === "object" && !Array.isArray(v)) {
        // Nested object → flatten one level with "Parent - Child" label
        for (const [nk, nv] of Object.entries(v as Record<string, any>)) {
          if (nk.startsWith("_") || nv === null || nv === undefined) continue;
          const s = typeof nv === "object" ? JSON.stringify(nv) : String(nv).trim();
          if (s) rows.push({ key: `${k}.${nk}`, label: `${toLabel(k)} - ${toLabel(nk)}`, value: s });
        }
      } else if (Array.isArray(v)) {
        // Array of primitives → join; array of objects → stringify (handled at top level if needed)
        const s = v.every(item => typeof item !== "object" || item === null)
          ? v.filter(item => item !== null && item !== undefined).map(String).join(", ")
          : JSON.stringify(v);
        if (s && s.trim()) rows.push({ key: k, label: toLabel(k), value: s });
      } else {
        const s = String(v).trim();
        if (s) rows.push({ key: k, label: toLabel(k), value: s });
      }
    }
    return rows;
  }

  for (const [key, value] of Object.entries(extracted)) {
    if (key.startsWith("_") || value === null || value === undefined) continue;

    if (Array.isArray(value)) {
      if (value.length === 0) continue;
      const allPrimitive = value.every(item => typeof item !== "object" || item === null);
      if (allPrimitive) {
        // Simple array → single flat field
        const s = value.filter(item => item !== null && item !== undefined).map(String).join(", ");
        if (s.trim()) flatFields.push({ key, label: toLabel(key), value: s });
      } else {
        // Array of objects → one numbered section per item
        value.forEach((item, idx) => {
          if (!item || typeof item !== "object" || Array.isArray(item)) return;
          const fields = collectFields(item as Record<string, any>);
          if (fields.length) sections.push({ key: `${key}_${idx}`, title: `${toLabel(key)} ${idx + 1}`, fields });
        });
      }
    } else if (typeof value === "object") {
      // Plain object → single section
      const fields = collectFields(value as Record<string, any>);
      if (fields.length) sections.push({ key, title: toLabel(key), fields });
    } else {
      // Primitive → flat field
      const s = String(value).trim();
      if (s) flatFields.push({ key, label: toLabel(key), value: s });
    }
  }

  return { flatFields, sections };
}

function computeConfidenceLabel(extracted: any): string | null {
  if (!extracted || typeof extracted !== "object") return null;
  const { flatFields, sections } = buildDynamicSections(extracted);
  const total = flatFields.length + sections.reduce((s, sec) => s + sec.fields.length, 0);
  if (!total) return null;
  // Confidence based on how many fields were extracted vs a reasonable baseline (30 fields = 100%)
  const baseline = 30;
  const score = Math.min(Math.round((total / baseline) * 100), 100);
  const level = score >= 75 ? "High" : score >= 40 ? "Medium" : "Low";
  return `${level} ${score}%`;
}

export default function ACORDParserUI({ modelId: _modelId, onRun: _onRun, isRunning, result }: ACORDParserUIProps) {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [formType, setFormType] = useState<string>("25");
  const { toast } = useToast();
  const [editText, setEditText] = useState<string>("");
  const [editError, setEditError] = useState<string | null>(null);
  const [trainSubmitted, setTrainSubmitted] = useState(false);
  const [activeTab, setActiveTab] = useState<"json" | "fields" | "edit" | "changes" | "split">("json");
  const [ocrTab, setOcrTab] = useState<"json" | "fields" | "changes" | "rawtext">("fields");
  const [markdownEditText, setMarkdownEditText] = useState<string>("");
  const [trainSubmittedRunpod, setTrainSubmittedRunpod] = useState(false);
  const [isSubmittingTrain, setIsSubmittingTrain] = useState(false);
  const [fieldEdits, setFieldEdits] = useState<Record<string, string>>({});

  // Unified pipeline state
  const [processingPhase, setProcessingPhase] = useState<ProcessingPhase>("idle");
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [detectedPdfType, setDetectedPdfType] = useState<"digital" | "scanned" | null>(null);
  // upload_id is only set for scanned PDFs (needed for RunPod training sync)
  const [scannedUploadId, setScannedUploadId] = useState<string | null>(null);
  // Supabase acord_extraction_runs.id — set after createAcordRun succeeds
  const [runId, setRunId] = useState<string | null>(null);

  // Full extraction state (result store)
  const [extractionState, setExtractionState] = useState<ExtractionState>({ phase: "idle" });

  // Reset all state when a new file is selected
  useEffect(() => {
    setProcessingPhase("idle");
    setProcessingError(null);
    setDetectedPdfType(null);
    setScannedUploadId(null);
    setRunId(null);
    setExtractionState({ phase: "idle" });
    setTrainSubmittedRunpod(false);
    setMarkdownEditText("");
    setFieldEdits({});
    setOcrTab("fields");

  }, [file]);

  // Single entry point — handles detect → digital(Claude) or scanned(RunPod) automatically
  const handleProcess = async () => {
    if (!file) return;
    setProcessingPhase("processing");
    setProcessingError(null);
    setDetectedPdfType(null);
    setScannedUploadId(null);
    setRunId(null);
    setExtractionState({ phase: "idle" });
    setTrainSubmittedRunpod(false);
    setMarkdownEditText("");

    try {
      const smartResult = await smartExtractPdf(file, formType);
      setDetectedPdfType(smartResult.pdf_type);

      // ── Unified path: both digital and scanned are uploaded, then extracted on RunPod ──
      const uploadId = smartResult.upload_id;
      setScannedUploadId(uploadId);
      setProcessingPhase("extracting_scanned");
      setExtractionState({ phase: "extracting" });

      toast({
        title: `${smartResult.pdf_type === "digital" ? "Digital" : "Scanned"} PDF detected`,
        description: "PDF uploaded to RunPod — running OCR + field extraction…",
      });

      const result = await triggerFullExtraction(uploadId, formType);
      setExtractionState({ phase: "completed", result });
      const fields = flattenAcordFields(result);
      setMarkdownEditText(fieldsToMarkdown(fields, result.form_type_detected || formType, result.pdf_type || smartResult.pdf_type));
      // Seed inline field editor with all extracted values
      const extractedObj = result.extracted_json ?? result.extracted_fields ?? result.fields ?? {};
      const { flatFields: initFlat, sections: initSections } = buildDynamicSections(extractedObj);
      const initEdits: Record<string, string> = {};
      initFlat.forEach((f) => { initEdits[f.key] = f.value; });
      initSections.forEach((sec) => sec.fields.forEach((f) => { initEdits[`${sec.key}.${f.key}`] = f.value; }));
      setFieldEdits(initEdits);
      setProcessingPhase("done");
      const fieldCount = Object.keys(
        result.extracted_json ?? result.extracted_fields ?? result.fields ?? {}
      ).length;

      // Persist run to Supabase — non-blocking
      createAcordRun({
        source_filename: file.name,
        source_mime: file.type || "application/pdf",
        form_type_detected: result.form_type_detected || formType,
        raw_text: result.full_text ?? result.raw_text ?? "",
        extracted_json: result.extracted_json ?? result.extracted_fields ?? result.fields ?? {},
      })
        .then((id) => setRunId(id))
        .catch((err: any) => {
          const msg: string = err?.message || String(err) || "Unknown error";
          const isAuthErr = /not authenticated|session expired|unauthorized|jwt/i.test(msg);
          console.error("[ACORD] createAcordRun failed:", msg);
          toast({
            title: "Warning: run not saved",
            description: isAuthErr
              ? "Your session expired during extraction. Please sign in again — the extraction results are still visible above."
              : `Could not save to database: ${msg}. Save & Train will be unavailable.`,
            variant: "destructive",
          });
        });

      toast({
        title: `${smartResult.pdf_type === "digital" ? "Digital" : "Scanned"} PDF extracted`,
        description: `${fieldCount} field(s) extracted via RunPod`,
      });
    } catch (e: any) {
      const msg = e?.message || "Processing failed";
      setProcessingError(msg);
      setProcessingPhase("failed");
      setExtractionState({ phase: "failed", message: msg });
      toast({ title: "Extraction failed", description: msg, variant: "destructive" });
    }
  };

  const handleSubmitAndTrain = async (overrideCorrectedFields?: Record<string, string>) => {
    if (extractionState.phase !== "completed") return;
    if (!runId) {
      toast({
        title: "Cannot save",
        description: "Run was not persisted to database. Re-process the PDF and try again.",
        variant: "destructive",
      });
      return;
    }

    const r = extractionState.result;
    const originalFields = (r.extracted_json ?? r.extracted_fields ?? r.fields ?? {}) as Record<string, any>;
    const rawText = r.full_text ?? r.raw_text ?? "";
    const correctedFields = overrideCorrectedFields ?? parseMarkdownTableToJson(markdownEditText);

    setIsSubmittingTrain(true);
    try {
      // 1. Save correction to Supabase (acord_extraction_feedback + run status → submitted)
      await saveAcordFeedback(runId, correctedFields);

      // 2. For scanned PDFs: also sync to RunPod pod filesystem (non-blocking)
      //    Digital PDFs have no upload_id — skipped. RunPod will get data at Fine-tune time
      //    via getAcordTrainingSamples() → syncFeedbacksToRunpod().
      if (scannedUploadId) {
        submitRunpodForTraining(scannedUploadId, originalFields, correctedFields, rawText, formType).catch(() => {});
      }

      setTrainSubmittedRunpod(true);
      toast({
        title: "Training sample saved",
        description: "Saved to database. Go to Model Training → Local Training to fine-tune.",
      });
    } catch (e: any) {
      toast({ title: "Training submission failed", description: e?.message || "Unknown error", variant: "destructive" });
    } finally {
      setIsSubmittingTrain(false);
    }
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
    const extracted = r.run_id ?? (r as any).runId ?? (r as any).run?.run_id ?? (r as any).run_id?.toString?.();
    return typeof extracted === "string" ? extracted : "";
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

          {/* ── Process PDF (auto-detects digital vs scanned) ──────────── */}
          <div className="border-t border-border/50 pt-4 space-y-3">

            {/* PDF type badge — shown once type is detected */}
            {detectedPdfType && (
              <div className="flex items-center gap-2 p-2.5 rounded-md border bg-muted/20">
                {detectedPdfType === "digital" ? (
                  <>
                    <FileDigit className="h-4 w-4 text-blue-400 shrink-0" />
                    <div>
                      <span className="text-xs font-semibold text-blue-400">Digital PDF</span>
                      <p className="text-[11px] text-muted-foreground leading-tight">
                        Uploaded to RunPod · extracted on RunPod pipeline
                      </p>
                    </div>
                    <Badge className="ml-auto shrink-0 bg-blue-500/15 text-blue-400 border-blue-500/30">RunPod</Badge>
                  </>
                ) : (
                  <>
                    <Scan className="h-4 w-4 text-orange-400 shrink-0" />
                    <div>
                      <span className="text-xs font-semibold text-orange-400">Scanned PDF</span>
                      <p className="text-[11px] text-muted-foreground leading-tight">
                        Uploaded to RunPod · Surya OCR + Qwen VL extraction
                      </p>
                    </div>
                    <Badge className="ml-auto shrink-0 bg-orange-500/15 text-orange-400 border-orange-500/30">RunPod GPU</Badge>
                  </>
                )}
              </div>
            )}

            {/* Status badge */}
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium text-muted-foreground">Extract ACORD Fields</Label>
              {(processingPhase === "processing" || processingPhase === "extracting_scanned") && (
                <Badge variant="outline" className="border-yellow-500 text-yellow-400">
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  {processingPhase === "extracting_scanned" ? "Running OCR…" : "Processing…"}
                </Badge>
              )}
              {processingPhase === "done" && (
                <Badge variant="outline" className="border-green-500 text-green-400">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  Completed
                </Badge>
              )}
              {processingPhase === "failed" && (
                <Badge variant="outline" className="border-red-500 text-red-400">
                  <AlertCircle className="h-3 w-3 mr-1" />
                  Failed
                </Badge>
              )}
            </div>

            {/* Single action button */}
            <Button
              onClick={handleProcess}
              disabled={!file || processingPhase === "processing" || processingPhase === "extracting_scanned"}
              className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:opacity-90 text-white"
            >
              {processingPhase === "processing" ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {detectedPdfType ? "Uploading to RunPod…" : "Detecting PDF type…"}
                </>
              ) : processingPhase === "extracting_scanned" ? (
                <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Running OCR + Extraction on RunPod…</>
              ) : processingPhase === "done" ? (
                <><RefreshCw className="h-4 w-4 mr-2" />Re-process PDF</>
              ) : (
                <><Upload className="h-4 w-4 mr-2" />Process PDF — Extract ACORD Fields</>
              )}
            </Button>

            {/* RunPod progress indicator */}
            {processingPhase === "extracting_scanned" && (
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center gap-2 text-yellow-400">
                  <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
                  RunPod extraction in progress...
                </div>
              </div>
            )}

            {processingPhase === "failed" && processingError && (
              <p className="text-xs text-red-400">{processingError}</p>
            )}
          </div>
          {/* ── end process section ────────────────────────────────────── */}
        </CardContent>
      </Card>

      {/* ── Extracted Fields Card ────────────────────────────────────── */}
      {extractionState.phase === "completed" && (() => {
        const r = extractionState.result;
        const formTypeDetected = r.form_type_detected || formType;
        const pdfType = r.pdf_type || "";
        const nlSummary = r.natural_language_summary || null;
        const extractedJson = r.extracted_json ?? r.extracted_fields ?? r.fields ?? {};
        const confidenceLabel = computeConfidenceLabel(extractedJson);
        const formTypeLabel = `ACORD ${String(formTypeDetected).replace(/^acord\s*/i, "").toUpperCase()}`;

        return (
          <Card className="bg-card border-border animate-fade-in">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <CardTitle className="text-card-foreground flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  Extracted Fields
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="border-violet-500 text-violet-400 text-xs font-semibold">
                    {formTypeLabel}
                  </Badge>
                  {pdfType && (
                    <Badge variant="outline" className="border-blue-500/60 text-blue-400 text-xs">
                      {pdfType === "scanned" ? "Scanned" : pdfType === "digital" ? "Digital" : pdfType}
                    </Badge>
                  )}
                  {confidenceLabel && (() => {
                    const level = confidenceLabel.split(" ")[0];
                    const cls =
                      level === "High" ? "bg-green-500/15 text-green-700 border-green-500/30" :
                      level === "Medium" ? "bg-amber-500/15 text-amber-800 border-amber-500/30" :
                      "bg-red-500/15 text-red-700 border-red-500/30";
                    return (
                      <Badge className={`text-xs font-semibold border ${cls}`}>
                        {confidenceLabel}
                      </Badge>
                    );
                  })()}
                </div>
              </div>
            </CardHeader>

            <CardContent className="pt-2 space-y-4">
              {/* Natural Language Summary */}
              <div className={`rounded-lg border p-4 space-y-2 ${nlSummary ? "border-violet-500/30 bg-violet-500/5" : "border-border/60 bg-muted/30"}`}>
                <div className="flex items-center gap-2 mb-1">
                  <FileText className={`h-4 w-4 shrink-0 ${nlSummary ? "text-violet-400" : "text-muted-foreground"}`} />
                  <span className={`text-sm font-semibold ${nlSummary ? "text-violet-300" : "text-foreground"}`}>
                    Document Summary
                  </span>
                  <Badge
                    variant="outline"
                    className={`ml-auto text-[10px] ${nlSummary ? "border-violet-500/50 text-violet-400" : "border-border text-muted-foreground"}`}
                  >
                    {nlSummary ? "AI Generated" : "SLM Unavailable"}
                  </Badge>
                </div>
                {nlSummary ? (
                  <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-line">{nlSummary}</p>
                ) : (
                  <div className="space-y-1.5">
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      A natural language narrative of this document is currently unavailable. The language model (SLM) is not active or the RunPod endpoint is unreachable.
                    </p>
                    <p className="text-xs text-muted-foreground/70">
                      To enable: set <code className="bg-muted px-1 py-0.5 rounded text-xs">ACORD_NL_SUMMARY_ENABLED=true</code> in the backend and ensure the RunPod endpoint is running.
                    </p>
                  </div>
                )}
              </div>

              {/* Tabs */}
              <Tabs value={ocrTab} onValueChange={(v) => setOcrTab(v as "json" | "fields" | "changes" | "rawtext" | "markdown")}>
                <TabsList>
                  <TabsTrigger value="json">
                    <span className="mr-1.5 text-[10px] font-mono font-bold">{"{}"}</span>JSON
                  </TabsTrigger>
                  <TabsTrigger value="fields">
                    <FileCheck className="h-3.5 w-3.5 mr-1.5" />Fields
                  </TabsTrigger>
                  <TabsTrigger value="rawtext">Raw Text</TabsTrigger>
                  <TabsTrigger value="changes">
                    <RefreshCw className="h-3.5 w-3.5 mr-1.5" />Changes
                  </TabsTrigger>
                </TabsList>

                {/* JSON Tab */}
                <TabsContent value="json" className="mt-3">
                  <pre className="rounded-lg border border-border/70 bg-[#0b1020] p-3 overflow-auto max-h-[380px] text-xs font-mono leading-5 whitespace-pre-wrap text-muted-foreground">
                    {JSON.stringify(extractedJson, null, 2) || "(no data)"}
                  </pre>
                </TabsContent>

                {/* Fields Tab — dynamic, inline-editable fields */}
                <TabsContent value="fields" className="mt-3">
                  {(() => {
                    const { flatFields, sections: dynSections } = buildDynamicSections(extractedJson);
                    const hasAny = flatFields.length > 0 || dynSections.length > 0;
                    if (!hasAny) {
                      return <p className="text-xs text-muted-foreground italic">No fields extracted. Check the JSON tab for raw output.</p>;
                    }
                    return (
                      <div className="space-y-4">
                        <div className="space-y-6 max-h-[520px] overflow-y-auto pr-1">
                          {/* Flat top-level fields */}
                          {flatFields.length > 0 && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              {flatFields.map((f) => (
                                <div key={f.key} className="space-y-1">
                                  <p className="text-xs text-muted-foreground">{f.label}</p>
                                  <Input
                                    value={fieldEdits[f.key] ?? f.value}
                                    onChange={(e) => {
                                      setFieldEdits((prev) => ({ ...prev, [f.key]: e.target.value }));
                                      setTrainSubmittedRunpod(false);
                                    }}
                                    className="h-9 text-sm bg-background"
                                  />
                                </div>
                              ))}
                            </div>
                          )}
                          {/* Nested object sections */}
                          {dynSections.map((section) => (
                            <div key={section.key}>
                              <div className="flex items-center gap-2 mb-3">
                                <span className="h-2.5 w-2.5 rounded-full bg-green-500 shrink-0" />
                                <span className="text-sm font-semibold text-foreground">{section.title}</span>
                              </div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                {section.fields.map((f) => {
                                  const editKey = `${section.key}.${f.key}`;
                                  return (
                                    <div key={f.key} className="space-y-1">
                                      <p className="text-xs text-muted-foreground">{f.label}</p>
                                      <Input
                                        value={fieldEdits[editKey] ?? f.value}
                                        onChange={(e) => {
                                          setFieldEdits((prev) => ({ ...prev, [editKey]: e.target.value }));
                                          setTrainSubmittedRunpod(false);
                                        }}
                                        className="h-9 text-sm bg-background"
                                      />
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          ))}
                        </div>
                        {/* Save & Train */}
                        <div className="flex items-center justify-between gap-3 pt-2 border-t border-border/50">
                          <p className="text-xs text-muted-foreground">
                            Correct any wrong values above, then save to add a training sample.
                          </p>
                          <Button
                            onClick={async () => {
                              await handleSubmitAndTrain(fieldEdits);
                              setTimeout(() => setTrainSubmittedRunpod(false), 2000);
                            }}
                            disabled={isSubmittingTrain}
                            className="shrink-0 bg-gradient-to-r from-green-600 to-emerald-600 hover:opacity-90 text-white"
                          >
                            {isSubmittingTrain ? (
                              <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving…</>
                            ) : trainSubmittedRunpod ? (
                              <><CheckCircle2 className="h-4 w-4 mr-2" />Saved!</>
                            ) : (
                              <><FileCheck className="h-4 w-4 mr-2" />Save &amp; Train</>
                            )}
                          </Button>
                        </div>
                      </div>
                    );
                  })()}
                </TabsContent>

                {/* Raw Text Tab */}
                <TabsContent value="rawtext" className="mt-3">
                  <pre className="rounded-lg border border-border/70 bg-[#0b1020] p-3 overflow-auto max-h-[480px] text-xs font-mono leading-5 whitespace-pre-wrap text-muted-foreground">
                    {(r.full_text || r.raw_text || "").trim() || "(no raw text available)"}
                  </pre>
                </TabsContent>

                {/* Changes Tab — edit & submit for training */}
                <TabsContent value="changes" className="mt-3 space-y-3">
                  <p className="text-xs text-muted-foreground">
                    Edit the fields below — correct any wrong values — then click <strong>Save &amp; Train</strong>.
                  </p>
                  <Textarea
                    value={markdownEditText}
                    onChange={(e) => { setMarkdownEditText(e.target.value); setTrainSubmittedRunpod(false); }}
                    className="min-h-[340px] font-mono text-xs bg-[#0b1020] border-border/70 text-muted-foreground resize-y leading-5"
                    spellCheck={false}
                  />
                  <div className="flex items-center justify-between gap-3 pt-1">
                    <p className="text-xs text-muted-foreground">
                      Each save adds one sample to <strong>Model Training → Local Training</strong>.
                    </p>
                    <Button
                      onClick={async () => {
                        await handleSubmitAndTrain();
                        setTimeout(() => setTrainSubmittedRunpod(false), 2000);
                      }}
                      disabled={isSubmittingTrain}
                      className="shrink-0 bg-gradient-to-r from-green-600 to-emerald-600 hover:opacity-90 text-white"
                    >
                      {isSubmittingTrain ? (
                        <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving…</>
                      ) : trainSubmittedRunpod ? (
                        <><CheckCircle2 className="h-4 w-4 mr-2" />Saved!</>
                      ) : (
                        <><FileCheck className="h-4 w-4 mr-2" />Save &amp; Train</>
                      )}
                    </Button>
                  </div>
                </TabsContent>
              </Tabs>

              <div className="flex items-center justify-start pt-3 border-t border-border/50">
                <Button
                  variant="outline"
                  className="shrink-0 text-muted-foreground"
                  onClick={() => toast({ title: "Send to Review", description: "Review workflow coming soon." })}
                >
                  Send to Review
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })()}

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
                          {changes.map((c: any) => (
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
                        Added ({changes.filter((c: any) => c.type === "added").length})
                      </Badge>
                      <Badge
                        variant="destructive"
                        className="bg-red-500/10 text-red-700 border border-red-500/30"
                      >
                        Removed ({changes.filter((c: any) => c.type === "removed").length})
                      </Badge>
                      <Badge className="bg-amber-500/15 text-amber-700 border border-amber-500/30">
                        Changed ({changes.filter((c: any) => c.type === "changed").length})
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
                            {changes.map((c: any) => (
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
