import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Play, Loader2, Sparkles } from "lucide-react";
import MarkdownRenderer from "./MarkdownRenderer";
import OutputCorrection from "./OutputCorrection";

interface GenericPromptUIProps {
  modelName: string;
  modelId?: string;
  onRun: (data: any) => void;
  isRunning: boolean;
  result: string;
}

export default function GenericPromptUI({ modelName, modelId, onRun, isRunning, result }: GenericPromptUIProps) {
  const [prompt, setPrompt] = useState("");
  const [lastPrompt, setLastPrompt] = useState("");

  const handleRun = () => {
    if (!prompt.trim()) return;
    setLastPrompt(prompt);
    onRun({
      type: "generic",
      prompt
    });
  };

  return (
    <div className="space-y-6">
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-card-foreground flex items-center gap-2">
            <Sparkles className="h-5 w-5" />
            {modelName}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="prompt">Enter Your Prompt</Label>
            <Textarea
              id="prompt"
              placeholder="Describe what you need help with..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="min-h-[150px]"
            />
          </div>

          <Button
            onClick={handleRun}
            disabled={!prompt.trim() || isRunning}
            className="w-full bg-gradient-primary hover:opacity-90"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Run Prompt
              </>
            )}
          </Button>

          <div className="bg-muted/50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-foreground mb-2">💡 Quick Tips</h4>
            <ul className="text-xs text-muted-foreground space-y-1">
              <li>• Be specific and detailed in your prompts</li>
              <li>• Include relevant context and requirements</li>
              <li>• Break complex tasks into smaller steps</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {result && (
        <Card className="bg-card border-border animate-fade-in">
          <CardHeader className="bg-gradient-to-r from-primary/5 to-transparent">
            <CardTitle className="text-card-foreground flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Result
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <OutputCorrection
              modelId={modelId || "generic"}
              prompt={lastPrompt}
              output={result}
            >
              <MarkdownRenderer content={result} />
            </OutputCorrection>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
