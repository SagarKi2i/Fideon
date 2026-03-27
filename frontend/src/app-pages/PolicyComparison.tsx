import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Shield, ArrowLeftRight, AlertCircle } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { Badge } from "@/components/ui/badge";

interface Document {
  id: string;
  filename: string;
  file_type: string;
}

function getCoverageStatusBadge(status: string): { variant: "default" | "secondary"; label: string; className: string } {
  if (status === "increased") {
    return { variant: "default", label: "Changed", className: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20" };
  }
  return { variant: "secondary", label: "Same", className: "" };
}

function getExclusionStatusBadge(status: string): { variant: "destructive" | "secondary"; label: string } {
  if (status === "removed") return { variant: "destructive", label: "Added Exclusion" };
  return { variant: "secondary", label: "No Change" };
}

export default function PolicyComparison() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [policyA, setPolicyA] = useState<string>("");
  const [policyB, setPolicyB] = useState<string>("");
  const [comparing, setComparing] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<any>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        setDocuments([]);
        return;
      }
      const { data, error } = await supabase
        .from("documents")
        .select("id, filename, file_type")
        .eq("user_id", user.id)
        .or("file_type.eq.application/pdf,file_type.ilike.%word%");

      if (error) throw error;
      setDocuments(data ?? []);
    } catch (error) {
      console.error("Error loading documents:", error);
    }
  };

  const handleCompare = async () => {
    if (!policyA || !policyB) {
      toast({
        title: "Missing Selection",
        description: "Please select both policies to compare.",
        variant: "destructive",
      });
      return;
    }

    if (policyA === policyB) {
      toast({
        title: "Same Policy",
        description: "Please select two different policies.",
        variant: "destructive",
      });
      return;
    }

    setComparing(true);

    try {
      // Mock comparison result (in a real implementation, this would call an AI service)
      setTimeout(() => {
        setComparisonResult({
          coverage_differences: [
            { item: "Property Damage Liability", policyA: "$100,000", policyB: "$150,000", status: "increased" },
            { item: "Bodily Injury Liability", policyA: "$250,000/$500,000", policyB: "$250,000/$500,000", status: "same" },
            { item: "Comprehensive Deductible", policyA: "$500", policyB: "$1,000", status: "increased" },
          ],
          exclusions: [
            { item: "Earthquake Coverage", policyA: true, policyB: false, status: "removed" },
            { item: "Flood Coverage", policyA: false, policyB: false, status: "same" },
          ],
          key_changes: [
            "Property damage liability limit increased by $50,000",
            "Comprehensive deductible increased from $500 to $1,000",
            "Earthquake coverage exclusion added",
          ],
        });
        setComparing(false);
      }, 2000);
    } catch (error) {
      console.error("Error comparing policies:", error);
      toast({
        title: "Comparison Failed",
        description: "Failed to compare policies. Please try again.",
        variant: "destructive",
      });
      setComparing(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Policy Comparison</h1>
        <p className="text-muted-foreground mt-1">
          Compare insurance policies side-by-side with AI analysis
        </p>
      </div>

      {/* Selection Card */}
      <Card className="bg-card border-border shadow-card">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Select Policies
          </CardTitle>
          <CardDescription>Choose two insurance policy documents to compare</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="policy-a-select" className="text-sm font-medium text-foreground">Policy A</Label>
              <Select value={policyA} onValueChange={setPolicyA}>
                <SelectTrigger id="policy-a-select">
                  <SelectValue placeholder="Select first policy" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map((doc) => (
                    <SelectItem key={doc.id} value={doc.id}>
                      {doc.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="policy-b-select" className="text-sm font-medium text-foreground">Policy B</Label>
              <Select value={policyB} onValueChange={setPolicyB}>
                <SelectTrigger id="policy-b-select">
                  <SelectValue placeholder="Select second policy" />
                </SelectTrigger>
                <SelectContent>
                  {documents.map((doc) => (
                    <SelectItem key={doc.id} value={doc.id}>
                      {doc.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button
            className="w-full mt-6 bg-gradient-primary hover:opacity-90 transition-opacity"
            onClick={handleCompare}
            disabled={comparing || !policyA || !policyB}
          >
            <ArrowLeftRight className="h-4 w-4 mr-2" />
            {comparing ? "Analyzing..." : "Compare Coverage"}
          </Button>
        </CardContent>
      </Card>

      {/* Results */}
      {comparisonResult && (
        <>
          {/* Coverage Differences */}
          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground">Coverage Differences</CardTitle>
              <CardDescription>Comparison of coverage limits and deductibles</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {comparisonResult.coverage_differences.map((item: any) => {
                  const badge = getCoverageStatusBadge(item.status);
                  return (
                  <div key={`${item.item}-${item.policyA}-${item.policyB}`} className="flex items-center justify-between p-3 rounded-lg border border-border">
                    <div className="flex-1">
                      <p className="font-medium text-foreground">{item.item}</p>
                      <div className="flex items-center gap-4 mt-1">
                        <span className="text-sm text-muted-foreground">Policy A: {item.policyA}</span>
                        <span className="text-sm text-muted-foreground">→</span>
                        <span className="text-sm text-muted-foreground">Policy B: {item.policyB}</span>
                      </div>
                    </div>
                    <Badge
                      variant={badge.variant}
                      className={badge.className}
                    >
                      {badge.label}
                    </Badge>
                  </div>
                )})}
              </div>
            </CardContent>
          </Card>

          {/* Exclusions */}
          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground">Exclusions Comparison</CardTitle>
              <CardDescription>Changes in policy exclusions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {comparisonResult.exclusions.map((item: any) => {
                  const badge = getExclusionStatusBadge(item.status);
                  return (
                  <div key={`${item.item}-${item.policyA}-${item.policyB}`} className="flex items-center justify-between p-3 rounded-lg border border-border">
                    <div className="flex-1">
                      <p className="font-medium text-foreground">{item.item}</p>
                      <div className="flex items-center gap-4 mt-1">
                        <span className="text-sm text-muted-foreground">
                          Policy A: {item.policyA ? "Excluded" : "Covered"}
                        </span>
                        <span className="text-sm text-muted-foreground">→</span>
                        <span className="text-sm text-muted-foreground">
                          Policy B: {item.policyB ? "Excluded" : "Covered"}
                        </span>
                      </div>
                    </div>
                    <Badge
                      variant={badge.variant}
                    >
                      {badge.label}
                    </Badge>
                  </div>
                )})}
              </div>
            </CardContent>
          </Card>

          {/* Key Changes */}
          <Card className="bg-card border-border shadow-card">
            <CardHeader>
              <CardTitle className="text-card-foreground flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-primary" />
                Key Changes Summary
              </CardTitle>
              <CardDescription>Important differences to review</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {comparisonResult.key_changes.map((change: string, index: number) => (
                  <li key={`${change}-${index}`} className="flex items-start gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary mt-2 flex-shrink-0" />
                    <p className="text-sm text-foreground">{change}</p>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </>
      )}

      {!comparisonResult && documents.length === 0 && (
        <Card className="bg-card border-border shadow-card">
          <CardContent className="text-center py-12">
            <Shield className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-medium text-foreground mb-2">No Documents Available</h3>
            <p className="text-muted-foreground max-w-sm mx-auto mb-6">
              Upload policy documents first to use the comparison tool
            </p>
            <Button onClick={() => window.location.href = "/documents"}>
              Go to Documents
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
