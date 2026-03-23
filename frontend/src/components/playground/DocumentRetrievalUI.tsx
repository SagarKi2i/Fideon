import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { 
  Download, 
  FileText, 
  Loader2, 
  Building2, 
  FolderOpen, 
  CheckCircle2, 
  File,
  FileSpreadsheet,
  FileBadge,
  Receipt,
  ScrollText,
  FileCheck,
  ClipboardList,
  BarChart3,
  Scale,
  Sparkles,
  ArrowRight,
  TrendingUp,
  Info,
  RefreshCw,
  DollarSign
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useWorkflowSettings } from "@/hooks/useWorkflowSettings";

// Import AMS logos
import appliedEpicLogo from "@/assets/logos/applied-epic-logo.png";
import hawksoftLogo from "@/assets/logos/hawksoft-logo.png";
import ams360Logo from "@/assets/logos/ams360-logo.png";
import qqCatalystLogo from "@/assets/logos/qq-catalyst-logo.png";
import ezlynxLogo from "@/assets/logos/ezlynx-logo.png";

interface DocumentRetrievalUIProps {
  onRun: (data: any) => void;
  isRunning: boolean;
  result: string;
}

const documentTypes = [
  { id: "policy-renewal", label: "Policy Renewal", icon: FileCheck },
  { id: "cancellation", label: "Cancellation", icon: File },
  { id: "endorsement", label: "Endorsement", icon: FileBadge },
  { id: "memo", label: "Memo", icon: ScrollText },
  { id: "invoice", label: "Invoice", icon: Receipt },
  { id: "certificate", label: "Certificate", icon: FileSpreadsheet },
  { id: "dec-page", label: "Dec Page", icon: ClipboardList },
  { id: "loss-run", label: "Loss Run", icon: BarChart3 },
];

const carriers = [
  { id: "travelers", name: "Travelers", logo: "🏢" },
  { id: "hartford", name: "The Hartford", logo: "🦌" },
  { id: "chubb", name: "Chubb", logo: "🛡️" },
  { id: "liberty-mutual", name: "Liberty Mutual", logo: "🗽" },
  { id: "nationwide", name: "Nationwide", logo: "🏠" },
  { id: "progressive", name: "Progressive", logo: "📊" },
  { id: "amtrust", name: "AmTrust", logo: "💼" },
  { id: "markel", name: "Markel", logo: "📈" },
  { id: "berkshire", name: "Berkshire", logo: "🏛️" },
  { id: "zurich", name: "Zurich", logo: "🏔️" },
];

const amsOptions = [
  { id: "applied-epic", name: "Applied Epic", logo: appliedEpicLogo },
  { id: "hawksoft", name: "HawkSoft", logo: hawksoftLogo },
  { id: "ams360", name: "AMS 360", logo: ams360Logo },
  { id: "qq-catalyst", name: "QQ Catalyst", logo: qqCatalystLogo },
  { id: "ezlynx", name: "EZLynx", logo: ezlynxLogo },
];

interface RetrievedDocument {
  name: string;
  type: string;
  size: string;
  status: "success" | "pending" | "error";
  amsLocation?: string;
  premium?: number;
  effectiveDate?: string;
  expirationDate?: string;
}

interface RetrievalStats {
  found: number;
  downloaded: number;
  attached: number;
  totalSize: string;
  time: string;
}

interface ParsedRetrievalResult {
  documents: RetrievedDocument[];
  stats: RetrievalStats;
  hasRenewalDocs: boolean;
  hasInvoiceDocs: boolean;
  totalPremium: number;
  daysUntilExpiration: number;
}

