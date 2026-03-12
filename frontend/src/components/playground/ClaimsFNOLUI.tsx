import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Upload, AlertCircle, Loader2, FileCheck } from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";

interface ClaimsFNOLUIProps {
  onRun: (data: any) => void;
  isRunning: boolean;
  result: string;
}

export default function ClaimsFNOLUI({ onRun, isRunning, result }: ClaimsFNOLUIProps) {
  const [file, setFile] = useState<File | null>(null);
  const [claimDescription, setClaimDescription] = useState("");

  const handleRun = () => {
    if (!claimDescription.trim()) return;
    onRun({
      type: "claims-fnol",
      file: file?.name,
      description: claimDescription
    });
  };

  return (
    <div className="space-y-6">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            First Notice of Loss (FNOL)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="claim-desc">Claim Description</Label>
            <Textarea
              id="claim-desc"
              placeholder="Describe the incident, date, location, parties involved, and damages..."
              value={claimDescription}
              onChange={(e) => setClaimDescription(e.target.value)}
              className="min-h-[120px]"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="fnol-file">Supporting Documents (Optional)</Label>
            <Input
              id="fnol-file"
              type="file"
              accept=".pdf,.docx,.jpg,.png"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Upload className="h-4 w-4" />
                {file.name}
              </div>
            )}
          </div>

          <Button
            onClick={handleRun}
            disabled={!claimDescription.trim() || isRunning}
            className="w-full bg-gradient-primary hover:opacity-90"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Analyzing Claim...
              </>
            ) : (
              <>
                <AlertCircle className="h-4 w-4 mr-2" />
                Analyze FNOL
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <Card className="bg-card border-border animate-fade-in">
          <CardHeader className="bg-gradient-to-r from-primary/5 to-transparent">
            <CardTitle className="text-card-foreground flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-primary" />
              FNOL Analysis Report
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <MarkdownRenderer content={result} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
