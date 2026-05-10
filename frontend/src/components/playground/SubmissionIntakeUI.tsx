import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText } from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";
import SubmissionForm from "./submission-intake/SubmissionForm";
import SubmissionResultCard from "./submission-intake/SubmissionResultCard";
import { parseSubmissionResult } from "./submission-intake/parseSubmissionResult";
import { SubmissionIntakeUIProps } from "./submission-intake/types";

export default function SubmissionIntakeUI({ onRun, isRunning, result }: SubmissionIntakeUIProps) {
  const handleSubmit = (data: { file: File | null; details: string; lineOfBusiness: string }) => {
    if (!data.details.trim()) return;
    onRun({
      type: "carrier-submission-intake",
      file: data.file?.name,
      details: data.details,
      lineOfBusiness: data.lineOfBusiness
    });
  };

  const parsedResult = result ? parseSubmissionResult(result) : null;

  return (
    <div className="space-y-6">
      <SubmissionForm onSubmit={handleSubmit} isRunning={isRunning} />

      {result && (
        <div className="space-y-6">
          {/* Visual Submission Summary Card */}
          {parsedResult && <SubmissionResultCard submission={parsedResult} />}

          {/* Raw Analysis */}
          <Card className="bg-card border-border overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500 delay-150">
            <CardHeader className="bg-gradient-to-r from-muted/50 to-transparent border-b border-border/50">
              <CardTitle className="text-lg text-card-foreground flex items-center gap-2">
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