// Parse the mock result to extract document data
const parseRetrievalResult = (result: string): ParsedRetrievalResult | null => {
  if (!result?.includes("Document Retrieval Results")) return null;
  
  // Mock parsed documents based on result with enhanced data
  const documents: RetrievedDocument[] = [
    { 
      name: "POL-2025-12345_Renewal_Notice.pdf", 
      type: "Policy Renewal", 
      size: "245 KB", 
      status: "success", 
      amsLocation: "Policies > Documents",
      premium: 12450,
      effectiveDate: "2025-03-01",
      expirationDate: "2026-03-01"
    },
    { 
      name: "POL-2025-12345_Endorsement_AI.pdf", 
      type: "Endorsement", 
      size: "128 KB", 
      status: "success", 
      amsLocation: "Policies > Endorsements" 
    },
    { 
      name: "INV-2025-67890.pdf", 
      type: "Invoice", 
      size: "89 KB", 
      status: "success", 
      amsLocation: "Accounting > Invoices",
      premium: 12450 
    },
    { 
      name: "MEMO-2025-Coverage_Update.pdf", 
      type: "Memo", 
      size: "156 KB", 
      status: "success", 
      amsLocation: "Client > Correspondence" 
    },
  ];

  const hasRenewalDocs = documents.some(d => d.type === "Policy Renewal");
  const hasInvoiceDocs = documents.some(d => d.type === "Invoice");
  const totalPremium = documents.reduce((sum, d) => sum + (d.premium ?? 0), 0) / (documents.filter(d => d.premium).length || 1);
  
  // Calculate days until expiration from renewal doc
  const renewalDoc = documents.find(d => d.expirationDate);
  const daysUntilExpiration = renewalDoc 
    ? Math.ceil((new Date(renewalDoc.expirationDate!).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24))
    : 0;
  
  return {
    documents,
    stats: {
      found: 4,
      downloaded: 4,
      attached: 4,
      totalSize: "618 KB",
      time: "12.3s"
    },
    hasRenewalDocs,
    hasInvoiceDocs,
    totalPremium,
    daysUntilExpiration
  };
};

