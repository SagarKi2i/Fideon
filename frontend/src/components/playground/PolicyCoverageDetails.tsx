import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { 
  Shield, 
  Heart, 
  Car, 
  Wrench, 
  Home, 
  Building, 
  Package, 
  Clock, 
  DollarSign, 
  Users, 
  Briefcase, 
  Plus,
  AlertTriangle,
  FileText,
  CheckCircle2,
  XCircle
} from "lucide-react";
import { getInsuranceCoverage, type CoverageSection } from "./insuranceCoverageData";

interface PolicyCoverageDetailsProps {
  readonly insuranceType: string;
}

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  shield: Shield,
  heart: Heart,
  car: Car,
  wrench: Wrench,
  home: Home,
  building: Building,
  package: Package,
  clock: Clock,
  dollar: DollarSign,
  users: Users,
  briefcase: Briefcase,
  plus: Plus,
};

export default function PolicyCoverageDetails({ 
  insuranceType
}: PolicyCoverageDetailsProps) {
  const coverageData = getInsuranceCoverage(insuranceType);

  if (!coverageData) {
    return null;
  }

  const renderSection = (section: CoverageSection) => {
    const IconComponent = ICON_MAP[section.icon] ?? Shield;

    return (
      <div key={section.title} className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-primary/10">
            <IconComponent className="h-4 w-4 text-primary" />
          </div>
          <h4 className="font-semibold text-foreground text-sm">{section.title}</h4>
        </div>
        <div className="bg-background rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left py-2 px-3 font-medium text-muted-foreground">Coverage</th>
                <th className="text-right py-2 px-3 font-medium text-muted-foreground">Limit</th>
              </tr>
            </thead>
            <tbody>
              {section.items.map((item: any) => (
                <tr key={item.name} className="border-t border-border/50 hover:bg-muted/30 transition-colors">
                  <td className="py-2.5 px-3">
                    <div>
                      <p className="font-medium text-foreground">{item.name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{item.description}</p>
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <Badge variant="outline" className="font-mono text-xs bg-primary/5 text-primary border-primary/20">
                      {item.limit}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* Coverage Schedule Header */}
      <div className="bg-gradient-to-r from-primary/10 to-primary/5 rounded-xl p-4 border border-primary/20">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-primary/20">
            <FileText className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h3 className="font-bold text-lg text-foreground">Declarations & Coverage Schedule</h3>
            <p className="text-sm text-muted-foreground">Detailed coverage limits and policy provisions</p>
          </div>
        </div>
      </div>

      {/* Coverage Sections */}
      <div className="grid gap-4">
        {coverageData.sections.map((section: any) => renderSection(section))}
      </div>

      <Separator />

      {/* Exclusions */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-destructive/10">
            <XCircle className="h-4 w-4 text-destructive" />
          </div>
          <h4 className="font-semibold text-foreground text-sm">Policy Exclusions</h4>
        </div>
        <div className="bg-destructive/5 rounded-lg p-4 border border-destructive/20">
          <p className="text-xs text-muted-foreground mb-3">
            The following are NOT covered under this policy:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {coverageData.exclusions.map((exclusion: any) => (
              <div key={exclusion} className="flex items-start gap-2 text-sm">
                <XCircle className="h-3.5 w-3.5 text-destructive flex-shrink-0 mt-0.5" />
                <span className="text-foreground/80">{exclusion}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Policy Conditions */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-amber-500/10">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
          </div>
          <h4 className="font-semibold text-foreground text-sm">Policy Conditions</h4>
        </div>
        <div className="bg-amber-500/5 rounded-lg p-4 border border-amber-500/20">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {coverageData.conditions.map((condition: any) => (
              <div key={condition} className="flex items-start gap-2 text-sm">
                <CheckCircle2 className="h-3.5 w-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
                <span className="text-foreground/80">{condition}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Legal Notice */}
      <div className="bg-muted/30 rounded-lg p-4 border border-border text-xs text-muted-foreground">
        <p className="font-medium text-foreground mb-1">Policy Form & Endorsements</p>
        <p>
          This declarations page provides a summary of coverages. Complete policy terms, conditions, 
          and exclusions are contained in the policy form and endorsements. In the event of a conflict 
          between this summary and the policy, the policy shall control. Please read your policy carefully 
          and contact your agent with any questions.
        </p>
      </div>
    </div>
  );
}
