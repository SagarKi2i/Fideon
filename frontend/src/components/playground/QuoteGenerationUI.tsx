import { useState, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { 
  Loader2, 
  Globe, 
  FileText, 
  RefreshCw, 
  Scale, 
  CheckCircle2,
  Clock,
  DollarSign,
  AlertCircle,
  ArrowRight,
  Bot,
  Shield,
  Calendar,
  MapPin,
  Phone,
  Mail,
  User,
  Briefcase,
  Award,
  CheckSquare,
  FileCheck,
  Download,
  Eye
} from "lucide-react";
import QuoteComparisonAnalysis from "./QuoteComparisonAnalysis";
import EmailPreviewDialog from "./EmailPreviewDialog";
import PolicyCoverageDetails from "./PolicyCoverageDetails";
import jsPDF from "jspdf";

interface QuoteGenerationUIProps {
  readonly onRun: (data: any) => void;
  readonly isRunning: boolean;
  readonly result: string;
}

interface CarrierQuote {
  carrier: string;
  logo: string;
  premium: number;
  coverage: string;
  deductible: number;
  status: "pending" | "fetching" | "complete" | "error";
  features: string[];
  rating?: number;
  claimsScore?: number;
  financialStrength?: string;
}

const CARRIERS = [
  { id: "progressive", name: "Progressive" },
  { id: "geico", name: "GEICO" },
  { id: "state-farm", name: "State Farm" },
  { id: "allstate", name: "Allstate" },
  { id: "liberty-mutual", name: "Liberty Mutual" },
  { id: "travelers", name: "Travelers" },
  { id: "nationwide", name: "Nationwide" },
  { id: "farmers", name: "Farmers Insurance" },
  { id: "usaa", name: "USAA" },
  { id: "american-family", name: "American Family" },
  { id: "hartford", name: "The Hartford" },
  { id: "chubb", name: "Chubb" },
  { id: "aig", name: "AIG" },
  { id: "zurich", name: "Zurich" },
  { id: "hanover", name: "The Hanover" },
  { id: "cincinnati", name: "Cincinnati Insurance" },
  { id: "erie", name: "Erie Insurance" },
  { id: "auto-owners", name: "Auto-Owners" },
];

const INSURANCE_TYPES = [
  { id: "auto", name: "Auto Insurance" },
  { id: "home", name: "Homeowners Insurance" },
  { id: "commercial", name: "Commercial Property" },
  { id: "general-liability", name: "General Liability" },
  { id: "workers-comp", name: "Workers Compensation" },
  { id: "professional-liability", name: "Professional Liability" },
];

export default function QuoteGenerationUI({ onRun, isRunning, result }: QuoteGenerationUIProps) {
  const { toast } = useToast();
  const hasExternalResult = result.trim().length > 0;
  const [step, setStep] = useState<"input" | "fetching" | "compare" | "proposal">("input");
  const [insuranceType, setInsuranceType] = useState("");
  const [selectedCarriers, setSelectedCarriers] = useState<string[]>([]);
  const [applicantInfo, setApplicantInfo] = useState({
    name: "",
    businessName: "",
    email: "",
    phone: "",
    address: "",
    coverageAmount: "",
  });
  const [quotes, setQuotes] = useState<CarrierQuote[]>([]);
  const [selectedQuote, setSelectedQuote] = useState<string | null>(null);
  const [fetchProgress, setFetchProgress] = useState(0);
  const [currentCarrier, setCurrentCarrier] = useState("");
  const [showEmailPreview, setShowEmailPreview] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  const getProposalNumber = () => `PROP-${Date.now().toString(36).toUpperCase()}`;
  const proposalNumber = useRef(getProposalNumber());

  const today = new Date();
  const effectiveDate = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000);

  const handleSendProposal = () => {
    setShowEmailPreview(false);
    toast({
      title: "✅ Proposal Sent Successfully!",
        description: `The insurance proposal has been sent to ${applicantInfo.email ?? applicantInfo.name ?? 'the insured'}.`,
    });
  };

  const handleExportPdf = async () => {
    const quote = quotes.find(q => q.carrier === selectedQuote);
    if (!quote) return;

    setIsExportingPdf(true);
    
    try {
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pageWidth = pdf.internal.pageSize.getWidth();
      const margin = 20;
      let yPos = 20;

      // Header
      pdf.setFillColor(59, 130, 246);
      pdf.rect(0, 0, pageWidth, 40, 'F');
      pdf.setTextColor(255, 255, 255);
      pdf.setFontSize(24);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Insurance Proposal', margin, 25);
      pdf.setFontSize(12);
      pdf.setFont('helvetica', 'normal');
      pdf.text(`Proposal #: ${proposalNumber.current}`, margin, 35);
      pdf.text(`Date: ${today.toLocaleDateString()}`, pageWidth - margin - 50, 35);

      yPos = 55;
      pdf.setTextColor(0, 0, 0);

      // Carrier Info
      pdf.setFontSize(16);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Carrier Information', margin, yPos);
      yPos += 10;
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'normal');
      pdf.text(`Carrier: ${quote.carrier}`, margin, yPos);
      yPos += 7;
      pdf.text(`Insurance Type: ${INSURANCE_TYPES.find(t => t.id === insuranceType)?.name || insuranceType}`, margin, yPos);
      yPos += 15;

      // Premium Details
      pdf.setFontSize(16);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Premium & Coverage Details', margin, yPos);
      yPos += 10;
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'normal');
      pdf.text(`Annual Premium: $${quote.premium.toLocaleString()}`, margin, yPos);
      yPos += 7;
      pdf.text(`Monthly Payment: $${Math.round(quote.premium / 12).toLocaleString()}/mo`, margin, yPos);
      yPos += 7;
      pdf.text(`Coverage Limit: ${quote.coverage}`, margin, yPos);
      yPos += 7;
      pdf.text(`Deductible: $${quote.deductible.toLocaleString()}`, margin, yPos);
      yPos += 7;
      pdf.text(`Policy Term: 12 Months`, margin, yPos);
      yPos += 15;

      // Policy Period
      pdf.setFontSize(16);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Policy Period', margin, yPos);
      yPos += 10;
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'normal');
      pdf.text(`Effective Date: ${effectiveDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`, margin, yPos);
      yPos += 7;
      const expirationDate = new Date(effectiveDate.getTime() + 365 * 24 * 60 * 60 * 1000);
      pdf.text(`Expiration Date: ${expirationDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`, margin, yPos);
      yPos += 15;

      // Insured Information
      pdf.setFontSize(16);
      pdf.setFont('helvetica', 'bold');
      pdf.text('Named Insured', margin, yPos);
      yPos += 10;
      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'normal');
      pdf.text(`Name: ${applicantInfo.name || 'N/A'}`, margin, yPos);
      yPos += 7;
      if (applicantInfo.businessName) {
        pdf.text(`Business: ${applicantInfo.businessName}`, margin, yPos);
        yPos += 7;
      }
      pdf.text(`Email: ${applicantInfo.email || 'N/A'}`, margin, yPos);
      yPos += 7;
      pdf.text(`Phone: ${applicantInfo.phone || 'N/A'}`, margin, yPos);
      yPos += 7;
      pdf.text(`Address: ${applicantInfo.address || 'N/A'}`, margin, yPos);
      yPos += 15;

      // Features
      if (quote.features.length > 0) {
        pdf.setFontSize(16);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Included Benefits', margin, yPos);
        yPos += 10;
        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'normal');
        quote.features.forEach(feature => {
          pdf.text(`• ${feature}`, margin, yPos);
          yPos += 6;
        });
        pdf.text(`• 24/7 Customer Support`, margin, yPos);
        yPos += 6;
        pdf.text(`• Online Policy Management`, margin, yPos);
        yPos += 15;
      }

      // Footer
      pdf.setFillColor(245, 245, 245);
      pdf.rect(0, 270, pageWidth, 30, 'F');
      pdf.setFontSize(9);
      pdf.setTextColor(100, 100, 100);
      pdf.text('This proposal is valid for 30 days from the date of issue.', margin, 280);
      pdf.text(`Document ID: ${proposalNumber.current} | Generated by AI Quote Agent`, margin, 286);

      pdf.save(`Insurance_Proposal_${proposalNumber.current}.pdf`);

      toast({
        title: "📄 PDF Exported Successfully!",
        description: "The proposal has been downloaded to your device.",
      });
    } catch (error) {
      console.error('Error exporting PDF:', error);
      toast({
        title: "Export Failed",
        description: "There was an error exporting the PDF. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsExportingPdf(false);
    }
  };

  const toggleCarrier = (carrierId: string) => {
    setSelectedCarriers(prev => 
      prev.includes(carrierId) 
        ? prev.filter(c => c !== carrierId)
        : [...prev, carrierId]
    );
  };
  const getFetchingStatusClass = (status: CarrierQuote["status"]) => {
    if (status === "complete") return "border-green-500/50 bg-green-500/5";
    if (status === "fetching") return "border-primary/50 bg-primary/5";
    return "border-border";
  };

  const simulateFetchQuotes = async () => {
    if (!insuranceType || selectedCarriers.length === 0) return;

    setStep("fetching");
    setFetchProgress(0);
    setQuotes([]);

    const initialQuotes: CarrierQuote[] = selectedCarriers.map(carrierId => {
      const carrier = CARRIERS.find(c => c.id === carrierId);
      return {
        carrier: carrier?.name || carrierId,
        logo: "shield",
        premium: 0,
        coverage: "",
        deductible: 0,
        status: "pending" as const,
        features: [],
      };
    });
    setQuotes(initialQuotes);

    // Simulate fetching from each carrier
    for (let i = 0; i < selectedCarriers.length; i++) {
      const carrier = CARRIERS.find(c => c.id === selectedCarriers[i]);
      if (!carrier) continue;

      setCurrentCarrier(carrier.name);
      
      // Update status to fetching
      setQuotes(prev => prev.map((q, idx) => 
        idx === i ? { ...q, status: "fetching" as const } : q
      ));

      // Simulate navigation and form filling delay
      await new Promise(resolve => setTimeout(resolve, 1500 + Math.random() * 1000));

      // Generate mock quote data
      const mockQuote: CarrierQuote = {
        carrier: carrier.name,
        logo: "shield",
        premium: Math.floor(1200 + Math.random() * 3000),
        coverage: `$${(parseInt(applicantInfo.coverageAmount) || 500000).toLocaleString()}`,
        deductible: [500, 1000, 1500, 2000, 2500][Math.floor(Math.random() * 5)],
        status: "complete" as const,
        features: [
          "24/7 Claims Support",
          Math.random() > 0.5 ? "Multi-policy Discount" : "New Customer Discount",
          Math.random() > 0.5 ? "Paperless Billing Discount" : "Autopay Discount",
          Math.random() > 0.3 ? "Accident Forgiveness" : "Roadside Assistance",
        ].slice(0, 2 + Math.floor(Math.random() * 2)),
      };

      setQuotes(prev => prev.map((q, idx) => 
        idx === i ? mockQuote : q
      ));

      setFetchProgress(((i + 1) / selectedCarriers.length) * 100);
    }

    setCurrentCarrier("");
    setStep("compare");

    // Call the AI for analysis
    onRun({
      type: "quote-generation",
      action: "compare",
      insuranceType,
      applicantInfo,
      carriers: selectedCarriers,
    });
  };

  const generateProposal = () => {
    if (!selectedQuote) return;
    
    const quote = quotes.find(q => q.carrier === selectedQuote);
    if (!quote) return;

    setStep("proposal");
    
    onRun({
      type: "quote-generation",
      action: "generate-proposal",
      insuranceType,
      applicantInfo,
      selectedQuote: quote,
    });
  };

  const resetFlow = () => {
    setStep("input");
    setQuotes([]);
    setSelectedQuote(null);
    setFetchProgress(0);
  };

  const renderInputStep = () => (
    <div className="space-y-6">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            Quote Generation Agent
          </CardTitle>
          <CardDescription>
            Automatically navigate carrier websites, apply for quotes, and compare results
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Insurance Type */}
          <div className="space-y-2">
            <Label>Insurance Type</Label>
            <Select value={insuranceType} onValueChange={setInsuranceType}>
              <SelectTrigger>
                <SelectValue placeholder="Select insurance type" />
              </SelectTrigger>
              <SelectContent>
                {INSURANCE_TYPES.map(type => (
                  <SelectItem key={type.id} value={type.id}>
                    {type.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Applicant Information */}
          <div className="space-y-4">
            <Label className="text-base font-semibold">Applicant Information</Label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Full Name</Label>
                <Input
                  id="name"
                  placeholder="John Doe"
                  value={applicantInfo.name}
                  onChange={(e) => setApplicantInfo(prev => ({ ...prev, name: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="business">Business Name (if applicable)</Label>
                <Input
                  id="business"
                  placeholder="Acme Corp"
                  value={applicantInfo.businessName}
                  onChange={(e) => setApplicantInfo(prev => ({ ...prev, businessName: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="john@example.com"
                  value={applicantInfo.email}
                  onChange={(e) => setApplicantInfo(prev => ({ ...prev, email: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <Input
                  id="phone"
                  placeholder="(555) 123-4567"
                  value={applicantInfo.phone}
                  onChange={(e) => setApplicantInfo(prev => ({ ...prev, phone: e.target.value }))}
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="address">Address</Label>
                <Input
                  id="address"
                  placeholder="123 Main St, City, State ZIP"
                  value={applicantInfo.address}
                  onChange={(e) => setApplicantInfo(prev => ({ ...prev, address: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="coverage">Desired Coverage Amount</Label>
                <Input
                  id="coverage"
                  placeholder="500000"
                  value={applicantInfo.coverageAmount}
                  onChange={(e) => setApplicantInfo(prev => ({ ...prev, coverageAmount: e.target.value }))}
                />
              </div>
            </div>
          </div>

          <Separator />

          {/* Carrier Selection */}
          <div className="space-y-4">
            <Label className="text-base font-semibold">Select Carriers to Quote</Label>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {CARRIERS.map(carrier => (
                <div
                  key={carrier.id}
                  onClick={() => toggleCarrier(carrier.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggleCarrier(carrier.id);
                  }
                }}
                role="button"
                tabIndex={0}
                aria-pressed={selectedCarriers.includes(carrier.id)}
                  className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${
                    selectedCarriers.includes(carrier.id)
                      ? "border-primary bg-primary/10"
                      : "border-border hover:border-muted-foreground"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-primary/10">
                      <Shield className="h-5 w-5 text-primary" />
                    </div>
                    <span className="font-medium text-sm">{carrier.name}</span>
                  </div>
                  {selectedCarriers.includes(carrier.id) && (
                    <CheckCircle2 className="h-4 w-4 text-primary mt-2" />
                  )}
                </div>
              ))}
            </div>
            {selectedCarriers.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {selectedCarriers.length} carrier(s) selected
              </p>
            )}
          </div>

          <Button
            onClick={simulateFetchQuotes}
            disabled={!insuranceType || selectedCarriers.length === 0 || !applicantInfo.name || isRunning}
            className="w-full bg-gradient-primary hover:opacity-90"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Globe className="h-4 w-4 mr-2" />
                Fetch Quotes from Carriers
              </>
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  const renderFetchingStep = () => (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <RefreshCw className="h-5 w-5 text-primary animate-spin" />
          Fetching Quotes
        </CardTitle>
        <CardDescription>
          The agent is navigating carrier websites and applying for quotes...
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Overall Progress</span>
            <span>{Math.round(fetchProgress)}%</span>
          </div>
          <Progress value={fetchProgress} className="h-2" />
          {currentCarrier && (
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              <Globe className="h-4 w-4 animate-pulse" />
              Currently fetching from {currentCarrier}...
            </p>
          )}
        </div>

        <div className="space-y-3">
          {quotes.map((quote) => (
            <div
              key={quote.carrier}
              className={`p-4 rounded-lg border ${getFetchingStatusClass(quote.status)}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-primary/10">
                    <Shield className="h-5 w-5 text-primary" />
                  </div>
                  <span className="font-medium">{quote.carrier}</span>
                </div>
                <div className="flex items-center gap-2">
                  {quote.status === "pending" && (
                    <Badge variant="outline" className="text-muted-foreground">
                      <Clock className="h-3 w-3 mr-1" />
                      Pending
                    </Badge>
                  )}
                  {quote.status === "fetching" && (
                    <Badge variant="outline" className="text-primary">
                      <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                      Fetching
                    </Badge>
                  )}
                  {quote.status === "complete" && (
                    <Badge variant="outline" className="text-green-600">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Complete
                    </Badge>
                  )}
                </div>
              </div>
              {quote.status === "complete" && (
                <div className="mt-3 text-sm text-muted-foreground">
                  Premium: ${quote.premium.toLocaleString()}/year
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );

  const renderCompareStep = () => (
    <div className="space-y-6">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Scale className="h-5 w-5 text-primary" />
            Compare Quotes
          </CardTitle>
          <CardDescription>
            Select the best quote to convert into a proposal
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {quotes.filter(q => q.status === "complete").map((quote) => (
              <div
                key={quote.carrier}
                onClick={() => setSelectedQuote(quote.carrier)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedQuote(quote.carrier);
                  }
                }}
                role="button"
                tabIndex={0}
                aria-pressed={selectedQuote === quote.carrier}
                className={`p-5 rounded-xl border-2 cursor-pointer transition-all ${
                  selectedQuote === quote.carrier
                    ? "border-primary bg-primary/5 shadow-lg"
                    : "border-border hover:border-muted-foreground"
                }`}
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <Shield className="h-6 w-6 text-primary" />
                    </div>
                    <span className="font-semibold">{quote.carrier}</span>
                  </div>
                  {selectedQuote === quote.carrier && (
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                  )}
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Annual Premium</span>
                    <span className="text-xl font-bold text-primary">
                      ${quote.premium.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Coverage</span>
                    <span>{quote.coverage}</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Deductible</span>
                    <span>${quote.deductible.toLocaleString()}</span>
                  </div>
                  
                  <Separator />
                  
                  <div className="space-y-1">
                    <span className="text-sm text-muted-foreground">Included Features:</span>
                    <div className="flex flex-wrap gap-1">
                      {quote.features.map((feature) => (
                        <Badge key={`${quote.carrier}-${feature}`} variant="secondary" className="text-xs">
                          {feature}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-3 pt-4">
            <Button variant="outline" onClick={resetFlow}>
              Start Over
            </Button>
            <Button
              onClick={generateProposal}
              disabled={!selectedQuote || isRunning}
              className="flex-1 bg-gradient-primary hover:opacity-90"
            >
              {isRunning ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating Proposal...
                </>
              ) : (
                <>
                  <FileText className="h-4 w-4 mr-2" />
                  Generate Proposal
                  <ArrowRight className="h-4 w-4 ml-2" />
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Visual Analysis - always show when quotes are complete */}
      <QuoteComparisonAnalysis quotes={quotes} />
      {hasExternalResult && (
        <p className="text-xs text-muted-foreground">
          External analysis data received and merged into this quote workflow.
        </p>
      )}

      {/* Detailed Coverage Schedule */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileCheck className="h-4 w-4 text-primary" />
            Policy Coverage Details
          </CardTitle>
          <CardDescription>
            Complete coverage schedule, limits, exclusions, and conditions for {INSURANCE_TYPES.find(t => t.id === insuranceType)?.name ?? "this policy type"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PolicyCoverageDetails insuranceType={insuranceType} />
        </CardContent>
      </Card>
    </div>
  );

  const renderProposalStep = () => {
    const quote = quotes.find(q => q.carrier === selectedQuote);
    const expirationDate = new Date(effectiveDate.getTime() + 365 * 24 * 60 * 60 * 1000);
    
    return (
      <div className="space-y-6">
        {/* Professional Insurance Proposal Document */}
        <div className="bg-white dark:bg-card rounded-xl border-2 border-border shadow-lg overflow-hidden">
          {/* Header Banner */}
          <div className="bg-gradient-to-r from-primary to-primary/80 text-primary-foreground p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-white/20 rounded-xl">
                  <Shield className="h-8 w-8" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold">Insurance Proposal</h1>
                  <p className="text-primary-foreground/80 text-sm">
                    {INSURANCE_TYPES.find(t => t.id === insuranceType)?.name}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-primary-foreground/80">Proposal #</p>
                <p className="font-mono font-bold">{proposalNumber.current}</p>
              </div>
            </div>
          </div>

          {/* Document Body */}
          <div className="p-6 space-y-6">
            {/* Status Badge */}
            <div className="flex items-center justify-between">
              <Badge className="bg-green-500/10 text-green-600 border-green-500/30 px-4 py-1">
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Ready for Review
              </Badge>
              <p className="text-sm text-muted-foreground">
                Generated on {today.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
              </p>
            </div>

            <Separator />

            {/* Carrier & Coverage Section */}
            {quote && (
              <>
                {/* Carrier Info */}
                <div className="bg-muted/30 rounded-xl p-5 border border-border">
                  <div className="flex items-center gap-4 mb-4">
                    <div className="p-3 rounded-xl bg-primary/10">
                      <Shield className="h-8 w-8 text-primary" />
                    </div>
                    <div>
                      <h2 className="text-xl font-bold text-foreground">{quote.carrier}</h2>
                      <p className="text-sm text-muted-foreground">Insurance Carrier</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div className="bg-background rounded-lg p-3">
                      <Award className="h-5 w-5 mx-auto text-amber-500 mb-1" />
                      <p className="text-xs text-muted-foreground">AM Best Rating</p>
                      <p className="font-bold text-foreground">A+ (Superior)</p>
                    </div>
                    <div className="bg-background rounded-lg p-3">
                      <Shield className="h-5 w-5 mx-auto text-blue-500 mb-1" />
                      <p className="text-xs text-muted-foreground">Years in Business</p>
                      <p className="font-bold text-foreground">75+ Years</p>
                    </div>
                    <div className="bg-background rounded-lg p-3">
                      <CheckSquare className="h-5 w-5 mx-auto text-green-500 mb-1" />
                      <p className="text-xs text-muted-foreground">Claims Satisfaction</p>
                      <p className="font-bold text-foreground">4.7/5.0</p>
                    </div>
                  </div>
                </div>

                {/* Premium & Coverage Details */}
                <div className="grid md:grid-cols-2 gap-4">
                  {/* Premium Card */}
                  <div className="bg-gradient-to-br from-green-500/10 to-green-600/5 rounded-xl p-5 border border-green-500/20">
                    <div className="flex items-center gap-2 mb-3">
                      <DollarSign className="h-5 w-5 text-green-600" />
                      <h3 className="font-semibold text-foreground">Premium Details</h3>
                    </div>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Annual Premium</span>
                        <span className="text-2xl font-bold text-green-600">${quote.premium.toLocaleString()}</span>
                      </div>
                      <Separator />
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Monthly Payment</span>
                        <span className="font-medium">${Math.round(quote.premium / 12).toLocaleString()}/mo</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Payment Options</span>
                        <span className="font-medium">Annual, Semi-Annual, Monthly</span>
                      </div>
                    </div>
                  </div>

                  {/* Coverage Card */}
                  <div className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 rounded-xl p-5 border border-blue-500/20">
                    <div className="flex items-center gap-2 mb-3">
                      <Shield className="h-5 w-5 text-blue-600" />
                      <h3 className="font-semibold text-foreground">Coverage Summary</h3>
                    </div>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="text-muted-foreground">Coverage Limit</span>
                        <span className="text-2xl font-bold text-blue-600">{quote.coverage}</span>
                      </div>
                      <Separator />
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Deductible</span>
                        <span className="font-medium">${quote.deductible.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Policy Term</span>
                        <span className="font-medium">12 Months</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Policy Dates */}
                <div className="bg-muted/20 rounded-xl p-5 border border-border">
                  <div className="flex items-center gap-2 mb-4">
                    <Calendar className="h-5 w-5 text-primary" />
                    <h3 className="font-semibold text-foreground">Policy Period</h3>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-background rounded-lg p-4">
                      <p className="text-xs text-muted-foreground mb-1">Effective Date</p>
                      <p className="font-bold text-lg text-foreground">
                        {effectiveDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                      </p>
                    </div>
                    <div className="bg-background rounded-lg p-4">
                      <p className="text-xs text-muted-foreground mb-1">Expiration Date</p>
                      <p className="font-bold text-lg text-foreground">
                        {expirationDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Included Features */}
                <div className="bg-muted/20 rounded-xl p-5 border border-border">
                  <div className="flex items-center gap-2 mb-4">
                    <FileCheck className="h-5 w-5 text-primary" />
                    <h3 className="font-semibold text-foreground">Included Benefits & Features</h3>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {quote.features.map((feature) => (
                      <div key={`${quote.carrier}-benefit-${feature}`} className="flex items-center gap-2 bg-background rounded-lg p-3">
                        <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                        <span className="text-sm text-foreground">{feature}</span>
                      </div>
                    ))}
                    <div className="flex items-center gap-2 bg-background rounded-lg p-3">
                      <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                      <span className="text-sm text-foreground">24/7 Customer Support</span>
                    </div>
                    <div className="flex items-center gap-2 bg-background rounded-lg p-3">
                      <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
                      <span className="text-sm text-foreground">Online Policy Management</span>
                    </div>
                  </div>
                </div>

                {/* Detailed Coverage Schedule - New Section */}
                <PolicyCoverageDetails insuranceType={insuranceType} />
              </>
            )}

            <Separator />

            {/* Insured Information */}
            <div className="bg-muted/20 rounded-xl p-5 border border-border">
              <div className="flex items-center gap-2 mb-4">
                <User className="h-5 w-5 text-primary" />
                <h3 className="font-semibold text-foreground">Named Insured</h3>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Full Name</p>
                      <p className="font-medium text-foreground">{applicantInfo.name ?? "N/A"}</p>
                    </div>
                  </div>
                  {applicantInfo.businessName && (
                    <div className="flex items-center gap-3">
                      <Briefcase className="h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="text-xs text-muted-foreground">Business Name</p>
                        <p className="font-medium text-foreground">{applicantInfo.businessName}</p>
                      </div>
                    </div>
                  )}
                  <div className="flex items-center gap-3">
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Address</p>
                      <p className="font-medium text-foreground">{applicantInfo.address ?? "N/A"}</p>
                    </div>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Mail className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Email Address</p>
                      <p className="font-medium text-foreground">{applicantInfo.email ?? "N/A"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-xs text-muted-foreground">Phone Number</p>
                      <p className="font-medium text-foreground">{applicantInfo.phone ?? "N/A"}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Terms & Conditions */}
            <div className="bg-amber-500/5 rounded-xl p-4 border border-amber-500/20">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm text-muted-foreground">
                  <p className="font-medium text-foreground mb-1">Important Notice</p>
                  <p>
                    This proposal is valid for 30 days from the date of issue. Coverage is subject to 
                    underwriting approval and policy terms and conditions. Please review all documents 
                    carefully before accepting. Contact your agent for any questions.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="bg-muted/30 px-6 py-4 border-t border-border">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <p>Document ID: {proposalNumber.current} | Generated by AI Quote Agent</p>
              <p>Page 1 of 1</p>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={resetFlow}>
            New Quote
          </Button>
          <Button 
            variant="outline"
            onClick={handleExportPdf}
            disabled={isExportingPdf}
          >
            {isExportingPdf ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Export PDF
          </Button>
          <Button 
            className="flex-1 bg-gradient-primary hover:opacity-90"
            onClick={() => setShowEmailPreview(true)}
          >
            <Eye className="h-4 w-4 mr-2" />
            Preview & Send Email
          </Button>
        </div>

        {/* Email Preview Dialog */}
        {quote && (
          <EmailPreviewDialog
            open={showEmailPreview}
            onOpenChange={setShowEmailPreview}
            onSend={handleSendProposal}
            proposalData={{
              recipientName: applicantInfo.name,
              recipientEmail: applicantInfo.email,
              carrierName: quote.carrier,
              premium: quote.premium,
              coverage: quote.coverage,
              deductible: quote.deductible,
              insuranceType: INSURANCE_TYPES.find(t => t.id === insuranceType)?.name ?? insuranceType,
              proposalNumber: proposalNumber.current,
              effectiveDate: effectiveDate,
            }}
          />
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {step === "input" && renderInputStep()}
      {step === "fetching" && renderFetchingStep()}
      {step === "compare" && renderCompareStep()}
      {step === "proposal" && renderProposalStep()}
    </div>
  );
}
