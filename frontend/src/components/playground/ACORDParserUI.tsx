import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Upload, FileText, Loader2, FileCheck } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import MarkdownRenderer from "./MarkdownRenderer";
import OutputCorrection from "./OutputCorrection";

interface ACORDParserUIProps {
  modelId?: string;
  onRun: (data: any) => void;
  isRunning: boolean;
  result: string;
}

export default function ACORDParserUI({ modelId, onRun, isRunning, result }: ACORDParserUIProps) {
  const [file, setFile] = useState<File | null>(null);
  const [formType, setFormType] = useState<string>("25");
  const [lastInput, setLastInput] = useState("");

  const handleRun = () => {
    if (!file) return;
    const inputDesc = `Parse ACORD ${formType}: ${file.name}`;
    setLastInput(inputDesc);
    onRun({
      type: "acord-parser",
      file: file.name,
      formType
    });
  };

  return (
    <div className="space-y-6">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Upload ACORD Form
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="form-type">ACORD Form Type</Label>
            <Select value={formType} onValueChange={setFormType}>
              <SelectTrigger>
                <SelectValue placeholder="Select form type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="25">ACORD 25 - Certificate of Insurance</SelectItem>
                <SelectItem value="27">ACORD 27 - Evidence of Property Insurance</SelectItem>
                <SelectItem value="80">ACORD 80 - Garage Coverage Summary</SelectItem>
                <SelectItem value="85">ACORD 85 - General Liability Application</SelectItem>
                <SelectItem value="90">ACORD 90 - Automobile Application</SelectItem>
                <SelectItem value="125">ACORD 125 - Commercial Insurance Application</SelectItem>
                <SelectItem value="126">ACORD 126 - Commercial General Liability</SelectItem>
                <SelectItem value="140">ACORD 140 - Property Loss Notice</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="acord-file">Upload Document</Label>
            <Input
              id="acord-file"
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            {file && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <FileText className="h-4 w-4" />
                {file.name}
              </div>
            )}
          </div>

          <Button
            onClick={handleRun}
            disabled={!file || isRunning}
            className="w-full bg-gradient-primary hover:opacity-90"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Parsing...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-2" />
                Parse ACORD Form
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
              Parsed Data
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <OutputCorrection modelId={modelId || "acord-parser"} prompt={lastInput} output={result}>
              <MarkdownRenderer content={result} />
            </OutputCorrection>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
