import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Building2, FolderOpen, CheckCircle2, FileCheck, File, FileBadge, ScrollText, Receipt, FileSpreadsheet, ClipboardList, BarChart3, Workflow, Loader2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";

import appliedEpicLogo from "@/assets/logos/applied-epic-logo.png";
import hawksoftLogo from "@/assets/logos/hawksoft-logo.png";
import ams360Logo from "@/assets/logos/ams360-logo.png";
import qqCatalystLogo from "@/assets/logos/qq-catalyst-logo.png";
import ezlynxLogo from "@/assets/logos/ezlynx-logo.png";

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

const amsOptions = [
  { id: "applied-epic", name: "Applied Epic", logo: appliedEpicLogo },
  { id: "hawksoft", name: "HawkSoft", logo: hawksoftLogo },
  { id: "ams360", name: "AMS 360", logo: ams360Logo },
  { id: "qq-catalyst", name: "QQ Catalyst", logo: qqCatalystLogo },
  { id: "ezlynx", name: "EZLynx", logo: ezlynxLogo },
];

const INSURANCE_TYPES = [
  { id: "auto", name: "Auto Insurance" },
  { id: "home", name: "Homeowners Insurance" },
  { id: "commercial", name: "Commercial Property" },
  { id: "general-liability", name: "General Liability" },
  { id: "workers-comp", name: "Workers Compensation" },
  { id: "professional-liability", name: "Professional Liability" },
];

const QUOTE_CARRIERS = [
  { id: "progressive", name: "Progressive" },
  { id: "geico", name: "GEICO" },
  { id: "state-farm", name: "State Farm" },
  { id: "allstate", name: "Allstate" },
  { id: "liberty-mutual", name: "Liberty Mutual" },
  { id: "travelers", name: "Travelers" },
  { id: "nationwide", name: "Nationwide" },
  { id: "farmers", name: "Farmers" },
  { id: "hartford", name: "The Hartford" },
  { id: "chubb", name: "Chubb" },
  { id: "aig", name: "AIG" },
  { id: "zurich", name: "Zurich" },
  { id: "hanover", name: "The Hanover" },
  { id: "cincinnati", name: "Cincinnati" },
  { id: "erie", name: "Erie" },
  { id: "auto-owners", name: "Auto-Owners" },
  { id: "usaa", name: "USAA" },
  { id: "american-family", name: "American Family" },
];

const CLAIM_TYPES = [
  { id: "property-fire", name: "Property - Fire" },
  { id: "property-water", name: "Property - Water Damage" },
  { id: "property-weather", name: "Property - Weather/Storm" },
  { id: "liability-bodily", name: "Liability - Bodily Injury" },
  { id: "liability-property", name: "Liability - Property Damage" },
  { id: "auto-collision", name: "Auto - Collision" },
  { id: "auto-comprehensive", name: "Auto - Comprehensive" },
  { id: "workers-comp", name: "Workers Compensation" },
  { id: "professional", name: "Professional Liability" },
];

export interface AgentConfig {
  [key: string]: any;
}

interface AgentConfigFormProps {
  readonly agentId: string;
  readonly config: AgentConfig;
  readonly onChange: (config: AgentConfig) => void;
}

interface AgentSectionProps {
  readonly config: AgentConfig;
  readonly onChange: (config: AgentConfig) => void;
}