export default function DocumentRetrievalUI({ onRun, isRunning, result }: DocumentRetrievalUIProps) {
  const navigate = useNavigate();
  const { settings: workflowSettings } = useWorkflowSettings();
  const [selectedCarriers, setSelectedCarriers] = useState<string[]>([]);
  const [selectedAMS, setSelectedAMS] = useState("");
  const [policyNumber, setPolicyNumber] = useState("");
  const [insuredName, setInsuredName] = useState("");
  const [selectedDocTypes, setSelectedDocTypes] = useState<string[]>([]);

  const handleCarrierToggle = (carrierId: string) => {
    setSelectedCarriers(prev =>
      prev.includes(carrierId)
        ? prev.filter(id => id !== carrierId)
        : [...prev, carrierId]
    );
  };

  const handleDocTypeToggle = (docTypeId: string) => {
    setSelectedDocTypes(prev =>
      prev.includes(docTypeId)
        ? prev.filter(id => id !== docTypeId)
        : [...prev, docTypeId]
    );
  };

  const handleRun = () => {
    if (selectedCarriers.length === 0 || !selectedAMS || selectedDocTypes.length === 0) return;
    onRun({
      type: "document-retrieval",
      carriers: selectedCarriers,
      ams: selectedAMS,
      policyNumber,
      insuredName,
      documentTypes: selectedDocTypes
    });
  };

  const isFormValid = selectedCarriers.length > 0 && selectedAMS && selectedDocTypes.length > 0;
  const parsedResult = parseRetrievalResult(result);
  const selectedAMSData = amsOptions.find(a => a.id === selectedAMS);

  return (
    <div className="space-y-6">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <Download className="h-5 w-5" />
            Document Retrieval
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Download documents from carrier websites and attach to your AMS
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Carrier & AMS Selection - Visual Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                Select Carriers
                {selectedCarriers.length > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {selectedCarriers.length} selected
                  </Badge>
                )}
              </Label>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                {carriers.map((carrier) => (
                  <button
                    key={carrier.id}
                    type="button"
                    onClick={() => handleCarrierToggle(carrier.id)}
                    className={`flex flex-col items-center gap-1 p-3 rounded-lg border text-center transition-all relative ${
                      selectedCarriers.includes(carrier.id)
                        ? "border-primary bg-primary/10 ring-1 ring-primary"
                        : "border-border hover:border-primary/50 hover:bg-muted/50"
                    }`}
                  >
                    {selectedCarriers.includes(carrier.id) && (
                      <div className="absolute top-1 right-1">
                        <CheckCircle2 className="h-4 w-4 text-primary" />
                      </div>
                    )}
                    <span className="text-2xl">{carrier.logo}</span>
                    <span className="text-xs font-medium truncate w-full">{carrier.name}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <FolderOpen className="h-4 w-4" />
                Target AMS
              </Label>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                {amsOptions.map((ams) => (
                  <button
                    key={ams.id}
                    type="button"
                    onClick={() => setSelectedAMS(ams.id)}
                    className={`flex flex-col items-center gap-1 p-3 rounded-lg border text-center transition-all ${
                      selectedAMS === ams.id
                        ? "border-primary bg-primary/10 ring-1 ring-primary"
                        : "border-border hover:border-primary/50 hover:bg-muted/50"
                    }`}
                  >
                    <img src={ams.logo.src} alt={`${ams.name} logo`} className="h-8 w-8 object-contain" />
                    <span className="text-xs font-medium truncate w-full">{ams.name}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Policy Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="policy-number">Policy Number (Optional)</Label>
              <Input
                id="policy-number"
                placeholder="e.g., POL-2025-12345"
                value={policyNumber}
                onChange={(e) => setPolicyNumber(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="insured-name">Insured Name (Optional)</Label>
              <Input
                id="insured-name"
                placeholder="e.g., ABC Corporation"
                value={insuredName}
                onChange={(e) => setInsuredName(e.target.value)}
              />
            </div>
          </div>

          {/* Document Type Selection - Compact Grid */}
          <div className="space-y-3">
            <Label>Document Types to Retrieve</Label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {documentTypes.map((docType) => {
                const IconComponent = docType.icon;
                return (
                  <button
                    key={docType.id}
                    type="button"
                    onClick={() => handleDocTypeToggle(docType.id)}
                    className={`flex items-center gap-2 p-3 rounded-lg border cursor-pointer transition-all ${
                      selectedDocTypes.includes(docType.id)
                        ? "border-primary bg-primary/10 ring-1 ring-primary"
                        : "border-border hover:border-primary/50"
                    }`}
                  >
                    <Checkbox
                      checked={selectedDocTypes.includes(docType.id)}
                      onCheckedChange={() => handleDocTypeToggle(docType.id)}
                      className="pointer-events-none"
                    />
                    <IconComponent className="h-4 w-4 flex-shrink-0" />
                    <span className="text-sm font-medium truncate">{docType.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <Button
            onClick={handleRun}
            disabled={!isFormValid || isRunning}
            className="w-full bg-gradient-primary hover:opacity-90"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Retrieving Documents...
              </>
            ) : (
              <>
                <Download className="h-4 w-4 mr-2" />
                Retrieve & Attach to AMS
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Visual Results Display */}
      {result && parsedResult && (
        <div className="space-y-4 animate-fade-in">
          {/* Stats Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <Card className="bg-card border-border">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-primary">{parsedResult.stats.found}</p>
                <p className="text-xs text-muted-foreground">Found</p>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-green-600">{parsedResult.stats.downloaded}</p>
                <p className="text-xs text-muted-foreground">Downloaded</p>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-green-600">{parsedResult.stats.attached}</p>
                <p className="text-xs text-muted-foreground">Attached</p>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-foreground">{parsedResult.stats.totalSize}</p>
                <p className="text-xs text-muted-foreground">Total Size</p>
              </CardContent>
            </Card>
            <Card className="bg-card border-border">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-foreground">{parsedResult.stats.time}</p>
                <p className="text-xs text-muted-foreground">Time</p>
              </CardContent>
            </Card>
          </div>

          {/* Documents List */}
          <Card className="bg-card border-border">
            <CardHeader className="bg-gradient-to-r from-primary/5 to-transparent pb-3">
              <CardTitle className="text-card-foreground flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  Retrieved Documents
                </div>
                <Badge variant="outline" className="text-green-600 border-green-600">
                  <CheckCircle2 className="h-3 w-3 mr-1" />
                  All Attached
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="space-y-3">
                {parsedResult.documents.map((doc) => (
                  <div 
                    key={doc.name}
                    className="flex items-center gap-4 p-4 rounded-lg border border-border bg-muted/30 hover:bg-muted/50 transition-colors"
                  >
                    <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <FileText className="h-6 w-6 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-foreground truncate">{doc.name}</p>
                      <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                        <span>{doc.type}</span>
                        <span>•</span>
                        <span>{doc.size}</span>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <Badge variant="outline" className="text-green-600 border-green-600 mb-1">
                        <CheckCircle2 className="h-3 w-3 mr-1" />
                        Attached
                      </Badge>
                      <p className="text-xs text-muted-foreground">{doc.amsLocation}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* AMS Sync Status */}
          <Card className="bg-card border-border">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {selectedAMSData?.logo && (
                    <img src={selectedAMSData.logo.src} alt={`${selectedAMSData.name} logo`} className="h-10 w-10 object-contain" />
                  )}
                  <div>
                    <p className="font-medium text-foreground">{selectedAMSData?.name}</p>
                    <p className="text-sm text-muted-foreground">Documents synced successfully</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Progress value={100} className="w-24 h-2" />
                  <span className="text-sm font-medium text-green-600">100%</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Smart Recommendations Based on Downloaded Documents */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-foreground flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Smart Recommendations
            </h3>

            {/* Policy Comparison Recommendation - Show if renewal docs downloaded */}
            {parsedResult.hasRenewalDocs && (
              <Alert className="border-blue-500/30 bg-gradient-to-r from-blue-500/10 to-transparent">
                <Scale className="h-5 w-5 text-blue-600" />
                <AlertTitle className="text-foreground flex items-center gap-2">
                  <Badge variant="outline" className="text-blue-600 border-blue-600">Renewal Detected</Badge>
                  Compare Expiring vs. Renewal Policy
                </AlertTitle>
                <AlertDescription className="mt-3">
                  <p className="text-muted-foreground mb-3">
                    We detected a <strong className="text-foreground">Policy Renewal Notice</strong> in the downloaded documents. 
                    Use our Policy Comparison Engine to identify coverage changes, gaps, and ensure you're getting the best terms.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                    <Button 
                      onClick={() => navigate("/playground?model=policy-comparison")}
                      variant="outline"
                      className="border-blue-500/50 text-blue-600 hover:bg-blue-500/10"
                    >
                      <Scale className="h-4 w-4 mr-2" />
                      Compare Policies
                      <ArrowRight className="h-4 w-4 ml-2" />
                    </Button>
                    {parsedResult.daysUntilExpiration > 0 && (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <RefreshCw className="h-4 w-4" />
                        <span>Policy expires in <strong className="text-foreground">{parsedResult.daysUntilExpiration} days</strong></span>
                      </div>
                    )}
                  </div>
                </AlertDescription>
              </Alert>
            )}

            {/* Quote Generation Recommendation - Show if premium exceeds threshold */}
            {workflowSettings.enableSmartRecommendations && parsedResult.hasInvoiceDocs && parsedResult.totalPremium > workflowSettings.documentRetrievalPremiumThreshold && (
              <Alert className="border-primary/30 bg-gradient-to-r from-primary/10 to-transparent">
                <Sparkles className="h-5 w-5 text-primary" />
                <AlertTitle className="text-foreground flex items-center gap-2">
                  <Badge variant="outline" className="text-primary border-primary">High Premium</Badge>
                  Potential Savings Opportunity
                </AlertTitle>
                <AlertDescription className="mt-3">
                  <div className="flex items-center gap-4 mb-3">
                    <div className="flex items-center gap-2">
                      <DollarSign className="h-5 w-5 text-primary" />
                      <span className="text-2xl font-bold text-foreground">${parsedResult.totalPremium.toLocaleString()}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <TrendingUp className="h-4 w-4 text-amber-500" />
                      <span>Current premium from invoice</span>
                    </div>
                  </div>
                  <p className="text-muted-foreground mb-4">
                    With premiums at this level, there may be significant savings opportunities. Our Quote Generation Agent 
                    can compare quotes from <strong className="text-foreground">18+ carriers</strong> and potentially 
                    save <strong className="text-primary">${Math.round(parsedResult.totalPremium * 0.15).toLocaleString()} - ${Math.round(parsedResult.totalPremium * 0.25).toLocaleString()}/year</strong>.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
                    <Button 
                      onClick={() => navigate("/playground?model=quote-generation")}
                      className="bg-primary hover:bg-primary/90"
                    >
                      <Sparkles className="h-4 w-4 mr-2" />
                      Generate Competitive Quotes
                      <ArrowRight className="h-4 w-4 ml-2" />
                    </Button>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Info className="h-4 w-4" />
                      <span>Compare Travelers, Hartford, Chubb & more</span>
                    </div>
                  </div>
                </AlertDescription>
              </Alert>
            )}

            {/* Generic Tip if no specific recommendations */}
            {!parsedResult.hasRenewalDocs && !(workflowSettings.enableSmartRecommendations && parsedResult.hasInvoiceDocs && parsedResult.totalPremium > workflowSettings.documentRetrievalPremiumThreshold) && (
              <Card className="bg-muted/30 border-border">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-foreground">Documents Synced Successfully</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        All retrieved documents have been attached to your AMS. You can now access them 
                        from the client record in {selectedAMSData?.name}.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
