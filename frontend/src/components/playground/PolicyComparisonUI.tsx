import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { 
  Upload, 
  FileText, 
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
  ChevronRight,
  Info,
  AlertCircle,
  Sparkles
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useNavigate } from "react-router-dom";
import { useWorkflowSettings } from "@/hooks/useWorkflowSettings";
import OutputCorrection from "./OutputCorrection";

interface PolicyComparisonUIProps {
  modelId?: string;
  onRun: (data: any) => void;
  isRunning: boolean;
  result: string;
}

interface ComparisonResult {
  policyA: {
    name: string;
    carrier: string;
    premium: number;
    generalLiability: string;
    deductible: number;
    cyberCoverage: boolean;
    eplCoverage: boolean;
    waterDamage: boolean;
  };
  policyB: {
    name: string;
    carrier: string;
    premium: number;
    generalLiability: string;
    deductible: number;
    cyberCoverage: boolean;
    eplCoverage: boolean;
    waterDamage: boolean;
  };
  recommendation: "A" | "B";
  gaps: string[];
  strengths: { policy: "A" | "B"; description: string }[];
}

// Parse mock result to structured data
const parseComparisonResult = (result: string): ComparisonResult | null => {
  if (!result || !result.includes("Policy Comparison Analysis")) return null;
  
  // Mock parsed comparison data
  return {
    policyA: {
      name: "Commercial Package GL-2025-001",
      carrier: "Travelers Insurance",
      premium: 8450,
      generalLiability: "$1M/$2M",
      deductible: 5000,
      cyberCoverage: false,
      eplCoverage: false,
      waterDamage: false,
    },
    policyB: {
      name: "Business Protection Plus BP-2025-042",
      carrier: "The Hartford",
      premium: 10562,
      generalLiability: "$2M/$4M",
      deductible: 2500,
      cyberCoverage: true,
      eplCoverage: false,
      waterDamage: true,
    },
    recommendation: "B",
    gaps: [
      "Neither policy includes Employment Practices Liability (EPL)",
      "Policy A missing Cyber Liability coverage",
      "Policy A has water damage exclusion"
    ],
    strengths: [
      { policy: "B", description: "Higher liability limits ($2M/$4M vs $1M/$2M)" },
      { policy: "B", description: "Lower deductible ($2,500 vs $5,000)" },
      { policy: "B", description: "Includes Cyber Liability coverage" },
      { policy: "B", description: "Water damage coverage included" },
      { policy: "A", description: "Lower premium ($8,450 vs $10,562)" }
    ]
  };
};

