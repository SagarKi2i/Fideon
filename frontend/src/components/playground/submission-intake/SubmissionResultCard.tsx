import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  Inbox, Building2, FileText, Calendar, DollarSign, 
  ArrowRight, User, Clock, Send
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ParsedSubmission } from "./types";
import SubmissionStatusStepper from "./SubmissionStatusStepper";
import AppetiteMatchGauge from "./AppetiteMatchGauge";
import RiskFactorsList from "./RiskFactorsList";

interface SubmissionResultCardProps {
  submission: ParsedSubmission;
}

export default function SubmissionResultCard({ submission }: SubmissionResultCardProps) {
  const getPriorityConfig = (priority: string) => {
    switch (priority) {
      case "high":
        return { 
          bg: "bg-red-500/10", 
          text: "text-red-500", 
          border: "border-red-500/30",
          dot: "bg-red-500"
        };
      case "medium":
        return { 
          bg: "bg-amber-500/10", 
          text: "text-amber-500", 
          border: "border-amber-500/30",
          dot: "bg-amber-500"
        };
      case "low":
        return { 
          bg: "bg-green-500/10", 
          text: "text-green-500", 
          border: "border-green-500/30",
          dot: "bg-green-500"
        };
      default:
        return { 
          bg: "bg-muted", 
          text: "text-muted-foreground", 
          border: "border-border",
          dot: "bg-muted-foreground"
        };
    }
  };

  const priorityConfig = getPriorityConfig(submission.priority);

  return (
    <Card className="bg-card border-border overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Header with gradient */}
      <CardHeader className="bg-gradient-to-br from-primary/10 via-accent/5 to-transparent border-b border-border/50 pb-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-2xl bg-gradient-to-br from-primary/20 to-accent/20 shadow-lg">
              <Inbox className="h-7 w-7 text-primary" />
            </div>
            <div>
              <CardTitle className="text-2xl font-bold">{submission.submissionId}</CardTitle>
              <p className="text-lg text-muted-foreground mt-0.5">{submission.insuredName}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge 
              variant="outline" 
              className={`${priorityConfig.bg} ${priorityConfig.text} ${priorityConfig.border} gap-1.5 px-3 py-1`}
            >
              <span className={`w-2 h-2 rounded-full ${priorityConfig.dot} animate-pulse`} />
              {submission.priority.toUpperCase()} PRIORITY
            </Badge>
            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/30 px-3 py-1">
              <Clock className="h-3.5 w-3.5 mr-1.5" />
              {submission.receivedDate}
            </Badge>
          </div>
        </div>

        {/* Status Stepper */}
        <div className="mt-6">
          <SubmissionStatusStepper status={submission.status} />
        </div>
      </CardHeader>

      <CardContent className="p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Key Details */}
          <div className="space-y-6">
            <div>
              <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider mb-4">
                Submission Details
              </h4>
              <div className="space-y-4">
                <DetailRow 
                  icon={Building2} 
                  label="Broker" 
                  value={submission.broker} 
                />
                <DetailRow 
                  icon={FileText} 
                  label="Line of Business" 
                  value={submission.lineOfBusiness} 
                />
                <DetailRow 
                  icon={Calendar} 
                  label="Policy Period" 
                  value={`${submission.effectiveDate} → ${submission.expirationDate}`} 
                />
                <DetailRow 
                  icon={DollarSign} 
                  label="Premium Estimate" 
                  value={submission.premiumEstimate}
                  highlight
                />
              </div>
            </div>

            {/* Documents */}
            <div>
              <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider mb-3">
                Documents Received
              </h4>
              <div className="flex flex-wrap gap-2">
                {submission.documents.map((doc, idx) => (
                  <Badge 
                    key={idx} 
                    variant="secondary" 
                    className="text-xs px-2.5 py-1 bg-muted/50"
                  >
                    <FileText className="h-3 w-3 mr-1.5" />
                    {doc}
                  </Badge>
                ))}
              </div>
            </div>
          </div>

          {/* Center Column - Appetite Match & Risk Factors */}
          <div className="space-y-6">
            <div>
              <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider mb-4 text-center">
                Appetite Match
              </h4>
              <div className="flex justify-center">
                <AppetiteMatchGauge score={submission.appetiteMatch} />
              </div>
            </div>

            <div>
              <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider mb-3">
                Risk Factors
              </h4>
              <RiskFactorsList factors={submission.riskFactors} />
            </div>
          </div>

          {/* Right Column - Next Steps & Actions */}
          <div className="space-y-6">
            <div>
              <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider mb-4">
                Recommended Actions
              </h4>
              <div className="space-y-3">
                {submission.nextSteps.map((step, idx) => (
                  <div 
                    key={idx} 
                    className="flex items-start gap-3 p-3 rounded-lg bg-muted/30 border border-border/50 hover:bg-muted/50 transition-colors"
                  >
                    <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <span className="text-xs font-semibold text-primary">{idx + 1}</span>
                    </div>
                    <span className="text-sm">{step}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Assignment Card */}
            {submission.assignedUnderwriter && (
              <div className="p-4 rounded-xl bg-gradient-to-br from-green-500/10 to-emerald-500/5 border border-green-500/20">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-green-500/20">
                    <User className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-xs text-green-600 uppercase tracking-wide font-medium">
                      Assigned Underwriter
                    </p>
                    <p className="font-semibold text-green-700">{submission.assignedUnderwriter}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Quick Actions */}
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="flex-1">
                <Send className="h-4 w-4 mr-1.5" />
                Request Info
              </Button>
              <Button size="sm" className="flex-1">
                <ArrowRight className="h-4 w-4 mr-1.5" />
                Start Quote
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function DetailRow({ 
  icon: Icon, 
  label, 
  value, 
  highlight = false 
}: { 
  icon: React.ElementType; 
  label: string; 
  value: string; 
  highlight?: boolean;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="p-2 rounded-lg bg-muted">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={`font-medium ${highlight ? "text-primary" : ""} truncate`}>
          {value}
        </p>
      </div>
    </div>
  );
}
