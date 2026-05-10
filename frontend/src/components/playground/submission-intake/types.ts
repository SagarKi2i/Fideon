export interface ParsedSubmission {
  submissionId: string;
  receivedDate: string;
  broker: string;
  insuredName: string;
  lineOfBusiness: string;
  effectiveDate: string;
  expirationDate: string;
  premiumEstimate: string;
  appetiteMatch: number;
  priority: "high" | "medium" | "low";
  status: "received" | "triaged" | "assigned" | "quoted" | "declined";
  assignedUnderwriter?: string;
  documents: string[];
  riskFactors: { label: string; status: "good" | "warning" | "critical" }[];
  nextSteps: string[];
}

export interface SubmissionIntakeUIProps {
  onRun: (data: any) => void;
  isRunning: boolean;
  result: string;
}