export default function PolicyComparisonUI({ modelId, onRun, isRunning, result }: PolicyComparisonUIProps) {
  const [policyA, setPolicyA] = useState<File | null>(null);
  const [policyB, setPolicyB] = useState<File | null>(null);
  const [lastPrompt, setLastPrompt] = useState("");
  const navigate = useNavigate();
  const { settings: workflowSettings } = useWorkflowSettings();

  const handleRun = () => {
    if (!policyA || !policyB) return;
    setLastPrompt(`Compare policies: ${policyA.name} vs ${policyB.name}`);
    onRun({
      type: "policy-comparison",
      policyA: policyA.name,
      policyB: policyB.name
    });
  };

  const parsedResult = parseComparisonResult(result);
  const showQuoteRecommendation = workflowSettings.enableSmartRecommendations && parsedResult && 
    (parsedResult.policyA.premium > workflowSettings.policyComparisonPremiumThreshold || 
     parsedResult.policyB.premium > workflowSettings.policyComparisonPremiumThreshold);

  const calculateSavingsPotential = () => {
    if (!parsedResult) return 0;
    const higherPremium = Math.max(parsedResult.policyA.premium, parsedResult.policyB.premium);
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
                onClick={() => document.getElementById("policy-a-input")?.click()}
              >
                <Input
                  id="policy-a-input"
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setPolicyA(e.target.files?.[0] || null)}
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
                onClick={() => document.getElementById("policy-b-input")?.click()}
              >
                <Input
                  id="policy-b-input"
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setPolicyB(e.target.files?.[0] || null)}
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
      {result && parsedResult && (
        <OutputCorrection modelId={modelId || "policy-comparison"} prompt={lastPrompt} output={result}>
        <div className="space-y-6 animate-fade-in">
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Premium Difference</p>
                    <p className="text-2xl font-bold text-foreground">
                      ${Math.abs(parsedResult.policyB.premium - parsedResult.policyA.premium).toLocaleString()}
                    </p>
                  </div>
                  <div className={`h-10 w-10 rounded-full flex items-center justify-center ${
                    parsedResult.policyB.premium > parsedResult.policyA.premium 
                      ? "bg-amber-500/10" 
                      : "bg-green-500/10"
                  }`}>
                    {parsedResult.policyB.premium > parsedResult.policyA.premium ? (
                      <TrendingUp className="h-5 w-5 text-amber-600" />
                    ) : (
                      <TrendingDown className="h-5 w-5 text-green-600" />
                    )}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Policy B is {parsedResult.policyB.premium > parsedResult.policyA.premium ? "higher" : "lower"} by{" "}
                  {Math.round(Math.abs(parsedResult.policyB.premium - parsedResult.policyA.premium) / parsedResult.policyA.premium * 100)}%
                </p>
              </CardContent>
            </Card>

            <Card className="bg-card border-border">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Coverage Gaps Found</p>
                    <p className="text-2xl font-bold text-foreground">{parsedResult.gaps.length}</p>
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
                    <p className="text-2xl font-bold text-foreground">Policy {parsedResult.recommendation}</p>
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
                  <p className="text-sm font-medium text-foreground">{parsedResult.policyA.carrier}</p>
                </div>
                <div className="p-4 bg-green-500/5 text-center">
                  <Badge variant="outline" className="mb-2 text-green-600 border-green-600">Policy B</Badge>
                  <p className="text-sm font-medium text-foreground">{parsedResult.policyB.carrier}</p>
                </div>

                {/* Premium Row */}
                <div className="p-4 border-t border-border font-medium flex items-center gap-2">
                  <DollarSign className="h-4 w-4 text-muted-foreground" />
                  Annual Premium
                </div>
                <div className="p-4 border-t border-border text-center">
                  <span className="text-lg font-bold text-foreground">${parsedResult.policyA.premium.toLocaleString()}</span>
                </div>
                <div className="p-4 border-t border-border text-center">
                  <span className="text-lg font-bold text-foreground">${parsedResult.policyB.premium.toLocaleString()}</span>
                  {parsedResult.policyB.premium > parsedResult.policyA.premium && (
                    <Badge variant="secondary" className="ml-2 text-xs">+{Math.round((parsedResult.policyB.premium - parsedResult.policyA.premium) / parsedResult.policyA.premium * 100)}%</Badge>
                  )}
                </div>

                {/* General Liability Row */}
                <div className="p-4 border-t border-border font-medium flex items-center gap-2">
                  <Shield className="h-4 w-4 text-muted-foreground" />
                  General Liability
                </div>
                <div className="p-4 border-t border-border text-center text-foreground">{parsedResult.policyA.generalLiability}</div>
                <div className="p-4 border-t border-border text-center">
                  <span className="text-foreground">{parsedResult.policyB.generalLiability}</span>
                  <Badge className="ml-2 bg-green-500/20 text-green-600 hover:bg-green-500/30">Better</Badge>
                </div>

                {/* Deductible Row */}
                <div className="p-4 border-t border-border font-medium">Deductible</div>
                <div className="p-4 border-t border-border text-center text-foreground">${parsedResult.policyA.deductible.toLocaleString()}</div>
                <div className="p-4 border-t border-border text-center">
                  <span className="text-foreground">${parsedResult.policyB.deductible.toLocaleString()}</span>
                  <Badge className="ml-2 bg-green-500/20 text-green-600 hover:bg-green-500/30">Lower</Badge>
                </div>

                {/* Cyber Coverage Row */}
                <div className="p-4 border-t border-border font-medium">Cyber Liability</div>
                <div className="p-4 border-t border-border text-center">
                  {parsedResult.policyA.cyberCoverage ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 mx-auto" />
                  ) : (
                    <XCircle className="h-5 w-5 text-destructive mx-auto" />
                  )}
                </div>
                <div className="p-4 border-t border-border text-center">
                  {parsedResult.policyB.cyberCoverage ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 mx-auto" />
                  ) : (
                    <XCircle className="h-5 w-5 text-destructive mx-auto" />
                  )}
                </div>

                {/* EPL Coverage Row */}
                <div className="p-4 border-t border-border font-medium">Employment Practices</div>
                <div className="p-4 border-t border-border text-center">
                  {parsedResult.policyA.eplCoverage ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 mx-auto" />
                  ) : (
                    <XCircle className="h-5 w-5 text-destructive mx-auto" />
                  )}
                </div>
                <div className="p-4 border-t border-border text-center">
                  {parsedResult.policyB.eplCoverage ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 mx-auto" />
                  ) : (
                    <XCircle className="h-5 w-5 text-destructive mx-auto" />
                  )}
                </div>

                {/* Water Damage Row */}
                <div className="p-4 border-t border-border font-medium">Water Damage</div>
                <div className="p-4 border-t border-border text-center">
                  {parsedResult.policyA.waterDamage ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 mx-auto" />
                  ) : (
                    <XCircle className="h-5 w-5 text-destructive mx-auto" />
                  )}
                </div>
                <div className="p-4 border-t border-border text-center">
                  {parsedResult.policyB.waterDamage ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 mx-auto" />
                  ) : (
                    <XCircle className="h-5 w-5 text-destructive mx-auto" />
                  )}
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
              {parsedResult.gaps.map((gap, index) => (
                <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
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
                {parsedResult.strengths.map((strength, index) => (
                  <div 
                    key={index} 
                    className={`flex items-start gap-3 p-3 rounded-lg border ${
                      strength.policy === "A" 
                        ? "bg-blue-500/5 border-blue-500/20" 
                        : "bg-green-500/5 border-green-500/20"
                    }`}
                  >
                    <Badge 
                      variant="outline" 
                      className={strength.policy === "A" ? "text-blue-600 border-blue-600" : "text-green-600 border-green-600"}
                    >
                      {strength.policy}
                    </Badge>
                    <p className="text-sm text-foreground">{strength.description}</p>
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
                    Based on the analysis, <strong className="text-foreground">Policy B</strong> offers superior protection 
                    with higher liability limits, lower deductibles, and comprehensive cyber coverage. 
                    While the premium is 25% higher, the significantly better coverage breadth and 
                    reduced out-of-pocket exposure make it the recommended choice.
                  </p>
                  <div className="flex items-center gap-2 mt-4">
                    <Badge variant="secondary" className="text-primary">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Recommended: Policy B
                    </Badge>
                    <Badge variant="outline">Coverage Score: 92/100</Badge>
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
        </OutputCorrection>
      )}
    </div>
  );
}
