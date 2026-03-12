import { ParsedSubmission } from "./types";

export function parseSubmissionResult(result: string): ParsedSubmission | null {
  try {
    // Mock parsing - in production this would parse actual AI response
    if (result.includes("Submission") || result.includes("submission")) {
      return {
        submissionId: "SUB-2025-" + Math.floor(Math.random() * 10000).toString().padStart(5, '0'),
        receivedDate: new Date().toISOString().split('T')[0],
        broker: "ABC Insurance Brokers",
        insuredName: "Tech Solutions Corp",
        lineOfBusiness: "Commercial Package",
        effectiveDate: "2025-03-01",
        expirationDate: "2026-03-01",
        premiumEstimate: "$45,000 - $52,000",
        appetiteMatch: 87,
        priority: "high",
        status: "triaged",
        assignedUnderwriter: "Sarah Chen",
        documents: ["ACORD 125", "ACORD 126", "Loss Runs", "Financial Statements", "SOV"],
        riskFactors: [
          { label: "Years in Business: 12", status: "good" },
          { label: "Loss Ratio: 42%", status: "good" },
          { label: "Revenue Growth: 25% YoY", status: "warning" },
          { label: "Territory: Coastal FL", status: "critical" },
          { label: "Prior Claims: 2 in 5 years", status: "warning" }
        ],
        nextSteps: [
          "Review SOV for TIV accuracy",
          "Request updated loss runs (60 days old)",
          "Verify coastal windstorm modeling",
          "Check reinsurance capacity for FL exposure"
        ]
      };
    }
    return null;
  } catch {
    return null;
  }
}
