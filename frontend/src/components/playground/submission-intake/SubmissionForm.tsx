import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Upload, Inbox, Loader2, FileUp, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface SubmissionFormProps {
  onSubmit: (data: { file: File | null; details: string; lineOfBusiness: string }) => void;
  isRunning: boolean;
}

const lineOfBusinessOptions = [
  { value: "commercial-package", label: "Commercial Package", icon: "📦" },
  { value: "general-liability", label: "General Liability", icon: "🛡️" },
  { value: "property", label: "Property", icon: "🏢" },
  { value: "workers-comp", label: "Workers Compensation", icon: "👷" },
  { value: "professional-liability", label: "Professional Liability", icon: "💼" },
  { value: "cyber", label: "Cyber Liability", icon: "🔐" },
  { value: "auto", label: "Commercial Auto", icon: "🚛" },
];

export default function SubmissionForm({ onSubmit, isRunning }: SubmissionFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [submissionDetails, setSubmissionDetails] = useState("");
  const [lineOfBusiness, setLineOfBusiness] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);

  const handleSubmit = () => {
    if (!submissionDetails.trim()) return;
    onSubmit({ file, details: submissionDetails, lineOfBusiness });
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) setFile(droppedFile);
  };

  return (
    <Card className="bg-card border-border overflow-hidden">
      <CardHeader className="bg-gradient-to-br from-primary/5 via-accent/5 to-transparent border-b border-border/50">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 shadow-lg">
            <Inbox className="h-6 w-6 text-primary" />
          </div>
          <div>
            <CardTitle className="text-xl text-card-foreground flex items-center gap-2">
              Submission Intake
              <Badge variant="secondary" className="text-xs font-normal">
                <Sparkles className="h-3 w-3 mr-1" />
                AI-Powered
              </Badge>
            </CardTitle>
            <CardDescription className="mt-1">
              Upload documents and describe the submission for intelligent triage
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-6 space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Line of Business */}
          <div className="space-y-2">
            <Label htmlFor="lob" className="text-sm font-medium">Line of Business</Label>
            <Select value={lineOfBusiness} onValueChange={setLineOfBusiness}>
              <SelectTrigger className="h-11">
                <SelectValue placeholder="Select line of business" />
              </SelectTrigger>
              <SelectContent>
                {lineOfBusinessOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    <span className="flex items-center gap-2">
                      <span>{option.icon}</span>
                      <span>{option.label}</span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* File Upload */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">Submission Documents</Label>
            <div
              className={`relative border-2 border-dashed rounded-xl p-4 transition-all duration-200 cursor-pointer ${
                isDragOver 
                  ? "border-primary bg-primary/5 scale-[1.02]" 
                  : file 
                    ? "border-green-500/50 bg-green-500/5" 
                    : "border-border hover:border-primary/50 hover:bg-muted/50"
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <Input
                id="submission-file"
                type="file"
                accept=".pdf,.docx,.xlsx,.zip"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="absolute inset-0 opacity-0 cursor-pointer"
              />
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${file ? "bg-green-500/10" : "bg-muted"}`}>
                  {file ? (
                    <FileUp className="h-5 w-5 text-green-500" />
                  ) : (
                    <Upload className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  {file ? (
                    <p className="text-sm font-medium text-green-600 truncate">{file.name}</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Drop files here or <span className="text-primary font-medium">browse</span>
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-0.5">PDF, DOCX, XLSX, ZIP</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Submission Details */}
        <div className="space-y-2">
          <Label htmlFor="submission-details" className="text-sm font-medium">
            Submission Details / Email Content
          </Label>
          <Textarea
            id="submission-details"
            placeholder="Paste the broker's submission email or describe the risk details including insured name, effective dates, coverage requested, and any special requirements..."
            value={submissionDetails}
            onChange={(e) => setSubmissionDetails(e.target.value)}
            className="min-h-[140px] resize-none"
          />
          <p className="text-xs text-muted-foreground">
            Include insured name, effective dates, coverage limits, and any special requirements
          </p>
        </div>

        <Button
          onClick={handleSubmit}
          disabled={!submissionDetails.trim() || isRunning}
          className="w-full h-12 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 shadow-lg shadow-primary/20 transition-all duration-200"
          size="lg"
        >
          {isRunning ? (
            <>
              <Loader2 className="h-5 w-5 mr-2 animate-spin" />
              Processing Submission...
            </>
          ) : (
            <>
              <Sparkles className="h-5 w-5 mr-2" />
              Analyze Submission
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
