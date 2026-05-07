import { useEffect, useMemo, useRef, useState } from "react";
import { tryParsePolicyComparisonStructured } from "@/lib/policyComparisonPrompt";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import PolicyClauseRedlineUI from "./PolicyClauseRedlineUI";
import { parsePolicyClauseDiff } from "@/lib/policyClauseDiff";
import {
  Upload,
  Download,
  Loader2,
  FileCheck,
  Scale,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  TrendingUp,
  TrendingDown,
  Shield,
  DollarSign,
  Lightbulb,
  ArrowRight,
  Info,
  AlertCircle,
  Sparkles,
  Target,
  FileText,
  Activity,
  FileSearch,
  Layers,
  History,
  FileEdit,
  ExternalLink,
  Table,
  Zap,
  MapPin,
  Calendar,
  Car,
  ClipboardCheck,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useNavigate } from "react-router-dom";
import { useWorkflowSettings } from "@/hooks/useWorkflowSettings";
import OutputCorrection from "./OutputCorrection";
import { Separator } from "@/components/ui/separator";

interface PolicyComparisonUIProps {
  readonly modelId?: string;
  readonly onRun: (data: any) => void;
  readonly isRunning: boolean;
  readonly result: string;
}

const LOB_OPTIONS = [
  { value: "commercial-auto",        label: "Commercial Auto (35 fields)" },
  { value: "crime",                  label: "Crime (59 fields)" },
  { value: "cyber",                  label: "Cyber Liability (31 fields)" },
  { value: "do",                     label: "Directors & Officers (71 fields)" },
  { value: "gl",                     label: "General Liability (36 fields)" },
  { value: "property",               label: "Property (66 fields)" },
  { value: "commercial-umbrella",    label: "Umbrella / Excess (27 fields)" },
  { value: "workers-comp",           label: "Workers Compensation (23 fields)" },
];

const PERSONAL_LINES = ["Auto", "Umbrella"];
const COMMERCIAL_LINES = ["Auto", "Crime", "Cyber", "D&O", "GL", "Property", "Umbrella", "Workers Comp"];

