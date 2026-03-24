import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { ParsedSubmission } from "./types";

interface RiskFactorsListProps {
  readonly factors: ParsedSubmission["riskFactors"];
}

export default function RiskFactorsList({ factors }: RiskFactorsListProps) {
  const getStatusConfig = (status: string) => {
    switch (status) {
      case "good":
        return {
          icon: CheckCircle2,
          bgColor: "bg-green-500/10",
          borderColor: "border-green-500/20",
          textColor: "text-green-600",
          iconColor: "text-green-500",
        };
      case "warning":
        return {
          icon: AlertTriangle,
          bgColor: "bg-amber-500/10",
          borderColor: "border-amber-500/20",
          textColor: "text-amber-600",
          iconColor: "text-amber-500",
        };
      case "critical":
        return {
          icon: XCircle,
          bgColor: "bg-red-500/10",
          borderColor: "border-red-500/20",
          textColor: "text-red-600",
          iconColor: "text-red-500",
        };
      default:
        return {
          icon: CheckCircle2,
          bgColor: "bg-muted",
          borderColor: "border-border",
          textColor: "text-muted-foreground",
          iconColor: "text-muted-foreground",
        };
    }
  };

  return (
    <div className="space-y-2">
      {factors.map((factor) => {
        const config = getStatusConfig(factor.status);
        const Icon = config.icon;

        return (
          <div
            key={`${factor.label}-${factor.status}`}
            className={`
              flex items-center gap-3 p-3 rounded-lg border transition-all duration-200
              ${config.bgColor} ${config.borderColor}
              hover:scale-[1.02] cursor-default
            `}
          >
            <Icon className={`h-4 w-4 flex-shrink-0 ${config.iconColor}`} />
            <span className={`text-sm font-medium ${config.textColor}`}>
              {factor.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
