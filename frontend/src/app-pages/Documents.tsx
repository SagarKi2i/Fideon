import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FileText, Upload } from "lucide-react";

export default function Documents() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Documents</h1>
        <p className="text-muted-foreground mt-1">
          Manage your uploaded files for AI processing
        </p>
      </div>

      <Card className="bg-card border-border shadow-card">
        <CardHeader>
          <CardTitle className="text-card-foreground">Document Library</CardTitle>
          <CardDescription>PDF, DOCX, TXT files for model analysis</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-12">
            <FileText className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-medium text-foreground mb-2">No Documents Yet</h3>
            <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
              Upload documents to use with your AI models for analysis and Q&A
            </p>
            <Button className="bg-gradient-primary hover:opacity-90 transition-opacity">
              <Upload className="h-4 w-4 mr-2" />
              Upload Document
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
