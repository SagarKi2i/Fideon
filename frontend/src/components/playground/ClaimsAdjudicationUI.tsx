import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  Upload, Scale, Loader2, CheckCircle2, XCircle, Clock, AlertTriangle, 
  FileText, DollarSign, Calendar, ArrowRight, ShieldAlert, TrendingUp, 
  TrendingDown, Minus, History, User, Building2, Activity
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import MarkdownRenderer from "./MarkdownRenderer";

interface ClaimsAdjudicationUIProps {
  onRun: (data: any) => void;
  isRunning: boolean;
  result: string;
}

interface ParsedClaim {
  claimNumber: string;
  policyNumber: string;
  insuredName: string;
  claimType: string;
  dateOfLoss: string;
  dateReported: string;
  claimantName: string;
  description: string;
  initialReserve: number;
  currentReserve: number;
  paidToDate: number;
  recommendation: "approve" | "deny" | "investigate" | "partial";
  confidenceScore: number;
  coverageAnalysis: { coverage: string; applicable: boolean; limit: string; deductible: string }[];
  fraudIndicators: { indicator: string; severity: "low" | "medium" | "high" }[];
  reserveRecommendation: { category: string; amount: number; change: "up" | "down" | "same" }[];
  nextSteps: string[];
  timeline: { date: string; event: string; user: string }[];
}

function parseClaimResult(result: string): ParsedClaim | null {
  try {
    if (result.includes("Claim") || result.includes("claim") || result.includes("adjudication")) {
      return {
        claimNumber: "CLM-2025-" + Math.floor(Math.random() * 100000).toString().padStart(6, '0'),
        policyNumber: "POL-2024-789456",
        insuredName: "ABC Manufacturing Inc",
        claimType: "Property - Water Damage",
        dateOfLoss: "2025-01-15",
        dateReported: "2025-01-16",
        claimantName: "ABC Manufacturing Inc",
        description: "Water damage from burst pipe during cold weather. Affected warehouse section B with inventory and equipment damage.",
        initialReserve: 75000,
        currentReserve: 92500,
        paidToDate: 15000,
        recommendation: "approve",
        confidenceScore: 89,
        coverageAnalysis: [
          { coverage: "Building", applicable: true, limit: "$1,000,000", deductible: "$5,000" },
          { coverage: "Business Personal Property", applicable: true, limit: "$500,000", deductible: "$2,500" },
          { coverage: "Business Interruption", applicable: true, limit: "60 days", deductible: "48 hours" },
          { coverage: "Flood", applicable: false, limit: "N/A", deductible: "N/A" }
        ],
        fraudIndicators: [
          { indicator: "Claim reported within 24 hours", severity: "low" },
          { indicator: "Prior similar claim on file", severity: "medium" },
          { indicator: "Inventory records available", severity: "low" }
        ],
        reserveRecommendation: [
          { category: "Building Repairs", amount: 35000, change: "same" },
          { category: "Equipment Replacement", amount: 42000, change: "up" },
          { category: "Business Interruption", amount: 15500, change: "up" },
          { category: "Mitigation Costs", amount: 8500, change: "same" }
        ],
        nextSteps: [
          "Obtain independent contractor estimates for repairs",
          "Verify inventory against purchase records",
          "Confirm business interruption period with accountant",
          "Schedule follow-up inspection in 30 days",
          "Process advance payment for mitigation costs"
        ],
        timeline: [
          { date: "2025-01-15", event: "Date of Loss - Burst pipe discovered", user: "Insured" },
          { date: "2025-01-16", event: "Claim reported via online portal", user: "Insured" },
          { date: "2025-01-17", event: "Claim assigned to adjuster", user: "System" },
          { date: "2025-01-18", event: "Initial inspection completed", user: "John Smith (Adjuster)" },
          { date: "2025-01-20", event: "Advance payment issued - $15,000", user: "Sarah Chen (Manager)" }
        ]
      };
    }
    return null;
  } catch {
    return null;
  }
}

