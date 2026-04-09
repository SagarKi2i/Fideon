import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import PolicyClauseRedlineUI from "./PolicyClauseRedlineUI";
import { parsePolicyClauseDiff } from "@/lib/policyClauseDiff";
import { 
  Upload, 
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
  Sparkles
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useNavigate } from "react-router-dom";
import { useWorkflowSettings } from "@/hooks/useWorkflowSettings";
import OutputCorrection from "./OutputCorrection";

interface PolicyComparisonUIProps {
  readonly modelId?: string;
  readonly onRun: (data: any) => void;
  readonly isRunning: boolean;
  readonly result: string;
}

import { tryParsePolicyComparisonStructured } from "@/lib/policyComparisonPrompt";

export default function PolicyComparisonUI({ modelId, onRun, isRunning, result }: PolicyComparisonUIProps) {
  const [policyA, setPolicyA] = useState<File | null>(null);
  const [policyB, setPolicyB] = useState<File | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");
  const [viewMode, setViewMode] = useState<"coverage" | "clause">("coverage");
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
    });
  };

  const structured = useMemo(() => tryParsePolicyComparisonStructured(result), [result]);
  const clauseDiff = useMemo(() => parsePolicyClauseDiff(result), [result]);

  // Auto-select clause redline when structured diff is available.
  useEffect(() => {
    setViewMode(clauseDiff ? "clause" : "coverage");
  }, [result, clauseDiff]); // result changes imply clauseDiff potentially changed
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

  const renderCoverageIcon = (covered: boolean) =>
    covered ? (
      <CheckCircle2 className="h-5 w-5 text-green-600 mx-auto" />
    ) : (
      <XCircle className="h-5 w-5 text-destructive mx-auto" />
    );
  const openFilePicker = (inputId: string) => document.getElementById(inputId)?.click();

  const calculateSavingsPotential = () => {
    const a = structured ? (structured.extracted_fields?.policyA as any)?.premium : undefined;
    const b = structured ? (structured.extracted_fields?.policyB as any)?.premium : undefined;
    if (typeof a !== "number" || typeof b !== "number") return 0;
    const higherPremium = Math.max(a, b);
    // Estimated savings potential of 15-25%
    return Math.round(higherPremium * 0.20);
  };

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <Scale className="h-5 w-5 text-primary" />
            Policy Comparison Engine
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Upload two policies to compare coverage, limits, deductibles, and identify gaps
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Policy A Upload */}
            <div className="space-y-3">
              <Label className="text-base font-semibold flex items-center gap-2">
                <div className="h-6 w-6 rounded-full bg-blue-500/20 flex items-center justify-center">
                  <span className="text-xs font-bold text-blue-600">A</span>
                </div>
                Current / Expiring Policy
              </Label>
              <div 
                className={`border-2 border-dashed rounded-lg p-6 text-center transition-all cursor-pointer hover:border-primary/50 hover:bg-muted/30 ${
                  policyA ? "border-primary bg-primary/5" : "border-border"
                }`}
                onClick={() => openFilePicker("policy-a-input")}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openFilePicker("policy-a-input");
                  }
                }}
                role="button"
                tabIndex={0}
                aria-label="Upload policy A document"
              >
                <Input
                  id="policy-a-input"
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setPolicyA(e.target.files?.[0] ?? null)}
                  className="hidden"
                />
                {policyA ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                      <FileCheck className="h-6 w-6 text-primary" />
                    </div>
                    <p className="font-medium text-foreground">{policyA.name}</p>
                    <p className="text-xs text-muted-foreground">{(policyA.size / 1024).toFixed(1)} KB</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
                      <Upload className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <p className="font-medium text-muted-foreground">Click to upload Policy A</p>
                    <p className="text-xs text-muted-foreground">PDF or DOCX</p>
                  </div>
                )}
              </div>
            </div>

            {/* Policy B Upload */}
            <div className="space-y-3">
              <Label className="text-base font-semibold flex items-center gap-2">
                <div className="h-6 w-6 rounded-full bg-green-500/20 flex items-center justify-center">
                  <span className="text-xs font-bold text-green-600">B</span>
                </div>
                Proposed / Renewal Policy
              </Label>
              <div 
                className={`border-2 border-dashed rounded-lg p-6 text-center transition-all cursor-pointer hover:border-primary/50 hover:bg-muted/30 ${
                  policyB ? "border-primary bg-primary/5" : "border-border"
                }`}
                onClick={() => openFilePicker("policy-b-input")}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openFilePicker("policy-b-input");
                  }
                }}
                role="button"
                tabIndex={0}
                aria-label="Upload policy B document"
              >
                <Input
                  id="policy-b-input"
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setPolicyB(e.target.files?.[0] ?? null)}
                  className="hidden"
                />
                {policyB ? (
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                      <FileCheck className="h-6 w-6 text-primary" />
                    </div>
                    <p className="font-medium text-foreground">{policyB.name}</p>
                    <p className="text-xs text-muted-foreground">{(policyB.size / 1024).toFixed(1)} KB</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
                      <Upload className="h-6 w-6 text-muted-foreground" />
                    </div>
                    <p className="font-medium text-muted-foreground">Click to upload Policy B</p>
                    <p className="text-xs text-muted-foreground">PDF or DOCX</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <Button
            onClick={handleRun}
            disabled={!policyA || !policyB || isRunning}
            className="w-full bg-gradient-primary hover:opacity-90"
            size="lg"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Analyzing Policies...
              </>
            ) : (
              <>
                <Scale className="h-4 w-4 mr-2" />
                Compare Policies
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Results Section */}
      {result && (structured || clauseDiff) && (
        <OutputCorrection modelId={modelId ?? "policy-comparison"} prompt={lastPrompt} output={result}>
        {(() => {
          const trend = getPremiumTrend();
          const toggleBar = clauseDiff ? (
            <div className="flex items-center gap-2 flex-wrap">
              <Button
                type="button"
                variant={viewMode === "coverage" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("coverage")}
              >
                Coverage View
              </Button>
              <Button
                type="button"
                variant={viewMode === "clause" ? "default" : "outline"}
                size="sm"
                onClick={() => setViewMode("clause")}
              >
                Clause Redline
              </Button>
            </div>
          ) : null;

          if (viewMode === "clause" && clauseDiff) {
            return (
              <div className="space-y-6 animate-fade-in">
                {toggleBar}
                <PolicyClauseRedlineUI result={result} />
              </div>
            );
          }

          // If coverage parsing fails, prefer the clause redline view (when available).
          // This also ensures TypeScript narrows `parsedResult` for the Coverage JSX below.
          if (!structured) {
            return (
              <div className="space-y-6 animate-fade-in">
                {toggleBar}
                {clauseDiff ? <PolicyClauseRedlineUI result={result} /> : null}
              </div>
            );
          }

          const policyA: any = structured.extracted_fields?.policyA ?? {};
          const policyB: any = structured.extracted_fields?.policyB ?? {};
          const recommendation = structured.recommendation?.recommended_policy ?? "NEITHER";
          const gaps = (structured.recommendation?.rationale ?? structured.warnings ?? []).slice(0, 6);

          return (
        <div className="space-y-6 animate-fade-in">
          {toggleBar}
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Premium Difference</p>
                    <p className="text-2xl font-bold text-foreground">
                      ${trend.diff.toLocaleString()}
                    </p>
                  </div>
                  <div className={`h-10 w-10 rounded-full flex items-center justify-center ${
                    trend.isHigher
                      ? "bg-amber-500/10" 
                      : "bg-green-500/10"
                  }`}>
                    {trend.isHigher ? (
                      <TrendingUp className="h-5 w-5 text-amber-600" />
                    ) : (
                      <TrendingDown className="h-5 w-5 text-green-600" />
                    )}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Policy B is {trend.isHigher ? "higher" : "lower"} by {trend.pct}%
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Coverage Gaps Found</p>
                    <p className="text-2xl font-bold text-foreground">{Math.max(0, gaps.length)}</p>
                  </div>
                  <div className="h-10 w-10 rounded-full bg-destructive/10 flex items-center justify-center">
                    <AlertTriangle className="h-5 w-5 text-destructive" />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Issues requiring attention
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Recommendation</p>
                    <p className="text-2xl font-bold text-foreground">
                      {recommendation === "NEITHER" ? "Review" : `Policy ${recommendation}`}
                    </p>
                  </div>
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <Shield className="h-5 w-5 text-primary" />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Based on coverage analysis
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Side by Side Comparison */}
          <Card className="bg-card border-border overflow-hidden">
            <CardHeader className="bg-gradient-to-r from-primary/5 to-transparent">
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <Scale className="h-5 w-5 text-primary" />
                Side-by-Side Comparison
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="grid grid-cols-3 divide-x divide-border">
                {/* Header Row */}
                <div className="p-4 bg-muted/30 font-medium text-muted-foreground">
                  Coverage Details
                </div>
                <div className="p-4 bg-blue-500/5 text-center">
                  <Badge variant="outline" className="mb-2 text-blue-600 border-blue-600">Policy A</Badge>
                  <p className="text-sm font-medium text-foreground">{String(policyA.carrier ?? policyA.insurer ?? "—")}</p>
                </div>
                <div className="p-4 bg-green-500/5 text-center">
                  <Badge variant="outline" className="mb-2 text-green-600 border-green-600">Policy B</Badge>
                  <p className="text-sm font-medium text-foreground">{String(policyB.carrier ?? policyB.insurer ?? "—")}</p>
                </div>

                {/* Premium Row */}
                <div className="p-4 border-t border-border font-medium flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                  Annual Premium
                </div>
                <div className="p-4 border-t border-border text-center">
                  <span className="text-lg font-bold text-foreground">
                    {typeof policyA.premium === "number" ? `$${policyA.premium.toLocaleString()}` : "—"}
                  </span>
                </div>
                <div className="p-4 border-t border-border text-center">
                  <span className="text-lg font-bold text-foreground">
                    {typeof policyB.premium === "number" ? `$${policyB.premium.toLocaleString()}` : "—"}
                  </span>
                  {typeof policyA.premium === "number" &&
                    typeof policyB.premium === "number" &&
                    policyA.premium > 0 &&
                    policyB.premium > policyA.premium && (
                      <Badge variant="secondary" className="ml-2 text-xs">
                        +{Math.round(((policyB.premium - policyA.premium) / policyA.premium) * 100)}%
                      </Badge>
                    )}
                </div>

                {/* General Liability Row */}
                <div className="p-4 border-t border-border font-medium flex items-center gap-2">
                  <Shield className="h-4 w-4 text-muted-foreground" />
                  General Liability
                </div>
                <div className="p-4 border-t border-border text-center text-foreground">
                  {String(policyA.general_liability ?? policyA.generalLiability ?? policyA.gl_limits ?? "—")}
                </div>
                <div className="p-4 border-t border-border text-center">
                  <span className="text-foreground">
                    {String(policyB.general_liability ?? policyB.generalLiability ?? policyB.gl_limits ?? "—")}
                  </span>
                </div>

                {/* Deductible Row */}
                <div className="p-4 border-t border-border font-medium">Deductible</div>
                <div className="p-4 border-t border-border text-center text-foreground">
                  {typeof policyA.deductible === "number" ? `$${policyA.deductible.toLocaleString()}` : "—"}
                </div>
                <div className="p-4 border-t border-border text-center">
                  <span className="text-foreground">
                    {typeof policyB.deductible === "number" ? `$${policyB.deductible.toLocaleString()}` : "—"}
                  </span>
                </div>

                {/* Cyber Coverage Row */}
                <div className="p-4 border-t border-border font-medium">Cyber Liability</div>
                <div className="p-4 border-t border-border text-center">
                  {renderCoverageIcon(Boolean(policyA.cyber_coverage ?? policyA.cyberCoverage))}
                </div>
                <div className="p-4 border-t border-border text-center">
                  {renderCoverageIcon(Boolean(policyB.cyber_coverage ?? policyB.cyberCoverage))}
                </div>

                {/* EPL Coverage Row */}
                <div className="p-4 border-t border-border font-medium">Employment Practices</div>
                <div className="p-4 border-t border-border text-center">
                  {renderCoverageIcon(Boolean(policyA.epl_coverage ?? policyA.eplCoverage))}
                </div>
                <div className="p-4 border-t border-border text-center">
                  {renderCoverageIcon(Boolean(policyB.epl_coverage ?? policyB.eplCoverage))}
                </div>

                {/* Water Damage Row */}
                <div className="p-4 border-t border-border font-medium">Water Damage</div>
                <div className="p-4 border-t border-border text-center">
                  {renderCoverageIcon(Boolean(policyA.water_damage ?? policyA.waterDamage))}
                </div>
                <div className="p-4 border-t border-border text-center">
                  {renderCoverageIcon(Boolean(policyB.water_damage ?? policyB.waterDamage))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Coverage Gaps */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-amber-500" />
                Coverage Gaps Identified
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {gaps.map((gap) => (
                <div key={gap} className="flex items-start gap-3 p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                  <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-foreground">{gap}</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Consider adding this coverage to reduce exposure
                    </p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Strengths Analysis */}
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                Policy Strengths
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {(structured.recommendation?.rationale ?? []).map((rationale) => (
                  <div 
                    key={rationale} 
                    className="flex items-start gap-3 p-3 rounded-lg border bg-green-500/5 border-green-500/20"
                  >
                    <Badge 
                      variant="outline" 
                      className="text-green-600 border-green-600"
                    >
                      Tip
                    </Badge>
                    <p className="text-sm text-foreground">{rationale}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* AI Recommendation */}
          <Card className="bg-gradient-to-br from-primary/10 via-primary/5 to-transparent border-primary/20">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="h-12 w-12 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                  <Lightbulb className="h-6 w-6 text-primary" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-foreground mb-2">AI Recommendation</h3>
                  <p className="text-muted-foreground">
                    {structured.recommendation?.rationale?.length
                      ? structured.recommendation.rationale.join(" ")
                      : "Recommendation not available; review the clause diff and extracted fields."}
                  </p>
                  <div className="flex items-center gap-2 mt-4">
                    <Badge variant="secondary" className="text-primary">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Recommended: {recommendation === "NEITHER" ? "Review" : `Policy ${recommendation}`}
                    </Badge>
                    <Badge variant="outline">
                      Deviation: {typeof structured.deviation_percent === "number" ? `${structured.deviation_percent.toFixed(1)}%` : "—"}
                    </Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quote Generation Recommendation */}
          {showQuoteRecommendation && (
            <Alert className="border-primary/30 bg-gradient-to-r from-primary/10 to-transparent">
              <Sparkles className="h-5 w-5 text-primary" />
              <AlertTitle className="text-foreground flex items-center gap-2">
                Premium Exceeds ${workflowSettings.policyComparisonPremiumThreshold.toLocaleString()} – Consider Getting New Quotes
              </AlertTitle>
              <AlertDescription className="mt-3">
                <p className="text-muted-foreground mb-4">
                  With premiums at this level, there may be significant savings opportunities by comparing 
                  quotes from multiple carriers. Our Quote Generation Agent can automatically fetch quotes 
                  from 18+ carriers and potentially save you up to <strong className="text-primary">${calculateSavingsPotential().toLocaleString()}/year</strong>.
                </p>
                <div className="flex flex-col sm:flex-row gap-3">
                  <Button 
                    onClick={() => navigate("/playground?model=quote-generation")}
                    className="bg-primary hover:bg-primary/90"
                  >
                    <Sparkles className="h-4 w-4 mr-2" />
                    Generate New Quotes
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Info className="h-4 w-4" />
                    <span>Compare quotes from Travelers, Hartford, Chubb & more</span>
                  </div>
                </div>
              </AlertDescription>
            </Alert>
          )}
        </div>
          );
        })()}
        </OutputCorrection>
      )}
    </div>
  );
}