// ==================== Document Retrieval Config ====================
function DocumentRetrievalConfig({ config, onChange }: AgentSectionProps) {
  const selectedCarriers: string[] = config.carriers || [];
  const selectedDocTypes: string[] = config.documentTypes || [];
  const selectedAMS: string = config.ams || "";

  return (
    <div className="space-y-4">
      {/* Carriers */}
      <div className="space-y-1.5">
        <Label className="text-xs flex items-center gap-1"><Building2 className="h-3 w-3" /> Carriers {selectedCarriers.length > 0 && <Badge variant="secondary" className="text-[10px] ml-1">{selectedCarriers.length}</Badge>}</Label>
        <div className="grid grid-cols-5 gap-1.5">
          {carriers.map(c => (
            <button key={c.id} type="button"
              onClick={() => onChange({ ...config, carriers: selectedCarriers.includes(c.id) ? selectedCarriers.filter(x => x !== c.id) : [...selectedCarriers, c.id] })}
              className={`flex flex-col items-center gap-0.5 p-2 rounded-lg border text-center transition-all ${selectedCarriers.includes(c.id) ? "border-primary bg-primary/10 ring-1 ring-primary" : "border-border hover:border-primary/50"}`}>
              {selectedCarriers.includes(c.id) && <CheckCircle2 className="h-3 w-3 text-primary absolute top-0.5 right-0.5" />}
              <span className="text-lg">{c.logo}</span>
              <span className="text-[10px] font-medium truncate w-full">{c.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* AMS */}
      <div className="space-y-1.5">
        <Label className="text-xs flex items-center gap-1"><FolderOpen className="h-3 w-3" /> Target AMS</Label>
        <div className="grid grid-cols-5 gap-1.5">
          {amsOptions.map(ams => (
            <button key={ams.id} type="button"
              onClick={() => onChange({ ...config, ams: ams.id })}
              className={`flex flex-col items-center gap-0.5 p-2 rounded-lg border transition-all ${selectedAMS === ams.id ? "border-primary bg-primary/10 ring-1 ring-primary" : "border-border hover:border-primary/50"}`}>
              <img src={ams.logo.src} alt={ams.name} className="h-6 w-6 object-contain" />
              <span className="text-[10px] font-medium truncate w-full">{ams.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Doc Types */}
      <div className="space-y-1.5">
        <Label className="text-xs">Document Types</Label>
        <div className="grid grid-cols-4 gap-1.5">
          {documentTypes.map(dt => {
            const Icon = dt.icon;
            return (
              <button key={dt.id} type="button"
                onClick={() => onChange({ ...config, documentTypes: selectedDocTypes.includes(dt.id) ? selectedDocTypes.filter(x => x !== dt.id) : [...selectedDocTypes, dt.id] })}
                className={`flex items-center gap-1.5 p-2 rounded-lg border text-xs transition-all ${selectedDocTypes.includes(dt.id) ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"}`}>
                <Icon className="h-3 w-3 flex-shrink-0" />
                <span className="truncate">{dt.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Policy / Insured */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1"><Label className="text-xs">Policy Number</Label><Input className="h-8 text-xs" placeholder="POL-2025-12345" value={config.policyNumber || ""} onChange={e => onChange({ ...config, policyNumber: e.target.value })} /></div>
        <div className="space-y-1"><Label className="text-xs">Insured Name</Label><Input className="h-8 text-xs" placeholder="ABC Corporation" value={config.insuredName || ""} onChange={e => onChange({ ...config, insuredName: e.target.value })} /></div>
      </div>
    </div>
  );
}

// ==================== Policy Comparison Config ====================
function PolicyComparisonConfig({ config, onChange }: AgentSectionProps) {
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Compares two policies side-by-side for coverage, limits, deductibles, and gaps.</p>
      <div className="space-y-1.5">
        <Label className="text-xs">Source</Label>
        <Select value={config.source || "previous_step"} onValueChange={v => onChange({ ...config, source: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="previous_step">From previous step output</SelectItem>
            <SelectItem value="upload">Upload files manually</SelectItem>
            <SelectItem value="documents">From stored documents</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Focus Areas</Label>
        <div className="flex flex-wrap gap-1.5">
          {["Premiums", "Deductibles", "Liability Limits", "Cyber Coverage", "EPL", "Water Damage"].map(area => {
            const selected = (config.focusAreas || []).includes(area);
            return (
              <button key={area} type="button"
                onClick={() => onChange({ ...config, focusAreas: selected ? (config.focusAreas || []).filter((a: string) => a !== area) : [...(config.focusAreas || []), area] })}
                className={`px-2 py-1 rounded-md border text-xs transition-all ${selected ? "border-primary bg-primary/10 text-primary" : "border-border hover:border-primary/50"}`}>
                {area}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ==================== Quote Generation Config ====================
function QuoteGenerationConfig({ config, onChange }: AgentSectionProps) {
  const selectedCarriers: string[] = config.carriers || [];
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Insurance Type</Label>
        <Select value={config.insuranceType || ""} onValueChange={v => onChange({ ...config, insuranceType: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Select type" /></SelectTrigger>
          <SelectContent>
            {INSURANCE_TYPES.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1"><Label className="text-xs">Applicant Name</Label><Input className="h-8 text-xs" placeholder="John Doe" value={config.applicantName || ""} onChange={e => onChange({ ...config, applicantName: e.target.value })} /></div>
        <div className="space-y-1"><Label className="text-xs">Business Name</Label><Input className="h-8 text-xs" placeholder="Acme Corp" value={config.businessName || ""} onChange={e => onChange({ ...config, businessName: e.target.value })} /></div>
        <div className="space-y-1"><Label className="text-xs">Email</Label><Input className="h-8 text-xs" placeholder="john@example.com" value={config.email || ""} onChange={e => onChange({ ...config, email: e.target.value })} /></div>
        <div className="space-y-1"><Label className="text-xs">Coverage Amount</Label><Input className="h-8 text-xs" placeholder="500000" value={config.coverageAmount || ""} onChange={e => onChange({ ...config, coverageAmount: e.target.value })} /></div>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Carriers to Quote {selectedCarriers.length > 0 && <Badge variant="secondary" className="text-[10px] ml-1">{selectedCarriers.length}</Badge>}</Label>
        <div className="grid grid-cols-3 gap-1.5 max-h-32 overflow-y-auto">
          {QUOTE_CARRIERS.map(c => (
            <button key={c.id} type="button"
              onClick={() => onChange({ ...config, carriers: selectedCarriers.includes(c.id) ? selectedCarriers.filter(x => x !== c.id) : [...selectedCarriers, c.id] })}
              className={`flex items-center gap-1.5 p-1.5 rounded-md border text-xs transition-all ${selectedCarriers.includes(c.id) ? "border-primary bg-primary/10" : "border-border hover:border-primary/50"}`}>
              <Checkbox checked={selectedCarriers.includes(c.id)} className="h-3 w-3 pointer-events-none" />
              <span className="truncate">{c.name}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ==================== Claims FNOL Config ====================
function ClaimsFNOLConfig({ config, onChange }: AgentSectionProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Claim Description</Label>
        <Textarea className="text-xs min-h-[80px]" placeholder="Describe the incident, date, location, parties involved, and damages..."
          value={config.description || ""} onChange={e => onChange({ ...config, description: e.target.value })} />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Source</Label>
        <Select value={config.source || "manual"} onValueChange={v => onChange({ ...config, source: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="manual">Manual input</SelectItem>
            <SelectItem value="previous_step">From previous step</SelectItem>
            <SelectItem value="email">From email/mailbox</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

// ==================== Claims Adjudication Config ====================
function ClaimsAdjudicationConfig({ config, onChange }: AgentSectionProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Claim Type</Label>
        <Select value={config.claimType || ""} onValueChange={v => onChange({ ...config, claimType: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Select claim type" /></SelectTrigger>
          <SelectContent>
            {CLAIM_TYPES.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Claim Details</Label>
        <Textarea className="text-xs min-h-[80px]" placeholder="Policy number, date of loss, cause, damage description..."
          value={config.details || ""} onChange={e => onChange({ ...config, details: e.target.value })} />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Input Source</Label>
        <Select value={config.source || "manual"} onValueChange={v => onChange({ ...config, source: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="manual">Manual input</SelectItem>
            <SelectItem value="previous_step">From previous step</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

// ==================== Submission Intake Config ====================
function SubmissionIntakeConfig({ config, onChange }: AgentSectionProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Line of Business</Label>
        <Select value={config.lineOfBusiness || ""} onValueChange={v => onChange({ ...config, lineOfBusiness: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Select" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="commercial-property">Commercial Property</SelectItem>
            <SelectItem value="general-liability">General Liability</SelectItem>
            <SelectItem value="workers-comp">Workers Compensation</SelectItem>
            <SelectItem value="professional-liability">Professional Liability</SelectItem>
            <SelectItem value="commercial-auto">Commercial Auto</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Submission Details</Label>
        <Textarea className="text-xs min-h-[80px]" placeholder="Business description, operations, employee count, revenue..."
          value={config.details || ""} onChange={e => onChange({ ...config, details: e.target.value })} />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Input Source</Label>
        <Select value={config.source || "manual"} onValueChange={v => onChange({ ...config, source: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="manual">Manual input</SelectItem>
            <SelectItem value="previous_step">From previous step</SelectItem>
            <SelectItem value="email">From email/mailbox</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

// ==================== Generic Agent Config ====================
function GenericAgentConfig({ config, onChange }: AgentSectionProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label className="text-xs">Prompt / Instructions</Label>
        <Textarea className="text-xs min-h-[80px]" placeholder="What should this agent do?"
          value={config.prompt || ""} onChange={e => onChange({ ...config, prompt: e.target.value })} />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">Input Source</Label>
        <Select value={config.source || "manual"} onValueChange={v => onChange({ ...config, source: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="manual">Manual input</SelectItem>
            <SelectItem value="previous_step">From previous step</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

// ==================== Custom Workflow Config ====================
function CustomWorkflowConfig({ config, onChange }: AgentSectionProps) {
  const [workflows, setWorkflows] = useState<{ id: string; title: string; description: string | null; category: string | null; steps_count: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;
        const { data } = await supabase.from("workflows").select("id, title, description, category, parsed_steps").eq("user_id", user.id).order("created_at", { ascending: false });
        if (data) {
          setWorkflows(data.map(w => ({
            id: w.id,
            title: w.title,
            description: w.description,
            category: w.category,
            steps_count: Array.isArray(w.parsed_steps) ? (w.parsed_steps as any[]).length : 0,
          })));
        }
      } catch (e) { console.error(e); }
      finally { setLoading(false); }
    };
    load();
  }, []);

  const selectedWorkflow = workflows.find(w => w.id === config.workflowId);

  if (loading) {
    return <div className="flex items-center justify-center py-4"><Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Embed a custom SOP workflow as a step in this pipeline. The workflow steps will execute in sequence.</p>
      <div className="space-y-1.5">
        <Label className="text-xs flex items-center gap-1"><Workflow className="h-3 w-3" /> Select Workflow</Label>
        {workflows.length === 0 ? (
          <div className="text-center py-4 border border-dashed border-border rounded-lg">
            <p className="text-xs text-muted-foreground">No custom workflows found. Create one in Custom Workflows first.</p>
          </div>
        ) : (
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {workflows.map(wf => (
              <button key={wf.id} type="button"
                onClick={() => onChange({ ...config, workflowId: wf.id, workflowTitle: wf.title })}
                className={`w-full flex items-center justify-between p-2.5 rounded-lg border text-left transition-all ${config.workflowId === wf.id ? "border-primary bg-primary/10 ring-1 ring-primary" : "border-border hover:border-primary/50"}`}>
                <div className="min-w-0">
                  <span className="text-xs font-medium block truncate">{wf.title}</span>
                  <span className="text-[10px] text-muted-foreground">{wf.steps_count} steps{wf.category ? ` · ${wf.category}` : ""}</span>
                </div>
                {config.workflowId === wf.id && <CheckCircle2 className="h-3.5 w-3.5 text-primary flex-shrink-0" />}
              </button>
            ))}
          </div>
        )}
      </div>
      {selectedWorkflow && (
        <div className="p-2 rounded-lg bg-muted/50 border border-border/50">
          <p className="text-xs font-medium">{selectedWorkflow.title}</p>
          {selectedWorkflow.description && <p className="text-[10px] text-muted-foreground mt-0.5">{selectedWorkflow.description}</p>}
          <p className="text-[10px] text-muted-foreground mt-1">{selectedWorkflow.steps_count} SOP steps will execute in this pipeline stage</p>
        </div>
      )}
      <div className="space-y-1.5">
        <Label className="text-xs">Input Source</Label>
        <Select value={config.source || "previous_step"} onValueChange={v => onChange({ ...config, source: v })}>
          <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="previous_step">From previous step</SelectItem>
            <SelectItem value="manual">Manual input</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}

// ==================== Main Router ====================
export default function AgentConfigForm({ agentId, config, onChange }: AgentConfigFormProps) {
  switch (agentId) {
    case "document-retrieval":
      return <DocumentRetrievalConfig config={config} onChange={onChange} />;
    case "policy-comparison":
      return <PolicyComparisonConfig config={config} onChange={onChange} />;
    case "quote-generation":
      return <QuoteGenerationConfig config={config} onChange={onChange} />;
    case "claims-fnol":
      return <ClaimsFNOLConfig config={config} onChange={onChange} />;
    case "carrier-claims-adjudication":
    case "carrier-claims-intake":
    case "carrier-fraud-detection":
    case "carrier-subrogation":
      return <ClaimsAdjudicationConfig config={config} onChange={onChange} />;
    case "carrier-submission-intake":
    case "carrier-submission-triage":
      return <SubmissionIntakeConfig config={config} onChange={onChange} />;
    case "custom-workflow":
      return <CustomWorkflowConfig config={config} onChange={onChange} />;
    default:
      return <GenericAgentConfig config={config} onChange={onChange} />;
  }
}

// Export agent metadata for the pipeline builder
export const AGENT_REGISTRY: { id: string; name: string; category: string; description: string }[] = [
  { id: "document-retrieval", name: "Document Retrieval", category: "Broker", description: "Download docs from carrier websites → AMS" },
  { id: "policy-comparison", name: "Policy Comparison", category: "Broker", description: "Side-by-side policy analysis with gap detection" },
  { id: "quote-generation", name: "Quote Generation", category: "Broker", description: "Multi-carrier quote fetching & comparison" },
  { id: "claims-fnol", name: "Claims FNOL", category: "Broker", description: "First Notice of Loss intake & analysis" },
  { id: "acord-parser", name: "ACORD Parser", category: "Broker", description: "Parse ACORD forms and extract structured data" },
  { id: "carrier-submission-intake", name: "Submission Intake", category: "Carrier", description: "Analyze submissions with appetite matching" },
  { id: "carrier-claims-adjudication", name: "Claims Adjudication", category: "Carrier", description: "Claim analysis with reserve & fraud detection" },
  { id: "carrier-fraud-detection", name: "Fraud Detection", category: "Carrier", description: "Analyze claims for fraud indicators" },
  { id: "carrier-subrogation", name: "Subrogation", category: "Carrier", description: "Identify subrogation recovery opportunities" },
  { id: "custom-workflow", name: "Custom Workflow", category: "Custom", description: "Embed a saved SOP workflow as a pipeline step" },
];