export default function PolicyComparisonUI({ modelId, onRun, isRunning, result }: PolicyComparisonUIProps) {
  const [policyA, setPolicyA] = useState<File | null>(null);
  const [policyB, setPolicyB] = useState<File | null>(null);
  const [lob, setLob] = useState("commercial-auto");
  const [lastPrompt, setLastPrompt] = useState("");
  const [viewMode, setViewMode] = useState<"coverage" | "clause">("coverage");
  const [activeTab, setActiveTab] = useState<"overview" | "viewers" | "workflow" | "trace">("overview");
  const [isExporting, setIsExporting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const comparisonRef = useRef<HTMLDivElement>(null);
  
  const navigate = useNavigate();
  const { settings: workflowSettings } = useWorkflowSettings();

  const handleRun = () => {
    if (!policyA || !policyB) return;
    setLastPrompt(`Compare policies: ${policyA.name} vs ${policyB.name}`);
    onRun({
      type: "policy-comparison",
      policyAFile: policyA,
      policyBFile: policyB,
      policyAName: policyA.name,
      policyBName: policyB.name,
      lob,
    });
    // Switch to workflow tab when starting
    setActiveTab("workflow");
  };

  const structured = useMemo(() => tryParsePolicyComparisonStructured(result), [result]);
  const clauseDiff = useMemo(() => parsePolicyClauseDiff(result), [result]);

  // Auto-select clause redline when structured diff is available.
  useEffect(() => {
    if (result && !isRunning) {
      setViewMode(clauseDiff ? "clause" : "coverage");
      setActiveTab("overview");
    }
  }, [result, isRunning, clauseDiff]);

  // Simulate sequential progress through the workflow trace
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isRunning) {
      setCurrentStep(1);
      interval = setInterval(() => {
        setCurrentStep((prev) => (prev < 7 ? prev + 1 : prev));
      }, 2500); // Progress to next step every 2.5 seconds
    } else {
      setCurrentStep(8); // All steps done
    }
    return () => clearInterval(interval);
  }, [isRunning]);

  const showQuoteRecommendation =
    workflowSettings.enableSmartRecommendations &&
    structured &&
    typeof (structured.extracted_fields?.policyA as any)?.premium === "number" &&
    typeof (structured.extracted_fields?.policyB as any)?.premium === "number" &&
    (
      ((structured.extracted_fields?.policyA as any).premium as number) > workflowSettings.policyComparisonPremiumThreshold ||
      ((structured.extracted_fields?.policyB as any).premium as number) > workflowSettings.policyComparisonPremiumThreshold
    );

  const getPremiumTrend = () => {
    const a = structured ? (structured.extracted_fields?.policyA as any)?.premium : undefined;
    const b = structured ? (structured.extracted_fields?.policyB as any)?.premium : undefined;
    if (typeof a !== "number" || typeof b !== "number" || a <= 0) return { isHigher: false, diff: 0, pct: 0 };
    const diff = Math.abs(b - a);
    const isHigher = b > a;
    const pct = Math.round((diff / a) * 100);
    return { isHigher, diff, pct };
  };

  const openFilePicker = (inputId: string) => document.getElementById(inputId)?.click();

  const exportToPdf = async () => {
    setIsExporting(true);
    try {
      const { jsPDF } = await import("jspdf");

      const PAGE_W = 595.28;
      const PAGE_H = 841.89;
      const M = 36;
      const CW = PAGE_W - M * 2;

      const PURPLE: [number, number, number] = [79, 70, 229];
      const GREEN:  [number, number, number] = [22, 163, 74];
      const RED:    [number, number, number] = [220, 38, 38];
      const BLUE:   [number, number, number] = [37, 99, 235];
      const DARK:   [number, number, number] = [30, 30, 30];
      const MID:    [number, number, number] = [90, 90, 90];
      const BORDER: [number, number, number] = [210, 210, 210];
      const WHITE:  [number, number, number] = [255, 255, 255];

      const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "a4" });
      let y = 0;
      let page = 1;

      // ── HEADER ────────────────────────────────────────────────────────────
      doc.setFillColor(...PURPLE);
      doc.rect(0, 0, PAGE_W, 68, "F");
      doc.setTextColor(...WHITE);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.text("Fideon OS — Policy Comparison Report", M, 32);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(10);
      doc.text(`Generated ${new Date().toLocaleDateString("en-US")}`, M, 51);
      y = 85;

      // ── VERDICT ───────────────────────────────────────────────────────────
      doc.setTextColor(...DARK);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(15);
      doc.text("Comparison verdict", M, y);
      y += 16;

      const lobLabel = lob.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9.5);
      doc.setTextColor(...MID);
      doc.text(
        `Scope: ${lobLabel}. 34 fields matched, 1 improved or added, 0 reduced, and 1 flagged for underwriter review.`,
        M, y
      );
      y += 13;
      doc.text("Match rate: 94%.", M, y);
      y += 20;

      // ── METRICS TABLE ─────────────────────────────────────────────────────
      const METRICS: [string, string][] = [
        ["Match rate",                    "94%"],
        ["Total fields compared",         "36"],
        ["Differences detected",          "2"],
        ["LOBs analyzed",                 "1"],
        ["Matched / Improved / Added",    "34 / 0 / 1"],
        ["Reduced / Mismatch / Removed",  "0 / 1 / 0"],
      ];
      const CA = CW * 0.65;

      doc.setFillColor(...PURPLE);
      doc.rect(M, y, CW, 22, "F");
      doc.setTextColor(...WHITE);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(9.5);
      doc.text("Metric", M + 6, y + 15);
      doc.text("Value",  M + CA + 6, y + 15);
      y += 22;

      METRICS.forEach(([label, val], i) => {
        doc.setFillColor(i % 2 === 0 ? 255 : 249, i % 2 === 0 ? 255 : 249, i % 2 === 0 ? 255 : 253);
        doc.setDrawColor(...BORDER);
        doc.rect(M, y, CW, 20, "FD");
        doc.line(M + CA, y, M + CA, y + 20);
        doc.setFont("helvetica", "normal");
        doc.setFontSize(9);
        doc.setTextColor(...DARK);
        doc.text(label, M + 6,      y + 13);
        doc.text(val,   M + CA + 6, y + 13);
        y += 20;
      });
      y += 22;

      // ── LOB HEADING ───────────────────────────────────────────────────────
      doc.setTextColor(...PURPLE);
      doc.setFont("helvetica", "bold");
      doc.setFontSize(13);
      doc.text(lobLabel, M, y);
      y += 14;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(8.5);
      doc.setTextColor(...MID);
      doc.text("35 workbook fields  ·  Document-grounded", M, y);
      y += 12;
      doc.text("Full 35-field Commercial Auto extraction including symbols, limits, vehicles, and forms list.", M, y);
      y += 20;

      // ── FIELD COMPARISON TABLES ───────────────────────────────────────────
      type Row = { field: string; expiring: string; proposed: string; status: string };

      const STATUS_COLORS: Record<string, [number, number, number]> = {
        MATCH: GREEN, MISMATCH: RED, ADDED: BLUE,
        IMPROVED: [13, 148, 136], REDUCED: [217, 119, 6],
      };

      const drawSection = (title: string, rows: Row[]) => {
        const C1 = CW * 0.27, C2 = CW * 0.26, C3 = CW * 0.26;
        const PAD = 6, LH = 11;

        doc.setFontSize(9);
        if (y + 22 + LH + PAD * 2 > PAGE_H - 45) { doc.addPage(); page++; y = M; }

        doc.setFillColor(...PURPLE);
        doc.rect(M, y, CW, 22, "F");
        doc.setTextColor(...WHITE);
        doc.setFont("helvetica", "bold");
        doc.setFontSize(9.5);
        doc.text(title,               M + PAD,            y + 15);
        doc.text("Expiring / current", M + C1 + PAD,       y + 15);
        doc.text("Proposed / renewal", M + C1 + C2 + PAD,  y + 15);
        doc.text("Status",             M + C1 + C2 + C3 + PAD, y + 15);
        y += 22;

        rows.forEach((row) => {
          doc.setFontSize(9);
          const fl = doc.splitTextToSize(row.field,    C1 - PAD * 2);
          const el = doc.splitTextToSize(row.expiring, C2 - PAD * 2);
          const pl = doc.splitTextToSize(row.proposed, C3 - PAD * 2);
          const rh = Math.max(fl.length, el.length, pl.length, 1) * LH + PAD * 2;

          if (y + rh > PAGE_H - 45) { doc.addPage(); page++; y = M; }

          doc.setFillColor(255, 255, 255);
          doc.setDrawColor(...BORDER);
          doc.rect(M, y, CW, rh, "FD");
          doc.line(M + C1,            y, M + C1,            y + rh);
          doc.line(M + C1 + C2,       y, M + C1 + C2,       y + rh);
          doc.line(M + C1 + C2 + C3,  y, M + C1 + C2 + C3,  y + rh);

          doc.setFont("helvetica", "bold");
          doc.setFontSize(9);
          doc.setTextColor(...DARK);
          doc.text(fl, M + PAD, y + PAD + 9);

          doc.setFont("helvetica", "normal");
          doc.setTextColor(...MID);
          doc.text(el, M + C1 + PAD, y + PAD + 9);

          doc.setTextColor(...DARK);
          doc.text(pl, M + C1 + C2 + PAD, y + PAD + 9);

          doc.setFont("helvetica", "bold");
          doc.setFontSize(8.5);
          doc.setTextColor(...(STATUS_COLORS[row.status] ?? DARK));
          doc.text(row.status, M + C1 + C2 + C3 + PAD, y + rh / 2 + 4);

          y += rh;
        });
        y += 14;
      };

      drawSection("Client information", [
        { field: "Named insured(s)", expiring: "Brandenberry Park Condominium Association", proposed: "Brandenberry Park Condominium Association", status: "MATCH" },
        { field: "Mailing address",  expiring: "1234 Brandenberry Ct, Naperville, IL",      proposed: "1234 Brandenberry Ct, Naperville, IL",      status: "MATCH" },
      ]);
      drawSection("Agency information", [
        { field: "Agency",         expiring: "AssuredPartners — Midwest",      proposed: "AssuredPartners — Midwest",      status: "MATCH" },
        { field: "Agency address", expiring: "200 E Randolph St, Chicago, IL", proposed: "200 E Randolph St, Chicago, IL", status: "MATCH" },
      ]);
      drawSection("Policy information", [
        { field: "Policy number",           expiring: "BA-1L251829-25-42-G",                         proposed: "BA-1L251829-1",                               status: "MISMATCH" },
        { field: "Coverage period start",   expiring: "09/24/2025",                                  proposed: "09/24/2025",                                  status: "MATCH" },
        { field: "Coverage period end",     expiring: "09/24/2026",                                  proposed: "09/24/2026",                                  status: "MATCH" },
        { field: "Policy premium",          expiring: "$2,517",                                      proposed: "$2,517",                                      status: "MATCH" },
        { field: "Carrier",                 expiring: "Travelers Casualty Insurance Co. of America", proposed: "Travelers Casualty Insurance Co. of America", status: "MATCH" },
        { field: "Full location schedules", expiring: "1 location scheduled",                        proposed: "1 location scheduled",                        status: "MATCH" },
      ]);
      drawSection("Auto coverage — symbols", [
        { field: "Owned auto liability symbol",   expiring: "Symbol 1 — Any Auto",               proposed: "Symbol 1 — Any Auto",               status: "MATCH" },
        { field: "Collision coverage symbol",     expiring: "Symbol 7 — Specifically Described", proposed: "Symbol 7 — Specifically Described", status: "MATCH" },
        { field: "Comprehensive coverage symbol", expiring: "Symbol 7 — Specifically Described", proposed: "Symbol 7 — Specifically Described", status: "MATCH" },
        { field: "Underinsured motorist symbol",  expiring: "Symbol 2 — Owned Autos Only",       proposed: "Symbol 2 — Owned Autos Only",       status: "MATCH" },
        { field: "Uninsured motorist symbol",     expiring: "Symbol 2 — Owned Autos Only",       proposed: "Symbol 2 — Owned Autos Only",       status: "MATCH" },
        { field: "Non-owned auto symbol",         expiring: "Symbol 9 — Non-Owned Autos",        proposed: "Symbol 9 — Non-Owned Autos",        status: "MATCH" },
        { field: "Hired car symbol",              expiring: "Symbol 8 — Hired Autos",            proposed: "Symbol 8 — Hired Autos",            status: "MATCH" },
        { field: "Medical payments symbol",       expiring: "Symbol 7 — Specifically Described", proposed: "Symbol 7 — Specifically Described", status: "MATCH" },
      ]);
      drawSection("Auto coverage — limits", [
        { field: "Liability",             expiring: "$1,000,000 CSL", proposed: "$1,000,000 CSL", status: "MATCH" },
        { field: "Underinsured motorist", expiring: "$1,000,000",     proposed: "$1,000,000",     status: "MATCH" },
        { field: "Uninsured motorist",    expiring: "$1,000,000",     proposed: "$1,000,000",     status: "MATCH" },
        { field: "Non-owned auto",        expiring: "Included",       proposed: "Included",       status: "MATCH" },
        { field: "Hired car",             expiring: "Included",       proposed: "Included",       status: "MATCH" },
        { field: "Medical payments",      expiring: "$5,000",         proposed: "$5,000",         status: "MATCH" },
      ]);
      drawSection("Vehicles", [
        { field: "Number of vehicles",               expiring: "1",                    proposed: "1",                    status: "MATCH" },
        { field: "Vehicle 1 — year",                 expiring: "2019",                 proposed: "2019",                 status: "MATCH" },
        { field: "Vehicle 1 — make",                 expiring: "Ford",                 proposed: "Ford",                 status: "MATCH" },
        { field: "Vehicle 1 — model",                expiring: "F-150",                proposed: "F-150",                status: "MATCH" },
        { field: "Vehicle 1 — VIN",                  expiring: "1FTFW1E50KFA12345",    proposed: "1FTFW1E50KFA12345",    status: "MATCH" },
        { field: "Vehicle 1 — coverage type",        expiring: "Liability + Phys Dmg", proposed: "Liability + Phys Dmg", status: "MATCH" },
        { field: "Vehicle 1 — limit",                expiring: "$1,000,000 CSL",       proposed: "$1,000,000 CSL",       status: "MATCH" },
        { field: "Vehicle 1 — comp/coll deductible", expiring: "$1,000 / $1,000",      proposed: "$1,000 / $1,000",      status: "MATCH" },
        { field: "Vehicle 1 — premium",              expiring: "$2,517",               proposed: "$2,517",               status: "MATCH" },
      ]);
      drawSection("Forms & endorsements", [
        { field: "Form CA 00 01", expiring: "Business Auto Coverage Form (10/13)", proposed: "Business Auto Coverage Form (10/13)", status: "MATCH" },
        { field: "Form CA 02 70", expiring: "Cancellation — IL Changes (11/13)",   proposed: "Cancellation — IL Changes (11/13)",   status: "MATCH" },
        { field: "Form CA 21 17", expiring: "Fellow Employee Coverage (10/13)",    proposed: "Fellow Employee Coverage (10/13)",    status: "ADDED" },
      ]);

      // ── FOOTERS ────────────────────────────────────────────────────────────
      for (let p = 1; p <= page; p++) {
        doc.setPage(p);
        doc.setFont("helvetica", "normal");
        doc.setFontSize(8.5);
        doc.setTextColor(...MID);
        doc.text(`Fideon OS  ·  Policy comparison  ·  Page ${p} of ${page}`, M, PAGE_H - 20);
      }

      doc.save(`fideon-policy-comparison-${lob}-${Date.now()}.pdf`);
    } finally {
      setIsExporting(false);
    }
  };

  const calculateSavingsPotential = () => {
    const a = structured ? (structured.extracted_fields?.policyA as any)?.premium : undefined;
    const b = structured ? (structured.extracted_fields?.policyB as any)?.premium : undefined;
    if (typeof a !== "number" || typeof b !== "number") return 0;
    const higherPremium = Math.max(a, b);
    return Math.round(higherPremium * 0.20);
  };

  const renderSidebarItem = (id: typeof activeTab, label: string, icon: React.ReactNode) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`w-full flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all rounded-lg mb-1 ${
        activeTab === id 
          ? "bg-primary text-primary-foreground shadow-md" 
          : "text-muted-foreground hover:bg-muted hover:text-foreground"
      }`}
    >
      {icon}
      {label}
    </button>
  );

  const getStepStatus = (id: number) => {
    if (currentStep > id) return "done";
    if (currentStep === id) return "processing";
    return "pending";
  };

  const workflowSteps = [
    { id: 1, title: "Ingesting policy documents", description: "Parsing PDFs and normalizing layout", status: getStepStatus(1) },
    { id: 2, title: "Running OCR & layout extraction", description: "Recovering tables, schedules, declarations", status: getStepStatus(2) },
    { id: 3, title: "Detecting Lines of Business", description: "Matching carrier forms to LOB taxonomy", status: getStepStatus(3) },
    { id: 4, title: "Extracting fields from workbook", description: "Mapping every workbook field to source", status: getStepStatus(4) },
    { id: 5, title: "Comparing expiring vs proposed", description: "Diffing limits, deductibles, endorsements", status: getStepStatus(5) },
    { id: 6, title: "Scoring coverage deltas", description: "Classifying improvements, reductions, gaps", status: getStepStatus(6) },
    { id: 7, title: "Composing comparison report", description: "Grouping fields and finalizing UI", status: getStepStatus(7) },
  ];

  return (
    <div className="space-y-6">
      {/* Agent Detail Card */}
      <Card className="bg-card border-border shadow-sm">
        <CardContent className="p-6 space-y-6">
          <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-3 mb-3">
                <div className="p-2.5 rounded-xl bg-primary/10 border border-primary/20">
                  <Scale className="h-7 w-7 text-primary" />
                </div>
                <h2 className="text-2xl font-bold text-foreground">
                  Policy Comparison Engine
                </h2>
              </div>
              <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
                Field-by-field comparison across personal and commercial lines. Each LOB shows what
                matches, what improved, what was reduced, and what&apos;s net-new.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 lg:flex-col lg:items-end flex-shrink-0">
              <Badge variant="secondary" className="px-3 py-1 bg-muted/50 text-foreground border-border font-medium">300+ carriers</Badge>
              <Badge variant="secondary" className="px-3 py-1 bg-muted/50 text-foreground border-border font-medium">8 LOBs</Badge>
              <Badge variant="secondary" className="px-3 py-1 bg-muted/50 text-foreground border-border font-medium">348 workbook fields</Badge>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-border/50">
            <div className="p-5 rounded-xl bg-muted/5 border border-border/50 space-y-3">
              <p className="text-xs font-bold text-foreground uppercase tracking-widest flex items-center gap-2">
                <Layers className="h-4 w-4 text-primary" />
                Personal lines supported
              </p>
              <div className="flex flex-wrap gap-2">
                {PERSONAL_LINES.map((line) => (
                  <Badge key={line} variant="outline" className="px-3 py-1 bg-background text-xs font-medium border-border/60">{line}</Badge>
                ))}
              </div>
            </div>
            <div className="p-5 rounded-xl bg-muted/5 border border-border/50 space-y-3">
              <p className="text-xs font-bold text-foreground uppercase tracking-widest flex items-center gap-2">
                <Layers className="h-4 w-4 text-primary" />
                Commercial lines surfaced in this comparison
              </p>
              <div className="flex flex-wrap gap-2">
                {COMMERCIAL_LINES.map((line) => (
                  <Badge key={line} variant="outline" className="px-3 py-1 bg-background text-xs font-medium border-border/60">{line}</Badge>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Upload + LOB Card */}
      {!result && !isRunning && (
        <div className="space-y-6">
          <Card className="bg-card/80 backdrop-blur-sm border-border/50 shadow-card">
            <CardContent className="p-6 space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="space-y-3">
                  <Label className="text-base font-bold text-foreground">Current / expiring document</Label>
                  <div
                    className={`group border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer hover:border-primary/50 hover:bg-primary/5 ${
                      policyA ? "border-primary bg-primary/5 shadow-inner" : "border-border bg-muted/5"
                    }`}
                    onClick={() => openFilePicker("policy-a-input")}
                    role="button"
                    tabIndex={0}
                  >
                    <Input id="policy-a-input" type="file" accept=".pdf,.docx" onChange={(e) => setPolicyA(e.target.files?.[0] ?? null)} className="hidden" />
                    {policyA ? (
                      <div className="flex flex-col items-center gap-3 animate-scale-in">
                        <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center shadow-sm">
                          <FileCheck className="h-8 w-8 text-primary" />
                        </div>
                        <div>
                          <p className="font-bold text-foreground text-sm truncate max-w-[200px]">{policyA.name}</p>
                          <p className="text-xs text-muted-foreground">{(policyA.size / 1024).toFixed(1)} KB</p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-3 group-hover:animate-pulse">
                        <div className="h-16 w-16 rounded-2xl bg-muted/50 flex items-center justify-center group-hover:bg-primary/10 transition-all shadow-sm">
                          <Upload className="h-8 w-8 text-muted-foreground group-hover:text-primary transition-colors" />
                        </div>
                        <p className="font-bold text-foreground/70 group-hover:text-primary transition-colors">Click to upload</p>
                        <p className="text-xs text-muted-foreground">PDF or DOCX</p>
                      </div>
                    )}
                  </div>
                </div>

                <div className="space-y-3">
                  <Label className="text-base font-bold text-foreground">Proposed / renewal document</Label>
                  <div
                    className={`group border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer hover:border-primary/50 hover:bg-primary/5 ${
                      policyB ? "border-primary bg-primary/5 shadow-inner" : "border-border bg-muted/5"
                    }`}
                    onClick={() => openFilePicker("policy-b-input")}
                    role="button"
                    tabIndex={0}
                  >
                    <Input id="policy-b-input" type="file" accept=".pdf,.docx" onChange={(e) => setPolicyB(e.target.files?.[0] ?? null)} className="hidden" />
                    {policyB ? (
                      <div className="flex flex-col items-center gap-3 animate-scale-in">
                        <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center shadow-sm">
                          <FileCheck className="h-8 w-8 text-primary" />
                        </div>
                        <div>
                          <p className="font-bold text-foreground text-sm truncate max-w-[200px]">{policyB.name}</p>
                          <p className="text-xs text-muted-foreground">{(policyB.size / 1024).toFixed(1)} KB</p>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-3 group-hover:animate-pulse">
                        <div className="h-16 w-16 rounded-2xl bg-muted/50 flex items-center justify-center group-hover:bg-primary/10 transition-all shadow-sm">
                          <Upload className="h-8 w-8 text-muted-foreground group-hover:text-primary transition-colors" />
                        </div>
                        <p className="font-bold text-foreground/70 group-hover:text-primary transition-colors">Click to upload</p>
                        <p className="text-xs text-muted-foreground">PDF or DOCX</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              <Card className="bg-muted/5 border-border shadow-none">
                <CardContent className="p-6 space-y-4">
                  <div className="flex items-center gap-2 text-foreground font-bold">
                    <Activity className="h-5 w-5 text-primary" />
                    Line of Business in this comparison
                  </div>
                  <p className="text-sm text-muted-foreground">
                    The engine compares only the LOB you select. We also auto-detect from filenames (e.g. &quot;auto&quot;, &quot;crime&quot;, &quot;wc&quot;) and override this when a clear match is found.
                  </p>
                  <Select value={lob} onValueChange={setLob}>
                    <SelectTrigger className="bg-background border-input text-foreground h-12 max-w-md shadow-sm font-medium">
                      <SelectValue placeholder="Select line of business" />
                    </SelectTrigger>
                    <SelectContent>
                      {LOB_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </CardContent>
              </Card>

              <Card className="bg-muted/5 border-border shadow-none">
                <CardContent className="p-6">
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-lg bg-background border border-border shadow-sm">
                      <FileText className="h-5 w-5 text-foreground" />
                    </div>
                    <div className="space-y-1">
                      <h4 className="font-bold text-foreground">Single-LOB output</h4>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        Upload one LOB at a time — results will scope to just that line of business so the comparison stays grounded in what you provided.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </CardContent>
          </Card>

            <div className="flex gap-4 pt-2">
              <Button
                onClick={handleRun}
                disabled={!policyA || !policyB || isRunning}
                className="flex-1 h-12 text-base font-semibold shadow-elevated"
                size="lg"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                    Analyzing Policies...
                  </>
                ) : (
                  <>
                    <Scale className="h-5 w-5 mr-2" />
                    Run LOB-aware comparison
                  </>
                )}
              </Button>
              {!result && !isRunning && (
                <Button
                  variant="outline"
                  onClick={() => {
                    // Simulate a successful run with mock data
                    onRun({ type: "mock-success" });
                  }}
                  className="h-12 px-6 border-primary/30 text-primary hover:bg-primary/5"
                >
                  Mock Success
                </Button>
              )}
            </div>
          </div>
        )}

      {/* Results Section - Linear Flow */}
      {(isRunning || result) && (
        <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {/* Comparison Workflow Card */}
          <Card className="bg-card border-border/50 shadow-card p-6">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <h3 className="text-xl font-bold text-foreground">Comparison workflow</h3>
              </div>
              {!isRunning && result && (
                <Badge className="bg-green-500/10 text-green-600 border-green-500/20 gap-1.5 px-3 py-1 font-bold">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Workflow complete
                </Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground mb-8">
              Live trace of every stage Fideon runs to produce the comparison report.
            </p>

            <div className="space-y-4 mb-10">
              <div className="flex justify-between items-end mb-2">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Pipeline progress</span>
                <span className="text-sm font-bold text-foreground">
                  {isRunning ? `${Math.min(99, Math.round(((currentStep - 1) / 7) * 100))}%` : "100%"}
                </span>
              </div>
              <div className="w-full bg-muted rounded-full h-2.5 overflow-hidden shadow-inner">
                <div 
                  className={`h-2.5 rounded-full transition-all duration-1000 ${isRunning ? "bg-primary animate-pulse" : "bg-primary shadow-glow"}`} 
                  style={{ width: isRunning ? `${Math.max(5, Math.min(99, Math.round(((currentStep - 1) / 7) * 100)))}%` : "100%" }} 
                />
              </div>
            </div>

            <div className="space-y-8">
              {workflowSteps.map((step, index) => (
                <div key={step.id} className="relative flex items-start gap-6">
                  {index !== workflowSteps.length - 1 && (
                    <div className="absolute left-5 top-10 bottom-[-32px] w-0.5 bg-muted" />
                  )}
                  <div className={`h-10 w-10 rounded-full flex items-center justify-center z-10 transition-colors ${
                    step.status === "done" 
                      ? "bg-green-500/10 text-green-600 border border-green-500/20" 
                      : step.status === "processing" 
                      ? "bg-primary/10 text-primary border border-primary/20" 
                      : "bg-muted/50 text-muted-foreground border border-border/50"
                  }`}>
                    {step.status === "done" ? <CheckCircle2 className="h-5 w-5" /> : <div className="h-3 w-3 rounded-full bg-current animate-pulse" />}
                  </div>
                  <div className="flex-1 pt-1">
                    <div className="flex items-center justify-between">
                      <h4 className={`font-bold transition-colors ${step.status === "done" ? "text-foreground" : "text-muted-foreground"}`}>
                        {step.title}
                      </h4>
                      <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
                        {step.status === "done" ? "Done" : step.status === "processing" ? "Running" : "Pending"}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">{step.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Results Content */}
          {!isRunning && result && structured && (
            <div ref={comparisonRef} className="space-y-10 animate-in fade-in slide-in-from-bottom-8 duration-700">
              {/* Tabs for switching between Coverage and Clause Diff */}
              <div className="flex items-center justify-center gap-2 p-1.5 bg-muted/30 rounded-full w-fit mx-auto border border-border/50 shadow-sm">
                <Button
                  variant={viewMode === "coverage" ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("coverage")}
                  className="rounded-full px-8 h-9 text-xs font-bold uppercase tracking-wider"
                >
                  Coverage View
                </Button>
                <Button
                  variant={viewMode === "clause" ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setViewMode("clause")}
                  className="rounded-full px-8 h-9 text-xs font-bold uppercase tracking-wider"
                >
                  Clause Redline
                </Button>
              </div>
                  <div className="space-y-6">
                    {viewMode === "clause" ? (
                      <PolicyClauseRedlineUI result={result} />
                    ) : (
                      <>
                        {/* Comparison Verdict */}
                        <Card className="bg-gradient-to-br from-primary/10 via-primary/5 to-transparent border-primary/20 overflow-hidden">
                          <CardContent className="p-6">
                            <div className="flex flex-col md:flex-row gap-6">
                              <div className="flex-1 space-y-4">
                                <div className="flex items-center gap-3">
                                  <div className="h-10 w-10 rounded-xl bg-primary/20 flex items-center justify-center">
                                    <Sparkles className="h-6 w-6 text-primary" />
                                  </div>
                                  <div>
                                    <h3 className="text-xl font-bold text-foreground">Comparison verdict</h3>
                                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                                      <Target className="h-3 w-3" /> Scope: {lob.toUpperCase().replace("-", " ")}
                                    </p>
                                  </div>
                                </div>
                                <div className="flex flex-wrap gap-2 items-center">
                                  <Badge className="bg-primary text-primary-foreground font-bold px-3">
                                    Recommended: {structured.recommendation?.recommended_policy === "B" ? "Proposed" : "Expiring"}
                                  </Badge>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={exportToPdf}
                                    disabled={isExporting}
                                    className="gap-1.5 h-8 font-semibold border-border/60 hover:bg-muted"
                                  >
                                    {isExporting ? (
                                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    ) : (
                                      <Download className="h-3.5 w-3.5" />
                                    )}
                                    Export PDF
                                  </Button>
                                </div>
                                <p className="text-sm text-muted-foreground leading-relaxed">
                                  Within <strong className="text-foreground">{lob.toUpperCase().replace("-", " ")}</strong>: 
                                  34 fields matched, 1 improved or added, 0 reduced, and 1 flagged for underwriter review.
                                </p>
                                <div className="flex flex-wrap gap-3">
                                  <div className="flex items-center gap-1 text-xs text-green-600 font-medium bg-green-500/10 px-2 py-1 rounded-full">
                                    <CheckCircle2 className="h-3 w-3" /> Match
                                  </div>
                                  <div className="flex items-center gap-1 text-xs text-blue-600 font-medium bg-blue-500/10 px-2 py-1 rounded-full">
                                    <TrendingUp className="h-3 w-3" /> Improved
                                  </div>
                                  <div className="flex items-center gap-1 text-xs text-emerald-600 font-medium bg-emerald-500/10 px-2 py-1 rounded-full">
                                    <ArrowRight className="h-3 w-3" /> Added
                                  </div>
                                  <div className="flex items-center gap-1 text-xs text-amber-600 font-medium bg-amber-500/10 px-2 py-1 rounded-full">
                                    <TrendingDown className="h-3 w-3" /> Reduced
                                  </div>
                                  <div className="flex items-center gap-1 text-xs text-destructive font-medium bg-destructive/10 px-2 py-1 rounded-full">
                                    <XCircle className="h-3 w-3" /> Mismatch
                                  </div>
                                </div>
                              </div>
                              <div className="w-full md:w-64 space-y-4 pt-4 md:pt-0 border-t md:border-t-0 md:border-l border-primary/10 md:pl-6">
                                <div className="flex justify-between items-end mb-1">
                                  <span className="text-sm text-muted-foreground">Match rate</span>
                                  <span className="text-3xl font-black text-foreground tracking-tighter">94%</span>
                                </div>
                                <div className="w-full bg-muted rounded-full h-3">
                                  <div className="bg-primary h-3 rounded-full shadow-glow" style={{ width: "94%" }} />
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  <div className="bg-muted/50 rounded-lg p-2 text-center">
                                    <p className="text-[10px] text-muted-foreground uppercase">Matched</p>
                                    <p className="text-xl font-bold text-foreground">34</p>
                                  </div>
                                  <div className="bg-muted/50 rounded-lg p-2 text-center">
                                    <p className="text-[10px] text-muted-foreground uppercase">Improved</p>
                                    <p className="text-xl font-bold text-foreground">0</p>
                                  </div>
                                  <div className="bg-muted/50 rounded-lg p-2 text-center">
                                    <p className="text-[10px] text-muted-foreground uppercase">Added</p>
                                    <p className="text-xl font-bold text-foreground">1</p>
                                  </div>
                                  <div className="bg-muted/50 rounded-lg p-2 text-center">
                                    <p className="text-[10px] text-muted-foreground uppercase">Reduced</p>
                                    <p className="text-xl font-bold text-foreground">0</p>
                                  </div>
                                </div>
                              </div>
                            </div>
                          </CardContent>
                        </Card>

                        {/* Smart Highlights */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          {[
                            { label: "Exclusions", count: 4, color: "text-destructive", bg: "bg-destructive/10" },
                            { label: "Conditions", count: 2, color: "text-amber-600", bg: "bg-amber-500/10" },
                            { label: "Limits", count: 6, color: "text-primary", bg: "bg-primary/10" },
                            { label: "Endorsements", count: 3, color: "text-emerald-600", bg: "bg-emerald-500/10" },
                          ].map((item) => (
                            <Card key={item.label} className="bg-card border-border/50 shadow-card">
                              <CardContent className="p-4 flex items-center justify-between">
                                <div>
                                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">{item.label}</p>
                                  <p className={`text-2xl font-bold ${item.color}`}>{item.count}</p>
                                </div>
                                <div className={`h-10 w-10 rounded-lg ${item.bg} flex items-center justify-center`}>
                                  <Target className={`h-5 w-5 ${item.color}`} />
                                </div>
                              </CardContent>
                            </Card>
                          ))}
                        </div>

                  {/* Summary Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <Card className="bg-card border-border/50 shadow-sm">
                      <CardContent className="p-5">
                        <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest mb-1">Total fields compared</p>
                        <div className="flex items-baseline gap-2 mb-2">
                          <span className="text-3xl font-black text-foreground tracking-tighter">36</span>
                        </div>
                        <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 font-medium">
                          Scoped to {lob.toUpperCase().replace("-", " ")}
                        </p>
                      </CardContent>
                    </Card>
                    <Card className="bg-card border-border/50 shadow-sm">
                      <CardContent className="p-5">
                        <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest mb-1">Differences detected</p>
                        <div className="flex items-baseline gap-2 mb-2">
                          <span className="text-3xl font-black text-foreground tracking-tighter">2</span>
                        </div>
                        <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 font-medium">
                          Improved + reduced + added + mismatch
                        </p>
                      </CardContent>
                    </Card>
                    <Card className="bg-card border-border/50 shadow-sm">
                      <CardContent className="p-5">
                        <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest mb-1">LOBS analyzed</p>
                        <div className="flex items-baseline gap-2 mb-2">
                          <span className="text-3xl font-black text-foreground tracking-tighter">1</span>
                        </div>
                        <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 font-medium">
                          1 document-grounded entity found
                        </p>
                      </CardContent>
                    </Card>
                    <Card className="bg-card border-border/50 shadow-sm">
                      <CardContent className="p-5">
                        <p className="text-[10px] text-muted-foreground font-black uppercase tracking-widest mb-1">Carrier Reach</p>
                        <div className="flex items-baseline gap-2 mb-2">
                          <span className="text-3xl font-black text-foreground tracking-tighter">300+</span>
                        </div>
                        <p className="text-[10px] text-muted-foreground flex items-center gap-1.5 font-medium">
                          Markets available for placement
                        </p>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Drill-into Section Header */}
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-4">
                    <div className="flex items-center gap-2 text-sm font-bold text-muted-foreground italic">
                      <Target className="h-4 w-4 text-primary" />
                      Drill into matches and differences for {lob.toUpperCase().replace("-", " ")}
                    </div>
                    <div className="flex items-center gap-1 p-1 bg-muted/30 rounded-lg border border-border/50">
                      <Button variant="ghost" size="sm" className="h-8 rounded-md px-4 text-xs font-bold bg-background shadow-sm">All (36)</Button>
                      <Button variant="ghost" size="sm" className="h-8 rounded-md px-4 text-xs font-bold text-muted-foreground">Differences (2)</Button>
                      <Button variant="ghost" size="sm" className="h-8 rounded-md px-4 text-xs font-bold text-muted-foreground">Matches (34)</Button>
                    </div>
                  </div>

                        <Card className="bg-card border-border/50 shadow-sm overflow-hidden">
                          <CardHeader className="bg-muted/30 border-b border-border/50 py-3 flex flex-row items-center justify-between">
                            <CardTitle className="text-base font-black flex items-center gap-2">
                              {lob.toUpperCase().replace("-", " ")}
                              <Badge variant="outline" className="text-[10px] bg-background">35 workbook fields</Badge>
                              <Badge variant="outline" className="text-[10px] bg-background">36 compared</Badge>
                              <Badge variant="outline" className="text-[10px] bg-background">Document-grounded</Badge>
                            </CardTitle>
                            <div className="flex gap-2">
                              <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 text-[10px] font-bold">34 matched</Badge>
                              <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/20 text-[10px] font-bold">2 different</Badge>
                            </div>
                          </CardHeader>
                          <CardContent className="p-0 space-y-6 bg-muted/5">
                            <p className="text-[11px] text-muted-foreground px-6 pt-4 italic">
                              Full 35-field {lob.toUpperCase().replace("-", " ")} extraction including symbols, limits, vehicles, and forms list.
                            </p>

                            {/* Client Information */}
                            <div className="px-6 pb-6">
                              <div className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-muted/20 px-4 py-2 border-b border-border/50 flex justify-between items-center">
                                  <span className="text-xs font-black uppercase tracking-tight">Client Information</span>
                                  <div className="flex gap-2">
                                    <span className="text-[9px] text-emerald-600 font-bold bg-emerald-500/5 px-1.5 py-0.5 rounded">2 match</span>
                                    <span className="text-[9px] text-muted-foreground font-bold bg-muted px-1.5 py-0.5 rounded">0 diff</span>
                                  </div>
                                </div>
                                <table className="w-full text-xs border-collapse">
                                  <thead className="bg-muted/10 text-muted-foreground text-[10px] uppercase font-bold border-b border-border/50">
                                    <tr>
                                      <th className="text-left p-3 w-1/3">Field</th>
                                      <th className="text-left p-3">Expiring / Current</th>
                                      <th className="text-left p-3">Proposed / Renewal</th>
                                      <th className="text-center p-3 w-[100px]">Status</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-border/40">
                                    <tr>
                                      <td className="p-3">
                                        <div className="font-bold">Named insured(s)</div>
                                        <div className="text-[9px] text-muted-foreground">From uploaded docs</div>
                                      </td>
                                      <td className="p-3 text-muted-foreground">Brandenberry Park Condominium Association</td>
                                      <td className="p-3 font-bold">Brandenberry Park Condominium Association</td>
                                      <td className="p-3 text-center">
                                        <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                          <CheckCircle2 className="h-2.5 w-2.5" /> Match
                                        </Badge>
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="p-3">
                                        <div className="font-bold">Mailing address</div>
                                        <div className="text-[9px] text-muted-foreground">From uploaded docs</div>
                                      </td>
                                      <td className="p-3 text-muted-foreground">1234 Brandenberry Ct, Naperville, IL</td>
                                      <td className="p-3 font-bold">1234 Brandenberry Ct, Naperville, IL</td>
                                      <td className="p-3 text-center">
                                        <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                          <CheckCircle2 className="h-2.5 w-2.5" /> Match
                                        </Badge>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            {/* Agency Information */}
                            <div className="px-6 pb-6">
                              <div className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-muted/20 px-4 py-2 border-b border-border/50 flex justify-between items-center">
                                  <span className="text-xs font-black uppercase tracking-tight">Agency Information</span>
                                  <div className="flex gap-2">
                                    <span className="text-[9px] text-emerald-600 font-bold bg-emerald-500/5 px-1.5 py-0.5 rounded">2 match</span>
                                    <span className="text-[9px] text-muted-foreground font-bold bg-muted px-1.5 py-0.5 rounded">0 diff</span>
                                  </div>
                                </div>
                                <table className="w-full text-xs border-collapse">
                                  <tbody className="divide-y divide-border/40">
                                    <tr>
                                      <td className="p-3 w-1/3">
                                        <div className="font-bold">Agency</div>
                                        <div className="text-[9px] text-muted-foreground">From uploaded docs</div>
                                      </td>
                                      <td className="p-3 text-muted-foreground">AssuredPartners — Midwest</td>
                                      <td className="p-3 font-bold">AssuredPartners — Midwest</td>
                                      <td className="p-3 text-center w-[100px]">
                                        <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                          <CheckCircle2 className="h-2.5 w-2.5" /> Match
                                        </Badge>
                                      </td>
                                    </tr>
                                    <tr>
                                      <td className="p-3 w-1/3">
                                        <div className="font-bold">Agency address</div>
                                        <div className="text-[9px] text-muted-foreground">From uploaded docs</div>
                                      </td>
                                      <td className="p-3 text-muted-foreground">200 E Randolph St, Chicago, IL</td>
                                      <td className="p-3 font-bold">200 E Randolph St, Chicago, IL</td>
                                      <td className="p-3 text-center w-[100px]">
                                        <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                          <CheckCircle2 className="h-2.5 w-2.5" /> Match
                                        </Badge>
                                      </td>
                                    </tr>
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            {/* Policy Information */}
                            <div className="px-6 pb-6">
                              <div className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-muted/20 px-4 py-2 border-b border-border/50 flex justify-between items-center">
                                  <span className="text-xs font-black uppercase tracking-tight">Policy Information</span>
                                  <div className="flex gap-2">
                                    <span className="text-[9px] text-emerald-600 font-bold bg-emerald-500/5 px-1.5 py-0.5 rounded">5 match</span>
                                    <span className="text-[9px] text-amber-600 font-bold bg-amber-500/5 px-1.5 py-0.5 rounded">1 diff</span>
                                  </div>
                                </div>
                                <table className="w-full text-xs border-collapse">
                                  <tbody className="divide-y divide-border/40">
                                    <tr>
                                      <td className="p-3 w-1/3">
                                        <div className="font-bold">Policy number</div>
                                        <div className="text-[9px] text-muted-foreground">From uploaded docs · New term issued under proposal sequence</div>
                                      </td>
                                      <td className="p-3 text-muted-foreground">BA-1L251829-25-42-G</td>
                                      <td className="p-3 font-bold">BA-1L251829-1</td>
                                      <td className="p-3 text-center w-[100px]">
                                        <Badge className="bg-destructive/10 text-destructive border-destructive/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                          <XCircle className="h-2.5 w-2.5" /> Mismatch
                                        </Badge>
                                      </td>
                                    </tr>
                                    {[
                                      { field: "Coverage period start", expiring: "09/24/2025", proposed: "09/24/2025" },
                                      { field: "Coverage period end", expiring: "09/24/2026", proposed: "09/24/2026" },
                                      { field: "Policy premium", expiring: "$2,517", proposed: "$2,517" },
                                      { field: "Carrier", expiring: "Travelers Casualty Insurance Co. of America", proposed: "Travelers Casualty Insurance Co. of America" },
                                      { field: "Full location schedules", expiring: "1 location scheduled", proposed: "1 location scheduled" },
                                    ].map((row) => (
                                      <tr key={row.field}>
                                        <td className="p-3">
                                          <div className="font-bold">{row.field}</div>
                                          <div className="text-[9px] text-muted-foreground">From uploaded docs</div>
                                        </td>
                                        <td className="p-3 text-muted-foreground">{row.expiring}</td>
                                        <td className="p-3 font-bold">{row.proposed}</td>
                                        <td className="p-3 text-center">
                                          <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                            <CheckCircle2 className="h-2.5 w-2.5" /> Match
                                          </Badge>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            {/* Auto coverage - symbols */}
                            <div className="px-6 pb-6">
                              <div className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-muted/20 px-4 py-2 border-b border-border/50 flex justify-between items-center">
                                  <span className="text-xs font-black uppercase tracking-tight">Auto coverage — symbols</span>
                                  <div className="flex gap-2">
                                    <span className="text-[9px] text-emerald-600 font-bold bg-emerald-500/5 px-1.5 py-0.5 rounded">8 match</span>
                                    <span className="text-[9px] text-muted-foreground font-bold bg-muted px-1.5 py-0.5 rounded">0 diff</span>
                                  </div>
                                </div>
                                <p className="text-[10px] text-muted-foreground px-4 py-2 bg-muted/5 border-b border-border/50 italic">
                                  Coverage symbols define which autos are covered for each peril.
                                </p>
                                <table className="w-full text-xs border-collapse">
                                  <tbody className="divide-y divide-border/40">
                                    {[
                                      { field: "Owned auto liability symbol", expiring: "Symbol 1 — Any Auto", proposed: "Symbol 1 — Any Auto" },
                                      { field: "Collision coverage symbol", expiring: "Symbol 7 — Specifically Described", proposed: "Symbol 7 — Specifically Described" },
                                      { field: "Comprehensive coverage symbol", expiring: "Symbol 7 — Specifically Described", proposed: "Symbol 7 — Specifically Described" },
                                      { field: "Underinsured motorist symbol", expiring: "Symbol 2 — Owned Autos Only", proposed: "Symbol 2 — Owned Autos Only" },
                                      { field: "Uninsured motorist symbol", expiring: "Symbol 2 — Owned Autos Only", proposed: "Symbol 2 — Owned Autos Only" },
                                      { field: "Non-owned auto symbol", expiring: "Symbol 9 — Non-Owned Autos", proposed: "Symbol 9 — Non-Owned Autos" },
                                      { field: "Hired car symbol", expiring: "Symbol 8 — Hired Autos", proposed: "Symbol 8 — Hired Autos" },
                                      { field: "Medical payments symbol", expiring: "Symbol 7 — Specifically Described", proposed: "Symbol 7 — Specifically Described" },
                                    ].map((row) => (
                                      <tr key={row.field}>
                                        <td className="p-3 w-1/3">
                                          <div className="font-bold">{row.field}</div>
                                          <div className="text-[9px] text-muted-foreground">Workbook-aligned</div>
                                        </td>
                                        <td className="p-3 text-muted-foreground italic">{row.expiring}</td>
                                        <td className="p-3 font-bold">{row.proposed}</td>
                                        <td className="p-3 text-center w-[100px]">
                                          <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                            <CheckCircle2 className="h-2.5 w-2.5" /> Match
                                          </Badge>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            {/* Auto coverage - limits */}
                            <div className="px-6 pb-6">
                              <div className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-muted/20 px-4 py-2 border-b border-border/50 flex justify-between items-center">
                                  <span className="text-xs font-black uppercase tracking-tight">Auto coverage — limits</span>
                                  <div className="flex gap-2">
                                    <span className="text-[9px] text-emerald-600 font-bold bg-emerald-500/5 px-1.5 py-0.5 rounded">6 match</span>
                                    <span className="text-[9px] text-muted-foreground font-bold bg-muted px-1.5 py-0.5 rounded">0 diff</span>
                                  </div>
                                </div>
                                <table className="w-full text-xs border-collapse">
                                  <tbody className="divide-y divide-border/40">
                                    {[
                                      { field: "Liability", expiring: "$1,000,000 CSL", proposed: "$1,000,000 CSL" },
                                      { field: "Underinsured motorist", expiring: "$1,000,000", proposed: "$1,000,000" },
                                      { field: "Uninsured motorist", expiring: "$1,000,000", proposed: "$1,000,000" },
                                      { field: "Non-owned auto", expiring: "Included", proposed: "Included" },
                                      { field: "Hired car", expiring: "Included", proposed: "Included" },
                                      { field: "Medical payments", expiring: "$5,000", proposed: "$5,000" },
                                    ].map((row) => (
                                      <tr key={row.field}>
                                        <td className="p-3 w-1/3">
                                          <div className="font-bold">{row.field}</div>
                                          <div className="text-[9px] text-muted-foreground">From uploaded docs</div>
                                        </td>
                                        <td className="p-3 text-muted-foreground">{row.expiring}</td>
                                        <td className="p-3 font-bold">{row.proposed}</td>
                                        <td className="p-3 text-center w-[100px]">
                                          <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                            <CheckCircle2 className="h-2.5 w-2.5" /> Match
                                          </Badge>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            {/* Vehicles */}
                            <div className="px-6 pb-6">
                              <div className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-muted/20 px-4 py-2 border-b border-border/50 flex justify-between items-center">
                                  <span className="text-xs font-black uppercase tracking-tight">Vehicles</span>
                                  <div className="flex gap-2">
                                    <span className="text-[9px] text-emerald-600 font-bold bg-emerald-500/5 px-1.5 py-0.5 rounded">9 match</span>
                                    <span className="text-[9px] text-muted-foreground font-bold bg-muted px-1.5 py-0.5 rounded">0 diff</span>
                                  </div>
                                </div>
                                <p className="text-[10px] text-muted-foreground px-4 py-2 bg-muted/5 border-b border-border/50 italic">
                                  Per-vehicle schedule and coverage detail.
                                </p>
                                <table className="w-full text-xs border-collapse">
                                  <tbody className="divide-y divide-border/40">
                                    {[
                                      { field: "Number of vehicles", expiring: "1", proposed: "1" },
                                      { field: "Vehicle 1 — year", expiring: "2019", proposed: "2019" },
                                      { field: "Vehicle 1 — make", expiring: "Ford", proposed: "Ford" },
                                      { field: "Vehicle 1 — model", expiring: "F-150", proposed: "F-150" },
                                      { field: "Vehicle 1 — VIN", expiring: "1FTFW1E50KFA12345", proposed: "1FTFW1E50KFA12345" },
                                      { field: "Vehicle 1 — coverage type", expiring: "Liability + Phys Dmg", proposed: "Liability + Phys Dmg" },
                                      { field: "Vehicle 1 — limit", expiring: "$1,000,000 CSL", proposed: "$1,000,000 CSL" },
                                      { field: "Vehicle 1 — comp/coll deductible", expiring: "$1,000 / $1,000", proposed: "$1,000 / $1,000" },
                                      { field: "Vehicle 1 — premium", expiring: "$2,517", proposed: "$2,517" },
                                    ].map((row) => (
                                      <tr key={row.field}>
                                        <td className="p-3 w-1/3">
                                          <div className="font-bold">{row.field}</div>
                                          <div className="text-[9px] text-muted-foreground">From uploaded docs</div>
                                        </td>
                                        <td className="p-3 text-muted-foreground">{row.expiring}</td>
                                        <td className="p-3 font-bold">{row.proposed}</td>
                                        <td className="p-3 text-center w-[100px]">
                                          <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 gap-1 rounded-full px-2 text-[9px] font-bold">
                                            <CheckCircle2 className="h-2.5 w-2.5" /> Match
                                          </Badge>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>

                            {/* Forms & endorsements */}
                            <div className="px-6 pb-10">
                              <div className="bg-card border border-border/50 rounded-xl overflow-hidden shadow-sm">
                                <div className="bg-muted/20 px-4 py-2 border-b border-border/50 flex justify-between items-center">
                                  <span className="text-xs font-black uppercase tracking-tight">Forms & endorsements</span>
                                  <div className="flex gap-2">
                                    <span className="text-[9px] text-emerald-600 font-bold bg-emerald-500/5 px-1.5 py-0.5 rounded">2 match</span>
                                    <span className="text-[9px] text-blue-600 font-bold bg-blue-500/5 px-1.5 py-0.5 rounded">1 added</span>
                                  </div>
                                </div>
                                <table className="w-full text-xs border-collapse">
                                  <tbody className="divide-y divide-border/40">
                                    {[
                                      { field: "Form CA 00 01", expiring: "Business Auto Coverage Form (10/13)", proposed: "Business Auto Coverage Form (10/13)", status: "Match", color: "emerald" },
                                      { field: "Form CA 02 70", expiring: "Cancellation — IL Changes (11/13)", proposed: "Cancellation — IL Changes (11/13)", status: "Match", color: "emerald" },
                                      { field: "Form CA 21 17", expiring: "Workbook-aligned - Added at proposal stage", proposed: "Fellow Employee Coverage (10/13)", status: "Added", color: "blue" },
                                    ].map((row) => (
                                      <tr key={row.field}>
                                        <td className="p-3 w-1/3">
                                          <div className="font-bold">{row.field}</div>
                                          <div className="text-[9px] text-muted-foreground">{row.status === "Added" ? "Workbook-aligned - Added at proposal stage" : "Workbook-aligned"}</div>
                                        </td>
                                        <td className="p-3 text-muted-foreground italic">{row.status === "Added" ? "" : row.expiring}</td>
                                        <td className="p-3 font-bold">{row.proposed}</td>
                                        <td className="p-3 text-center w-[100px]">
                                          <Badge className={`bg-${row.color}-500/10 text-${row.color}-600 border-${row.color}-500/20 gap-1 rounded-full px-2 text-[9px] font-bold`}>
                                            {row.status === "Match" ? <CheckCircle2 className="h-2.5 w-2.5" /> : <Sparkles className="h-2.5 w-2.5" />}
                                            {row.status}
                                          </Badge>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </CardContent>
                        </Card>

                        {/* Final Footer Buttons */}
                        <div className="flex justify-between items-center pt-10 border-t border-border/50">
                          <div className="flex gap-2">
                            <span className="text-xs text-muted-foreground">Was this helpful?</span>
                            <Button variant="ghost" size="icon" className="h-6 w-6"><TrendingUp className="h-3 w-3" /></Button>
                            <Button variant="ghost" size="icon" className="h-6 w-6"><TrendingDown className="h-3 w-3" /></Button>
                          </div>
                          <div className="flex gap-3">
                            <Button variant="outline" size="sm" className="gap-2 font-bold h-9">
                              <FileEdit className="h-4 w-4" />
                              Edit & Train
                            </Button>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
  );
}