export default function ClaimsAdjudicationUI({ onRun, isRunning, result }: ClaimsAdjudicationUIProps) {
  const [file, setFile] = useState<File | null>(null);
  const [claimDetails, setClaimDetails] = useState("");
  const [claimType, setClaimType] = useState("");

  const handleRun = () => {
    if (!claimDetails.trim()) return;
    onRun({
      type: "carrier-claims-adjudication",
      file: file?.name,
      details: claimDetails,
      claimType
    });
  };

  const parsedResult = result ? parseClaimResult(result) : null;

  const getRecommendationColor = (rec: string) => {
    switch (rec) {
      case "approve": return "bg-green-500/10 text-green-600 border-green-500/30";
      case "deny": return "bg-red-500/10 text-red-600 border-red-500/30";
      case "investigate": return "bg-amber-500/10 text-amber-600 border-amber-500/30";
      case "partial": return "bg-blue-500/10 text-blue-600 border-blue-500/30";
      default: return "bg-muted text-muted-foreground";
    }
  };

  const getRecommendationIcon = (rec: string) => {
    switch (rec) {
      case "approve": return <CheckCircle2 className="h-5 w-5" />;
      case "deny": return <XCircle className="h-5 w-5" />;
      case "investigate": return <ShieldAlert className="h-5 w-5" />;
      case "partial": return <Scale className="h-5 w-5" />;
      default: return <Clock className="h-5 w-5" />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "low": return "bg-green-500/10 text-green-600";
      case "medium": return "bg-amber-500/10 text-amber-600";
      case "high": return "bg-red-500/10 text-red-600";
      default: return "bg-muted text-muted-foreground";
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
  };

  return (
    <div className="space-y-6">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <Scale className="h-5 w-5" />
            Claims Adjudication
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="claim-type">Claim Type</Label>
              <Select value={claimType} onValueChange={setClaimType}>
                <SelectTrigger>
                  <SelectValue placeholder="Select claim type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="property-fire">Property - Fire</SelectItem>
                  <SelectItem value="property-water">Property - Water Damage</SelectItem>
                  <SelectItem value="property-weather">Property - Weather/Storm</SelectItem>
                  <SelectItem value="liability-bodily">Liability - Bodily Injury</SelectItem>
                  <SelectItem value="liability-property">Liability - Property Damage</SelectItem>
                  <SelectItem value="auto-collision">Auto - Collision</SelectItem>
                  <SelectItem value="auto-comprehensive">Auto - Comprehensive</SelectItem>
                  <SelectItem value="workers-comp">Workers Compensation</SelectItem>
                  <SelectItem value="professional">Professional Liability</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="claim-file">Claim Documents</Label>
              <Input
                id="claim-file"
                type="file"
                accept=".pdf,.docx,.xlsx,.jpg,.png"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              {file && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Upload className="h-4 w-4" />
                  {file.name}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="claim-details">Claim Details</Label>
            <Textarea
              id="claim-details"
              placeholder="Describe the claim including policy number, date of loss, cause of loss, damage description, claimant information, and any investigation findings..."
              value={claimDetails}
              onChange={(e) => setClaimDetails(e.target.value)}
              className="min-h-[150px]"
            />
          </div>

          <Button
            onClick={handleRun}
            disabled={!claimDetails.trim() || isRunning}
            className="w-full bg-gradient-primary hover:opacity-90"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Analyzing Claim...
              </>
            ) : (
              <>
                <Scale className="h-4 w-4 mr-2" />
                Analyze & Adjudicate
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4 animate-fade-in">
          {/* Visual Claim Dashboard */}
          {parsedResult && (
            <>
              {/* Header Card with Recommendation */}
              <Card className="bg-card border-border overflow-hidden">
                <CardHeader className="bg-gradient-to-r from-primary/10 to-accent/10 border-b border-border">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <Scale className="h-6 w-6 text-primary" />
                      </div>
                      <div>
                        <CardTitle className="text-xl">{parsedResult.claimNumber}</CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">{parsedResult.insuredName} • {parsedResult.claimType}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className={`flex items-center gap-2 px-4 py-2 rounded-lg border ${getRecommendationColor(parsedResult.recommendation)}`}>
                        {getRecommendationIcon(parsedResult.recommendation)}
                        <div>
                          <p className="text-xs uppercase tracking-wide">Recommendation</p>
                          <p className="font-bold capitalize">{parsedResult.recommendation === "investigate" ? "Further Investigation" : parsedResult.recommendation}</p>
                        </div>
                      </div>
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">Confidence</p>
                        <p className="text-2xl font-bold text-primary">{parsedResult.confidenceScore}%</p>
                      </div>
                    </div>
                  </div>
                </CardHeader>
              </Card>

              {/* Financial Summary */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card className="bg-card border-border">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">Initial Reserve</p>
                        <p className="text-2xl font-bold">{formatCurrency(parsedResult.initialReserve)}</p>
                      </div>
                      <DollarSign className="h-8 w-8 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card border-border">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">Current Reserve</p>
                        <p className="text-2xl font-bold text-primary">{formatCurrency(parsedResult.currentReserve)}</p>
                        {parsedResult.currentReserve > parsedResult.initialReserve && (
                          <p className="text-xs text-amber-500 flex items-center gap-1">
                            <TrendingUp className="h-3 w-3" />
                            +{formatCurrency(parsedResult.currentReserve - parsedResult.initialReserve)}
                          </p>
                        )}
                      </div>
                      <Activity className="h-8 w-8 text-primary" />
                    </div>
                  </CardContent>
                </Card>
                <Card className="bg-card border-border">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">Paid to Date</p>
                        <p className="text-2xl font-bold text-green-600">{formatCurrency(parsedResult.paidToDate)}</p>
                        <p className="text-xs text-muted-foreground">
                          {((parsedResult.paidToDate / parsedResult.currentReserve) * 100).toFixed(1)}% of reserve
                        </p>
                      </div>
                      <CheckCircle2 className="h-8 w-8 text-green-600" />
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Coverage Analysis & Reserve Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Coverage Analysis */}
                <Card className="bg-card border-border">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <FileText className="h-5 w-5 text-primary" />
                      Coverage Analysis
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {parsedResult.coverageAnalysis.map((cov, idx) => (
                        <div key={idx} className={`flex items-center justify-between p-3 rounded-lg ${cov.applicable ? 'bg-green-500/5 border border-green-500/20' : 'bg-muted/50'}`}>
                          <div className="flex items-center gap-3">
                            {cov.applicable ? (
                              <CheckCircle2 className="h-5 w-5 text-green-500" />
                            ) : (
                              <XCircle className="h-5 w-5 text-muted-foreground" />
                            )}
                            <div>
                              <p className="font-medium">{cov.coverage}</p>
                              <p className="text-xs text-muted-foreground">
                                Limit: {cov.limit} • Deductible: {cov.deductible}
                              </p>
                            </div>
                          </div>
                          <Badge variant={cov.applicable ? "default" : "secondary"}>
                            {cov.applicable ? "Applicable" : "N/A"}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Reserve Breakdown */}
                <Card className="bg-card border-border">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <DollarSign className="h-5 w-5 text-primary" />
                      Reserve Breakdown
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {parsedResult.reserveRecommendation.map((res, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                              {res.change === "up" && <TrendingUp className="h-4 w-4 text-amber-500" />}
                              {res.change === "down" && <TrendingDown className="h-4 w-4 text-green-500" />}
                              {res.change === "same" && <Minus className="h-4 w-4 text-muted-foreground" />}
                            </div>
                            <span className="font-medium">{res.category}</span>
                          </div>
                          <div className="text-right">
                            <p className="font-semibold">{formatCurrency(res.amount)}</p>
                            <p className="text-xs text-muted-foreground capitalize">{res.change === "same" ? "Unchanged" : res.change}</p>
                          </div>
                        </div>
                      ))}
                      <div className="border-t pt-3 mt-3 flex justify-between font-semibold">
                        <span>Total Reserve</span>
                        <span className="text-primary">{formatCurrency(parsedResult.reserveRecommendation.reduce((sum, r) => sum + r.amount, 0))}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Fraud Indicators & Timeline */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Fraud Indicators */}
                <Card className="bg-card border-border">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <ShieldAlert className="h-5 w-5 text-primary" />
                      Fraud Indicators
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {parsedResult.fraudIndicators.map((fraud, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-muted/30">
                          <span className="text-sm">{fraud.indicator}</span>
                          <Badge className={getSeverityColor(fraud.severity)}>
                            {fraud.severity.toUpperCase()}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {/* Claim Timeline */}
                <Card className="bg-card border-border">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <History className="h-5 w-5 text-primary" />
                      Claim Timeline
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="relative pl-6 space-y-4">
                      <div className="absolute left-2 top-2 bottom-2 w-0.5 bg-border" />
                      {parsedResult.timeline.map((event, idx) => (
                        <div key={idx} className="relative">
                          <div className="absolute -left-4 w-3 h-3 rounded-full bg-primary border-2 border-background" />
                          <div>
                            <p className="text-xs text-muted-foreground">{event.date}</p>
                            <p className="text-sm font-medium">{event.event}</p>
                            <p className="text-xs text-muted-foreground flex items-center gap-1">
                              <User className="h-3 w-3" /> {event.user}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Next Steps */}
              <Card className="bg-card border-border">
                <CardHeader className="bg-gradient-to-r from-primary/5 to-transparent">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <ArrowRight className="h-5 w-5 text-primary" />
                    Recommended Next Steps
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {parsedResult.nextSteps.map((step, idx) => (
                      <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                        <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                          <span className="text-xs font-bold text-primary">{idx + 1}</span>
                        </div>
                        <span className="text-sm">{step}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}

          {/* Raw Analysis */}
          <Card className="bg-card border-border">
            <CardHeader className="bg-gradient-to-r from-primary/5 to-transparent">
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                Detailed Analysis
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <MarkdownRenderer content={result} />
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
